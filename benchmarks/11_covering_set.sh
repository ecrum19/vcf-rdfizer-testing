#!/usr/bin/env bash
# Plan §5.1 — the functional covering set.
#
# Not a cross product. Ten runs exercise every option VALUE and cover every
# legal option PAIR at least once. This is the correctness sweep and it belongs
# on SMALL inputs only.
#
# Rows 1-6 were the original table. It claimed full pair coverage but did not
# have it: `datasets.py coverage` reported 16 uncovered pairs once all six rows
# could actually run. Rows 7-10 close them, and the property is now checked
# rather than asserted -- see the verification note at the bottom.
#
# Constraints that shape the table (§1.2):
#
#   * --hdt-strategy single needs plain storage AND hdt without cottas. Read
#     hdt_strategy_rejection() in the wrapper: in full mode it refuses when
#     --rdf-storage-mode is space-optimized, and when cottas is among the
#     representations (that one used to be silently ignored, which meant a
#     benchmark cell measured partitioned HDT under a `single` label).
#     NOTHING ELSE constrains it. An earlier version of this comment claimed
#     row 2 was "the only legal home" for single; that was wrong, and it cost
#     three pairs of coverage. Row 7 pairs single with expanded, structured and
#     gzip on both compression axes, and exits 0 -- verified on the VM before
#     this row was added, not inferred from the code.
#   * Row 3 is where auto's HDT decision is actually exercised, because it
#     selects hdt. In rows without HDT (row 4) auto is a no-op, so a covering
#     set that only ever pairs auto with cottas does not test the policy.
#
# Usage: ./11_covering_set.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="11_covering_set"
INPUT="${BM_COVERING_INPUT:-test-1k.vcf}"

if ! bm_have_vcf "$INPUT"; then
  bm_die "covering-set input not available: $INPUT
This sweep belongs on a small fixture. The tool checkout ships
test/test_vcf_files/test-100.vcf, test-1k.vcf and test-10k.vcf."
fi
VCF="$(bm_vcf "$INPUT")"

bm_banner "§5.1 covering set on $(basename "$VCF")"

# row : sample-rep : info-rep : storage : rdf-comp : reprs : artifact-comp : hdt-strategy
ROWS="
1:expanded:structured:space-optimized:gzip:hdt,cottas:gzip:partitioned
2:condensed:raw:plain:brotli:hdt:brotli:single
3:expanded:raw:plain:brotli:hdt:gzip:auto
4:condensed:structured:space-optimized:gzip:cottas:brotli:auto
5:expanded:structured:space-optimized:brotli:hdt,cottas:brotli:partitioned
6:condensed:raw:plain:gzip:cottas:gzip:partitioned
7:expanded:structured:plain:gzip:hdt:gzip:single
8:condensed:raw:plain:gzip:hdt,cottas:gzip:auto
9:expanded:raw:space-optimized:gzip:hdt:gzip:partitioned
10:expanded:raw:plain:brotli:cottas:gzip:partitioned
"

for row in $ROWS; do
  IFS=':' read -r n sample_rep info_rep storage rdf_comp reprs artifact_comp strategy <<< "$row"

  bm_run "$EXPERIMENT" "row${n}" -- \
    --mode full \
    --input "$VCF" \
    --sample-representation "$sample_rep" \
    --info-representation "$info_rep" \
    --rdf-storage-mode "$storage" \
    --rdf-compression "$rdf_comp" \
    --representations "$reprs" \
    --artifact-compression "$artifact_comp" \
    --hdt-strategy "$strategy" \
    --validate \
    --validate-artifacts all \
    --validation-engine "${BM_VALIDATION_ENGINES:-all}" \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  bm_expect_ok
done

bm_info "Done. Verify coverage with:
  python3 $BM_ROOT/analysis/datasets.py coverage $EXPERIMENT

datasets.py coverage re-derives, from the recorded command lines, that every
option value appears and every option pair is covered — so an edit to the table
that breaks coverage is caught rather than assumed."
