# Vendor risk dashboard

A red-and-white vendor risk dashboard connected to the public-source collection and scoring framework. The `website-integration` branch combines `website` with `integration/data-collection-risk-framework`.

## Run locally

Requires Python 3.11 or newer. No dependencies or build step are needed.

```sh
python3 serve.py
```

Open **http://localhost:8000**. Use `--port 8001` if another preview is already running. The dashboard requires this server; opening the HTML directly does not provide its data API.

## Data and scoring

All vendor identities, scores, findings, citations, and collection timestamps come from the latest saved report per company in `companies/`. `serve.py` calls `WebsiteDataset(load_collection(...), load_config(...))` and serves its result through `GET /api/dashboard`. Weight changes use the same endpoint with a JSON `weights` query parameter and are calculated by the framework, preserving its risk thresholds, missing-data policy, and ranking semantics.

The dashboard uses **collector heuristic triage**. These scores prioritize analyst review; they are not calibrated bank risk assessments. It displays the framework's `overall.score`, category scores, and weighted coverage. Missing categories appear as unavailable; they are never replaced by zero. Available weights are renormalized by the framework. Sorting keeps unscored vendors last in either direction.

The checked-in collection contains ten vendors. Eight have sourced scores in cybersecurity, financial, and fraud; reputational and sanctions findings are unavailable. Chain IQ and HireRight remain unscored. Collection errors, including HireRight's EDGAR error, are visible in vendor details. Informational findings can support a genuine zero score.

Default weights and category definitions come from `examples/collection_weights.json` and `examples/collection_config.json`. The compact **Weights** menu controls all five dimensions. Changing a weight proportionally rebalances the others to total 100%; scores refresh after the scoring API responds. Table columns sort by individual subscores. Click any vendor or subscore to inspect collected findings and source links, publishers, retrieval dates, publication dates where available, and source-check outcomes. The CSV includes current scores, coverage, requested weights, report paths, and collection timestamps.

The browser checks the saved collection every 30 seconds while the tab is visible and auto-refresh is enabled. This does not retrieve new external evidence. The server rebuilds its cached dataset when report files or scoring configuration change. Collection dates remain distinct from the time the dashboard last checked. Failed refreshes preserve the last successful view and display an error; exports are disabled until a successful response.

## Refresh collected evidence

Run the collector separately, then the dashboard picks up the new report:

```sh
python3 -m risk_collector --company-file companies/microsoft/company.json --out companies/microsoft
```

See [collection operation and source descriptions](docs/DATA_COLLECTION.md) for configuration, including SEC User-Agent requirements. Collection may require network access. Reweighting saved reports is offline.

## Implementation and checks

- `index.html`, `styles.css`, `app.js`: dashboard, weighting popover, and source inspection.
- `serve.py`: localhost server and cached framework-backed scoring endpoint.
- `risk_collector/`, `companies/`: collectors and saved source reports.
- `risk_framework/`: validation, scoring, and website data adapter.
- `schemas/`: framework data contracts.

```sh
python3 -m unittest discover -s tests -v
```

The server binds to localhost and serves only dashboard assets and the data endpoint. It is intended for local use. The framework's broader CLI capabilities and data contracts are documented in [FRAMEWORK.md](docs/FRAMEWORK.md) and [WEBSITE_DATA.md](docs/WEBSITE_DATA.md).
