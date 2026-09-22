# Third-Party Risk Intelligence: scoring methodology and contract

The framework converts supplied repeated AI assessments into category summaries and a user-weighted risk scoreboard. It does not retrieve evidence or assess whether the supplied evidence is complete, credible, or current. A risk score is an analytical prioritization signal, not proof that a vendor is unsafe. Higher values always mean higher risk.

## 1. Scope and input validation

The canonical record is defined by `Assessment` in `risk_framework/models.py` and [the input schema](../schemas/assessment.schema.json). JSON files contain an array of records; JSONL files contain one record per nonblank line. A record requires an entity ID, category, and numeric score in [0, 100]. Optional entity name/type, run ID, timezone-bearing ISO 8601 timestamp, agent ID, and JSON metadata preserve context. Missing entity names fall back to the ID; missing entity types stay null.

Validation is strict and atomic: a malformed record rejects the batch, with record/line context, rather than silently dropping evidence. Numeric strings, booleans, NaN/infinities, scores outside the scale, blank/whitespace-padded identifiers, unknown fields, duplicate JSON keys, and conflicting entity names/types are rejected. A custom `risk_scale` can restrict the allowed range within [0, 100]; it does not rescale scores, and risk levels must cover the restricted scale.

Run IDs must be nonnegative integers or nonempty strings. Uniqueness is scoped to `(entity_id, category, textual run_id)`: integer `17` and string `"17"` identify the same run. Agent IDs do not provide an additional namespace; upstream producers should use globally distinct run IDs within each entity/category. Without run IDs, every row contributes once, including identical rows. Run IDs do not pair observations across categories.

The service retains optional metadata and exposes a defensive copy through `framework.assessments`. Metadata does not change weights or scores. It is omitted from compact scoreboard results; the caller retains the raw input alongside the payload for a full audit. The input digest is SHA-256 over a deterministic serialization of the assessment records and optional entity roster, insensitive to record order. It identifies content, not authenticity. Persist the input, resolved config, weights, and implementation version when saving a result.

All supplied rows are pooled per entity/category. The producer must select a coherent evidence batch, time window, agent mix, and scoring rubric before ingestion. No freshness filtering, automatic evidence deduplication, agent-quality weighting, or credibility inference is performed. Different run counts give different empirical distributions; they do not change business category weights.

## 2. Category configuration

With `categories: null`, the effective category set is the union of input categories and user-weight keys. This supports any category without code changes, including a requested category missing from every entity. It cannot distinguish a new category from a typo. An explicit nonempty category list is therefore recommended for integration: unknown assessment or weight keys fail validation. Configured categories omitted from weights have zero weight but still appear in category results.

A `RiskFramework` instance is a validated data snapshot. It caches category summaries and keeps the raw score distributions. `score_entity(id, weights)` computes one result; `score_all(weights)` computes a ranked envelope. Reuse the instance for arbitrary weight changes. Create a new instance for new data or policy. An optional `entities={"id": "Display name"}` roster includes entities without any observations. Without such a roster, an entity never mentioned in the input is unknown. Empty data without a roster produces an empty scoreboard.

## 3. Descriptive statistics and headline category scores

For entity e and category c, let the supplied scores be x₁,…,xₙ. Every run has equal weight within its category. Statistics describe the supplied finite ensemble:

```text
mean = Σ xᵢ / n
median = middle ordered value (average the two central values when n is even)
std = sqrt(Σ (xᵢ - mean)² / n)
IQR = p75 - p25
MAD = median(|xᵢ - median|)
spread = p90 - p10
```

Standard deviation uses the population denominator n, not n−1. MAD is unscaled. For percentile q, sort scores as y₀,…,yₙ₋₁, set h=(n−1)q/100, j=floor(h), k=ceil(h), and t=h−j:

```text
p_q = (1 - t) × y_j + t × y_k
```

A singleton has all percentiles equal to its value and zero spread/std. No observations produce `n: 0` and null descriptive statistics. No missing observation is imputed as zero.

Default headline category score rₑ,c is the median. Configured alternatives are:

| `category_aggregation.method` | Headline |
| --- | --- |
| `median` | Median of raw assessments |
| `mean` | Arithmetic mean |
| `percentile` | Percentile selected by `percentile` in [0, 100] |
| `risk_adjusted` | `(1 - alpha) × median + alpha × p90`, with alpha in [0, 1] |

Defaults are median, percentile parameter 90, and alpha 0.25. The latter two parameters apply only to their respective methods. With an outlier, the median can remain stable even as the mean and maximum change; the descriptive results preserve that information.

## 4. Eligibility, stability, and labels

The default `minimum_runs.minimum_required` is 10 and `preferred` is 100. These are operational policies, not statistical guarantees. Categories return:

| Status | Meaning | Headline/stability |
| --- | --- | --- |
| `missing` | n = 0 | null |
| `insufficient_runs` | 0 < n < minimum_required | null; descriptive statistics retained |
| `available` | n ≥ minimum_required | calculated |

`below_preferred_runs` is true whenever n < preferred, including missing categories. `sufficient` indicates minimum eligibility only. Thus 30 stable assessments can have `stability: "HIGH"` and `below_preferred_runs: true`. Neither label establishes evidence quality. Lowering minimum_required to 1 is allowed, but makes a singleton eligible with zero observed spread; consumers must keep n visible.

Stability uses p90−p10, with inclusive configurable maximums:

```text
HIGH:   spread ≤ high_max_p10_p90_spread           (default 15)
MEDIUM: high threshold < spread ≤ medium threshold (default 30)
LOW:    spread > medium threshold
```

Risk levels use the headline score and configured increasing upper bounds:

```text
LOW       [0, 20)
GUARDED   [20, 40)
MODERATE  [40, 60)
HIGH      [60, 80)
CRITICAL  [80, 100]
```

A threshold value belongs to the next band, except the scale maximum, which belongs to the last band. Labels and bounds can be changed together in config; bounds must be strictly increasing, labels unique, and the final bound must equal the scale maximum. Unavailable headlines have null risk levels.

Repeated LLM judgments are not statistically independent observations of objective reality. Shared prompts, evidence, model behavior, or systematic errors can make repeated answers agree while remaining wrong. A p10–p90 range is an **AI-assessment disagreement/sensitivity range, not a statistical confidence interval**. It does not mean there is a 90% probability that real risk lies within it. Stability is agreement in this supplied ensemble, not confidence in truth. Tail outliers outside p10–p90 remain visible in min/max and standard deviation.

## 5. User weights and coverage

Let u_c be a supplied nonnegative finite relative category weight. At least one must be positive; omitted categories have u_c=0. Percentages, fractions, or other consistently scaled nonnegative weights are normalized:

```text
w_c = u_c / Σ u_j
```

The implementation scales by the largest weight first to avoid overflow. It rejects extreme dynamic ranges that would round a positive normalized weight to zero. It does not infer units: mixing `35` and `0.2` means relative weights 35 and 0.2, not 35% and 20%. The envelope returns both original and normalized weights.

Let Aₑ contain the positive-weight categories for entity e that meet minimum_required:

```text
coverageₑ = Σ[c ∈ Aₑ] w_c
```

With default `missing_categories: "renormalize"`:

```text
w*ₑ,c = w_c / coverageₑ      for c ∈ Aₑ
Rₑ = Σ[c ∈ Aₑ] w*ₑ,c × rₑ,c
```

For complete data this is simply `Rₑ = Σ w_c × rₑ,c`. This weighted category headline is `overall.score`. The category median default is robust, while weights remain an explicit business/user preference.

Example: weights cyber 0.4, financial 0.3, regulatory 0.3; scores cyber 80, financial 20, regulatory missing. Coverage is 0.7, effective weights are 4/7 and 3/7, and the headline is about 54.3. It is not 38, which would incorrectly treat missing regulatory risk as zero.

`incomplete` is true if any positive-weight category is missing or insufficient. It does not mean merely below the preferred run count. Missing zero-weight categories remain in `categories`, but do not affect coverage or incomplete. `overall.below_preferred_categories` lists positive-weight categories below the preferred count, including missing ones. Coverage is availability under the chosen weights, not a measure of all relevant vendor evidence.

`effective_weights` lists the contributing categories and `contributions[c]` is effective weight × category headline. Their sum reproduces the overall headline up to floating-point arithmetic. With no contributing categories, all overall descriptive statistics and the headline are null, n=0, coverage=0, and status=`unscorable`. With `missing_categories: "withhold"`, incomplete but partly available entities have null overall values and status=`incomplete_withheld`; coverage and category results remain visible. In both cases effective weights and contributions are empty.

Partial-coverage scores are available-data scores. Two entities with different excluded categories are not necessarily directly comparable. The default ranking still orders them numerically and exposes their coverage; use withhold policy when complete positive-weight coverage is required for ranking. There is no hidden missing-data penalty or risk imputation.

## 6. Overall assessment distribution

For each of B simulations (default B=5,000):

1. Independently sample one raw score, with replacement, from each category in Aₑ.
2. Combine those scores using the same effective weights w*ₑ,c.
3. Store the combined score Sₑ,b.

```text
x*ₑ,c,b ← empirical distribution of supplied category scores
Sₑ,b = Σ[c ∈ Aₑ] w*ₑ,c × x*ₑ,c,b
```

Compute mean, median, population std, p10, p90, spread, and the other descriptive statistics from Sₑ,1,…,Sₑ,B. Apply the same stability thresholds to its spread. `overall.n` is the number of simulated scores, not the number of AI runs. The entity's overall risk level uses `overall.score`, not the simulated mean or median.

This procedure samples individual assessments, not bootstrap estimates of a median or uncertainty in a mean. More input runs do not shrink the range by a 1/√n rule. More simulations improve the numerical approximation to the combined supplied distributions; they add no new evidence. The headline weighted combination of category medians need not equal the median of simulated combinations and, particularly with percentile/risk-adjusted policies, need not fall inside the simulated p10–p90 range. The outputs answer different descriptive questions.

Sampling category marginals independently is an explicit modeling assumption. There is no information in this contract identifying correlated or paired scenarios; equal run IDs are not assumed to imply paired draws. Cross-category dependence could materially change the overall spread, so the simulated range can understate or overstate joint disagreement. It is not a probabilistic forecast of the vendor's true risk or a probability of a future loss.

For reproducibility, each entity/category gets a local `random.Random` stream derived from SHA-256 of the configured seed, length-prefixed entity ID, and category. Populations and categories are sorted before sampling. The global random state is untouched. Identical data, policy, weights, and Python implementation produce identical results; reordering records, adding another entity, or changing weight-key order does not alter an entity's simulation. Weight changes reuse the same seeded category draws so random resampling does not add avoidable noise to comparisons. Draws are recomputed from cached raw distributions; no agents are rerun. For byte-for-byte long-term replay, also pin the Python runtime and framework revision.

## 7. Scoreboard contract and ranking

The CLI's default JSON output and `to_json(framework.score_all(weights))` share [schemas/scoreboard.schema.json](../schemas/scoreboard.schema.json). `Scoreboard.to_dict()` returns the same structure as Python dictionaries/lists. JSON output uses null for unavailable values, never NaN or Infinity. It preserves numeric precision; consumers choose display rounding.

The top-level envelope contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Contract version, currently `"1.0"` |
| `assessment_count` | Number of validated supplied assessments |
| `input_digest` | Content identifier for assessments and optional entity roster |
| `config` | Fully resolved policy, including seed and simulation count |
| `weights` | Original supplied category weights |
| `normalized_weights` | Normalized weights for the resolved category set |
| `records` | Ranked entity results |

Each entity contains `entity_id`, display `entity_name`, nullable `entity_type`, `overall`, `categories`, and nullable `rank`. Category keys are dynamic. Each category and overall object exposes `n`, `mean`, `median`, `std`, `minimum`, `maximum`, `p10`, `p25`, `p75`, `p90`, `iqr`, `mad`, and `spread`. Category n counts raw assessments; overall n counts simulations.

Both expose nullable `score`, `risk_level`, and `stability`. Categories add `status`, `sufficient`, and `below_preferred_runs`. Overall adds `coverage`, `incomplete`, `status`, `effective_weights`, `contributions`, and the arrays `missing_categories`, `insufficient_categories`, and `below_preferred_categories`. Exclusion arrays concern positive-weight categories only. Overall status is `available`, `incomplete_withheld`, or `unscorable`.

`rank_entities(results)` and `score_all(weights)` rank descending by full-precision overall score. Rank 1 is highest risk. Exactly equal scores share competition rank: 1, 1, 3. Entity ID orders tied rows deterministically. No tolerance or display rounding defines a tie. Unavailable scores appear last in entity-ID order and have null rank. `score_entity()` alone has null rank because it makes no cross-entity comparison.

There is no claim of rank certainty. Overlapping ranges are not converted into probabilities of one vendor being riskier. Category results are always preserved; an aggregate can mask a high category risk through compensation, so a frontend should show the category breakdown, counts, coverage, and disagreement alongside the overall score. Changing user weights can change rankings, intentionally and transparently.

## 8. Configuration and operation

[risk_framework/defaults.json](../risk_framework/defaults.json) is the single source of default policy. `load_config(path)` accepts a partial JSON override; nested section fields merge into defaults, while arrays such as categories and risk_levels replace the entire array. Unknown fields, invalid bounds, nonpositive simulation counts, invalid seeds, and incoherent minimum/preferred run counts fail validation. The config and its nested policy models are frozen dataclasses.

```json
{
  "categories": ["cyber", "financial", "regulatory"],
  "category_aggregation": {"method": "median"},
  "overall_simulation": {"runs": 5000, "seed": 42},
  "minimum_runs": {"minimum_required": 10, "preferred": 100},
  "missing_categories": "renormalize"
}
```

The seed is a nonnegative integer; simulation runs must be a positive integer. Stability bounds are nonnegative and ordered. Preferred runs must be at least minimum_required. Policy defaults are prototype choices for the challenge, not empirically calibrated UBS risk thresholds.

`python3 -m unittest discover -s tests -v` runs the full offline suite. The README's CLI examples exercise the same service as programmatic consumers. JSON stdout is clean; `--format table` offers a readable local view and `--output PATH` writes a file. The CLI prevents output from overwriting any of its supplied input paths. An optional `--entities roster.json` uses the same ID-to-name mapping as the programmatic roster.

Recomputation requires no network or persistence infrastructure: construct a snapshot after upstream data changes, keep it for weight adjustments, and hand a fresh JSON envelope to the downstream application. There is no automatic background refresh, append API, historical database, or websocket service.
