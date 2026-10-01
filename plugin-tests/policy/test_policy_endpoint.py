"""vcf-rdfizer-policy against a SPARQL endpoint (QLever), kept apart from its code.

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 plugin-tests/policy/test_policy_endpoint.py

Run inside the VCF-RDFizer image, which has QLever; the endpoint tests skip
without it. What they pin:
  * parameters reach an endpoint as inline VALUES; the trailing form fails open;
  * the streaming executor (endpoint + one pass over the files) releases exactly
    what the in-memory one does, for every requester and both sample profiles;
  * check_stream passes a correct view and catches a leak, an uncovered triple,
    a dangling reference and an over-withheld record, the last two by asking an
    endpoint serving the view -- and refuses an endpoint serving another view;
  * LinkedSelector selects by link, and refuses a graph that lacks its links.
"""

import contextlib
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_policy import EXAMPLE, FIXTURE, POLICY, VCFS, request, setup, write  # noqa: E402

import rdflib  # noqa: E402

from vcf_rdfizer_policies import PolicyError  # noqa: E402
from vcf_rdfizer_policies.check import check_stream  # noqa: E402
from vcf_rdfizer_policies.engine import check_preconditions, select  # noqa: E402
from vcf_rdfizer_policies.graphs import load  # noqa: E402
from vcf_rdfizer_policies.policy import policy_digest  # noqa: E402
from vcf_rdfizer_policies.release import evaluate, evaluate_stream, write_release  # noqa: E402
from vcf_rdfizer_policies.store import EndpointStore, MemoryStore, iri, with_parameters  # noqa: E402
from vcf_rdfizer_policies.vcf_oracle import graph_from_vcfs, write_ntriples  # noqa: E402

QLEVER = Path(os.environ.get("QLEVER_INDEX_BUILDER_BIN", "/opt/qlever/bin/qlever-index"))
VCFC = "https://w3id.org/vcf-core/vocab#"
VCFL = "https://w3id.org/vcf-rdfizer/linking#"


@contextlib.contextmanager
def qlever(files):
    """A QLever endpoint over N-Triples `files` (plain or gzipped) for the duration of a block."""
    env = dict(os.environ, LD_LIBRARY_PATH="/opt/qlever/lib")
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        inputs = []
        for number, path in enumerate(files):
            plain = work / f"in{number}.nt"
            with (gzip.open(path, "rb") if str(path).endswith(".gz") else open(path, "rb")) as src:
                plain.write_bytes(src.read())
            inputs += ["-f", str(plain), "-F", "nt"]
        subprocess.run([str(QLEVER), "-i", str(work / "idx"), "-m", "1G", *inputs],
                       check=True, capture_output=True, env=env, cwd=work)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        server = subprocess.Popen([str(QLEVER.with_name("qlever-server")), "-i", str(work / "idx"),
                                   "-p", str(port), "-m", "1G"], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, env=env, cwd=work)
        url = f"http://127.0.0.1:{port}/"
        try:
            for _ in range(60):
                with contextlib.suppress(OSError):
                    urllib.request.urlopen(url + "?query=ASK%7B%7D", timeout=2).read()
                    break
                time.sleep(0.5)
            yield url
        finally:
            server.kill()
            server.wait()


def triples(path):
    """The triples of an N-Triples file (plain or gzipped), as a set."""
    data = gzip.open(path, "rb").read() if str(path).endswith(".gz") else Path(path).read_bytes()
    return set(rdflib.Graph().parse(data=data, format="nt"))


class ParameterInjection(unittest.TestCase):
    def test_parameters_open_the_outer_where_group(self):
        query = "SELECT ?resource WHERE { ?resource ?p ?o FILTER(?o = ?x) }"
        injected = with_parameters(query, (("x", rdflib.Literal(1)),
                                           ("set", (rdflib.URIRef("urn:a"), rdflib.URIRef("urn:b")))))
        self.assertTrue(injected.startswith(
            'SELECT ?resource WHERE { VALUES ?x { "1"^^<http://www.w3.org/2001/XMLSchema#integer> } '
            "VALUES ?set { <urn:a> <urn:b> }"))
        self.assertEqual(with_parameters(query, ()), query)

    def test_a_query_without_an_explicit_where_is_refused(self):
        with self.assertRaises(PolicyError):
            with_parameters("SELECT ?resource { ?resource ?p ?o }", (("x", rdflib.Literal(1)),))

    def test_unsafe_iris_are_refused(self):
        with self.assertRaises(PolicyError):
            iri("urn:a> } DELETE {")


@unittest.skipUnless(QLEVER.is_file(), "QLever is not installed; run inside the image")
class OnQLever(unittest.TestCase):
    """The streaming executor and check, against QLever serving the example cohort."""

    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp())
        cls.policy_graph, cls.profile, cls.vocabulary, cls.rules = setup(POLICY)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def release_pair(self, kind, key, url, files, name=None):
        """(in-memory release dir, streamed release dir) for one requester."""
        name = name or f"{kind}-{key}"
        req = request(key, self.vocabulary)
        written = {"policies": {r.policy for r in self.rules}, "digest": policy_digest(POLICY)}
        memory = self.work / f"{name}-memory"
        write_release(evaluate(load(files), self.rules, req, self.profile, self.vocabulary), memory, **written)
        streamed = self.work / f"{name}-stream"
        evaluate_stream(EndpointStore(url), files, self.rules, req, self.profile, self.vocabulary,
                        streamed, **written)
        return memory, streamed

    def check(self, view_dir, url, oracle=True, view=None):
        """check_stream with the view served on its own endpoint (by default, this view)."""
        view = Path(view or view_dir / "view.nt.gz")
        with contextlib.ExitStack() as stack:
            empty = not gzip.open(view, "rb").read(1)   # no endpoint can index an empty view
            view_store = None if empty else EndpointStore(stack.enter_context(qlever([view])))
            return check_stream(view_dir, policy_path=POLICY, rules=self.rules, profile=self.profile,
                                vocabulary=self.vocabulary, store=EndpointStore(url), view_store=view_store,
                                oracle=MemoryStore(graph_from_vcfs(VCFS)) if oracle else None)

    def test_region_parameters_select_on_an_endpoint_and_the_trailing_form_fails_open(self):
        region = self.profile.selectors["https://w3id.org/vcf-rdfizer/policy#RegionSelector"]
        bindings = (("assembly", rdflib.Literal(FIXTURE["assembly"])), ("chrom", rdflib.Literal("chr17")),
                    ("start", rdflib.Literal(43044295)), ("end", rdflib.Literal(43125483)))
        files = sorted((EXAMPLE / "converted" / "expanded").glob("*.nt.gz"))
        with qlever(files) as url:
            store = EndpointStore(url)
            inline = {r["resource"] for r in store.rows(with_parameters(region.query, bindings))}
            trailing = list(store.rows(region.query + " VALUES (?chrom ?start ?end) "
                                       '{ ("chr17" 43044295 43125483) }'))
        self.assertTrue(inline)                   # BRCA1 records exist in the cohort
        self.assertEqual(trailing, [])            # what a trailing VALUES would have released

    def test_streaming_releases_exactly_what_memory_does(self):
        for kind in ("expanded", "condensed"):
            files = sorted((EXAMPLE / "converted" / kind).glob("*.nt.gz"))
            with qlever(files) as url:
                for key in FIXTURE["requesters"]:
                    with self.subTest(profile=kind, requester=key):
                        memory, streamed = self.release_pair(kind, key, url, files)
                        self.assertEqual(triples(streamed / "view.nt.gz"), triples(memory / "view.nt"))
                        self.assertEqual((streamed / "decisions.csv").read_text(),
                                         (memory / "decisions.csv").read_text())
                        self.assertEqual(json.loads((streamed / "summary.json").read_text()),
                                         json.loads((memory / "summary.json").read_text()))
                        self.assertEqual(self.check(streamed, url), [])

    def test_check_stream_catches_each_kind_of_bad_view(self):
        files = sorted((EXAMPLE / "converted" / "expanded").glob("*.nt.gz"))
        source = [line for path in files for line in gzip.open(path, "rt", encoding="utf-8")]
        with qlever(files) as url:
            _, good = self.release_pair("expanded", "gru", url, files, name="mutants")
            kept = gzip.open(good / "view.nt.gz", "rt", encoding="utf-8").read().splitlines(keepends=True)

            def mutant(name, lines):
                bad = self.work / name
                shutil.copytree(good, bad)
                with gzip.open(bad / "view.nt.gz", "wt", encoding="utf-8") as out:
                    out.writelines(lines)
                return self.check(bad, url)

            withdrawn = [line for line in source if line.startswith("<file://P004.vcf#record/1>")]
            health_only = [line for line in source if line.startswith("<file://P003.vcf#record/1>")]
            # P004 is covered by its consent but withdrew: prohibited content. P003
            # consented to health research only, which general research is not.
            self.assertTrue(any("prohibited content present" in f for f in mutant("withdrawn", kept + withdrawn)))
            self.assertTrue(any("no permission covers" in f for f in mutant("uncovered", kept + health_only)))
            self.assertTrue(any(f.startswith("leak:") for f in mutant("leak-oracle", kept + withdrawn)))

            allele = next(line.split(">")[0][1:] for line in kept if "/allele/" in line.split(" ")[0])
            no_allele = [line for line in kept if not line.startswith(f"<{allele}>")]
            self.assertTrue(any("dangling" in f for f in mutant("dangling", no_allele)))

            other = self.work / "other.nt.gz"                  # an endpoint serving some other view
            with gzip.open(other, "wt", encoding="utf-8") as out:
                out.writelines(kept[: len(kept) // 2])
            self.assertTrue(any("the view endpoint serves" in f for f in self.check(good, url, view=other)))
            with self.assertRaisesRegex(PolicyError, "needs an endpoint serving it"):
                check_stream(good, policy_path=POLICY, rules=self.rules, profile=self.profile,
                             vocabulary=self.vocabulary, store=EndpointStore(url))
            empty = self.work / "empty"                      # nothing released: nothing to serve
            shutil.copytree(good, empty)
            with gzip.open(empty / "view.nt.gz", "wt", encoding="utf-8"):
                pass
            self.assertEqual(self.check(empty, url, oracle=False), [])

            record = next(line.split(">")[0][1:] for line in kept if line.split(" ")[0].endswith("#record/1>"))
            no_record = [line for line in kept if not line.startswith(f"<{record}")]
            self.assertTrue(any(f.startswith("over-withheld:") for f in mutant("over", no_record)))

    def test_the_oracle_can_be_served_too(self):
        with tempfile.TemporaryDirectory() as work:
            oracle_nt = Path(work) / "oracle.nt"
            with oracle_nt.open("w", encoding="utf-8") as out:
                write_ntriples(VCFS, out)
            self.assertEqual(triples(oracle_nt), set(graph_from_vcfs(VCFS)))
            files = sorted((EXAMPLE / "converted" / "expanded").glob("*.nt.gz"))
            with qlever(files) as url, qlever([oracle_nt]) as oracle_url:
                _, streamed = self.release_pair("expanded", "clinical", url, files, name="served-oracle")
                with qlever([streamed / "view.nt.gz"]) as view_url:
                    failures = check_stream(streamed, policy_path=POLICY, rules=self.rules, profile=self.profile,
                                            vocabulary=self.vocabulary, store=EndpointStore(url),
                                            view_store=EndpointStore(view_url), oracle=EndpointStore(oracle_url))
        self.assertEqual(failures, [])


class LinkedSelectorTests(unittest.TestCase):
    """Records selected by what their calls link to; refused when the links are absent."""

    GRAPH = f"""
<file://A.vcf#record/1> a <{VCFC}VCFRecord> ; <{VCFC}hasCall> <file://A.vcf#call/1> .
<file://A.vcf#record/2> a <{VCFC}VCFRecord> ; <{VCFC}hasCall> <file://A.vcf#call/2> .
<file://A.vcf#call/1> <{VCFL}overlapsGene> <https://identifiers.org/ensembl:ENSG1> .
<file://A.vcf#call/2> <{VCFL}overlapsGene> <https://identifiers.org/ensembl:ENSG2> ."""

    def rules(self, directory):
        path = write(directory, "panel.ttl", """@prefix vcfl: <https://w3id.org/vcf-rdfizer/linking#> .
ex:panel a odrl:Asset , vcfp:GraphSelection ;
    vcfp:selector [ a vcfp:LinkedSelector ; vcfp:predicate vcfl:overlapsGene ;
                    vcfp:entities ( <https://identifiers.org/ensembl:ENSG1> <https://identifiers.org/ensembl:ENSG9> ) ] .
ex:p a odrl:Set ; odrl:conflict odrl:prohibit ;
    odrl:prohibition [ odrl:target ex:panel ; odrl:action odrl:read ] .
""")
        return setup(path)[3]

    def test_it_selects_the_records_whose_calls_link_to_the_panel(self):
        with tempfile.TemporaryDirectory() as work:
            rule = self.rules(work)[0]
            graph = rdflib.Graph().parse(data=self.GRAPH, format="turtle")
            self.assertEqual(select(graph, rule.target), {"file://A.vcf#record/1"})
            check_preconditions(graph, [rule])     # links present: no violation

    def test_a_graph_without_the_links_is_refused(self):
        with tempfile.TemporaryDirectory() as work:
            rules = self.rules(work)
            bare = rdflib.Graph().parse(data=self.GRAPH.split("\n<file://A.vcf#call/1>")[0], format="turtle")
            with self.assertRaisesRegex(PolicyError, "cannot be applied"):
                check_preconditions(bare, rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
