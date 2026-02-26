#!/usr/bin/env bash
set -euo pipefail

# Download location (can be overridden): DATA_DIR=... bash scripts/download_test_data.sh
DATA_DIR="${DATA_DIR:-vcf_data}"
mkdir -p "$DATA_DIR"

# Nice log helpers
ts() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }

# Each entry:
# name | profile_url | size | label | wget_command
DATASETS=(
"KatSuricata-NG1N86S6FC-30x-WGS-Sequencing_com-03-18-24.sv.vcf.gz|https://my.pgp-hms.org/profile/hu416394|379 MB|Sequencing.com|wget --mirror --no-parent --no-host --cut-dirs=1 'https://f26290bdbc3bf08190edec227f21635c-291.collections.ac2it.arvadosapi.com/_/'"
"68484e35b07b48cd9eed01d1a0110ff0.vcf|https://my.pgp-hms.org/profile/huF85C76|2.91 GB|Nebula Genomics|wget --mirror --no-parent --no-host --cut-dirs=1 'https://362f852df716087509351bc471a93b83-2026.collections.ac2it.arvadosapi.com/_/'"
"YP3ZQ.snpeff.vep.vcf|https://my.pgp-hms.org/profile/huF85C76|6.49 GB|30x WGS|wget --mirror --no-parent --no-host --cut-dirs=1 'https://e2050a5a973b05c215ce43af953062c0-4404.collections.ac2it.arvadosapi.com/_/'"
"NG131FQA1I.vcf.gz|https://my.pgp-hms.org/profile/huFFFE77|224 MB|Dante Labs|wget --mirror --no-parent --no-host --cut-dirs=1 'https://5aa905ff32eca70008e6d6d8aca1f238-200.collections.ac2it.arvadosapi.com/_/'"
"NB72462M.vcf.gz|https://my.pgp-hms.org/profile/huF7A4DE|341 MB|Nebula Genomics|wget --mirror --no-parent --no-host --cut-dirs=1 'https://531155966bc06bca5de62439c00ce64b-282.collections.ac2it.arvadosapi.com/_/'"
"60820188475559.filtered.snp.vcf.gz|https://my.pgp-hms.org/profile/hu1C1368|325 MB|Filtered SNPs|wget --mirror --no-parent --no-host --cut-dirs=1 'https://e17abc964664035c2efe6041b954e4f1-300.collections.ac2it.arvadosapi.com/_/'"
"60820188475559_SA_L001_R1_001.fastq.gz.10009.g.vcf.gz|https://my.pgp-hms.org/profile/hu1C1368|1.86 GB|30x WGS|wget --mirror --no-parent --no-host --cut-dirs=1 'https://4db2692220447fa6aeb6b949efde90e5-1329.collections.ac2it.arvadosapi.com/_/'"
"60820188474283.snp.vcf.gz|https://my.pgp-hms.org/profile/hu6ABACE|222 MB|Dante Labs WGS|wget --mirror --no-parent --no-host --cut-dirs=1 'https://b42c5de31c35c2184a7119ddee4b049d-208.collections.ac2it.arvadosapi.com/_/'"
)

# wget flags to ensure visible progress in common terminal environments.
# --show-progress prints a progress bar; --progress=bar:force:noscroll keeps it readable in CI logs.
WGET_PROGRESS_FLAGS=(--show-progress --progress=bar:force:noscroll)
# Avoid downloading directory listing artifacts like index.html while mirroring.
WGET_FILTER_FLAGS=("--reject=index.html*")

log "Starting downloads"
log "Target directory: $DATA_DIR"
log "Datasets: ${#DATASETS[@]}"
echo

i=0
for entry in "${DATASETS[@]}"; do
  i=$((i+1))
  IFS='|' read -r name profile size label cmd <<< "$entry"

  log "[$i/${#DATASETS[@]}] Dataset: $name"
  log "    Provider/label : $label"
  log "    Size (approx.) : $size"
  log "    Profile        : $profile"
  log "    Output dir     : $DATA_DIR"
  log "    Command        : $cmd"
  echo

  (
    cd "$DATA_DIR"
    # shellcheck disable=SC2086
    eval "$cmd" "${WGET_PROGRESS_FLAGS[@]}" "${WGET_FILTER_FLAGS[@]}"
  )

  echo
  log "[$i/${#DATASETS[@]}] Completed: $name"
  echo "------------------------------------------------------------"
done

log "All downloads completed successfully."
