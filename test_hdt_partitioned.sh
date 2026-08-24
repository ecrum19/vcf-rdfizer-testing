#!/usr/bin/env bash
set -euo pipefail

# Edit these paths for the test you want to run.
INPUT_VCF="vcf-rdfizer-testing/vcf_data/"
RDF_INPUT="vcf-rdfizer-testing/test-results/test-larger/test-larger.nt.gz"
OUTPUT_DIR="vcf-rdfizer-testing/experiments"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# python3 VCF-RDFizer/vcf_rdfizer.py \
#   --mode full \
#   --input "$INPUT_VCF" \
#   --rdf-storage-mode space-optimized \
#   --rdf-compression none \
#   --representations hdt,cottas \
#   --artifact-compression none \
#   --hdt-strategy partitioned \
#   --out "$OUTPUT_DIR" \
#   --build

python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode compress \
  --rdf "$RDF_INPUT" \
  --rdf-compression none \
  --representations hdt \
  --artifact-compression none \
  --out "$OUTPUT_DIR" \
  --image vcf-rdfizer:local \
  --no-build