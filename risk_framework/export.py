"""Website-ready data contract; no HTTP server or frontend is required."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Iterable, Mapping

from .collection import CollectedData
from .config import Config, load_config
from .models import Assessment
from .service import RiskFramework
from .validation import ValidationError


class WebsiteDataset:
    """Join collected evidence to reusable scores under one explicit score basis."""

    def __init__(self, collection: CollectedData, config: Config | None = None, *,
                 assessments: Iterable[Assessment | dict] | None = None) -> None:
        self._collection = deepcopy(collection)
        cfg = config or load_config()
        self._triage = assessments is None
        if self._triage:
            # One upstream heuristic summary is sufficient only for provisional triage.
            # Ensemble mode always keeps the normal assessment eligibility policy.
            cfg = replace(cfg, minimum_runs=replace(cfg.minimum_runs, minimum_required=1),
                          overall_simulation=replace(cfg.overall_simulation, headline_method="weighted_categories"))
            if cfg.category_aggregation.method != "median":
                raise ValidationError("Collector triage uses the supplied summary unchanged; aggregation must be median")
        self._framework = RiskFramework(collection.assessments if self._triage else assessments,
                                        cfg, entities=collection.entities)
        flags = {a.metadata.get("synthetic") is True for a in self._framework.assessments}
        if len(flags) > 1:
            raise ValidationError("Do not mix synthetic assessments and real assessments in one website dataset")
        self._synthetic = flags == {True}
        if not self._triage:
            unknown = {a.entity_id for a in self._framework.assessments} - set(collection.entities)
            if unknown:
                raise ValidationError(f"Agent assessment entity IDs do not match collected entities: {sorted(unknown)}")

    def score(self, weights: Mapping[str, float]) -> dict:
        """Reweight a snapshot without re-collecting data or requesting assessments."""
        board = self._framework.score_all(weights, simulate=not self._triage).to_dict()
        if self._triage:
            # A single deterministic heuristic is not an assessment distribution.
            for entity in board["records"]:
                for category in entity["categories"].values():
                    for key in ("p10", "p25", "p75", "p90", "spread", "std", "iqr", "mad", "stability"):
                        category[key] = None
        return {
            "schema_version": "1.1",
            "score_basis": "collector_heuristic" if self._triage else "simulated_ai_assessments" if self._synthetic else "ai_assessments",
            "distribution_semantics": "not_available" if self._triage else "synthetic_assessment_spread" if self._synthetic else "ai_assessment_disagreement",
            "collection_digest": self._collection.digest,
            "scoreboard": board,
            "evidence": deepcopy(self._collection.evidence),
        }


def export_json(payload: dict | list, output: str | Path, *, protected_paths: Iterable[Path] = ()) -> None:
    """Atomically replace the website snapshot so readers never see a partial JSON file."""
    import os
    import tempfile

    path = Path(output)
    if any(path.resolve() == Path(p).resolve() for p in protected_paths):
        raise ValidationError("Output must not overwrite an input file")
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
