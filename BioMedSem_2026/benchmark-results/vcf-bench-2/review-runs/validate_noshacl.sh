#!/usr/bin/env bash
# C3 rerun: paired value-level validation of NG131FQA1I's first 250,000 records on
# QLever, v3.1.0 (d3b34d5, image 3.1.0), with the shape layer off. The first attempt
# (validate__NG131FQA1I__first250000, kept) ran v3.1.0's in-memory shapes on the
# whole graph -- its gate weighs the 277 MB artifact, not the graph -- and starved
# the host of memory. A watchdog stops this run, and only the containers it
# started, if available memory falls below 2 GB.
set -uo pipefail
R="$HOME/vrdev-test/review-runs"; T="$R/vcf-rdfizer-d3b34d5"; P="$HOME/vrdev-test/venv/bin/python"
L="$R/review-runs.log"; out="$R/validate__NG131FQA1I__first250000__noshacl"; slice="$1"
log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }
[[ -e "$out" ]] && { log "noshacl: $out exists, not overwriting"; exit 1; }
mkdir -p "$out"; docker ps -q | sort > "$out/containers_before.txt"
cmd=("$P" "$T/vcf_rdfizer.py" --mode full --input "$slice" --sample-representation expanded
     --rdf-storage-mode space-optimized --rdf-compression gzip --representations none
     --validate --validation-engine qlever --no-shacl
     --image ecrum19/vcf-rdfizer:3.1.0 --no-build --out "$out/out")
printf '%q ' "${cmd[@]}" > "$out/command.txt"; echo >> "$out/command.txt"
log "noshacl validate start: $slice"
timeout 21600 "${cmd[@]}" > "$out/stdout.log" 2> "$out/stderr.log" &
run=$!
while kill -0 "$run" 2>/dev/null; do
  avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  echo "$(date -u +%T) $avail" >> "$out/memavail_kb.tsv"
  if (( avail < 2000000 )); then
    log "noshacl watchdog: MemAvailable ${avail} kB, stopping the run"
    kill "$run" 2>/dev/null
    comm -13 "$out/containers_before.txt" <(docker ps -q | sort) | xargs -r docker kill >/dev/null
    break
  fi
  sleep 10
done
wait "$run"; log "noshacl validate exit $?"
