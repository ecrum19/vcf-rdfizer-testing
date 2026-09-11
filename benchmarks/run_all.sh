#!/usr/bin/env bash
# Run the whole suite in order, then collect everything.
#
# Sequential by design: one experiment at a time. Two concurrent runs invalidate
# every memory and timing number in the suite.
#
# A failing experiment does not stop the rest — each records its own results and
# the summary at the end says what did not finish.
#
# Usage:
#   ./run_all.sh              # everything
#   ./run_all.sh cheap        # skip the large-input experiments (01, 04, 05, 10)
#   ./run_all.sh smoke        # fast end-to-end pass: every cheap script, tiny inputs
#   ./run_all.sh 03 06 11     # only these

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

ALL="00 02 01 03 04 05 06 07 08 09 10 11 12 13"
CHEAP="00 02 03 06 07 08 09 11 12 13"

case "${1:-all}" in
  all)   SELECTED="$ALL" ;;
  cheap) SELECTED="$CHEAP" ;;
  smoke)
    # A fast end-to-end pass: does every script still run, and does the
    # analysis still consume what they write? It is NOT a measurement --
    # one replicate and tiny inputs answer "does this work", not "how fast".
    # Never report a number from a smoke run.
    #
    # `cheap` alone is not fast: several of its experiments default to
    # test-larger.vcf.gz (1.16M records) or HG005 (139 MB), which is hours.
    # Every value below is a default, so an explicit env var still wins.
    SELECTED="$CHEAP"
    export BM_REPS="${BM_REPS:-1}"
    export BM_SAMPLE_RUNGS="${BM_SAMPLE_RUNGS:-1 16}"
    export BM_TIMING_RUNGS="${BM_TIMING_RUNGS:-1 16}"
    export BM_FIXED_RECORDS="${BM_FIXED_RECORDS:-2000}"
    export BM_RECORD_RUNGS="${BM_RECORD_RUNGS:-10000}"
    export BM_ROBUSTNESS_INPUT="${BM_ROBUSTNESS_INPUT:-test-10k.vcf}"
    export BM_HEADER_INPUT="${BM_HEADER_INPUT:-test-10k.vcf}"
    export BM_EQUIV_INPUT="${BM_EQUIV_INPUT:-test-10k.vcf}"
    export BM_QUERY_SMALL="${BM_QUERY_SMALL:-test-1k.vcf}"
    export BM_QUERY_LARGE="${BM_QUERY_LARGE:-test-10k.vcf}"
    bm_warn "smoke profile: 1 replicate, tiny inputs. Results are not measurements."
    ;;
  *)     SELECTED="$*" ;;
esac

declare -a FAILED=()

for prefix in $SELECTED; do
  script="$(ls "$BM_ROOT/${prefix}"_*.sh 2>/dev/null | head -1)"
  if [[ -z "$script" ]]; then
    bm_warn "no script for prefix $prefix"
    continue
  fi
  bm_banner "$(basename "$script")"
  if bash "$script"; then
    :
  else
    bm_warn "$(basename "$script") exited non-zero"
    FAILED+=("$(basename "$script")")
  fi
done

bm_banner "Collecting"
python3 "$BM_ROOT/analysis/collect_metrics.py" --all || true

if (( ${#FAILED[@]} )); then
  printf '\nExperiments that exited non-zero:\n'
  printf '  %s\n' "${FAILED[@]}"
  printf 'Their cells are still recorded; check stderr.log under each.\n'
else
  printf '\nAll selected experiments completed.\n'
fi
