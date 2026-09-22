"""Render a RiskReport as JSON and as a Markdown brief with numbered citations.

Every finding in the Markdown output carries citation markers ([1], [2] ...)
that resolve to the "References" section, and every data source consulted -
including those that returned nothing - is listed under "Source coverage".
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .collectors import REGISTRY
from .models import Source
from .pipeline import RiskReport

SEV_BADGE = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "info": "INFO",
             "none": "-"}


class Bibliography:
    def __init__(self) -> None:
        self._num: Dict[str, int] = {}
        self.entries: List[Source] = []

    def cite(self, src: Source) -> int:
        if src.key not in self._num:
            self.entries.append(src)
            self._num[src.key] = len(self.entries)
        return self._num[src.key]

    def cites(self, sources: List[Source]) -> str:
        return "".join(f"[{self.cite(s)}]" for s in sources)


def _md(text: str) -> str:
    return re.sub(r"([|\[\]])", r"\\\1", (text or "").replace("\n", " ")).strip()


def to_markdown(report: RiskReport, max_per_category: int = 40) -> str:
    bib = Bibliography()
    c = report.company
    out: List[str] = [f"# Risk data brief: {c.name}", ""]
    ident = [f"**Generated:** {report.generated_at}"]
    for label, v in (("Aliases", ", ".join(c.aliases)), ("Ticker", c.ticker), ("Domain", c.domain),
                     ("Country", c.country), ("Related parties", ", ".join(c.related_parties))):
        if v:
            ident.append(f"**{label}:** {v}")
    out += [" · ".join(ident), "",
            "> Automated collection from public sources. Findings are *signals* for analyst review, "
            "not conclusions; fuzzy and keyword matches can be false positives. Every item cites its "
            "source - see References.", ""]

    out += ["## Summary", "", "| Category | Signals | Highest severity | Score (0-100) |", "|---|---:|---|---:|"]
    for s in report.summary:
        out.append(f"| {s.category} | {s.signals} | {SEV_BADGE[s.max_severity]} | {s.score} |")
    out.append("")

    for s in report.summary:
        sig = [x for x in report.signals if x.category.value == s.category]
        out += [f"## {s.category.capitalize()}", ""]
        if not sig:
            checked = [ch for ch in report.checks if ch.status != "error" and ch.collector in REGISTRY
                       and s.category in {cat.value for cat in REGISTRY[ch.collector].categories}
                       and (ch.collector != "gdelt" or s.category in ch.source.name)]
            out += ["No signals found in the sources consulted"
                    + (f" {bib.cites([ch.source for ch in checked])}" if checked else "")
                    + " (see Source coverage).", ""]
            continue
        for x in sig[:max_per_category]:
            when = f" · {x.observed_at[:10]}" if x.observed_at else ""
            out.append(f"- **[{SEV_BADGE[x.severity.value]}] {_md(x.title)}**{when} · confidence "
                       f"{x.confidence:.0%} {bib.cites(x.sources)}")
            out.append(f"  {_md(x.summary)}")
        if len(sig) > max_per_category:
            out.append(f"- ... {len(sig) - max_per_category} more in the JSON output")
        out.append("")

    out += ["## Source coverage", "",
            "Every source consulted, including those with no findings (negative results are evidence too).", "",
            "| Source | Collector | Status | Detail | Retrieved | Ref |", "|---|---|---|---|---|---|"]
    for ch in report.checks:
        out.append(f"| {_md(ch.source.name)} | {ch.collector} | {ch.status} | {_md(ch.detail)}"
                   + (f" ({ch.records_scanned:,} records)" if ch.records_scanned else "")
                   + f" | {ch.source.retrieved_at} | [{bib.cite(ch.source)}] |")
    out.append("")
    if report.errors:
        out += ["## Collection errors", "", *[f"- {_md(e)}" for e in report.errors], ""]

    out += ["## References", ""]
    for i, s in enumerate(bib.entries, 1):
        parts = [f"{i}. {_md(s.name)}. *{_md(s.publisher)}*."]
        if s.published_at:
            parts.append(f"Published {s.published_at[:10]}.")
        if s.accessed_via:
            parts.append(f"Via {s.accessed_via}.")
        parts.append(f"<{s.url}> (retrieved {s.retrieved_at}).")
        if s.license:
            parts.append(f"Licence: {_md(s.license)}.")
        out.append(" ".join(parts))
    out.append("")
    return "\n".join(out)


def write(report: RiskReport, out_dir: str) -> Tuple[Path, Path]:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", report.company.name.lower()).strip("-")
    stamp = report.generated_at[:19].replace(":", "").replace("-", "")
    jp, mp = d / f"{slug}_{stamp}.json", d / f"{slug}_{stamp}.md"
    jp.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))
    mp.write_text(to_markdown(report))
    return jp, mp
