# UBS Third-Party Risk Intelligence Framework

Turn repeated AI risk assessments into transparent category scores, disagreement ranges, weighted overall scores, and ranked JSON for a separate scoreboard. Higher values always mean higher risk, on a 0–100 scale.

This repository contains the public-source collector (`risk_collector`), the scoring layer (`risk_framework`), and an offline JSON export joining their outputs. The scoring layer does not call LLMs or retrieve evidence. There is no frontend, database, or UBS internal integration. A risk score is an analytical prioritization signal, not proof that a vendor is unsafe.

## Simulate 100 assessments and calculate overall risk

For the current demo, generate 100 explicitly synthetic assessments per available company/category, then run the Monte Carlo scorer:

```bash
python3 -m risk_framework simulate \
  --reports companies \
  --config examples/collection_config.json \
  --output exports/simulated-assessments.json

python3 -m risk_framework export \
  --reports companies \
  --weights examples/collection_weights.json \
  --config examples/collection_config.json \
  --assessments exports/simulated-assessments.json \
  --output exports/risk-data.json
```

This currently creates **1,600 synthetic assessments**: 100 each for cybersecurity and fraud across eight companies with findings. Scores use seeded normal noise around the collected heuristic, with a per-category standard deviation chosen between 4 and 12 points, clipped to [0, 100]. These are demo values, not AI judgments or factual company-risk estimates. Each raw assessment carries `metadata.synthetic: true`, its center, spread, seed/settings, and collection digest.

**Financial assessments are pending and excluded from this simulation**, even though saved reports contain financial heuristic summaries. No findings are invented for other missing categories or the two unscored companies. With the example weights, scored entities therefore have 50% coverage; financial, reputational, and sanctions remain missing. Real financial assessments can be supplied later through the canonical assessment input without code changes.

The scorer performs **5,000 weighted Monte Carlo draws per eligible entity**. `overall.score` is their median by default, and rankings/risk levels use that value. The output also includes p10–p90, spread, standard deviation, and stability. `overall.weighted_category_score` retains the weighted combination of category headlines for comparison; `overall.contributions` sums to that reference, not necessarily the Monte Carlo median.

The website payload is labeled `score_basis: "simulated_ai_assessments"` and `distribution_semantics: "synthetic_assessment_spread"`. The inner scoreboard also marks `contains_synthetic_assessments: true`. Its ranges describe injected demo variation, not observed AI disagreement or confidence in true risk. Synthetic and real assessments cannot be mixed in one website dataset.

Adjust `assessment_simulation` in [risk_framework/defaults.json](risk_framework/defaults.json), or override its `runs`, `seed`, `spread_std_min`, `spread_std_max`, and `excluded_categories` through `--config`. `overall_simulation.headline_method` supports `monte_carlo_median` (default), `monte_carlo_mean`, and `weighted_categories`. Synthetic generation and overall Monte Carlo resampling use separate seeds.

## Export the collected company data without simulated assessments

The checked-in `companies/` directory contains reports for ten companies. Produce one JSON file that a future website can load:

```bash
python3 -m risk_framework export \
  --reports companies \
  --weights examples/collection_weights.json \
  --config examples/collection_config.json \
  --output exports/collector-triage.json
```

This command is offline and uses the latest report per company. The output joins ranked category/overall scores to the original sourced findings, source checks, report timestamps, and collection errors. It is written atomically, so a consumer never reads a partially written snapshot. `exports/` is ignored by Git; regenerate the file after input changes.

**The collected scores are heuristic triage summaries, not repeated AI judgments.** The export identifies them with `score_basis: "collector_heuristic"`; disagreement ranges and stability are null, and no Monte Carlo simulations run. A category with no sourced findings remains unscored, including an upstream zero placeholder. A zero score supported by actual informational findings is retained as the collector's triage score. These numbers have not been calibrated as UBS vendor-risk assessments.

The saved reports cover `cybersecurity`, `financial`, and `fraud`. Requested `reputational` and `sanctions` data remain missing. Chain IQ and HireRight have no findings and remain unranked; HireRight's collection error stays visible. These are limitations of the saved collection, not claims that these companies are low risk. Example weights are editable demonstration preferences.

When repeated agent assessments are available, add `--assessments path/to/assessments.json`. Use IDs matching the company directories (`microsoft`, `aws`, `chain-iq`, etc.) and category names matching your configuration. This switches the entire scoreboard to `score_basis: "ai_assessments"`, preserves the original median/eligibility/resampling policy, and keeps collector evidence attached. It never mixes heuristic scores with AI runs. An empty assessment file stays empty; there is no heuristic fallback.

The future website contract is [schemas/website.schema.json](schemas/website.schema.json), explained in [docs/WEBSITE_DATA.md](docs/WEBSITE_DATA.md). The site reads `scoreboard.records` for rankings and joins `evidence[entity_id]` for findings and citations. Check `score_basis` and `distribution_semantics` before displaying uncertainty.

```python
from risk_framework import WebsiteDataset, load_collection, load_config, load_json

dataset = WebsiteDataset(
    load_collection("companies"),
    load_config("examples/collection_config.json"),
)
weights = load_json("examples/collection_weights.json")
payload = dataset.score(weights)
reweighted = dataset.score({**weights, "financial": 50})
```

Keep `dataset` for weight changes; recreate it after reports or agent assessments change. Neither reweighting nor exporting makes network or LLM calls. Collection operation, source descriptions, and caveats are documented in [docs/DATA_COLLECTION.md](docs/DATA_COLLECTION.md). To list available collectors without collecting anything:

```bash
python3 -m risk_collector --list-collectors
```

## Run the repeated-assessment example

Use Python 3.11 or newer from the repository root. There are **no runtime or test dependencies**, API keys, or network calls.

```bash
python3 -m unittest discover -s tests -v
python3 -m risk_framework score \
  --input examples/sample_assessments.json \
  --weights examples/sample_weights.json \
  --config examples/sample_config.json \
  --format table
```

For the frontend payload:

```bash
python3 -m risk_framework score \
  --input examples/sample_assessments.json \
  --weights examples/sample_weights.json \
  --config examples/sample_config.json \
  --output scoreboard.json
```

JSON is the default format; omit `--output` to write it to stdout. Invalid input exits with code 2 and an error on stderr, without partial scoring output. The config argument is optional.

The 395 sample assessments are **entirely synthetic**: Vendor Alpha, Vendor Beta, and Vendor Gamma are fictional, and none of the numbers are UBS assessments. Most categories have 30 runs to keep the example small. Gamma has no regulatory assessments and only five reputational assessments, demonstrating reduced coverage and withheld category scores.

## Architecture

```text
JSON / JSONL assessments + optional entity roster
                     ↓ validate once
          RiskFramework assessment snapshot
          ├─ retained raw scores and metadata
          └─ cached category descriptive statistics
                     ↓ user weights
     weighted score + empirical overall resampling
                     ↓
           ranked Scoreboard JSON
```

| Location | Responsibility |
| --- | --- |
| `risk_collector/`, `companies/` | Public-source collection and saved company reports |
| `risk_framework/collection.py`, `export.py` | Report validation, latest-snapshot selection, website export |
| `risk_framework/models.py` | Assessment and result dataclasses |
| `risk_framework/config.py`, `defaults.json` | Validated scoring policy and defaults |
| `risk_framework/scoring.py` | Category statistics, weights, resampling, ranking |
| `risk_framework/service.py` | Validated reusable snapshot and scoring interface |
| `risk_framework/io.py`, `validation.py` | JSON/JSONL loading and validation |
| `risk_framework/__main__.py` | Offline CLI |
| `schemas/` | Machine-readable input and scoreboard JSON contracts |
| `tests/`, `examples/` | Regression tests and fictional integration data |
| [docs/FRAMEWORK.md](docs/FRAMEWORK.md) | Formulas, assumptions, and complete output semantics |

## Input contract

Canonical input is a JSON array of assessment objects. `.jsonl` accepts one object per nonblank line. Only `entity_id`, `category`, and `risk_score` are required.

```json
{
  "entity_id": "vendor-alpha",
  "category": "cyber",
  "risk_score": 72.0,
  "entity_name": "Vendor Alpha",
  "entity_type": "vendor",
  "run_id": 17,
  "timestamp": "2026-09-22T12:00:00Z",
  "agent_id": "risk-agent-v1",
  "metadata": {"evidence_batch": "fictional-example"}
}
```

Scores must be finite JSON numbers in [0, 100]. Booleans, numeric strings, null scores, unknown top-level fields, and malformed records are rejected. Additional context belongs in `metadata`. Optional fields may be omitted or null, except `metadata`, which must be an object if supplied. Timestamps, when supplied, require a timezone.

Run IDs are nonnegative integers or nonempty strings. Duplicate IDs within an entity/category are rejected, including `17` and `"17"`, even across agents. Without IDs, each record is treated as a separate assessment; duplicates cannot be identified reliably. Entity names/types must be consistent across records. Metadata is retained, never used as an implicit evidence-quality weight.

Categories are data-driven. By default, the category set is the union of assessment and weight keys. Use `--config examples/sample_config.json` to declare an explicit category list and reject misspellings. Add, remove, or rename categories in that configuration and the input/weights; no source changes are needed.

## Scores and disagreement

The default category score is the **median**. Each category also returns `n`, mean, median, population standard deviation, min/max, p10, p25, p75, p90, IQR, unscaled MAD, and p90−p10 spread. Configurable alternatives are mean, a chosen percentile, and `(1 - alpha) × median + alpha × p90`.

Stability describes the spread of supplied assessments: HIGH at a p10–p90 spread ≤15 points, MEDIUM ≤30, otherwise LOW. These defaults live in [risk_framework/defaults.json](risk_framework/defaults.json). A narrow range does not establish accuracy or good evidence.

Repeated LLM judgments are **not independent measurements of objective ground truth**. The p10–p90 range is an **AI-assessment disagreement/sensitivity range, not a statistical confidence interval**. It is not a probability forecast of the vendor's true risk.

## Weights, coverage, and missing data

Supply a JSON object such as:

```json
{"cyber": 40, "financial": 20, "operational": 15, "reputational": 10, "regulatory": 15}
```

All finite, nonnegative relative weights are normalized. Percentages and fractions work identically when scaled consistently. At least one weight must be positive; omitted categories have zero weight. Weights express business/user preferences explicitly, and changes can intentionally change rankings.

The default overall headline is the median of weighted Monte Carlo draws from eligible category distributions. The weighted sum of category headlines is also returned as `overall.weighted_category_score`. By default, a category needs at least 10 runs; below 100 runs it is flagged as below the preferred count. Below 10 runs, its descriptive statistics remain visible, but its headline, risk level, and stability are null.

**Missing data is not low risk.** By default, weights are renormalized over eligible categories, with weighted coverage and excluded categories exposed. If cyber and financial cover 70% of requested weight, the score uses those categories with weights summing to one and reports `coverage: 0.7`, `incomplete: true`. Coverage measures availability under the requested weights, not evidence quality. Missing zero-weight categories remain visible but do not lower weighted coverage.

Set `missing_categories` to `"withhold"` to withhold the overall score whenever positive-weight coverage is incomplete. With no eligible positive-weight categories, the overall score and rank are null, never zero. Supply an optional `--entities` JSON object mapping IDs to names to include entities that have no assessments at all.

The overall distribution uses 5,000 seeded simulations by default: independently sample one observed score per eligible category with replacement, then combine using effective weights. It exposes the overall distribution's mean, median, p10, p90, standard deviation, and stability; its median is the default headline. Cross-category dependence is not modeled; see the [methodology](docs/FRAMEWORK.md).

## Frontend / teammate integration

```python
from risk_framework import RiskFramework, load_assessments, load_config, load_json, to_json

framework = RiskFramework(
    load_assessments("examples/sample_assessments.json"),
    load_config("examples/sample_config.json"),
)
weights = load_json("examples/sample_weights.json")
board = framework.score_all(weights)
payload = board.to_dict()     # return through the team's own API
json_text = to_json(board)    # standards-compliant JSON, unavailable values use null
one = framework.score_entity("vendor-alpha", weights)  # no comparative rank

changed_weights = {**weights, "cyber": 10, "financial": 50}
updated = framework.score_all(changed_weights)
```

Keep the framework instance when only weights change; category summaries and raw assessments are reused. Build a new instance when raw assessments or policy change. No AI calls are involved. The functions `score_category`, `normalize_weights`, and `rank_entities` are also public. `framework.assessments` returns a copy of the source records with provenance metadata.

Consume the versioned envelope described by [schemas/scoreboard.schema.json](schemas/scoreboard.schema.json):

```text
schema_version: "1.1"
assessment_count: integer
contains_synthetic_assessments: boolean
input_digest: SHA-256 identifier of assessment content and optional roster
config: resolved policy
weights: supplied weights
normalized_weights: weights across the full category set
records: [
  {
    entity_id, entity_name, entity_type, rank,
    overall: {
      score, score_method, weighted_category_score, risk_level, p10, p90, mean, median, std, spread, stability,
      n, minimum, maximum, p25, p75, iqr, mad,
      coverage, incomplete, status, effective_weights, contributions,
      missing_categories, insufficient_categories, below_preferred_categories
    },
    categories: {
      "<category>": {
        score, risk_level, p10, p90, mean, median, std, spread, stability,
        n, minimum, maximum, p25, p75, iqr, mad,
        status, sufficient, below_preferred_runs
      }
    }
  }
]
```

Rank 1 is highest risk. Exact ties share competition rank (1, 1, 3); tied rows are ordered by entity ID. Unscorable rows come last with null ranks. Partial-coverage rows are still ranked by their available-data score, so display coverage beside the ranking. Category results remain available even if overall scoring is withheld. `overall.score_method` states the selected headline rule. Always display `overall.score`; the default `monte_carlo_median` equals `overall.median`. Collector-only triage uses `weighted_categories`.

Numbers are serialized without display rounding so the calculations remain inspectable. Round only for presentation; show ranges, counts, coverage, and status alongside scores.
