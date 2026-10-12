"""The site's data must say what the paper says.

    python3 -m unittest scripts/test_build_site_data.py

Builds the data files into a temporary directory and checks the values the
paper reports, each audited against the archive. A change to the archive that
moves one of them fails here, before the site deploys, so the site and the
paper cannot drift apart silently.
"""

import re
import statistics
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
        self.assertEqual(self.files, ["campaign.json", "converters.json", "facts.json", "fidelity.json",
                                      "queries.json", "retrieval.json", "scaling.json", "usecase.json"])

    def test_every_query_shows_its_query_and_oracle(self):
        """Each query has its exact text, a pseudo-code oracle, and the exact oracle code;
        preflight checks assert graph properties and may have no oracle code."""
        groups = {g["id"]: g for g in self.data["queries"]["groups"]}
        self.assertEqual(set(groups), {"validation", "preflight", "usecase", "converters", "regional",
                                       "shacl-core", "shacl-consistency", "shacl-sparql"})
        self.assertEqual(len(groups["validation"]["items"]), 13)
        self.assertEqual(len(groups["converters"]["items"]), 8)
        self.assertEqual(len(groups["regional"]["items"]), 5)
        for group in groups.values():
            if group.get("kind") == "shacl":
                continue
            for item in group["items"]:
                self.assertTrue(item["summary"] and item["pseudo"].strip(), item["id"])
                self.assertTrue(item["sparql"] and all(q["text"].strip() for q in item["sparql"]), item["id"])
                if group["id"] != "preflight":
                    self.assertTrue(item["oracleCode"] and all(c["text"].strip() for c in item["oracleCode"]), item["id"])

    def test_the_paper_names_fourteen_preflight_queries(self):
        """The site stars what the paper's validation paragraph names, and counts the preflight
        queries the way app.js does (one per query file): eight checks, fourteen queries."""
        groups = {g["id"]: g for g in self.data["queries"]["groups"]}
        preflight = groups["preflight"]["items"]
        files = [len({Path(q["from"][0]["path"]).name for q in item["sparql"]}) for item in preflight]
        self.assertEqual((len(preflight), sum(files)), (8, 14))
        self.assertEqual({k for k, g in groups.items() if g.get("paper")},
                         {"preflight", "shacl-core", "shacl-consistency", "shacl-sparql"})

    def test_every_shape_shows_its_constraints_and_text(self):
        """Every node shape of the three profiles the validator runs, each with its exact
        Turtle text and line range at both releases."""
        groups = {g["id"]: g for g in self.data["queries"]["groups"] if g.get("kind") == "shacl"}
        self.assertEqual({k: len(g["items"]) for k, g in groups.items()},
                         {"shacl-core": 53, "shacl-consistency": 24, "shacl-sparql": 6})
        for group in groups.values():
            self.assertEqual([f["rev"] for f in group["file"]], ["v3.1.0", "v3.3.1"])
            for item in group["items"]:
                self.assertIn(item["label"], item["text"], item["id"])
                self.assertTrue(item["summary"] and item["constraints"], item["id"])
                self.assertTrue(all(f["lines"][0] <= f["lines"][1] for f in item["from"]), item["id"])

    def test_paper_links_land_on_a_section(self):
        """Every #section the paper or supplement links to exists: a section id in the page,
        or a query or shape anchor built the way app.js's itemAnchor() builds it."""
        page = (build_site_data.ROOT / "site" / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'\sid="([^"]+)"', page)
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids in index.html")
        for section in ("rq1-queries", "rq1-checks", "rq2-queries", "rq3-queries", "notes"):
            self.assertIn(section, ids)
        items = {f"{g['rq'].lower()}-{re.sub(r'[^a-z0-9]+', '-', item['id'].lower())}"
                 for g in self.data["queries"]["groups"] for item in g["items"]}
        self.assertFalse(items & set(ids), "a query anchor collides with a section id")
        papers = (build_site_data.ROOT / "BioMedSem_2026" / "paper").glob("*.tex")
        linked = {m for tex in papers for m in re.findall(r"vcf-rdfizer-testing/\\?#([\w-]+)", tex.read_text(encoding="utf-8"))}
        self.assertEqual(linked - set(ids) - items, set())

    def test_every_host_has_its_record(self):
        """Each host behind a reported result is listed, with the record its details come from."""
        hosts = self.data["campaign"]["hostRecords"]
        self.assertEqual([h["host"] for h in hosts], ["vcf-bench-1", "vcf-bench-2", "vcf-bench-3"])
        for host in hosts:
            path = build_site_data.ROOT / host["record"].split("/blob/main/", 1)[1]
            self.assertTrue(path.is_file(), path)
            self.assertTrue(host["cpu_model"] and host["kernel"] and host["docker"] and host["mem_total_kb"], host["host"])

    def test_campaign(self):
        totals = self.data["campaign"]["totals"]
        self.assertEqual(totals["cells"], 143)
        self.assertAlmostEqual(totals["hours"], 96.17, places=2)
        # The one RECORDED cell is the truncated gzip's intended refusal. The
        # sites-only fixture was the second until its rerun with a conformant
        # fixture (2026-10-10); the malformed first run is on the legacy branch.
        self.assertEqual(totals["byStatus"], {"OK": 137, "RECORDED": 1, "REFUSED": 2, "SKIPPED": 3})

    def test_validation_evidence(self):
        v = self.data["fidelity"]["validation"]
        self.assertEqual(v["validations"], 78)
        self.assertEqual(v["comparisons"]["PASS"], 1006)
        # Eight genotype comparisons (Q5, Q6) are verified not applicable: four
        # on the zero-record fixture and four on the sites-only fixture.
        self.assertEqual(v["comparisons"]["NOT_APPLICABLE_VERIFIED_NO_SAMPLES_OR_GT"], 8)
        self.assertEqual(sum(v["comparisons"].values()), 1014)
        self.assertEqual(v["invariants"], {"PASS": 1160})
        self.assertEqual(v["rapper"], {"PASS": 78})
        self.assertEqual(v["enginesAnswering"], {"1": 53, "4": 25})
        self.assertEqual(v["decode"], {"hdt:pass": 118, "cottas:pass": 34})
        self.assertEqual((v["shacl"]["validations"], v["shacl"]["violations"]), (60, 0))
        self.assertEqual(v["maxValidatedTriples"], 17_098_746)

    def test_mutation_scores(self):
        scores = self.data["fidelity"]["mutation"]["scores"]
        self.assertEqual({k: (s["detected"], s["total"]) for k, s in scores.items()},
                         {"queries": (96, 113), "core": (96, 113), "full": (113, 113)})
        missed = self.data["fidelity"]["mutation"]["missedByQueries"]
        self.assertEqual(len(missed), 10)
        self.assertEqual(sum(m["mutations"] for m in missed), 17)

    def test_real_genome(self):
        """The consumer WGS validation run with v3.3.1: every answer equal, shapes clean."""
        real = self.data["fidelity"]["realGenome"]
        self.assertEqual(real["triples"], 58_231_176)
        self.assertEqual(len(real["queries"]), 13)
        self.assertEqual({q["status"] for q in real["queries"]}, {"PASS"})
        self.assertEqual((real["shacl"]["status"], real["shacl"]["violations"]), ("PASS", 0))
        self.assertEqual((real["shacl"]["batches"], real["shacl"]["advisories"]), (117, 46))

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
        # Scenario 4 adds the participant's own physician as a requester (Table S9).
        arm4 = arms["arm4"]["carriers"]
        self.assertEqual({r: c["rdf"] for r, c in arm4.items()},
                         {"unrestricted": 1382, "own_physician": 1382, "clinical": 1382, "cardio": 722, "biobank": 983})
        self.assertTrue(all(c["agree"] for c in arm4.values()))
        rare = arms["arm2"]["rare"]
        self.assertEqual([rare[r]["rdf"] for r in ("unrestricted", "clinical", "cardio", "biobank")],
                         [4154, 1621, 2198, 1144])

    def test_use_case_records_and_costs(self):
        """Released records agree except Scenario 2's symbolic SVs; Scenario 4's once-per-scenario costs (Section S5.4)."""
        arms = self.data["usecase"]["arms"]
        differ = {(arm, r): c["rdf"] - c["baseline"] for arm, a in arms.items()
                  for r, c in a["records"].items() if not c["agree"]}
        self.assertEqual(differ, {("arm2", "cardio"): 110, ("arm2", "biobank"): 58})
        costs = arms["arm4"]["costs"]
        self.assertEqual((round(costs["convert"] / 60, 1), round(costs["link"] / 60, 1)), (88.7, 16.5))
        # The conventional workflow: one run per scenario for all requesters (Table S11).
        self.assertEqual([a["costs"]["conventional"] for a in arms.values()], [4, 77, 54, 91])

    def test_use_case_linking(self):
        arms = self.data["usecase"]["arms"]
        self.assertEqual(arms["arm1"]["linking"]["genomes"]["spdi"]["linked"], 51302)
        self.assertEqual(arms["arm2"]["linking"]["genomes"]["spdi"]["linked"], 1149198)
        self.assertEqual(arms["arm3"]["linking"]["genomes"]["spdi"]["linked"], 3887200)
        self.assertEqual(arms["arm3"]["linking"]["genomes"]["ensembl-genes-grch38"]["linked"], 1704954)
        self.assertEqual(arms["arm1"]["linking"]["clinvar"]["spdi"]["linked"], 331413)

    def test_use_case_figure_inputs_and_timings(self):
        """Figure 5 uses release conversions, with shared annotations counted once."""
        arms = self.data["usecase"]["arms"]
        self.assertEqual(self.data["usecase"]["convertImages"], ["ecrum19/vcf-rdfizer:3.3.1"])
        cohort = arms["arm2"]
        self.assertEqual(cohort["inputs"]["genomes"],
                         {"files": 104, "records": 1150288, "triples": 67848218})
        self.assertEqual(cohort["inputs"]["panel"],
                         {"files": 1, "records": 68635, "triples": 6517672})
        for arm in arms.values():
            self.assertEqual(arm["inputs"]["clinvar"],
                             {"files": 1, "records": 331453, "triples": 33096749})
        self.assertEqual(arms["arm4"]["inputs"]["genomes"],
                         {"files": 1, "records": 5063417, "triples": 1209739110})
        rare = cohort["queries"]["unrestricted"]["replicates"]["rare"]
        self.assertEqual(len(rare), 3)
        self.assertAlmostEqual(statistics.median(rare), 174.429, places=3)
        self.assertAlmostEqual(cohort["queries"]["unrestricted"]["setup"], 191.126, places=3)
        self.assertEqual((cohort["costs"]["convert"], cohort["costs"]["link"]), (2043, 1334))

    def test_use_case_conversion_provenance(self):
        """All plotted graph sizes come from the same pinned published release."""
        digest = "ecrum19/vcf-rdfizer@sha256:3ad71b1a54612142e3be43b24e7e4a38551949cb641f4421bcae9bf051102993"
        for arm in build_site_data.ARMS.values():
            for cell in build_site_data.reported_cells(arm, "convert"):
                with self.subTest(cell=cell.name, arm=arm.name):
                    bench = build_site_data.load(cell / "bench.json")
                    self.assertEqual(bench["image_mode"], "pinned-release")
                    self.assertEqual(bench["image_digest"], digest)

    def test_retrieval(self):
        r = self.data["retrieval"]
        self.assertAlmostEqual(r["batch"]["setup"], 22.8, places=1)
        self.assertAlmostEqual(r["batch"]["parser"], 12.4, places=1)
        self.assertEqual({e: round(x["mean"], 1) for e, x in r["engines"].items()},
                         {"qlever": 1.1, "comunica": 23.4, "cottas": 38.2, "hdt": 45.1})
        regional = r["regional"]["slice"]["ms"]
        self.assertEqual(round(regional["qlever"]["1000"], 1), 10.6)
        self.assertEqual(round(regional["qlever"]["10000000"], 1), 10.3)
        self.assertEqual(round(regional["cyvcf2-indexed"]["1000"], 1), 3.2)
        executions = sum(g["executions"] for g in r["regional"].values())
        self.assertEqual(executions, 11160)
        whole = [row for row in r["scale"]["rows"]
                 if row["scale"] == "whole" and row["engine"] == "qlever" and row["artifact"] == "nt.gz"]
        self.assertAlmostEqual(sum(row["seconds"] for row in whole), 646.4, delta=0.1)
        per_million = [round(row["perMillion"], 2) for row in r["costBySize"]]
        self.assertEqual(per_million, [1.13, 1.0, 0.97, 0.98])

    def test_break_even(self):
        """The minimal setup crosses over after about eleven questions; with HDT, 44 (Section S9.4)."""
        b = self.data["retrieval"]["breakEven"]
        self.assertEqual((round(b["conversion"], 1), round(b["index"], 1)), (95.7, 25.0))
        self.assertEqual((round(b["scan"], 2), round(b["query"], 2)), (12.28, 1.43))
        self.assertEqual((round(b["n_star"]), round(b["n_star_with_hdt"])), (11, 44))
        self.assertEqual((round(min(b["per_question"].values())), round(max(b["per_question"].values()))), (10, 17))

    def test_converters(self):
        """Only VCF-RDFizer answers all eight content questions as the oracle does, on both inputs (Figure 6)."""
        c = self.data["converters"]
        self.assertEqual(len(c["questions"]), 8)
        passed = {}
        for o in c["outcomes"]:
            passed.setdefault(o["tool"], []).append(o["status"] == "PASS")
        self.assertEqual({t for t, ok in passed.items() if all(ok)}, {"vcf-rdfizer"})
        self.assertEqual(len(c["outcomes"]), 5 * 2 * 8)

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
            "comparisonsEqual": "1,006", "comparisons": "1,014", "comparisonsOther": "eight", "faults": "113", "faultsMissed": "17",
            "faultClasses": "ten", "realTriples": "58.2M",
            "genes": "81", "requesters": "three", "cohort": "104", "restrictedGenes": "28",
            "wholeGenomeAgreement": "equals", "wholeGenomeFold": "400", "wholeGenomeIndexMinutes": "46",
            "dataEdits": "three of four", "rdfRules": "72 lines (policy.ttl 41, carriers.rq 31)",
            "baselineRules": "131 lines (baseline.sh 33, baseline_carriers.py 98)",
            "myvariantShare": "92–93%", "myvariantRequests": "21",
            "rssLow": "1.0", "rssHigh": "1.7", "diskCut": "7.7–9.2", "tripleRatio": "432", "hdtRatio": "69",
            "representationHours": "14.5", "wholeHours": "16.07", "sliceTriples": "17.1M",
            "fixtureTriples": "0.96M", "midTriples": "171M", "maxTriples": "657M", "qleverIndex": "22.8 s",
            "artifactSpread": "0.4%", "regionalExecutions": "11,160", "regionalFailures": "no",
            "scenarios": "four", "armsAgree": "four", "arm4Requesters": "four", "recordArmsAgree": "Scenarios 1, 3 and 4",
            "recordArmsDiffer": "Scenario 2", "recordExtra": "110 and 58", "querySeconds": "171–233",
            "conventionalSeconds": "4–91", "convertLinkMinutes": "5.7–105", "conventionalFold": "40",
            "converters": "four", "converterQuestions": "eight", "converterAllPass": "VCF-RDFizer",
            "breakEven": "11", "breakEvenWithHdt": "44", "breakEvenRange": "10–17", "invariants": "1,160",
        }
        self.assertEqual({k: facts[k] for k in expected}, expected)


# Names that contain digits but quote no result.
NAMES = re.compile(r"1000 Genomes|HG00\d|NG131FQA1I|NB72462M|GRCh38|cyvcf2|vcf-bench-\d|[Ss]cenarios?[ -]\d|\b\d\d_[a-z_]+"
                   r"|RQ\d|BioMedSem \d{4}")


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
