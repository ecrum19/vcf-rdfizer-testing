#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <vcf-file-name-or-path>" >&2
  echo "Example: $0 test-larger.vcf.gz" >&2
  exit 2
fi

# Pass either a VCF basename from VCF-RDFizer/test/test_vcf_files/, or a path
# relative to the current directory/repository (absolute paths also work).
RDF_NAME="$1"
OUTPUT_DIR="vcf-rdfizer-testing/experiments"
DOCKER_LOCAL="vcf-rdfizer:local"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# Existing benchmark scripts run from the parent directory so both the
# VCF-RDFizer checkout and this repository can be addressed by name.
cd "$PROJECT_ROOT"

INPUT_RDF="vcf-rdfizer-testing/$RDF_NAME"

if [[ ! -f "$INPUT_RDF" ]]; then
  echo "RDF file not found: $INPUT_RDF" >&2
  exit 1
fi


python3 VCF-RDFizer/vcf_rdfizer.py \
  --mode compress \
  --rdf "$INPUT_RDF" \
  --rdf-compression none \
  --representations cottas \
  --artifact-compression none \
  --out "$OUTPUT_DIR" \
  --image vcf-rdfizer:local \
  --no-build