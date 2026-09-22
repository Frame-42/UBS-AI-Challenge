"""Entity-name normalisation and fuzzy matching (stdlib only)."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Set, Tuple

# Legal-form suffixes and filler words that should not drive a match.
LEGAL_FORMS = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LLC",
    "LLP", "LP", "PLC", "AG", "SA", "SAS", "SARL", "SPA", "NV", "BV", "GMBH", "KG", "AB", "AS",
    "ASA", "OY", "OYJ", "JSC", "OJSC", "PJSC", "CJSC", "OOO", "ZAO", "OAO", "PAO", "AO", "TOO",
    "PTE", "PTY", "BHD", "SDN", "KK", "SE", "THE", "OF", "AND", "HOLDING", "HOLDINGS", "GROUP",
}
LEGAL_PHRASES = re.compile(r"\b(?:(?:PUBLIC|OPEN|CLOSED|PRIVATE) )?JOINT STOCK\b|\bLIMITED LIABILITY\b|"
                           r"\bSOCIETE ANONYME\b|\bAKTIENGESELLSCHAFT\b")


def normalize(name: str) -> str:
    """Upper-case, strip accents/punctuation and legal forms: 'Boeing Co.' -> 'BOEING'."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = LEGAL_PHRASES.sub(" ", s)
    tokens = [t for t in s.split() if t not in LEGAL_FORMS]
    return " ".join(tokens)


def tokens(name: str) -> List[str]:
    return normalize(name).split()


def similarity(a: str, b: str) -> float:
    """Similarity in [0, 1] of two already-normalised names.

    Combines a character-level ratio with a token-set comparison so that word
    order differences ("BANK OF X" vs "X BANK") are tolerated.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    char = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    inter = " ".join(sorted(ta & tb))
    sa = " ".join(sorted(ta))
    sb = " ".join(sorted(tb))
    token_set = max(
        SequenceMatcher(None, inter, sa).ratio() if inter else 0.0,
        SequenceMatcher(None, inter, sb).ratio() if inter else 0.0,
        SequenceMatcher(None, sa, sb).ratio(),
    )
    # A token-set hit only counts fully when both names have similar length,
    # otherwise "BANK" would match every "X BANK".
    len_penalty = min(len(ta), len(tb)) / max(len(ta), len(tb))
    return max(char, token_set * (0.6 + 0.4 * len_penalty))


class NameIndex:
    """Inverted token index so we only fuzzy-compare plausible candidates."""

    def __init__(self) -> None:
        self._names: List[Tuple[str, object]] = []  # (normalised name, payload)
        self._index: Dict[str, Set[int]] = {}

    def add(self, name: str, payload: object) -> None:
        norm = normalize(name)
        if not norm:
            return
        i = len(self._names)
        self._names.append((norm, payload))
        for t in set(norm.split()):
            self._index.setdefault(t, set()).add(i)

    def __len__(self) -> int:
        return len(self._names)

    def search(self, query: str, threshold: float = 0.88) -> List[Tuple[float, str, object]]:
        q = normalize(query)
        if not q:
            return []
        cand: Set[int] = set()
        for t in q.split():
            cand |= self._index.get(t, set())
        hits = []
        for i in cand:
            norm, payload = self._names[i]
            score = similarity(q, norm)
            if score >= threshold:
                hits.append((score, norm, payload))
        hits.sort(key=lambda h: -h[0])
        return hits


def mentions_any(text: str, names: Iterable[str]) -> bool:
    t = normalize(text)
    return any(n and re.search(rf"\b{re.escape(n)}\b", t) for n in (normalize(x) for x in names))
