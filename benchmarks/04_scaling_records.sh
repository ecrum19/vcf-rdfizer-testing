#!/usr/bin/env bash
# Plan §3.1 — cost model from the records ladder.
#
# This is the ONLY place records-scaling slopes are fitted, because it is the
# only place records vary with everything else held constant. One config, one
# source file, four rungs, one curve.
#
# Prerequisite: ./02_derive_ladders.sh records
#
# Usage: ./04_scaling_records.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="04_scaling_records"
RECORD_RUNGS="${BM_RECORD_RUNGS:-10000 100000 1000000}"
RECORD_SOURCE="${BM_RECORD_SOURCE:-HG005_GRCh38.vcf.gz}"
REPS="${BM_REPS:-3}"
stem="${RECORD_SOURCE%%.*}"

bm_banner "§3.1 records ladder ($REPS reps per rung)"

for rung in $RECORD_RUNGS; do
  input="${stem}_r${rung}.vcf.gz"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "r${rung}__missing" \
      "derived rung not built: $input (run ./02_derive_ladders.sh records)"
    continue
  fi
  vcf="$(bm_vcf "$input")"
  for rep in $(seq 1 "$REPS"); do
    bm_run "$EXPERIMENT" "r${rung}__rep${rep}" -- \
      --mode full \
      --input "$vcf" \
      --sample-representation expanded \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations hdt \
      --rdf-compression none \
      --artifact-compression none \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
done

# The full source file is the top of the ladder; include it when present.
if bm_have_vcf "$RECORD_SOURCE"; then
  vcf="$(bm_vcf "$RECORD_SOURCE")"
  for rep in $(seq 1 "$REPS"); do
    bm_run "$EXPERIMENT" "rfull__rep${rep}" -- \
      --mode full \
      --input "$vcf" \
      --sample-representation expanded \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations hdt \
      --rdf-compression none \
      --artifact-compression none \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
fi

bm_info "Done. Fit slopes with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/fit_scaling.py $EXPERIMENT --x records --y triples
  python3 $BM_ROOT/analysis/fit_scaling.py $EXPERIMENT --x triples --y wall_seconds

Report these as EMPIRICAL scaling exponents over the measured range, with CIs.
They are not algorithmic bounds and must not be generalized beyond the rungs
actually run."
