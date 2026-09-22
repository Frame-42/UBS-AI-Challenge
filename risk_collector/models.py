"""Core data model.

Every piece of evidence the framework produces is a ``RiskSignal`` and every
``RiskSignal`` must cite at least one ``Source``. This is enforced at
construction time so a signal without provenance cannot exist.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class RiskCategory(str, Enum):
    CYBERSECURITY = "cybersecurity"
    FRAUD = "fraud"
    REPUTATIONAL = "reputational"
    FINANCIAL = "financial"
    SANCTIONS = "sanctions"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return ["info", "low", "medium", "high", "critical"].index(self.value)


@dataclass
class Source:
    """Where a piece of information came from.

    ``name``       human readable name of the dataset / article
    ``publisher``  organisation that published it (e.g. "U.S. Treasury OFAC")
    ``url``        the most specific URL available (article, filing, list entry)
    ``retrieved_at`` ISO-8601 UTC timestamp of when the data was fetched
    ``accessed_via`` intermediary used to find it (e.g. "GDELT DOC 2.0 API")
    ``published_at`` publication date of the underlying item, if known
    ``license``    licence / terms of use of the data
    """

    name: str
    publisher: str
    url: str
    retrieved_at: str = field(default_factory=utcnow)
    accessed_via: Optional[str] = None
    published_at: Optional[str] = None
    license: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not self.publisher or not self.url:
            raise ValueError(f"Source requires name, publisher and url: {self!r}")

    @property
    def key(self) -> str:
        return self.url


@dataclass
class RiskSignal:
    """A single, sourced observation relevant to a company's risk profile."""

    category: RiskCategory
    title: str
    summary: str
    severity: Severity
    sources: List[Source]
    collector: str
    confidence: float = 0.5  # 0..1 - how sure we are this is about the right entity
    observed_at: Optional[str] = None  # date of the underlying event / publication
    tags: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError(f"RiskSignal '{self.title}' has no sources - every signal must be sourced")
        self.category = RiskCategory(self.category)
        self.severity = Severity(self.severity)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


@dataclass
class SourceCheck:
    """Records that a data source was consulted, even when it yielded nothing.

    Negative results matter (e.g. "not on the OFAC SDN list as of <date>"),
    so they are cited just like positive findings.
    """

    source: Source
    collector: str
    status: str  # "ok" | "no_match" | "error" | "skipped"
    detail: str = ""
    records_scanned: Optional[int] = None


@dataclass
class Company:
    name: str
    aliases: List[str] = field(default_factory=list)
    ticker: Optional[str] = None
    domain: Optional[str] = None
    country: Optional[str] = None
    cik: Optional[str] = None  # SEC Central Index Key, resolved automatically if omitted
    related_parties: List[str] = field(default_factory=list)  # executives, subsidiaries, owners
    wikipedia: List[str] = field(default_factory=list)  # English Wikipedia article titles; default: name

    @property
    def all_names(self) -> List[str]:
        seen, out = set(), []
        for n in [self.name, *self.aliases]:
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        return out


@dataclass
class CollectorResult:
    collector: str
    signals: List[RiskSignal] = field(default_factory=list)
    checks: List[SourceCheck] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
