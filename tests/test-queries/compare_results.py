#!/usr/bin/env python3
"""Compare canonical VCF-oracle and SPARQL results with structured diffs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


QUERY_SPECS = {
    "q01_record_density_1mb": {
        "keys": ("chrom", "windowIndex"),
        "values": ("recordCount",),
    },
    "q02_variant_shape_counts": {
        "keys": ("variantClass",),
        "values": ("recordCount",),
    },
    "q03_titv": {
        "keys": (),
        "values": (
            "biallelicSnvCount",
            "transitionCount",
            "transversionCount",
        ),
    },
    "q04_filter_distribution": {
        "keys": ("filterStatus", "filterLexical"),
        "values": ("recordCount",),
    },
    "q05_sample_genotype_counts": {
        "keys": ("sampleId", "genotypeClass"),
        "values": ("callCount",),
    },
    "q06_ac_an_distribution": {
        "keys": ("an", "ac"),
        "values": ("siteCount",),
    },
}


def _projection(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: row[field] for field in fields}


def compare_query(query_id: str, expected: Any, actual: Any) -> dict[str, Any]:
    spec = QUERY_SPECS[query_id]
    keys = spec["keys"]
    values = spec["values"]
    relevant = keys + values

    if not keys:
        expected_values = _projection(expected, values)
        actual_values = _projection(actual, values)
        equal = expected_values == actual_values
        return {
            "status": "PASS" if equal else "MISMATCH",
            "expected": expected_values,
            "actual": actual_values,
            "differingValues": {
                field: {"expected": expected_values[field], "actual": actual_values[field]}
                for field in values
                if expected_values[field] != actual_values[field]
            },
        }

    def index(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
        indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            key = tuple(row[field] for field in keys)
            if key in indexed:
                raise ValueError(f"Duplicate {query_id} key: {key!r}")
            indexed[key] = _projection(row, relevant)
        return indexed

    expected_by_key = index(expected)
    actual_by_key = index(actual)
    expected_keys = set(expected_by_key)
    actual_keys = set(actual_by_key)

    missing = [expected_by_key[key] for key in sorted(expected_keys - actual_keys)]
    extra = [actual_by_key[key] for key in sorted(actual_keys - expected_keys)]
    differing = []
    for key in sorted(expected_keys & actual_keys):
        expected_row = expected_by_key[key]
        actual_row = actual_by_key[key]
        if any(expected_row[field] != actual_row[field] for field in values):
            differing.append({"expected": expected_row, "actual": actual_row})

    equal = not missing and not extra and not differing
    return {
        "status": "PASS" if equal else "MISMATCH",
        "missingRows": missing,
        "extraRows": extra,
        "differingRows": differing,
    }


def _sum(rows: list[dict[str, Any]], field: str) -> int:
    return sum(int(row[field]) for row in rows)


def check_invariants(
    payload: dict[str, Any],
    *,
    total_records: int,
    single_alt_record_count: int,
    genotype_queries_required: bool,
    q06_eligible_site_count: int | None = None,
) -> list[dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []
    q1_total = _sum(payload["q01_record_density_1mb"], "recordCount")
    q2_total = _sum(payload["q02_variant_shape_counts"], "recordCount")
    q4_total = _sum(payload["q04_filter_distribution"], "recordCount")
    q3 = payload["q03_titv"]

    checks.extend(
        [
            ("q01_total_records", q1_total == total_records, f"{q1_total} == {total_records}"),
            ("q02_total_records", q2_total == total_records, f"{q2_total} == {total_records}"),
            ("q04_total_records", q4_total == total_records, f"{q4_total} == {total_records}"),
            (
                "q03_partition",
                q3["transitionCount"] + q3["transversionCount"]
                == q3["biallelicSnvCount"],
                f"{q3['transitionCount']} + {q3['transversionCount']} "
                f"== {q3['biallelicSnvCount']}",
            ),
        ]
    )

    snv_count = next(
        (
            row["recordCount"]
            for row in payload["q02_variant_shape_counts"]
            if row["variantClass"] == "SNV"
        ),
        0,
    )
    checks.append(
        (
            "q03_subset_of_q02_snv",
            q3["biallelicSnvCount"] <= snv_count,
            f"{q3['biallelicSnvCount']} <= {snv_count}",
        )
    )

    per_sample: dict[str, int] = {}
    if genotype_queries_required:
        for row in payload["q05_sample_genotype_counts"]:
            sample = row["sampleId"]
            per_sample[sample] = per_sample.get(sample, 0) + int(row["callCount"])
    for sample, count in sorted(per_sample.items()):
        checks.append(
            (
                f"q05_total_for_{sample}",
                count == total_records,
                f"{count} == {total_records}",
            )
        )

    q06_site_total = _sum(payload["q06_ac_an_distribution"], "siteCount")
    if genotype_queries_required:
        checks.append(
            (
                "q06_subset_of_single_alt_records",
                q06_site_total <= single_alt_record_count,
                f"{q06_site_total} <= {single_alt_record_count}",
            )
        )
        if q06_eligible_site_count is not None:
            checks.append(
                (
                    "q06_eligible_site_total",
                    q06_site_total == q06_eligible_site_count,
                    f"{q06_site_total} == {q06_eligible_site_count}",
                )
            )

    q06_rows = (
        payload["q06_ac_an_distribution"] if genotype_queries_required else []
    )
    for row in q06_rows:
        valid = (
            row["an"] > 0
            and 0 <= row["ac"] <= row["an"]
            and row["siteCount"] > 0
        )
        checks.append(
            (
                f"q06_valid_an_ac_{row['an']}_{row['ac']}",
                valid,
                f"0 <= {row['ac']} <= {row['an']}; siteCount={row['siteCount']}",
            )
        )

    return [
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
        for name, passed, detail in checks
    ]


def compare_payloads(
    parser_payload: dict[str, Any],
    sparql_payload: dict[str, Any],
    *,
    fixture_expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    genotype_queries_required = bool(
        parser_payload["sampleCount"] and parser_payload["gtRecordCount"]
    )
    query_results = {
        query_id: compare_query(
            query_id,
            parser_payload[query_id],
            sparql_payload[query_id],
        )
        for query_id in QUERY_SPECS
    }
    if not genotype_queries_required:
        for query_id in (
            "q05_sample_genotype_counts",
            "q06_ac_an_distribution",
        ):
            query_results[query_id] = {
                "status": "NOT_APPLICABLE_VERIFIED_NO_SAMPLES_OR_GT",
                "diagnosticComparison": query_results[query_id],
            }

    total_records = int(parser_payload["totalRecords"])
    single_alt_record_count = int(parser_payload["singleAltRecordCount"])
    parser_invariants = check_invariants(
        parser_payload,
        total_records=total_records,
        single_alt_record_count=single_alt_record_count,
        genotype_queries_required=genotype_queries_required,
        q06_eligible_site_count=int(parser_payload["q06EligibleSiteCount"]),
    )
    sparql_invariants = check_invariants(
        sparql_payload,
        total_records=total_records,
        single_alt_record_count=single_alt_record_count,
        genotype_queries_required=genotype_queries_required,
    )

    expected_results: dict[str, Any] | None = None
    if fixture_expected is not None:
        expected_results = {"parser": {}, "sparql": {}}
        for query_id in QUERY_SPECS:
            expected_results["parser"][query_id] = compare_query(
                query_id,
                fixture_expected[query_id],
                parser_payload[query_id],
            )
            expected_results["sparql"][query_id] = compare_query(
                query_id,
                fixture_expected[query_id],
                sparql_payload[query_id],
            )
        expected_results["status"] = (
            "PASS"
            if all(
                result["status"] == "PASS"
                for side in ("parser", "sparql")
                for result in expected_results[side].values()
            )
            else "MISMATCH"
        )

    acceptable_statuses = {"PASS", "NOT_APPLICABLE_VERIFIED_NO_SAMPLES_OR_GT"}
    all_passed = all(
        result["status"] in acceptable_statuses for result in query_results.values()
    )
    all_passed = all_passed and all(
        check["status"] == "PASS"
        for check in parser_invariants + sparql_invariants
    )
    if expected_results is not None:
        all_passed = all_passed and expected_results["status"] == "PASS"

    return {
        "status": "PASS" if all_passed else "MISMATCH",
        "queries": query_results,
        "invariants": {
            "parser": parser_invariants,
            "sparql": sparql_invariants,
        },
        "fixtureExpected": expected_results,
    }


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parser", type=Path, required=True, help="parser.json")
    parser.add_argument("--sparql", type=Path, required=True, help="sparql.json")
    parser.add_argument("--expected", type=Path, help="Optional hand-checked fixture JSON")
    parser.add_argument("--output", type=Path, help="Output JSON (default: stdout)")
    args = parser.parse_args()

    result = compare_payloads(
        _load(args.parser),
        _load(args.sparql),
        fixture_expected=_load(args.expected) if args.expected else None,
    )
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
