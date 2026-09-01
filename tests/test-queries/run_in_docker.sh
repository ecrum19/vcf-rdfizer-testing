#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="${VCF_QUERY_TEST_IMAGE:-vcf-rdfizer-query-tests:local}"
NODE_MEMORY_MB="${VCF_QUERY_NODE_MEMORY_MB:-8192}"
BUILD_IMAGE=1

if [[ "${1:-}" == "--no-build" ]]; then
  BUILD_IMAGE=0
  shift
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: tests/test-queries/run_in_docker.sh [--no-build] [RUN_SUITE_OPTIONS]

With no options, builds the image and runs the bundled edge-case fixture.
All remaining options are passed to run_suite.py. Paths must be under this
repository because the repository is the directory mounted in the container.

Examples:
  tests/test-queries/run_in_docker.sh
  tests/test-queries/run_in_docker.sh \
    --vcf vcf_data/example.vcf.gz \
    --rdf benchmark-results/example/rdf \
    --dataset-id example
EOF
  exit 0
fi

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required but was not found on PATH" >&2
  exit 127
}

if ((BUILD_IMAGE)); then
  docker build \
    --file "$SCRIPT_DIR/Dockerfile" \
    --tag "$IMAGE_NAME" \
    "$SCRIPT_DIR"
elif ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Docker image $IMAGE_NAME does not exist; omit --no-build first" >&2
  exit 2
fi

docker run --rm --init \
  --user "$(id -u):$(id -g)" \
  --env "NODE_OPTIONS=--max-old-space-size=$NODE_MEMORY_MB" \
  --volume "$REPOSITORY_ROOT:$REPOSITORY_ROOT" \
  --workdir "$REPOSITORY_ROOT" \
  "$IMAGE_NAME" \
  "$@"
