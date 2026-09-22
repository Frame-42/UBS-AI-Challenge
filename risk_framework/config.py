"""Validated policy; all default choices live in defaults.json."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .validation import ValidationError, identifier, integer, number, object_fields, parse_json


@dataclass(frozen=True)
class RiskScale:
    min: float
    max: float

    def __post_init__(self) -> None:
        number(self.min, "risk_scale.min", 0, 100)
        number(self.max, "risk_scale.max", 0, 100)
        if self.min >= self.max:
            raise ValidationError("risk_scale.min must be below max")


@dataclass(frozen=True)
class Aggregation:
    method: str
    percentile: float
    alpha: float

    def __post_init__(self) -> None:
        if self.method not in ("median", "mean", "percentile", "risk_adjusted"):
            raise ValidationError("Unknown category aggregation method")
        number(self.percentile, "percentile", 0, 100)
        number(self.alpha, "alpha", 0, 1)


@dataclass(frozen=True)
class Simulation:
    runs: int
    seed: int
    headline_method: str

    def __post_init__(self) -> None:
        integer(self.runs, "simulation.runs", 1)
        integer(self.seed, "simulation.seed")
        if self.headline_method not in ("monte_carlo_median", "monte_carlo_mean", "weighted_categories"):
            raise ValidationError("Unknown overall headline_method")


@dataclass(frozen=True)
class AssessmentSimulation:
    runs: int
    seed: int
    spread_std_min: float
    spread_std_max: float
    excluded_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        integer(self.runs, "assessment_simulation.runs", 1)
        integer(self.seed, "assessment_simulation.seed")
        low = number(self.spread_std_min, "spread_std_min", 0, 100)
        number(self.spread_std_max, "spread_std_max", low, 100)
        if low == 0:
            raise ValidationError("spread_std_min must be positive")
        if not isinstance(self.excluded_categories, tuple):
            raise ValidationError("excluded_categories must be a tuple")
        for category in self.excluded_categories:
            identifier(category, "excluded category")
        if len(set(self.excluded_categories)) != len(self.excluded_categories):
            raise ValidationError("Duplicate excluded categories")


@dataclass(frozen=True)
class Stability:
    high_max_p10_p90_spread: float
    medium_max_p10_p90_spread: float

    def __post_init__(self) -> None:
        high = number(self.high_max_p10_p90_spread, "high stability spread", 0)
        number(self.medium_max_p10_p90_spread, "medium stability spread", high)


@dataclass(frozen=True)
class MinimumRuns:
    preferred: int
    minimum_required: int

    def __post_init__(self) -> None:
        integer(self.minimum_required, "minimum_required", 1)
        integer(self.preferred, "preferred", self.minimum_required)


@dataclass(frozen=True)
class RiskLevel:
    label: str
    upper: float

    def __post_init__(self) -> None:
        identifier(self.label, "risk level label")
        number(self.upper, "risk level upper", 0, 100)


@dataclass(frozen=True)
class Config:
    categories: tuple[str, ...] | None
    risk_scale: RiskScale
    category_aggregation: Aggregation
    overall_simulation: Simulation
    assessment_simulation: AssessmentSimulation
    stability: Stability
    risk_levels: tuple[RiskLevel, ...]
    minimum_runs: MinimumRuns
    missing_categories: str

    def __post_init__(self) -> None:
        if self.categories is not None:
            if not isinstance(self.categories, tuple) or not self.categories:
                raise ValidationError("categories must be a nonempty tuple or null")
            for category in self.categories:
                identifier(category, "category")
            if len(set(self.categories)) != len(self.categories):
                raise ValidationError("Duplicate configured categories")
        if self.missing_categories not in ("renormalize", "withhold"):
            raise ValidationError("missing_categories must be renormalize or withhold")
        previous = self.risk_scale.min
        labels = set()
        for level in self.risk_levels:
            if level.label in labels or not previous < level.upper <= self.risk_scale.max:
                raise ValidationError("Risk levels must have unique labels and increasing bounds within the scale")
            labels.add(level.label)
            previous = level.upper
        if not self.risk_levels or previous != self.risk_scale.max:
            raise ValidationError("Risk levels must cover the entire configured scale")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["assessment_simulation"]["excluded_categories"] = list(self.assessment_simulation.excluded_categories)
        result["categories"] = list(self.categories) if self.categories is not None else None
        result["risk_levels"] = [asdict(level) for level in self.risk_levels]
        return result

    def risk_level(self, score: float) -> str:
        for level in self.risk_levels:
            if score < level.upper:
                return level.label
        return self.risk_levels[-1].label

    def stability_label(self, spread: float) -> str:
        if spread <= self.stability.high_max_p10_p90_spread:
            return "HIGH"
        if spread <= self.stability.medium_max_p10_p90_spread:
            return "MEDIUM"
        return "LOW"


def load_config(path: str | Path | None = None, *, overrides: dict | None = None) -> Config:
    """Merge a partial JSON config into defaults; reject unknown or invalid policies."""
    data = parse_json(Path(__file__).with_name("defaults.json").read_text(encoding="utf-8"))
    if path is not None and overrides is not None:
        raise ValidationError("Supply a config path or overrides, not both")
    changes = parse_json(Path(path).read_text(encoding="utf-8")) if path is not None else overrides
    if path is not None and changes is None:
        raise ValidationError("config must be a JSON object")
    if changes is not None:
        object_fields(changes, set(data), set(), "config")
        for key, value in changes.items():
            if isinstance(data[key], dict):
                object_fields(value, set(data[key]), set(), key)
                data[key].update(value)
            else:
                data[key] = value
    categories = data["categories"]
    if categories is not None and not isinstance(categories, list):
        raise ValidationError("categories must be an array or null")
    if not isinstance(data["risk_levels"], list):
        raise ValidationError("risk_levels must be an array")
    levels = []
    for level in data["risk_levels"]:
        object_fields(level, {"label", "upper"}, {"label", "upper"}, "risk level")
        levels.append(RiskLevel(**level))
    mock = dict(data["assessment_simulation"])
    if not isinstance(mock["excluded_categories"], list):
        raise ValidationError("assessment_simulation.excluded_categories must be an array")
    mock["excluded_categories"] = tuple(mock["excluded_categories"])
    return Config(
        categories=tuple(categories) if categories is not None else None,
        risk_scale=RiskScale(**data["risk_scale"]),
        category_aggregation=Aggregation(**data["category_aggregation"]),
        overall_simulation=Simulation(**data["overall_simulation"]),
        assessment_simulation=AssessmentSimulation(**mock),
        stability=Stability(**data["stability"]),
        risk_levels=tuple(levels),
        minimum_runs=MinimumRuns(**data["minimum_runs"]),
        missing_categories=data["missing_categories"],
    )
