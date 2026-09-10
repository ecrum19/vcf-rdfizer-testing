#!/usr/bin/env bash
# Plan §2 — condensed vs expanded: negligible at one sample, decisive at a cohort.
#
# The claim is an INTERACTION between --sample-representation and sample count,
# so it is measured as one: a ladder in S with the record set held fixed, not
# two bars from two different files.
#
# Cost control that makes this cheap: emitted triples is DETERMINISTIC, so one
# run per cell gives the exact number with no repetitions and no error bars.
# Only the secondary metrics (wall time, peak RSS, peak workspace) need
# repetitions, and only on a few rungs. 7 rungs x 2 modes = 14 conversions on
# 10k-record inputs, plus 3 reps on the two endpoint rungs for timing.
#
# Prediction to test (docs/sample-representation-guide.md):
#   expanded  sample-layer structure ~ V x S x F     slope ~1 in S
#   condensed sample-layer structure ~ S + (V x F)   slope ~0 in S
#
# Prerequisite: ./02_derive_ladders.sh samples
#
# Usage:
#   ./03_sample_representation.sh
#   BM_TIMING_RUNGS="1 2504" BM_REPS=3 ./03_sample_representation.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="03_sample_representation"
RUNGS="${BM_SAMPLE_RUNGS:-1 4 16 64 256 1024 2504}"
FIXED_RECORDS="${BM_FIXED_RECORDS:-10000}"
TIMING_RUNGS="${BM_TIMING_RUNGS:-1 2504}"   # rungs that get repetitions
REPS="${BM_REPS:-3}"

# One conversion per (rung, mode) for the deterministic triple count.
bm_banner "§2 sample-representation ladder — structure (n=1 per cell)"

for rung in $RUNGS; do
  input="1000G_${FIXED_RECORDS}r_s${rung}.vcf.gz"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "s${rung}__missing" \
      "derived rung not built: $input (run ./02_derive_ladders.sh samples)"
    continue
  fi
  vcf="$(bm_vcf "$input")"
  for mode in expanded condensed; do
    bm_run "$EXPERIMENT" "s${rung}__${mode}__structure" -- \
      --mode full \
      --input "$vcf" \
      --sample-representation "$mode" \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations hdt \
      --rdf-compression none \
      --artifact-compression none \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
done

# Repetitions only where a timing comparison is actually reported: the S=1
# endpoint (the equivalence claim) and the top rung (the difference claim).
bm_banner "§2 endpoint timing ($REPS reps on rungs: $TIMING_RUNGS)"

for rung in $TIMING_RUNGS; do
  input="1000G_${FIXED_RECORDS}r_s${rung}.vcf.gz"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "s${rung}__timing__missing" "derived rung not built: $input"
    continue
  fi
  vcf="$(bm_vcf "$input")"
  for rep in $(seq 1 "$REPS"); do
    for mode in expanded condensed; do   # interleaved, as in §1
      bm_run "$EXPERIMENT" "s${rung}__${mode}__r${rep}" -- \
        --mode full \
        --input "$vcf" \
        --sample-representation "$mode" \
        --rdf-storage-mode space-optimized \
        --hdt-strategy partitioned \
        --representations hdt \
        --rdf-compression none \
        --artifact-compression none \
        --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
    done
  done
done

# §2.4 — two anchors on unsubsetted real files. Anchors, not the evidence.
bm_banner "§2.4 real-cohort anchors"

for pair in "1000G_phase3_chr20.vcf.gz:cohort" "HG004_GRCh38.vcf.gz:single"; do
  input="${pair%%:*}"; role="${pair##*:}"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "anchor_${role}__missing" "corpus input not available: $input"
    continue
  fi
  vcf="$(bm_vcf "$input")"
  for mode in expanded condensed; do
    bm_run "$EXPERIMENT" "anchor_${role}__${mode}" -- \
      --mode full \
      --input "$vcf" \
      --sample-representation "$mode" \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations hdt \
      --rdf-compression none \
      --artifact-compression none \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
done

bm_info "Done. Analyse with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/fit_scaling.py $EXPERIMENT --x samples --y triples --group mode --cell-filter __structure
  python3 $BM_ROOT/analysis/equivalence.py $EXPERIMENT --cell-filter s1__ --margin 0.10"

cat <<'NOTE'

Reporting reminders (§2.3):
  * Report the STRUCTURE ratio and the ARTIFACT-BYTE ratio in separate columns
    and label them differently. The guide's worked example gives ~1,070x on
    structure; final .hdt bytes shrink far less, because the scalar values
    persist inside vector literals and HDT's dictionary already recovers part
    of the repetition. Conflating them reads as a compression claim that the
    data does not support.
  * The S=1 cell is an equivalence claim. Use the same +/-10% margin framing as
    §1, and here it CAN be pre-registered — do that before running.
NOTE
