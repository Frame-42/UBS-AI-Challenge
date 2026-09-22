# Dashboard operation and local API

The dashboard presents the latest saved collection through the scoring framework. It is a local analyst-review prototype: the browser reads JSON from `serve.py`, and all score calculations stay in Python.

## Start and stop

From the checkout root, run `python3 serve.py` and open `http://127.0.0.1:8000`. Python 3.11+ is required; there are no runtime packages or frontend build tools to install. `--port 8001` selects another port. Ctrl+C closes the server. It binds to `127.0.0.1`, not a public network interface.

Only `/`, `/index.html`, `/styles.css`, `/app.js`, and `GET /api/dashboard` are exposed. Arbitrary repository files and directories return 404. HEAD is supported for the four asset paths; the scoring API is GET-only. The development server has no authentication, persisted user sessions, or deployment configuration.

The dashboard does not read `exports/risk-data.json`. Generating a Monte Carlo demo export will not alter the live browser view. See [WEBSITE_DATA.md](WEBSITE_DATA.md) for portable exports and [ARCHITECTURE.md](ARCHITECTURE.md) for that explicit boundary.

## What the screen means

The four top metrics are vendor count, number in HIGH/CRITICAL bands, average overall score among scored vendors, and total sourced findings in the latest selected reports. They describe the full loaded collection, not just the filtered table.

The table shows one weighted overall score, a requested-weight coverage percentage, category scores, and a risk label. Values are rounded for display; sorting uses full-precision server results. Unavailable scores display a dash and sort last in either direction. Click a vendor, row, or subscore to inspect its detail panel; category buttons jump to the corresponding evidence.

The detail panel preserves source names/URLs, publishers, retrieval dates, publication dates where available, licenses, collected findings, report paths, source-check outcomes, and collection errors. Source links allow HTTP(S) URLs only. Finding text is displayed as text rather than interpreted markup. A `no_match` result means no matching finding was returned from that consulted source, not proof of safety.

Search checks vendor name, aliases, country, and domain. Filters select country, scored/unscored coverage status, or risk level. Score columns sort independently of the framework's comparative rank. Pagination shows eight rows per page. Clear filters preserves custom weights; Reset in the weights menu restores configured weight defaults. `/` focuses search when no dialog or form control is active. Escape closes dialogs, and focus is returned to their trigger where possible.

## Weights and missing data

Weights are percentages in the UI, with 0.1-point precision. Changing one dimension redistributes the remainder proportionally across the others, or evenly if their previous total was zero. A single-category configuration remains at 100%. Input changes debounce for 120 ms before a server request.

The browser sends all requested weights to the API. The scoring layer validates and normalizes them, excludes missing categories, and returns effective weights, coverage, score, and rank. A category's absence never becomes a zero score. Triage imports a genuine zero only when the report contains sourced informational findings supporting that summary.

Example: cyber 40%, financial 30%, regulatory 30%, with regulatory missing. The score uses effective cyber/financial weights 4/7 and 3/7 and reports 70% coverage. This is an available-data score, not a full-evidence assessment.

This branch's live view is collector triage. Category n=1 identifies one heuristic summary, not one AI run or one finding. There are no disagreement ranges or Monte Carlo draws in this mode. The UI explicitly rejects other score bases to avoid presenting synthetic or AI results with collector-only labels.

## API requests and responses

Default weights:

```bash
curl --fail http://127.0.0.1:8000/api/dashboard
```

Custom weights, encoded as one JSON query parameter:

```bash
curl --fail --get http://127.0.0.1:8000/api/dashboard \
  --data-urlencode 'weights={"cybersecurity":60,"financial":20,"fraud":10,"reputational":5,"sanctions":5}'
```

The query accepts only `weights`. It must appear once and contain a JSON object. Empty values, null, arrays, malformed JSON, duplicate JSON keys, non-finite values, negative weights, all-zero weights, and unknown categories are rejected. Omitted categories receive zero weight. Fractions and percentages both work as consistent relative weights; units are not inferred.

Successful responses follow [dashboard.schema.json](../schemas/dashboard.schema.json). The root is the portable website envelope plus:

```json
{
  "dashboard": {
    "default_weights": {
      "cybersecurity": 35,
      "financial": 25,
      "fraud": 15,
      "reputational": 15,
      "sanctions": 10
    }
  }
}
```

That example shows only the additional field, not the complete payload. Read rows at `scoreboard.records`, join evidence through `evidence[entity_id]`, and inspect `scoreboard.normalized_weights` for the applied requested weights. Defaults are separate from the weights used for a particular response.

| Status | Meaning | Body |
| --- | --- | --- |
| 200 | Valid snapshot and weight request | Versioned dashboard JSON |
| 400 | Invalid query or requested weights | `{"error":"explanation"}` |
| 503 | Saved reports/configuration unavailable or invalid | `{"error":"Collection snapshot unavailable…"}` |
| 404 | Unexposed route or repository path | Standard local-server error page |

API responses use `Content-Type: application/json; charset=utf-8` and `Cache-Control: no-store`, including JSON errors. The full details of a snapshot reload error are logged in the server terminal. Request validation errors are distinct from malformed saved files: repairing weights cannot fix a broken report.

## Refresh lifecycle

The browser requests data on initial load, after a weight change, and every 30 seconds when auto-refresh is enabled, the tab is visible, and no request is pending. Pausing auto-refresh stops the timer-driven requests; manual weight changes still recompute. Superseded requests are aborted and out-of-date responses ignored.

On each request, the server checks paths, modification times, and sizes for collection JSON files, the dashboard config/weights, and scoring defaults. A change rebuilds a candidate WebsiteDataset; it replaces the cache only after validation succeeds. Weight-only requests reuse the existing snapshot. HTTP workers share a lock around this small in-memory cache and scoring.

A category/default/risk-label change rebuilds browser controls. If a removed category invalidates old weights, the browser retries once without custom weights and restores server defaults. Users may need to reapply their preferences after such a configuration change. New input files are not automatically collected; another process or teammate must write them.

Collection timestamps reflect provider report generation, shown in UTC. The separate “Checked” time is the browser's last successful check, shown in local time. It is not evidence freshness. A failed refresh leaves the last successful view visible with an error and disables export until a successful response. There is no fallback to fabricated scores or older report snapshots.

## CSV export

Export includes all currently filtered rows in the current sort order, not only the visible page. Columns contain vendor/country, score basis, overall score, risk level, weighted coverage, each category score, requested category weights in percent, collection timestamp, and report path. Coverage is a fraction (0–1) in CSV. Missing numerical values are empty cells, never zeros inserted by the exporter.

The CSV uses UTF-8 with a BOM, quotes each cell, escapes embedded quotes, and prefixes spreadsheet formula-like values with an apostrophe. It does not embed every finding or source; use the JSON envelope for full provenance. Export is disabled while scoring is pending or the latest refresh failed, so selected controls cannot be exported with stale scores.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Port already in use | Start with `--port 8001`; use the matching browser URL |
| Empty page opened as a file | Start `serve.py`; use its HTTP URL instead of `file://` |
| “Unable to load vendor data” | Read the server terminal; validate the collection with the export CLI |
| HTTP 503 after editing a report | Check JSON syntax, matching category/summary counts, valid scores, entity identity, and ambiguous latest timestamps |
| A vendor is unscored | Inspect its findings, missing positive-weight categories, and collection errors; do not substitute zero |
| New report has no effect | Check `generated_at`, selected report path, auto-refresh, and whether the file was written under `companies/` |
| File changed but cache did not | The cache uses size/mtime; restart if those attributes were deliberately preserved |
| Synthetic export is not on screen | Expected: the live server uses collector triage only |
| Reputational or sanctions score is blank | This checkout's saved reports do not provide eligible findings in those categories |
| Fonts look different offline | Google Fonts may be unavailable; local fallback fonts are intentional |

To validate the same saved collection independently of HTTP:

```bash
python3 -m risk_framework export \
  --reports companies \
  --weights examples/collection_weights.json \
  --config examples/collection_config.json \
  --output exports/collector-triage.json
```

This does not query external providers. For refresh instructions, see [DATA_COLLECTION.md](DATA_COLLECTION.md). For scores and uncertainty, see [FRAMEWORK.md](FRAMEWORK.md).
