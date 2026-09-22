from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import ClassVar, List

from ..http import HttpClient
from ..models import Company, CollectorResult, RiskCategory


class Collector(ABC):
    """Base class for all data collectors.

    Subclasses set ``name`` and ``categories`` and implement ``collect``.
    ``collect`` must never raise for data-source problems: record them in
    ``CollectorResult.errors`` (plus a ``SourceCheck`` with status "error") so
    one failing provider does not abort the whole run.
    """

    name: ClassVar[str]
    categories: ClassVar[List[RiskCategory]]
    description: ClassVar[str] = ""

    def __init__(self, http: HttpClient, lookback_days: int = 90) -> None:
        self.http = http
        self.lookback_days = lookback_days

    @property
    def since(self) -> dt.date:
        return dt.date.today() - dt.timedelta(days=self.lookback_days)

    @abstractmethod
    def collect(self, company: Company) -> CollectorResult:
        ...
