#!/usr/bin/env python3
"""Normalize Comunica SPARQL Results JSON into the oracle's canonical shapes."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


QUERY_ALIASES = {
    "q01": "q01_record_density_1mb",
    "q02": "q02_variant_shape_counts",
    "q03": "q03_titv",
    "q04": "q04_filter_distribution",
    "q05": "q05_sample_genotype_counts",
    "q06": "q06_ac_an_distribution",
}

QUERY_SCHEMAS = {
    "q01_record_density_1mb": {
        "fields": ("chrom", "windowIndex", "recordCount"),
        "integers": ("windowIndex", "recordCount"),
        "sort": ("chrom", "windowIndex"),
    },
    "q02_variant_shape_counts": {
        "fields": ("variantClass", "recordCount"),
        "integers": ("recordCount",),
        "sort": ("variantClass",),
    },
    "q03_titv": {
        "fields": (
            "biallelicSnvCount",
            "transitionCount",
            "transversionCount",
        ),
        "integers": (
            "biallelicSnvCount",
            "transitionCount",
            "transversionCount",
        ),
        "sort": (),
    },
    "q04_filter_distribution": {
        "fields": ("filterStatus", "filterLexical", "recordCount"),
        "integers": ("recordCount",),
        "sort": ("filterStatus", "filterLexical"),
    },
    "q05_sample_genotype_counts": {
        "fields": ("sampleId", "genotypeClass", "callCount"),
        "integers": ("callCount",),
        "sort": ("sampleId", "genotypeClass"),
    },
    "q06_ac_an_distribution": {
        "fields": ("an", "ac", "siteCount"),
        "integers": ("an", "ac", "siteCount"),
        "sort": ("an", "ac"),
    },
}


def canonical_query_id(query_id: str) -> str:
    query_id = Path(query_id).stem
    query_id = QUERY_ALIASES.get(query_id, query_id)
    if query_id not in QUERY_SCHEMAS:
        choices = ", ".join(sorted(QUERY_SCHEMAS))
        raise ValueError(f"Unknown query {query_id!r}; expected one of: {choices}")
    return query_id


def _integer(lexical: str, *, field: str) -> int:
    try:
        value = Decimal(lexical)
    except InvalidOperation as error:
        raise ValueError(f"{field} is not numeric: {lexical!r}") from error
    if not value.is_finite() or value != value.to_integral_value():
        raise ValueError(f"{field} is not an integer: {lexical!r}")
    return int(value)


def _bindings(document: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        bindings = document["results"]["bindings"]
    except (KeyError, TypeError) as error:
        raise ValueError("Not a SPARQL Results JSON document") from error
    if not isinstance(bindings, list):
        raise ValueError("SPARQL results.bindings must be a list")
    return bindings


def normalize_document(query_id: str, document: dict[str, Any]) -> Any:
    query_id = canonical_query_id(query_id)
    schema = QUERY_SCHEMAS[query_id]
    integer_fields = set(schema["integers"])
    rows: list[dict[str, Any]] = []

    for row_number, binding in enumerate(_bindings(document), start=1):
        row: dict[str, Any] = {}
        for field in schema["fields"]:
            try:
                lexical = binding[field]["value"]
            except (KeyError, TypeError) as error:
                raise ValueError(
                    f"Row {row_number} has no bound value for {field!r}"
                ) from error
            row[field] = (
                _integer(lexical, field=field)
                if field in integer_fields
                else str(lexical)
            )
        rows.append(row)

    sort_fields = schema["sort"]
    if sort_fields:
        rows.sort(key=lambda row: tuple(row[field] for field in sort_fields))
        keys = [tuple(row[field] for field in sort_fields) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{query_id} returned duplicate canonical keys")

    if query_id == "q03_titv":
        if len(rows) != 1:
            raise ValueError(f"q03_titv must return exactly one row, got {len(rows)}")
        row = rows[0]
        transversions = row["transversionCount"]
        row["tiTvRatio"] = (
            row["transitionCount"] / transversions if transversions else None
        )
        return row

    if query_id == "q06_ac_an_distribution":
        for row in rows:
            row["af"] = row["ac"] / row["an"]

    return rows


def normalize_file(query_id: str, input_path: Path) -> Any:
    with input_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    return normalize_document(query_id, document)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Query ID, such as q01 or q01_record_density_1mb")
    parser.add_argument("input", type=Path, help="Comunica SPARQL Results JSON")
    parser.add_argument("--output", type=Path, help="Output JSON (default: stdout)")
    args = parser.parse_args()

    normalized = normalize_file(args.query, args.input)
    serialized = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)


if __name__ == "__main__":
    main()
