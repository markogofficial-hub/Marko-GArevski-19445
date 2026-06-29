"""
init_es.py
-----------
Creates an Elasticsearch index and loads sample stock-market data into it.

Compared with a normalized SQL database, notice the modelling difference:

  * SQL  -> 3 normalized tables (companies, quarters, price_records) joined
            at query time.
  * ES   -> ONE "stocks" index where each document is DENORMALIZED: every
            daily price record already carries its company name, ticker
            symbol and sector inside it.

Denormalizing is the idiomatic Elasticsearch approach — you trade some
storage and update-complexity for very fast, join-free search.

Run once (after you have an Elasticsearch URL + credentials — see README):

    python init_es.py
"""

from elasticsearch import helpers

from es_client import get_client

INDEX = "stocks"


# ---------------------------------------------------------------------------
# Index mapping (the "schema")
# ---------------------------------------------------------------------------
# Text fields get a `.keyword` sub-field so the SAME field can be used two ways:
#   * `company`          -> analyzed text, for full-text/fuzzy search
#   * `company.keyword`  -> exact value, for aggregations, sorting, exact filters
MAPPING = {
    "mappings": {
        "properties": {
            "company":     {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "symbol":      {"type": "keyword"},
            "sector":      {"type": "keyword"},
            "quarter":     {"type": "keyword"},
            "year":        {"type": "integer"},
            "date":        {"type": "date"},
            "close_price": {"type": "float"},
            "volume":      {"type": "long"},
            "change_pct":  {"type": "float"},
        }
    }
}


# ---------------------------------------------------------------------------
# Seed data — a fictional set of companies, flattened into daily price
# records. None of this is real market data.
# ---------------------------------------------------------------------------
# (company, symbol, sector, quarter, year, date, close_price, volume, change_pct)
RAW = [
    ("NovaTech Systems",  "NVTC", "Technology",     "Q1 2024", 2024, "2024-01-05", 142.10, 5_200_000,  1.2),
    ("NovaTech Systems",  "NVTC", "Technology",     "Q1 2024", 2024, "2024-02-09", 138.40, 4_800_000, -0.8),
    ("NovaTech Systems",  "NVTC", "Technology",     "Q1 2024", 2024, "2024-03-15", 151.75, 6_100_000,  2.1),
    ("NovaTech Systems",  "NVTC", "Technology",     "Q2 2024", 2024, "2024-04-12", 149.90, 5_000_000, -0.5),
    ("NovaTech Systems",  "NVTC", "Technology",     "Q2 2024", 2024, "2024-05-17", 156.30, 5_500_000,  1.7),

    ("Cobalt Energy Corp", "CBLT", "Energy",        "Q1 2024", 2024, "2024-01-08", 64.20, 3_100_000,  0.4),
    ("Cobalt Energy Corp", "CBLT", "Energy",        "Q1 2024", 2024, "2024-02-14", 61.85, 2_900_000, -1.1),
    ("Cobalt Energy Corp", "CBLT", "Energy",        "Q1 2024", 2024, "2024-03-20", 67.10, 3_400_000,  1.9),

    ("Harbor Foods Inc",   "HRBF", "Consumer Goods", "Q1 2024", 2024, "2024-01-10", 28.55, 1_800_000,  0.2),
    ("Harbor Foods Inc",   "HRBF", "Consumer Goods", "Q1 2024", 2024, "2024-02-21", 27.90, 1_650_000, -0.3),

    ("BluePeak Software",  "BPKS", "Technology",     "Q1 2024", 2024, "2024-01-22", 88.40, 4_200_000,  3.0),
    ("BluePeak Software",  "BPKS", "Technology",     "Q1 2024", 2024, "2024-02-26", 92.15, 4_600_000,  1.4),
    ("BluePeak Software",  "BPKS", "Technology",     "Q1 2024", 2024, "2024-03-29", 85.60, 3_900_000, -2.2),
    ("BluePeak Software",  "BPKS", "Technology",     "Q2 2024", 2024, "2024-04-18", 90.75, 4_000_000,  1.1),

    ("Meridian Biotech",   "MRDB", "Healthcare",     "Q1 2024", 2024, "2024-01-30", 45.30, 2_200_000, -0.9),
    ("Meridian Biotech",   "MRDB", "Healthcare",     "Q1 2024", 2024, "2024-02-28", 47.80, 2_500_000,  1.6),
    ("Meridian Biotech",   "MRDB", "Healthcare",     "Q1 2024", 2024, "2024-03-25", 44.95, 2_100_000, -1.5),
    ("Meridian Biotech",   "MRDB", "Healthcare",     "Q2 2024", 2024, "2024-04-22", 49.10, 2_700_000,  2.0),
    ("Meridian Biotech",   "MRDB", "Healthcare",     "Q2 2024", 2024, "2024-05-30", 51.40, 2_900_000,  1.3),
]


def documents():
    """Turn each raw row into an Elasticsearch document."""
    for company, symbol, sector, quarter, year, date, close_price, volume, change_pct in RAW:
        yield {
            "company": company,
            "symbol": symbol,
            "sector": sector,
            "quarter": quarter,
            "year": year,
            "date": date,
            "close_price": close_price,
            "volume": volume,
            "change_pct": change_pct,
        }


def load_data(es) -> int:
    """
    Create the index (fresh) and bulk-load the seed documents.
    Returns the final document count. Shared by init_es.py (command line)
    and app.py's /setup route (a browser-only alternative — see README).
    """
    # Start clean so this is safe to re-run.
    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
    es.indices.create(index=INDEX, **MAPPING)

    # Bulk-load all documents in one request.
    actions = ({"_index": INDEX, "_source": doc} for doc in documents())
    helpers.bulk(es, actions)

    # Make the new docs searchable immediately (normally near-real-time).
    es.indices.refresh(index=INDEX)

    return es.count(index=INDEX)["count"]


def main() -> None:
    es = get_client()

    if not es.ping():
        raise SystemExit(
            "Could not reach Elasticsearch. Make sure ES_URL / ES_PASSWORD are "
            "set correctly (see README) and that your cluster — local or "
            "Elastic Cloud — is up."
        )

    count = load_data(es)
    print(f"Indexed documents into '{INDEX}'. Total now: {count}")


if __name__ == "__main__":
    main()
