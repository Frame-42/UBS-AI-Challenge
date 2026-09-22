"""Canonical input and frontend result contracts, with no frontend dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
import re
from typing import Any

from .validation import ValidationError, identifier, integer, json_value, number, object_fields


@dataclass(frozen=True)
class Assessment:
    entity_id: str
    category: str
    risk_score: float
    entity_name: str | None = None
    entity_type: str | None = None
    run_id: str | int | None = None
    timestamp: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier(self.entity_id, "entity_id")
        identifier(self.category, "category")
        number(self.risk_score, "risk_score", 0, 100)
        for name in ("entity_name", "entity_type", "agent_id"):
            value = getattr(self, name)
            if value is not None:
                identifier(value, name)
        if self.run_id is not None:
            if isinstance(self.run_id, str):
                identifier(self.run_id, "run_id")
            else:
                integer(self.run_id, "run_id")
        if self.timestamp is not None:
            identifier(self.timestamp, "timestamp")
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", self.timestamp):
                    raise ValueError("timestamp must include date, time, and timezone")
                parsed = datetime.fromisoformat(self.timestamp.upper().replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    raise ValueError("timezone required")
            except ValueError as exc:
                raise ValidationError("timestamp must be ISO 8601 with timezone") from exc
        if not isinstance(self.metadata, dict):
            raise ValidationError("metadata must be a JSON object")
        json_value(self.metadata)

    @classmethod
    def from_dict(cls, value: dict) -> Assessment:
        object_fields(value, {f.name for f in fields(cls)},
                      {"entity_id", "category", "risk_score"}, "assessment")
        return cls(**value)


@dataclass(frozen=True)
class Distribution:
    n: int
    mean: float | None
    median: float | None
    std: float | None
    minimum: float | None
    maximum: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    iqr: float | None
    mad: float | None
    spread: float | None


@dataclass(frozen=True)
class CategoryResult(Distribution):
    score: float | None
    risk_level: str | None
    stability: str | None
    status: str
    sufficient: bool
    below_preferred_runs: bool


@dataclass(frozen=True)
class OverallResult(Distribution):
    score: float | None
    risk_level: str | None
    stability: str | None
    coverage: float
    incomplete: bool
    status: str
    effective_weights: dict[str, float]
    contributions: dict[str, float]
    missing_categories: tuple[str, ...]
    insufficient_categories: tuple[str, ...]
    below_preferred_categories: tuple[str, ...]


@dataclass(frozen=True)
class EntityResult:
    entity_id: str
    entity_name: str
    entity_type: str | None
    overall: OverallResult
    categories: dict[str, CategoryResult]
    rank: int | None = None


@dataclass(frozen=True)
class Scoreboard:
    schema_version: str
    assessment_count: int
    input_digest: str
    config: dict[str, Any]
    weights: dict[str, float]
    normalized_weights: dict[str, float]
    records: tuple[EntityResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return plain JSON-compatible objects, including arrays rather than tuples."""
        def plain(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: plain(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [plain(v) for v in value]
            return value
        return plain(asdict(self))
