#!/usr/bin/env python3
"""What each route asks its author to write, and to change (plan §2.5).

    VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 effort.py <out-dir>

Needs rdflib and a VCF-RDFizer checkout (the policy plug-in runs as a CLI).

1. Inventory. The authored lines of arm 1's two routes, split into rules and
   data. The RDF route is policy.ttl and carriers.rq; the linkers, selectors
   and profile it uses ship with the tool. The baseline is baseline.sh,
   baseline_carriers.py and the case file's tables they read. Blank lines,
   comments and docstrings are not counted. generate.py, which writes
   policy.ttl here so that both routes read one definition, stands in for an
   author writing the Turtle by hand, and is not counted.
2. Change scenarios. Each is applied to both routes as a real edit: the case
   file (both routes' data) and, where a route needs it, its rules or code.
   The edited lines are counted per file. Then each edited pair must still
   release the same records to every requester for every participant, on the
   fixture below. A scenario whose edits disagree is reported as such, not
   counted.

The fixture gives every participant four records: one in a cancer gene
(BRCA1), one in a cardiac gene (MYH7), one elsewhere, and HFE C282Y (ClinVar
variation 9). They are linked the way the real linkers link them: SPDI
identifiers on RefSeq accessions, and Ensembl gene IRIs. HG002's file names
contigs without "chr", as its real file does.

Writes <out-dir>/effort.json and prints both tables.
"""

from __future__ import annotations

import ast
import copy
import csv
import difflib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import tokenize

HERE = pathlib.Path(__file__).resolve().parent
CASE = json.loads((HERE / "use_case.json").read_text(encoding="utf-8"))
REGIONS = {r["symbol"]: r for r in json.loads((HERE / "regions.json").read_text(encoding="utf-8"))["regions"]}
VCFC = "https://w3id.org/vcf-core/vocab#"
VCFL = "https://w3id.org/vcf-rdfizer/linking#"
SPDI = "https://api.ncbi.nlm.nih.gov/variation/v0/spdi/"
ENSEMBL = "https://identifiers.org/ensembl:"
ASSEMBLY = "GCA_000001405.15_GRCh38_no_alt_analysis_set"
ACCESSIONS = {"6": "NC_000006.12", "14": "NC_000014.9", "17": "NC_000017.11"}   # grch38-refseq.tsv
CLINICAL = "DUO:0000043"

#: HFE C282Y, rs1800562, ClinVar variation 9 (GRCh38).
C282Y = ("chr6", 26092913, "G", "A")
#: ACMG SF v3.2 cardiomyopathy, arrhythmia, aortopathy and familial
#: hypercholesterolaemia genes: the 81 less the cancer, metabolic,
#: miscellaneous and HHT genes.
CARDIAC = ["ACTA2", "ACTC1", "APOB", "BAG3", "CALM1", "CALM2", "CALM3", "CASQ2", "COL3A1", "DES", "DSC2",
           "DSG2", "DSP", "FBN1", "FLNC", "KCNH2", "KCNQ1", "LDLR", "LMNA", "MYBPC3", "MYH11", "MYH7", "MYL2",
           "MYL3", "PCSK9", "PKP2", "PRKAG2", "RBM20", "RYR2", "SCN5A", "SMAD3", "TGFBR1", "TGFBR2", "TMEM43",
           "TNNC1", "TNNI3", "TNNT2", "TPM1", "TRDN", "TTN"]


# --- Counting -----------------------------------------------------------------

def python_lines(text: str) -> set[int]:
    """Line numbers carrying code: not blank, not a comment, not a docstring."""
    docstrings = set()
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            docstrings.update(range(body[0].lineno, body[0].end_lineno + 1))
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
    lines = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type not in skip:
            lines.update(range(token.start[0], token.end[0] + 1))
    return lines - docstrings


def plain_lines(text: str) -> list[str]:
    """Shell, Turtle, SPARQL, JSON: the lines that are not blank or a whole-line comment."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def count(path_or_text, kind: str) -> int:
    text = path_or_text.read_text(encoding="utf-8") if isinstance(path_or_text, pathlib.Path) else path_or_text
    return len(python_lines(text)) if kind == "python" else len(plain_lines(text))


def changed(before: str, after: str, kind: str) -> dict:
    """Lines added and removed, counting only the lines `count` counts."""
    keep = (lambda t: [l for n, l in enumerate(t.splitlines(), 1) if n in python_lines(t)]) if kind == "python" \
        else plain_lines
    added = removed = 0
    for line in difflib.unified_diff(keep(before), keep(after), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"added": added, "removed": removed}


def data_json(case: dict) -> str:
    """The case file's tables that the baseline reads, as the file writes them."""
    return json.dumps({"policy": case["policy"], "definition": case["definition"]}, indent=2)


# --- The two routes, for one case -------------------------------------------------

def generate_policy(case: dict, work: pathlib.Path) -> str:
    """policy.ttl as generate.py writes it for `case` (what an author would write by hand)."""
    work.mkdir(parents=True, exist_ok=True)
    (work / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "generate.py"), str(work), str(work / "case.json")],
                   check=True, capture_output=True)
    return (work / "policy.ttl").read_text(encoding="utf-8")


def load_baseline(source: str, name: str):
    """baseline_carriers.py from `source` text, as a module (so an edited copy can be run)."""
    path = pathlib.Path(tempfile.mkdtemp()) / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- The fixture --------------------------------------------------------------------

def fixture_records(participant: str) -> list[tuple]:
    """(chrom as the file writes it, pos, ref, alt, gene or None)."""
    plain = participant == "HG002"
    rows = [(REGIONS["BRCA1"]["chrom"], (REGIONS["BRCA1"]["start"] + REGIONS["BRCA1"]["end"]) // 2, "A", "G", "BRCA1"),
            (REGIONS["MYH7"]["chrom"], (REGIONS["MYH7"]["start"] + REGIONS["MYH7"]["end"]) // 2, "A", "G", "MYH7"),
            ("chr17", 1_000_000, "C", "T", None),
            (*C282Y, "HFE")]
    return [(chrom.removeprefix("chr") if plain else chrom, pos, ref, alt, gene) for chrom, pos, ref, alt, gene in rows]


def fixture_nt(participant: str) -> str:
    source = f"file://{participant}.acmg.vcf"
    lines = [f'<{source}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{VCFC}VCFFile> .',
             f'<{source}> <{VCFC}referenceGenome> "{ASSEMBLY}" .']
    for n, (chrom, pos, ref, alt, gene) in enumerate(fixture_records(participant), 1):
        record, call = f"{source}#record/{n}", f"{source}#call/{n}"
        spdi = f"{SPDI}{ACCESSIONS[chrom.removeprefix('chr')]}:{pos - 1}:{ref}:{alt}"
        lines += [f"<{source}> <{VCFC}hasRecord> <{record}> .",
                  f"<{record}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{VCFC}VCFRecord> .",
                  f'<{record}> <{VCFC}chrom> "{chrom}" .', f'<{record}> <{VCFC}pos> "{pos}"^^<http://www.w3.org/2001/XMLSchema#integer> .',
                  f'<{record}> <{VCFC}ref> "{ref}" .', f'<{record}> <{VCFC}alt> "{alt}" .',
                  f"<{record}> <{VCFC}hasCall> <{call}> .", f"<{call}> <{VCFL}sameVariantAs> <{spdi}> ."]
        if gene:
            lines.append(f"<{call}> <{VCFL}overlapsGene> <{ENSEMBL}{REGIONS[gene]['ensembl_id']}> .")
    return "\n".join(lines) + "\n"


def rdf_released(tool: pathlib.Path, policy: pathlib.Path, vocabulary, participant: str, requester: dict,
                 work: pathlib.Path) -> set[int]:
    rdf = work / f"{participant}.nt"
    rdf.write_text(fixture_nt(participant), encoding="utf-8")
    out = work / f"{participant}-{requester['purpose'].replace(':', '')}-{len(list(work.iterdir()))}"
    argv = [sys.executable, str(tool / "vcf_rdfizer_policy.py"), "evaluate", "--rdf", str(rdf), "--policy", str(policy),
            "--assignee", requester["assignee"], "--purpose", requester["purpose"], "-o", str(out)]
    if vocabulary:
        argv += ["--purposes", str(vocabulary)]
    subprocess.run(argv, check=True, capture_output=True, text=True)
    with (out / "decisions.csv").open(encoding="utf-8") as handle:
        return {int(row["pos"]) for row in csv.DictReader(handle) if row["released"] == "True"}


def baseline_released(module, case: dict, participant: str, requester: dict) -> set[int]:
    spans = module.restricted_spans(list(REGIONS.values()), case["policy"]["secondary_findings"]["genes"])
    released = set()
    for chrom, pos, ref, alt, _ in fixture_records(participant):
        carrier = {"participant": participant, "chrom": chrom.removeprefix("chr"), "pos": pos, "ref": ref, "alt": alt,
                   "restricted": module.overlaps(chrom, pos, ref, spans)}
        if module.released(carrier, requester["purpose"], case["policy"]):
            released.add(pos)
    return released


# --- Scenarios ----------------------------------------------------------------------

BASELINE = (HERE / "baseline_carriers.py").read_text(encoding="utf-8")
VOCABULARY = None      # the plug-in's shipped DUO subset, unless a scenario extends it

POA_TERMS = """
obo:DUO_0000011 rdfs:label "population origins or ancestry research only" ;
    rdfs:subClassOf obo:DUO_0000001 .
"""

C282Y_RULE = f"""
# HFE C282Y (rs1800562) is released only for clinical care. The target is its
# SPDI identity, so the rule holds whatever a file calls chromosome 6.
ex:hfe-c282y a odrl:Asset , vcfp:GraphSelection ;
    vcfp:selector [ a vcfp:LinkedSelector ; vcfp:predicate vcfl:sameVariantAs ;
                    vcfp:entities ( <{SPDI}NC_000006.12:26092912:G:A> ) ] .
ex:hfe a odrl:Set ; odrl:uid ex:hfe ; odrl:profile <https://w3id.org/vcf-rdfizer/policy> ; odrl:conflict odrl:prohibit ;
    odrl:prohibition [ odrl:target ex:hfe-c282y ; odrl:action odrl:read ; odrl:assignee odrl:All ;
        odrl:constraint [ odrl:leftOperand odrl:purpose ; odrl:operator odrl:isNoneOf ; odrl:rightOperand obo:DUO_0000043 ] ] .
"""

C282Y_CODE_OLD = """    # The secondary-findings rule is about the record, not ClinVar's gene label.
    return not carrier["restricted"] or purpose == "DUO:0000043"
"""
C282Y_CODE_NEW = """    # A named variant is released only for clinical care.
    variants = {tuple(v) for v in policy.get("clinical_only_variants", [])}
    if (carrier["chrom"], carrier["pos"], carrier["ref"], carrier["alt"]) in variants and purpose != "DUO:0000043":
        return False
    # The secondary-findings rule is about the record, not ClinVar's gene label.
    return not carrier["restricted"] or purpose == "DUO:0000043"
"""


def scenarios() -> list[dict]:
    """Each: a name, the case edit (both routes' data), and any rule or code edit per route."""
    withdraw = copy.deepcopy(CASE)
    withdraw["policy"]["consents"]["NB72462M"]["withdrawn"] = True

    ancestry = copy.deepcopy(CASE)
    ancestry["policy"]["requesters"]["ancestry"] = {"assignee": "https://example.org/party/ancestry-study",
                                                     "purpose": "DUO:0000011"}

    cardiac = copy.deepcopy(CASE)
    cardiac["policy"]["secondary_findings"] = {**cardiac["policy"]["secondary_findings"], "genes": CARDIAC,
                                               "source": "ACMG SF v3.2 cardiovascular genes (40)"}

    variant = copy.deepcopy(CASE)
    variant["policy"]["clinical_only_variants"] = [[C282Y[0].removeprefix("chr"), *C282Y[1:]]]

    return [
        {"name": "withdrawal", "summary": "NB72462M withdraws consent", "case": withdraw},
        {"name": "new purpose", "summary": "a new requester for ancestry research (DUO:0000011)", "case": ancestry,
         "vocabulary": POA_TERMS},
        {"name": "panel change", "summary": "the restricted panel becomes 40 cardiac genes", "case": cardiac},
        {"name": "variant rule", "summary": "HFE C282Y is released only for clinical care", "case": variant,
         "policy_extra": C282Y_RULE, "baseline_code": (C282Y_CODE_OLD, C282Y_CODE_NEW)},
    ]


def agreement(tool, work, case, policy_text, vocabulary_text, baseline_source, name) -> dict:
    """Both edited routes, every requester and participant: do they release the same records?"""
    work.mkdir(parents=True, exist_ok=True)
    policy = work / "policy.ttl"
    policy.write_text(policy_text, encoding="utf-8")
    vocabulary = None
    if vocabulary_text:
        vocabulary = work / "purposes.ttl"
        shipped = (tool / "vcf_rdfizer_data" / "policy" / "duo-subset.ttl").read_text(encoding="utf-8")
        vocabulary.write_text(shipped + vocabulary_text, encoding="utf-8")
    module = load_baseline(baseline_source, "baseline_" + name.replace(" ", "_"))
    mismatches, outcomes, cells = [], set(), 0
    for rname, requester in case["policy"]["requesters"].items():
        for participant in case["policy"]["consents"]:
            rdf = rdf_released(tool, policy, vocabulary, participant, requester, work)
            base = baseline_released(module, case, participant, requester)
            cells += 1
            outcomes.add(frozenset(base))
            if rdf != base:
                mismatches.append({"requester": rname, "participant": participant,
                                   "rdf": sorted(rdf), "baseline": sorted(base)})
    return {"cells": cells, "distinct_outcomes": len(outcomes), "agree": not mismatches, "mismatches": mismatches}


def main(argv: list[str]) -> int:
    out = pathlib.Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    tool = pathlib.Path(os.environ["VCF_RDFIZER_SRC"])
    work = pathlib.Path(tempfile.mkdtemp())

    base_policy = generate_policy(CASE, work / "base")
    query = (HERE / "carriers.rq").read_text(encoding="utf-8")
    panel_lines = sum(1 for line in plain_lines(base_policy) if line.strip().startswith("ensembl:"))
    gene_values = sum(1 for line in plain_lines(query) if line.strip().startswith("VALUES ?gene"))
    inventory = {
        "rdf": {"policy.ttl": count(base_policy, "turtle"), "of which panel IRIs (data)": panel_lines,
                "carriers.rq": count(query, "sparql"), "of which gene list (data)": gene_values,
                "linkers, selectors, profile": 0},
        "baseline": {"baseline.sh": count(HERE / "baseline.sh", "shell"),
                     "baseline_carriers.py": count(HERE / "baseline_carriers.py", "python"),
                     "case tables (data)": count(data_json(CASE), "json"),
                     "acmg_sf_v3.2.genes.txt (data)": count(HERE / "acmg_sf_v3.2.genes.txt", "text")},
    }
    base_check = agreement(tool, work / "check-base", CASE, base_policy, None, BASELINE, "base")

    results = []
    for scenario in scenarios():
        case = scenario["case"]
        policy = generate_policy(case, work / scenario["name"]) + scenario.get("policy_extra", "")
        code = BASELINE
        if "baseline_code" in scenario:
            assert scenario["baseline_code"][0] in BASELINE, "the baseline no longer has the code this edit replaces"
            code = BASELINE.replace(*scenario["baseline_code"])
        edits = {
            "rdf": {"policy.ttl": changed(base_policy, policy, "turtle"),
                    "purpose vocabulary": changed("", scenario.get("vocabulary", ""), "turtle"),
                    "carriers.rq": {"added": 0, "removed": 0}},
            "baseline": {"baseline_carriers.py": changed(BASELINE, code, "python"),
                         "case tables (data)": changed(data_json(CASE), data_json(case), "json")},
        }
        check = agreement(tool, work / f"check-{scenario['name']}", case, policy, scenario.get("vocabulary"), code,
                          scenario["name"])
        results.append({"name": scenario["name"], "summary": scenario["summary"], "edits": edits, "check": check})

    report = {"inventory": inventory, "base_check": base_check, "scenarios": results}
    (out / "effort.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("Authored lines (arm 1)")
    for route, parts in inventory.items():
        print(f"  {route:9} " + ", ".join(f"{k} {v}" for k, v in parts.items()))
    print(f"  both routes agree before any change: {base_check['agree']} ({base_check['cells']} cells)")
    print("Change scenarios: lines added/removed per file; both routes checked on the fixture")
    for r in results:
        cells = "; ".join(f"{route}: " + (", ".join(f"{f} +{e['added']}/-{e['removed']}" for f, e in files.items()
                                                     if e["added"] or e["removed"]) or "none")
                          for route, files in r["edits"].items())
        print(f"  {r['name']:13} {cells}  | agree {r['check']['agree']} ({r['check']['cells']} cells, "
              f"{r['check']['distinct_outcomes']} outcomes)")
    return 0 if base_check["agree"] and all(r["check"]["agree"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
