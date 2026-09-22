# UBS-AI-Challenge: company risk data collection

`risk_collector` collects public risk data about a company in five categories: **cybersecurity, fraud, reputational, financial and sanctions**. It writes a JSON dataset and a Markdown brief. **Every finding cites its sources**, and every source that was checked is recorded, including the ones that returned nothing. The combined collection/scoring repository uses only the Python standard library (Python 3.11 or later).

## Quick start

```bash
python3 -m risk_collector --company-file companies/microsoft/company.json --out companies/microsoft
python3 -m risk_collector "Boeing" --alias "The Boeing Company" --ticker BA --domain boeing.com
python3 -m risk_collector "Sberbank" --related "Herman Gref" --collectors sanctions
python3 -m risk_collector --list-collectors
python3 -m unittest discover -s tests -v  # offline tests
```

Options: `--categories`, `--collectors`, `--lookback-days`, `--out` (default `reports/`), `--no-cache`, `-v`.
For SEC EDGAR, set a User-Agent that identifies you, as SEC's [fair-access policy](https://www.sec.gov/os/accessing-edgar-data) requires:
`export RISK_COLLECTOR_USER_AGENT="Your Org risk-team you@yourorg.com"`.

## Data sources

| Collector | Categories | Source (publisher) | Notes |
|---|---|---|---|
| `gdelt` | cyber, fraud, reputational, financial | [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) (The GDELT Project) | News articles from the last 90 days, found with keyword queries for each category, plus a news-tone timeline. Each article cites its own publisher and URL. The API allows 1 request every 5 seconds. |
| `sanctions` | sanctions | OFAC SDN + Consolidated lists (U.S. Treasury), UN Security Council Consolidated List, EU Consolidated Financial Sanctions List, UK Sanctions List (FCDO), Swiss SECO list | Official downloads from each issuing authority, cached for 24h. Fuzzy name matching (default threshold 0.88) covers the company, its aliases and any `related_parties`. |
| `sec_edgar` | financial, fraud, cyber, reputational | SEC EDGAR submissions, full-text search, XBRL company facts | Risk-relevant 8-K items (1.05 cyber incident, 1.03 bankruptcy, 4.02 non-reliance, 4.01 auditor change, and others), NT late filings, red-flag phrases in filings, and annual ratios such as equity, liquidity, leverage, losses and revenue decline. |
| `cisa_kev` | cyber | CISA Known Exploited Vulnerabilities catalog | Vulnerabilities in the company's own products that are being exploited in the wild. Each links to its NVD entry. |
| `hibp` | cyber | Have I Been Pwned breach catalogue (CC BY 4.0) | Known data breaches, matched by domain or name. |

## How sourcing is enforced

- `RiskSignal` cannot be created without at least one `Source`, and a `Source` needs a name, publisher and URL (`risk_collector/models.py`).
- Each `Source` records `retrieved_at`, and where known also `published_at`, `accessed_via` (for example "GDELT DOC 2.0 API") and `license`.
- `SourceCheck` records every source that was consulted, with its status (`ok`, `no_match` or `error`). For example: "no match on OFAC SDN as of <timestamp>".
- In the Markdown brief, every finding has numbered citations `[n]` that point to a References list, and there is a Source coverage table.

## Layout

```
risk_collector/
  models.py      Company, Source, RiskSignal, SourceCheck
  http.py        stdlib HTTP client: per-host rate limits, retries, disk cache
  matching.py    name normalisation and fuzzy matching
  collectors/    gdelt, sanctions, sec_edgar, cyber (cisa_kev, hibp)
  pipeline.py    runs collectors and builds per-category summaries and scores
  report.py      JSON and Markdown (citations) output
```

To add a source, subclass `collectors.base.Collector`, return a `CollectorResult` with sourced signals and checks, and register the class in `collectors/__init__.py`.

## Caveats

Findings are **signals for analyst review**, not conclusions. Fuzzy sanctions hits, and keyword matches in news or filings, can be false positives. The category scores (0–100) are a simple sum of severity weighted by confidence, and are meant for triage only.
