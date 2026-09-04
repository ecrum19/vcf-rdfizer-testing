#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 )); then
  echo "Usage: $0 <vcf-file-name-or-path> [more-vcf-files-or-paths ...]" >&2
  echo "Example: $0 test-larger.vcf.gz vcf_data/another-sample.vcf.gz" >&2
  exit 2
fi

# Pass one or more VCF basenames from VCF-RDFizer/test/test_vcf_files/, or
# paths relative to the invoking directory/repository (absolute paths work).
DOCKER_LOCAL="vcf-rdfizer:local"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
CALLER_DIR="$(pwd -P)"
OUTPUT_DIR="$SCRIPT_DIR/experiments"
RDFIZER_DIR="$PROJECT_ROOT/vcf-rdfizer"

if [[ ! -f "$RDFIZER_DIR/vcf_rdfizer.py" && -f "$PROJECT_ROOT/VCF-RDFizer/vcf_rdfizer.py" ]]; then
  RDFIZER_DIR="$PROJECT_ROOT/VCF-RDFizer"
fi

if [[ ! -f "$RDFIZER_DIR/vcf_rdfizer.py" ]]; then
  echo "VCF-RDFizer entry point not found: $RDFIZER_DIR/vcf_rdfizer.py" >&2
  exit 1
fi

resolve_vcf() {
  local requested_path="$1"
  local candidate_path

  if [[ "$requested_path" == /* ]]; then
    candidate_path="$requested_path"
  elif [[ -f "$CALLER_DIR/$requested_path" ]]; then
    candidate_path="$CALLER_DIR/$requested_path"
  elif [[ -f "$SCRIPT_DIR/$requested_path" ]]; then
    candidate_path="$SCRIPT_DIR/$requested_path"
  else
    candidate_path="$RDFIZER_DIR/test/test_vcf_files/$requested_path"
  fi

  if [[ ! -f "$candidate_path" ]]; then
    echo "VCF file not found: $candidate_path" >&2
    return 1
  fi

  printf '%s/%s\n' "$(cd -- "$(dirname -- "$candidate_path")" && pwd -P)" "$(basename -- "$candidate_path")"
}

INPUT_VCFS=()
for VCF_NAME in "$@"; do
  INPUT_VCFS+=("$(resolve_vcf "$VCF_NAME")")
done

for INPUT_VCF in "${INPUT_VCFS[@]}"; do
  printf 'Running all-compressions benchmark for: %s\n' "$INPUT_VCF"

  python3 "$RDFIZER_DIR/vcf_rdfizer.py" \
    --mode full \
    --input "$INPUT_VCF" \
    --sample-representation expanded \
    --rdf-storage-mode space-optimized \
    --rdf-compression gzip,brotli \
    --representations hdt,cottas \
    --artifact-compression gzip,brotli \
    --hdt-strategy partitioned \
    --image "$DOCKER_LOCAL" \
    --out "$OUTPUT_DIR" \
    --validate \
    --validate-artifacts all \
    --validation-engine all \
    --no-build
done
