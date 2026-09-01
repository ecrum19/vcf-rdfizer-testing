#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <vcf-file-name-or-path>" >&2
  echo "Example: $0 test-larger.vcf.gz" >&2
  exit 2
fi

# Pass either a VCF basename from VCF-RDFizer/test/test_vcf_files/, or a path
# relative to the current directory/repository (absolute paths also work).
VCF_NAME="$1"
OUTPUT_DIR="vcf-rdfizer-testing/experiments"
DOCKER_IMAGE="ecrum19/vcf-rdfizer:v2.1.0"
DOCKER_LOCAL="vcf-rdfizer:local"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# Existing benchmark scripts run from the parent directory so both the
# VCF-RDFizer checkout and this repository can be addressed by name.
cd "$PROJECT_ROOT"

if [[ "$VCF_NAME" == /* ]]; then
  INPUT_VCF="$VCF_NAME"
elif [[ -f "$VCF_NAME" ]]; then
  INPUT_VCF="$VCF_NAME"
elif [[ -f "vcf-rdfizer-testing/$VCF_NAME" ]]; then
  INPUT_VCF="vcf-rdfizer-testing/$VCF_NAME"
else
  INPUT_VCF="VCF-RDFizer/test/test_vcf_files/$VCF_NAME"
fi

if [[ ! -f "$INPUT_VCF" ]]; then
  echo "VCF file not found: $INPUT_VCF" >&2
  exit 1
fi

# docker pull "$DOCKER_IMAGE"

python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input "$INPUT_VCF" \
  --sample-representation condensed \
  --rdf-storage-mode space-optimized \
  --rdf-compression gzip,brotli \
  --representations hdt,cottas \
  --artifact-compression gzip,brotli \
  --hdt-strategy partitioned \
  --image "$DOCKER_LOCAL" \
  --out "$OUTPUT_DIR" \
  --no-build
