#!/usr/bin/env python3
"""Write arm 3's case file: arm 1's question, for one participant's whole genome.

    python3 make_wgs.py        # writes wgs/case.json; then: generate.py wgs wgs/case.json

The participant and their consent come from use_case.json unchanged, so the
arm-3 answer can be compared record for record with that participant's arm-1
answer. Only derive.sh's region restriction differs (the harness passes `all`).
"""

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def wgs_case(case: dict) -> dict:
    case = {k: v for k, v in case.items() if k != "cohort"}
    pid = case["whole_genome"]["participant"]
    case["participants"] = [p for p in case["participants"] if p["id"] == pid]
    case["policy"] = {**case["policy"], "consents": {pid: case["policy"]["consents"][pid]}}
    return case


def main() -> int:
    case = wgs_case(json.loads((HERE / "use_case.json").read_text(encoding="utf-8")))
    out = HERE / "wgs"
    out.mkdir(exist_ok=True)
    (out / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    print(f"wgs/case.json: {case['participants'][0]['id']}, whole genome")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
