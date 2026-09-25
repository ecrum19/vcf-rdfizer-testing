#!/usr/bin/env bash
# OPTIONAL — build the large graphs that 16_scale_retrieval.sh queries.
#
# This is the GENERATION half of the scale experiment, and it is separate from
# the querying half on purpose. Building the whole HG005 graph is a ~16 h job;
# the questions we actually want to ask of it take minutes. Folding the two
# together, as 13_query_cost.sh does, means every replicate and every new
# engine re-pays the build. Here the build happens once, its artifacts are
# written to a persistent store, and any number of later query runs read them.
#
# ---------------------------------------------------------------------------
# WHY THE STORE LIVES OUTSIDE benchmarks_outputs
# ---------------------------------------------------------------------------
# $BM_RESULTS gets archived, moved and pruned between campaigns -- freeing disk
# by deleting out/<dataset>/ is a normal thing to do there, and it has been done
# in this project before. A 16 h artifact must not be inside a tree anyone would
# reasonably clear. BM_SCALE_STORE defaults to a sibling of vcf_data instead.
# The cell that produced it still lands in $BM_RESULTS with the usual bench.json,
# so provenance is recorded exactly as every other experiment records it.
#
# ---------------------------------------------------------------------------
# THE IMAGE IS PINNED, AND THAT IS A RESULT-INTEGRITY CHOICE
# ---------------------------------------------------------------------------
# Generation runs on the PUBLISHED release image (default ecrum19/vcf-rdfizer:3.1.0),
# never on a local build, so the graph is produced by the same code that
# produced the manuscript's Figure 6 data. The query half may run a newer image
# -- it needs --validation-queries, which postdates v3.1.0 -- and that
# asymmetry is fine precisely because the two halves are separate: a newer
# engine reading an older graph changes retrieval cost, not the graph.
#
# Usage:
#   ./15_scale_prepare.sh                 # every scale in BM_SCALE_SET
#   ./15_scale_prepare.sh r1000000        # one scale
#   BM_SCALE_REPRS=hdt ./15_scale_prepare.sh whole
#
# Idempotent: a scale whose manifest is already complete is skipped, so an
# interrupted campaign is resumed by re-running the same command.

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"
source "$(dirname -- "${BASH_SOURCE[0]}")/lib/scale.sh"

EXPERIMENT="15_scale_prepare"

bm_scale_require_pinned_image

WANTED="${*:-$(bm_scale_ids)}"

bm_banner "§scale generation: $WANTED  ->  $BM_SCALE_STORE"
bm_step "image: $BM_IMAGE_REF ($(bm_image_digest))"

for scale in $WANTED; do
  input="$(bm_scale_input "$scale")" || bm_die "unknown scale: $scale
Known scales: $(bm_scale_ids)
Add one with BM_SCALE_SET=\"<id>:<input.vcf.gz> ...\"."

  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "$scale" "input not available: $input"
    continue
  fi
  vcf="$(bm_vcf "$input")"

  store="$BM_SCALE_STORE/$scale"
  if bm_scale_manifest_complete "$scale"; then
    bm_step "$scale: already built ($(bm_scale_manifest_field "$scale" triples) triples) -- skipping"
    continue
  fi
  if [[ -e "$store" ]]; then
    bm_die "$store exists but its manifest is incomplete.
A previous build was interrupted. Remove it and re-run, or keep it and point
BM_SCALE_STORE elsewhere:
  rm -rf $store"
  fi
  mkdir -p "$store"

  bm_step "$scale: building from $(basename "$vcf") into $store"

  # Same conversion configuration as 13_query_cost.sh's large cell, so a
  # retrieval number taken here is comparable with Figure 6's rather than
  # measuring a differently-built graph. --no-shacl for the same reason it
  # gives there: the shape layer is a fixed per-run cost belonging to neither
  # side of the comparison.
  bm_run_raw "$EXPERIMENT" "$scale" -- \
    python3 "$BM_TOOL" \
      --mode full \
      --input "$vcf" \
      --sample-representation expanded \
      --info-representation structured \
      --rdf-storage-mode space-optimized \
      --hdt-strategy partitioned \
      --representations "${BM_SCALE_REPRS:-hdt,cottas}" \
      --rdf-compression gzip \
      --artifact-compression none \
      --no-shacl \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}" \
      --image "$BM_IMAGE_REF" \
      --no-build \
      --out "$store"
  bm_record_outcome "built $scale"

  if [[ "${BM_LAST_DRY_RUN:-0}" == "1" ]]; then
    bm_step "$scale: dry run -- command recorded, nothing built, no manifest written"
    continue
  fi
  if [[ "$BM_LAST_RC" -ne 0 ]]; then
    bm_warn "$scale: build exited $BM_LAST_RC; no manifest written"
    continue
  fi
  bm_scale_write_manifest "$scale" "$vcf" "$BM_LAST_DIR"
  bm_step "$scale: $(bm_scale_manifest_field "$scale" triples) triples, artifacts in $store"
done

bm_info "Done. Inspect the store with:
  python3 $BM_ROOT/analysis/scale_store.py list

Then query it WITHOUT rebuilding:
  ./16_scale_retrieval.sh

Nothing in $BM_SCALE_STORE is regenerable in less than hours. It is deliberately
outside $BM_RESULTS so that archiving or pruning benchmark results cannot
destroy it."
