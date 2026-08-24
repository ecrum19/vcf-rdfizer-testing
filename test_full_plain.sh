#!/usr/bin/env bash
set -euo pipefail

# Edit these paths for the test you want to run.
INPUT_VCF="VCF-RDFizer/test/test_vcf_files/test-larger.vcf.gz"
OUTPUT_DIR="vcf-rdfizer-testing/experiments"
DOCKER_IMAGE="ecrum19/vcf-rdfizer:v2.1.0"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

docker pull "$DOCKER_IMAGE"

python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input "$INPUT_VCF" \
  --rdf-storage-mode plain \
  --rdf-compression none \
  --representations hdt,cottas \
  --artifact-compression none \
  --hdt-strategy partitioned \
  --image "$DOCKER_IMAGE" \
  --out "$OUTPUT_DIR" \
  --no-build
