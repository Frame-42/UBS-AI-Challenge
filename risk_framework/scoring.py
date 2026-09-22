"""Pure descriptive aggregation and empirical resampling of AI assessments."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import math
import random
import statistics
from typing import Iterable, Mapping, Sequence

from .config import Config
from .models import CategoryResult, Distribution, EntityResult, OverallResult
from .validation import ValidationError, identifier, number


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear interpolation at (n - 1) * q / 100, including singleton inputs."""
    position = (len(sorted_values) - 1) * q / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def describe(values: Sequence[float]) -> Distribution:
    if not values:
        return Distribution(n=0, **{name: None for name in (
            "mean", "median", "std", "minimum", "maximum", "p10", "p25",
            "p75", "p90", "iqr", "mad", "spread")})
    ordered = sorted(values)
    median = statistics.median(ordered)
    p10, p25, p75, p90 = (percentile(ordered, q) for q in (10, 25, 75, 90))
    return Distribution(
        n=len(ordered), mean=statistics.fmean(ordered), median=median,
        std=statistics.pstdev(ordered), minimum=ordered[0], maximum=ordered[-1],
        p10=p10, p25=p25, p75=p75, p90=p90, iqr=p75-p25,
        mad=statistics.median(abs(value-median) for value in ordered), spread=p90-p10,
    )


def score_category(values: Sequence[float], config: Config) -> CategoryResult:
    checked = tuple(number(v, "risk_score", config.risk_scale.min, config.risk_scale.max) for v in values)
    stats = describe(checked)
    enough = stats.n >= config.minimum_runs.minimum_required
    score = None
    if enough:
        method = config.category_aggregation
        if method.method == "median":
            score = stats.median
        elif method.method == "mean":
            score = stats.mean
        elif method.method == "percentile":
            score = percentile(sorted(checked), method.percentile)
        else:
            score = (1-method.alpha) * stats.median + method.alpha * stats.p90
    return CategoryResult(
        **asdict(stats), score=score,
        risk_level=config.risk_level(score) if score is not None else None,
        stability=config.stability_label(stats.spread) if enough else None,
        status="available" if enough else "missing" if not checked else "insufficient_runs",
        sufficient=enough, below_preferred_runs=stats.n < config.minimum_runs.preferred,
    )


def normalize_weights(weights: Mapping[str, float], categories: Iterable[str]) -> dict[str, float]:
    """Accept relative nonnegative weights; use scaling to avoid sum overflow."""
    if not isinstance(weights, Mapping) or not weights:
        raise ValidationError("weights must be a nonempty mapping")
    known = set(categories)
    checked = {}
    for key, value in weights.items():
        identifier(key, "weight category")
        if key not in known:
            raise ValidationError(f"Unknown weight category: {key}")
        checked[key] = number(value, f"weight[{key}]", 0)
    largest = max(checked.values())
    if largest == 0:
        raise ValidationError("At least one category weight must be positive")
    scaled = {key: value / largest for key, value in checked.items()}
    total = math.fsum(scaled.values())
    result = {key: scaled.get(key, 0.0) / total for key in sorted(known)}
    if any(value > 0 and result[key] == 0 for key, value in checked.items()):
        raise ValidationError("Weight magnitudes differ too much to normalize without losing a positive weight")
    return result


def score_overall(entity_id: str, scores: Mapping[str, Sequence[float]],
                  categories: Mapping[str, CategoryResult], weights: Mapping[str, float],
                  config: Config, *, simulate: bool = True) -> OverallResult:
    """Sample category marginals independently; this does not estimate true-risk probabilities."""
    method = config.overall_simulation.headline_method
    if not simulate and method != "weighted_categories":
        raise ValidationError("Monte Carlo headline requires simulation; use weighted_categories for point-only scoring")
    normalized = normalize_weights(weights, categories)
    positive = [key for key in sorted(categories) if normalized[key] > 0]
    available = [key for key in positive if categories[key].sufficient]
    missing = tuple(key for key in positive if categories[key].status == "missing")
    insufficient = tuple(key for key in positive if categories[key].status == "insufficient_runs")
    below_preferred = tuple(key for key in positive if categories[key].below_preferred_runs)
    incomplete = bool(missing or insufficient)
    coverage = min(1.0, math.fsum(normalized[key] for key in available)) if incomplete else 1.0
    status = "available"
    effective, contributions = {}, {}
    simulated: list[float] = []
    headline = None
    if not available:
        status = "unscorable"
    elif incomplete and config.missing_categories == "withhold":
        status = "incomplete_withheld"
    else:
        effective = normalize_weights({key: weights.get(key, 0.0) for key in available}, available)
        contributions = {key: effective[key] * categories[key].score for key in available}
        headline = min(config.risk_scale.max, max(config.risk_scale.min, math.fsum(contributions.values())))
        if simulate:
            draws = {}
            for key in available:
                # Stable across input order, other entities, and changes to user weights.
                seed_material = f"{config.overall_simulation.seed}:{len(entity_id)}:{entity_id}:{key}"
                seed = int.from_bytes(hashlib.sha256(seed_material.encode()).digest(), "big")
                rng = random.Random(seed)
                population = sorted(scores[key])
                draws[key] = [rng.choice(population) for _ in range(config.overall_simulation.runs)]
            simulated = [min(config.risk_scale.max, max(config.risk_scale.min,
                         math.fsum(effective[key] * draws[key][i] for key in available)))
                         for i in range(config.overall_simulation.runs)]
    stats = describe(simulated)
    weighted_category_score = headline
    if headline is not None:
        if method == "monte_carlo_median":
            headline = stats.median
        elif method == "monte_carlo_mean":
            headline = stats.mean
    return OverallResult(
        **asdict(stats), score=headline, score_method=method,
        weighted_category_score=weighted_category_score,
        risk_level=config.risk_level(headline) if headline is not None else None,
        stability=config.stability_label(stats.spread) if simulated else None,
        coverage=coverage, incomplete=incomplete, status=status,
        effective_weights=effective, contributions=contributions,
        missing_categories=missing, insufficient_categories=insufficient,
        below_preferred_categories=below_preferred,
    )


def rank_entities(results: Iterable[EntityResult]) -> tuple[EntityResult, ...]:
    """Highest risk first; exact ties share competition rank; null scores are unranked."""
    ordered = sorted(results, key=lambda row: (
        row.overall.score is None,
        -row.overall.score if row.overall.score is not None else 0,
        row.entity_id,
    ))
    ranked = []
    previous, rank = None, None
    for position, row in enumerate(ordered, 1):
        score = row.overall.score
        if score is None:
            ranked.append(replace(row, rank=None))
            continue
        if score != previous:
            rank = position
        ranked.append(replace(row, rank=rank))
        previous = score
    return tuple(ranked)
