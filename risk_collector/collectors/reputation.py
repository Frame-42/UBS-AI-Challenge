"""Reputational-risk sources that need no API key.

  * CourtListener (Free Law Project) - federal court dockets (PACER/RECAP) where
    the company is named in the case caption, grouped by nature of suit.
  * U.S. Department of Justice press releases - settlements, penalties, guilty
    pleas and lawsuits whose headline names the company.
  * Wikipedia - encyclopedic sections on controversies, criticism and litigation.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from ..matching import mentions_any
from ..models import (Company, CollectorResult, RiskCategory, RiskSignal, Severity,
                      Source, SourceCheck)
from .base import Collector

C, S = RiskCategory, Severity

# --------------------------------------------------------------- CourtListener
CL_SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"
CL_SITE = "https://www.courtlistener.com"
CL_PUBLISHER = "Free Law Project (CourtListener)"
CL_LICENSE = "Court records are public domain; CourtListener data free of known copyright restrictions"

# Federal civil nature-of-suit codes grouped into reputational themes:
# theme -> (NOS codes, label, severity for 1+ cases, count that escalates, escalated severity)
SUIT_THEMES: Dict[str, Tuple[set, str, Severity, int, Severity]] = {
    "securities": ({"850"}, "securities suits", S.MEDIUM, 3, S.HIGH),
    "antitrust": ({"410"}, "antitrust suits", S.MEDIUM, 5, S.HIGH),
    "product_liability": ({"245", "315", "345", "355", "365", "367", "368", "385"},
                          "product liability suits", S.MEDIUM, 10, S.HIGH),
    "consumer": ({"370", "371", "375", "376", "480", "485", "490", "890"},
                 "consumer protection, fraud and privacy suits", S.LOW, 10, S.MEDIUM),
    "employment": ({"440", "442", "445", "446", "448", "710", "720", "740", "751", "790", "791"},
                   "employment, discrimination and labour suits", S.LOW, 10, S.MEDIUM),
}
IP_CODES = {"820", "830", "835", "840"}


# Fallback when a docket's nature of suit has no numeric code ("Consumer Credit").
THEME_WORDS: List[Tuple[str, str]] = [
    ("securities", r"securit|commodit"), ("antitrust", r"antitrust"),
    ("product_liability", r"product liab"),
    ("consumer", r"consumer|truth in lending|telephone consumer|false claims|other fraud|privacy"),
    ("employment", r"employ|civil rights|disab|labor|labour|fair labor|family and medical|erisa"),
]


def suit_code(nature: str) -> str:
    # State-court removals are sometimes coded with a prefix digit, e.g. "3480".
    m = re.match(r"\s*\d?(\d{3})\b", nature or "")
    return m.group(1) if m else ""


def suit_theme(nature: str) -> Optional[str]:
    code = suit_code(nature)
    if code:
        return next((t for t, (codes, *_rest) in SUIT_THEMES.items() if code in codes), None)
    return next((t for t, pat in THEME_WORDS if re.search(pat, nature or "", re.I)), None)


def is_defendant(case_name: str, names: List[str]) -> bool:
    """True when the company is named on the defendant side of 'A v. B'."""
    parts = re.split(r"\s+v\.?\s+|\s+vs\.?\s+", case_name or "", maxsplit=1, flags=re.I)
    return len(parts) == 2 and mentions_any(parts[1], names)


def _caption_query(names: List[str]) -> str:
    return "caseName:(" + " OR ".join(f'"{n}"' for n in names) + ")"


class CourtListenerCollector(Collector):
    name = "courtlistener"
    categories = [C.REPUTATIONAL]
    description = "U.S. federal court dockets naming the company (CourtListener / RECAP)"

    def __init__(self, http, lookback_days: int = 365, max_pages: int = 10, examples: int = 5) -> None:
        super().__init__(http, lookback_days)
        self.max_pages = max_pages
        self.examples = examples

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        names = company.all_names
        since = self.since.isoformat()
        params = {"type": "r", "q": _caption_query(names), "filed_after": since,
                  "order_by": "dateFiled desc"}
        dockets, total, url, first = [], 0, CL_SEARCH, None
        try:
            for page in range(self.max_pages):
                resp = self.http.get(url, params if page == 0 else None, cache_ttl=12 * 3600)
                data = resp.json()
                if page == 0:
                    first, total = resp, int(data.get("count") or 0)
                dockets += data.get("results", [])
                url = data.get("next")
                if not url:
                    break
        except Exception as e:  # noqa: BLE001
            res.errors.append(f"CourtListener: {e}")
            res.checks.append(SourceCheck(Source("CourtListener RECAP search", CL_PUBLISHER, CL_SEARCH),
                                          self.name, "error", str(e)))
            if first is None:
                return res
        api_src = Source(f"CourtListener RECAP docket search: {company.name}", CL_PUBLISHER,
                         CL_SITE + "/?" + first.url.split("?", 1)[1], retrieved_at=first.retrieved_at,
                         accessed_via="CourtListener REST API v4", license=CL_LICENSE)

        seen, against = set(), []
        for d in dockets:
            if d.get("docket_id") in seen or not mentions_any(d.get("caseName", ""), names):
                continue
            seen.add(d.get("docket_id"))
            if is_defendant(d.get("caseName", ""), names):
                against.append(d)
        natures = Counter((d.get("suitNature") or "unclassified") for d in against)
        n_ip = sum(1 for d in against if suit_code(d.get("suitNature", "")) in IP_CODES
                   or re.search(r"patent|trademark|copyright", d.get("suitNature") or "", re.I))
        note = "" if len(dockets) >= total else f" (first {len(dockets)} of {total} dockets reviewed)"

        if against:
            top = "; ".join(f"{k}: {v}" for k, v in natures.most_common(6))
            res.signals.append(RiskSignal(
                category=C.REPUTATIONAL,
                title=f"{len(against)} federal cases filed against {company.name} since {since}",
                summary=(f"CourtListener lists {total} federal dockets since {since} whose caption names "
                         f"{company.name}; {len(against)} name it as defendant{note}. By nature of suit: "
                         f"{top}. {n_ip} are patent, trademark or copyright disputes."),
                severity=S.INFO, sources=[api_src], collector=self.name, confidence=0.8,
                tags=["litigation", "court-records"],
                data={"dockets_total": total, "reviewed": len(dockets), "as_defendant": len(against),
                      "by_nature_of_suit": dict(natures)}))

        for theme, (_codes, label, sev, escalate_at, sev_hi) in SUIT_THEMES.items():
            cases = [d for d in against if suit_theme(d.get("suitNature", "")) == theme]
            if not cases:
                continue
            srcs = [Source(f"{d.get('caseName')} ({d.get('court_citation_string') or d.get('court')}, "
                           f"{d.get('docketNumber')})", CL_PUBLISHER,
                           CL_SITE + d.get("docket_absolute_url", ""), retrieved_at=api_src.retrieved_at,
                           published_at=d.get("dateFiled"), accessed_via="CourtListener REST API v4",
                           license=CL_LICENSE) for d in cases[: self.examples]]
            res.signals.append(RiskSignal(
                category=C.REPUTATIONAL,
                title=f"{len(cases)} {label} filed against {company.name} since {since}",
                summary=("Most recent: " + "; ".join(f"{d.get('caseName')} ({d.get('dateFiled')}, "
                                                     f"{d.get('suitNature')})" for d in cases[:3])
                         + ". Filings are allegations, not findings of liability."),
                severity=sev_hi if len(cases) >= escalate_at else sev, sources=srcs + [api_src],
                collector=self.name, confidence=0.75, observed_at=cases[0].get("dateFiled"),
                tags=["litigation", theme], data={"cases": len(cases), "theme": theme}))

        res.checks.append(SourceCheck(api_src, self.name, "ok" if against else "no_match",
                                      f"{total} dockets since {since}, {len(against)} as defendant{note}",
                                      len(dockets)))
        return res


# --------------------------------------------------------------------- DOJ
DOJ_API = "https://www.justice.gov/api/v1/press_releases.json"
DOJ_PUBLISHER = "U.S. Department of Justice, Office of Public Affairs"
GOV_LICENSE = "U.S. Government work - public domain"

# Headline patterns where the company itself is the subject of an enforcement outcome.
DOJ_RESOLUTION = re.compile(
    r"\b(agrees? to pay|to pay \$|pays? \$|pleads? guilty|plea agreement|settle[sd]?|settlement|"
    r"resolve[sd]?|civil penalty|criminal penalty|fined?|consent decree|deferred prosecution|"
    r"non-prosecution)\b", re.I)
DOJ_ACTION = re.compile(r"\b(sues|lawsuit against|files suit|complaint against|charges|antitrust|"
                        r"investigation)\b", re.I)


def classify_doj(title: str, names: List[str]) -> Optional[Tuple[Severity, str]]:
    """Severity and reason for a DOJ headline, or None when it does not name the company.

    The API's title filter also matches inside other words ("Cisco" in "San Francisco").
    """
    if not mentions_any(title, names):
        return None
    alt = "|".join(re.escape(n) for n in names)
    if re.search(rf"\b(defraud\w*|scam\w*|impersonat\w*|steal\w*|stole|theft|hack\w*|counterfeit|"
                 rf"illicit|from)\b(\W+\w+){{0,3}}\W+({alt})", title, re.I):
        return S.INFO, "company appears to be the victim, not the subject"
    if DOJ_RESOLUTION.search(title):
        return S.HIGH, "enforcement resolution naming the company (settlement, penalty or plea)"
    if DOJ_ACTION.search(title):
        return S.MEDIUM, "DOJ action or investigation naming the company"
    return S.INFO, "company named, but likely as victim or context (e.g. an individual's case)"


class DojCollector(Collector):
    name = "doj"
    categories = [C.REPUTATIONAL]
    description = "U.S. Department of Justice press releases naming the company"

    def __init__(self, http, lookback_days: int = 365 * 3, max_per_name: int = 50) -> None:
        super().__init__(http, lookback_days)
        self.max_per_name = max_per_name

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        names = company.all_names
        since = self.since.isoformat()
        found: Dict[str, dict] = {}
        resp = None
        for n in names:
            params = {"title": n, "sort": "date", "direction": "DESC", "pagesize": self.max_per_name}
            try:
                resp = self.http.get(DOJ_API, params, cache_ttl=24 * 3600)
                rows = resp.json().get("results", [])
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"DOJ press releases ({n}): {e}")
                res.checks.append(SourceCheck(Source("DOJ press releases API", DOJ_PUBLISHER, DOJ_API),
                                              self.name, "error", str(e)))
                continue
            for r in rows:
                day = dt.datetime.fromtimestamp(int(r.get("date") or 0), dt.timezone.utc).date().isoformat()
                if day >= since:
                    found.setdefault(r.get("uuid") or r.get("url"), {**r, "day": day})
        if resp is None:
            return res
        api_src = Source(f"DOJ press releases API, headline search for {company.name}", DOJ_PUBLISHER,
                         resp.url, retrieved_at=resp.retrieved_at, license=GOV_LICENSE)
        hits = named = 0
        for r in sorted(found.values(), key=lambda r: r["day"], reverse=True):
            title = re.sub(r"\s+", " ", r.get("title") or "").strip()
            verdict = classify_doj(title, names)
            if verdict is None:
                continue
            sev, why = verdict
            named += 1
            teaser = re.sub(r"<[^>]+>", "", r.get("teaser") or "").strip()
            res.signals.append(RiskSignal(
                category=C.REPUTATIONAL, title=title, summary=f"{why.capitalize()}. {teaser[:400]}".strip(),
                severity=sev,
                sources=[Source(title, DOJ_PUBLISHER, r.get("url"), retrieved_at=resp.retrieved_at,
                                published_at=r["day"], accessed_via="DOJ press releases API",
                                license=GOV_LICENSE), api_src],
                collector=self.name, confidence=0.85 if sev != S.INFO else 0.4, observed_at=r["day"],
                tags=["enforcement", "government"], data={"number": r.get("number")}))
            hits += sev != S.INFO
        res.checks.append(SourceCheck(api_src, self.name, "ok" if named else "no_match",
                                      f"{len(found)} releases since {since}, {named} name the company in the "
                                      f"headline, {hits} enforcement-related",
                                      len(found)))
        return res


# ---------------------------------------------------------------- Wikipedia
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PUBLISHER = "Wikipedia (Wikimedia Foundation)"
WIKI_LICENSE = "CC BY-SA 4.0"
CONTROVERSY = re.compile(
    r"controvers|critic|lawsuit|litigation|legal (issue|action|dispute)|scandal|fine[sd]?\b|antitrust|"
    r"competition|discriminat|privacy|data breach|security (breach|incident)|hack|dispute|allegation|"
    r"investigation|censorship|backdoor|tax|labou?r|working conditions|union|environment|human rights|"
    r"ethic|boycott|settlement|surveillance|outage|fraud|bribery|corruption|sanction|misconduct|recall",
    re.I)
SKIP_SECTIONS = re.compile(r"^(see also|references|notes|further reading|external links|sources|"
                           r"bibliography)$", re.I)


def split_sections(text: str) -> List[Tuple[List[str], str]]:
    """Split a plain-text extract ('== H ==' headings) into (heading path, body) pairs."""
    out, path, body = [], [], []
    for line in text.splitlines():
        m = re.match(r"^(={2,6})\s*(.+?)\s*\1\s*$", line)
        if m:
            if path:
                out.append((list(path), "\n".join(body).strip()))
            level = len(m.group(1)) - 1
            path = path[: level - 1] + [m.group(2)]
            body = []
        else:
            body.append(line)
    if path:
        out.append((list(path), "\n".join(body).strip()))
    return out


def latest_year(text: str, today: Optional[dt.date] = None) -> Optional[int]:
    now = (today or dt.date.today()).year
    years = [int(y) for y in re.findall(r"\b(19[5-9]\d|20\d\d)\b", text) if int(y) <= now]
    return max(years) if years else None


class WikipediaCollector(Collector):
    name = "wikipedia"
    categories = [C.REPUTATIONAL]
    description = "Controversy, criticism and litigation sections of the company's Wikipedia articles"

    def __init__(self, http, lookback_days: int = 365 * 2, max_signals: int = 20) -> None:
        # lookback_days: sections mentioning a year inside this window are rated medium.
        super().__init__(http, lookback_days)
        self.max_signals = max_signals

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        titles = company.wikipedia or [company.name]
        recent_year = self.since.year
        n = 0
        for title in titles:
            params = {"action": "query", "prop": "extracts|info|pageprops", "explaintext": 1,
                      "exsectionformat": "wiki", "titles": title, "redirects": 1, "format": "json",
                      "formatversion": 2}
            try:
                resp = self.http.get(WIKI_API, params, cache_ttl=7 * 86400)
                pages = resp.json().get("query", {}).get("pages", [])
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"Wikipedia ({title}): {e}")
                res.checks.append(SourceCheck(Source(f"Wikipedia: {title}", WIKI_PUBLISHER, WIKI_API),
                                              self.name, "error", str(e)))
                continue
            page = pages[0] if pages else {}
            page_url = f"https://en.wikipedia.org/wiki/{(page.get('title') or title).replace(' ', '_')}"
            if not page or page.get("missing") or "disambiguation" in page.get("pageprops", {}):
                res.checks.append(SourceCheck(
                    Source(f"Wikipedia article: {title}", WIKI_PUBLISHER, page_url, retrieved_at=resp.retrieved_at,
                           license=WIKI_LICENSE), self.name, "no_match", "no article (or a disambiguation page)"))
                continue
            rev = page.get("lastrevid")
            permalink = f"https://en.wikipedia.org/w/index.php?title={page['title'].replace(' ', '_')}&oldid={rev}"
            page_src = Source(f"Wikipedia: {page['title']} (revision {rev})", WIKI_PUBLISHER, permalink,
                              retrieved_at=resp.retrieved_at, accessed_via="MediaWiki API",
                              license=WIKI_LICENSE)
            whole_page = page["title"].lower().startswith(("criticism of", "controversies"))
            hits = []
            for path, body in split_sections(page.get("extract", "")):
                if SKIP_SECTIONS.match(path[-1]) or len(body) < 80:
                    continue
                if whole_page or any(CONTROVERSY.search(h) for h in path):
                    hits.append((path, body))
            for path, body in hits:
                if n >= self.max_signals:
                    break
                year = latest_year(body)
                recent = year is not None and year >= recent_year
                anchor = path[-1].replace(" ", "_")
                res.signals.append(RiskSignal(
                    category=C.REPUTATIONAL,
                    title=f"Wikipedia: {' > '.join(path)}" + (f" (latest year mentioned {year})" if year else ""),
                    summary=re.sub(r"\s+", " ", body)[:500] + ("..." if len(body) > 500 else ""),
                    severity=S.MEDIUM if recent else S.LOW,
                    sources=[Source(f"Wikipedia: {page['title']} - section '{path[-1]}'", WIKI_PUBLISHER,
                                    f"{page_url}#{anchor}", retrieved_at=resp.retrieved_at,
                                    accessed_via="MediaWiki API", license=WIKI_LICENSE), page_src],
                    collector=self.name, confidence=0.8, observed_at=str(year) if year else None,
                    tags=["encyclopedia", "controversy"],
                    data={"section": path, "latest_year": year, "chars": len(body)}))
                n += 1
            res.checks.append(SourceCheck(page_src, self.name, "ok" if hits else "no_match",
                                          f"{len(hits)} controversy/litigation sections in '{page['title']}'"))
        return res
