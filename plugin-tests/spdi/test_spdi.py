"""Tests for VCF-RDFizer's spdi linker, on real ClinVar variants, kept apart from its code.

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 plugin-tests/spdi/test_spdi.py

Needs a VCF-RDFizer checkout that ships the spdi linker, and rdflib. Offline:
NCBI's answers are recorded in ncbi_contextuals.json (see its "source").

The framework's own tests (trimming rules, manifest validation, the sequence
map) are in VCF-RDFizer's test/test_linking_unit.py. These answer a different
question: does the shipped linker give real variants the identifier NCBI
would, and does it give the same variant the same IRI across files?

  * Outside repeats, the IRI's SPDI is NCBI's, character for character.
  * Inside a repeat, NCBI writes the contextual form (the whole repeat) and the
    linker writes the trimmed one. The strings differ -- that is documented,
    and pinned here so the docs cannot silently go stale -- but applying the
    linker's edit to NCBI's reference window must give NCBI's allele: both
    expressions denote the same variant.
  * Two files that name the chromosome differently still share the IRI.
"""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [os.environ.get("VCF_RDFIZER_SRC")] + [
        str(here.parents[3] / name) for name in ("VCF-RDFizer", "vcf-rdfizer") if len(here.parents) > 3]
    for candidate in filter(None, candidates):
        if (Path(candidate) / "vcf_rdfizer_data" / "linkers" / "spdi").is_dir():
            return Path(candidate)
    raise SystemExit("set VCF_RDFIZER_SRC to a VCF-RDFizer checkout that ships the spdi linker")


TOOL = _tool_root()
sys.path.insert(0, str(TOOL))

from rdflib import Graph, URIRef  # noqa: E402

from vcf_rdfizer_linking.inputs import read_vcf  # noqa: E402
from vcf_rdfizer_linking.manifest import VCFL, discover  # noqa: E402
from vcf_rdfizer_linking.runner import run_linkers  # noqa: E402

FIXTURE = json.loads((Path(__file__).with_name("ncbi_contextuals.json")).read_text(encoding="utf-8"))
CASES = FIXTURE["cases"]
SPDI = "https://api.ncbi.nlm.nih.gov/variation/v0/spdi/"
#: Variant classes whose allele sits in a repeat, where NCBI's contextual form
#: spans the repeat and the linker's trimmed form does not.
IN_A_REPEAT = {266565, 55628, 418073}


def parse(spdi: str) -> tuple[str, int, str, str]:
    sequence, position, deleted, inserted = spdi.split(":")
    return sequence, int(position), deleted, inserted


def vcf(chrom_name: str) -> str:
    lines = ["##fileformat=VCFv4.2", "##reference=GRCh38", "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"]
    lines += [f"{chrom_name}\t{c['vcf']['pos']}\t{c['clinvar_variation']}\t{c['vcf']['ref']}\t{c['vcf']['alt']}\t.\t.\t."
              for c in CASES]
    return "\n".join(lines) + "\n"


class SpdiOnClinVar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        root = Path(cls.work.name)
        cls.spdi = discover()["spdi"]
        cls.links = {}
        for name in ("17", "chr17"):
            path = root / f"clinvar-{name}.vcf"
            path.write_text(vcf(name), encoding="utf-8")
            output = root / f"{name}.links.nt"
            run_linkers(read_vcf(path), [cls.spdi], output, cache_dir=root / "cache", offline=True)
            graph = Graph().parse(output, format="nt")
            cls.links[name] = {
                row: str(graph.value(URIRef(f"file://{path.name}#call/{row}"), VCFL.sameVariantAs))
                for row in range(1, len(CASES) + 1)}

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def linked(self, row: int) -> str:
        iri = self.links["17"][row]
        self.assertTrue(iri.startswith(SPDI), iri)
        return iri[len(SPDI):]

    def test_outside_repeats_the_identifier_is_ncbis(self):
        for row, case in enumerate(CASES, start=1):
            if case["clinvar_variation"] in IN_A_REPEAT:
                continue
            with self.subTest(clinvar=case["clinvar_variation"], kind=case["clinvar_class"]):
                self.assertEqual(self.linked(row), case["ncbi_contextual"])

    def test_inside_repeats_the_strings_differ_as_documented(self):
        for row, case in enumerate(CASES, start=1):
            if case["clinvar_variation"] in IN_A_REPEAT:
                with self.subTest(clinvar=case["clinvar_variation"], kind=case["clinvar_class"]):
                    self.assertNotEqual(self.linked(row), case["ncbi_contextual"])

    def test_every_identifier_denotes_ncbis_allele(self):
        """Apply the linker's edit to NCBI's reference window: it must give NCBI's allele."""
        for row, case in enumerate(CASES, start=1):
            with self.subTest(clinvar=case["clinvar_variation"], kind=case["clinvar_class"]):
                sequence, position, deleted, inserted = parse(self.linked(row))
                context_sequence, start, window, allele = parse(case["ncbi_contextual"])
                self.assertEqual(sequence, context_sequence)
                offset = position - start
                self.assertTrue(0 <= offset and offset + len(deleted) <= len(window),
                                "the trimmed allele lies inside NCBI's window")
                self.assertEqual(window[offset:offset + len(deleted)], deleted)
                self.assertEqual(window[:offset] + inserted + window[offset + len(deleted):], allele)

    def test_the_contig_name_does_not_change_the_identifier(self):
        self.assertEqual(self.links["17"], self.links["chr17"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
