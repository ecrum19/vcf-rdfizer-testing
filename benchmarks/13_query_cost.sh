#!/usr/bin/env bash
# Plan §4.5 — SPARQL retrieval against a VCF parser, on identical work.
#
# The question a biological researcher actually asks: if I convert my VCF to
# RDF, what does it cost me to get an answer out compared with parsing the VCF?
#
# This needs almost no new machinery. The validation suite already computes
# every expected value TWICE — once by parsing the VCF with cyvcf2, once by
# querying the graph — so every validated run is already a like-for-like
# measurement on identical work, with the answers proven equal first. This
# script turns that byproduct into the experiment: repetitions, several engines,
# two graph scales, and setup separated from query time.
#
# ---------------------------------------------------------------------------
# THE COMPARISON THAT IS VALID, AND THE ONE THAT IS NOT
# ---------------------------------------------------------------------------
# benchmark.csv has one row per engine per query, with columns `wall_seconds`
# and `oracle_wall_seconds`. Those are NOT two measurements of the same thing:
#
#   wall_seconds         this ONE query, on this engine
#   oracle_wall_seconds  the parser's total for ALL queries, repeated on every
#                        row so the CSV needs no join
#
# A row-wise ratio therefore divides one query by twenty-seven. The only valid
# comparison is aggregate against aggregate — the sum of an engine's query
# seconds against the oracle total — which is what datasets.py querycost
# computes. There is no per-query oracle timing to be had today.
#
# ---------------------------------------------------------------------------
# WHAT IS BEING COMPARED, HONESTLY
# ---------------------------------------------------------------------------
# The two sides do not have the same cost shape, and that IS the finding:
#
#   parser  parse + census, paid in full on every invocation. No index.
#   SPARQL  setup once (index/load), then query. Setup amortizes; queries do not.
#
# So a single-question workload favours the parser and a repeated-question
# workload favours the graph, and the useful number is the BREAK-EVEN: how many
# repeated queries before the graph's setup has paid for itself. The analysis
# computes it. Reporting a bare "Nx faster" without saying which regime it came
# from is the mistake to avoid.
#
# Also true and worth stating: conversion cost is not in either column. The
# graph has to exist first. Quote it from §3 rather than folding it in here.
#
# Note: the query set is not selectable — the suite always runs its full set
# (preflight + count + core). The aggregate is therefore over all of them,
# which is a fairer basis than a hand-picked subset anyway.
#
# Usage:
#   ./13_query_cost.sh
#   BM_QUERY_ENGINES="comunica,qlever" BM_REPS=5 ./13_query_cost.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="13_query_cost"
REPS="${BM_REPS:-3}"
ENGINES="${BM_QUERY_ENGINES:-all}"

# Two scales, because the doc's own indicative numbers show the ordering is
# dominated by per-process startup on a fixture and says nothing about a
# cohort-sized graph. One scale would be a misleading result.
SMALL="${BM_QUERY_SMALL:-test-larger-multisample.vcf.gz}"
LARGE="${BM_QUERY_LARGE:-HG005_GRCh38.vcf.gz}"

run_scale() {
  local label="$1" input="$2" engines="$3"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "${label}__missing" "input not available: $input"
    return 0
  fi
  local vcf; vcf="$(bm_vcf "$input")"

  bm_banner "§4.5 $label scale: $(basename "$vcf")  engines=$engines"

  local rep
  for rep in $(seq 1 "$REPS"); do
    # Conversion and validation in one run: the oracle has to parse the same
    # file the graph was built from, and the suite guarantees that by
    # construction when it validates the artifact it just produced.
    bm_run "$EXPERIMENT" "${label}__r${rep}" -- \
      --mode full \
      --input "$vcf" \
      --sample-representation expanded \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations hdt,cottas \
      --rdf-compression gzip \
      --artifact-compression none \
      --validate \
      --validate-artifacts all \
      --validation-engine "$engines" \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  done
}

# Small scale: every engine, which is affordable here and nowhere else.
run_scale "small" "$SMALL" "$ENGINES"

# Large scale: qlever only. Comunica spawns one process per query, so at this
# size it measures process startup rather than retrieval — the docs say so
# explicitly, and burning hours to re-learn it is not a result.
run_scale "large" "$LARGE" "${BM_QUERY_LARGE_ENGINES:-qlever}"

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/datasets.py querycost $EXPERIMENT

The dataset reports, per engine and scale: median engine query seconds, median
oracle (cyvcf2) seconds for the same work, the ratio, setup seconds, and the
break-even repetition count. Equality of the answers is established by the
validation status in the same row — check it is PASS before quoting any speed."
