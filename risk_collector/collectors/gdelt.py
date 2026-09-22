"""GDELT DOC 2.0 API - global news coverage for cyber, fraud, reputational and financial risk.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
The DOC API searches a rolling ~3 month window of monitored online news, and
asks clients to send at most one request every 5 seconds.
"""
from __future__ import annotations

import datetime as dt
import re
import statistics
from typing import Dict, List, Optional

from ..matching import mentions_any, normalize
from ..models import (Company, CollectorResult, RiskCategory, RiskSignal, Severity,
                      Source, SourceCheck, utcnow)
from .base import Collector

API = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_NAME = "GDELT DOC 2.0 API"
GDELT_PUBLISHER = "The GDELT Project"
GDELT_LICENSE = "GDELT data is free and open; cite 'The GDELT Project' (https://www.gdeltproject.org/about.html#termsofuse)"
MAX_LOOKBACK_DAYS = 90

# Keywords per category. ``terms`` are OR-ed into the GDELT query; titles that
# contain a ``high`` term are escalated to high severity.
KEYWORDS: Dict[RiskCategory, Dict[str, List[str]]] = {
    RiskCategory.CYBERSECURITY: {
        "terms": ['"data breach"', "ransomware", "cyberattack", "hacked", "hackers",
                  '"security breach"', '"data leak"', "malware", '"cyber incident"'],
        "high": ["ransomware", "breach", "hacked", "cyberattack", "leak", "stolen data"],
    },
    RiskCategory.FRAUD: {
        "terms": ["fraud", "embezzlement", '"money laundering"', "bribery", "indicted",
                  '"insider trading"', "corruption", '"accounting scandal"', "kickbacks"],
        "high": ["charged", "indicted", "fraud", "laundering", "guilty", "arrested", "bribery"],
    },
    RiskCategory.REPUTATIONAL: {
        "terms": ["scandal", "boycott", "lawsuit", "backlash", "controversy", '"class action"',
                  "recall", "whistleblower", "misconduct", "outrage"],
        "high": ["scandal", "boycott", "class action", "whistleblower", "misconduct"],
    },
    RiskCategory.FINANCIAL: {
        "terms": ["bankruptcy", "insolvency", "downgrade", '"profit warning"', '"debt default"',
                  '"going concern"', "layoffs", "writedown", '"credit rating"', "restructuring"],
        "high": ["bankruptcy", "insolvency", "default", "going concern", "chapter 11", "junk"],
    },
}


def _name_clause(names: List[str]) -> str:
    quoted = [f'"{n}"' if " " in n else n for n in names]
    return quoted[0] if len(quoted) == 1 else "(" + " OR ".join(quoted) + ")"


def build_query(names: List[str], terms: List[str], language: Optional[str] = "english") -> str:
    q = f"{_name_clause(names)} ({' OR '.join(terms)})"
    if language:
        q += f" sourcelang:{language}"
    return q


def _gdelt_date(s: str) -> Optional[str]:
    try:
        return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


class GdeltCollector(Collector):
    name = "gdelt"
    categories = [RiskCategory.CYBERSECURITY, RiskCategory.FRAUD, RiskCategory.REPUTATIONAL,
                  RiskCategory.FINANCIAL]
    description = "News coverage via the GDELT DOC 2.0 API (articles + tone timeline)"

    def __init__(self, http, lookback_days: int = 90, max_records: int = 50,
                 language: Optional[str] = "english",
                 categories: Optional[List[RiskCategory]] = None,
                 require_name_in_title: bool = True) -> None:
        super().__init__(http, min(lookback_days, MAX_LOOKBACK_DAYS))
        self.max_records = max_records
        self.language = language
        self.enabled = categories or self.categories
        # GDELT matches keywords anywhere in the article body, so by default we
        # keep only articles whose headline names the company.
        self.require_name_in_title = require_name_in_title

    def _window(self) -> Dict[str, str]:
        end = dt.datetime.now(dt.timezone.utc)
        start = end - dt.timedelta(days=self.lookback_days)
        return {"startdatetime": start.strftime("%Y%m%d%H%M%S"), "enddatetime": end.strftime("%Y%m%d%H%M%S")}

    def _api_source(self, url: str, retrieved_at: str, what: str) -> Source:
        return Source(name=f"{GDELT_NAME} - {what}", publisher=GDELT_PUBLISHER, url=url,
                      retrieved_at=retrieved_at, license=GDELT_LICENSE)

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        names = company.all_names
        for cat in self.enabled:
            if cat in KEYWORDS:
                self._collect_articles(company, names, cat, res)
        if RiskCategory.REPUTATIONAL in self.enabled:
            self._collect_tone(company, names, res)
        return res

    # ---------------------------------------------------------------- articles
    def _collect_articles(self, company: Company, names: List[str], cat: RiskCategory,
                          res: CollectorResult) -> None:
        kw = KEYWORDS[cat]
        params = {"query": build_query(names, kw["terms"], self.language), "mode": "ArtList",
                  "format": "json", "maxrecords": self.max_records, "sort": "DateDesc", **self._window()}
        try:
            resp = self.http.get(API, params, cache_ttl=3600)
            payload = resp.json() if resp.body.strip() else {}
        except Exception as e:  # noqa: BLE001 - one failing query must not stop the run
            res.errors.append(f"GDELT {cat.value} query failed: {e}")
            res.checks.append(SourceCheck(self._api_source(API, utcnow(), f"{cat.value} news"),
                                          self.name, "error", str(e)))
            return

        api_src = self._api_source(resp.url, resp.retrieved_at, f"{cat.value} news search")
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        seen_urls, seen_titles = set(), set()
        n = 0
        for a in articles:
            url, title = a.get("url"), (a.get("title") or "").strip()
            tkey = normalize(title)
            if not url or url in seen_urls or tkey in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(tkey)
            in_title = mentions_any(title, names)
            if self.require_name_in_title and not in_title:
                continue
            hot = any(re.search(rf"\b{re.escape(h)}", title, re.I) for h in kw["high"])
            risky_title = hot or any(re.search(r"\b" + re.escape(t.strip('"')), title, re.I)
                                     for t in kw["terms"])
            severity = (Severity.HIGH if hot and in_title else Severity.MEDIUM if risky_title and in_title
                        else Severity.LOW)
            published = _gdelt_date(a.get("seendate", ""))
            article_src = Source(
                name=title or url, publisher=a.get("domain") or "unknown publisher", url=url,
                retrieved_at=resp.retrieved_at, published_at=published,
                accessed_via=GDELT_NAME)
            res.signals.append(RiskSignal(
                category=cat, title=title or url,
                summary=(f"{a.get('domain')} ({a.get('sourcecountry') or 'n/a'}) article matching "
                         f"{company.name} and {cat.value} risk keywords."
                         + ("" if in_title else " Company is not named in the headline - verify relevance.")),
                severity=severity, sources=[article_src, api_src], collector=self.name,
                confidence=0.75 if in_title else 0.35, observed_at=published,
                tags=["news", cat.value],
                data={"domain": a.get("domain"), "language": a.get("language"),
                      "source_country": a.get("sourcecountry")}))
            n += 1
        res.checks.append(SourceCheck(api_src, self.name, "ok" if n else "no_match",
                                      f"{n} unique articles for {cat.value}", len(articles)))

    # -------------------------------------------------------------------- tone
    def _collect_tone(self, company: Company, names: List[str], res: CollectorResult) -> None:
        q = _name_clause(names) + (f" sourcelang:{self.language}" if self.language else "")
        params = {"query": q, "mode": "TimelineTone", "format": "json", **self._window()}
        try:
            resp = self.http.get(API, params, cache_ttl=3600)
            payload = resp.json() if resp.body.strip() else {}
        except Exception as e:  # noqa: BLE001
            res.errors.append(f"GDELT tone query failed: {e}")
            res.checks.append(SourceCheck(self._api_source(API, utcnow(), "tone timeline"),
                                          self.name, "error", str(e)))
            return
        src = self._api_source(resp.url, resp.retrieved_at, "news tone timeline")
        values = [p["value"] for s in payload.get("timeline", []) for p in s.get("data", [])
                  if isinstance(p.get("value"), (int, float))]
        if not values:
            res.checks.append(SourceCheck(src, self.name, "no_match", "no coverage in window"))
            return
        avg, low = statistics.mean(values), min(values)
        # GDELT tone is roughly -10..+10; typical business news sits around -1..+1.
        severity = (Severity.HIGH if avg <= -4 else Severity.MEDIUM if avg <= -2.5
                    else Severity.LOW if avg <= -1.5 else Severity.INFO)
        res.signals.append(RiskSignal(
            category=RiskCategory.REPUTATIONAL,
            title=f"Average news tone {avg:+.2f} over last {self.lookback_days} days",
            summary=(f"GDELT tone of global coverage mentioning {company.name}: mean {avg:+.2f}, "
                     f"most negative interval {low:+.2f} across {len(values)} intervals "
                     "(scale approx. -10 very negative to +10 very positive)."),
            severity=severity, sources=[src], collector=self.name, confidence=0.6,
            tags=["news", "sentiment"],
            data={"mean_tone": round(avg, 3), "min_tone": round(low, 3), "intervals": len(values)}))
        res.checks.append(SourceCheck(src, self.name, "ok", f"{len(values)} tone intervals"))
