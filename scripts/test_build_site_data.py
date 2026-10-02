"""The site's data must say what the paper says.

    python3 -m unittest scripts/test_build_site_data.py

Builds the data files into a temporary directory and checks the values the
paper reports, each audited against the archive. A change to the archive that
moves one of them fails here, before the site deploys, so the site and the
paper cannot drift apart silently.
"""

import sys
import tempfile
import unittest
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
        self.assertEqual(self.files, ["campaign.json", "fidelity.json", "retrieval.json",
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


if __name__ == "__main__":
    unittest.main()
