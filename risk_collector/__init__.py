"""Company risk data collection framework.

Collects sourced signals across cybersecurity, fraud, reputational, financial
and sanctions risk from public data (GDELT, official sanctions lists, SEC
EDGAR, CISA KEV, Have I Been Pwned). Every signal cites its sources.
"""
from .models import Company, CollectorResult, RiskCategory, RiskSignal, Severity, Source, SourceCheck

__version__ = "0.1.0"
__all__ = ["Company", "CollectorResult", "RiskCategory", "RiskSignal", "Severity", "Source", "SourceCheck"]
