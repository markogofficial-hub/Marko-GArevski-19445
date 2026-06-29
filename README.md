# Sample Web App — Stock Market (Elasticsearch + Kibana edition)

A stock-market learning app that uses **Elasticsearch** as the data store +
search engine, with **Kibana** for dashboards. All companies and prices are
**fictional sample data** — this is not real market data and not financial
advice.

What this app demonstrates:

| | Traditional SQL | This app |
|---|---|---|
| Data shape | tables, joined at query time | 1 index of denormalized JSON documents |
| Query language | SQL (`SELECT … JOIN … LIKE`) | Elasticsearch JSON DSL (`multi_match`, `terms` agg) |
| Search | exact substring | **fuzzy + relevance-ranked** (typos OK, best match first) |
| "Group by" | `GROUP BY` | **aggregations** |
| Visualization | hand-written HTML | **Kibana** dashboards, no code |

```
stock-market-app/
├── es_client.py         # builds the ES connection from env vars
├── init_es.py           # creates the index + loads data (run once)
├── app.py               # the Flask web app (queries Elasticsearch)
├── requirements.txt     # Flask + elasticsearch client + gunicorn
├── Procfile              # tells a hosting platform how to start the app
└── templates/            # HTML pages
```

---

## 1. Get an Elasticsearch URL + credentials

You have two options — pick one. Either way, the app talks to it through the
exact same three environment variables (`ES_URL`, `ES_USERNAME`, `ES_PASSWORD`).

### Option A — a local Elasticsearch (good for learning on your own machine)
Start it however you normally do, e.g. from your install directory:
```bash
bin/elasticsearch
bin/kibana          # in another terminal, optional
```
Then use `ES_URL=http://localhost:9200` (security off) or
`https://localhost:9200` + `ES_PASSWORD` (security on, the 8.x default).

### Option B — Elastic Cloud (needed if you want a link that works from
anywhere, not just your own computer)
1. Go to **elastic.co/cloud** and start a deployment. At the time of writing
   this is a free 14-day trial, no credit card required to start — but check
   the current terms on Elastic's site, since trial offers change.
2. Once the deployment is ready, copy its **Elasticsearch endpoint URL**
   (shown on the deployment's "Manage" page) and the **`elastic` user
   password** (shown once, right after creation — save it).
3. Use those as `ES_URL` and `ES_PASSWORD` below. `ES_CA_CERT` is not needed
   for Elastic Cloud.

## 2. Tell the app how to connect (environment variables)

**macOS / Linux:**
```bash
export ES_URL="https://localhost:9200"          # or your Elastic Cloud URL
export ES_PASSWORD="your-elastic-password"
# optional, local HTTPS only:
export ES_CA_CERT="/path/to/elasticsearch/config/certs/http_ca.crt"
```

**Windows (PowerShell):**
```powershell
$env:ES_URL = "https://localhost:9200"
$env:ES_PASSWORD = "your-elastic-password"
```

All variables are optional and have defaults (see `es_client.py`):
`ES_URL` → `https://localhost:9200`, `ES_USERNAME` → `elastic`.

## 3. Install Python deps + load the data

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_es.py                 # creates the 'stocks' index and loads it
```

You should see: `Indexed 19 documents into 'stocks'. Total now: 19`

## 4. Run the web app locally

```bash
python app.py
```

Open **http://127.0.0.1:5000**.

### Things to try in the app
- **Search `biotek`** — a typo for "Biotech", yet it still finds *Meridian
  Biotech* thanks to fuzzy matching. The **Score** column shows relevance.
- **Companies page** — quarter/record counts come from an aggregation, not a JOIN.
- **`/api/search?q=enrgy`** — the same search as raw JSON.

---

## 5. Putting it online (getting a link you can share)

The app above only answers on your own computer. To get a link other people
can open, you need two things online: the Elasticsearch index, and the Flask
app itself. Two ways to do that, from quickest to most permanent:

### Option 1 — Quick & temporary (a link that works right now)
Good for showing someone today; the link only works while your computer and
the tunnel are running.
1. Run the app locally as in steps 1–4 above.
2. Use a tunneling tool (e.g. `ngrok`, or Cloudflare Tunnel) to expose port
   5000 to the internet — these tools give you one command that prints a
   public `https://...` URL pointing at your local app. Check the tool's own
   docs for the exact install/run command, since these change over time.
3. Share that URL. Close the tunnel (or your computer) and the link stops
   working.

### Option 2 — Permanent (stays online without your computer)
1. **Elasticsearch**: use Elastic Cloud (Option B in step 1 above) so the
   data lives on the internet, not on your machine.
2. **Put this code on GitHub** (create a repo, push these files).
3. **Deploy the Flask app** to a host that runs Python web services from a
   Git repo — e.g. **Render**, **Railway**, or **PythonAnywhere**. As of
   early 2026, Render offers a free web-service tier (it sleeps after ~15
   minutes of inactivity and takes 30-60s to wake back up on the next
   request — fine for a demo, not for instant response times). These
   details change, so check the host's current pricing page before relying
   on it.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app` (already in the included `Procfile`,
     which Render/Railway detect automatically)
   - Add the same `ES_URL` / `ES_USERNAME` / `ES_PASSWORD` as environment
     variables in the host's dashboard (never commit them to GitHub).
4. Run `python init_es.py` **once**, pointed at the Elastic Cloud URL (you
   can run it from your own machine — it just needs the same env vars), to
   create the index and load the sample data into the cloud cluster.
5. The host gives you a public URL (e.g. `https://your-app.onrender.com`).
   That's the link you share.

---

## 6. Explore the data in Kibana

1. Open Kibana — `http://localhost:5601` for a local install, or the Kibana
   link shown on your Elastic Cloud deployment's page.
2. **☰ menu → Stack Management → Data Views → Create data view**
   - **Name:** `stocks`  ·  **Index pattern:** `stocks`  ·  no time field needed
     (or pick `date` if you want time-based charts) → **Save**
3. **☰ menu → Discover** — browse all documents. Try the search bar (KQL):
   `sector : "Technology"` or `close_price >= 100`.
4. **☰ menu → Dashboard → Create → Create visualization** — make a bar chart
   of count by `sector` or `company.keyword`, then save it to a dashboard.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot reach Elasticsearch` | Is it running (local) or is the deployment healthy (cloud)? Is `ES_URL` correct? |
| `401 / authentication` errors | Set `ES_PASSWORD` correctly. |
| TLS / certificate errors (local only) | Set `ES_CA_CERT` to `http_ca.crt`, or leave it unset to skip verification. |
| `index_not_found` in the app | Run `python init_es.py` first. |
| App works locally but not when deployed | Did you set the same env vars in the host's dashboard? Did you run `init_es.py` against the *cloud* URL, not localhost? |

## How the code maps to Elasticsearch concepts

| In `app.py` | Elasticsearch concept |
|---|---|
| `es.search(... query={"multi_match": ...})` | full-text query with field boosts + fuzziness |
| `aggs={"companies": {"terms": ...}}` | bucket aggregation (like `GROUP BY`) |
| `cardinality` agg | count of distinct values (like `COUNT(DISTINCT …)`) |
| `term` on `company.keyword` | exact-match filter on the non-analyzed sub-field |
| `_score` | relevance score Elasticsearch assigns each hit |

## Next steps for learning
- Add **highlighting** so matched words are bold in results.
- Add **autocomplete** with a `search_as_you_type` field.
- Add a **write** path: index new price records from a form (`es.index(...)`).
- Load a **bigger dataset** and watch search scale.
