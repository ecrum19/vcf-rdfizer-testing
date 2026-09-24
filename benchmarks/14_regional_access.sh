#!/usr/bin/env bash
# Indexed regional access — SPARQL against a coordinate-indexed VCF.
#
# 13_query_cost pits SPARQL against cyvcf2 SCANNING the file, because none of
# Q1-Q13 is coordinate-restricted. That is internally consistent, and it is the
# one VCF access mode nobody uses for a selective question. Real VCF work
# seeks: bgzip + tabix, then `bcftools -r` or cyvcf2's region iterator, which
# reads a handful of BGZF blocks instead of the whole file.
#
# This experiment adds that arm and asks five region-restricted questions of
# every access path. Either outcome is publishable:
#
#   SPARQL still wins   the retrieval claim gets stronger than it is now
#   tabix wins          the paper says plainly that indexed VCF is the fastest
#                       route to coordinate-bounded retrieval, and that the RDF
#                       path's value is in joins and cross-resource questions --
#                       which is what the Discussion argues anyway
#
# Unlike every other experiment here, this one does not drive the wrapper CLI:
# the wrapper has no mode for it, so the cell runs the regional runner inside
# the pinned image directly, via bm_run_raw. Everything else about the cell --
# image digest, host, timings, the bench.json record -- is identical.
#
# ---------------------------------------------------------------------------
# WHAT THIS MEASURES, AND WHAT IT DOES NOT
# ---------------------------------------------------------------------------
# Measured per (arm, question, window, replicate): the wall time of answering
# ONE question about ONE window.
#
# Reported separately, never folded in: each side's one-time setup. On the VCF
# side that is bgzip + tabix; on the SPARQL side it is the engine's index build
# or load. Neither belongs in a per-question number, and both belong in the
# repeated-question view, which is where the lines cross if they cross.
#
# Not measured here at all: conversion. The graph has to exist first. Quote
# that from the conversion experiments rather than hiding it or omitting it.
#
# The scan arm is timed on fewer windows than the indexed arms, deliberately:
# its cost does not depend on the window, so timing it on all 80 would measure
# one number 80 times at ~11 s a go. Correctness is still checked on every
# window, because the equality reference is a single whole-file pass that fills
# every window at once.
#
# Usage:
#   ./14_regional_access.sh                      # slice scale, all arms
#   BM_REGIONAL_SCALES=slice ./14_regional_access.sh
#   BM_REGIONAL_ARMS="cyvcf2-indexed,bcftools-indexed,qlever" ./14_regional_access.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="14_regional_access"
REPLICATES="${BM_REPS:-3}"
WINDOW_SIZES="${BM_WINDOW_SIZES:-1000,100000,1000000,10000000}"
WINDOWS_PER_SIZE="${BM_WINDOWS_PER_SIZE:-20}"
SCAN_WINDOWS_PER_SIZE="${BM_SCAN_WINDOWS_PER_SIZE:-3}"
SEED="${BM_WINDOW_SEED:-20260923}"
QUERIES="${BM_REGIONAL_QUERIES:-r01_region_record_count,r02_region_variant_shape_counts,r03_region_titv,r04_region_filter_distribution,r05_region_sample_genotype_counts}"

# Which scales to run. `slice` reuses the 100,000-record HG005 slice that
# 13_query_cost already converted; `whole` is the full HG005 file, where the
# comparison actually bites -- an index seek is independent of file size and a
# scan is not.
SCALES="${BM_REGIONAL_SCALES:-slice}"

# Every arm at slice scale. At whole-file scale Comunica and HDT spawn one
# process per query, so they would measure process startup over a 657M-triple
# graph; qlever is the only engine worth the hours there.
ARMS_SLICE="${BM_REGIONAL_ARMS:-cyvcf2-scan,cyvcf2-indexed,bcftools-indexed,comunica,hdt,cottas,qlever}"
ARMS_WHOLE="${BM_REGIONAL_ARMS_WHOLE:-cyvcf2-scan,cyvcf2-indexed,bcftools-indexed,qlever}"

# --------------------------------------------------------------------------
# Locate the RDF artifact for a scale.
#
# The SPARQL side reuses what 13_query_cost already built rather than
# reconverting: the artifact is the same, and rebuilding it would add hours and
# a second provenance to reconcile. BM_REGIONAL_RDF_<SCALE> overrides.
# --------------------------------------------------------------------------
find_rdf_for_scale() {
  local scale="$1" override=""
  case "$scale" in
    slice) override="${BM_REGIONAL_RDF_SLICE:-}" ;;
    whole) override="${BM_REGIONAL_RDF_WHOLE:-}" ;;
  esac
  if [[ -n "$override" ]]; then
    [[ -f "$override" ]] || bm_die "BM_REGIONAL_RDF override not found: $override"
    printf '%s\n' "$override"
    return 0
  fi

  # Search every 13_query_cost cell rather than guessing its naming. Picking
  # the wrong graph here would benchmark a different dataset under this
  # experiment's label, so ambiguity is reported rather than resolved by
  # guessing: if more than one candidate turns up, the caller names one.
  local base="$BM_RESULTS/13_query_cost"
  [[ -d "$base" ]] || return 0
  local -a found=()
  local path
  while IFS= read -r path; do
    [[ -n "$path" ]] && found+=("$path")
  done < <(find "$base" -maxdepth 4 \( -name '*.nt.gz' -o -name '*.nt' \) 2>/dev/null | sort)

  if (( ${#found[@]} == 0 )); then
    return 0
  fi
  if (( ${#found[@]} == 1 )); then
    printf '%s\n' "${found[0]}"
    return 0
  fi
  bm_warn "more than one RDF artifact under $base; name the one this scale means:
$(printf '  %s\n' "${found[@]}")
  BM_REGIONAL_RDF_SLICE=<path>   or   BM_REGIONAL_RDF_WHOLE=<path>"
  return 0
}

run_scale() {
  local scale="$1" input="$2" arms="$3"

  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "${scale}__missing" "input not available: $input"
    return 0
  fi
  local vcf; vcf="$(bm_vcf "$input")"

  local rdf=""
  if printf '%s' "$arms" | grep -qE 'comunica|hdt|cottas|qlever'; then
    rdf="$(find_rdf_for_scale "$scale")"
    if [[ -z "$rdf" ]]; then
      bm_skip "$EXPERIMENT" "${scale}__no_rdf" \
        "no RDF artifact found for the SPARQL arms.
Run 13_query_cost first so its aggregate can be reused, or point at one with
  BM_REGIONAL_RDF_SLICE=/path/to/graph.nt.gz (or ..._WHOLE)"
      return 0
    fi
    bm_step "reusing RDF artifact: $rdf"
  fi

  local cell_dir="$BM_RESULTS/$EXPERIMENT/$scale"
  local out_dir="$cell_dir/out"

  bm_banner "regional access — $scale scale: $(basename "$vcf")"
  bm_step "arms: $arms"
  bm_step "windows: $WINDOWS_PER_SIZE per size of [$WINDOW_SIZES], seed $SEED"

  # Mounts. The RDF directory is only mounted when a SPARQL arm needs it, so a
  # VCF-only run does not depend on a converted graph existing.
  local -a mounts=()
  mounts+=(-v "$(cd -- "$(dirname -- "$vcf")" && pwd -P):/data/vcf:ro")
  local -a rdf_args=()
  if [[ -n "$rdf" ]]; then
    mounts+=(-v "$(cd -- "$(dirname -- "$rdf")" && pwd -P):/data/rdf:ro")
    local rdf_format="nt"
    case "$rdf" in
      *.nt.gz)  rdf_format="nt.gz" ;;
      *.hdt)    rdf_format="hdt" ;;
      *.cottas) rdf_format="cottas" ;;
    esac
    rdf_args=(--rdf "/data/rdf/$(basename -- "$rdf")" --rdf-format "$rdf_format")
  fi

  bm_run_raw "$EXPERIMENT" "$scale" -- \
    docker run --rm --init \
      "${mounts[@]}" \
      -v "$out_dir:/data/regional" \
      "$BM_IMAGE_REF" \
      /opt/pycottas-venv/bin/python \
      /opt/vcf-rdfizer/validation/regional_runner.py \
        --vcf "/data/vcf/$(basename -- "$vcf")" \
        "${rdf_args[@]}" \
        --representation expanded \
        --arms "$arms" \
        --queries "$QUERIES" \
        --window-sizes "$WINDOW_SIZES" \
        --windows-per-size "$WINDOWS_PER_SIZE" \
        --scan-windows-per-size "$SCAN_WINDOWS_PER_SIZE" \
        --replicates "$REPLICATES" \
        --seed "$SEED" \
        --index-kind auto \
        --results-dir /data/regional \
        --dataset-id "$scale" \
        --scratch-dir /work

  # A non-zero exit means the arms disagreed or an arm failed. Both are results
  # worth keeping, and neither is a reason to abandon the other scale.
  if [[ "${BM_LAST_RC:-0}" != "0" ]]; then
    bm_warn "$scale exited ${BM_LAST_RC}. If the arms disagreed, no speed number
from this scale is reportable until that is resolved:
  $out_dir/mismatches.json"
  fi
}

for scale in $SCALES; do
  case "$scale" in
    slice) run_scale slice "${BM_REGIONAL_SLICE:-HG005_GRCh38_r100000.vcf.gz}" "$ARMS_SLICE" ;;
    whole) run_scale whole "${BM_REGIONAL_WHOLE:-HG005_GRCh38.vcf.gz}" "$ARMS_WHOLE" ;;
    *)     bm_die "unknown scale: $scale (expected 'slice' and/or 'whole')" ;;
  esac
done

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/datasets.py regional $EXPERIMENT

The dataset reports, per arm and window size: median seconds per question, the
ratio against the indexed VCF arms, each side's one-time setup, and the
repeated-question break-even. Check agrees_with_reference is true everywhere
before quoting any speed -- a number from arms that disagree is a bug, not a
result."
