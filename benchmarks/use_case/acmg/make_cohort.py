#!/usr/bin/env python3
"""Select arm 2's cohort from the 1000 Genomes high-coverage call set, and draw its consents.

    make_cohort.py <ped.txt> <2504.sequence.index>     # writes cohort/cohort.json

Unrelated samples only (the 2,504 of the sequence index), `per_population`
from each of the 26 populations, chosen with a fixed seed. Each participant's
consent is drawn from `consent_mix`, and a `withdrawal_percent` withdraw; all
SIMULATED. The output is a complete case file (use_case.json with its
participants and consents replaced), so both routes read it exactly as they
read arm 1's. It is committed, so the cohort does not change under the paper.
"""

from __future__ import annotations

import collections
import csv
import hashlib
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent


def unrelated(index: pathlib.Path) -> set[str]:
    with index.open(encoding="utf-8") as handle:
        rows = csv.DictReader((line.lstrip("#") for line in handle if not line.startswith("##")), delimiter="\t")
        return {row["SAMPLE_NAME"] for row in rows}


def populations(ped: pathlib.Path, keep: set[str]) -> dict[str, list[str]]:
    by_population = collections.defaultdict(list)
    with ped.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter=" "):
            if row["SampleID"] in keep:
                by_population[row["Population"]].append(row["SampleID"])
    return {p: sorted(s) for p, s in sorted(by_population.items())}


def select(pools: dict[str, list[str]], per_population: int, rng: random.Random) -> list[tuple[str, str]]:
    return [(sample, population) for population, samples in pools.items()
            for sample in sorted(rng.sample(samples, per_population))]


def consents(samples, cohort, rng: random.Random) -> dict[str, dict]:
    mix = cohort["consent_mix"]
    drawn = {}
    for sample, _ in samples:
        choice = rng.choices(mix, weights=[m["weight"] for m in mix])[0]
        drawn[sample] = {"permits": choice["permits"]}
        if rng.randrange(100) < cohort["withdrawal_percent"]:
            drawn[sample]["withdrawn"] = True
    return drawn


def main(argv: list[str]) -> int:
    ped, index = map(pathlib.Path, argv)
    case = json.loads((HERE / "use_case.json").read_text(encoding="utf-8"))
    cohort = case.pop("cohort")
    panel = cohort.pop("panel_frequencies")
    case.pop("whole_genome")                  # arm 3's, not the cohort's
    rng = random.Random(cohort["seed"])
    pools = populations(ped, unrelated(index))
    if len(pools) != 26:
        raise SystemExit(f"expected 26 populations, found {len(pools)}")
    samples = select(pools, cohort["per_population"], rng)
    case["participants"] = [{"id": s, "input": f"{s}.vcf.gz", "rsids": False,
                             "source": f"1000 Genomes high coverage (NYGC), {p}"} for s, p in samples]
    case["policy"]["consents"] = consents(samples, cohort, rng)
    case["cohort"] = {**cohort, "inputs_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                                  for path in (ped, index)}}
    case["panel"] = panel
    out = HERE / "cohort"
    out.mkdir(exist_ok=True)
    (out / "cohort.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    mix = collections.Counter(",".join(c["permits"]) + (" withdrawn" if c.get("withdrawn") else "")
                              for c in case["policy"]["consents"].values())
    print(f"{len(samples)} participants from {len(pools)} populations; consents {dict(mix)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
