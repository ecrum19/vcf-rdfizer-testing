#!/usr/bin/env bash
# Start experiment 18 (converter comparison) on this host. The host needs only Docker with the
# Compose plugin; everything else runs in the containers compose.yaml declares.
#
#   CONV_DATA=/path/to/vcf_data benchmarks/converters/run.sh
#
# CONV_DATA must hold derived/HG005_GRCh38_r100000.vcf.gz and derived/1000G_10000r_s16.vcf.gz
# (made by 02_derive_ladders.sh). CONV_WORK (scratch) and BM_RESULTS (the cells) default to
# directories inside this checkout. Every container runs as the calling user, so nothing the
# experiment writes is owned by root.
set -euo pipefail
CONV="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONV_REPO="$(cd -- "$CONV/../.." && pwd -P)"
CONV_DATA="$(cd -- "${CONV_DATA:?set CONV_DATA to the directory that holds derived/<input>.vcf.gz}" && pwd -P)"
CONV_WORK="${CONV_WORK:-$CONV_REPO/.conv-work}"
BM_RESULTS="${BM_RESULTS:-$CONV_REPO/benchmarks/results}"
mkdir -p "$CONV_WORK" "$BM_RESULTS"
CONV_WORK="$(cd -- "$CONV_WORK" && pwd -P)"
BM_RESULTS="$(cd -- "$BM_RESULTS" && pwd -P)"
CONV_UID="$(id -u)"
CONV_GID="$(id -g)"
CONV_DOCKER_GID="$(stat -c %g /var/run/docker.sock)"
CONV_REPO_COMMIT="$(git -C "$CONV_REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
export CONV_REPO CONV_DATA CONV_WORK BM_RESULTS CONV_UID CONV_GID CONV_DOCKER_GID CONV_REPO_COMMIT

compose=(docker compose -f "$CONV/compose.yaml" --env-file "$CONV/pins.env")
"${compose[@]}" build runner
exec "${compose[@]}" run --rm runner "$@"
