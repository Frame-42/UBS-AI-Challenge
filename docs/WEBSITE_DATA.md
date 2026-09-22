# Data contract for a future website

The integration exports a complete local snapshot without an HTTP server or frontend. A website can load the generated JSON as a static asset, or its own backend can call `WebsiteDataset.score(weights)` and return that same object. No collection or LLM call is needed when weights change.

## Generate the current snapshot

```bash
python3 -m risk_framework export \
  --reports companies \
  --weights examples/collection_weights.json \
  --config examples/collection_config.json \
  --output exports/collector-triage.json
```

Use Python 3.11+. No dependencies or network access are needed for this command. The destination's parent directories are created, and the JSON is replaced atomically after successful calculation. Failed validation leaves an existing snapshot unchanged. The CLI refuses outputs inside the input report directory or over any supplied input file. Export directories are ignored by Git.

Input can be `companies/`, one company directory, a single report JSON file, or a flat directory of collector reports. Other JSON files in a report directory are rejected as malformed reports; keep unrelated JSON and output files elsewhere. `company.json` is a company manifest, not a report. Markdown briefs are ignored.

The preferred layout is `companies/<entity_id>/company.json` plus dated reports. The directory name is the stable entity ID. An adjacent manifest is respected even for a single report input. Without a manifest, a report's company name is lowercased and non-ASCII-alphanumeric runs replaced with hyphens to produce the ID. Use manifests for stable IDs across company renames, and use only one identity layout per input dataset. Conflicting names for an ID are rejected.

Reports are selected by parsed `generated_at` **for each explicitly requested category**, not filename order or modification time. A newer reputation-only report retains the last cyber, financial, and fraud reports. If a newer report explicitly requests a category but returns zero findings or errors, its missing score replaces the older score; no fallback to earlier findings occurs. Two latest reports at the same timestamp for the same category are rejected. Disjoint categories may share a timestamp. Each selected category contributes at most one heuristic assessment.

`report_count` counts all snapshots on disk. `category_reports` maps each requested category to its selected `report_file` and `generated_at`. `report_files` lists selected originals; `selected_reports` retains their complete JSON. For multiple selected reports, `report` is a combined view containing only selected category summaries/findings and deduplicated source checks/errors from those reports. Its timestamp and the compatibility field `report_file` refer to the newest selected original, not to the age of every category. Read category timestamps when displaying freshness. A manifest without reports remains unscored.

## Envelope

The machine-readable contract is [website.schema.json](../schemas/website.schema.json); it references the existing [scoreboard.schema.json](../schemas/scoreboard.schema.json). Keep both schemas together when validating offline.

| Field | Meaning |
| --- | --- |
| `schema_version` | Website envelope version, `"1.1"` |
| `score_basis` | `"collector_heuristic"`, `"ai_assessments"`, or `"simulated_ai_assessments"` |
| `distribution_semantics` | `"not_available"`, `"ai_assessment_disagreement"`, or `"synthetic_assessment_spread"` |
| `collection_digest` | SHA-256 identifier of exported collection evidence, including report filenames/counts |
| `scoreboard` | Existing versioned scoreboard: resolved config, original/effective weights, ranked entity records |
| `evidence` | Entity-ID-keyed company context, collection diagnostics, and source reports |

`scoreboard.records` holds `entity_id`, `entity_name`, nullable `entity_type`, `rank`, `overall`, and dynamic `categories`. `overall.score` is the headline; `score_method` identifies its calculation. By default it is the median of 5,000 Monte Carlo draws. `weighted_category_score` is a separate reference whose category contributions are exposed. `scoreboard.contains_synthetic_assessments` flags demo inputs even when consuming the inner scoreboard alone. Display its coverage, incomplete flag, status, and category breakdown alongside it. Rank 1 is highest numerical risk; equal values share a rank; unscored entities have null ranks and appear last. The [framework methodology](FRAMEWORK.md) defines the full scoreboard fields and weight formulas.

Join an entity row with `payload.evidence[row.entity_id]`. Each evidence entry contains:

| Field | Meaning |
| --- | --- |
| `company` | Collector company metadata, including aliases, domain, ticker, country when supplied |
| `report_file` | Selected report path relative to the supplied input directory, or basename for a single file; provenance, not a public URL |
| `generated_at` | Collector timestamp, null if no report |
| `category_reports` | Category-to-report path and original collection timestamp |
| `report_files` | Paths of all selected originals |
| `selected_reports` | Original report JSON keyed by path, preserving parameters and diagnostics |
| `report_count` | Number of report snapshots found for the entity |
| `status` | `"available"` or `"missing_report"`; available does not imply error-free collection |
| `source_check_counts` | Counts by supplied check status: ok, no_match, error, skipped; absent statuses have count zero |
| `excluded_zero_signal_categories` | Categories whose zero placeholders were excluded from heuristic scoring; these diagnostics remain about collection even in AI mode |
| `notes` | Human-readable caveats about scoring basis, report selection, gaps, and errors |
| `report` | Combined selected-category view (or original JSON when only one report is selected); null without a report |

Every signal retains its source objects (name, publisher, URL, retrieval/publication timestamps, intermediary, and license when present). The frontend can link citations directly to their supplied URLs and preserve attribution. Report paths are not automatically served. Treat source text as display text and collection evidence as unverified analyst-review material; no source credibility judgment is added by the adapter.

## Current collection mode

When exporting without `--assessments`, the envelope uses `collector_heuristic` and `not_available`. The collector currently computes one confidence-weighted severity sum per category, capped at 100. Individual findings are evidence items, not repeated agent runs, and report history is not an ensemble.

The adapter imports one category summary only if it has at least one sourced finding. It checks that the summary's signal count matches the actual signal records. No-findings zeros stay visible in the original report but become missing scores. A genuine upstream zero with informational findings remains zero. This prevents an empty or failed collection from looking like a safe vendor while preserving actual triage values.

For provisional triage, the output config explicitly uses minimum_required=1 and median aggregation. The original repeated-assessment defaults are not changed. Category n=1 describes the single summary, not the number of findings; finding counts remain in the evidence report. Disagreement quantiles, std, spread, MAD, IQR, and stability are null. Overall n=0 means no simulation was performed. Do not display a zero-width range or high stability for these deterministic summaries. These triage scores are not calibrated UBS risk judgments.

The checked-in snapshot has ten companies, 234 findings, and 33 sourced category summaries. Eight companies have cyber, financial, fraud, and reputation scores at 90% requested-weight coverage. HireRight has reputation only at 15%; Chain IQ remains unscored. Nine reputation scores are supported by 151 findings. Sanctions remain missing. HireRight's prior EDGAR error remains visible with its original report. Exporting does not refresh external evidence.

## Switch to repeated AI assessments

Once the upstream team supplies canonical JSON/JSONL assessments, pass their path through `--assessments` alongside the same report/weight/config arguments. Programmatically:

```python
from risk_framework import WebsiteDataset, load_collection, load_assessments, load_config, load_json

# agent-assessments.json is supplied by the upstream team.
dataset = WebsiteDataset(
    load_collection("companies"),
    load_config("examples/collection_config.json"),
    assessments=load_assessments("agent-assessments.json"),
)
weights = load_json("examples/collection_weights.json")
payload = dataset.score(weights)
updated = dataset.score({**weights, "financial": 50})
```

This uses `ai_assessments` and `ai_assessment_disagreement`. Repeated assessments replace all heuristic scores; they are never blended. The normal minimum_required=10/preferred=100 policy applies unless explicitly configured otherwise. Empty assessments leave companies unscored. IDs must match the collected entity roster, and category names must match the selected config; no implicit category aliases exist. Keep the evidence batch IDs in assessment metadata and retain the raw assessments for audit. The caller ensures they correspond to the selected report snapshots.

Only real assessment mode supplies observed AI-disagreement ranges; simulated assessment mode supplies explicitly synthetic spread. These are not statistical confidence intervals or probabilities of true vendor risk. Even in this mode, check per-row eligibility and null values: some companies may lack enough assessments.

## Simulate the pending AI valuations

The README's two-step `simulate` → `export --assessments` workflow writes `exports/simulated-assessments.json` and then `exports/risk-data.json`. Each available non-financial entity/category gets 100 seeded noisy assessments. Financial is excluded until real assessments arrive; absent reputational/sanctions findings are not invented. With the current reports, the optional assessment generator includes reputation: eight entities have 65% weighted coverage, HireRight has 15%, and Chain IQ remains unscored.

Synthetic files carry `metadata.synthetic: true`. `WebsiteDataset` detects that marker and returns `score_basis: "simulated_ai_assessments"` with `distribution_semantics: "synthetic_assessment_spread"`. Never label this as measured AI confidence or real vendor risk. Display the demo label with all scores. Mixing synthetic and real input rows is rejected. Replace the complete input file with real agent assessments when available; real financial scores are accepted without changing code.

The default overall headline is the median of the weighted Monte Carlo distribution, used for ranking and risk levels. `overall.n` is 5,000 for scored entities, while each available category's n is 100. p10/p90 and stability describe the injected synthetic variation in this mode. `overall.weighted_category_score` preserves the weighted category headline reference; `contributions` sums to that reference, not necessarily `overall.score`.

Defaults and override keys are documented in [FRAMEWORK.md](FRAMEWORK.md#10-synthetic-assessment-demonstration). The raw generated JSON retains each category's center and selected standard deviation for audit. Keep it if reproducibility matters; importing it does not regenerate the values.

## Recompute and publish

Keep a `WebsiteDataset` instance while users change weights. It reuses validated inputs and category summaries. Rebuild it when reports, policy, or assessments change. The API returns detached dictionaries; consumer edits do not mutate the retained snapshot.

The website/backend team decides how to serve or refresh this file and whether to offer a weight-recalculation endpoint. This branch provides a local dashboard through `python3 serve.py`; `/api/dashboard` uses the data function and accepts weight changes. The browser checks saved reports every 30 seconds.
