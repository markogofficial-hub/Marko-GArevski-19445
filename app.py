"""
app.py  (Elasticsearch edition — stock market)
-----------------------------------------------
A small "stock market data" web app reading from Elasticsearch instead of
a SQL database. All data is fictional / for learning purposes only — this
is not financial advice and not real market data.

What changed vs. a SQL version?
  * No SQL and no JOINs. We send JSON query bodies to Elasticsearch's REST API
    through the official Python client.
  * "List companies with quarter/record counts" becomes a TERMS AGGREGATION
    instead of GROUP BY.
  * "Search" becomes a fuzzy, relevance-ranked multi_match query — it tolerates
    typos and ranks the best matches first (a plain LIKE query could not).

Routes
  GET  /                   -> home: totals + top sectors (an aggregation)
  GET  /companies          -> all companies with quarter/record counts (aggregation)
  GET  /companies/<name>   -> one company: its quarters and daily price records
  GET  /search?q=...       -> fuzzy full-text search across companies/symbols/sectors
  GET  /api/search?q=...   -> the same search, returned as raw JSON

Run (with an Elasticsearch URL + credentials already configured — see README):
  # set ES_URL / ES_PASSWORD first — see README
  python init_es.py        # load the data (once)
  python app.py            # then open http://127.0.0.1:5000

Deploying so you can share a link: see README.md, section "Putting it online".
"""

import os

from flask import Flask, render_template, request, jsonify, abort

from es_client import get_client
import init_es

app = Flask(__name__)

INDEX = "stocks"

# One client for the whole app. The client is thread-safe and pools connections.
es = get_client()


@app.route("/setup")
def setup():
    """
    Browser-only alternative to running 'python init_es.py' from a terminal.
    Visit this once after deploying (e.g. https://your-app.onrender.com/setup?key=...)
    to create the index and load the sample data — no local Python needed.

    Protected by the SETUP_KEY environment variable so random visitors can't
    reset your data. Set SETUP_KEY to anything you like in your host's
    environment variables, then put the same value in the URL's ?key=.
    """
    expected = os.environ.get("SETUP_KEY")
    if not expected:
        return "SETUP_KEY is not set on the server — add it in your host's environment variables first.", 503
    if request.args.get("key") != expected:
        abort(403)
    if not es.ping():
        return "Could not reach Elasticsearch. Check ES_URL / ES_PASSWORD.", 502
    count = init_es.load_data(es)
    return f"Done! Loaded {count} price records into the '{INDEX}' index. You can now use the app normally."


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    # size=0 -> we want aggregations only, not the documents themselves.
    resp = es.search(
        index=INDEX,
        size=0,
        aggs={
            "distinct_companies": {"cardinality": {"field": "company.keyword"}},
            "distinct_sectors":   {"cardinality": {"field": "sector"}},
            "top_sectors":        {"terms": {"field": "sector", "size": 10}},
        },
    )
    aggs = resp["aggregations"]
    stats = {
        "records":   resp["hits"]["total"]["value"],
        "companies": aggs["distinct_companies"]["value"],
        "sectors":   aggs["distinct_sectors"]["value"],
    }
    sectors = [
        {"name": b["key"], "count": b["doc_count"]}
        for b in aggs["top_sectors"]["buckets"]
    ]
    return render_template("index.html", stats=stats, sectors=sectors)


@app.route("/companies")
def companies():
    # Group by company; for each, count distinct quarters and grab its
    # ticker symbol + sector (constant per company in this dataset).
    resp = es.search(
        index=INDEX,
        size=0,
        aggs={
            "companies": {
                "terms": {"field": "company.keyword", "size": 100,
                          "order": {"_key": "asc"}},
                "aggs": {
                    "quarters": {"cardinality": {"field": "quarter"}},
                    "symbol":   {"terms": {"field": "symbol", "size": 1}},
                    "sector":   {"terms": {"field": "sector", "size": 1}},
                },
            }
        },
    )
    rows = [
        {
            "name": b["key"],
            "symbol": b["symbol"]["buckets"][0]["key"] if b["symbol"]["buckets"] else "",
            "sector": b["sector"]["buckets"][0]["key"] if b["sector"]["buckets"] else "",
            "quarter_count": b["quarters"]["value"],
            "record_count": b["doc_count"],
        }
        for b in resp["aggregations"]["companies"]["buckets"]
    ]
    return render_template("companies.html", companies=rows)


@app.route("/companies/<path:name>")
def company_detail(name: str):
    # Exact-match all price records for this company using the .keyword sub-field.
    resp = es.search(
        index=INDEX,
        size=100,
        query={"term": {"company.keyword": name}},
        sort=[{"date": "asc"}],
    )
    hits = resp["hits"]["hits"]
    if not hits:
        abort(404)

    # Group the flat price-record documents back into quarters (Python, not the DB).
    quarters = {}
    for h in hits:
        src = h["_source"]
        key = (src["quarter"], src.get("year"))
        quarters.setdefault(key, []).append(src)

    quarters_sorted = [
        {"label": label, "year": year, "records": records}
        for (label, year), records in sorted(quarters.items(), key=lambda kv: (kv[0][1], kv[0][0]))
    ]
    symbol = hits[0]["_source"].get("symbol", "")
    sector = hits[0]["_source"].get("sector", "")
    return render_template(
        "company_detail.html",
        company=name, symbol=symbol, sector=sector, quarters=quarters_sorted,
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        resp = es.search(index=INDEX, size=25, **_search_body(q))
        results = [
            {**h["_source"], "score": round(h["_score"], 2)}
            for h in resp["hits"]["hits"]
        ]
    return render_template("search.html", q=q, results=results)


@app.route("/api/search")
def api_search():
    """The same search, exposed as JSON — shows how ES feeds an API directly."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    resp = es.search(index=INDEX, size=25, **_search_body(q))
    return jsonify(
        [
            {**h["_source"], "score": h["_score"]}
            for h in resp["hits"]["hits"]
        ]
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def _search_body(q: str) -> dict:
    """
    A fuzzy, relevance-ranked search.

    * multi_match searches several fields at once.
    * The ^ numbers are BOOSTS: a hit in `company` counts 3x, `symbol` 2x.
    * fuzziness="AUTO" tolerates typos (e.g. "biotek" still finds "Biotech").
    """
    return {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["company^3", "symbol^2", "sector", "quarter"],
                "fuzziness": "AUTO",
            }
        }
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not es.ping():
        raise SystemExit(
            "Cannot reach Elasticsearch. Set ES_URL / ES_PASSWORD (see README) "
            "to point at a local Elasticsearch or an Elastic Cloud deployment, "
            "and load data with 'python init_es.py'."
        )
    # host=0.0.0.0 + the PORT env var let this same file run unchanged on
    # hosting platforms (Render, Railway, etc.) — see README, "Putting it online".
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
