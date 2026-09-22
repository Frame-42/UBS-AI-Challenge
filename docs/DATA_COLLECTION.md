# Data collection and saved evidence

`risk_collector` gathers public-source signals for a named company and writes a JSON report plus a Markdown brief. Collection is an explicit network operation. The dashboard and scorer read saved files and never invoke providers while a user changes weights.

Findings are material for analyst review, not conclusions about a company. Keyword and fuzzy-name matches can be false positives, a provider can fail, and no returned finding does not establish low risk. Reports preserve these distinctions rather than collapsing them into a score.

## Company identity

The recommended layout is:

```text
companies/
  microsoft/
    company.json
    microsoft_20260922T143313.json
    microsoft_20260922T143313.md
```

The directory name is the framework's stable entity ID. `company.json` describes collection identity; it is not a risk report. Supported fields are:

| Field | Purpose |
| --- | --- |
| `name` | Required company name |
| `aliases` | Additional names used for matching/search |
| `ticker` | Optional stock symbol |
| `domain` | Optional primary domain, useful for breach matching |
| `country` | Optional display/context field |
| `cik` | Optional SEC identifier, resolved by the collector if absent |
| `related_parties` | Optional executives, subsidiaries, or owners to include in screening |

For example, the existing Microsoft manifest includes its display name, aliases, ticker, domain, and country. Use the manifest with `--company-file`; command-line aliases and related parties append to the file's lists, while supplied scalar options override the file's values. A positional company name also overrides its name.

For a new company, add a new directory and manifest, then collect into that same directory. Keep IDs stable for future agent assessments and website joins. A manifest-only company remains visible but unscored. Avoid silently reusing an existing directory ID for a different entity.

## Commands

List available collectors without provider requests:

```bash
python3 -m risk_collector --list-collectors
```

Refresh one existing company's saved report:

```bash
export RISK_COLLECTOR_USER_AGENT="Your Org risk-team you@yourorg.com"
python3 -m risk_collector \
  --company-file companies/microsoft/company.json \
  --out companies/microsoft
```

Select a subset of collectors/categories or override the lookback window:

```bash
python3 -m risk_collector \
  --company-file companies/microsoft/company.json \
  --collectors sec_edgar cisa_kev hibp \
  --categories cybersecurity financial fraud \
  --lookback-days 365 \
  --out companies/microsoft
```

The User-Agent environment variable identifies provider requests; replace the example with real contact information when using SEC endpoints. The HTTP client passes it through as configured. Provider requirements and availability can change; the saved snapshot and tests do not verify current external services.

| Option | Behavior |
| --- | --- |
| `--company-file PATH` | Read Company fields from JSON |
| `--alias`, `--related` | Repeat to add names or related parties |
| `--ticker`, `--domain`, `--country`, `--cik` | Override scalar identity fields |
| `--categories ...` | Restrict requested categories |
| `--collectors ...` | Restrict provider implementations |
| `--lookback-days N` | Override collector windows; GDELT caps its window at 90 days |
| `--out DIR` | Report destination; default `reports/` is not a dashboard input |
| `--cache-dir DIR` | HTTP cache location, default `.cache/risk_collector` |
| `--no-cache` | Disable response-cache reads and writes for the run |
| `-v` | Verbose collector/request logging |

Run `python3 -m risk_collector --help` for the authoritative option list. Collection can take time because provider requests are rate-limited. It may complete with recorded errors and partial evidence; inspect the report rather than treating process completion as complete coverage.

## Collector implementations

These are the sources and behavior configured by the repository, not a claim that every source succeeded in the saved collection.

| Collector | Categories | Configured inputs and interpretation |
| --- | --- | --- |
| `gdelt` | cybersecurity, fraud, reputational, financial | GDELT DOC article searches using company/alias names and category keywords; a news-tone timeline also contributes reputational context |
| `sanctions` | sanctions | OFAC, UN, EU, UK, and Swiss SECO list downloads; fuzzy screening of company/alias/related-party names |
| `sec_edgar` | financial, fraud, cybersecurity, reputational | SEC submissions, search, and company facts; filing events, red-flag phrases, and selected financial indicators |
| `cisa_kev` | cybersecurity | CISA Known Exploited Vulnerabilities entries matched to the company's products/vendor names |
| `hibp` | cybersecurity | Have I Been Pwned breach catalogue, matched by domain/name |

Sanctions matching uses a default similarity threshold of 0.88. That similarity is not a calibrated probability. SEC coverage depends on identifying the appropriate registrant; a missing registrant or financials request can leave gaps. Product vulnerabilities and company-wide third-party risk are different concepts, so the underlying evidence must remain visible.

The shared HTTP client configures minimum host intervals of 6 seconds for GDELT and 0.15 seconds for its SEC hosts. It retries selected transient failures with exponential backoff; the default permits an initial attempt and three retries. These are implementation settings, not guarantees of provider access. Cached responses retain original retrieval timestamps. Many requests cache for an hour; sanctions lists use a 24-hour TTL. `--no-cache` requests a fresh network run and does not make it historically reproducible.

## Report contract and provenance

Each collector returns signals, source checks, and errors. The pipeline filters signals to requested categories and preserves failures. Report JSON contains:

| Field | Contents |
| --- | --- |
| `company` | Identity used for this run |
| `generated_at` | Time the assembled report was generated |
| `parameters` | Collectors, requested categories, per-collector lookback windows |
| `summary` | Per-category finding count, maximum severity, heuristic score, counts by severity |
| `signals` | Category, title, summary, severity, confidence, collector, sources, optional observed time/tags/data |
| `sources_consulted` | Source checks, including negative results and failures |
| `errors` | Collection failures with their collector context |

A `RiskSignal` requires at least one source. A source requires a name, publisher, and URL; it records retrieval time and may include publication time, intermediary, and license. The Markdown writer turns these into numbered citations and a references section. The complete JSON remains the machine-readable artifact; the website does not parse Markdown.

Source checks use `ok`, `no_match`, `error`, or `skipped`. Checks refer to the consulted source, not automatically to one category's completeness. A report can contain findings while also having errors. Metadata records where evidence came from; it is not an independent credibility assessment.

The current collector model constrains confidence to [0,1] and uses it mainly as an entity/matching relevance signal. It should not be read as statistical confidence in a claim. The downstream report adapter rejects invalid structures, mismatched signal counts, absent citations, invalid category sets, or out-of-range scores rather than silently dropping malformed records.

## Heuristic score calculation

For each requested category, the collector calculates:

```text
score = min(100, round(Σ severity_weight(signal) × confidence(signal)))

severity_weight:
  info      0
  low       2
  medium    6
  high     15
  critical 40
```

This is a triage heuristic, not a financial model, calibrated probability, repeated AI valuation, or UBS-approved risk rating. A category with many signals can reach the cap. Informational findings can legitimately yield zero; no findings also yield a producer placeholder of zero. The downstream adapter distinguishes those cases: it imports a score only when at least one sourced finding exists. With no findings, the framework reports missing data instead of zero risk.

Repeated AI assessment scoring is separate and described in [FRAMEWORK.md](FRAMEWORK.md). Individual evidence items and historical reports must never be treated as repeated AI runs.

## Refresh semantics and the saved snapshot

The dashboard chooses the latest report per entity by `generated_at`, not filename or modification time. Older JSON/Markdown snapshots may be retained for provenance; their values are not blended into the current score. A newer incomplete report can reduce coverage. Equal latest timestamps are ambiguous and rejected. Writes using the same filename timestamp can overwrite an existing producer report, so use distinct collection times if history must be preserved.

After collection writes into `companies/<id>/`, the server detects changed JSON files on a subsequent request. The browser normally checks every 30 seconds while visible and enabled. A partially written or invalid report can temporarily cause a 503; the browser keeps its last successful view with an error until inputs validate again. For manual imports, finish/validate files outside `companies/` before moving them into place.

This checkout's saved reports contain ten companies and were generated on 22 September 2026 using `sec_edgar`, `cisa_kev`, and `hibp`. They request cybersecurity, financial, and fraud. Eight companies have eligible sourced summaries. Chain IQ and HireRight have no findings; HireRight also records an EDGAR financials error. No eligible reputational or sanctions findings are present in these saved reports. Starting the dashboard does not add newer reports or merge data from another Git branch.

Financial heuristic summaries in the collection are distinct from the pending financial AI assessment inputs. The synthetic demonstration excludes financial explicitly. Keep that distinction visible when comparing dashboard triage with the demo export.

## Adding a source and testing

Subclass `collectors.base.Collector`, implement its `collect(company)` method, return sourced signals/checks/errors, and register the class in `collectors/__init__.py`. A new category also requires extending the collector's category model. Scoring categories can be configured independently, but a configured category does not create evidence.

Add offline parsing/matching fixtures and provenance tests. Run:

```bash
python3 -m unittest discover -s tests -v
```

The suite never requests provider data. It validates saved/fixture behavior, not provider uptime, complete evidence coverage, or real-world predictive accuracy. To inspect joined collection/scoring output without HTTP, use the export workflow in [WEBSITE_DATA.md](WEBSITE_DATA.md).
