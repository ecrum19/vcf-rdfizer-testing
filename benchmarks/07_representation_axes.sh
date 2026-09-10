#!/usr/bin/env bash
# Plan §4.2 — the three configurability axes the original plan omitted.
#
#   --info-representation   structured | raw      cost axis
#   --header-representation structured | basic    cost axis
#   --vcf-version           auto | 4.1 .. 4.5     robustness axis
#
# All three trade triples for queryability in the same way
# --sample-representation does, and none of them were in the "96 configurations"
# the plan originally counted.
#
# INFO is per-record, so its cost scales with V rather than V x S. On a
# single-sample WGS file structuring it is plausibly MORE expensive than
# expanded samples, which is a genuinely useful result for anyone choosing
# settings and completes the "pay triples for queryability" story on a second
# axis.
#
# Usage: ./07_representation_axes.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="07_representation_axes"
REPS="${BM_REPS:-3}"

common_args() {
  printf '%s\n' \
    --rdf-storage-mode space-optimized \
    --hdt-strategy partitioned \
    --representations hdt \
    --rdf-compression none \
    --artifact-compression none \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
}

read_common() {
  BM_COMMON=()
  local token
  while IFS= read -r token; do BM_COMMON+=("$token"); done < <(common_args)
}
read_common

# --------------------------------------------------------------------------
# INFO representation. Two inputs: a single-sample WGS file (where INFO cost
# competes with sample cost) and the SV batch (whose records carry heavy INFO).
# --------------------------------------------------------------------------
bm_banner "§4.2 --info-representation (paired, $REPS reps)"

for input in HG005_GRCh38.vcf.gz HGSVC2.vcf.gz; do
  stem="${input%%.*}"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "info__${stem}__missing" "corpus input not available: $input"
    continue
  fi
  vcf="$(bm_vcf "$input")"
  for rep in $(seq 1 "$REPS"); do
    for info_rep in structured raw; do    # interleaved
      bm_run "$EXPERIMENT" "info__${stem}__${info_rep}__r${rep}" -- \
        --mode full --input "$vcf" \
        --info-representation "$info_rep" \
        "${BM_COMMON[@]}"
    done
  done
done

# --------------------------------------------------------------------------
# Header representation. Header cost is per-file rather than per-record, so a
# small input is enough to show the difference in emitted structure.
# --------------------------------------------------------------------------
bm_banner "§4.2 --header-representation"

HEADER_INPUT="${BM_HEADER_INPUT:-test-larger.vcf.gz}"
if bm_have_vcf "$HEADER_INPUT"; then
  vcf="$(bm_vcf "$HEADER_INPUT")"
  for header_rep in structured basic; do
    bm_run "$EXPERIMENT" "header__${header_rep}" -- \
      --mode full --input "$vcf" \
      --header-representation "$header_rep" \
      "${BM_COMMON[@]}"
  done
else
  bm_skip "$EXPERIMENT" "header__missing" "fixture not available: $HEADER_INPUT"
fi

# --------------------------------------------------------------------------
# VCF version conformance. The version selects the SHACL overlay, the
# flattened-tuple semantics and which FORMAT families exist, so cost and graph
# size are NOT comparable across versions. This is a robustness axis: show the
# version-dependent emitter behaviour actually changes.
#
# The corpus already spans 4.1 (1000G) and 4.2 (everything else). The 4.3/4.4/
# 4.5 cells need fixtures declaring those versions; 08_robustness.sh builds
# them under benchmarks/fixtures/ if they are absent.
# --------------------------------------------------------------------------
bm_banner "§4.2 --vcf-version conformance overlays"

FIXTURE_DIR="$BM_ROOT/fixtures"
for version in 4.1 4.2 4.3 4.4 4.5; do
  fixture="$FIXTURE_DIR/version_${version}.vcf"
  if [[ ! -f "$fixture" ]]; then
    bm_skip "$EXPERIMENT" "version__${version}__missing" \
      "fixture not built: $fixture (run ./08_robustness.sh fixtures)"
    continue
  fi
  bm_run "$EXPERIMENT" "version__${version}" -- \
    --mode full --input "$fixture" \
    --vcf-version "$version" \
    "${BM_COMMON[@]}"
done

# A file with no ##fileformat must convert under the 4.5 fallback WITHOUT
# emitting a vcfc:VCF4xFile class — it does not claim a version gate it cannot
# verify. Degrading honestly is itself a robustness result.
fallback="$FIXTURE_DIR/version_missing_declaration.vcf"
if [[ -f "$fallback" ]]; then
  bm_run "$EXPERIMENT" "version__fallback_undeclared" -- \
    --mode full --input "$fallback" \
    --vcf-version auto \
    "${BM_COMMON[@]}"
  bm_expect_ok
else
  bm_skip "$EXPERIMENT" "version__fallback_undeclared__missing" \
    "fixture not built (run ./08_robustness.sh fixtures)"
fi

bm_info "Done. Analyse with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/equivalence.py $EXPERIMENT --cell-filter info__ --margin 0.10

For the version cells, check metrics.csv's vcf_version and vcf_version_source
columns: the fallback run must record 'fallback', and every explicit run must
record 'forced'. Group any cost comparison BY VERSION; the overlays change what
is emitted, so cross-version costs are not comparable."
