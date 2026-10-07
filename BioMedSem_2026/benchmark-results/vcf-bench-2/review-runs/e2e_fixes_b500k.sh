#!/usr/bin/env bash
# End-to-end check of the validation fixes, in the scratch image built from the
# fix tree: NG131FQA1I's first 250,000 records, expanded, QLever, with the
# default (core) shapes batched at the 500k-triple default. Expect PASS where v3.1.0 reported MISMATCH (and,
# with shapes, exhausted memory). A watchdog stops the run and only the
# containers it started if available memory falls below 2 GB.
set -uo pipefail
R="$HOME/vrdev-test/review-runs"; T="$HOME/vrdev-test/validation-fixes"; P="$HOME/vrdev-test/venv/bin/python"
L="$R/review-runs.log"; out="$R/validate__NG131FQA1I__first250000__fixes_b500k"; slice="$1"
log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }
[[ -e "$out" ]] && { log "fixes: $out exists, not overwriting"; exit 1; }
mkdir -p "$out"; docker ps -q | sort > "$out/containers_before.txt"
cmd=("$P" "$T/vcf_rdfizer.py" --mode full --input "$slice" --sample-representation expanded
     --rdf-storage-mode space-optimized --rdf-compression gzip --representations none
     --validate --validation-engine qlever
     --image vcf-rdfizer:dev-validation-fixes --no-build --out "$out/out")
printf '%q ' "${cmd[@]}" > "$out/command.txt"; echo >> "$out/command.txt"
log "fixes validate start: $slice"
"${cmd[@]}" > "$out/stdout.log" 2> "$out/stderr.log" &
run=$!
while kill -0 "$run" 2>/dev/null; do
  avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  echo "$(date -u +%T) $avail" >> "$out/memavail_kb.tsv"
  if (( avail < 2000000 )); then
    log "fixes watchdog: MemAvailable ${avail} kB, stopping the run"
    kill "$run" 2>/dev/null
    comm -13 "$out/containers_before.txt" <(docker ps -q | sort) | xargs -r docker kill >/dev/null
    break
  fi
  sleep 10
done
wait "$run"; log "fixes validate exit $?"
