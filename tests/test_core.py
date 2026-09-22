"""Offline tests: no network access required."""
import unittest

from risk_collector.collectors.gdelt import build_query
from risk_collector.collectors.reputation import (classify_doj, is_defendant, latest_year,
                                                  split_sections, suit_theme)
from risk_collector.collectors.sanctions import _ofac_csv, _uk_csv
from risk_collector.matching import NameIndex, normalize, similarity
from risk_collector.models import Company, RiskCategory, RiskSignal, Severity, Source
from risk_collector.pipeline import RiskReport, summarise
from risk_collector.report import to_markdown

SRC = Source("Test dataset", "Test publisher", "https://example.org/item/1")


class SourcingTests(unittest.TestCase):
    def test_signal_without_sources_is_rejected(self):
        with self.assertRaises(ValueError):
            RiskSignal(RiskCategory.FRAUD, "t", "s", Severity.LOW, sources=[], collector="x")

    def test_source_requires_url(self):
        with self.assertRaises(ValueError):
            Source("name", "publisher", "")

    def test_markdown_cites_every_signal(self):
        sig = RiskSignal(RiskCategory.FRAUD, "Fraud probe", "summary", Severity.HIGH, [SRC], "x")
        rep = RiskReport(Company("Acme"), "2026-01-01", {}, [sig], [], [],
                         summarise([sig], list(RiskCategory)))
        md = to_markdown(rep)
        self.assertIn("Fraud probe", md)
        self.assertIn("[1]", md)
        self.assertIn("1. Test dataset. *Test publisher*.", md)
        self.assertIn("https://example.org/item/1", md)


class MatchingTests(unittest.TestCase):
    def test_normalize_strips_legal_forms(self):
        self.assertEqual(normalize("The Boeing Co."), "BOEING")
        self.assertEqual(normalize("PJSC Sberbank"), "SBERBANK")

    def test_similarity(self):
        self.assertEqual(similarity("SBERBANK", "SBERBANK"), 1.0)
        self.assertLess(similarity("BANK", "SBERBANK OF RUSSIA"), 0.88)

    def test_index_search(self):
        idx = NameIndex()
        idx.add("Public Joint Stock Company Sberbank of Russia", {"id": "1"})
        idx.add("Bank Melli Iran", {"id": "2"})
        hits = idx.search("Sberbank of Russia")
        self.assertEqual([h[2]["id"] for h in hits], ["1"])
        self.assertEqual(idx.search("Boeing"), [])


class ParserTests(unittest.TestCase):
    def test_ofac_joins_aliases(self):
        prim = b'306,"BANCO NACIONAL DE CUBA",-0- ,"CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n'
        alt = b'306,220,"aka","NATIONAL BANK OF CUBA",-0- \n'
        names = [n for n, _ in _ofac_csv([prim, alt])]
        self.assertEqual(names, ["BANCO NACIONAL DE CUBA", "NATIONAL BANK OF CUBA"])

    def test_uk_skips_report_date_line(self):
        csv = ("Report Date: 21-Sep-2026\nUnique ID,Name 1,Name 6,Name type,Designation Type,Regime Name,"
               "Date Designated\nRUS001,,ACME BANK,Primary Name,Entity,Russia,01/03/2022\n").encode()
        (name, entry), = list(_uk_csv([csv]))
        self.assertEqual(name, "ACME BANK")
        self.assertEqual(entry["listed_on"], "2022-03-01")


class GdeltTests(unittest.TestCase):
    def test_query(self):
        q = build_query(["UBS", "UBS Group AG"], ["fraud", '"money laundering"'])
        self.assertEqual(q, '(UBS OR "UBS Group AG") (fraud OR "money laundering") sourcelang:english')


class ReputationTests(unittest.TestCase):
    def test_defendant_side(self):
        self.assertTrue(is_defendant("Akiyoshi v. HireRight, LLC", ["HireRight"]))
        self.assertFalse(is_defendant("Microsoft Corp. v. Doe", ["Microsoft"]))

    def test_suit_theme(self):
        self.assertEqual(suit_theme("850 Securities/Commodities"), "securities")
        self.assertEqual(suit_theme("3480 Consumer Credit"), "consumer")
        self.assertEqual(suit_theme("Consumer Credit"), "consumer")
        self.assertIsNone(suit_theme("830 Patent"))

    def test_classify_doj(self):
        names = ["Microsoft"]
        self.assertEqual(classify_doj("Microsoft Agrees to Pay $20 Million Civil Penalty", names)[0], Severity.HIGH)
        self.assertEqual(classify_doj("Software Distributor Sentenced for Illicit Microsoft Keys", names)[0],
                         Severity.INFO)
        self.assertEqual(classify_doj("Indictment Charges Man with Defrauding Amazon", ["Amazon"])[0], Severity.INFO)
        self.assertIsNone(classify_doj("San Francisco Man Sentenced", ["Cisco"]))

    def test_split_sections(self):
        text = "Intro\n== History ==\nFounded.\n== Controversies ==\nx\n=== Antitrust ===\nFined in 2004."
        secs = split_sections(text)
        self.assertEqual([p for p, _ in secs], [["History"], ["Controversies"], ["Controversies", "Antitrust"]])
        self.assertEqual(latest_year(secs[-1][1]), 2004)


if __name__ == "__main__":
    unittest.main()
