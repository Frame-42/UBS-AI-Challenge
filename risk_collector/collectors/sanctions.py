"""Sanctions-list screening against official government / UN publications.

Lists (all downloaded directly from the issuing authority):
  * OFAC Specially Designated Nationals (SDN) list        - U.S. Treasury
  * OFAC Consolidated (non-SDN) sanctions list           - U.S. Treasury
  * UN Security Council Consolidated List                - United Nations
  * EU Consolidated Financial Sanctions List              - European Commission
  * UK Sanctions List                                    - UK FCDO
  * Swiss SECO sanctions list (Gesamtliste)               - Swiss State Secretariat for Economic Affairs

Every hit cites the list, the issuing authority, the download URL, the list
entry identifier and the retrieval timestamp. Every list that was screened
without a hit is recorded as a ``SourceCheck`` so the report can state
"no match on <list> as of <date>".

Fuzzy matches are *potential* matches that require analyst review.
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from ..matching import NameIndex
from ..models import (Company, CollectorResult, RiskCategory, RiskSignal, Severity,
                      Source, SourceCheck, utcnow)
from .base import Collector

LIST_TTL = 24 * 3600  # sanctions lists are refreshed at most daily

Entry = Dict[str, object]  # id, primary_name, type, programs, listed_on, url, remarks


@dataclass
class SanctionsList:
    key: str
    name: str
    publisher: str
    urls: List[str]
    license: str
    parser: Callable[[List[bytes]], Iterator[Tuple[str, Entry]]]  # yields (name, entry)
    entry_url: Optional[str] = None  # template with {id}


# ------------------------------------------------------------------ parsers
def _ofac_csv(blobs: List[bytes]) -> Iterator[Tuple[str, Entry]]:
    """OFAC legacy CSV: primary file + alt-names file (joined on ent_num)."""
    prim, alt = blobs
    entries: Dict[str, Entry] = {}
    for row in csv.reader(io.StringIO(prim.decode("latin-1"))):
        if len(row) < 4 or not row[0].strip().isdigit():
            continue
        clean = [c.strip() if c.strip() != "-0-" else "" for c in row]
        ent = {"id": clean[0], "primary_name": clean[1], "type": clean[2] or "entity",
               "programs": [p.strip() for p in clean[3].split(";") if p.strip()],
               "remarks": clean[11] if len(clean) > 11 else ""}
        entries[clean[0]] = ent
        yield clean[1], ent
    for row in csv.reader(io.StringIO(alt.decode("latin-1"))):
        if len(row) >= 4 and row[0].strip() in entries:
            yield row[3].strip(), entries[row[0].strip()]


def _un_xml(blobs: List[bytes]) -> Iterator[Tuple[str, Entry]]:
    root = ET.fromstring(blobs[0])
    for kind, alias_tag in (("INDIVIDUAL", "INDIVIDUAL_ALIAS"), ("ENTITY", "ENTITY_ALIAS")):
        for el in root.iter(kind):
            parts = [(el.findtext(t) or "").strip() for t in
                     ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")]
            primary = " ".join(p for p in parts if p)
            ent = {"id": (el.findtext("REFERENCE_NUMBER") or el.findtext("DATAID") or "").strip(),
                   "primary_name": primary, "type": kind.lower(),
                   "programs": [(el.findtext("UN_LIST_TYPE") or "").strip()],
                   "listed_on": (el.findtext("LISTED_ON") or "").strip(),
                   "remarks": (el.findtext("COMMENTS1") or "").strip()[:500]}
            if primary:
                yield primary, ent
            for a in el.findall(alias_tag):
                n = (a.findtext("ALIAS_NAME") or "").strip()
                if n:
                    yield n, ent


def _eu_csv(blobs: List[bytes]) -> Iterator[Tuple[str, Entry]]:
    reader = csv.DictReader(io.StringIO(blobs[0].decode("utf-8-sig")), delimiter=";")
    entries: Dict[str, Entry] = {}
    for row in reader:
        eid = row.get("Entity_LogicalId", "")
        name = (row.get("NameAlias_WholeName") or "").strip()
        if not eid or not name:
            continue
        ent = entries.setdefault(eid, {
            "id": eid, "primary_name": name,
            "type": row.get("Entity_SubjectType_ClassificationCode") or "",
            "programs": [row.get("Entity_Regulation_Programme") or ""],
            "listed_on": row.get("Entity_DesignationDate") or "",
            "legal_basis_url": row.get("Entity_Regulation_PublicationUrl") or "",
            "remarks": (row.get("Entity_Remark") or "")[:500]})
        yield name, ent


def _uk_date(s: str) -> str:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", s.strip())
    return f"{m[3]}-{m[2]}-{m[1]}" if m else s


def _uk_csv(blobs: List[bytes]) -> Iterator[Tuple[str, Entry]]:
    text = blobs[0].decode("utf-8-sig")
    if text.startswith("Report Date"):
        text = text.split("\n", 1)[1]
    entries: Dict[str, Entry] = {}
    for row in csv.DictReader(io.StringIO(text)):
        uid = (row.get("Unique ID") or "").strip()
        parts = [row.get(f"Name {i}") or "" for i in range(1, 6)] + [row.get("Name 6") or ""]
        name = " ".join(p.strip() for p in parts if p and p.strip())
        if not uid or not name:
            continue
        is_primary = (row.get("Name type") or "").lower().startswith("primary name")
        ent = entries.get(uid)
        if ent is None:
            ent = entries[uid] = {"id": uid, "primary_name": name,
                                  "type": (row.get("Designation Type") or "").lower(),
                                  "programs": [row.get("Regime Name") or ""],
                                  "listed_on": _uk_date(row.get("Date Designated") or ""),
                                  "remarks": (row.get("Other Information") or "")[:500]}
        elif is_primary and (row.get("Name type") or "").lower() == "primary name":
            ent["primary_name"] = name
        yield name, ent


def _seco_xml(blobs: List[bytes]) -> Iterator[Tuple[str, Entry]]:
    root = ET.fromstring(blobs[0])
    programs: Dict[str, str] = {}
    for prog in root.findall("sanctions-program"):
        key = next((k.text for k in prog.findall("program-key") if k.get("lang") == "eng"), "")
        for s in prog.findall("sanctions-set"):
            programs[s.get("ssid", "")] = key or ""
    for t in root.findall("target"):
        mods = t.findall("modification")
        if mods:
            latest = max(mods, key=lambda m: m.get("effective-date") or m.get("enactment-date") or "")
            if latest.get("modification-type") == "de-listed":
                continue
        subj = next((c for c in t if c.tag in ("entity", "individual", "object")), None)
        if subj is None:
            continue
        names: List[str] = []
        for ident in subj.findall("identity"):
            for nm in ident.findall("name"):
                parts = sorted(nm.findall("name-part"), key=lambda p: int(p.get("order", "0")))
                n = " ".join((p.findtext("value") or "").strip() for p in parts).strip()
                if n:
                    names.append(n)
        if not names:
            continue
        listed = next((m.get("enactment-date") for m in mods if m.get("modification-type") == "listed"), "")
        ent = {"id": t.get("ssid", ""), "primary_name": names[0], "type": subj.tag,
               "programs": [programs.get(t.findtext("sanctions-set-id") or "", "")],
               "listed_on": listed or "",
               "remarks": (subj.findtext("justification") or "")[:500]}
        for n in names:
            yield n, ent


OFAC_LICENSE = "U.S. Government work - public domain"
LISTS: List[SanctionsList] = [
    SanctionsList("ofac_sdn", "OFAC Specially Designated Nationals (SDN) List",
                  "U.S. Department of the Treasury - Office of Foreign Assets Control",
                  ["https://www.treasury.gov/ofac/downloads/sdn.csv",
                   "https://www.treasury.gov/ofac/downloads/alt.csv"],
                  OFAC_LICENSE, _ofac_csv,
                  entry_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id={id}"),
    SanctionsList("ofac_cons", "OFAC Consolidated (non-SDN) Sanctions List",
                  "U.S. Department of the Treasury - Office of Foreign Assets Control",
                  ["https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv",
                   "https://www.treasury.gov/ofac/downloads/consolidated/cons_alt.csv"],
                  OFAC_LICENSE, _ofac_csv,
                  entry_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id={id}"),
    SanctionsList("un", "UN Security Council Consolidated List", "United Nations Security Council",
                  ["https://scsanctions.un.org/resources/xml/en/consolidated.xml"],
                  "Public UN document", _un_xml),
    SanctionsList("eu", "EU Consolidated Financial Sanctions List",
                  "European Commission - DG FISMA",
                  ["https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"],
                  "EU open data (reuse authorised, Commission Decision 2011/833/EU)", _eu_csv),
    SanctionsList("uk", "UK Sanctions List", "UK Foreign, Commonwealth & Development Office",
                  ["https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"],
                  "Open Government Licence v3.0", _uk_csv),
    SanctionsList("ch_seco", "Swiss Sanctions List (SECO)",
                  "Swiss State Secretariat for Economic Affairs (SECO)",
                  ["https://www.sesam.search.admin.ch/sesam-search-web/pages/downloadXmlGesamtliste.xhtml?lang=en&action=downloadXmlGesamtlisteAction"],
                  "Swiss Federal Administration open data", _seco_xml),
]


class SanctionsCollector(Collector):
    name = "sanctions"
    categories = [RiskCategory.SANCTIONS]
    description = "Screens the company, its aliases and related parties against official sanctions lists"

    def __init__(self, http, lookback_days: int = 90, threshold: float = 0.88,
                 lists: Optional[List[str]] = None) -> None:
        super().__init__(http, lookback_days)
        self.threshold = threshold
        self.lists = [sl for sl in LISTS if lists is None or sl.key in lists]
        self._indexes: Dict[str, Tuple[NameIndex, str]] = {}

    def _load(self, sl: SanctionsList) -> Tuple[NameIndex, str]:
        if sl.key not in self._indexes:
            resps = [self.http.get(u, cache_ttl=LIST_TTL) for u in sl.urls]
            idx = NameIndex()
            for name, entry in sl.parser([r.body for r in resps]):
                idx.add(name, entry)
            self._indexes[sl.key] = (idx, resps[0].retrieved_at)
        return self._indexes[sl.key]

    def collect(self, company: Company) -> CollectorResult:
        res = CollectorResult(self.name)
        subjects = [(n, "company") for n in company.all_names] + \
                   [(n, "related party") for n in company.related_parties]
        for sl in self.lists:
            list_src = Source(name=sl.name, publisher=sl.publisher, url=sl.urls[0],
                              license=sl.license, retrieved_at=utcnow())
            try:
                idx, retrieved_at = self._load(sl)
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"{sl.name}: {e}")
                res.checks.append(SourceCheck(list_src, self.name, "error", str(e)))
                continue
            list_src.retrieved_at = retrieved_at

            best: Dict[str, Tuple[float, str, str, Entry]] = {}  # entry id -> best hit
            for query, role in subjects:
                for score, matched, entry in idx.search(query, self.threshold):
                    eid = str(entry["id"])
                    if eid not in best or score > best[eid][0]:
                        best[eid] = (score, query, role, entry)  # type: ignore[assignment]

            for score, query, role, entry in sorted(best.values(), key=lambda b: -b[0]):
                res.signals.append(self._signal(sl, list_src, score, query, role, entry))
            names = ", ".join(q for q, _ in subjects)
            res.checks.append(SourceCheck(
                list_src, self.name, "ok" if best else "no_match",
                (f"{len(best)} potential match(es)" if best else f"no match for: {names}")
                + f" (threshold {self.threshold:.2f})", len(idx)))
        return res

    def _signal(self, sl: SanctionsList, list_src: Source, score: float, query: str, role: str,
                entry: Entry) -> RiskSignal:
        eid = str(entry["id"])
        sources = [list_src]
        if sl.entry_url:
            sources.insert(0, Source(name=f"{sl.name} entry {eid}: {entry['primary_name']}",
                                     publisher=sl.publisher, url=sl.entry_url.format(id=eid),
                                     retrieved_at=list_src.retrieved_at, license=sl.license))
        if entry.get("legal_basis_url"):
            sources.append(Source(name=f"Legal act designating {entry['primary_name']}",
                                  publisher=sl.publisher, url=str(entry["legal_basis_url"]),
                                  retrieved_at=list_src.retrieved_at))
        exact = score >= 0.97
        severity = (Severity.CRITICAL if exact and role == "company"
                    else Severity.HIGH if exact or role == "company" else Severity.MEDIUM)
        programs = ", ".join(p for p in entry.get("programs", []) if p) or "n/a"  # type: ignore[union-attr]
        return RiskSignal(
            category=RiskCategory.SANCTIONS,
            title=f"{'Match' if exact else 'Potential match'}: '{query}' ~ '{entry['primary_name']}' on {sl.name}",
            summary=(f"{role.capitalize()} name '{query}' matched {sl.name} entry {eid} "
                     f"('{entry['primary_name']}', type {entry.get('type') or 'n/a'}, programme(s) {programs}"
                     + (f", listed {entry['listed_on']}" if entry.get("listed_on") else "")
                     + f") with similarity {score:.2f}. Requires analyst review to confirm identity."),
            severity=severity, sources=sources, collector=self.name, confidence=score,
            observed_at=str(entry.get("listed_on") or "") or None,
            tags=["sanctions", sl.key, role],
            data={"list": sl.key, "entry_id": eid, "matched_query": query, "role": role,
                  "entry": {k: v for k, v in entry.items() if k != "legal_basis_url"}})
