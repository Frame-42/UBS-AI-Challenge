# Data contract for a future website

The integration exports a complete local snapshot without an HTTP server or frontend. A website can load the generated JSON as a static asset, or its own backend can call `WebsiteDataset.score(weights)` and return that same object. No collection or LLM call is needed when weights change.

## Generate the current snapshot

```bash
python3 -m risk_framework export \
  --reports companies \
  --weights examples/collection_weights.json \
  --config examples/collection_config.json \
  --output exports/risk-data.json
```

Use Python 3.11+. No dependencies or network access are needed for this command. The destination's parent directories are created, and the JSON is replaced atomically after successful calculation. Failed validation leaves an existing snapshot unchanged. The CLI refuses outputs inside the input report directory or over any supplied input file. Export directories are ignored by Git.

Input can be `companies/`, one company directory, a single report JSON file, or a flat directory of collector reports. Other JSON files in a report directory are rejected as malformed reports; keep unrelated JSON and output files elsewhere. `company.json` is a company manifest, not a report. Markdown briefs are ignored.

The preferred layout is `companies/<entity_id>/company.json` plus dated reports. The directory name is the stable entity ID. An adjacent manifest is respected even for a single report input. Without a manifest, a report's company name is lowercased and non-ASCII-alphanumeric runs replaced with hyphens to produce the ID. Use manifests for stable IDs across company renames, and use only one identity layout per input dataset. Conflicting names for an ID are rejected.

Reports are selected by parsed `generated_at`, not filename ordering or filesystem modification time. Only the latest snapshot contributes scores. Multiple latest reports with the same timestamp are rejected; older snapshots are counted in `report_count` and left on disk. A newer sparse/error-containing report is not backfilled from older evidence. A manifest without any report remains in the output as an unscored company.

## Envelope

The machine-readable contract is [website.schema.json](../schemas/website.schema.json); it references the existing [scoreboard.schema.json](../schemas/scoreboard.schema.json). Keep both schemas together when validating offline.

| Field | Meaning |
| --- | --- |
| `schema_version` | Website envelope version, `"1.0"` |
| `score_basis` | `"collector_heuristic"` or `"ai_assessments"` |
| `distribution_semantics` | `"not_available"` or `"ai_assessment_disagreement"` |
| `collection_digest` | SHA-256 identifier of exported collection evidence, including report filenames/counts |
| `scoreboard` | Existing versioned scoreboard: resolved config, original/effective weights, ranked entity records |
| `evidence` | Entity-ID-keyed company context, collection diagnostics, and source reports |

`scoreboard.records` holds `entity_id`, `entity_name`, nullable `entity_type`, `rank`, `overall`, and dynamic `categories`. `overall.score` is the headline. Display its coverage, incomplete flag, status, and category breakdown alongside it. Rank 1 is highest numerical risk; equal values share a rank; unscored entities have null ranks and appear last. The [framework methodology](FRAMEWORK.md) defines the full scoreboard fields and weight formulas.

Join an entity row with `payload.evidence[row.entity_id]`. Each evidence entry contains:

| Field | Meaning |
| --- | --- |
| `company` | Collector company metadata, including aliases, domain, ticker, country when supplied |
| `report_file` | Selected report path relative to the supplied input directory, or basename for a single file; provenance, not a public URL |
| `generated_at` | Collector timestamp, null if no report |
| `report_count` | Number of report snapshots found for the entity |
| `status` | `"available"` or `"missing_report"`; available does not imply error-free collection |
| `source_check_counts` | Counts by supplied check status: ok, no_match, error, skipped; absent statuses have count zero |
| `excluded_zero_signal_categories` | Categories whose zero placeholders were excluded from heuristic scoring; these diagnostics remain about collection even in AI mode |
| `notes` | Human-readable caveats about scoring basis, report selection, gaps, and errors |
| `report` | Original selected collector JSON, including company, generated_at, parameters, summary, signals, sources_consulted, errors; null without a report |

Every signal retains its source objects (name, publisher, URL, retrieval/publication timestamps, intermediary, and license when present). The frontend can link citations directly to their supplied URLs and preserve attribution. Report paths are not automatically served. Treat source text as display text and collection evidence as unverified analyst-review material; no source credibility judgment is added by the adapter.

## Current collection mode

Without `--assessments`, the envelope uses `collector_heuristic` and `not_available`. The collector currently computes one confidence-weighted severity sum per category, capped at 100. Individual findings are evidence items, not repeated agent runs, and report history is not an ensemble.

The adapter imports one category summary only if it has at least one sourced finding. It checks that the summary's signal count matches the actual signal records. No-findings zeros stay visible in the original report but become missing scores. A genuine upstream zero with informational findings remains zero. This prevents an empty or failed collection from looking like a safe vendor while preserving actual triage values.

For provisional triage, the output config explicitly uses minimum_required=1 and median aggregation. The original repeated-assessment defaults are not changed. Category n=1 describes the single summary, not the number of findings; finding counts remain in the evidence report. Disagreement quantiles, std, spread, MAD, IQR, and stability are null. Overall n=0 means no simulation was performed. Do not display a zero-width range or high stability for these deterministic summaries. These triage scores are not calibrated UBS risk judgments.

The checked-in snapshot has ten companies and three collected categories: cybersecurity, financial, fraud. The example config also requests reputational and sanctions, which are missing. Eight companies have eligible sourced category summaries and 75% requested-weight coverage under the example weights. Chain IQ and HireRight remain unscored. HireRight has an EDGAR collection error, which is preserved. The scores reflect this saved snapshot; exporting does not refresh the evidence.

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

Only this mode supplies AI-disagreement ranges. These are not statistical confidence intervals or probabilities of true vendor risk. Even in this mode, check per-row eligibility and null values: some companies may lack enough assessments.

## Recompute and publish

Keep a `WebsiteDataset` instance while users change weights. It reuses validated inputs and category summaries. Rebuild it when reports, policy, or assessments change. The API returns detached dictionaries; consumer edits do not mutate the retained snapshot.

The website/backend team decides how to serve or refresh this file and whether to offer a weight-recalculation endpoint. This repository provides the data function and CLI only. No dashboard, route, websocket, or browser application is implemented.
