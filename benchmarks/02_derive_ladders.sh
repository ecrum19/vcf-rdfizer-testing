#!/usr/bin/env bash
# Plan §2.1 and §3.1 — build the derived one-factor ladders.
#
# Both headline scaling questions need ladders where exactly ONE thing varies.
# Deriving every rung from a single source file holds variant class, caller,
# assembly and header constant, which is what makes a fitted slope mean
# something (§3). The ten-file corpus cannot do this: HGSVC2 is structural
# variants, 1000G is a phased SNV cohort, and a regression across them
# estimates a mixture of genomic content, not the tool's scaling.
#
#   samples ladder  1000G_phase3_chr20  fixed records, S = 1..2504
#   records ladder  HG005_GRCh38        fixed 1 sample,  V = 10k..1M
#
# Implemented in awk rather than bcftools, deliberately:
#
#   * No dependency. bcftools is not installed everywhere this suite runs.
#   * No INFO recomputation. `bcftools view -S` without -I recomputes AC/AN,
#     which makes the INFO layer change with S and contaminates the triple
#     counts we are attributing to the sample layer. Cutting columns cannot
#     recompute anything, so INFO is byte-identical across rungs by
#     construction rather than by remembering a flag.
#
# ---------------------------------------------------------------------------
# WHAT THESE FILES ARE NOT
# ---------------------------------------------------------------------------
# Dropping sample columns without recomputing INFO means INFO/AC and INFO/AN no
# longer agree with the genotypes that remain. That is intended here — INFO is
# a held-fixed control, not a measurement — but it makes every rung a BENCHMARK
# FIXTURE, not a biologically valid VCF. Do not use them for anything but cost
# measurement, and say so in the manuscript.
#
# Validation is unaffected: the suite's Q6 derives AC/AN from GT rather than
# trusting INFO, and every query compares the graph against an oracle computed
# from the same file, so internal consistency holds.
#
# Usage:
#   ./02_derive_ladders.sh              # both ladders
#   ./02_derive_ladders.sh samples
#   ./02_derive_ladders.sh records

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

WHICH="${1:-both}"
SAMPLE_RUNGS="${BM_SAMPLE_RUNGS:-1 4 16 64 256 1024 2504}"
RECORD_RUNGS="${BM_RECORD_RUNGS:-10000 100000 1000000}"
FIXED_RECORDS="${BM_FIXED_RECORDS:-10000}"

SAMPLE_SOURCE="${BM_SAMPLE_SOURCE:-1000G_phase3_chr20.vcf.gz}"
RECORD_SOURCE="${BM_RECORD_SOURCE:-HG005_GRCh38.vcf.gz}"

mkdir -p "$BM_DERIVED"

# Portable sha256.
bm_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else printf 'unavailable\n'; fi
}

# Stream a VCF, gzipped or not.
bm_cat_vcf() {
  case "$1" in
    *.gz) gzip -dc -- "$1" ;;
    *)    cat -- "$1" ;;
  esac
}

# Write a provenance record beside each derived file. Derived inputs are
# irreproducible without this (§5.4).
bm_write_provenance() {
  local derived="$1" source_path="$2" recipe="$3" records="$4" samples="$5"
  python3 - "$derived" "$source_path" "$recipe" "$records" "$samples" \
    "$(bm_sha256 "$derived")" "$(bm_sha256 "$source_path")" <<'PYEOF'
import json, pathlib, sys, time
derived, source, recipe, records, samples, d_sha, s_sha = sys.argv[1:8]
path = pathlib.Path(derived)
path.with_suffix(path.suffix + ".provenance.json").write_text(json.dumps({
    "derived_file": path.name,
    "derived_sha256": d_sha,
    "derived_bytes": path.stat().st_size,
    "source_file": pathlib.Path(source).name,
    "source_sha256": s_sha,
    "recipe": recipe,
    "data_records": int(records),
    "sample_columns": int(samples),
    "generator": "benchmarks/02_derive_ladders.sh (awk column/record slicing)",
    "info_recomputed": False,
    "biologically_valid": False,
    "caveat": (
        "Sample columns were cut without recomputing INFO, so INFO/AC and "
        "INFO/AN do not agree with the retained genotypes. INFO is a held-fixed "
        "control here. Benchmark fixture only."
    ),
    "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, indent=2) + "\n")
PYEOF
}

# --------------------------------------------------------------------------
# Samples ladder: fixed record set, varying sample-column count
# --------------------------------------------------------------------------
derive_samples() {
  bm_banner "§2.1 samples ladder from $SAMPLE_SOURCE"
  if ! bm_have_vcf "$SAMPLE_SOURCE"; then
    bm_warn "source not available: $SAMPLE_SOURCE — samples ladder skipped.
Download it with: bash $BM_REPO/scripts/download_test_data.sh"
    return 0
  fi
  local src; src="$(bm_vcf "$SAMPLE_SOURCE")"

  local total_samples
  total_samples="$(bm_cat_vcf "$src" | awk -F'\t' '
    /^#CHROM/ { print (NF > 9 ? NF - 9 : 0); exit }')"
  bm_step "source has $total_samples sample columns"

  # Fix the record set once so every rung has byte-identical variant content.
  local base="$BM_DERIVED/base_${FIXED_RECORDS}rec.vcf"
  if [[ ! -f "$base.gz" ]]; then
    bm_step "fixing record set at $FIXED_RECORDS records"
    bm_cat_vcf "$src" | awk -v n="$FIXED_RECORDS" '
      /^#/ { print; next }
      kept < n { print; kept++; next }
      { exit }' > "$base"
    gzip -f "$base"
  fi

  local rung
  for rung in $SAMPLE_RUNGS; do
    if (( rung > total_samples )); then
      bm_warn "rung S=$rung exceeds the source's $total_samples samples — skipped"
      continue
    fi
    local target="$BM_DERIVED/1000G_${FIXED_RECORDS}r_s${rung}.vcf.gz"
    if [[ -f "$target" ]]; then
      bm_step "S=$rung already built"
      continue
    fi
    bm_step "S=$rung"
    # Keep the 9 fixed columns plus the first `rung` sample columns. The
    # #CHROM line is truncated identically so the header matches the body.
    bm_cat_vcf "$base.gz" | awk -F'\t' -v s="$rung" 'BEGIN { OFS = "\t" }
      /^##/ { print; next }
      {
        last = 9 + s
        if (NF < last) last = NF
        line = $1
        for (i = 2; i <= last; i++) line = line OFS $i
        print line
      }' | gzip -c > "$target"
    bm_write_provenance "$target" "$src" \
      "awk: first $FIXED_RECORDS data records, columns 1..$((9 + rung))" \
      "$FIXED_RECORDS" "$rung"
  done
}

# --------------------------------------------------------------------------
# Records ladder: fixed sample count, varying record count
# --------------------------------------------------------------------------
derive_records() {
  bm_banner "§3.1 records ladder from $RECORD_SOURCE"
  if ! bm_have_vcf "$RECORD_SOURCE"; then
    bm_warn "source not available: $RECORD_SOURCE — records ladder skipped.
Download it with: bash $BM_REPO/scripts/download_test_data.sh"
    return 0
  fi
  local src; src="$(bm_vcf "$RECORD_SOURCE")"
  local stem="${RECORD_SOURCE%%.*}"

  local samples
  samples="$(bm_cat_vcf "$src" | awk -F'\t' '
    /^#CHROM/ { print (NF > 9 ? NF - 9 : 0); exit }')"

  local rung
  for rung in $RECORD_RUNGS; do
    local target="$BM_DERIVED/${stem}_r${rung}.vcf.gz"
    if [[ -f "$target" ]]; then
      bm_step "V=$rung already built"
      continue
    fi
    bm_step "V=$rung"
    bm_cat_vcf "$src" | awk -v n="$rung" '
      /^#/ { print; next }
      kept < n { print; kept++; next }
      { exit }' | gzip -c > "$target"
    # Record how many data records actually landed: a rung larger than the
    # source is silently short, and the fitted slope must use the real count.
    local actual
    actual="$(gzip -dc "$target" | awk '!/^#/ { n++ } END { print n+0 }')"
    if (( actual < rung )); then
      bm_warn "V=$rung requested but the source only had $actual records"
    fi
    bm_write_provenance "$target" "$src" \
      "awk: first $rung data records, all columns" "$actual" "$samples"
  done
}

case "$WHICH" in
  samples) derive_samples ;;
  records) derive_records ;;
  both)    derive_samples; derive_records ;;
  *)       bm_die "usage: $0 [samples|records|both]" ;;
esac

bm_info "Derived inputs in $BM_DERIVED
Each has a .provenance.json recording source, checksums, recipe and real
record/sample counts. Cite those in the manuscript; the fixtures are not
biologically valid VCFs (see the header of this script)."
