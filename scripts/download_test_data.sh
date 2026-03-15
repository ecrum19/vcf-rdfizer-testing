#!/usr/bin/env bash
set -euo pipefail

# Download location (can be overridden): DATA_DIR=... bash scripts/download_test_data.sh
DATA_DIR="${DATA_DIR:-vcf_data}"
mkdir -p "$DATA_DIR"

ts() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }

# Each entry:
# canonical_name|source_name|profile_url|size|label|download_mode|download_target
DATASETS=(
"NG1N86S6FC.vcf.gz|KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.sv.vcf.gz|https://my.pgp-hms.org/profile/hu416394|379 MB|Sequencing.com|mirror|https://f26290bdbc3bf08190edec227f21635c-291.collections.ac2it.arvadosapi.com/_/"
"NG131FQA1I.vcf.gz|NG131FQA1I.vcf.gz|https://my.pgp-hms.org/profile/huFFFE77|224 MB|Dante Labs|mirror|https://5aa905ff32eca70008e6d6d8aca1f238-200.collections.ac2it.arvadosapi.com/_/"
"NB72462M.vcf.gz|NB72462M.vcf.gz|https://my.pgp-hms.org/profile/huF7A4DE|341 MB|Nebula Genomics|mirror|https://531155966bc06bca5de62439c00ce64b-282.collections.ac2it.arvadosapi.com/_/"
"60820188475559.vcf.gz|60820188475559.filtered.snp.vcf.gz|https://my.pgp-hms.org/profile/hu1C1368|325 MB|Filtered SNPs|mirror|https://e17abc964664035c2efe6041b954e4f1-300.collections.ac2it.arvadosapi.com/_/"
"60820188474283.vcf.gz|60820188474283.snp.vcf.gz|https://my.pgp-hms.org/profile/hu6ABACE|222 MB|Dante Labs WGS|mirror|https://b42c5de31c35c2184a7119ddee4b049d-208.collections.ac2it.arvadosapi.com/_/"
"0GOOR_HG002.vcf.gz|0GOOR_HG002.vcf.gz|https://precision.fda.gov/challenges/10/results|69 MB|Genome in a Bottle Truth Challenge v2|direct|https://data.nist.gov/od/ds/ark:/88434/mds2-2336/submission_vcfs/0GOOR/0GOOR_HG002.vcf.gz"
)

WGET_PROGRESS_FLAGS=(--show-progress --progress=bar:force:noscroll)
WGET_FILTER_FLAGS=(--reject=index.html*)

find_downloaded_file() {
  local filename="$1"
  local match

  match="$(find "$DATA_DIR" -type f -name "$filename" -print | head -n 1 || true)"
  if [[ -n "$match" ]]; then
    printf '%s\n' "$match"
    return 0
  fi

  return 1
}

normalize_downloaded_file() {
  local canonical_name="$1"
  local source_name="$2"
  local source_path canonical_path

  canonical_path="$DATA_DIR/$canonical_name"
  if [[ -f "$canonical_path" ]]; then
    return 0
  fi

  if ! source_path="$(find_downloaded_file "$source_name")"; then
    log "Warning: could not locate downloaded file for $canonical_name (expected source name: $source_name)"
    return 1
  fi

  if [[ "$source_path" != "$canonical_path" ]]; then
    mv "$source_path" "$canonical_path"
    log "Normalized filename: $(basename "$source_path") -> $canonical_name"
  fi

  if source_path="$(find_downloaded_file "${source_name}.tbi")"; then
    if [[ "$source_path" != "${canonical_path}.tbi" ]]; then
      mv "$source_path" "${canonical_path}.tbi"
      log "Normalized index: $(basename "$source_path") -> ${canonical_name}.tbi"
    fi
  fi

  return 0
}

run_download() {
  local mode="$1"
  local target="$2"
  local canonical_name="$3"

  case "$mode" in
    mirror)
      (
        cd "$DATA_DIR"
        wget \
          --mirror \
          --no-parent \
          --no-host \
          --cut-dirs=1 \
          "${WGET_PROGRESS_FLAGS[@]}" \
          "${WGET_FILTER_FLAGS[@]}" \
          "$target"
      )
      ;;
    direct)
      (
        cd "$DATA_DIR"
        wget \
          "${WGET_PROGRESS_FLAGS[@]}" \
          -O "$canonical_name" \
          "$target"
      )
      ;;
    *)
      log "Unsupported download mode: $mode"
      return 1
      ;;
  esac
}

log "Starting downloads"
log "Target directory: $DATA_DIR"
log "Datasets: ${#DATASETS[@]}"
echo

i=0
for entry in "${DATASETS[@]}"; do
  i=$((i + 1))
  IFS='|' read -r canonical_name source_name profile size label mode target <<< "$entry"

  log "[$i/${#DATASETS[@]}] Dataset: $canonical_name"
  log "    Provider/label : $label"
  log "    Size (approx.) : $size"
  log "    Profile        : $profile"
  log "    Output dir     : $DATA_DIR"
  log "    Mode           : $mode"
  log "    Source         : $target"
  echo

  run_download "$mode" "$target" "$canonical_name"
  normalize_downloaded_file "$canonical_name" "$source_name" || true

  echo
  log "[$i/${#DATASETS[@]}] Completed: $canonical_name"
  echo "------------------------------------------------------------"
done

log "All downloads completed successfully."
