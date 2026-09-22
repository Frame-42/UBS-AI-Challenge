from typing import Dict, Type

from .base import Collector
from .cyber import CisaKevCollector, HibpCollector
from .gdelt import GdeltCollector
from .reputation import CourtListenerCollector, DojCollector, WikipediaCollector
from .sanctions import SanctionsCollector
from .sec_edgar import SecEdgarCollector

REGISTRY: Dict[str, Type[Collector]] = {
    c.name: c for c in (GdeltCollector, SanctionsCollector, SecEdgarCollector,
                        CisaKevCollector, HibpCollector, CourtListenerCollector, DojCollector,
                        WikipediaCollector)
}

__all__ = ["Collector", "REGISTRY", "GdeltCollector", "SanctionsCollector", "SecEdgarCollector",
           "CisaKevCollector", "HibpCollector", "CourtListenerCollector", "DojCollector",
           "WikipediaCollector"]
