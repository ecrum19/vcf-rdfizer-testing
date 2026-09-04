#!/usr/bin/env bash
# Run VCF-RDFizer's validation mode against a compressed VCF and RDF dataset.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./test_validation.sh <input.vcf.gz> <input.nt.gz> [expanded|condensed] [output-dir] [validation-id]

Both input paths may be absolute or relative to the vcf-rdfizer-testing directory.

Arguments:
  input.vcf.gz       Source VCF used as the validation oracle (required).
  input.nt.gz        RDF generated from that VCF (required).
  representation     RDF sample representation: expanded (default) or condensed.
  output-dir         Directory in which validation-results/ is written
                     (default: validation-results).
  validation-id      Optional name for this validation run. By default, the VCF
                     filename (without .vcf.gz) is used.

Examples:
  ./test_validation.sh vcf_data/HG004_GRCh38.vcf.gz \
    experiments/HG004_GRCh38/HG004_GRCh38.nt.gz

  ./test_validation.sh vcf_data/HG004_GRCh38.vcf.gz \
    experiments/HG004_GRCh38/HG004_GRCh38.nt.gz \
    expanded validation-results HG004_GRCh38

Environment:
  VCF_RDFIZER_DIR                 Path to the VCF-RDFizer checkout. Defaults to
                                  the sibling ../vcf-rdfizer directory.
  VCF_RDFIZER_IMAGE               Optional Docker image passed to VCF-RDFizer.
  VCF_RDFIZER_VALIDATION_BUILD    "build" (default) to build the local image, or
                                  "no-build" to use an already available image.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if (( $# < 2 || $# > 5 )); then
  usage >&2
  exit 2
fi

TEST_REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DEFAULT_RDFIZER_DIR="$TEST_REPO/../vcf-rdfizer"

# Retain compatibility with checkouts that still use the former capitalization.
if [[ ! -f "$DEFAULT_RDFIZER_DIR/vcf_rdfizer.py" && -f "$TEST_REPO/../VCF-RDFizer/vcf_rdfizer.py" ]]; then
  DEFAULT_RDFIZER_DIR="$TEST_REPO/../VCF-RDFizer"
fi

VCF_RDFIZER_DIR="${VCF_RDFIZER_DIR:-$DEFAULT_RDFIZER_DIR}"
VCF_RDFIZER_CLI="$VCF_RDFIZER_DIR/vcf_rdfizer.py"

if [[ ! -f "$VCF_RDFIZER_CLI" ]]; then
  printf 'VCF-RDFizer entry point not found: %s\n' "$VCF_RDFIZER_CLI" >&2
  printf 'Set VCF_RDFIZER_DIR to the directory containing vcf_rdfizer.py.\n' >&2
  exit 1
fi

resolve_existing_file() {
  local requested_path="$1"
  local label="$2"
  local candidate_path

  if [[ "$requested_path" == /* ]]; then
    candidate_path="$requested_path"
  else
    candidate_path="$TEST_REPO/$requested_path"
  fi

  if [[ ! -f "$candidate_path" ]]; then
    printf '%s file not found: %s\n' "$label" "$candidate_path" >&2
    exit 1
  fi

  printf '%s/%s\n' "$(cd -- "$(dirname -- "$candidate_path")" && pwd -P)" "$(basename -- "$candidate_path")"
}

VCF_PATH="$(resolve_existing_file "$1" "VCF")"
RDF_PATH="$(resolve_existing_file "$2" "RDF")"
REPRESENTATION="${3:-expanded}"
OUTPUT_DIR_ARGUMENT="${4:-validation-results}"
VALIDATION_ID="${5:-}"

if [[ "$VCF_PATH" != *.vcf.gz ]]; then
  printf 'VCF input must have a .vcf.gz extension: %s\n' "$VCF_PATH" >&2
  exit 2
fi

if [[ "$RDF_PATH" != *.nt.gz ]]; then
  printf 'RDF input must have a .nt.gz extension: %s\n' "$RDF_PATH" >&2
  exit 2
fi

case "$REPRESENTATION" in
  expanded|condensed) ;;
  *)
    printf 'Sample representation must be "expanded" or "condensed": %s\n' "$REPRESENTATION" >&2
    exit 2
    ;;
esac

if [[ "$OUTPUT_DIR_ARGUMENT" == /* ]]; then
  OUTPUT_DIR="$OUTPUT_DIR_ARGUMENT"
else
  OUTPUT_DIR="$TEST_REPO/$OUTPUT_DIR_ARGUMENT"
fi

BUILD_MODE="${VCF_RDFIZER_VALIDATION_BUILD:-build}"
case "$BUILD_MODE" in
  build) BUILD_ARGUMENT="--build" ;;
  no-build) BUILD_ARGUMENT="--no-build" ;;
  *)
    printf 'VCF_RDFIZER_VALIDATION_BUILD must be "build" or "no-build".\n' >&2
    exit 2
    ;;
esac

command=(
  python3 "$VCF_RDFIZER_CLI"
  --mode validation
  --input "$VCF_PATH"
  --rdf "$RDF_PATH"
  --sample-representation "$REPRESENTATION"
  --out "$OUTPUT_DIR"
  "$BUILD_ARGUMENT"
)

if [[ -n "${VCF_RDFIZER_IMAGE:-}" ]]; then
  command+=(--image "$VCF_RDFIZER_IMAGE")
fi

if [[ -n "$VALIDATION_ID" ]]; then
  command+=(--validation-id "$VALIDATION_ID")
fi

printf 'Validating %s RDF against %s VCF (%s representation).\n' \
  "$RDF_PATH" "$VCF_PATH" "$REPRESENTATION"
printf 'Results will be written below: %s/validation\n' "$OUTPUT_DIR"

exec "${command[@]}"
