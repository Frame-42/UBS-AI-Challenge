"""Command-line entry point.

    python -m risk_collector "Boeing" --alias "The Boeing Company" --ticker BA --domain boeing.com
    python -m risk_collector --company-file companies/microsoft/company.json --categories sanctions financial
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import pipeline, report
from .collectors import REGISTRY
from .http import HttpClient
from .models import Company, RiskCategory


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="risk_collector", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", nargs="?", help="company name")
    p.add_argument("--company-file", help="JSON file with Company fields (name, aliases, ticker, ...)")
    p.add_argument("--alias", action="append", default=[], help="alternative name (repeatable)")
    p.add_argument("--ticker")
    p.add_argument("--domain", help="primary web domain, e.g. ubs.com")
    p.add_argument("--country")
    p.add_argument("--cik", help="SEC CIK (looked up automatically if omitted)")
    p.add_argument("--related", action="append", default=[],
                   help="related party to screen against sanctions lists (repeatable)")
    p.add_argument("--categories", nargs="+", choices=[c.value for c in RiskCategory])
    p.add_argument("--collectors", nargs="+", choices=list(REGISTRY))
    p.add_argument("--lookback-days", type=int,
                   help="override every collector's lookback window (GDELT is capped at 90)")
    p.add_argument("--out", default="reports", help="output directory (default: reports/)")
    p.add_argument("--cache-dir", default=".cache/risk_collector")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--list-collectors", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.list_collectors:
        for name, cls in REGISTRY.items():
            print(f"{name:10s} [{', '.join(c.value for c in cls.categories)}] {cls.description}")
        return 0

    fields = json.loads(open(a.company_file).read()) if a.company_file else {}
    if a.name:
        fields["name"] = a.name
    if not fields.get("name"):
        print("error: a company name or --company-file is required", file=sys.stderr)
        return 2
    fields["aliases"] = fields.get("aliases", []) + a.alias
    fields["related_parties"] = fields.get("related_parties", []) + a.related
    for k in ("ticker", "domain", "country", "cik"):
        if getattr(a, k):
            fields[k] = getattr(a, k)
    company = Company(**fields)

    cats = [RiskCategory(c) for c in a.categories] if a.categories else None
    http = HttpClient(cache_dir=a.cache_dir, use_cache=not a.no_cache)
    collectors = pipeline.build_collectors(http, a.collectors, cats, a.lookback_days)
    rep = pipeline.run(company, collectors, cats)
    jp, mp = report.write(rep, a.out)

    print(f"\n{company.name}: {len(rep.signals)} signals from {len(rep.checks)} source checks")
    for s in rep.summary:
        print(f"  {s.category:13s} signals={s.signals:<4d} max={s.max_severity:<9s} score={s.score}")
    if rep.errors:
        print(f"  {len(rep.errors)} collection error(s) - see report")
    print(f"\nJSON:     {jp}\nMarkdown: {mp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
