"""Offline adapter for risk_collector reports. Findings are not repeated AI runs."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .io import load_json
from .models import Assessment
from .validation import ValidationError, identifier, integer, number


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValidationError(f"{name} must be an object")
    return value


def _array(value: Any, name: str) -> list:
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be an array")
    return value


def _source(value: Any) -> None:
    source = _object(value, "source")
    for key in ("name", "publisher", "url", "retrieved_at"):
        identifier(source.get(key), f"source.{key}")


def validate_report(value: Any) -> dict:
    """Check the producer boundary without importing or executing any collectors."""
    report = _object(value, "collector report")
    company = _object(report.get("company"), "company")
    identifier(company.get("name"), "company.name")
    # Reuse canonical timestamp validation, with no score imported at this point.
    timestamp = report.get("generated_at")
    identifier(timestamp, "generated_at")
    Assessment("validation", "validation", 0, timestamp=timestamp)
    parameters = _object(report.get("parameters"), "parameters")
    requested = _array(parameters.get("categories"), "parameters.categories")
    for category in requested:
        identifier(category, "requested category")
    if len(set(requested)) != len(requested):
        raise ValidationError("Duplicate requested category")
    counts: Counter[str] = Counter()
    for signal in _array(report.get("signals"), "signals"):
        signal = _object(signal, "signal")
        category = identifier(signal.get("category"), "signal.category")
        if category not in requested:
            raise ValidationError(f"Signal category not requested: {category}")
        counts[category] += 1
        for key in ("title", "collector", "severity"):
            identifier(signal.get(key), f"signal.{key}")
        number(signal.get("confidence"), "signal.confidence", 0, 1)
        sources = _array(signal.get("sources"), "signal.sources")
        if not sources:
            raise ValidationError("Collected signals must cite at least one source")
        for source in sources:
            _source(source)
    summaries = {}
    for summary in _array(report.get("summary"), "summary"):
        summary = _object(summary, "category summary")
        category = identifier(summary.get("category"), "summary.category")
        if category in summaries:
            raise ValidationError(f"Duplicate summary category: {category}")
        number(summary.get("score"), "summary.score", 0, 100)
        count = integer(summary.get("signals"), "summary.signals")
        if count != counts[category]:
            raise ValidationError(f"Signal count mismatch for {category}")
        if count == 0 and summary["score"] != 0:
            raise ValidationError(f"Nonzero heuristic score without signals: {category}")
        summaries[category] = summary
    if set(summaries) != set(requested):
        raise ValidationError("Summary categories must match parameters.categories")
    for check in _array(report.get("sources_consulted"), "sources_consulted"):
        check = _object(check, "source check")
        if check.get("status") not in ("ok", "no_match", "error", "skipped"):
            raise ValidationError("Invalid source check status")
        identifier(check.get("collector"), "check.collector")
        _source(check.get("source"))
    for error in _array(report.get("errors"), "errors"):
        identifier(error, "collection error")
    return deepcopy(report)


@dataclass(frozen=True)
class CollectedData:
    entities: dict[str, str]
    evidence: dict[str, dict[str, Any]]
    assessments: tuple[Assessment, ...]
    input_files: tuple[Path, ...]
    digest: str


def load_collection(path: str | Path) -> CollectedData:
    """Select the latest report per entity; older snapshots never become ensemble runs.

    Accept companies/<id>/company.json + reports, a flat reports directory,
    a single company directory, or a single report file.
    """
    root = Path(path)
    if not root.exists():
        raise ValidationError(f"Collection input does not exist: {root}")
    files = sorted(root.rglob("*.json")) if root.is_dir() else [root]
    if not files:
        raise ValidationError(f"No JSON collection files in {root}")
    entities: dict[str, str] = {}
    companies: dict[str, dict] = {}
    histories: dict[str, list[tuple[datetime, Path, dict]]] = {}
    manifest_ids: dict[Path, str] = {}
    for file in files:
        if file.name != "company.json":
            continue
        company = _object(load_json(file), "company manifest")
        name = identifier(company.get("name"), "company.name")
        entity_id = identifier(file.parent.name, "company directory ID")
        if entity_id in entities:
            raise ValidationError(f"Duplicate company directory ID: {entity_id}")
        manifest_ids[file.parent] = entity_id
        entities[entity_id], companies[entity_id] = name, deepcopy(company)
    for file in files:
        if file.name == "company.json":
            continue
        try:
            report = validate_report(load_json(file))
            name = report["company"]["name"]
            entity_id = manifest_ids.get(file.parent)
            if entity_id is None:
                # A single report still uses its adjacent manifest's stable directory ID.
                manifest = file.parent / "company.json"
                if manifest.is_file():
                    company = _object(load_json(manifest), "company manifest")
                    if company.get("name") != name:
                        raise ValidationError("Report company does not match adjacent manifest")
                    entity_id = file.parent.name
                else:
                    entity_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                identifier(entity_id, "derived entity_id")
            if entity_id in entities and entities[entity_id] != name:
                raise ValidationError(f"Conflicting company names for {entity_id}")
            entities[entity_id] = name
            companies.setdefault(entity_id, report["company"])
            date = datetime.fromisoformat(report["generated_at"].upper().replace("Z", "+00:00"))
            histories.setdefault(entity_id, []).append((date, file, report))
        except ValidationError as exc:
            raise ValidationError(f"{file}: {exc}") from exc
    evidence = {}
    assessments = []
    for entity_id in sorted(entities):
        history = sorted(histories.get(entity_id, []), key=lambda item: item[0], reverse=True)
        report = history[0][2] if history else None
        if len(history) > 1 and history[0][0] == history[1][0]:
            raise ValidationError(f"Ambiguous latest reports with identical timestamps: {entity_id}")
        file = history[0][1] if history else None
        notes = ["Collector summary scores are heuristic triage signals, not repeated AI assessments."]
        if len(history) > 1:
            notes.append(f"Selected latest report; {len(history)-1} older snapshot(s) excluded from scoring.")
        if report is None:
            notes.append("No collection report is available for this entity.")
        if report and (report["errors"] or any(c["status"] in ("error", "skipped") for c in report["sources_consulted"])):
            notes.append("Collection has errors or skipped sources; inspect source checks before interpreting scores.")
        excluded = []
        for summary in report["summary"] if report else []:
            if not summary["signals"]:
                excluded.append(summary["category"])
                continue
            assessments.append(Assessment(
                entity_id=entity_id, entity_name=entities[entity_id], entity_type="vendor",
                category=summary["category"], risk_score=summary["score"],
                run_id=report["generated_at"], timestamp=report["generated_at"],
                agent_id="risk_collector:heuristic-summary",
                metadata={"score_basis": "collector_heuristic", "signal_count": summary["signals"]},
            ))
        if excluded:
            notes.append("Zero-signal category summaries are excluded rather than interpreted as low risk.")
        checks = Counter(c["status"] for c in report["sources_consulted"]) if report else Counter()
        evidence[entity_id] = {
            "company": deepcopy(report["company"] if report else companies[entity_id]),
            "report_file": str(file.relative_to(root) if root.is_dir() else file.name) if file else None,
            "generated_at": report["generated_at"] if report else None,
            "report_count": len(history), "status": "available" if report else "missing_report",
            "source_check_counts": dict(sorted(checks.items())),
            "excluded_zero_signal_categories": excluded, "notes": notes,
            "report": report,
        }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, allow_nan=False).encode()).hexdigest()
    input_files = set(files)
    input_files.update(file.parent / "company.json" for file in files if (file.parent / "company.json").is_file())
    return CollectedData(entities, evidence, tuple(assessments), tuple(sorted(input_files)), digest)
