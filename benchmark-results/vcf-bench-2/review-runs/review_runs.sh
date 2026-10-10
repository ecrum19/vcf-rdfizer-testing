#!/usr/bin/env bash
# Two runs the JBMS review asks for, on the campaign's own release (v3.1.0, commit d3b34d5):
#   C2  the mutation score under the default (core) SHACL profile, with a queries-only rerun
#       that must reproduce the campaign's 96/113;
#   C3  paired value-level validation, on QLever, of one heterogeneous real file:
#       NG131FQA1I (PGP, Dante Labs) through its first 250,000 records, the corpus slice.
set -uo pipefail
R="$HOME/vrdev-test/review-runs"; T="$R/vcf-rdfizer-d3b34d5"; P="$HOME/vrdev-test/venv/bin/python"
L="$R/review-runs.log"
log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }

for profile in none core; do
  out="$R/mutation__$profile"
  [[ -e "$out/mutation-score.json" ]] && { log "mutation $profile already done"; continue; }
  mkdir -p "$out"; log "mutation $profile start"
  ( cd "$T"
    [[ "$profile" == none ]] || export VCF_RDFIZER_MUTATION_SHACL="$profile"
    VCF_RDFIZER_MUTATION_REPORT="$out/mutation-score.json" timeout 14400 "$P" -m unittest test.test_validation_mutation_unit
  ) > "$out/stdout.log" 2> "$out/stderr.log"
  log "mutation $profile exit $?"
done

out="$R/validate__NG131FQA1I__first250000"
slice="$1"
if [[ ! -e "$out/out" ]]; then
  mkdir -p "$out"; log "validate start: $slice"
  printf '%s\n' "$P $T/vcf_rdfizer.py --mode full --input $slice --sample-representation expanded --rdf-storage-mode space-optimized --rdf-compression gzip --representations none --validate --validation-engine qlever --image ecrum19/vcf-rdfizer:3.1.0 --no-build --out $out/out" > "$out/command.txt"
  ( timeout 21600 "$P" "$T/vcf_rdfizer.py" --mode full --input "$slice" --sample-representation expanded \
      --rdf-storage-mode space-optimized --rdf-compression gzip --representations none \
      --validate --validation-engine qlever --image ecrum19/vcf-rdfizer:3.1.0 --no-build --out "$out/out" ) \
    > "$out/stdout.log" 2> "$out/stderr.log"
  log "validate exit $?"
fi
log "done"
