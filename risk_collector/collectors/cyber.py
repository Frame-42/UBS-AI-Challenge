"""Cybersecurity feeds that need no API key.

  * CISA Known Exploited Vulnerabilities (KEV) catalog - vulnerabilities in the
    company's own products that are being exploited in the wild.
  * Have I Been Pwned (HIBP) breach catalogue - publicly known data breaches of
    the company's services (matched by domain or name).
"""
from __future__ import annotations

import html
import re

from ..matching import normalize, similarity
from ..models import (Company, CollectorResult, RiskCategory, RiskSignal, Severity,
                      Source, SourceCheck)
from .base import Collector

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
HIBP_URL = "https://haveibeenpwned.com/api/v3/breaches"


class CisaKevCollector(Collector):
    name = "cisa_kev"
    categories = [RiskCategory.CYBERSECURITY]
    description = "CISA Known Exploited Vulnerabilities in the company's products"

    def __init__(self, http, lookback_days: int = 365, max_signals: int = 25) -> None:
        super().__init__(http, lookback_days)
        self.max_signals = max_signals

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        base = Source("CISA Known Exploited Vulnerabilities Catalog",
                      "U.S. Cybersecurity and Infrastructure Security Agency (CISA)", KEV_URL,
                      license="U.S. Government work - public domain")
        try:
            resp = self.http.get(KEV_URL, cache_ttl=12 * 3600)
            catalog = resp.json()
        except Exception as e:  # noqa: BLE001
            res.errors.append(f"CISA KEV: {e}")
            res.checks.append(SourceCheck(base, self.name, "error", str(e)))
            return res
        base.retrieved_at = resp.retrieved_at
        names = [normalize(n) for n in company.all_names]
        vulns = catalog.get("vulnerabilities", [])
        matched = [v for v in vulns
                   if any(similarity(normalize(v.get("vendorProject", "")), n) >= 0.92 for n in names)]
        since = self.since.isoformat()
        recent = sorted((v for v in matched if v.get("dateAdded", "") >= since),
                        key=lambda v: v["dateAdded"], reverse=True)
        for v in recent[: self.max_signals]:
            ransomware = v.get("knownRansomwareCampaignUse") == "Known"
            cve = v["cveID"]
            res.signals.append(RiskSignal(
                category=RiskCategory.CYBERSECURITY,
                title=f"{cve}: {v.get('vulnerabilityName', '')} actively exploited",
                summary=(f"{v.get('vendorProject')} {v.get('product')} vulnerability added to CISA KEV on "
                         f"{v.get('dateAdded')}. {v.get('shortDescription', '')}"
                         + (" Known use in ransomware campaigns." if ransomware else "")),
                severity=Severity.HIGH if ransomware else Severity.MEDIUM,
                sources=[Source(f"NVD entry {cve}", "NIST National Vulnerability Database",
                                f"https://nvd.nist.gov/vuln/detail/{cve}", retrieved_at=resp.retrieved_at,
                                published_at=v.get("dateAdded"), accessed_via="CISA KEV catalog",
                                license="U.S. Government work - public domain"), base],
                collector=self.name, confidence=0.9, observed_at=v.get("dateAdded"),
                tags=["vulnerability", "product-security"] + (["ransomware"] if ransomware else []),
                data={k: v.get(k) for k in ("cveID", "vendorProject", "product", "dateAdded",
                                            "dueDate", "knownRansomwareCampaignUse", "cwes")}))
        res.checks.append(SourceCheck(
            base, self.name, "ok" if recent else "no_match",
            f"{len(recent)} KEV entries since {since} ({len(matched)} all-time) for vendor "
            f"{company.name}", len(vulns)))
        return res


class HibpCollector(Collector):
    name = "hibp"
    categories = [RiskCategory.CYBERSECURITY]
    description = "Publicly known data breaches from Have I Been Pwned"

    def __init__(self, http, lookback_days: int = 365 * 5) -> None:
        super().__init__(http, lookback_days)

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        base = Source("Have I Been Pwned - breached websites catalogue", "Have I Been Pwned (Troy Hunt)",
                      HIBP_URL, license="CC BY 4.0 - attribution to haveibeenpwned.com required")
        try:
            resp = self.http.get(HIBP_URL, cache_ttl=24 * 3600)
            breaches = resp.json()
        except Exception as e:  # noqa: BLE001
            res.errors.append(f"HIBP: {e}")
            res.checks.append(SourceCheck(base, self.name, "error", str(e)))
            return res
        base.retrieved_at = resp.retrieved_at
        domain = re.sub(r"^www\.", "", (company.domain or "").lower())
        names = [normalize(n) for n in company.all_names]
        since = self.since.isoformat()
        hits = []
        for b in breaches:
            bdom = (b.get("Domain") or "").lower()
            by_domain = bool(domain) and (bdom == domain or bdom.endswith("." + domain))
            by_name = any(similarity(normalize(b.get("Title") or b.get("Name") or ""), n) >= 0.95 for n in names)
            if (by_domain or by_name) and (b.get("BreachDate") or "") >= since:
                hits.append((b, by_domain))
        for b, by_domain in hits:
            pwn = int(b.get("PwnCount") or 0)
            sensitive = {"Passwords", "Credit cards", "Bank account numbers", "Social security numbers",
                         "Government issued IDs"} & set(b.get("DataClasses", []))
            sev = Severity.HIGH if (pwn >= 1_000_000 or sensitive) else Severity.MEDIUM
            desc = html.unescape(re.sub(r"<[^>]+>", "", b.get("Description", "")))
            sources = [Source(f"HIBP breach record: {b.get('Title')}", "Have I Been Pwned (Troy Hunt)",
                              f"https://haveibeenpwned.com/PwnedWebsites#{b.get('Name')}",
                              retrieved_at=resp.retrieved_at, published_at=b.get("AddedDate"),
                              license=base.license), base]
            if b.get("DisclosureUrl"):
                sources.insert(1, Source(f"Breach disclosure for {b.get('Title')}", b.get("Title") or "breached organisation",
                                         b["DisclosureUrl"], retrieved_at=resp.retrieved_at))
            res.signals.append(RiskSignal(
                category=RiskCategory.CYBERSECURITY,
                title=f"Data breach: {b.get('Title')} ({b.get('BreachDate')}, {pwn:,} accounts)",
                summary=desc[:600] + (f" Exposed data: {', '.join(b.get('DataClasses', []))}." if b.get("DataClasses") else ""),
                severity=sev, sources=sources, collector=self.name,
                confidence=0.9 if by_domain else 0.6, observed_at=b.get("BreachDate"),
                tags=["data-breach"] + (["verified"] if b.get("IsVerified") else ["unverified"]),
                data={k: b.get(k) for k in ("Name", "Domain", "BreachDate", "PwnCount", "DataClasses", "IsVerified")}))
        res.checks.append(SourceCheck(base, self.name, "ok" if hits else "no_match",
                                      f"{len(hits)} breaches since {since} (domain={domain or 'n/a'})",
                                      len(breaches)))
        return res
