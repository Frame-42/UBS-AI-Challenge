"""Strict JSON/JSONL ingestion and standards-compliant result serialization."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from .models import Assessment, Scoreboard
from .validation import ValidationError, parse_json


def load_json(path: str | Path) -> Any:
    return parse_json(Path(path).read_text(encoding="utf-8"))


def load_assessments(path: str | Path) -> tuple[Assessment, ...]:
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    rows.append(Assessment.from_dict(parse_json(line)))
                except ValidationError as exc:
                    raise ValidationError(f"{path}: line {line_no}: {exc}") from exc
        return tuple(rows)
    data = load_json(path)
    if not isinstance(data, list):
        raise ValidationError("Assessment JSON must be an array of assessment objects")
    rows = []
    for index, row in enumerate(data, 1):
        try:
            rows.append(Assessment.from_dict(row))
        except ValidationError as exc:
            raise ValidationError(f"{path}: record {index}: {exc}") from exc
    return tuple(rows)


def to_json(scoreboard: Scoreboard) -> str:
    return json.dumps(scoreboard.to_dict(), ensure_ascii=False, allow_nan=False, indent=2) + "\n"
