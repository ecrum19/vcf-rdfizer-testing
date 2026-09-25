"""Tests for VCF-RDFizer's policy plug-in (vcf-rdfizer-policy), kept apart from its code.

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 plugin-tests/policy/test_policy.py

The plug-in lives in VCF-RDFizer; these tests live here so the plug-in's logic
and its verification are maintained separately. They need a VCF-RDFizer source
checkout (for the package and examples/policy/) and rdflib. Without
VCF_RDFIZER_SRC they look for a sibling checkout named VCF-RDFizer or vcf-rdfizer.

What they pin:
  * the engine's three steps -- select, partition, decide -- on the example cohort,
    cell by cell against docs/policy-demonstrator.md §5;
  * that it is general: a selector type declared in Turtle, a non-VCF graph
    partitioned by a property path, and a SKOS purpose vocabulary, with no code;
  * that `check` catches every way a view can go wrong (the mutation tests).
"""

import contextlib
import filecmp
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [os.environ.get("VCF_RDFIZER_SRC")] + [
        str(here.parents[3] / name) for name in ("VCF-RDFizer", "vcf-rdfizer")]
    for candidate in filter(None, candidates):
        if (Path(candidate) / "vcf_rdfizer_policies").is_dir():
            return Path(candidate)
    raise SystemExit("set VCF_RDFIZER_SRC to a VCF-RDFizer checkout that has vcf_rdfizer_policies/")


TOOL = _tool_root()
sys.path.insert(0, str(TOOL))

import rdflib  # noqa: E402  (after the path is set, so a missing tool fails first)

from vcf_rdfizer_policies import PolicyError  # noqa: E402
from vcf_rdfizer_policies.engine import Request, check_preconditions, evaluation  # noqa: E402
from vcf_rdfizer_policies.graphs import load  # noqa: E402
from vcf_rdfizer_policies.policy import Direct, Selection, load_rules, policy_digest, read_graph  # noqa: E402
from vcf_rdfizer_policies.profile import load_profile  # noqa: E402
from vcf_rdfizer_policies.release import attach, evaluate, write_release  # noqa: E402
from vcf_rdfizer_policies.vocabulary import Vocabulary  # noqa: E402

EXAMPLE = TOOL / "examples" / "policy"
POLICY = EXAMPLE / "policy.ttl"
CUSTOM = EXAMPLE / "custom-selector.ttl"
VCFS = sorted(EXAMPLE.glob("P00*.vcf"))
FIXTURE = json.loads((EXAMPLE / "fixture.json").read_text(encoding="utf-8"))
DUO = "http://purl.obolibrary.org/obo/DUO_"
PREFIXES = """@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix vcfp: <https://w3id.org/vcf-rdfizer/policy#> .
@prefix obo:  <http://purl.obolibrary.org/obo/> .
@prefix ex:   <https://example.org/> .
"""


def setup(policy_path, profiles=(), purposes=None):
    """(policy graph, profile, vocabulary, rules), as the command builds them."""
    graph = read_graph(policy_path)
    profile = load_profile(profiles, extra_graph=graph)
    vocabulary = Vocabulary.load(purposes)
    return graph, profile, vocabulary, load_rules(graph, profile, vocabulary)


def request(key, vocabulary):
    spec = FIXTURE["requesters"][key]
    return Request(spec["assignee"], vocabulary.resolve(spec["purpose"]))


def write(directory, name, text):
    path = Path(directory) / name
    path.write_text(PREFIXES + text, encoding="utf-8")
    return path


FILE_PERMISSION = "odrl:permission [ odrl:target <file://P001.vcf> ; odrl:action odrl:read ]"


def policy_text(body, conflict="odrl:prohibit"):
    return f"ex:p a odrl:Set ; odrl:conflict {conflict} ;\n{body} .\n"


class VocabularyTests(unittest.TestCase):
    def test_prefixed_names_and_iris_resolve_to_the_same_term(self):
        vocabulary = Vocabulary.load()
        self.assertEqual(vocabulary.resolve("DUO:0000007"), DUO + "0000007")
        self.assertEqual(vocabulary.resolve(DUO + "0000007"), DUO + "0000007")

    def test_unknown_terms_and_prefixes_are_refused(self):
        vocabulary = Vocabulary.load()
        for value in ("DUO:0000019", "XYZ:1", "GRU"):
            with self.subTest(value), self.assertRaises(PolicyError):
                vocabulary.resolve(value)

    def test_narrower_purposes_fall_within_broader_consents(self):
        vocabulary = Vocabulary.load()
        gru, hmb, ds, cc = (DUO + n for n in ("0000042", "0000006", "0000007", "0000043"))
        self.assertTrue(vocabulary.within(ds, gru) and vocabulary.within(ds, hmb))
        self.assertFalse(vocabulary.within(gru, hmb) or vocabulary.within(cc, gru))

    def test_a_skos_vocabulary_works_in_place_of_duo(self):
        with tempfile.TemporaryDirectory() as td:
            path = write(td, "p.ttl", "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
                                      "ex:cardio skos:broader ex:research . ex:research skos:broader ex:any .\n")
            vocabulary = Vocabulary.load(path)
        self.assertTrue(vocabulary.within("https://example.org/cardio", "https://example.org/any"))
        self.assertEqual(vocabulary.resolve("ex:cardio"), "https://example.org/cardio")


class ProfileTests(unittest.TestCase):
    def test_the_bundled_profile_declares_the_vcf_selectors_and_partition(self):
        profile = load_profile()
        vcfp = "https://w3id.org/vcf-rdfizer/policy#"
        self.assertEqual(set(profile.selectors), {vcfp + "RegionSelector", vcfp + "VariantSelector"})
        self.assertTrue(profile.iri_subtree and profile.ownership_path and profile.unit_query)

    def test_a_declaration_that_cannot_work_is_refused_at_load_time(self):
        cases = {
            "does not parse": 'ex:T a vcfp:SelectorType ; vcfp:query "SELECT ?resource WHERE {" .',
            "no ?resource": 'ex:T a vcfp:SelectorType ; vcfp:query "SELECT ?x WHERE { ?x ?p ?o }" .',
            "second profile": "ex:Other a vcfp:Profile .",
        }
        for name, text in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(PolicyError):
                    load_profile(["vcf-core", write(td, "x.ttl", text)])


class PolicyTests(unittest.TestCase):
    def test_the_example_policy_reads_as_eight_rules(self):
        _, _, _, rules = setup(POLICY)
        kinds = sorted((r.kind, type(r.target).__name__) for r in rules)
        self.assertEqual(kinds.count(("permission", "Direct")), 5)
        self.assertEqual(kinds.count(("prohibition", "Direct")), 1)          # P004's withdrawal
        self.assertEqual(kinds.count(("prohibition", "Selection")), 2)       # BRCA1 and e4

    def test_anything_the_engine_cannot_evaluate_is_refused(self):
        region = ('ex:a a vcfp:GraphSelection ; vcfp:selector [ a vcfp:RegionSelector ; '
                  'vcfp:assembly "GRCh38" ; vcfp:chrom "chr1" ; vcfp:start 1 {extra} ] .\n')
        selection_rule = "odrl:prohibition [ odrl:target ex:a ; odrl:action odrl:read ]"
        cases = {
            "deny-wins required": policy_text(FILE_PERMISSION, "odrl:perm"),
            "only read": policy_text(FILE_PERMISSION.replace("odrl:read", "odrl:distribute")),
            "unknown rule property": policy_text(FILE_PERMISSION[:-1] + " ; odrl:refinement [] ]"),
            "unsupported effect": policy_text(FILE_PERMISSION[:-1] + " ; odrl:duty [ odrl:action "
                                              "odrl:anonymize ; vcfp:transform vcfp:generalize ] ]"),
            "purpose outside the vocabulary": policy_text(FILE_PERMISSION[:-1] + " ; odrl:constraint [ "
                "odrl:leftOperand odrl:purpose ; odrl:operator odrl:isAnyOf ; odrl:rightOperand ex:x ] ]"),
            "blank-node target": policy_text(FILE_PERMISSION.replace("<file://P001.vcf>", "[]")),
            "missing parameter": policy_text(selection_rule) + region.format(extra=""),
            "undeclared selector type": policy_text(selection_rule)
                + region.format(extra="; vcfp:end 2").replace("RegionSelector", "SampleSelector"),
        }
        for name, text in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(PolicyError):
                    setup(write(td, "policy.ttl", text))


class Views(unittest.TestCase):
    """Shared setup: every requester's view of both fixture profiles. No tests of its own."""

    @classmethod
    def setUpClass(cls):
        cls.policy_graph, cls.profile, cls.vocabulary, cls.rules = setup(POLICY)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.graphs, cls.views = {}, {}
        for kind in ("expanded", "condensed"):
            graph = load(sorted((EXAMPLE / "converted" / kind).glob("*.nt.gz")))
            cls.graphs[kind] = graph
            for key in FIXTURE["requesters"]:
                release = evaluate(graph, cls.rules, request(key, cls.vocabulary), cls.profile, cls.vocabulary)
                out = Path(cls.tmp.name) / kind / key
                write_release(release, out, policies={r.policy for r in cls.rules}, digest=policy_digest(POLICY))
                cls.views[kind, key] = (release, out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, out, policy=POLICY, kind="expanded", vcfs=VCFS):
        from vcf_rdfizer_policies.check import check_view, read_view
        from vcf_rdfizer_policies.vcf_oracle import compare

        _, profile, vocabulary, rules = setup(policy)
        view, manifest, req = read_view(out)
        failures = check_view(view, manifest, req, policy_path=policy, rules=rules, profile=profile,
                              vocabulary=vocabulary, source=self.graphs[kind])
        return failures + (compare(view, vcfs, rules=rules, request=req, profile=profile, vocabulary=vocabulary)
                           if vcfs else [])


class DecisionTests(Views):
    """docs/policy-demonstrator.md §5, cell by cell, on the converted fixture."""

    def released(self, key, pos, file="P001", kind="expanded"):
        release, _ = self.views[kind, key]
        return {u["pos"].toPython(): ok for u, ok, _ in release.units
                if str(u["group"]) == f"file://{file}.vcf"}.get(pos)

    def test_files_follow_each_participants_consent(self):
        grid = {"gru": "✓✓———", "alz": "✓✓✓—✓", "clinical": "✓✓———"}
        for key, expected in grid.items():
            groups = self.views["expanded", key][0].groups
            self.assertEqual("".join("✓" if groups[f"file://P00{n}.vcf"][0] else "—" for n in range(1, 6)),
                             expected, key)

    def test_each_cohort_rule_exempts_one_purpose(self):
        brca1_inside, e4 = 43044295, 44908684
        self.assertEqual([self.released(k, brca1_inside) for k in ("gru", "alz", "clinical")], [False, False, True])
        self.assertEqual([self.released(k, e4) for k in ("gru", "alz", "clinical")], [False, True, False])

    def test_region_bounds_are_inclusive(self):
        self.assertEqual([self.released("gru", p) for p in (43044294, 43044295, 43125483, 43125484)],
                         [True, False, False, True])

    def test_the_variant_rule_matches_alleles_not_just_position(self):
        self.assertTrue(self.released("gru", 44908684, file="P002"))       # the T>G decoy

    def test_a_rule_for_one_party_does_not_bind_another(self):
        from dataclasses import replace
        from vcf_rdfizer_policies.engine import applies

        withdrawal = next(r for r in self.rules if r.kind == "prohibition" and isinstance(r.target, Direct))
        only_alz = replace(withdrawal, assignee=FIXTURE["requesters"]["alz"]["assignee"])
        self.assertTrue(applies(only_alz, request("alz", self.vocabulary), self.vocabulary))
        self.assertFalse(applies(only_alz, request("gru", self.vocabulary), self.vocabulary))

    def test_a_selector_precondition_stops_evaluation(self):
        graph = rdflib.Graph()
        graph += self.graphs["expanded"]
        vcfc = rdflib.Namespace("https://w3id.org/vcf-core/vocab#")
        graph.set((rdflib.URIRef("file://P001.vcf"), vcfc.referenceGenome, rdflib.Literal("GRCh37")))
        with self.assertRaises(PolicyError):
            check_preconditions(graph, self.rules)


class ReleaseTests(Views):
    def test_every_view_passes_its_checks_and_the_oracle(self):
        for (kind, key), (_, out) in self.views.items():
            with self.subTest(kind=kind, requester=key):
                self.assertEqual(self.check(out, kind=kind), [])

    def test_a_view_partitions_the_graph(self):
        for (kind, _), (release, _) in self.views.items():
            self.assertEqual(len(release.view) + release.triples_withheld, len(self.graphs[kind]))

    def test_the_withdrawn_file_leaves_nothing_behind(self):
        for key_, (release, _) in self.views.items():
            self.assertFalse([t for t in release.view if "P004.vcf" in str(t[0]) + str(t[2])], key_)

    def test_the_manifest_records_the_request_and_what_was_withheld(self):
        release, out = self.views["expanded", "alz"]
        text = (out / "manifest.ttl").read_text(encoding="utf-8")
        for expected in ("governed release; not anonymization", "DUO_0000007", "odrl:attribute",
                         f"vcfp:recordsWithheld {sum(not ok for _, ok, _ in release.units)}"):
            self.assertIn(expected, text)
        groups = json.loads((out / "summary.json").read_text())["groups"]
        self.assertFalse(groups["file://P004.vcf"]["released"])
        self.assertEqual(sum(g["records_released"] for g in groups.values()),
                         sum(ok for _, ok, _ in release.units))

    def test_a_release_is_never_written_over_another(self):
        release, out = self.views["expanded", "gru"]
        with self.assertRaises(FileExistsError):
            write_release(release, out, policies=set(), digest="")

    def test_attach_makes_policies_queryable_alongside_the_data(self):
        graph = rdflib.Graph()
        graph += self.graphs["expanded"]
        counts = attach(graph, self.policy_graph, self.rules)
        self.assertEqual(counts["https://example.org/policy/demo-cohort/apoe-e4"], 4)
        rows = graph.query("""
            PREFIX odrl: <http://www.w3.org/ns/odrl/2/> PREFIX vcfc: <https://w3id.org/vcf-core/vocab#>
            SELECT DISTINCT ?chrom WHERE { ?r a vcfc:VCFRecord ; vcfc:chrom ?chrom ; odrl:hasPolicy ?p .
                                           ?p odrl:prohibition ?rule . }""")
        self.assertEqual(sorted(str(c) for (c,) in rows), ["chr17", "chr19"])


class GeneralityTests(Views):
    """The engine is configured, not coded: none of these changes any Python."""

    def test_a_selector_declared_in_the_policy_file(self):
        _, profile, vocabulary, rules = setup(CUSTOM)
        release = evaluate(self.graphs["expanded"], rules, Request("https://example.org/party/anyone",
                           vocabulary.resolve("DUO:0000042")), profile, vocabulary)
        low = sum(1 for p in VCFS for line in p.read_text().splitlines()
                  if not line.startswith("#") and float(line.split("\t")[5]) < 60)
        self.assertEqual(sum(not ok for _, ok, _ in release.units), low)
        with tempfile.TemporaryDirectory() as td:
            write_release(release, Path(td) / "v", policies={r.policy for r in rules}, digest=policy_digest(CUSTOM))
            self.assertEqual(self.check(Path(td) / "v", policy=CUSTOM), [])

    def test_a_non_vcf_graph_with_a_property_path_partition(self):
        """A dataset of documents, each owning its sections; IRIs are opaque, so no subtree rule."""
        profile_ttl = """
ex:Docs a vcfp:Profile ; vcfp:ownershipPath "<https://example.org/hasSection>*" ; vcfp:iriSubtree false ;
    vcfp:unitQuery "SELECT ?resource ?group WHERE { ?group <https://example.org/hasDoc> ?resource }" .
ex:Tagged a vcfp:SelectorType ; vcfp:parameter ex:tag ;
    vcfp:query "SELECT ?resource WHERE { ?resource <https://example.org/tag> ?tag }" .
"""
        data = """
ex:set ex:hasDoc ex:d1 , ex:d2 . ex:d1 ex:hasSection ex:s1 . ex:s1 ex:text "a" .
ex:d2 ex:hasSection ex:s2 ; ex:tag "sensitive" . ex:s2 ex:text "b" .
"""
        policy = policy_text(
            "odrl:permission [ odrl:target ex:set ; odrl:action odrl:read ] ;"
            " odrl:permission [ odrl:target ex:d1 ; odrl:action odrl:read ] ;"
            " odrl:permission [ odrl:target ex:d2 ; odrl:action odrl:read ] ;"
            " odrl:prohibition [ odrl:target ex:tagged ; odrl:action odrl:read ]"
        ) + 'ex:tagged a vcfp:GraphSelection ; vcfp:selector [ a ex:Tagged ; ex:tag "sensitive" ] .\n'
        with tempfile.TemporaryDirectory() as td:
            profile_path = write(td, "profile.ttl", profile_ttl)
            _, profile, vocabulary, rules = setup(write(td, "policy.ttl", policy), profiles=[profile_path])
            graph = rdflib.Graph().parse(data=PREFIXES + data, format="turtle")
        release = evaluate(graph, rules, Request("https://example.org/me", vocabulary.resolve("DUO:0000042")),
                           profile, vocabulary)
        self.assertEqual({str(u["resource"]): ok for u, ok, _ in release.units},
                         {"https://example.org/d1": True, "https://example.org/d2": False})
        kept = {str(s) for s, _, _ in release.view}
        self.assertIn("https://example.org/s1", kept)
        self.assertNotIn("https://example.org/s2", kept)          # d2 owns s2 through the path


class MutationTests(Views):
    """Break a correct view each way a view can go wrong; `check` must say so."""

    def mutate(self, key, edit, *, policy=POLICY):
        _, out = self.views["expanded", key]
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "view"
            shutil.copytree(out, copy)
            lines = (copy / "view.nt").read_text(encoding="utf-8").splitlines()
            (copy / "view.nt").write_text("\n".join(edit(lines)) + "\n", encoding="utf-8")
            return "\n".join(self.check(copy, policy=policy))

    def source_lines(self, starting):
        return [line for line in self.graphs["expanded"].serialize(format="nt").splitlines()
                if line.startswith(starting)]

    def brca1_record(self):
        release, _ = self.views["expanded", "gru"]
        window = FIXTURE["loci"]["brca1"]
        return next(u["resource"] for u, _, _ in release.units if str(u["group"]).endswith("P001.vcf")
                    and window["start"] < u["pos"].toPython() < window["end"])

    def test_a_reinstated_prohibited_record_is_caught(self):
        record = f"<{self.brca1_record()}>"
        link = [l for l in self.source_lines("<file://P001.vcf> ") if l.endswith(f"{record} .")]
        report = self.mutate("gru", lambda lines: lines + self.source_lines(record + " ") + link)
        self.assertIn("prohibited content present", report)
        self.assertIn("leak", report)

    def test_a_restored_triple_of_the_withdrawn_file_is_caught(self):
        report = self.mutate("alz", lambda lines: lines + self.source_lines("<file://P004.vcf> ")[:1])
        self.assertIn("P004.vcf", report)

    def test_a_deleted_released_record_is_caught(self):
        report = self.mutate("alz", lambda lines: [l for l in lines if not l.startswith("<file://P003.vcf#record/1>")])
        self.assertIn("over-withheld: <file://P003.vcf#record/1>", report)

    def test_a_reference_to_a_missing_resource_is_dangling(self):
        report = self.mutate("alz", lambda lines: [l for l in lines
                                                   if not l.startswith("<file://P003.vcf#record/1/allele/0>")])
        self.assertIn("dangling reference", report)

    def test_one_requesters_view_does_not_pass_as_anothers(self):
        _, alz = self.views["expanded", "alz"]
        alz_lines = (alz / "view.nt").read_text(encoding="utf-8").splitlines()
        self.assertIn("prohibited content present", self.mutate("gru", lambda _: alz_lines))

    def test_a_view_is_checked_against_the_policy_it_was_made_under(self):
        with tempfile.TemporaryDirectory() as td:
            changed = Path(td) / "policy.ttl"
            changed.write_text(POLICY.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
            self.assertIn("different policy", self.mutate("gru", lambda lines: lines, policy=changed))


class CommandTests(unittest.TestCase):
    def run_cli(self, *argv):
        from vcf_rdfizer_policy import main

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main([str(a) for a in argv])
        return code, buffer.getvalue()

    def test_evaluate_then_check_round_trip(self):
        rdf = sorted((EXAMPLE / "converted" / "condensed").glob("*.nt.gz"))
        spec = FIXTURE["requesters"]["clinical"]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "clinical"
            args = ("evaluate", "--rdf", *rdf, "--policy", POLICY, "--assignee", spec["assignee"],
                    "--purpose", spec["purpose"], "-o", out)
            self.assertEqual(self.run_cli(*args)[0], 0)
            code, text = self.run_cli("check", "--view", out, "--rdf", *rdf, "--policy", POLICY, "--vcf", *VCFS)
            self.assertEqual((code, text.strip().splitlines()[-1]), (0, "PASS"))
            self.assertEqual(self.run_cli(*args)[0], 2)               # never overwrites

    def test_an_unsupported_policy_exits_2_with_the_reason(self):
        with tempfile.TemporaryDirectory() as td:
            code, text = self.run_cli("explain", "--policy", write(td, "p.ttl", policy_text(FILE_PERMISSION, "odrl:perm")))
        self.assertEqual(code, 2)
        self.assertIn("deny wins", text)

    def test_explain_and_attach(self):
        code, text = self.run_cli("explain", "--policy", CUSTOM)
        self.assertEqual(code, 0)
        self.assertIn("(a https://example.org/policy/quality/QualityBelow)", text)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "annotated.nt"
            self.assertEqual(self.run_cli("attach", "--rdf", EXAMPLE / "converted" / "expanded" / "P001.nt.gz",
                                          "--policy", POLICY, "-o", out)[0], 0)
            self.assertIn("http://www.w3.org/ns/odrl/2/hasPolicy", out.read_text(encoding="utf-8"))


class FixtureTests(unittest.TestCase):
    def test_the_committed_fixture_is_what_the_generator_writes(self):
        spec = importlib.util.spec_from_file_location("make_fixture", EXAMPLE / "make_fixture.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            module.main(Path(td))
            names = [p.name for p in VCFS] + ["fixture.json"]
            match, mismatch, errors = filecmp.cmpfiles(EXAMPLE, td, names, shallow=False)
        self.assertEqual((mismatch, errors, len(match)), ([], [], 6))


if __name__ == "__main__":
    unittest.main()
