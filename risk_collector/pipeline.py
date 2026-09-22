"""Runs collectors for a company and aggregates their output into a RiskReport."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .collectors import REGISTRY, Collector, GdeltCollector
from .http import HttpClient
from .models import Company, RiskCategory, RiskSignal, Severity, SourceCheck, utcnow

log = logging.getLogger(__name__)

SEVERITY_WEIGHT = {Severity.INFO: 0, Severity.LOW: 2, Severity.MEDIUM: 6,
                   Severity.HIGH: 15, Severity.CRITICAL: 40}


@dataclass
class CategorySummary:
    category: str
    signals: int
    max_severity: str
    score: int  # 0-100, confidence-weighted sum of severities (capped)
    by_severity: Dict[str, int]


@dataclass
class RiskReport:
    company: Company
    generated_at: str
    parameters: Dict[str, Any]
    signals: List[RiskSignal]
    checks: List[SourceCheck]
    errors: List[str]
    summary: List[CategorySummary] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": asdict(self.company),
            "generated_at": self.generated_at,
            "parameters": self.parameters,
            "summary": [asdict(s) for s in self.summary],
            "signals": [s.to_dict() for s in self.signals],
            "sources_consulted": [asdict(c) for c in self.checks],
            "errors": self.errors,
        }


def summarise(signals: List[RiskSignal], categories: List[RiskCategory]) -> List[CategorySummary]:
    out = []
    for cat in categories:
        sig = [s for s in signals if s.category == cat]
        by_sev = {sev.value: sum(1 for s in sig if s.severity == sev) for sev in Severity}
        score = min(100, round(sum(SEVERITY_WEIGHT[s.severity] * s.confidence for s in sig)))
        top = max((s.severity for s in sig), key=lambda s: s.rank, default=Severity.INFO)
        out.append(CategorySummary(cat.value, len(sig), top.value if sig else "none", score, by_sev))
    return out


def build_collectors(http: HttpClient, names: Optional[List[str]] = None,
                     categories: Optional[List[RiskCategory]] = None,
                     lookback_days: Optional[int] = None) -> List[Collector]:
    cats = set(categories or RiskCategory)
    selected = []
    for name in names or list(REGISTRY):
        cls = REGISTRY[name]
        if not cats & set(cls.categories):
            continue
        kwargs: Dict[str, Any] = {}
        if lookback_days is not None:
            kwargs["lookback_days"] = lookback_days
        if cls is GdeltCollector:
            kwargs["categories"] = [c for c in cls.categories if c in cats]
        selected.append(cls(http, **kwargs))
    return selected


def run(company: Company, collectors: List[Collector],
        categories: Optional[List[RiskCategory]] = None) -> RiskReport:
    cats = list(categories or RiskCategory)
    signals: List[RiskSignal] = []
    checks: List[SourceCheck] = []
    errors: List[str] = []
    for c in collectors:
        t0 = time.monotonic()
        log.info("running collector %s", c.name)
        try:
            res = c.collect(company)
        except Exception as e:  # noqa: BLE001 - defensive: collectors should not raise
            log.exception("collector %s crashed", c.name)
            errors.append(f"{c.name}: {e}")
            continue
        signals += [s for s in res.signals if s.category in cats]
        checks += res.checks
        errors += [f"{c.name}: {e}" for e in res.errors]
        log.info("collector %s: %d signals in %.1fs", c.name, len(res.signals), time.monotonic() - t0)

    # Newest first within (category, severity, confidence) - stable two-pass sort.
    signals.sort(key=lambda s: s.observed_at or "", reverse=True)
    signals.sort(key=lambda s: (cats.index(s.category), -s.severity.rank, -s.confidence))
    return RiskReport(
        company=company, generated_at=utcnow(),
        parameters={"collectors": [c.name for c in collectors], "categories": [c.value for c in cats],
                    "lookback_days": {c.name: c.lookback_days for c in collectors}},
        signals=signals, checks=checks, errors=errors, summary=summarise(signals, cats))
