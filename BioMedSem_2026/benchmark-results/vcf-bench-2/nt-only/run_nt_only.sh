#!/usr/bin/env bash
# N-Triples-only rerun of the 100,000-record HG005 slice with VCF-RDFizer v3.1.0
# (d3b34d5, image ecrum19/vcf-rdfizer:3.1.0), the base campaign's release.
#   A  convert__repN : conversion only, as 13_query_cost/large minus HDT, COTTAS and
#                      validation; its wall time is the setup QLever needs.
#   B  validate__repN: 13_query_cost/large minus HDT and COTTAS, so QLever indexes the
#                      same gzip-framed N-Triples and cyvcf2 parses the VCF per question.
# Runs one at a time; writes only under this folder.
set -uo pipefail
R="$HOME/vrdev-test/nt-only"; T="$R/vcf-rdfizer-d3b34d5"; L="$R/run.log"
IN="$HOME/vcf-rdfizer-testing/vcf_data/derived/HG005_GRCh38_r100000.vcf.gz"
log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }
common=(--mode full --input "$IN" --sample-representation expanded --rdf-storage-mode space-optimized
        --representations none --rdf-compression gzip --artifact-compression none --spark-partitions 8
        --image ecrum19/vcf-rdfizer:3.1.0 --no-build)
run() {  # run <cell> [extra args...]
  local cell="$1"; shift; local out="$R/$cell"
  [[ -e "$out" ]] && { log "$cell exists, not overwriting"; return; }
  mkdir -p "$out"
  local cmd=(python3 "$T/vcf_rdfizer.py" "${common[@]}" "$@" --out "$out/out")
  printf '%q ' "${cmd[@]}" > "$out/command.txt"; echo >> "$out/command.txt"
  docker ps -q | sort > "$out/containers_before.txt"
  log "$cell start"
  local t0 t1 rc; t0=$(date +%s%N)
  "${cmd[@]}" > "$out/stdout.log" 2> "$out/stderr.log"; rc=$?
  t1=$(date +%s%N)
  awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.3f\n", (b - a) / 1e9 }' > "$out/wall_seconds.txt"
  log "$cell exit $rc wall $(cat "$out/wall_seconds.txt") s"
}
log "host $(hostname) image $(docker image inspect ecrum19/vcf-rdfizer:3.1.0 --format '{{.Id}}')"
for rep in 1 2 3; do run "convert__rep$rep"; done
for rep in 1 2 3; do run "validate__rep$rep" --validate --validate-artifacts all --validation-engine qlever --no-shacl; done
log "NT-ONLY-DONE"
