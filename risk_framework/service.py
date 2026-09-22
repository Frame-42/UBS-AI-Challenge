"""Reusable validated assessment snapshot; weight changes need no upstream work."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from typing import Iterable, Mapping

from .config import Config, load_config
from .models import Assessment, EntityResult, Scoreboard
from .scoring import normalize_weights, rank_entities, score_category, score_overall
from .validation import ValidationError, identifier, number


class RiskFramework:
    """Validate once and cache category summaries. Create a new snapshot when data changes."""

    def __init__(self, assessments: Iterable[Assessment | dict], config: Config | None = None,
                 *, entities: Mapping[str, str] | None = None) -> None:
        self._config = config or load_config()
        self._names: dict[str, str] = {}
        self._types: dict[str, str] = {}
        if entities is not None:
            if not isinstance(entities, Mapping):
                raise ValidationError("entities must map entity IDs to display names")
            for key, value in entities.items():
                self._names[identifier(key, "entity_id")] = identifier(value, "entity_name")
        raw = []
        grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        seen = set()
        for index, item in enumerate(assessments, 1):
            try:
                # Revalidate and copy even model inputs, including their metadata.
                assessment = Assessment.from_dict(deepcopy(asdict(item) if isinstance(item, Assessment) else item))
                number(assessment.risk_score, "risk_score", self.config.risk_scale.min, self.config.risk_scale.max)
                if self.config.categories is not None and assessment.category not in self.config.categories:
                    raise ValidationError(f"Unknown assessment category: {assessment.category}")
                if assessment.run_id is not None:
                    key = (assessment.entity_id, assessment.category, str(assessment.run_id))
                    if key in seen:
                        raise ValidationError(f"Duplicate run_id for entity/category: {key}")
                    seen.add(key)
                for value, mapping, label in ((assessment.entity_name, self._names, "entity_name"),
                                              (assessment.entity_type, self._types, "entity_type")):
                    if value is not None:
                        previous = mapping.get(assessment.entity_id)
                        if previous is not None and previous != value:
                            raise ValidationError(f"Conflicting {label} for {assessment.entity_id}")
                        mapping[assessment.entity_id] = value
                grouped[assessment.entity_id][assessment.category].append(float(assessment.risk_score))
                raw.append(assessment)
            except ValidationError as exc:
                raise ValidationError(f"Assessment {index}: {exc}") from exc
        self._assessments = tuple(raw)
        self._scores = {entity: {category: tuple(sorted(values)) for category, values in groups.items()}
                        for entity, groups in grouped.items()}
        for entity in self._names:
            self._scores.setdefault(entity, {})
        self._observed_categories = {category for groups in self._scores.values() for category in groups}
        self._summaries = {entity: {category: score_category(values, self.config)
                                   for category, values in groups.items()}
                           for entity, groups in self._scores.items()}
        canonical = {
            "assessments": sorted(json.dumps(asdict(a), sort_keys=True, allow_nan=False) for a in raw),
            "entities": dict(entities) if entities is not None else {},
        }
        self.input_digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

    @property
    def config(self) -> Config:
        """Immutable policy for this snapshot; rebuild to change scoring policy."""
        return self._config

    @property
    def assessments(self) -> tuple[Assessment, ...]:
        """Copy of the source records, retaining optional provenance metadata."""
        return deepcopy(self._assessments)

    def _categories_and_weights(self, weights: Mapping[str, float]) -> tuple[list[str], dict[str, float]]:
        if not isinstance(weights, Mapping):
            raise ValidationError("weights must be a mapping")
        for key in weights:
            identifier(key, "weight category")
        categories = sorted(self.config.categories if self.config.categories is not None
                            else self._observed_categories | set(weights))
        return categories, normalize_weights(weights, categories)

    def _score(self, entity_id: str, categories: list[str], weights: Mapping[str, float],
               *, simulate: bool = True) -> EntityResult:
        if entity_id not in self._scores:
            raise ValidationError(f"Unknown entity_id: {entity_id}")
        summaries = {key: self._summaries[entity_id].get(key) or score_category((), self.config)
                     for key in categories}
        return EntityResult(
            entity_id=entity_id, entity_name=self._names.get(entity_id, entity_id),
            entity_type=self._types.get(entity_id), categories=summaries,
            overall=score_overall(entity_id, self._scores[entity_id], summaries, weights, self.config, simulate=simulate),
        )

    def score_entity(self, entity_id: str, weights: Mapping[str, float]) -> EntityResult:
        """Score a single known entity; rank remains null until compared with others."""
        categories, _ = self._categories_and_weights(weights)
        return self._score(entity_id, categories, weights)

    def score_all(self, weights: Mapping[str, float], *, simulate: bool = True) -> Scoreboard:
        """Recompute overall distributions and rankings using cached category results."""
        categories, normalized = self._categories_and_weights(weights)
        return Scoreboard(
            schema_version="1.1", assessment_count=len(self._assessments),
            contains_synthetic_assessments=any(a.metadata.get("synthetic") is True for a in self._assessments),
            input_digest=self.input_digest, config=self.config.to_dict(), weights=dict(weights),
            normalized_weights=normalized,
            records=rank_entities(self._score(entity, categories, weights, simulate=simulate) for entity in self._scores),
        )
