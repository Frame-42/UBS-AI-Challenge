"""SEC EDGAR - regulatory filings and XBRL financials for SEC registrants.

Three sub-collectors:
  * Filing events: risk-relevant 8-K items (e.g. 1.05 material cybersecurity
    incident, 4.02 non-reliance on financials) and late-filing notices.
  * Full-text search of filings for red-flag phrases (Wells notice, going concern ...).
  * XBRL "company facts": annual financial ratios and trends.

SEC fair-access policy: max 10 requests/second and a User-Agent that
identifies you, e.g. ``RISK_COLLECTOR_USER_AGENT="Acme Corp risk-team admin@acme.com"``.
https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple

from ..matching import normalize, similarity
from ..models import (Company, CollectorResult, RiskCategory, RiskSignal, Severity,
                      Source, SourceCheck, utcnow)
from .base import Collector

PUBLISHER = "U.S. Securities and Exchange Commission (EDGAR)"
LICENSE = "U.S. Government work - public domain"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
FTS = "https://efts.sec.gov/LATEST/search-index"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}"

C, S = RiskCategory, Severity
ITEM_RISKS: Dict[str, Tuple[RiskCategory, Severity, str]] = {
    "1.05": (C.CYBERSECURITY, S.CRITICAL, "Material cybersecurity incident (8-K Item 1.05)"),
    "1.03": (C.FINANCIAL, S.CRITICAL, "Bankruptcy or receivership (8-K Item 1.03)"),
    "2.04": (C.FINANCIAL, S.HIGH, "Triggering event accelerating a financial obligation (8-K Item 2.04)"),
    "2.06": (C.FINANCIAL, S.MEDIUM, "Material impairment (8-K Item 2.06)"),
    "2.05": (C.FINANCIAL, S.LOW, "Exit or disposal costs / restructuring (8-K Item 2.05)"),
    "3.01": (C.FINANCIAL, S.HIGH, "Delisting notice or failure to meet listing standards (8-K Item 3.01)"),
    "4.01": (C.FRAUD, S.MEDIUM, "Change in certifying accountant (8-K Item 4.01)"),
    "4.02": (C.FRAUD, S.HIGH, "Non-reliance on previously issued financial statements (8-K Item 4.02)"),
    "5.02": (C.REPUTATIONAL, S.INFO, "Director / officer departure or appointment (8-K Item 5.02)"),
}
FORM_RISKS: Dict[str, Tuple[RiskCategory, Severity, str]] = {
    "NT 10-K": (C.FINANCIAL, S.MEDIUM, "Notification of late annual report (NT 10-K)"),
    "NT 10-Q": (C.FINANCIAL, S.MEDIUM, "Notification of late quarterly report (NT 10-Q)"),
    "NT 20-F": (C.FINANCIAL, S.MEDIUM, "Notification of late annual report (NT 20-F)"),
}
# (query, category, severity, label). Full-text hits can be boilerplate
# risk-factor language, so they are deliberately low/medium severity.
FTS_TERMS: List[Tuple[str, RiskCategory, Severity, str]] = [
    ('"Wells notice"', C.FRAUD, S.MEDIUM, "Filings mention a Wells notice"),
    ('"material weakness"', C.FRAUD, S.LOW, "Filings mention a material weakness in internal control"),
    ('"deferred prosecution agreement"', C.FRAUD, S.MEDIUM, "Filings mention a deferred prosecution agreement"),
    ('"substantial doubt" "going concern"', C.FINANCIAL, S.MEDIUM, "Filings mention going-concern doubt"),
    ('"ransomware"', C.CYBERSECURITY, S.LOW, "Filings mention ransomware"),
    ('"cybersecurity incident"', C.CYBERSECURITY, S.LOW, "Filings mention a cybersecurity incident"),
]
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
METRICS: Dict[str, Dict[str, List[str]]] = {
    "assets": {"us-gaap": ["Assets"], "ifrs-full": ["Assets"]},
    "liabilities": {"us-gaap": ["Liabilities"], "ifrs-full": ["Liabilities"]},
    "equity": {"us-gaap": ["StockholdersEquity",
                           "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
               "ifrs-full": ["Equity", "EquityAttributableToOwnersOfParent"]},
    "current_assets": {"us-gaap": ["AssetsCurrent"], "ifrs-full": ["CurrentAssets"]},
    "current_liabilities": {"us-gaap": ["LiabilitiesCurrent"], "ifrs-full": ["CurrentLiabilities"]},
    "net_income": {"us-gaap": ["NetIncomeLoss", "ProfitLoss"], "ifrs-full": ["ProfitLoss"]},
    "revenue": {"us-gaap": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "SalesRevenueNet"], "ifrs-full": ["Revenue"]},
    "operating_cash_flow": {"us-gaap": ["NetCashProvidedByUsedInOperatingActivities"],
                            "ifrs-full": ["CashFlowsFromUsedInOperatingActivities"]},
}
INSTANT = {"assets", "liabilities", "equity", "current_assets", "current_liabilities"}


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def annual_series(facts: dict, metric: str) -> Tuple[Dict[str, Tuple[float, str]], Optional[str]]:
    """Return ({period_end: (value, accession)}, unit) for annual filings, latest filing wins."""
    for taxonomy, concepts in METRICS[metric].items():
        for concept in concepts:
            units = facts.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {})
            for unit, rows in units.items():
                if unit.lower() in ("shares", "pure") or "/" in unit:
                    continue
                out: Dict[str, Tuple[float, str, str]] = {}
                for r in rows:
                    if r.get("form") not in ANNUAL_FORMS or r.get("fp") != "FY":
                        continue
                    if metric not in INSTANT and not (r.get("start") and 330 <= _days(r["start"], r["end"]) <= 400):
                        continue
                    prev = out.get(r["end"])
                    if prev is None or r.get("filed", "") > prev[2]:
                        out[r["end"]] = (float(r["val"]), r.get("accn", ""), r.get("filed", ""))
                if out:
                    return {k: (v[0], v[1]) for k, v in out.items()}, unit
    return {}, None


class SecEdgarCollector(Collector):
    name = "sec_edgar"
    categories = [C.FINANCIAL, C.FRAUD, C.CYBERSECURITY, C.REPUTATIONAL]
    description = "SEC EDGAR filings (8-K risk items, full-text red flags) and XBRL financials"

    def __init__(self, http, lookback_days: int = 365, full_text: bool = True, financials: bool = True) -> None:
        super().__init__(http, lookback_days)
        self.full_text = full_text
        self.financials = financials
        self._sic = 0

    # -------------------------------------------------------------- CIK lookup
    def resolve_cik(self, company: Company) -> Optional[Tuple[str, str]]:
        if company.cik:
            return company.cik.zfill(10), company.name
        queries = [q for q in [company.ticker, *company.all_names] if q]
        for q in queries:
            data = self.http.get(FTS, {"keysTyped": q}, cache_ttl=7 * 86400).json()
            for h in data.get("hits", {}).get("hits", []):
                src = h.get("_source", {})
                entity = src.get("entity", "")
                tickers = [t.strip().upper() for t in (src.get("tickers") or "").split(",") if t.strip()]
                bare = re.sub(r"\s*\(.*\)\s*$", "", entity)
                if company.ticker and company.ticker.upper() in tickers:
                    return h["_id"].zfill(10), bare
                if any(similarity(normalize(n), normalize(bare)) >= 0.93 for n in company.all_names):
                    return h["_id"].zfill(10), bare
        return None

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        try:
            found = self.resolve_cik(company)
        except Exception as e:  # noqa: BLE001
            res.errors.append(f"EDGAR company lookup failed: {e}")
            res.checks.append(SourceCheck(Source("EDGAR company search", PUBLISHER, FTS), self.name, "error", str(e)))
            return res
        if not found:
            res.checks.append(SourceCheck(
                Source("EDGAR company search", PUBLISHER, "https://www.sec.gov/edgar/search/", license=LICENSE),
                self.name, "no_match", f"{company.name} does not appear to be an SEC registrant"))
            return res
        cik, entity = found
        for step in (self._filings, self._full_text, self._financials):
            if step is self._full_text and not self.full_text or step is self._financials and not self.financials:
                continue
            try:
                step(cik, entity, res)
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"EDGAR {step.__name__.strip('_')} failed: {e}")
        return res

    # ----------------------------------------------------------------- filings
    def _filings(self, cik: str, entity: str, res: CollectorResult) -> None:
        resp = self.http.get(SUBMISSIONS.format(cik=cik), cache_ttl=6 * 3600)
        sub = resp.json()
        self._sic = int(sub.get("sic") or 0)
        api_src = Source(f"EDGAR submissions index for {entity} (CIK {cik})", PUBLISHER, resp.url,
                         retrieved_at=resp.retrieved_at, license=LICENSE)
        r = sub["filings"]["recent"]
        since = self.since.isoformat()
        hits = 0
        for i, form in enumerate(r["form"]):
            filed = r["filingDate"][i]
            if filed < since:
                break  # recent filings are sorted newest first
            risks = []
            if form in ("8-K", "8-K/A"):
                risks = [ITEM_RISKS[it] for it in (r["items"][i] or "").split(",") if it in ITEM_RISKS]
            elif form in FORM_RISKS:
                risks = [FORM_RISKS[form]]
            if not risks:
                continue
            accn = r["accessionNumber"][i]
            url = ARCHIVE.format(cik=int(cik), accn=accn.replace("-", ""), doc=r["primaryDocument"][i])
            doc = Source(f"{entity} {form} filed {filed} (accession {accn})", PUBLISHER, url,
                         retrieved_at=resp.retrieved_at, published_at=filed, license=LICENSE,
                         accessed_via="EDGAR submissions API")
            for cat, sev, label in risks:
                hits += 1
                res.signals.append(RiskSignal(
                    category=cat, title=f"{label} - filed {filed}",
                    summary=f"{entity} filed a {form} on {filed} disclosing: {label}.",
                    severity=sev, sources=[doc, api_src], collector=self.name, confidence=0.95,
                    observed_at=filed, tags=["sec-filing", form],
                    data={"form": form, "accession": accn, "items": r["items"][i]}))
        res.checks.append(SourceCheck(api_src, self.name, "ok" if hits else "no_match",
                                      f"{hits} risk-relevant filings since {since}"))

    # --------------------------------------------------------------- full text
    def _full_text(self, cik: str, entity: str, res: CollectorResult) -> None:
        start, end = self.since.isoformat(), dt.date.today().isoformat()
        for query, cat, sev, label in FTS_TERMS:
            params = {"q": query, "ciks": cik, "dateRange": "custom", "startdt": start, "enddt": end}
            resp = self.http.get(FTS, params, cache_ttl=6 * 3600)
            data = resp.json()
            total = data.get("hits", {}).get("total", {}).get("value", 0)
            # Cite the human-readable EDGAR search page for the same query.
            search_src = Source(f"EDGAR full-text search: {query} ({entity})", PUBLISHER,
                                "https://www.sec.gov/edgar/search/#/" + resp.url.split("?", 1)[1],
                                retrieved_at=resp.retrieved_at, license=LICENSE,
                                accessed_via=resp.url)
            if not total:
                res.checks.append(SourceCheck(search_src, self.name, "no_match", f"no filings match {query}"))
                continue
            docs: List[Source] = []
            forms = set()
            for h in data["hits"]["hits"][:5]:
                s = h["_source"]
                adsh, _, fname = h["_id"].partition(":")
                forms.add(s.get("form"))
                docs.append(Source(f"{entity} {s.get('form')} filed {s.get('file_date')} ({fname})", PUBLISHER,
                                   ARCHIVE.format(cik=int(cik), accn=adsh.replace("-", ""), doc=fname),
                                   retrieved_at=resp.retrieved_at, published_at=s.get("file_date"),
                                   license=LICENSE, accessed_via="EDGAR full-text search"))
            res.signals.append(RiskSignal(
                category=cat, title=f"{label} ({total} document(s) since {start})",
                summary=(f"EDGAR full-text search found {query} in {total} document(s) filed by {entity} "
                         f"since {start} (forms: {', '.join(sorted(f for f in forms if f))}). "
                         "May be boilerplate risk-factor language - read the cited filings."),
                severity=sev, sources=docs + [search_src], collector=self.name, confidence=0.5,
                observed_at=docs[0].published_at if docs else None, tags=["sec-filing", "full-text"],
                data={"query": query, "documents": total}))
            res.checks.append(SourceCheck(search_src, self.name, "ok", f"{total} documents"))

    # -------------------------------------------------------------- financials
    def _financials(self, cik: str, entity: str, res: CollectorResult) -> None:
        resp = self.http.get(FACTS.format(cik=cik), cache_ttl=24 * 3600)
        facts = resp.json()
        api_src = Source(f"SEC XBRL company facts for {entity} (CIK {cik})", PUBLISHER, resp.url,
                         retrieved_at=resp.retrieved_at, license=LICENSE)
        series = {m: annual_series(facts, m) for m in METRICS}
        assets, unit = series["assets"]
        if not assets:
            res.checks.append(SourceCheck(api_src, self.name, "no_match", "no annual XBRL financial data"))
            return
        latest = max(assets)
        prior = max((e for e in assets if _days(e, latest) >= 300), default=None)

        def val(metric: str, end: Optional[str]) -> Optional[float]:
            if end is None:
                return None
            data = series[metric][0]
            hit = data.get(end) or next((v for e, v in data.items() if abs(_days(e, end)) <= 10), None)
            return hit[0] if hit else None

        accn = assets[latest][1]
        filing_src = Source(f"{entity} annual report for fiscal year ending {latest} (accession {accn})",
                            PUBLISHER, f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/",
                            retrieved_at=resp.retrieved_at, license=LICENSE, accessed_via="SEC XBRL API")
        srcs = [filing_src, api_src]
        m = {k: val(k, latest) for k in METRICS}
        p = {k: val(k, prior) for k in ("net_income", "revenue")}
        if m["liabilities"] is None and m["assets"] is not None and m["equity"] is not None:
            m["liabilities"] = m["assets"] - m["equity"]
        is_financial_firm = 6000 <= getattr(self, "_sic", 0) < 7000

        def fmt(x: Optional[float]) -> str:
            return "n/a" if x is None else f"{x / 1e6:,.0f}m {unit}"

        def add(cat, sev, title, summary, data=None):
            res.signals.append(RiskSignal(category=cat, title=title, summary=summary, severity=sev,
                                          sources=srcs, collector=self.name, confidence=0.9,
                                          observed_at=latest, tags=["financials", "xbrl"], data=data or {}))

        add(C.FINANCIAL, S.INFO, f"Financial snapshot FY ending {latest}",
            "; ".join(f"{k.replace('_', ' ')}: {fmt(v)}" for k, v in m.items()),
            {"period_end": latest, "unit": unit, **{k: v for k, v in m.items()},
             "prior_period_end": prior, "prior": p})
        if m["equity"] is not None and m["equity"] < 0:
            add(C.FINANCIAL, S.HIGH, "Negative shareholders' equity",
                f"Equity of {fmt(m['equity'])} at {latest}: liabilities exceed assets.")
        if m["current_assets"] and m["current_liabilities"]:
            cr = m["current_assets"] / m["current_liabilities"]
            if cr < 1:
                add(C.FINANCIAL, S.MEDIUM if cr >= 0.7 else S.HIGH, f"Current ratio {cr:.2f} below 1.0",
                    f"Current assets {fmt(m['current_assets'])} vs current liabilities "
                    f"{fmt(m['current_liabilities'])} at {latest} indicate short-term liquidity pressure.",
                    {"current_ratio": round(cr, 3)})
        if m["assets"] and m["liabilities"] and not is_financial_firm:
            lev = m["liabilities"] / m["assets"]
            if lev > 0.9:
                add(C.FINANCIAL, S.MEDIUM, f"High leverage: liabilities are {lev:.0%} of assets",
                    f"Liabilities {fmt(m['liabilities'])} vs assets {fmt(m['assets'])} at {latest}.",
                    {"liabilities_to_assets": round(lev, 3)})
        if m["net_income"] is not None and m["net_income"] < 0:
            two = p["net_income"] is not None and p["net_income"] < 0
            add(C.FINANCIAL, S.HIGH if two else S.MEDIUM,
                "Net loss" + (" for two consecutive years" if two else f" in FY ending {latest}"),
                f"Net income {fmt(m['net_income'])} (FY {latest}); prior year {fmt(p['net_income'])}.")
        if m["revenue"] and p["revenue"]:
            chg = m["revenue"] / p["revenue"] - 1
            if chg < -0.10:
                add(C.FINANCIAL, S.HIGH if chg < -0.25 else S.MEDIUM, f"Revenue down {abs(chg):.0%} year over year",
                    f"Revenue {fmt(m['revenue'])} (FY {latest}) vs {fmt(p['revenue'])} (FY {prior}).",
                    {"revenue_change": round(chg, 4)})
        if m["operating_cash_flow"] is not None and m["operating_cash_flow"] < 0 and not is_financial_firm:
            add(C.FINANCIAL, S.MEDIUM, "Negative operating cash flow",
                f"Operating cash flow {fmt(m['operating_cash_flow'])} in FY ending {latest}.")
        res.checks.append(SourceCheck(api_src, self.name, "ok", f"annual XBRL data through {latest}"))
