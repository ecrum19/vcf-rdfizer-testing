"""The site's data must say what the paper says.

    python3 -m unittest scripts/test_build_site_data.py

Builds the data files into a temporary directory and checks the values the
paper reports, each audited against the archive. A change to the archive that
moves one of them fails here, before the site deploys, so the site and the
paper cannot drift apart silently.
"""

import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site_data  # noqa: E402


class SiteDataMatchesThePaper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            cls.data = build_site_data.build(Path(td))
            cls.files = sorted(p.name for p in Path(td).iterdir())

    def test_every_dataset_is_written(self):
        self.assertEqual(self.files, ["campaign.json", "facts.json", "fidelity.json", "retrieval.json",
                                      "scaling.json", "usecase.json"])

    def test_campaign(self):
        totals = self.data["campaign"]["totals"]
        self.assertEqual(totals["cells"], 143)
        self.assertAlmostEqual(totals["hours"], 96.16, places=2)
        self.assertEqual(totals["byStatus"], {"OK": 136, "RECORDED": 2, "REFUSED": 2, "SKIPPED": 3})

    def test_validation_evidence(self):
        v = self.data["fidelity"]["validation"]
        self.assertEqual(v["validations"], 78)
        self.assertEqual(v["comparisons"]["PASS"], 984)
        self.assertEqual(sum(v["comparisons"].values()), 988)
        self.assertEqual(v["invariants"], {"PASS": 1144})
        self.assertEqual(v["rapper"], {"PASS": 76})
        self.assertEqual(v["enginesAnswering"], {"0": 2, "1": 51, "4": 25})
        self.assertEqual(v["decode"], {"hdt:pass": 118, "cottas:pass": 34})
        self.assertEqual((v["shacl"]["validations"], v["shacl"]["violations"]), (58, 0))
        self.assertEqual(v["maxValidatedTriples"], 17_098_746)

    def test_mutation_scores(self):
        scores = self.data["fidelity"]["mutation"]["scores"]
        self.assertEqual({k: (s["detected"], s["total"]) for k, s in scores.items()},
                         {"queries": (96, 113), "core": (96, 113), "full": (113, 113)})
        missed = self.data["fidelity"]["mutation"]["missedByQueries"]
        self.assertEqual(len(missed), 10)
        self.assertEqual(sum(m["mutations"] for m in missed), 17)

    def test_real_genome(self):
        real = self.data["fidelity"]["realGenome"]
        self.assertEqual(real["triples"], 58_231_176)
        statuses = {q["query"][:3]: q["status"] for q in real["queries"]}
        self.assertEqual(sorted(k for k, s in statuses.items() if s != "PASS"), ["q09", "q10", "q11"])

    def test_real_genome_rerun(self):
        """The v3.3.1 validator's rerun on the same graph: every answer equal, shapes clean."""
        real = self.data["fidelity"]["realGenome"]
        rerun = real["rerun"]
        self.assertEqual(rerun["triples"], real["triples"])
        self.assertEqual(len(rerun["queries"]), 13)
        self.assertEqual({q["status"] for q in rerun["queries"]}, {"PASS"})
        self.assertEqual((rerun["shacl"]["status"], rerun["shacl"]["violations"]), ("PASS", 0))

    def test_use_case_carriers(self):
        arms = self.data["usecase"]["arms"]
        expected = {
            "arm1": (7211, 2878, 2988, 1987),
            "arm2": (173102, 63529, 92870, 48207),
            "arm3": (1496, 1496, 0, 0),
        }
        for arm, counts in expected.items():
            with self.subTest(arm=arm):
                carriers = arms[arm]["carriers"]
                got = tuple(carriers[r]["rdf"] for r in ("unrestricted", "clinical", "cardio", "biobank"))
                self.assertEqual(got, counts)
                self.assertTrue(all(c["agree"] for c in carriers.values()))
        rare = arms["arm2"]["rare"]
        self.assertEqual([rare[r]["rdf"] for r in ("unrestricted", "clinical", "cardio", "biobank")],
                         [4154, 1621, 2198, 1144])

    def test_use_case_linking(self):
        arms = self.data["usecase"]["arms"]
        self.assertEqual(arms["arm1"]["linking"]["genomes"]["spdi"]["linked"], 51302)
        self.assertEqual(arms["arm2"]["linking"]["genomes"]["spdi"]["linked"], 1149198)
        self.assertEqual(arms["arm3"]["linking"]["genomes"]["spdi"]["linked"], 3887200)
        self.assertEqual(arms["arm3"]["linking"]["genomes"]["ensembl-genes-grch38"]["linked"], 1704921)
        self.assertEqual(arms["arm1"]["linking"]["clinvar"]["spdi"]["linked"], 331413)

    def test_retrieval(self):
        r = self.data["retrieval"]
        self.assertAlmostEqual(r["batch"]["setup"], 22.8, places=1)
        self.assertAlmostEqual(r["batch"]["parser"], 12.4, places=1)
        self.assertEqual({e: round(x["mean"], 1) for e, x in r["engines"].items()},
                         {"qlever": 1.1, "comunica": 23.4, "cottas": 38.2, "hdt": 45.1})
        regional = r["regional"]["slice"]["ms"]
        self.assertEqual(round(regional["qlever"]["1000"], 1), 9.6)
        self.assertEqual(round(regional["qlever"]["10000000"], 1), 11.1)
        self.assertEqual(round(regional["cyvcf2-indexed"]["1000"], 1), 3.3)
        executions = sum(g["executions"] for g in r["regional"].values())
        self.assertEqual(executions, 11160)
        whole = [row for row in r["scale"]["rows"]
                 if row["scale"] == "whole" and row["engine"] == "qlever" and row["artifact"] == "nt.gz"]
        self.assertAlmostEqual(sum(row["seconds"] for row in whole), 634.6, delta=0.1)
        per_million = [round(row["perMillion"], 2) for row in r["costBySize"]]
        self.assertEqual(per_million, [1.13, 1.0, 0.96, 0.97])

    def test_conversion_cost(self):
        s = self.data["scaling"]
        self.assertEqual([round(w, 1) for w in s["records"]["meanWall"][:3]], [40.7, 423.7, 5476.0])
        self.assertEqual(s["records"]["median"]["triples"][-1] > 6.5e8, True)
        expanded, condensed = s["samples"]["expanded"], s["samples"]["condensed"]
        self.assertEqual(round(expanded["triples"][-1] / condensed["triples"][-1]), 432)
        self.assertEqual(round(expanded["hdt"][-1] / condensed["hdt"][-1]), 69)
        cottas = [row["cottas"] / row["nt"] for row in s["corpus"]]
        self.assertEqual((round(min(cottas), 2), round(max(cottas), 2)), (0.37, 0.55))

    def test_facts_quoted_in_the_prose(self):
        facts = self.data["facts"]
        expected = {
            "campaignVersion": "v3.1.0", "cells": "143", "questions": "thirteen",
            "comparisonsEqual": "984", "comparisons": "988", "faults": "113", "faultsMissed": "17",
            "faultClasses": "ten", "realTriples": "58.2M", "phaseSets": "30,910", "qualChanged": "1,998",
            "genes": "81", "requesters": "three", "cohort": "104", "restrictedGenes": "28",
            "wholeGenomeAgreement": "equals", "wholeGenomeFold": "400", "wholeGenomeIndexMinutes": "45",
            "dataEdits": "three of four", "rdfRules": "72 lines (policy.ttl 41, carriers.rq 31)",
            "baselineRules": "131 lines (baseline.sh 33, baseline_carriers.py 98)",
            "myvariantShare": "92–93%", "myvariantRequests": "21",
            "rssLow": "1.0", "rssHigh": "1.7", "diskCut": "7.7–9.2", "tripleRatio": "432", "hdtRatio": "69",
            "representationHours": "14.5", "wholeHours": "16.07", "sliceTriples": "17.1M",
            "fixtureTriples": "0.96M", "midTriples": "171M", "maxTriples": "657M", "qleverIndex": "22.8 s",
            "artifactSpread": "0.3%", "regionalExecutions": "11,160", "regionalFailures": "no",
        }
        self.assertEqual({k: facts[k] for k in expected}, expected)


# Names that contain digits but quote no result.
NAMES = re.compile(r"1000 Genomes|HG00\d|NG131FQA1I|NB72462M|GRCh38|cyvcf2|vcf-bench-\d|[Aa]rm[ -]\d|\b\d\d_[a-z_]+")


class PageQuotesNoNumberOfItsOwn(unittest.TestCase):
    """Every number in the page's prose must come from facts.json, not be typed in."""

    def assert_no_digits(self, text, where):
        self.assertIsNone(re.search(r"\d", NAMES.sub("", text)), f"{where}: {text!r}")

    def test_index_html(self):
        class Text(HTMLParser):
            def __init__(self):
                super().__init__()
                self.chunks, self.skip = [], 0

            def handle_starttag(self, tag, attrs):
                self.skip += tag in ("head", "script", "style")

            def handle_endtag(self, tag):
                self.skip -= tag in ("head", "script", "style")

            def handle_data(self, data):
                if not self.skip and data.strip():
                    self.chunks.append(data.strip())

        parser = Text()
        parser.feed((build_site_data.ROOT / "site" / "index.html").read_text(encoding="utf-8"))
        for chunk in parser.chunks:
            self.assert_no_digits(chunk, "index.html")

    def test_chart_text(self):
        source = (build_site_data.ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
        prose = re.findall(r'(?:title|help|caption): "([^"]*)"', source) + re.findall(r'fill\("([^"]*)"\)', source)
        self.assertGreater(len(prose), 20)
        for text in prose:
            self.assert_no_digits(re.sub(r"\{\w+\}", "", text), "app.js")


if __name__ == "__main__":
    unittest.main()
