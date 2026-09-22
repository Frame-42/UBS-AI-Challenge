# UBS Third-Party Risk Intelligence Framework

Turn repeated AI risk assessments into transparent category scores, disagreement ranges, weighted overall scores, and ranked JSON for a separate scoreboard. Higher values always mean higher risk, on a 0–100 scale.

The framework begins with assessments supplied by another team. It does not research vendors, retrieve evidence, call LLMs, orchestrate agents, or provide a frontend, database, or UBS integration. A risk score is an analytical prioritization signal, not proof that a vendor is unsafe.

## Run it

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

The overall headline is the weighted sum of eligible category scores. By default, a category needs at least 10 runs; below 100 runs it is flagged as below the preferred count. Below 10 runs, its descriptive statistics remain visible, but its headline, risk level, and stability are null.

**Missing data is not low risk.** By default, weights are renormalized over eligible categories, with weighted coverage and excluded categories exposed. If cyber and financial cover 70% of requested weight, the score uses those categories with weights summing to one and reports `coverage: 0.7`, `incomplete: true`. Coverage measures availability under the requested weights, not evidence quality. Missing zero-weight categories remain visible but do not lower weighted coverage.

Set `missing_categories` to `"withhold"` to withhold the overall score whenever positive-weight coverage is incomplete. With no eligible positive-weight categories, the overall score and rank are null, never zero. Supply an optional `--entities` JSON object mapping IDs to names to include entities that have no assessments at all.

The overall distribution uses 5,000 seeded simulations by default: independently sample one observed score per eligible category with replacement, then combine using effective weights. It exposes the overall distribution's mean, median, p10, p90, standard deviation, and stability, alongside the weighted headline. Cross-category dependence is not modeled; see the [methodology](docs/FRAMEWORK.md).

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
schema_version: "1.0"
assessment_count: integer
input_digest: SHA-256 identifier of assessment content and optional roster
config: resolved policy
weights: supplied weights
normalized_weights: weights across the full category set
records: [
  {
    entity_id, entity_name, entity_type, rank,
    overall: {
      score, risk_level, p10, p90, mean, median, std, spread, stability,
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

Rank 1 is highest risk. Exact ties share competition rank (1, 1, 3); tied rows are ordered by entity ID. Unscorable rows come last with null ranks. Partial-coverage rows are still ranked by their available-data score, so display coverage beside the ranking. Category results remain available even if overall scoring is withheld. Do not substitute the simulated `overall.median` for the configured headline `overall.score`.

Numbers are serialized without display rounding so the calculations remain inspectable. Round only for presentation; show ranges, counts, coverage, and status alongside scores.
