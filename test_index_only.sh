#!/usr/bin/env bash
set -euo pipefail

# Edit these paths for the indexed artifacts you want to test.
HDT_INPUT="vcf-rdfizer-testing/experiments/0GOOR_HG002/0GOOR_HG002.hdt"
COTTAS_INPUT="vcf-rdfizer-testing/experiments/0GOOR_HG002/0GOOR_HG002.cottas"
OUTPUT_DIR="vcf-rdfizer-testing/testing-results/index-only"
DOCKER_IMAGE="vcf-rdfizer:local"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Build locally so the container includes the index-only COTTAS adapter.
# docker build --tag "$DOCKER_IMAGE" VCF-RDFizer

HDT_INDEX_MEMORY_LIMIT=512M python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode index \
  --hdt "$HDT_INPUT" \
  --image "$DOCKER_IMAGE" \
  --out "$OUTPUT_DIR" \
  --no-build

# python3 VCF-RDFizer/vcf_rdfizer.py \
#   --mode index \
#   --cottas "$COTTAS_INPUT" \
#   --image "$DOCKER_IMAGE" \
#   --out "$OUTPUT_DIR" \
#   --no-build
