#!/usr/bin/env python3
"""Write arm 4's case file: one whole genome under layered consent, four requesters.

    python3 make_layered.py   # writes layered/case.json; then: generate.py layered layered/case.json

Arms 1-3 govern whole files: a participant's consent releases their file or
withholds it, and one cohort rule withholds the cancer genes from research. In
arm 3 that left the whole genome all or nothing. Arm 4 keeps arm 1's question
and definitions, takes one participant's whole genome (NB72462M), and stacks
rules that each target a different kind of selection, so every requester gets
a different, non-empty part of the same genome:

  participant   the consent: clinical care and general research
  gene panel    the cancer-predisposition genes, for clinical care only (arm 1's rule)
  purpose       disease-specific research sees only the cardiovascular genes
  region        APOE, only for care by the participant's own physician
  variant       one variant of uncertain significance, never for the biobank

"Only the participant's own physician" is a purpose narrower than clinical
care, declared in the case's purpose vocabulary (layered/purposes.ttl), not an
assignee: ODRL has no "everyone except", so a rule naming the physician's
assignee would release APOE to any clinical requester it did not list.

All of it is simulated consent on a real public genome, like arms 1-3.
"""

import json
import pathlib

from effort import CARDIAC

HERE = pathlib.Path(__file__).resolve().parent
PARTICIPANT = "NB72462M"
CLINICAL = "DUO:0000043"
GENERAL = "DUO:0000042"
DISEASE_SPECIFIC = "DUO:0000007"
OWN_PHYSICIAN = "https://example.org/purpose/own-physician-care"


def layered_case(case: dict) -> dict:
    case = {k: v for k, v in case.items() if k not in ("cohort", "whole_genome")}
    case["participants"] = [p for p in case["participants"] if p["id"] == PARTICIPANT]
    policy = case["policy"]
    case["purposes"] = [{
        "iri": OWN_PHYSICIAN, "broader": CLINICAL,
        "label": "clinical care by the participant's own physician",
    }]
    case["policy"] = {
        "note": policy["note"],
        "consents": {PARTICIPANT: {"permits": [CLINICAL, GENERAL]}},
        "secondary_findings": policy["secondary_findings"],
        "purpose_panels": [{
            "purpose": DISEASE_SPECIFIC, "genes": CARDIAC,
            "rule": "Disease-specific research receives only records whose REF extent overlaps one of "
                    "these genes; everything else in the file is withheld from it.",
        }],
        "regions": [{
            "name": "APOE", "chrom": "chr19", "start": 44903787, "end": 44909396,
            "assembly": case["reference"]["name"], "purposes": [OWN_PHYSICIAN],
            "source": "Ensembl release 116, ENSG00000130203, gene span",
            "rule": "Records whose POS lies in the span are released only for care by the participant's "
                    "own physician. The region is coordinates on a named contig, so it binds the contig "
                    "name as the file writes it.",
        }],
        "variants": [{
            "name": "DSP chr6:7569314 C>G, uncertain significance", "chrom": "chr6", "pos": 7569314, "ref": "C",
            "alt": "G", "spdi": "NC_000006.12:7569313:C:G", "withheld_from": ["biobank"],
            "rule": "Withheld from the biobank by name, whatever its purpose; the target is the "
                    "variant's SPDI identity, so it holds whatever the file calls chromosome 6.",
        }],
        "requesters": {
            "own_physician": {"assignee": "https://example.org/party/participant-physician",
                              "purpose": OWN_PHYSICIAN},
            **policy["requesters"],
        },
    }
    return case


def main() -> int:
    case = layered_case(json.loads((HERE / "use_case.json").read_text(encoding="utf-8")))
    out = HERE / "layered"
    out.mkdir(exist_ok=True)
    (out / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    print(f"layered/case.json: {PARTICIPANT}, whole genome, {len(case['policy']['requesters'])} requesters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
