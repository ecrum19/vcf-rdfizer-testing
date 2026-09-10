#!/usr/bin/env python3
"""Build the small VCF fixtures the robustness experiments need.

Two families:

* ``version_<v>.vcf`` — one file per supported specification version, so the
  version-dependent emitter behaviour can be exercised (plan §4.2). The 4.4/4.5
  files carry the features those versions add: per-ALT tuple repetition, the
  leading phase indicator, and the local-allele (LA/LR/LG) family.
* awkward inputs — real situations that a VCF consumer meets and that a
  converter can plausibly get wrong (plan §4.4). Each one is legal VCF, or
  deliberately malformed in a single named way.

Every fixture is tiny and readable on purpose: when one of them fails, the
diagnosis should be visible in the file itself.

Usage:
    python3 make_fixtures.py <output-dir>
"""

from __future__ import annotations

import gzip
import json
import pathlib
import sys
import time

HEADER_COMMON = [
    "##contig=<ID=20,length=64444167>",
    "##reference=file:///ref/GRCh38.fa",
    '##FILTER=<ID=LowQual,Description="Low quality">',
    '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total depth">',
    '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">',
    '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
]

COLUMNS = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT"


def vcf(lines: list[str], samples: list[str] | None = None) -> str:
    """Assemble a VCF from meta lines plus data rows."""
    samples = samples or []
    column_line = COLUMNS + ("".join("\t" + s for s in samples) if samples else "")
    body = [line for line in lines if not line.startswith("#")]
    meta = [line for line in lines if line.startswith("##")]
    return "\n".join(meta + [column_line] + body) + "\n"


# ---------------------------------------------------------------------------
# Version fixtures
# ---------------------------------------------------------------------------
def version_fixtures() -> dict[str, str]:
    """One fixture per version, each exercising that version's own features."""
    out: dict[str, str] = {}

    for version in ("4.1", "4.2", "4.3"):
        out[f"version_{version}.vcf"] = vcf(
            [f"##fileformat=VCFv{version}", *HEADER_COMMON]
            + [
                "20\t100\t.\tA\tG\t50\tPASS\tDP=30;AF=0.5\tGT:DP\t0/1:30",
                "20\t200\trs1\tAT\tA\t60\tPASS\tDP=25;AF=0.25\tGT:DP\t0/0:25",
                "20\t300\t.\tC\tG,T\t40\tLowQual\tDP=18;AF=0.1,0.2\tGT:DP\t1/2:18",
            ],
            samples=["SAMPLE_A"],
        )

    # 4.4 adds the leading phase indicator and per-ALT tuple repetition.
    out["version_4.4.vcf"] = vcf(
        [
            "##fileformat=VCFv4.4",
            *HEADER_COMMON,
            '##FORMAT=<ID=PS,Number=1,Type=Integer,Description="Phase set">',
        ]
        + [
            "20\t100\t.\tA\tG\t50\tPASS\tDP=30;AF=0.5\tGT:DP:PS\t|0/1:30:100",
            "20\t300\t.\tC\tG,T\t40\tPASS\tDP=18;AF=0.1,0.2\tGT:DP:PS\t1|2:18:100",
        ],
        samples=["SAMPLE_A"],
    )

    # 4.5 adds the local-allele family (LA/LR/LG) and base modifications.
    out["version_4.5.vcf"] = vcf(
        [
            "##fileformat=VCFv4.5",
            *HEADER_COMMON,
            '##FORMAT=<ID=LAA,Number=.,Type=Integer,Description="Local alleles">',
            '##FORMAT=<ID=LAD,Number=R,Type=Integer,Description="Local allele depths">',
        ]
        + [
            "20\t100\t.\tA\tG\t50\tPASS\tDP=30;AF=0.5\tGT:DP:LAA:LAD\t0/1:30:1:20,10",
            "20\t300\t.\tC\tG,T\t40\tPASS\tDP=18;AF=0.1,0.2\tGT:DP:LAA:LAD\t1/2:18:1,2:0,9,9",
        ],
        samples=["SAMPLE_A"],
    )

    # No ##fileformat at all. Must convert under the newest supported rules and
    # emit NO vcfc:VCF4xFile class, i.e. claim no version gate it cannot verify.
    out["version_missing_declaration.vcf"] = vcf(
        HEADER_COMMON
        + ["20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30"],
        samples=["SAMPLE_A"],
    )

    # A declared version with no conformance overlay (4.0) — also fallback.
    out["version_4.0_declared.vcf"] = vcf(
        ["##fileformat=VCFv4.0", *HEADER_COMMON]
        + ["20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30"],
        samples=["SAMPLE_A"],
    )
    return out


# ---------------------------------------------------------------------------
# Awkward-input fixtures
# ---------------------------------------------------------------------------
BASE = ["##fileformat=VCFv4.2", *HEADER_COMMON]


def awkward_fixtures() -> dict[str, tuple[str, str]]:
    """name -> (content, what a correct tool must do with it)."""
    out: dict[str, tuple[str, str]] = {}

    out["awkward_sites_only.vcf"] = (
        vcf(BASE + [
            "20\t100\t.\tA\tG\t50\tPASS\tDP=30",
            "20\t200\t.\tC\tT\t60\tPASS\tDP=25",
        ]),
        "Convert. No FORMAT or sample columns at all; Q5/Q6 are not applicable.",
    )

    out["awkward_symbolic_alleles.vcf"] = (
        vcf(
            BASE + [
                '##ALT=<ID=DEL,Description="Deletion">',
                '##ALT=<ID=INS,Description="Insertion">',
                '##INFO=<ID=SVTYPE,Number=1,Type=String,Description="SV type">',
                '##INFO=<ID=END,Number=1,Type=Integer,Description="End position">',
                "20\t1000\tsv1\tA\t<DEL>\t60\tPASS\tSVTYPE=DEL;END=2000\tGT:DP\t0/1:12",
                "20\t3000\tsv2\tC\t<INS>\t60\tPASS\tSVTYPE=INS;END=3001\tGT:DP\t1/1:14",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. Symbolic alleles are not sequence alleles; the graph must not "
        "treat '<DEL>' as a base string.",
    )

    out["awkward_breakend.vcf"] = (
        vcf(
            BASE + [
                '##INFO=<ID=SVTYPE,Number=1,Type=String,Description="SV type">',
                '##INFO=<ID=MATEID,Number=1,Type=String,Description="Mate">',
                "20\t5000\tbnd_a\tG\tG]20:7000]\t60\tPASS\tSVTYPE=BND;MATEID=bnd_b\tGT:DP\t0/1:9",
                "20\t7000\tbnd_b\tT\t[20:5000[T\t60\tPASS\tSVTYPE=BND;MATEID=bnd_a\tGT:DP\t0/1:9",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert, or refuse with a clear diagnostic. Breakend ALT syntax is not "
        "a plain allele string.",
    )

    out["awkward_high_ploidy.vcf"] = (
        vcf(
            BASE + [
                "20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/0/1/1:30",
                "20\t200\t.\tC\tT\t50\tPASS\tDP=30\tGT:DP\t0/1/1:30",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. Ploidy is 4 then 3; vcfc:ploidy must follow the data, not "
        "assume 2.",
    )

    out["awkward_half_and_haploid_calls.vcf"] = (
        vcf(
            BASE + [
                "20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t./1:30",
                "20\t200\t.\tC\tT\t50\tPASS\tDP=30\tGT:DP\t1:30",
                "20\t300\t.\tG\tA\t50\tPASS\tDP=30\tGT:DP\t.:30",
                "20\t400\t.\tT\tC\t50\tPASS\tDP=30\tGT:DP\t./.:30",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. Half-call, haploid, single-missing and fully-missing "
        "genotypes are four distinct cases and must not collapse.",
    )

    out["awkward_filter_variants.vcf"] = (
        vcf(
            BASE + [
                "20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30",
                "20\t200\t.\tC\tT\t50\t.\tDP=30\tGT:DP\t0/1:30",
                "20\t300\t.\tG\tA\t50\tLowQual\tDP=30\tGT:DP\t0/1:30",
                "20\t400\t.\tT\tC\t50\tLowQual;q10\tDP=30\tGT:DP\t0/1:30",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. PASS, '.' (no filter applied) and a failed filter are three "
        "different states — Q4 checks the exact lexical value. Note 'q10' is "
        "undeclared in the header, which is also worth surfacing.",
    )

    out["awkward_missing_values.vcf"] = (
        vcf(
            BASE + [
                "20\t100\t.\tA\tG\t.\t.\t.\tGT:DP\t./.:.",
                "20\t200\t.\tC\tT\t.\t.\tDP=.\tGT:DP\t0/1:.",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. Missing QUAL, FILTER, INFO and FORMAT values must be absent "
        "from the graph, not emitted as the literal '.'.",
    )

    out["awkward_declared_format_absent.vcf"] = (
        vcf(
            BASE + [
                '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allele depths">',
                "20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30",
            ],
            samples=["SAMPLE_A"],
        ),
        "Convert. AD is declared in the header but never used in a record; the "
        "header declaration should still be represented.",
    )

    out["awkward_no_records.vcf"] = (
        vcf(BASE, samples=["SAMPLE_A"]),
        "Convert to a header-only graph, or refuse clearly. Zero data records "
        "must not be reported as success with a silently empty artifact.",
    )

    out["awkward_crlf.vcf"] = (
        vcf(
            BASE + ["20\t100\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30"],
            samples=["SAMPLE_A"],
        ).replace("\n", "\r\n"),
        "Convert. CRLF line endings must not leave a stray \\r inside the last "
        "field's literal.",
    )

    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_dir = pathlib.Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for name, content in version_fixtures().items():
        (out_dir / name).write_text(content, newline="")
        written.append({"file": name, "kind": "version", "expectation": None})

    expectations = {}
    for name, (content, expectation) in awkward_fixtures().items():
        (out_dir / name).write_text(content, newline="")
        written.append({"file": name, "kind": "awkward", "expectation": expectation})
        expectations[name] = expectation

    # A truncated gzip stream cannot be written as text: build it by cutting a
    # valid member short, so the failure is a real decompression error rather
    # than an invalid-VCF error.
    good = vcf(
        BASE + ["20\t%d\t.\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:30" % pos
                for pos in range(100, 1100, 10)],
        samples=["SAMPLE_A"],
    )
    full = gzip.compress(good.encode())
    truncated = out_dir / "awkward_truncated.vcf.gz"
    truncated.write_bytes(full[: max(1, len(full) // 2)])
    expectation = (
        "Refuse with a clear decompression diagnostic. This must NOT be "
        "reported as a successful conversion of a partial graph."
    )
    written.append({"file": truncated.name, "kind": "awkward", "expectation": expectation})
    expectations[truncated.name] = expectation

    (out_dir / "FIXTURES.json").write_text(
        json.dumps(
            {
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "generator": "benchmarks/lib/make_fixtures.py",
                "fixtures": written,
            },
            indent=2,
        )
        + "\n"
    )

    print(f"wrote {len(written)} fixtures to {out_dir}")
    for entry in written:
        print(f"  {entry['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
