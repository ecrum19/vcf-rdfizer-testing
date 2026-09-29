#!/usr/bin/env python3
"""Tests for the ACMG use case's own code (not for VCF-RDFizer).

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 test_use_case.py

Needs rdflib. The policy tests also need a VCF-RDFizer checkout, for the
policy plug-in (sibling checkout by default); the derive test needs bcftools
on PATH and is skipped without it -- run it inside the image.

The central test is TwoConsentImplementationsAgree: the policy (generate.py ->
policy.ttl, applied by vcf-rdfizer-policy) and the baseline's consent script
(baseline_carriers.py) must release the same records to every requester. They
are written independently on purpose, so this is the test that catches one of
them misreading use_case.json.
"""

from __future__ import annotations

import collections
import contextlib
import csv
import gzip
import io
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baseline_carriers as B  # noqa: E402
import make_cohort as M  # noqa: E402
import compare as C  # noqa: E402

from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD  # noqa: E402

VCFC = Namespace("https://w3id.org/vcf-core/vocab#")
VCFL = Namespace("https://w3id.org/vcf-rdfizer/linking#")
CASE = json.loads((HERE / "use_case.json").read_text(encoding="utf-8"))
REGIONS = {r["symbol"]: r for r in json.loads((HERE / "regions.json").read_text(encoding="utf-8"))["regions"]}
SPDI = "https://api.ncbi.nlm.nih.gov/variation/v0/spdi/"
ASSEMBLY = "GCA_000001405.15_GRCh38_no_alt_analysis_set"


def tool_checkout() -> pathlib.Path | None:
    """The VCF-RDFizer checkout, or None so the tests that need it skip.

    Returns None rather than raising when this file is somewhere shallow --
    mounted at /case inside the image, say, where a sibling checkout cannot
    exist and the policy tests are not the ones being run.
    """
    explicit = os.environ.get("VCF_RDFIZER_SRC")
    if explicit:
        candidates = [pathlib.Path(explicit)]
    elif len(HERE.parents) > 3:
        candidates = [HERE.parents[3] / name for name in ("vcf-rdfizer", "VCF-RDFizer")]
    else:
        candidates = []
    return next((c for c in candidates if (c / "vcf_rdfizer_policy.py").is_file()), None)


class Genome:
    """A tiny graph in the shape VCF-RDFizer writes for an expanded genome."""

    def __init__(self, participant: str):
        self.file = URIRef(f"file://{participant}.acmg.vcf")
        self.graph = Graph()
        self.graph.add((self.file, RDF.type, VCFC.VCFFile))
        self.graph.add((self.file, VCFC.referenceGenome, Literal(ASSEMBLY)))
        self.rows = 0

    def record(self, chrom, pos, ref, alt, gt="0/1", status=VCFC.FiltersPassed, info=None, sample="S",
               gene=None, decimals=None):
        self.rows += 1
        g, n = self.graph, self.rows
        record, call = URIRef(f"{self.file}#record/{n}"), URIRef(f"{self.file}#call/{n}")
        g.add((self.file, VCFC.hasRecord, record))
        g.add((record, RDF.type, VCFC.VCFRecord))
        for p, v in ((VCFC.chrom, chrom), (VCFC.pos, pos), (VCFC.ref, ref), (VCFC.alt, alt)):
            g.add((record, p, Literal(v)))
        g.add((record, VCFC.hasCall, call))
        g.add((call, RDF.type, VCFC.VariantCall))
        g.add((call, VCFC.filterStatus, status))
        g.add((call, VCFL.sameVariantAs, URIRef(f"{SPDI}{chrom.removeprefix('chr')}:{pos - 1}:{ref}:{alt}")))
        if gene is not None:     # what the ensembl-genes-grch38 linker writes
            g.add((call, VCFL.overlapsGene, URIRef(f"https://identifiers.org/ensembl:{REGIONS[gene]['ensembl_id']}")))
        if gt is not None:
            sample_call, genotype = URIRef(f"{self.file}#sample/{n}/{sample}"), URIRef(f"{self.file}#sample/{n}/{sample}/genotype")
            g.add((call, VCFC.hasSampleCall, sample_call))
            g.add((sample_call, RDF.type, VCFC.SampleCall))
            g.add((sample_call, VCFC.sampleId, Literal(sample)))
            g.add((sample_call, VCFC.hasGenotype, genotype))
            g.add((genotype, VCFC.genotypeString, Literal(gt)))
        for key, value in {**(info or {}), **(decimals or {})}.items():
            item, definition = URIRef(f"{call}/info/{key}"), URIRef(f"{self.file}#header/{key}")
            g.add((call, VCFC.hasInfoValue, item))
            g.add((item, VCFC.declaredBy, definition))
            g.add((definition, VCFC.fieldId, Literal(key)))
            g.add((item, VCFC.fieldValue, Literal(str(value))))
            if key in (decimals or {}):
                g.add((item, VCFC.fieldValueDecimal, Literal(value, datatype=XSD.decimal)))
        return record


def middle(gene: str) -> int:
    return (REGIONS[gene]["start"] + REGIONS[gene]["end"]) // 2


def generate_into(directory: pathlib.Path, case: pathlib.Path = HERE / "use_case.json") -> pathlib.Path:
    """Run generate.py into *directory* and return it (the case dir may be read-only)."""
    subprocess.run([sys.executable, str(HERE / "generate.py"), str(directory), str(case)],
                   check=True, capture_output=True)
    return directory


class GeneratedFilesAreCurrent(unittest.TestCase):
    """policy.ttl and carriers.rq are generated; a stale committed copy is a silent lie.

    Both routes are supposed to read the same definitions. If use_case.json
    changes and only the baseline picks it up, the experiment compares two
    different questions and its agreement means nothing.
    """

    def test_the_committed_copies_match_use_case_json(self):
        for committed, case, names in ((HERE, HERE / "use_case.json", ("policy.ttl", "carriers.rq")),
                                       (HERE / "cohort", HERE / "cohort" / "cohort.json",
                                        ("policy.ttl", "carriers.rq", "rare.rq"))):
            with tempfile.TemporaryDirectory() as work:
                fresh = generate_into(pathlib.Path(work), case)
                self.assertEqual(sorted(p.name for p in fresh.iterdir()), sorted(names))
                for name in names:
                    with self.subTest(file=committed / name):
                        self.assertEqual((fresh / name).read_text(encoding="utf-8"),
                                         (committed / name).read_text(encoding="utf-8"),
                                         f"{name} is stale; re-run generate.py and commit it")

    def test_the_cohort_carries_the_panel_definition(self):
        cohort = json.loads((HERE / "cohort" / "cohort.json").read_text(encoding="utf-8"))
        self.assertEqual(cohort["panel"], CASE["cohort"]["panel_frequencies"])
        self.assertNotIn("panel_frequencies", cohort["cohort"])


class BaselineRules(unittest.TestCase):
    def test_purposes_fall_under_broader_consents_only(self):
        self.assertTrue(B.within("DUO:0000007", "DUO:0000042"))   # DS under GRU
        self.assertTrue(B.within("DUO:0000006", "DUO:0000006"))
        self.assertFalse(B.within("DUO:0000042", "DUO:0000006"))  # GRU is not HMB
        self.assertFalse(B.within("DUO:0000043", "DUO:0000042"))  # CC is outside research

    def test_classification_is_the_first_term(self):
        self.assertEqual(B.classification("Pathogenic|risk_factor"), "Pathogenic")
        self.assertEqual(B.classification("Benign"), "Benign")
        self.assertEqual(B.classification("Conflicting_classifications_of_pathogenicity"),
                         "Conflicting_classifications_of_pathogenicity")

    def test_reportable_is_counted_but_never_filtered_on(self):
        """The question returns every classification; P/LP is reported separately."""
        reportable = CASE["definition"]["reportable_significance"]
        self.assertTrue(B.is_reportable("Pathogenic|risk_factor", reportable))
        self.assertTrue(B.is_reportable("Pathogenic/Likely_pathogenic", reportable))
        self.assertFalse(B.is_reportable("Conflicting_classifications_of_pathogenicity", reportable))
        self.assertFalse(B.is_reportable("risk_factor|Pathogenic", reportable))
        self.assertFalse(B.is_reportable("Benign", reportable))

    def test_genes_come_from_geneinfo_and_the_acmg_list(self):
        self.assertEqual(B.acmg_genes("BRCA1:672|NBR2:10230", {"BRCA1", "TP53"}), ["BRCA1"])
        self.assertEqual(B.acmg_genes(".", {"BRCA1"}), [])

    def test_withdrawal_and_the_cancer_rule(self):
        policy = CASE["policy"]
        cancer = {"participant": "NB72462M", "restricted": True}
        cardio = {"participant": "NB72462M", "restricted": False}
        self.assertTrue(B.released(cancer, "DUO:0000043", policy))
        self.assertFalse(B.released(cancer, "DUO:0000042", policy))
        self.assertTrue(B.released(cardio, "DUO:0000007", policy))
        self.assertFalse(B.released({"participant": "HG004", "restricted": False}, "DUO:0000042", policy))

    def test_the_cancer_rule_is_about_the_record_not_the_gene_label(self):
        """A record is restricted when its REF extent overlaps a cancer-gene span."""
        spans = B.restricted_spans(list(REGIONS.values()), ["BRCA1"])
        start = REGIONS["BRCA1"]["start"]
        self.assertTrue(B.overlaps("chr17", start, "A", spans))
        self.assertTrue(B.overlaps("17", start, "A", spans))            # contig style does not matter
        self.assertTrue(B.overlaps("17", start - 2, "TCA", spans))      # a deletion reaching into the span
        self.assertFalse(B.overlaps("17", start - 2, "TC", spans))      # ends one base short
        self.assertFalse(B.overlaps("14", start, "A", spans))


class RareBaseline(unittest.TestCase):
    def test_rare_is_each_requesters_carriers_below_the_panel_threshold(self):
        cohort = json.loads((HERE / "cohort" / "cohort.json").read_text(encoding="utf-8"))
        participant = cohort["participants"][0]["id"]
        brca1 = middle("BRCA1")
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            (work / "genotypes.tsv").write_text("".join(
                f"{participant}\tchr17\t{pos}\tA\tG\tBenign\tcriteria_provided,_single_submitter\tBRCA1:672\t0/1\n"
                for pos in (brca1, brca1 + 2, brca1 + 4)), encoding="utf-8")
            (work / "panel.tsv").write_text(f"chr17\t{brca1}\tA\tG\t0.000156\n"
                                            f"chr17\t{brca1 + 2}\tA\tG\t0.3\n"
                                            f"chr17\t{brca1 + 4}\tA\tG\t.\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                B.main([str(HERE / "cohort" / "cohort.json"), str(HERE / "acmg_sf_v3.2.genes.txt"),
                        str(work / "genotypes.tsv"), str(work), str(work / "panel.tsv")])
            read = lambda name: list(csv.DictReader((work / name).open(encoding="utf-8"), delimiter="\t"))
            self.assertEqual([int(r["pos"]) for r in read("rare.unrestricted.tsv")], [brca1])
            for name in cohort["policy"]["requesters"]:
                with self.subTest(requester=name):
                    carriers = read(f"carriers.{name}.tsv")
                    self.assertEqual(read(f"rare.{name}.tsv"), [r for r in carriers if int(r["pos"]) == brca1])


class TwoConsentImplementationsAgree(unittest.TestCase):
    """policy.ttl through the plug-in == baseline_carriers.released, everywhere."""

    GENES = ("BRCA1", "MYH7")  # one restricted (cancer), one not

    @classmethod
    def setUpClass(cls):
        cls.tool = tool_checkout()
        if cls.tool is None:
            raise unittest.SkipTest("no VCF-RDFizer checkout; set VCF_RDFIZER_SRC")
        cls.work = pathlib.Path(tempfile.mkdtemp())
        cls.policy = generate_into(cls.work) / "policy.ttl"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def evaluate(self, participant: str, requester: dict) -> set[str]:
        genome = Genome(participant)
        for gene in self.GENES:
            chrom = REGIONS[gene]["chrom"]
            # HG002's file names contigs without "chr"; the rule must still apply.
            genome.record(chrom.removeprefix("chr") if participant == "HG002" else chrom,
                          middle(gene), "A", "G", gene=gene)
        rdf = self.work / f"{participant}.nt"
        genome.graph.serialize(rdf, format="nt", encoding="utf-8")
        out = self.work / f"{participant}-{requester['purpose'].replace(':', '')}"
        subprocess.run([sys.executable, str(self.tool / "vcf_rdfizer_policy.py"), "evaluate",
                        "--rdf", str(rdf), "--policy", str(self.policy),
                        "--assignee", requester["assignee"], "--purpose", requester["purpose"],
                        "-o", str(out)], check=True, capture_output=True, text=True)
        with (out / "decisions.csv").open(encoding="utf-8") as handle:
            released = {int(row["pos"]) for row in csv.DictReader(handle) if row["released"] == "True"}
        return {gene for gene in self.GENES if middle(gene) in released}

    def test_every_requester_and_participant(self):
        outcomes = set()
        for name, requester in CASE["policy"]["requesters"].items():
            for participant in CASE["policy"]["consents"]:
                with self.subTest(requester=name, participant=participant):
                    restricted = set(CASE["policy"]["secondary_findings"]["genes"])
                    expected = {gene for gene in self.GENES if B.released(
                        {"participant": participant, "restricted": gene in restricted},
                        requester["purpose"], CASE["policy"])}
                    self.assertEqual(self.evaluate(participant, requester), expected)
                    outcomes.add(frozenset(expected))
        # Nothing, only the unrestricted gene, and both genes all occur, so the
        # agreement is not the trivial one of two routes that release nothing.
        self.assertEqual(outcomes, {frozenset(), frozenset({"MYH7"}), frozenset(self.GENES)})


class CarriersQuery(unittest.TestCase):
    """carriers.rq's filters, over a genome and a ClinVar graph (rdflib)."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.query = (generate_into(pathlib.Path(cls.temp.name)) / "carriers.rq").read_text(encoding="utf-8")
        cohort = generate_into(pathlib.Path(cls.temp.name) / "cohort", HERE / "cohort" / "cohort.json")
        cls.rare_query = (cohort / "rare.rq").read_text(encoding="utf-8")

    def rows(self, query: str, graphs: list[Genome]) -> set[tuple]:
        graph = Graph()
        for g in graphs:
            graph += g.graph
        return {(str(r.gene), int(r.pos), str(r.gt)) for r in graph.query(query)}

    def answer(self, genome: Genome, clinvar: Genome) -> set[tuple]:
        return self.rows(self.query, [genome, clinvar])

    def clinvar(self, *records) -> Genome:
        clinvar = Genome("clinvar")
        for chrom, pos, ref, alt, clnsig, revstat, geneinfo in records:
            clinvar.record(chrom, pos, ref, alt, gt=None, status=VCFC.FiltersNotApplied,
                           info={"CLNSIG": clnsig, "CLNREVSTAT": revstat, "GENEINFO": geneinfo})
        return clinvar

    def test_the_rules_select_every_classified_carrier(self):
        brca1, myh7, tp53 = middle("BRCA1"), middle("MYH7"), middle("TP53")
        genome = Genome("NB72462M")
        genome.record("chr17", brca1, "A", "G", gt="0/1")                  # pathogenic
        genome.record("chr17", brca1 + 1, "C", "T", gt="0/0")              # not a carrier
        genome.record("chr14", myh7, "G", "A", gt="1/1", status=VCFC.FiltersFailed)  # failed FILTER
        genome.record("chr17", tp53, "T", "C", gt="0|1")                  # weak review status
        genome.record("chr17", brca1 + 2, "G", "C", gt="0/1")              # conflicting: still a carrier
        genome.record("chr14", myh7 + 4, "T", "A", gt="0/1")               # benign: still a carrier
        clinvar = self.clinvar(
            ("17", brca1, "A", "G", "Pathogenic", "criteria_provided,_single_submitter", "BRCA1:672"),
            ("17", brca1 + 1, "C", "T", "Pathogenic", "reviewed_by_expert_panel", "BRCA1:672"),
            ("14", myh7, "G", "A", "Likely_pathogenic", "criteria_provided,_single_submitter", "MYH7:4625"),
            ("17", tp53, "T", "C", "Pathogenic", "no_assertion_criteria_provided", "TP53:7157"),
            ("17", brca1 + 2, "G", "C", "Conflicting_classifications_of_pathogenicity",
             "criteria_provided,_conflicting_classifications", "BRCA1:672"),
            ("14", myh7 + 4, "T", "A", "Benign", "criteria_provided,_multiple_submitters,_no_conflicts", "MYH7:4625"))
        # Carried, classified and at least one star: genotype, FILTER and review
        # status still exclude; the classification itself no longer does.
        self.assertEqual(self.answer(genome, clinvar),
                         {("BRCA1", brca1, "0/1"), ("BRCA1", brca1 + 2, "0/1"), ("MYH7", myh7 + 4, "0/1")})

    def test_contig_names_do_not_have_to_agree(self):
        # The genome says 17 and ClinVar says chr17: the SPDI link still joins them.
        brca1 = middle("BRCA1")
        genome = Genome("HG002")
        genome.record("17", brca1, "A", "G")
        clinvar = self.clinvar(("chr17", brca1, "A", "G", "Benign|risk_factor",
                                "criteria_provided,_single_submitter", "NBR2:10230|BRCA1:672"))
        self.assertEqual(self.answer(genome, clinvar), {("BRCA1", brca1, "0/1")})

    def test_rare_keeps_the_carriers_the_panel_calls_rare(self):
        brca1, myh7 = middle("BRCA1"), middle("MYH7")
        genome = Genome("HG00120")
        for pos in (brca1, brca1 + 2, brca1 + 4):
            genome.record("chr17", pos, "A", "G")
        genome.record("chr14", myh7, "G", "A")
        clinvar = self.clinvar(*[("17", pos, "A", "G", "Benign", "criteria_provided,_single_submitter", "BRCA1:672")
                                 for pos in (brca1, brca1 + 2, brca1 + 4)],
                               ("14", myh7, "G", "A", "Benign", "criteria_provided,_single_submitter", "MYH7:4625"))
        panel = Genome("panel")
        panel.record("chr17", brca1, "A", "G", gt=None, decimals={"AF": "0.000156"})   # rare
        panel.record("chr17", brca1 + 2, "A", "G", gt=None, decimals={"AF": "0.25"})   # common
        panel.record("chr17", brca1 + 4, "A", "G", gt=None, decimals={"AF_EUR": "0.001"})  # another field
        panel.record("chr14", myh7, "G", "A", gt=None, decimals={"AF": "0.01"})       # not below
        self.assertEqual(len(self.answer(genome, clinvar)), 4)
        self.assertEqual(self.rows(self.rare_query, [genome, clinvar, panel]), {("BRCA1", brca1, "0/1")})
        self.assertEqual(self.rows(self.query, [genome, clinvar, panel]), self.answer(genome, clinvar))

    def test_clinvar_is_never_its_own_carrier(self):
        brca1 = middle("BRCA1")
        clinvar = self.clinvar(("17", brca1, "A", "G", "Benign",
                                "criteria_provided,_single_submitter", "BRCA1:672"))
        self.assertEqual(self.answer(Genome("NB72462M"), clinvar), set())


class Comparison(unittest.TestCase):
    def test_a_requester_not_yet_queried_is_not_counted_as_agreeing(self):
        with tempfile.TemporaryDirectory() as work:
            results = pathlib.Path(work)
            header = "participant\tgene\tchrom\tpos\tref\talt\n"
            (results / "baseline").mkdir()
            for name in ["unrestricted", *CASE["policy"]["requesters"]]:
                (results / "baseline" / f"carriers.{name}.tsv").write_text(header, encoding="utf-8")
            (results / "query" / "unrestricted").mkdir(parents=True)
            (results / "query" / "unrestricted" / "carriers.tsv").write_text(
                "file\tsample\tgene\tchrom\tpos\tref\talt\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(C.main([str(results), str(HERE / "use_case.json")]), 0)
                comparison = json.loads((results / "comparison.json").read_text(encoding="utf-8"))
                self.assertEqual(comparison["not_run"], list(CASE["policy"]["requesters"]))
                (results / "query" / "unrestricted" / "carriers.tsv").unlink()
                self.assertEqual(C.main([str(results), str(HERE / "use_case.json")]), 1)  # nothing ran


    def test_rare_lists_are_compared_when_both_routes_wrote_them(self):
        with tempfile.TemporaryDirectory() as work:
            results = pathlib.Path(work)
            (results / "baseline").mkdir()
            (results / "query" / "unrestricted").mkdir(parents=True)
            row = "file://HG002.acmg.vcf\tS\tBRCA1\t17\t43100000\tA\tG\n"
            for query in ("carriers", "rare"):
                (results / "baseline" / f"{query}.unrestricted.tsv").write_text(
                    "participant\tgene\tchrom\tpos\tref\talt\nHG002\tBRCA1\t17\t43100000\tA\tG\n", encoding="utf-8")
                (results / "query" / "unrestricted" / f"{query}.tsv").write_text(
                    "file\tsample\tgene\tchrom\tpos\tref\talt\n" + row, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(C.main([str(results), str(HERE / "use_case.json")]), 0)
                self.assertTrue(json.loads((results / "comparison.json").read_text())["rare"]["unrestricted"]["agree"])
                (results / "query" / "unrestricted" / "rare.tsv").write_text(
                    "file\tsample\tgene\tchrom\tpos\tref\talt\n", encoding="utf-8")
                self.assertEqual(C.main([str(results), str(HERE / "use_case.json")]), 1)

    def test_keys_ignore_contig_prefix_and_read_the_file_iri(self):
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work, "carriers.tsv")
            path.write_text("file\tsample\tgene\tchrom\tpos\tref\talt\n"
                            "file://HG002.acmg.vcf\tS\tBRCA1\t17\t43100000\tA\tG\n", encoding="utf-8")
            self.assertEqual(C.rdf_keys(path), {C.key("HG002", "BRCA1", "chr17", "43100000", "A", "G")})


QLEVER = pathlib.Path("/opt/qlever/bin/qlever-index")


@unittest.skipUnless(QLEVER.is_file(), "QLever not installed; run inside the image")
class RunQueryOnQLever(CarriersQuery):
    """run_query.py answers carriers.rq on QLever exactly as rdflib does.

    The inputs arrive as separate files, one gzipped and one plain, so this also
    checks the FIFO streaming, a named graph per input, and that a query with no
    GRAPH clause sees all of them.
    """

    def rows(self, query: str, graphs: list[Genome]) -> set[tuple]:
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            # The first input gzipped, the rest plain.
            files = [work / (f"graph{n}.nt.gz" if n == 0 else f"graph{n}.nt") for n in range(len(graphs))]
            with gzip.open(files[0], "wb") as handle:
                handle.write(graphs[0].graph.serialize(format="nt", encoding="utf-8"))
            for path, g in zip(files[1:], graphs[1:]):
                g.graph.serialize(path, format="nt", encoding="utf-8")
            path = work / "q.rq"
            path.write_text(query, encoding="utf-8")
            subprocess.run([sys.executable, str(HERE / "run_query.py"), "--query", str(path),
                            "--out", str(work / "out"), "--replicates", "2", "--memory-gb", "1",
                            "--scratch-dir", str(work / "scratch"), *map(str, files)],
                           check=True, capture_output=True)
            timing = json.loads((work / "out" / "timing.json").read_text(encoding="utf-8"))
            self.assertEqual(timing["triples_per_graph"], {f.name: len(g.graph) for f, g in zip(files, graphs)})
            self.assertEqual(len(timing["replicates"]["q"]), 2)
            with (work / "out" / "q.tsv").open(encoding="utf-8") as handle:
                found = list(csv.DictReader(handle, delimiter="\t"))
        answer = {(r["gene"], int(r["pos"]), r["gt"]) for r in found}
        self.assertEqual(answer, super().rows(query, graphs))   # parity with rdflib
        return answer


@unittest.skipUnless(shutil.which("bcftools"), "bcftools not on PATH; run inside the image")
class Derive(unittest.TestCase):
    """derive.sh on a two-contig synthetic reference."""

    def test_normalises_and_keeps_the_source_contig_names(self):
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            # chr1 = ACGT CAG CAG CAG T..., so a CAG deletion left-aligns to POS 4.
            seq = "ACGTCAGCAGCAGTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"
            (work / "ref.fna").write_text(f">chr1\n{seq}\n>chr2\n{'G' * 50}\n", encoding="utf-8")
            (work / "ref.fna.fai").write_text(f"chr1\t50\t6\t50\t51\nchr2\t50\t63\t50\t51\n", encoding="utf-8")
            (work / "regions.bed").write_text("chr1\t0\t50\tGENE\n", encoding="utf-8")
            vcf = ("##fileformat=VCFv4.2\n##reference=file:///lab/hg38.fa\n"
                   "##contig=<ID=1,length=50>\n##contig=<ID=2,length=50>\n"
                   '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
                   "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\n"
                   "1\t10\t.\tGCAG\tG\t.\tPASS\t.\tGT\t0/1\n"       # left-aligns to 4
                   "1\t14\t.\tT\tA,C\t.\tPASS\t.\tGT\t1/2\n"        # splits in two
                   "1\t15\t.\tG\tA\t.\tPASS\t.\tGT\t0/1\n"          # REF mismatch: dropped
                   "2\t5\t.\tG\tT\t.\tPASS\t.\tGT\t0/1\n")          # outside the regions
            (work / "in.vcf").write_text(vcf, encoding="utf-8")
            subprocess.run(["bash", str(HERE / "derive.sh"), str(work / "in.vcf"), "T", str(work / "out"),
                            str(work / "ref.fna"), str(work / "regions.bed")], check=True, capture_output=True)
            text = (work / "out" / "T.acmg.vcf").read_text(encoding="utf-8")
            records = [line.split("\t")[:5] for line in text.splitlines() if not line.startswith("#")]
            self.assertEqual(records, [["1", "4", ".", "TCAG", "T"],
                                       ["1", "14", ".", "T", "A"], ["1", "14", ".", "T", "C"]])
            self.assertIn(f"##reference={ASSEMBLY}\n", text)
            self.assertNotIn("/lab/hg38.fa", text)
            stats = json.loads((work / "out" / "T.derive.json").read_text(encoding="utf-8"))
            self.assertEqual((stats["contig_style"], stats["records_in_regions"], stats["records_out"]), ("plain", 3, 3))
            self.assertFalse(stats["info_dropped"])

    def test_drop_info_keeps_every_record_and_no_info(self):
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            (work / "ref.fna").write_text(">chr1\n" + "A" * 50 + "\n", encoding="utf-8")
            (work / "ref.fna.fai").write_text("chr1\t50\t6\t50\t51\n", encoding="utf-8")
            (work / "regions.bed").write_text("chr1\t0\t50\tGENE\n", encoding="utf-8")
            (work / "in.vcf").write_text(
                "##fileformat=VCFv4.2\n##contig=<ID=chr1,length=50>\n"
                '##INFO=<ID=AF_EUR,Number=A,Type=Float,Description="Panel frequency">\n'
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\n"
                "chr1\t10\t.\tA\tG,T\t.\tPASS\tAF_EUR=0.1,0.2\tGT\t1/2\n", encoding="utf-8")
            subprocess.run(["bash", str(HERE / "derive.sh"), str(work / "in.vcf"), "P", str(work / "out"),
                            str(work / "ref.fna"), str(work / "regions.bed"), "drop-info"], check=True, capture_output=True)
            text = (work / "out" / "P.acmg.vcf").read_text(encoding="utf-8")
            records = [line.split("\t") for line in text.splitlines() if not line.startswith("#")]
            self.assertEqual([r[3:5] + [r[7]] for r in records], [["A", "G", "."], ["A", "T", "."]])
            self.assertNotIn("AF_EUR", text)
            self.assertTrue(json.loads((work / "out" / "P.derive.json").read_text(encoding="utf-8"))["info_dropped"])


@unittest.skipUnless(shutil.which("bcftools"), "bcftools not on PATH; run inside the image")
class DeriveWithoutContigHeaders(unittest.TestCase):
    """ClinVar declares no ##contig lines, and the first run died on it.

    htslib adds contigs to the in-memory header while parsing, which is too
    late for a BCF or an index: both commit the header before the first record.
    The derived file must therefore carry contig declarations of its own,
    in the source's naming style, or the baseline cannot index ClinVar.
    """

    def test_contigs_come_from_the_reference_in_the_sources_naming_style(self):
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            (work / "ref.fna").write_text(">chr1\n" + "A" * 50 + "\n>chrM\n" + "G" * 50 + "\n", encoding="utf-8")
            (work / "ref.fna.fai").write_text("chr1\t50\t6\t50\t51\nchrM\t50\t63\t50\t51\n", encoding="utf-8")
            (work / "regions.bed").write_text("chr1\t0\t50\tGENE\n", encoding="utf-8")
            # No ##contig lines, plain contig names, and a record on a contig
            # the reference does not have -- ClinVar's shape exactly.
            (work / "in.vcf").write_text(
                "##fileformat=VCFv4.2\n##source=ClinVar\n"
                '##INFO=<ID=CLNSIG,Number=.,Type=String,Description="Significance">\n'
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                "1\t10\t12345\tA\tG\t.\t.\tCLNSIG=Pathogenic\n"
                "NT_113889.1\t5\t99\tA\tG\t.\t.\tCLNSIG=Pathogenic\n", encoding="utf-8")
            subprocess.run(["bash", str(HERE / "derive.sh"), str(work / "in.vcf"), "cv", str(work / "out"),
                            str(work / "ref.fna"), str(work / "regions.bed")], check=True, capture_output=True)

            text = (work / "out" / "cv.acmg.vcf").read_text(encoding="utf-8")
            self.assertIn("##contig=<ID=1,length=50>", text)    # plain, as the source writes it
            self.assertIn("##contig=<ID=MT,length=50>", text)   # chrM -> MT, not M
            self.assertNotIn("##contig=<ID=chr1", text)
            records = [line.split("\t")[:5] for line in text.splitlines() if not line.startswith("#")]
            self.assertEqual(records, [["1", "10", "12345", "A", "G"]])  # the off-reference contig is out of regions
            # The baseline annotates against this file, so it has to be indexable.
            self.assertTrue((work / "out" / "cv.acmg.vcf.gz.csi").is_file())
            subprocess.run(["bcftools", "view", "-H", "-r", "1:10", str(work / "out" / "cv.acmg.vcf.gz")],
                           check=True, capture_output=True)


@unittest.skipUnless(shutil.which("bcftools"), "bcftools not on PATH; run inside the image")
class Baseline(unittest.TestCase):
    """baseline.sh end to end, on two genomes with different contig names."""

    HEADER = ("##fileformat=VCFv4.2\n##contig=<ID={c17}>\n##contig=<ID={c14}>\n{info}"
              '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
              "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO{samples}\n")
    CLINVAR_INFO = "".join(f'##INFO=<ID={k},Number=.,Type=String,Description="{k}">\n'
                           for k in ("CLNSIG", "CLNREVSTAT", "GENEINFO"))

    def write(self, directory: pathlib.Path, name: str, text: str) -> None:
        (directory / f"{name}.vcf").write_text(text, encoding="utf-8")
        subprocess.run(["bcftools", "view", "-Oz", "-o", str(directory / f"{name}.acmg.vcf.gz"),
                        str(directory / f"{name}.vcf")], check=True)
        subprocess.run(["bcftools", "index", str(directory / f"{name}.acmg.vcf.gz")], check=True)

    def test_carriers_per_requester(self):
        brca1, myh7 = middle("BRCA1"), middle("MYH7")
        with tempfile.TemporaryDirectory() as work:
            derived, out = pathlib.Path(work, "derived"), pathlib.Path(work, "out")
            derived.mkdir()
            plain = dict(c17="17", c14="14")
            self.write(derived, "clinvar", self.HEADER.format(**plain, info=self.CLINVAR_INFO, samples="") +
                       f"14\t{myh7}\t1\tG\tA\t.\t.\tCLNSIG=Likely_pathogenic;CLNREVSTAT=criteria_provided,_single_submitter;GENEINFO=MYH7:4625\n"
                       f"17\t{brca1}\t2\tA\tG\t.\t.\tCLNSIG=Pathogenic;CLNREVSTAT=criteria_provided,_single_submitter;GENEINFO=BRCA1:672\n"
                       f"17\t{brca1 + 5}\t3\tC\tT\t.\t.\tCLNSIG=Benign;CLNREVSTAT=criteria_provided,_single_submitter;GENEINFO=BRCA1:672\n")
            self.write(derived, "NB72462M", self.HEADER.format(c17="chr17", c14="chr14", info="", samples="\tFORMAT\tS") +
                       f"chr14\t{myh7}\t.\tG\tA\t.\tPASS\t.\tGT\t1/1\n"
                       f"chr14\t{myh7 + 3}\t.\tT\tC\t.\tPASS\t.\tGT\t0/1\n"     # not in ClinVar
                       f"chr17\t{brca1}\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"
                       f"chr17\t{brca1 + 5}\t.\tC\tT\t.\tPASS\t.\tGT\t0/1\n")   # benign
            self.write(derived, "HG002", self.HEADER.format(**plain, info="", samples="\tFORMAT\tS") +
                       f"14\t{myh7}\t.\tG\tA\t.\t.\t.\tGT\t0/1\n"               # FILTER missing: kept
                       f"17\t{brca1}\t.\tA\tC\t.\t.\t.\tGT\t0/1\n")             # other ALT: no match
            subprocess.run(["bash", str(HERE / "baseline.sh"), str(derived), str(out), str(HERE / "use_case.json"),
                            "NB72462M", "HG002"], check=True, capture_output=True)

            def carriers(name):
                with (out / f"carriers.{name}.tsv").open(encoding="utf-8") as handle:
                    return {(r["participant"], r["gene"]) for r in csv.DictReader(handle, delimiter="\t")}
            # BRCA1 is a cancer-predisposition gene, so only the clinical
            # requester sees it; MYH7 is not, so consent alone decides.
            self.assertEqual(carriers("unrestricted"), {("NB72462M", "BRCA1"), ("NB72462M", "MYH7"), ("HG002", "MYH7")})
            self.assertEqual(carriers("clinical"), {("NB72462M", "BRCA1"), ("NB72462M", "MYH7")})
            self.assertEqual(carriers("cardio"), {("NB72462M", "MYH7"), ("HG002", "MYH7")})
            self.assertEqual(carriers("biobank"), {("NB72462M", "MYH7"), ("HG002", "MYH7")})

    def test_reportable_is_counted_separately(self):
        """The summary must say how many carriers are ACMG-reportable, even when none are."""
        brca1 = middle("BRCA1")
        with tempfile.TemporaryDirectory() as work:
            derived, out = pathlib.Path(work, "derived"), pathlib.Path(work, "out")
            derived.mkdir()
            self.write(derived, "clinvar", self.HEADER.format(c17="17", c14="14", info=self.CLINVAR_INFO, samples="") +
                       f"17\t{brca1}\t1\tA\tG\t.\t.\tCLNSIG=Benign;CLNREVSTAT=criteria_provided,_single_submitter;GENEINFO=BRCA1:672\n")
            self.write(derived, "NB72462M", self.HEADER.format(c17="17", c14="14", info="", samples="\tFORMAT\tS") +
                       f"17\t{brca1}\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n")
            subprocess.run(["bash", str(HERE / "baseline.sh"), str(derived), str(out),
                            str(HERE / "use_case.json"), "NB72462M"], check=True, capture_output=True)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["unrestricted"], 1)
            self.assertEqual(summary["reportable"]["total"], 0)
            self.assertEqual(summary["classifications"], {"Benign": 1})


@unittest.skipUnless(shutil.which("bcftools"), "bcftools not on PATH; run inside the image")
class BaselineContigRenamingAtScale(Baseline):
    """A chr-style genome must still match ClinVar once it is big enough to matter.

    The first run matched nothing for the four chr-style genomes. The style
    test was `bcftools view -H "$genome" | head -1 | ...` inside an `if`:
    head closes the pipe, bcftools dies of SIGPIPE with status 141, and
    pipefail hands that status to the condition, so the rename never ran. Four-
    record fixtures fit the 64 KiB pipe buffer and never reproduced it, so this
    test pads the genome past the buffer -- the bug is a function of size.
    """

    PADDING = 3000

    def test_carriers_per_requester(self):
        brca1, myh7 = middle("BRCA1"), middle("MYH7")
        with tempfile.TemporaryDirectory() as work:
            derived, out = pathlib.Path(work, "derived"), pathlib.Path(work, "out")
            derived.mkdir()
            self.write(derived, "clinvar",
                       self.HEADER.format(c17="17", c14="14", info=self.CLINVAR_INFO, samples="") +
                       f"17\t{brca1}\t1\tA\tG\t.\t.\tCLNSIG=Pathogenic;CLNREVSTAT=criteria_provided,_single_submitter;GENEINFO=BRCA1:672\n")
            # One reportable variant, then enough benign padding to fill the pipe.
            padding = "".join(
                f"chr14\t{myh7 + 10 + i}\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"
                for i in range(self.PADDING))
            self.write(derived, "NB72462M",
                       self.HEADER.format(c17="chr17", c14="chr14", info="", samples="\tFORMAT\tS") +
                       f"chr17\t{brca1}\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n" + padding)
            self.assertGreater((derived / "NB72462M.vcf").stat().st_size, 64 * 1024,
                               "the fixture must exceed the pipe buffer or it cannot reproduce the bug")
            subprocess.run(["bash", str(HERE / "baseline.sh"), str(derived), str(out),
                            str(HERE / "use_case.json"), "NB72462M"], check=True, capture_output=True)
            with (out / "carriers.unrestricted.tsv").open(encoding="utf-8") as handle:
                found = {(r["participant"], r["gene"]) for r in csv.DictReader(handle, delimiter="\t")}
            self.assertEqual(found, {("NB72462M", "BRCA1")})


class MakeCohort(unittest.TestCase):
    """Arm 2's selection: unrelated samples only, stratified, reproducible from the seed."""

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        work = pathlib.Path(self.work.name)
        (work / "ped.txt").write_text("FamilyID SampleID FatherID MotherID Sex Population Superpopulation\n" + "".join(
            f"F{p}{n} {p}{n} 0 0 1 {p} X\n" for p in ("AAA", "BBB") for n in range(5)), encoding="utf-8")
        # AAA4 and BBB4 are the related ones: absent from the unrelated index.
        (work / "index.tsv").write_text("##header\n#SAMPLE_NAME\tPOPULATION\n" + "".join(
            f"{p}{n}\t{p}\n" for p in ("AAA", "BBB") for n in range(4)), encoding="utf-8")
        self.pools = M.populations(work / "ped.txt", M.unrelated(work / "index.tsv"))

    def test_only_unrelated_samples_are_eligible(self):
        self.assertEqual(self.pools, {"AAA": ["AAA0", "AAA1", "AAA2", "AAA3"], "BBB": ["BBB0", "BBB1", "BBB2", "BBB3"]})

    def test_selection_is_stratified_and_reproducible(self):
        first = M.select(self.pools, 2, random.Random(7))
        self.assertEqual(first, M.select(self.pools, 2, random.Random(7)))
        self.assertEqual(collections.Counter(p for _, p in first), {"AAA": 2, "BBB": 2})

    def test_consents_come_from_the_mix_and_withdrawal_is_drawn(self):
        cohort = {"consent_mix": [{"permits": ["DUO:0000042"], "weight": 1}], "withdrawal_percent": 100}
        drawn = M.consents(M.select(self.pools, 2, random.Random(7)), cohort, random.Random(7))
        self.assertEqual(len(drawn), 4)
        self.assertTrue(all(c == {"permits": ["DUO:0000042"], "withdrawn": True} for c in drawn.values()))

    def test_the_committed_cohort_matches_its_definition(self):
        cohort = json.loads((HERE / "cohort" / "cohort.json").read_text(encoding="utf-8"))
        per_population = CASE["cohort"]["per_population"]
        self.assertEqual(len(cohort["participants"]), 26 * per_population)
        self.assertEqual(set(cohort["policy"]["consents"]), {p["id"] for p in cohort["participants"]})
        self.assertEqual(cohort["definition"], CASE["definition"])     # the same question as arm 1


@unittest.skipUnless(shutil.which("bcftools"), "bcftools not on PATH; run inside the image")
class FetchCohort(unittest.TestCase):
    """fetch_cohort.sh on a local two-chromosome panel standing in for the remote one."""

    def test_regions_samples_and_one_file_per_participant(self):
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            header = ("##fileformat=VCFv4.2\n##contig=<ID=chr14>\n##contig=<ID=chr17>\n"
                      '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
                      "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tA\tB\tC\n")
            rows = {"chr17": ["chr17\t100\t.\tA\tG,T\t.\tPASS\t.\tGT\t0|1\t0|0\t2|2",   # A has G only
                              "chr17\t150\t.\tC\tT\t.\tPASS\t.\tGT\t0|0\t1|1\t0|0",     # only B
                              "chr17\t900\t.\tC\tT\t.\tPASS\t.\tGT\t1|1\t1|1\t1|1"],    # outside the regions
                    "chr14": ["chr14\t50\t.\tG\tA\t.\tPASS\t.\tGT\t1|0\t0|0\t0|0"]}
            # chr14's file breaks the naming pattern, as chrX's does on the real panel.
            names = {"chr17": "chr17.vcf.gz", "chr14": "chr14.v2.vcf.gz"}
            for chrom, lines in rows.items():
                (work / f"{chrom}.vcf").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
                subprocess.run(["bcftools", "view", "-Oz", "-o", str(work / names[chrom]),
                                str(work / f"{chrom}.vcf")], check=True)
                subprocess.run(["bcftools", "index", "-t", str(work / names[chrom])], check=True)
            (work / "regions.bed").write_text("chr14\t0\t100\tG1\nchr17\t50\t200\tG2\n", encoding="utf-8")
            case = {"participants": [{"id": "A"}, {"id": "B"}],
                    "cohort": {"source": {"panel": str(work / "{chrom}.vcf.gz"),
                                          "panel_overrides": {"chr14": str(work / "chr14.v2.vcf.gz")}}}}
            (work / "cohort.json").write_text(json.dumps(case), encoding="utf-8")
            out = work / "out"
            run = ["bash", str(HERE / "fetch_cohort.sh"), str(work / "cohort.json"), str(work / "regions.bed"), str(out)]
            subprocess.run(run, check=True, capture_output=True)

            def records(sample):
                text = subprocess.run(["bcftools", "view", "-H", str(out / f"{sample}.vcf.gz")],
                                      check=True, capture_output=True, text=True).stdout
                return [line.split("\t")[:5] + [line.split("\t")[-1]] for line in text.splitlines()]
            self.assertEqual(records("A"), [["chr14", "50", ".", "G", "A", "1|0"], ["chr17", "100", ".", "A", "G", "0|1"]])
            self.assertEqual(records("B"), [["chr17", "150", ".", "C", "T", "1|1"]])
            before = (out / "A.vcf.gz").stat().st_mtime_ns
            subprocess.run(run, check=True, capture_output=True)        # resumable: nothing redone
            self.assertEqual((out / "A.vcf.gz").stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
