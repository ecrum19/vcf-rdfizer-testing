#!/usr/bin/env bash
# Index storage: what each route keeps on disk to answer queries.
#
# A standalone measurement, not part of the suite: run_all.sh does not run it,
# and no profile includes it. Run it by hand, on a host that holds the graphs
# the other experiments converted.
#
# The VCF route answers a question from the VCF compressed with bgzip, which
# tabix requires, plus its tabix index (.tbi). The RDF route answers it from a
# QLever index built from the tool's gzip-framed N-Triples; once built, the
# index needs neither the N-Triples nor the VCF. So the like-for-like storage
# comparison is the bgzipped VCF plus its .tbi against the QLever index. The
# .tbi alone is only offsets into the VCF, and comparing it with QLever's index
# would overstate the gap by the size of the VCF it points into.
#
# For each scale, the cell builds both indexes from the same inputs the other
# experiments used, records every size, build time and the QLever build's peak
# memory, and deletes the indexes again (BM_INDEX_KEEP=1 keeps them). QLever is
# built with VCF-RDFizer's validator arguments (-F nt -m 4G), the same as in
# 13_query_cost, 14_regional_access and 16_scale_retrieval; lib/index_storage.py
# does the measuring, inside the image, and writes out/index_storage.json.
#
# The scales, and where each input comes from:
#
#   slice   HG005_GRCh38_r100000.vcf.gz; N-Triples from 13_query_cost's large
#           cells (the first replicate, as 14 reuses it)
#   whole   HG005_GRCh38.vcf.gz; N-Triples from the scale store that
#           15_scale_prepare wrote and 16_scale_retrieval queries
#
# BM_INDEX_RDF_SLICE / BM_INDEX_RDF_WHOLE point at the N-Triples directly.
#
# The image needs bgzip, tabix and QLever's index builder. v3.1.0 has no tabix,
# so this experiment runs on the v3.3.1 release, like 14; its QLever is the
# same build (bfd5741) the v3.1.0 validator used. BM_INDEX_IMAGE overrides the
# image for this experiment alone, and bench.json records the one used.
#
# Usage:
#   BM_IMAGE_VERSION=3.3.1 ./19_index_storage.sh                 # slice and whole
#   BM_INDEX_SCALES=slice BM_IMAGE_VERSION=3.3.1 ./19_index_storage.sh
#
# The complete VCF takes about 15 minutes, about 8 GB of scratch space for its
# index, and 5-6 GB of memory; the slice takes under a minute.

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"
source "$(dirname -- "${BASH_SOURCE[0]}")/lib/scale.sh"

EXPERIMENT="19_index_storage"
SCALES="${BM_INDEX_SCALES:-slice whole}"
INPUT_SLICE="${BM_INDEX_SLICE:-HG005_GRCh38_r100000.vcf.gz}"
INPUT_WHOLE="${BM_INDEX_WHOLE:-HG005_GRCh38.vcf.gz}"
QLEVER_MEMORY="${BM_INDEX_QLEVER_MEMORY:-4G}"

if [[ -n "${BM_INDEX_IMAGE:-}" ]]; then
  BM_IMAGE_REF="$BM_INDEX_IMAGE"
  BM_IMAGE_MODE="experiment-override"
  BM_IMAGE_DIGEST="$(bm_image_digest)"
  bm_step "image for this experiment only: $BM_IMAGE_REF ($BM_IMAGE_DIGEST)"
fi

# Prints why the image cannot run this experiment, or nothing when it can.
index_image_problem() {
  local out
  if ! out="$(docker run --rm --entrypoint sh "$BM_IMAGE_REF" -c '
      for tool in bgzip tabix python3 gunzip; do
        command -v "$tool" >/dev/null 2>&1 || echo "no $tool"
      done
      test -x "${QLEVER_INDEX_BUILDER_BIN:-/opt/qlever/bin/qlever-index}" || echo "no qlever-index"
      test -x /usr/bin/time || echo "no /usr/bin/time"' 2>&1)"; then
    printf 'image could not be started: %s\n' "$(printf '%s' "$out" | tail -1)"
    return 0
  fi
  printf '%s' "$out" | paste -sd ';' -
}

# The N-Triples a scale's graph was converted to. The slice reuses 13's
# conversion, the whole VCF the scale store's, rather than converting again:
# the graph is the one the reported queries ran on.
find_rdf_for_scale() {
  local scale="$1" path
  case "$scale" in
    slice)
      if [[ -n "${BM_INDEX_RDF_SLICE:-}" ]]; then printf '%s\n' "$BM_INDEX_RDF_SLICE"; return 0; fi
      path="$(find -H "$BM_RESULTS/13_query_cost" -maxdepth 4 -path '*large__r*' \
        -name 'HG005_GRCh38_r100000.nt.gz' 2>/dev/null | sort | head -1)"
      ;;
    whole)
      if [[ -n "${BM_INDEX_RDF_WHOLE:-}" ]]; then printf '%s\n' "$BM_INDEX_RDF_WHOLE"; return 0; fi
      path="$BM_SCALE_STORE/whole/HG005_GRCh38/HG005_GRCh38.nt.gz"
      ;;
  esac
  [[ -n "$path" && -s "$path" ]] && printf '%s\n' "$path"
}

run_scale() {
  local scale="$1" input="$2"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "${scale}__missing" "input not available: $input"
    return 0
  fi
  local vcf rdf
  vcf="$(bm_vcf "$input")"
  rdf="$(find_rdf_for_scale "$scale")"
  if [[ -z "$rdf" || ! -s "$rdf" ]]; then
    bm_skip "$EXPERIMENT" "${scale}__no_rdf" "no N-Triples found for $scale.
Run 13_query_cost (slice) or 15_scale_prepare (whole) first, or set
  BM_INDEX_RDF_$(printf %s "$scale" | tr a-z A-Z)=/path/to/graph.nt.gz"
    return 0
  fi

  bm_banner "index storage — $scale: $(basename -- "$vcf")"
  bm_step "N-Triples: $rdf"

  # Mount the files' real paths: the corpus VCFs are symlinks to their upstream names.
  local vcf_real rdf_real
  vcf_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$vcf")"
  rdf_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$rdf")"
  local -a keep=()
  [[ "${BM_INDEX_KEEP:-0}" == "1" ]] && keep=(--keep)

  bm_run_raw "$EXPERIMENT" "$scale" -- \
    docker run --rm --init --user "$(id -u):$(id -g)" \
      -v "$vcf_real:/data/vcf/$(basename -- "$input"):ro" \
      -v "$rdf_real:/data/rdf/$(basename -- "$rdf"):ro" \
      -v "$BM_LIB_DIR/index_storage.py:/harness/index_storage.py:ro" \
      -v "$BM_RESULTS/$EXPERIMENT/$scale/out:/data/out" \
      --mount "type=volume,target=/work" \
      --entrypoint python3 \
      "$BM_IMAGE_REF" \
      /harness/index_storage.py \
        --vcf "/data/vcf/$(basename -- "$input")" \
        --nt "/data/rdf/$(basename -- "$rdf")" \
        --dataset "$scale" \
        --memory "$QLEVER_MEMORY" \
        --scratch /work \
        --out /data/out \
        "${keep[@]}"
}

if [[ "$BM_DRY_RUN" != "1" ]]; then
  problem="$(index_image_problem)"
  if [[ -n "$problem" ]]; then
    for scale in $SCALES; do
      bm_skip "$EXPERIMENT" "${scale}__image" \
        "image $BM_IMAGE_REF cannot run this experiment ($problem); use v3.3.1 or later:
  BM_IMAGE_VERSION=3.3.1 $0"
    done
    exit 0
  fi
fi

for scale in $SCALES; do
  case "$scale" in
    slice) run_scale slice "$INPUT_SLICE" ;;
    whole) run_scale whole "$INPUT_WHOLE" ;;
    *) bm_die "unknown scale: $scale (expected slice or whole)" ;;
  esac
done
