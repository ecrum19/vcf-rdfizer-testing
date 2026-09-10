#!/usr/bin/env bash
# Plan §4.1 — the keystone: configurability does not cost correctness.
#
# Every option is a different physical encoding of the SAME information. This is
# the experiment that makes configurability a feature rather than a menu of ways
# to get different answers.
#
# The tool already ships the query suite this needs. `--validate` runs Q1-Q13
# against a VCF-side oracle computed from the same input:
#   Q1  record density by contig and 1 Mb window
#   Q2  record-level allele shape classes
#   Q3  biallelic SNV transition/transversion counts
#   Q4  FILTER status and exact lexical value
#   Q5  per-sample genotype class counts        <- traverses the sample layer
#   Q6  genotype-derived (AN, AC, siteCount)    <- traverses the sample layer
#   Q7-Q13  header declarations, predicate/class inventory, identity digests
#
# Q5 and Q6 are the cells where `condensed` could have broken and did not.
# Report them explicitly rather than burying them in a uniform PASS table.
#
# Small input only: cross-engine agreement is the deliverable here, and
# --validation-engine all is affordable at this size and nowhere else (§5.2).
#
# Usage:
#   ./06_equivalence.sh
#   BM_EQUIV_INPUT=test-1k.vcf ./06_equivalence.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="06_equivalence"
INPUT="${BM_EQUIV_INPUT:-test-larger-multisample.vcf.gz}"
ENGINES="${BM_VALIDATION_ENGINES:-all}"

if ! bm_have_vcf "$INPUT"; then
  bm_die "equivalence input not available: $INPUT
This experiment needs a small multi-sample fixture so Q5/Q6 are exercised.
The tool checkout ships test/test_vcf_files/test-larger-multisample.vcf.gz."
fi
VCF="$(bm_vcf "$INPUT")"

bm_banner "§4.1 representation equivalence on $(basename "$VCF")"
bm_step "engines: $ENGINES  (targets: all produced artifacts)"

# --------------------------------------------------------------------------
# Encoding cells: storage mode x sample representation, validated end to end.
# Each run converts AND validates, so the oracle comparison is per-encoding.
# --------------------------------------------------------------------------
for storage in plain space-optimized; do
  for sample_rep in expanded condensed; do
    bm_run "$EXPERIMENT" "encoding__${storage}__${sample_rep}" -- \
      --mode full \
      --input "$VCF" \
      --sample-representation "$sample_rep" \
      --rdf-storage-mode "$storage" \
      --hdt-strategy partitioned \
      --representations hdt,cottas \
      --rdf-compression gzip \
      --artifact-compression none \
      --validate \
      --validate-artifacts all \
      --validation-engine "$ENGINES" \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
done

# --------------------------------------------------------------------------
# The mechanism check: is the chunked hdtc merge equivalent to one rdf2hdt pass?
#
# This is the one experiment --hdt-strategy single is still worth running. It
# is not a performance comparison — there is no size regime where single wins
# (§1.2) — it is the oracle that justifies partitioned being the default rather
# than merely convenient.
#
# The configuration is enforced, not merely recommended: single requires plain
# storage AND hdt without cottas. Anything else exits 2.
# --------------------------------------------------------------------------
bm_banner "§4.1 mechanism check: single-pass vs partitioned merge"

for strategy in single partitioned; do
  bm_run "$EXPERIMENT" "mechanism__hdt_${strategy}" -- \
    --mode full \
    --input "$VCF" \
    --sample-representation expanded \
    --rdf-storage-mode plain \
    --hdt-strategy "$strategy" \
    --representations hdt \
    --rdf-compression none \
    --artifact-compression none \
    --validate \
    --validate-artifacts all \
    --validation-engine "$ENGINES" \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  bm_expect_ok
done

# --------------------------------------------------------------------------
# Confirm the two refusals are refusals, not silent downgrades. A benchmark
# that quietly measures partitioned HDT under a `single` label is worse than
# one that fails, and this suite asserts the tool no longer allows it.
# --------------------------------------------------------------------------
bm_banner "§1.2 refusals are enforced, not silent"

bm_run "$EXPERIMENT" "refusal__single_with_cottas" -- \
  --mode full --input "$VCF" \
  --rdf-storage-mode plain --representations hdt,cottas \
  --rdf-compression none --hdt-strategy single
bm_expect_refusal "HDT-only run"

bm_run "$EXPERIMENT" "refusal__single_with_space_optimized" -- \
  --mode full --input "$VCF" \
  --rdf-storage-mode space-optimized --representations hdt \
  --rdf-compression none --hdt-strategy single
bm_expect_refusal "gzip aggregate"

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/datasets.py equivalence $EXPERIMENT

Every cell equal to the oracle is one quotable sentence: 'every configuration
answers all six biological queries identically to the source VCF.' Call out
Q5/Q6 separately — they are the sample-layer traversals."
