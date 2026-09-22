"""Synthetic repeated assessments for demos only; this module never calls an AI model."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import random

from .collection import CollectedData
from .config import Config
from .models import Assessment
from .validation import number


def simulate_assessments(collection: CollectedData, config: Config) -> tuple[Assessment, ...]:
    """Generate seeded clipped-normal scores around eligible collector summaries.

    Missing findings remain missing. Configured exclusions (financial by default)
    apply even when a saved report contains a financial heuristic placeholder.
    """
    policy = config.assessment_simulation
    settings = asdict(policy)
    settings["excluded_categories"] = list(policy.excluded_categories)
    assessments = []
    for base in sorted(collection.assessments, key=lambda a: (a.entity_id, a.category)):
        if base.category in policy.excluded_categories:
            continue
        if config.categories is not None and base.category not in config.categories:
            continue
        center = number(base.risk_score, "simulation center", config.risk_scale.min, config.risk_scale.max)
        seed_material = json.dumps(["synthetic-assessments-v1", policy.seed, base.entity_id, base.category])
        rng = random.Random(int.from_bytes(hashlib.sha256(seed_material.encode()).digest(), "big"))
        std = rng.uniform(policy.spread_std_min, policy.spread_std_max)
        for run in range(policy.runs):
            value = min(config.risk_scale.max, max(config.risk_scale.min, rng.gauss(center, std)))
            assessments.append(Assessment(
                entity_id=base.entity_id, entity_name=base.entity_name, entity_type=base.entity_type,
                category=base.category, risk_score=value, run_id=run,
                timestamp=base.timestamp, agent_id="synthetic-assessment-generator-v1",
                metadata={
                    "synthetic": True, "distribution": "clipped_normal",
                    "center": center, "spread_std": std, "simulation": settings.copy(),
                    "collection_digest": collection.digest,
                    "timestamp_basis": "source_report_time_not_ai_execution",
                },
            ))
    return tuple(assessments)
