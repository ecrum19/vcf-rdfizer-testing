"""Tests for VCF-RDFizer's ensembl-genes-grch38 linker on real loci, kept apart from its code.

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 plugin-tests/genes/test_genes.py

Needs the Ensembl 116 GFF3 in the linker cache (fetched once by the linker, or
seeded there by digest); skips without it, and never downloads. The expected
genes come from an independent scan of that GFF3's `gene` features, so the test
pins the linker to Ensembl's own coordinates: at BRCA1's first base, which a
second protein-coding gene also covers, one base before it, in its middle and
at its last base, under both contig styles.
"""

import gzip
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
        if (Path(candidate) / "vcf_rdfizer_data" / "linkers" / "ensembl-genes-grch38").is_dir():
            return Path(candidate)
    raise SystemExit("set VCF_RDFIZER_SRC to a VCF-RDFizer checkout that ships ensembl-genes-grch38")


sys.path.insert(0, str(_tool_root()))

from rdflib import Graph, URIRef  # noqa: E402

from vcf_rdfizer_linking.inputs import read_vcf  # noqa: E402
from vcf_rdfizer_linking.manifest import VCFL, discover  # noqa: E402
from vcf_rdfizer_linking.reference import DEFAULT_CACHE  # noqa: E402
from vcf_rdfizer_linking.runner import run_linkers  # noqa: E402

MANIFEST = discover()["ensembl-genes-grch38"]
CACHED = DEFAULT_CACHE / "references" / MANIFEST.reference.sha256


def gene_features():
    """[(seqid, start, end, gene_id)] of every `gene` feature, read straight from the cached GFF3."""
    found = []
    with gzip.open(CACHED, "rt", encoding="utf-8") as handle:
        for line in handle:
            columns = line.split("\t")
            if len(columns) == 9 and columns[2] == "gene":
                attributes = dict(a.split("=", 1) for a in columns[8].strip().split(";") if "=" in a)
                found.append((columns[0], int(columns[3]), int(columns[4]), attributes["gene_id"]))
    return found


@unittest.skipUnless(CACHED.is_file(), "the Ensembl 116 GFF3 is not in the linker cache")
class GenesOnRealLoci(unittest.TestCase):
    BRCA1 = "ENSG00000012048"

    @classmethod
    def setUpClass(cls):
        cls.features = gene_features()
        cls.brca1 = next(f for f in cls.features if f[3] == cls.BRCA1)

    def expected(self, pos):
        return {gene for seqid, start, end, gene in self.features if seqid == "17" and start <= pos <= end}

    def link(self, rows):
        with tempfile.TemporaryDirectory() as work:
            vcf = Path(work) / "real.vcf"
            vcf.write_text("##fileformat=VCFv4.2\n##reference=GRCh38\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                           + "".join(f"{c}\t{p}\t.\tA\tG\t.\t.\t.\n" for c, p in rows), encoding="utf-8")
            output = Path(work) / "real.links.nt"
            run_linkers(read_vcf(vcf), [MANIFEST], output, offline=True)
            graph = Graph().parse(output, format="nt")
            return [{str(o).rsplit(":", 1)[1] for o in graph.objects(URIRef(f"file://real.vcf#call/{n}"),
                                                                        VCFL.overlapsGene)}
                    for n in range(1, len(rows) + 1)]

    def test_links_match_the_gff3_under_both_contig_styles(self):
        seqid, start, end, _ = self.brca1
        self.assertEqual(seqid, "17")
        positions = [start - 1, start, (start + end) // 2, end]
        expected = [self.expected(p) for p in positions]
        self.assertNotIn(self.BRCA1, expected[0])
        self.assertTrue(all(self.BRCA1 in e for e in expected[1:]))
        for style in ("chr17", "17"):
            with self.subTest(contig=style):
                self.assertEqual(self.link([(style, p) for p in positions]), expected)

    def test_a_position_inside_two_genes_links_to_both(self):
        start = self.brca1[1]
        both = self.expected(start)
        self.assertGreaterEqual(len(both), 2, "BRCA1's first base lies inside a second gene in Ensembl 116")
        self.assertEqual(self.link([("chr17", start)]), [both])


if __name__ == "__main__":
    unittest.main(verbosity=2)
