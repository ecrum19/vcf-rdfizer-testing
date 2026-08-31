#!/usr/bin/env python3
"""Compute the six semantic-query results directly from a source VCF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from cyvcf2 import VCF


TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def alt_lexical(variant: Any) -> str:
    alleles = variant.ALT or [None]
    return ",".join("." if allele is None else str(allele) for allele in alleles)


def classify_variant_shape(ref_value: str, alt_value: str) -> str:
    ref = str(ref_value).upper()
    alt = str(alt_value).upper()

    if alt == ".":
        return "NO_ALT"
    if "," in alt:
        return "MULTIALLELIC"
    if (
        alt == "*"
        or "[" in alt
        or "]" in alt
        or (alt.startswith("<") and alt.endswith(">"))
    ):
        return "SYMBOLIC_OR_BREAKEND"
    if not re.fullmatch(r"[ACGTN]+", ref) or not re.fullmatch(r"[ACGTN]+", alt):
        return "OTHER"
    if len(ref) == 1 and len(alt) == 1:
        return "SNV"
    if len(ref) == len(alt):
        return "MNV_OR_EQUAL_LENGTH_SUBSTITUTION"
    if len(ref) < len(alt):
        return "INSERTION_SHAPE"
    return "DELETION_SHAPE"


def exact_filter_lexical(variant: Any) -> str:
    """Recover FILTER exactly when bcftools is unavailable.

    ``Variant.FILTER`` maps both PASS and the not-applied dot to ``None``.
    Serializing only those ambiguous rows preserves the source distinction.
    """

    values = list(variant.FILTERS or [])
    if values:
        return ";".join(str(value) for value in values)

    fields = str(variant).rstrip("\r\n").split("\t", 8)
    if len(fields) < 7:
        raise ValueError("Could not recover FILTER from serialized VCF record")
    return fields[6]


def filter_status(filter_lexical: str) -> str:
    if filter_lexical == "PASS":
        return "PASS"
    if filter_lexical == ".":
        return "NOT_APPLIED"
    return "FAILED"


def filters_with_bcftools(vcf_path: Path) -> Counter[tuple[str, str]]:
    command = ["bcftools", "query", "-f", "%FILTER\n", str(vcf_path)]
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_handle:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=stderr_handle,
            text=True,
            encoding="utf-8",
        )
        assert process.stdout is not None
        counts: Counter[tuple[str, str]] = Counter()
        for line in process.stdout:
            lexical = line.rstrip("\r\n")
            if lexical == "":
                process.kill()
                process.wait()
                raise ValueError("bcftools returned an empty FILTER value")
            counts[(filter_status(lexical), lexical)] += 1
        return_code = process.wait()
        stderr_handle.seek(0)
        stderr = stderr_handle.read()
        if return_code != 0:
            raise RuntimeError(
                f"bcftools FILTER extraction failed with exit {return_code}: "
                f"{stderr.strip()}"
            )
        return counts


def genotype_alleles(raw_gt: Any) -> tuple[int | None, ...] | None:
    if raw_gt is None:
        return None
    return tuple(
        None if allele is None or int(allele) < 0 else int(allele)
        for allele in raw_gt[:-1]
    )


def classify_genotype(
    alleles: tuple[int | None, ...] | None,
    *,
    has_gt_field: bool,
) -> str:
    if not has_gt_field:
        return "NO_GT_FIELD"
    if alleles is None or not alleles or any(allele is None for allele in alleles):
        return "MISSING"
    complete = tuple(int(allele) for allele in alleles if allele is not None)
    if len(complete) == 1:
        return "HAPLOID_REF" if complete[0] == 0 else "HAPLOID_ALT"
    if len(complete) == 2:
        if complete[0] == complete[1]:
            return "HOM_REF" if complete[0] == 0 else "HOM_ALT"
        return "HET"
    return "OTHER_PLOIDY"


def _header_ids(lines: Iterable[str], kind: str) -> list[str]:
    pattern = re.compile(rf"^##{re.escape(kind)}=<ID=([^,>]+)")
    return sorted(
        match.group(1)
        for line in lines
        if (match := pattern.match(line)) is not None
    )


def header_inventory(raw_header: str, samples: list[str]) -> dict[str, Any]:
    lines = raw_header.splitlines()

    def values(prefix: str) -> list[str]:
        return [line[len(prefix) :] for line in lines if line.startswith(prefix)]

    file_formats = values("##fileformat=")
    return {
        "fileFormat": file_formats[0] if file_formats else None,
        "samples": samples,
        "sampleCount": len(samples),
        "contigs": _header_ids(lines, "contig"),
        "references": values("##reference="),
        "assemblies": values("##assembly="),
        "formatIds": _header_ids(lines, "FORMAT"),
        "infoIds": _header_ids(lines, "INFO"),
        "filterIds": _header_ids(lines, "FILTER"),
        "altIds": _header_ids(lines, "ALT"),
    }


def run(vcf_path: Path, *, filter_oracle: str = "auto") -> dict[str, Any]:
    vcf_path = vcf_path.resolve()
    if not vcf_path.is_file():
        raise FileNotFoundError(f"VCF does not exist: {vcf_path}")

    use_bcftools = filter_oracle == "bcftools" or (
        filter_oracle == "auto" and shutil.which("bcftools") is not None
    )
    if filter_oracle == "bcftools" and shutil.which("bcftools") is None:
        raise RuntimeError("--filter-oracle=bcftools requested but bcftools is absent")

    filters = filters_with_bcftools(vcf_path) if use_bcftools else Counter()
    resolved_filter_oracle = "bcftools" if use_bcftools else "cyvcf2-serialization"

    reader = VCF(str(vcf_path), strict_gt=True)
    samples = list(reader.samples)
    inventory = header_inventory(reader.raw_header, samples)

    density: Counter[tuple[str, int]] = Counter()
    variant_shapes: Counter[str] = Counter()
    genotype_classes: Counter[tuple[str, str]] = Counter()
    ac_an: Counter[tuple[int, int]] = Counter()

    biallelic_snv_count = 0
    transition_count = 0
    transversion_count = 0
    total_records = 0
    gt_record_count = 0
    single_alt_record_count = 0
    q06_eligible_site_count = 0

    for variant in reader:
        total_records += 1

        window_index = (int(variant.POS) - 1) // 1_000_000
        density[(str(variant.CHROM), window_index)] += 1

        raw_alt = alt_lexical(variant)
        variant_shapes[classify_variant_shape(variant.REF, raw_alt)] += 1

        ref = str(variant.REF).upper()
        alt = raw_alt.upper()
        if (
            re.fullmatch(r"[ACGT]", ref)
            and re.fullmatch(r"[ACGT]", alt)
            and ref != alt
        ):
            biallelic_snv_count += 1
            if (ref, alt) in TRANSITIONS:
                transition_count += 1
            else:
                transversion_count += 1

        if not use_bcftools:
            raw_filter = exact_filter_lexical(variant)
            filters[(filter_status(raw_filter), raw_filter)] += 1

        raw_format = variant.FORMAT
        if not raw_format:
            format_keys: list[str] = []
        elif isinstance(raw_format, str):
            format_keys = raw_format.split(":")
        else:
            format_keys = [str(key) for key in raw_format]
        has_gt = "GT" in format_keys
        if has_gt:
            gt_record_count += 1

        allele_calls: list[tuple[int | None, ...] | None] = []
        if samples:
            if has_gt:
                raw_genotypes = list(variant.genotypes)
                if len(raw_genotypes) != len(samples):
                    raise ValueError(
                        "Sample/genotype length mismatch at "
                        f"{variant.CHROM}:{variant.POS}: "
                        f"{len(samples)} samples, {len(raw_genotypes)} genotypes"
                    )
                allele_calls = [genotype_alleles(gt) for gt in raw_genotypes]
            else:
                allele_calls = [None] * len(samples)

            for sample_id, alleles in zip(samples, allele_calls, strict=True):
                gt_class = classify_genotype(alleles, has_gt_field=has_gt)
                genotype_classes[(sample_id, gt_class)] += 1

        if raw_alt != "." and "," not in raw_alt:
            single_alt_record_count += 1
            if has_gt:
                an = 0
                ac = 0
                for alleles in allele_calls:
                    if alleles is None or any(allele is None for allele in alleles):
                        continue
                    complete = tuple(
                        int(allele) for allele in alleles if allele is not None
                    )
                    if len(complete) not in (1, 2):
                        continue
                    if any(allele not in (0, 1) for allele in complete):
                        continue
                    an += len(complete)
                    ac += sum(complete)
                if an > 0:
                    ac_an[(an, ac)] += 1
                    q06_eligible_site_count += 1

    reader.close()

    if sum(filters.values()) != total_records:
        raise ValueError(
            "FILTER oracle record count differs from cyvcf2: "
            f"{sum(filters.values())} != {total_records}"
        )

    q1 = [
        {"chrom": chrom, "windowIndex": window, "recordCount": int(count)}
        for (chrom, window), count in sorted(density.items())
    ]
    q2 = [
        {"variantClass": variant_class, "recordCount": int(count)}
        for variant_class, count in sorted(variant_shapes.items())
    ]
    q3 = {
        "biallelicSnvCount": biallelic_snv_count,
        "transitionCount": transition_count,
        "transversionCount": transversion_count,
        "tiTvRatio": (
            transition_count / transversion_count if transversion_count else None
        ),
    }
    q4 = [
        {
            "filterStatus": status,
            "filterLexical": lexical,
            "recordCount": int(count),
        }
        for (status, lexical), count in sorted(filters.items())
    ]
    q5_rows = [
        {
            "sampleId": sample,
            "genotypeClass": genotype_class,
            "callCount": int(count),
        }
        for (sample, genotype_class), count in sorted(genotype_classes.items())
    ]

    per_sample: dict[str, Counter[str]] = {}
    for (sample, genotype_class), count in genotype_classes.items():
        per_sample.setdefault(sample, Counter())[genotype_class] += count
    q5_call_rates = []
    for sample, counts in sorted(per_sample.items()):
        total = sum(counts.values())
        missing = counts["MISSING"] + counts["NO_GT_FIELD"]
        called = total - missing
        q5_call_rates.append(
            {
                "sampleId": sample,
                "total": total,
                "called": called,
                "missing": missing,
                "callRate": called / total if total else None,
            }
        )

    q6 = [
        {
            "an": int(an),
            "ac": int(ac),
            "siteCount": int(count),
            "af": ac / an,
        }
        for (an, ac), count in sorted(ac_an.items())
    ]

    return {
        "source": str(vcf_path),
        "sourceSha256": sha256_file(vcf_path),
        "filterOracle": resolved_filter_oracle,
        "inventory": inventory,
        "sampleCount": len(samples),
        "samples": samples,
        "totalRecords": total_records,
        "gtRecordCount": gt_record_count,
        "singleAltRecordCount": single_alt_record_count,
        "q06EligibleSiteCount": q06_eligible_site_count,
        "q01_record_density_1mb": q1,
        "q02_variant_shape_counts": q2,
        "q03_titv": q3,
        "q04_filter_distribution": q4,
        "q05_sample_genotype_counts": q5_rows,
        "q05_call_rates_derived": q5_call_rates,
        "q06_ac_an_distribution": q6,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vcf", type=Path, help="Source VCF or bgzip-compressed VCF")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON (default: stdout)",
    )
    parser.add_argument(
        "--filter-oracle",
        choices=("auto", "bcftools", "cyvcf2"),
        default="auto",
        help="Use bcftools when available, or exact cyvcf2 row serialization",
    )
    args = parser.parse_args()

    result = run(args.vcf, filter_oracle=args.filter_oracle)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)


if __name__ == "__main__":
    main()
