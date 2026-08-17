#!/usr/bin/env bash
set -euo pipefail

# Edit these paths for the test you want to run.
INPUT_VCF="../vcf-rdfizer-testing/vcf_data/0GOOR_HG002.vcf.gz"
OUTPUT_DIR="../vcf-rdfizer-testing/testing-results"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

python3 ../VCF-RDFizer/vcf_rdfizer.py \
  --mode full \
  --input "$INPUT_VCF" \
  --rdf-layout batch \
  --compression hdt \
  --hdt-strategy partitioned \
  --hdt-target-chunk-bytes 536870912 \
  --hdt-min-chunk-bytes 134217728 \
  --hdt-max-chunk-bytes 1073741824 \
  --out "$OUTPUT_DIR" \
  --keep-rdf \
  --build
