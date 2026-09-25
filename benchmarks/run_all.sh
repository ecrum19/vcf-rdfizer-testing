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
#   ./run_all.sh biomedsem    # the manuscript configuration: every claim, ~2-3 days
#   ./run_all.sh 03 06 11     # only these
#   ./run_all.sh 15 16        # optional experiments, never run by a profile
#
# The optional experiments (14, 15, 16) are in no profile. `all` does not
# include them, and it is not an oversight: each is a standalone investigation
# costing hours to days, and 16 depends on 15 having been run first.

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

ALL="00 02 01 03 04 05 06 07 08 09 10 11 12 13"
CHEAP="00 02 03 06 07 08 09 11 12 13"

# OPTIONAL experiments. Deliberately absent from ALL, CHEAP and biomedsem:
# they are standalone investigations, not part of the manuscript campaign, and
# each costs hours to days. Nothing runs them unless they are named.
#
#   14  regional access -- windowed retrieval against indexed VCF readers
#   15  scale generation -- builds the large graphs 16 queries (~16 h at 657M)
#   16  scale retrieval  -- queries what 15 built, and never builds
#
# 15 and 16 are two halves of one experiment, split so the expensive half runs
# once. Run 15, then 16 as many times as you like.
OPTIONAL="14 15 16"

# A profile may be followed by an explicit experiment list, so one profile can
# be split across hosts: `run_all.sh biomedsem 05 06 10`. Without the shift the
# list was silently discarded and every host ran the whole suite.
case "${1:-all}" in
  all)   SELECTED="$ALL" ;;
  cheap) shift; SELECTED="${*:-$CHEAP}" ;;
  smoke)
    # A fast end-to-end pass: does every script still run, and does the
    # analysis still consume what they write? It is NOT a measurement --
    # one replicate and tiny inputs answer "does this work", not "how fast".
    # Never report a number from a smoke run.
    #
    # `cheap` alone is not fast: several of its experiments default to
    # test-larger.vcf.gz (1.16M records) or HG005 (139 MB), which is hours.
    # Every value below is a default, so an explicit env var still wins.
    shift; SELECTED="${*:-$CHEAP}"
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
    # The cells that ignore the rung parameters, because they deliberately run
    # whole real files: §2.4's anchors and §4.2's INFO inputs. Measured on one
    # smoke pass, §2.4 alone was 17.7h of that script's 17.8h while the eight
    # cells the rungs *did* shrink took 2.7 minutes. Point them at fixtures.
    # test-larger-multisample keeps the cohort/single contrast (2,504 samples
    # vs 1), and its expanded cell is still skipped by the cohort guard --
    # which exercises the guard too.
    export BM_ANCHOR_PAIRS="${BM_ANCHOR_PAIRS:-test-larger-multisample.vcf.gz:cohort test-10k.vcf:single}"
    export BM_INFO_INPUTS="${BM_INFO_INPUTS:-test-10k.vcf}"
    # One engine, not four. Validation setup is per engine per artifact, so
    # `all` multiplies a cheap graph by twelve engine startups.
    export BM_VALIDATION_ENGINES="${BM_VALIDATION_ENGINES:-comunica}"
    export BM_QUERY_ENGINES="${BM_QUERY_ENGINES:-comunica}"
    bm_warn "smoke profile: 1 replicate, fixtures instead of corpus files, one engine. Results are not measurements."
    ;;
  biomedsem)
    # The configuration behind the BioMedSem manuscript. Every claim in
    # benchmarking_suggestions.md is still supported; the cost is cut by
    # choosing where the evidence has to be expensive and where it does not.
    # Unlike `smoke`, these ARE measurements.
    #
    # Measured costs this is built from (see the plan's §5.4 run manifests):
    #   01 at default sizes/reps        57.8 h for 11 of 30 cells
    #   one HG005 cell                  12.3 h
    #   03's three real-file anchors    17.7 h, vs 3.6 min on the fixture
    #   06 on a 10k fixture, 1 engine   92 min  (validation is overhead-bound)
    shift; SELECTED="${*:-$ALL}"

    # C1 -- replicates bound the CI and variance is a machine property (sd was
    # ~1% of the mean), so buy the corridor on the cheap size and run the large
    # one once as a size check. Drops the 397 MB size entirely: §3's ladder
    # covers the size trend far more cheaply than a third paired arm.
    export BM_REPS="${BM_REPS:-3}"
    export BM_REPS_AT_SCALE="${BM_REPS_AT_SCALE:-1}"
    export BM_SIZES="${BM_SIZES:-HG005_GRCh38_r100000.vcf.gz test-larger.vcf.gz}"

    # C2 -- the ladder is the evidence and it is cheap. The §2.4 anchors are
    # explicitly "anchors, not the evidence", and the multisample fixture makes
    # the same cohort-vs-single contrast at 2,504 samples.
    export BM_ANCHOR_PAIRS="${BM_ANCHOR_PAIRS:-test-larger-multisample.vcf.gz:cohort test-10k.vcf:single}"

    # C4 breadth -- features, not file length; one real file still whole.
    export BM_CORPUS_MAX_RECORDS="${BM_CORPUS_MAX_RECORDS:-250000}"
    export BM_CORPUS_WHOLE="${BM_CORPUS_WHOLE:-NG1N86S6FC.vcf.gz}"

    # C4 feasibility -- the claim is that it COMPLETES under a memory cap. A
    # 1M-record ladder input demonstrates that; the 397 MB file only makes it
    # slower to demonstrate.
    export BM_FEASIBILITY_INPUT="${BM_FEASIBILITY_INPUT:-HG005_GRCh38_r1000000.vcf.gz}"

    # C4/C5 validation -- buy cross-engine agreement once, where it IS the
    # claim (§4.1), and run one engine everywhere else. Validation cost is
    # engine setup x artifacts x queries, so this is the dominant saving.
    export BM_EQUIV_ENGINES="${BM_EQUIV_ENGINES:-all}"
    export BM_EQUIV_INPUT="${BM_EQUIV_INPUT:-test-10k.vcf}"
    export BM_VALIDATION_ENGINES="${BM_VALIDATION_ENGINES:-comunica}"
    export BM_QUERY_SMALL="${BM_QUERY_SMALL:-test-10k.vcf}"
    export BM_QUERY_LARGE="${BM_QUERY_LARGE:-HG005_GRCh38_r100000.vcf.gz}"

    # C4 robustness -- round-trip, determinism and idempotence are PROPERTIES,
    # not timings. The default test-larger.vcf.gz means four conversions of
    # 1.16M records (~20h) to prove things a 100k-record input proves just as
    # well, while still being large enough to span multiple chunks.
    export BM_ROBUSTNESS_INPUT="${BM_ROBUSTNESS_INPUT:-HG005_GRCh38_r100000.vcf.gz}"

    # C4 axes -- reuse the derived ladder rather than whole corpus files.
    export BM_INFO_INPUTS="${BM_INFO_INPUTS:-HGSVC2.vcf.gz HG005_GRCh38_r100000.vcf.gz}"
    export BM_HEADER_INPUT="${BM_HEADER_INPUT:-HG005_GRCh38_r100000.vcf.gz}"

    bm_step "biomedsem profile: manuscript configuration; every claim covered"
    bm_step "  reps=$BM_REPS (at scale: $BM_REPS_AT_SCALE)  corpus truncated to $BM_CORPUS_MAX_RECORDS records (whole: $BM_CORPUS_WHOLE)"
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
  # Say so out loud. An optional experiment is never reached by a profile, so
  # if one is running, someone asked for it -- and should be told what it costs.
  case " $OPTIONAL " in
    *" $prefix "*)
      bm_warn "$prefix is an OPTIONAL experiment: it is in no profile and can run for hours."
      ;;
  esac
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
