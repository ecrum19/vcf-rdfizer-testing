#!/usr/bin/env bash
# Indexed regional access — SPARQL against a coordinate-indexed VCF.
#
# A standalone investigation, not part of the suite: run_all.sh does not run
# it, and no profile includes it. Run it by hand, after 13_query_cost, on the
# host that holds 13's results. If 13 ran outside the biomedsem profile, set
# BM_QUERY_SMALL to the small input it used, so the graph can be found.
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
# The scan arm is timed on fewer windows than the others, deliberately: its
# cost does not depend on the window, so timing it on all 80 would measure one
# number 80 times. It gets BM_SCAN_WINDOWS_PER_SIZE windows of each size, as
# does any arm in BM_REGIONAL_THIN_ARMS. The equality reference still covers
# every window: it is a single whole-file pass that fills them all at once.
#
# Every engine is timed on every window. A region-restricted question costs
# Comunica, HDT and COTTAS about one second on the 10k-record fixture (measured
# on vcf-bench-1), not the 23-45 s they take on 13's whole-file questions, so
# the small scale is roughly an hour and needs no thinning.
#
# The scales follow 13_query_cost exactly, and read its variables, so the two
# experiments always describe the same inputs:
#
#   small   13's small input (BM_QUERY_SMALL)   every arm
#   slice   the 100,000-record HG005 slice      VCF arms + qlever, as 13's large
#   whole   the full HG005 file (opt-in)        VCF arms + qlever
#
# Usage:
#   ./14_regional_access.sh                      # small and slice
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

# Which scales to run. `small` and `slice` reuse the graphs 13_query_cost
# already converted; `whole` is the full HG005 file, where the comparison
# actually bites -- an index seek is independent of file size and a scan is not
# -- but it needs a whole-file graph that 13 does not build.
SCALES="${BM_REGIONAL_SCALES:-small slice}"
INPUT_SMALL="${BM_REGIONAL_SMALL:-${BM_QUERY_SMALL:-test-10k.vcf}}"
INPUT_SLICE="${BM_REGIONAL_SLICE:-HG005_GRCh38_r100000.vcf.gz}"
INPUT_WHOLE="${BM_REGIONAL_WHOLE:-HG005_GRCh38.vcf.gz}"

# Every engine at small scale, which is the only scale 13 runs them at. Above
# it, only qlever: on the 17M-triple slice HDT spent over ten minutes
# rebuilding its index and Comunica's endpoint crashed during start-up (see
# vcf-rdfizer's validation_runner _await_bind), and 13 has no numbers for them
# there to compare against. BM_REGIONAL_ARMS overrides every scale.
ALL_ARMS="cyvcf2-scan,cyvcf2-indexed,bcftools-indexed,comunica,hdt,cottas,qlever"
VCF_AND_QLEVER="cyvcf2-scan,cyvcf2-indexed,bcftools-indexed,qlever"
ARMS_SMALL="${BM_REGIONAL_ARMS_SMALL:-${BM_REGIONAL_ARMS:-$ALL_ARMS}}"
ARMS_SLICE="${BM_REGIONAL_ARMS_SLICE:-${BM_REGIONAL_ARMS:-$VCF_AND_QLEVER}}"
ARMS_WHOLE="${BM_REGIONAL_ARMS_WHOLE:-${BM_REGIONAL_ARMS:-$VCF_AND_QLEVER}}"
THIN_ARMS="${BM_REGIONAL_THIN_ARMS:-cyvcf2-scan}"

# --------------------------------------------------------------------------
# The image.
#
# The regional runner and the tabix package ship in the image, not in this
# harness, and VCF-RDFizer v3.1.0 has neither. A campaign pinned to v3.1.0
# therefore cannot run this experiment as it stands. BM_REGIONAL_IMAGE lets
# this experiment alone use an image that has them, while every other
# experiment stays on the session's image; bench.json then records THIS
# image's reference and digest for these cells, so the two provenances stay
# distinguishable rather than being blurred into one.
# --------------------------------------------------------------------------
if [[ -n "${BM_REGIONAL_IMAGE:-}" ]]; then
  BM_IMAGE_REF="$BM_REGIONAL_IMAGE"
  BM_IMAGE_MODE="experiment-override"
  BM_IMAGE_DIGEST="$(bm_image_digest)"
  bm_step "image for this experiment only: $BM_IMAGE_REF ($BM_IMAGE_DIGEST)"
fi

# Prints why the image cannot run this experiment, or nothing when it can.
# Checked before any cell, so an image that predates the runner is a stated
# skip rather than a failure after the setup has been paid for.
regional_image_problem() {
  local out
  if ! out="$(docker run --rm --entrypoint sh "$BM_IMAGE_REF" -c '
      runner=/opt/vcf-rdfizer/validation/regional_runner.py
      if test -f "$runner"; then
        grep -q -- "--thin-arms" "$runner" || echo "regional_runner.py predates --thin-arms"
      else
        echo "no regional_runner.py"
      fi
      command -v tabix >/dev/null 2>&1 || echo "no tabix"
      command -v bcftools >/dev/null 2>&1 || echo "no bcftools"' 2>&1)"; then
    printf 'image could not be started: %s\n' "$(printf '%s' "$out" | tail -1)"
    return 0
  fi
  printf '%s' "$out" | paste -sd ';' -
}

# --------------------------------------------------------------------------
# Locate the RDF artifact for a scale.
#
# The SPARQL side reuses what 13_query_cost already built rather than
# reconverting: the artifact is the same, and rebuilding it would add hours and
# a second provenance to reconcile. BM_REGIONAL_RDF_<SCALE> overrides.
# --------------------------------------------------------------------------
find_rdf_for_scale() {
  local scale="$1" input="$2" override=""
  case "$scale" in
    small) override="${BM_REGIONAL_RDF_SMALL:-}" ;;
    slice) override="${BM_REGIONAL_RDF_SLICE:-}" ;;
    whole) override="${BM_REGIONAL_RDF_WHOLE:-}" ;;
  esac
  if [[ -n "$override" ]]; then
    [[ -f "$override" ]] || bm_die "BM_REGIONAL_RDF override not found: $override"
    printf '%s\n' "$override"
    return 0
  fi

  # Only a graph converted from THIS scale's input will do: 13_query_cost also
  # holds the 10k-record graph, and using it would benchmark a different
  # dataset under this experiment's label. So candidates are matched on the
  # input's own name. Several matches are then replicates of one conversion --
  # 13 runs three, and the determinism cell shows repeated conversions are
  # byte-identical -- so the first is used and the choice is logged.
  local stem; stem="$(basename -- "$input")"; stem="${stem%.gz}"; stem="${stem%.vcf}"
  local base path
  local -a found=()
  for base in "$BM_RESULTS/13_query_cost" "$BM_RESULTS/04_scaling_records"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r path; do
      [[ -n "$path" ]] && found+=("$path")
    done < <(find -H "$base" -maxdepth 4 \( -name "$stem.nt.gz" -o -name "$stem.nt" \) 2>/dev/null | sort)
    (( ${#found[@]} > 0 )) && break
  done

  (( ${#found[@]} == 0 )) && return 0
  if (( ${#found[@]} > 1 )); then
    bm_step "${#found[@]} replicate conversions of $stem found; using the first:" >&2
  fi
  printf '%s\n' "${found[0]}"
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
    rdf="$(find_rdf_for_scale "$scale" "$input")"
    if [[ -z "$rdf" ]]; then
      bm_skip "$EXPERIMENT" "${scale}__no_rdf" \
        "no RDF artifact found for the SPARQL arms.
Run 13_query_cost first so its aggregate can be reused, or point at one with
  BM_REGIONAL_RDF_$(printf %s "$scale" | tr a-z A-Z)=/path/to/graph.nt.gz"
      return 0
    fi
    bm_step "reusing RDF artifact: $rdf"
  fi

  local cell_dir="$BM_RESULTS/$EXPERIMENT/$scale"
  local out_dir="$cell_dir/out"

  bm_banner "regional access — $scale scale: $(basename "$vcf")"
  bm_step "arms: $arms"
  bm_step "windows: $WINDOWS_PER_SIZE per size of [$WINDOW_SIZES], seed $SEED"
  bm_step "thin arms ($SCAN_WINDOWS_PER_SIZE per size): $THIN_ARMS"

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
        --thin-arms "$THIN_ARMS" \
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

if [[ "$BM_DRY_RUN" != "1" ]]; then
  problem="$(regional_image_problem)"
  if [[ -n "$problem" ]]; then
    for scale in $SCALES; do
      bm_skip "$EXPERIMENT" "${scale}__image" \
        "image $BM_IMAGE_REF cannot run this experiment ($problem). The regional
runner and tabix first ship in the release that includes VCF-RDFizer PR #23;
until then point this experiment at an image built from it:
  BM_REGIONAL_IMAGE=<image> ./14_regional_access.sh"
    done
    exit 0
  fi
fi

for scale in $SCALES; do
  case "$scale" in
    small) run_scale small "$INPUT_SMALL" "$ARMS_SMALL" ;;
    slice) run_scale slice "$INPUT_SLICE" "$ARMS_SLICE" ;;
    whole) run_scale whole "$INPUT_WHOLE" "$ARMS_WHOLE" ;;
    *)     bm_die "unknown scale: $scale (expected small, slice and/or whole)" ;;
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
