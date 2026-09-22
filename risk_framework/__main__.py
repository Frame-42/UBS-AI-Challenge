"""Offline command line interface. JSON stdout is the default integration surface."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import RiskFramework, ValidationError, load_assessments, load_config, load_json, to_json
from .models import Scoreboard


def _display(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def table(result: Scoreboard) -> str:
    lines = ["AI assessment disagreement ranges (p10–p90); higher scores mean higher risk."]
    for row in result.records:
        overall = row.overall
        lines.append(f"{row.rank or '-':>3}  {row.entity_name}: {_display(overall.score)} "
                     f"[{_display(overall.p10)}, {_display(overall.p90)}] "
                     f"{overall.risk_level or 'UNSCORED'} | stability {overall.stability or 'n/a'} | "
                     f"coverage {overall.coverage:.1%} | {overall.status}"
                     f"{' | INCOMPLETE' if overall.incomplete else ''}")
        for category, value in row.categories.items():
            lines.append(f"     {category}: {_display(value.score)} "
                         f"[{_display(value.p10)}, {_display(value.p90)}] "
                         f"stability {value.stability or 'n/a'} | n={value.n} | {value.status}"
                         f"{' | below preferred runs' if value.below_preferred_runs else ''}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    score = sub.add_parser("score", help="Validate assessments and produce a ranked scoreboard")
    score.add_argument("--input", required=True, help="Assessment JSON array or JSONL")
    score.add_argument("--weights", required=True, help="JSON category-to-weight object")
    score.add_argument("--config", help="Partial JSON policy override")
    score.add_argument("--entities", help="Optional JSON entity-ID-to-name roster, including entities without data")
    score.add_argument("--format", choices=("json", "table"), default="json")
    score.add_argument("--output", help="Write to this file instead of stdout")
    args = parser.parse_args(argv)
    try:
        framework = RiskFramework(load_assessments(args.input), load_config(args.config),
                                  entities=load_json(args.entities) if args.entities else None)
        result = framework.score_all(load_json(args.weights))
        output = to_json(result) if args.format == "json" else table(result)
        if args.output:
            input_paths = [args.input, args.weights, args.config, args.entities]
            if any(Path(args.output).resolve() == Path(p).resolve() for p in input_paths if p):
                raise ValidationError("Output must not overwrite an input file")
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (ValidationError, OSError, UnicodeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
