# Architecture and developer guide

The application has three layers: explicit evidence collection, reusable scoring, and presentation. The website renders the scoring layer's results; it does not fetch provider evidence or implement a second risk formula. Python code uses the standard library, and the browser uses plain HTML/CSS/JavaScript.

## Two data paths

The local dashboard path is:

```text
companies/<id>/company.json + dated collector JSON reports
  → load_collection(): validate, select latest per entity, preserve sources
  → WebsiteDataset(): adapt sourced category summaries
  → RiskFramework(): category summaries, weights, coverage, rankings
  → DashboardData: retain a validated snapshot between requests
  → GET /api/dashboard: website envelope + dashboard.default_weights
  → app.js: table, metrics, filters, detail panel, CSV
```

The assessment distribution path is separate:

```text
upstream assessment JSON/JSONL, or explicitly synthetic generated assessments
  → Assessment validation
  → WebsiteDataset(..., assessments=...): attach collected evidence
  → RiskFramework: category distributions and weighted Monte Carlo draws
  → portable website JSON
```

`serve.py` currently creates `WebsiteDataset` without an assessments argument. Consequently the browser supports **collector triage only** and rejects other score bases. Files under `exports/` are not dashboard inputs. The assessment workflow is available via the framework API/CLI but is not wired into the browser. Making that boundary explicit prevents demo noise being presented as live evidence.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `risk_collector/models.py` | Company, sourced signal, source, source-check, and collector-result models |
| `risk_collector/http.py` | Provider HTTP requests, rate limits, retries, response cache |
| `risk_collector/collectors/` | Provider-specific parsing and matching |
| `risk_collector/pipeline.py` | Execute selected collectors, preserve failures, calculate heuristic summaries |
| `risk_collector/report.py` | Collector JSON and Markdown with numbered citations |
| `risk_framework/validation.py` | Strict identifiers, finite numbers, JSON values, duplicate-key rejection |
| `risk_framework/models.py` | Canonical assessment and result dataclasses |
| `risk_framework/config.py`, `defaults.json` | Validated policy and its default values |
| `risk_framework/collection.py` | Validate report structure and identity; select latest reports; exclude no-findings score placeholders |
| `risk_framework/scoring.py` | Descriptive statistics, weight normalization, coverage, Monte Carlo, ranking |
| `risk_framework/service.py` | Validated assessment snapshot and reusable category summaries |
| `risk_framework/simulation.py` | Reproducible, explicitly synthetic assessment generation |
| `risk_framework/export.py` | Website envelope, scoring-mode labels, atomic file export |
| `risk_framework/io.py`, `__main__.py` | JSON/JSONL ingestion, serialization, `score`/`simulate`/`export` commands |
| `serve.py` | Local HTTP server and cache of a collector-based WebsiteDataset |
| `app.js` | User preferences, requests, rendering, sorting/filtering, source inspection, CSV |

There is no database or persistent user state. The browser holds current weights and filters in memory. Restarting/reloading resets those preferences to the configured defaults. JSON/Markdown reports and optional HTTP cache files are the persistent artifacts.

## Identity and report selection

The recommended input layout is `companies/<entity_id>/company.json` with dated reports beside it. Directory names identify entities consistently across report refreshes. Agent assessments must use the same IDs. Category IDs are literal, such as `cybersecurity`; the framework does not infer that `cyber` is an alias.

The adapter selects the latest timezone-aware `generated_at` per entity. File naming and filesystem modification time do not determine which report wins. Modification time is only used by the local server to decide whether to rebuild its cache. Equal latest timestamps are ambiguous and rejected. A newer report can reduce coverage; there is no implicit backfill from older reports or mixing of history into an assessment ensemble.

Manifest-only entities appear unscored. A report's original company metadata, findings, source checks, errors, and summary remain available in `evidence[entity_id].report`. Raw report files are not directly exposed by the server.

## Configuration ownership

| File or setting | Owner / purpose |
| --- | --- |
| `companies/<id>/company.json` | Collection identity: name, aliases, ticker/domain/country, optional CIK/related parties |
| `examples/collection_config.json` | Explicit categories for the checked-in collection and local dashboard |
| `examples/collection_weights.json` | Dashboard/example default relative weights |
| `risk_framework/defaults.json` | Scoring policy, minimum runs, risk labels, stability thresholds, simulation seeds/counts |
| Collector CLI arguments and registry | Provider selection and supported collection categories |
| `RISK_COLLECTOR_USER_AGENT` | Provider request identity; not a scoring parameter |
| `app.js` constants | Pagination (8), visible-tab polling (30 seconds), weight-input debounce (120 ms) |

Example files are deliberately small and editable. The local server currently uses the two collection example paths directly; changing its input locations requires changing `DashboardData`. A partial scoring config merges nested values into defaults, while arrays replace the full array. All resolved scoring choices are returned in the scoreboard.

Dynamic scoring categories do not require source changes. Adding collection support for a new category is a different operation: update the collector model/registry and provide sourced signals. The browser derives its controls from returned normalized-weight keys and uses literal category IDs with optional friendly display labels.

## Recomputing without recollecting

`RiskFramework` validates raw rows and caches category summaries at construction. `score_all(weights)` recomputes overall values and ranks; it never requests new assessments. `WebsiteDataset` also retains collected evidence and returns detached dictionaries, so consumers cannot mutate the cached snapshot through a result object.

`DashboardData` holds one WebsiteDataset. It fingerprints every collection JSON file, the dashboard config/weights, and the default policy by path, nanosecond modification time, and size. Added, removed, or changed files rebuild the cache on the next request. New inputs must validate before replacing the cache. A reload failure returns HTTP 503; the browser keeps its previously displayed snapshot visibly stale.

This fingerprint is a local development optimization, not a cryptographic change detector. If bytes change while size and timestamps are deliberately preserved, restart the server. A lock serializes snapshot rebuilds and scoring; this small server is not designed as a high-throughput multiuser service.

## Contracts and mode boundaries

- [assessment.schema.json](../schemas/assessment.schema.json): one canonical raw assessment; JSON files hold an array, JSONL holds one per line.
- [scoreboard.schema.json](../schemas/scoreboard.schema.json): version 1.1 scoring results and resolved policy.
- [website.schema.json](../schemas/website.schema.json): version 1.1 portable scoreboard plus evidence and mode labels.
- [dashboard.schema.json](../schemas/dashboard.schema.json): local API success response, adding `dashboard.default_weights` and restricting the score basis to collector triage.

The input models enforce batch constraints not expressible by the per-record schema, such as duplicate run IDs and consistent entity identities. An API error is a separate `{"error":"message"}` object. Do not validate errors as successful dashboard payloads.

Category distributions and overall resampling are independent of presentation. The [methodology](FRAMEWORK.md) is the reference for score meanings. Triage, injected demo spread, and supplied AI disagreement must not be relabeled interchangeably.

## Extending the application

**Add a company:** create a new company directory/manifest, run collection into that directory, and verify the next API response includes it. A manifest without evidence remains visible as unscored.

**Add or rename a scoring category:** update the config and weights together, then ensure incoming reports/assessments use the exact ID. Unknown configured IDs fail validation. The browser rebuilds its controls when categories, risk labels, or default weights change; invalid old weight requests are retried with server defaults.

**Use real assessments:** provide a canonical assessment file to `risk_framework export --assessments`. At present this changes the portable export only. To support it in the dashboard later, explicitly add assessment selection to `DashboardData`, include that input in cache invalidation, and update browser labels/range/count displays and contract tests before accepting the new score basis. There is intentionally no automatic fallback from missing real assessments to heuristic or synthetic scores.

**Add a collector:** implement the collector interface and register it. Reuse existing source/provenance models, record provider failures, and add offline parser/fixture tests. Collection should remain an explicit upstream action.

## Development and validation

Run `python3 -m unittest discover -s tests -v` from the repository root. Tests cover collectors without external calls, scoring methods, missing data, seeds, JSON/CLI exports, website joins, and temporary localhost HTTP endpoints. Node 18+ is optional and only needed for `node --check app.js` and `node --test tests/dashboard_logic.test.cjs`. The latter tests request/control logic against small DOM stubs; it is not a visual browser test.

A Python wheel packages `risk_framework`, `risk_collector`, and scoring defaults. The root-level dashboard assets, saved reports, documentation, and examples are repository artifacts; run the dashboard from a checkout. No install/build step is required for normal development.

For UI changes, additionally check search, both score-sort directions, null-score rows, weight reset/rebalancing, failed refresh recovery, source links, keyboard focus, dialog dismissal, CSV, and narrow-screen horizontal scrolling. The Python tests do not replace a visual browser check.
