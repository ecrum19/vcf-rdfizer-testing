#!/usr/bin/env bash
# Plan §1 — storage mode: same compute, much less disk.
#
# Paired comparison of --rdf-storage-mode plain vs space-optimized. Everything
# else is held fixed, including --hdt-strategy partitioned: `single` cannot read
# a gzip aggregate and is refused, so the strategy is a confound that has to be
# pinned, not a second factor (§1.2).
#
# Three input sizes, because the point is that the disk saving GROWS with input
# size while the time penalty stays flat. One size cannot show that.
#
# Repetitions are interleaved (p,s,p,s,...) rather than blocked, so thermal
# drift and page-cache state cannot land preferentially on one mode.
#
# Usage:
#   ./01_storage_mode.sh                 # default ladder, 5 reps
#   BM_REPS=3 ./01_storage_mode.sh
#   BM_SIZES="test-larger.vcf.gz" ./01_storage_mode.sh
#
# Results: results/01_storage_mode/<size>__<mode>__r<N>/

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="01_storage_mode"
REPS="${BM_REPS:-5}"

# Small -> medium -> large. Override with BM_SIZES to run a subset.
DEFAULT_SIZES="test-larger.vcf.gz HG005_GRCh38.vcf.gz NG1N86S6FC.vcf.gz"
SIZES="${BM_SIZES:-$DEFAULT_SIZES}"

bm_banner "§1 Storage mode (paired, $REPS reps, interleaved)"
bm_step "sizes: $SIZES"

for size in $SIZES; do
  if ! bm_have_vcf "$size"; then
    bm_skip "$EXPERIMENT" "${size%%.*}__missing" "input not available: $size"
    continue
  fi
  vcf="$(bm_vcf "$size")"
  stem="${size%%.*}"

  for rep in $(seq 1 "$REPS"); do
    # Interleave within each repetition: the pair is adjacent in time.
    for mode in plain space-optimized; do
      bm_run "$EXPERIMENT" "${stem}__${mode}__r${rep}" -- \
        --mode full \
        --input "$vcf" \
        --rdf-storage-mode "$mode" \
        --hdt-strategy partitioned \
        --representations hdt,cottas \
        --rdf-compression none \
        --artifact-compression none \
        --sample-representation expanded \
        --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
    done
  done
done

bm_info "Done. Analyse with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/equivalence.py $EXPERIMENT --margin 0.10
  python3 $BM_ROOT/analysis/fit_scaling.py $EXPERIMENT --x input_bytes --y peak_host_workspace --group storage"

cat <<'NOTE'

Reporting reminders (§1.1):
  * The disk metric is PEAK WORKSPACE, not final artifact bytes. Both modes
    emit the same triples, so a table of final sizes shows ~0% and looks like
    it refutes the claim. bench.json records peak_out_tree_bytes; the Docker
    volume used by the partitioned stage is reported separately by the tool in
    stages/partitioned/<sample>.json and collected by collect_metrics.py.
    Peak host footprint and peak volume footprint are different numbers.
  * Compare decoded triples or a canonicalized digest, never the raw .nt.gz
    checksum: space-optimized assembles a concatenated gzip stream and plain
    gzips one merged .nt, so the two are not byte-identical even though they
    decompress to the same N-Triples.
  * State when the ±10% equivalence margin was fixed. If it was chosen after
    seeing the data, say so; do not imply pre-registration that did not happen.
NOTE
