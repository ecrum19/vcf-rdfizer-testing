#!/usr/bin/env bash
# OPTIONAL — retrieval cost on graphs that already exist.
#
# This is the QUERYING half. It never builds a graph: it reads the store that
# 15_scale_prepare.sh wrote and refuses to run against a scale that is not
# there. That refusal is the point. The manuscript's Figure 6 comes from
# 13_query_cost.sh, where every replicate re-converts the input, so three
# replicates at 657M triples would spend ~48 h rebuilding the same graph to ask
# 33 minutes of questions. Here the build is paid once, by a different script,
# and the marginal cost of another engine, another artifact, another replicate
# or one more query is the cost of that query alone.
#
# ---------------------------------------------------------------------------
# EVERY AXIS IS SELECTABLE
# ---------------------------------------------------------------------------
#   BM_SCALE_QUERY_SCALES  which prepared graphs          (default: all in the store)
#   BM_SCALE_CELLS         engine:artifact pairs          (default: qlever:nt.gz)
#   BM_SCALE_QUERIES       which queries                  (default: core -- the thirteen)
#   BM_REPS                replicates                     (default: 3)
#
# So a single question against one artifact is:
#   BM_SCALE_QUERIES=q03_titv BM_REPS=1 ./16_scale_retrieval.sh r1000000
#
# and the full cross-engine comparison at one scale is:
#   BM_SCALE_CELLS="qlever:nt.gz comunica:nt.gz hdt:hdt cottas:cottas" \
#     ./16_scale_retrieval.sh r1000000
#
# ---------------------------------------------------------------------------
# WHY THE DEFAULT IS THE THIRTEEN CORE QUERIES AND NOT THE WHOLE SUITE
# ---------------------------------------------------------------------------
# Measured on the v3.1.0 17.1M-triple cell, per artifact: the thirteen core
# queries cost 17 s and the preflight set costs 201 s. Figure 6 reports the
# thirteen. Running the full suite to obtain them means paying 12x for numbers
# the figure does not contain, which at 657M triples is the difference between
# ~33 minutes and ~7 hours.
#
# A subset means the tool reports TIMING_ONLY rather than a validation verdict
# -- deliberately, see --validation-queries in the wrapper. Each selected query
# is still compared against the cyvcf2 oracle, so the protocol that Figure 6
# states ("result equality verified before any timing was compared") still
# holds. Pass BM_SCALE_QUERIES=all to get a verdict as well, at full cost.
#
# ---------------------------------------------------------------------------
# COMPARABILITY WITH FIGURE 6
# ---------------------------------------------------------------------------
# q01..q13 are byte-identical between v3.1.0 (which produced Figure 6) and the
# image this script runs. The two preflight_missing_token_conformance queries
# are NOT -- they were narrowed after v3.1.0 -- so preflight timings from this
# script must not be put beside Figure 6's. The core thirteen may be.
#
# Usage:
#   ./16_scale_retrieval.sh               # every prepared scale
#   ./16_scale_retrieval.sh r1000000      # one scale

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"
source "$(dirname -- "${BASH_SOURCE[0]}")/lib/scale.sh"

EXPERIMENT="16_scale_retrieval"
REPS="${BM_REPS:-3}"
QUERIES="${BM_SCALE_QUERIES:-core}"
CELLS="${BM_SCALE_CELLS:-qlever:nt.gz}"

# An engine that will not finish is worth refusing rather than discovering
# after six hours. comunica-sparql-file holds the graph in memory; on the 0.96M
# fixture it already needed 11.7-12.5 s of setup, and nothing in the campaign
# has run it above 17.1M. The threshold is a documented judgement, not a
# measurement, so it is overridable -- and a refusal is RECORDED as a cell, so
# "we did not run it" stays visible in the dataset instead of looking like an
# omission.
BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES="${BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES:-50000000}"

# Disk, which is the constraint that actually bites at this size.
#
# Only a plain .nt artifact is queried in place; every other format is
# decompressed to N-Triples inside the container before an engine sees it
# (DIRECT_FORMATS in the validation runner is exactly {"nt"}). So querying the
# 657M-triple .nt.gz materializes the whole graph as text.
#
# The constant is measured, not guessed: the v3.1.0 whole-HG005 build recorded
# chunk_input_bytes = 99,325,167,164 for 657,425,805 triples, i.e. 151 bytes of
# N-Triples per triple. QLever's index is allowed a further 50 B/triple, which
# is a rough upper bound rather than a measurement and is why the total is
# checked with a margin rather than exactly.
#
# Discovering this after a 16-hour build has already been paid would be the
# expensive way to learn it.
BM_SCALE_BYTES_PER_TRIPLE="${BM_SCALE_BYTES_PER_TRIPLE:-201}"
BM_SCALE_SKIP_DISK_CHECK="${BM_SCALE_SKIP_DISK_CHECK:-0}"

bm_scale_disk_ok() {
  local triples="$1" kind="$2" label="$3"
  [[ "$BM_SCALE_SKIP_DISK_CHECK" == "1" ]] && return 0
  [[ "$triples" == "unknown" || -z "$triples" ]] && return 0
  # A plain .nt is queried where it lies, so it needs index space only.
  local per_triple="$BM_SCALE_BYTES_PER_TRIPLE"
  [[ "$kind" == "nt" ]] && per_triple=50

  local need free
  need=$(( triples * per_triple ))
  free=$(( $(df -kP "$BM_SCALE_STORE" | awk 'NR==2 {print $4}') * 1024 ))
  if (( free < need )); then
    bm_skip "$EXPERIMENT" "$label" \
      "needs about $(( need / 1000000000 )) GB free to materialize and index \
$triples triples from a '$kind' artifact, and $(( free / 1000000000 )) GB is available. \
Free space, query a plain .nt artifact in place, or set BM_SCALE_SKIP_DISK_CHECK=1."
    return 1
  fi
  return 0
}

WANTED="${*:-}"
if [[ -z "$WANTED" ]]; then
  for scale in $(bm_scale_ids); do
    bm_scale_manifest_complete "$scale" && WANTED="$WANTED $scale"
  done
fi
[[ -n "${WANTED// /}" ]] || bm_die "no prepared graphs in $BM_SCALE_STORE.
Build one first -- it is the expensive half and it is a separate script:
  ./15_scale_prepare.sh r1000000"

bm_banner "§scale retrieval: scales=$WANTED cells=$CELLS queries=$QUERIES reps=$REPS"

for scale in $WANTED; do
  if ! bm_scale_manifest_complete "$scale"; then
    bm_skip "$EXPERIMENT" "${scale}__missing" \
      "no complete manifest for '$scale' in $BM_SCALE_STORE -- run 15_scale_prepare.sh first"
    continue
  fi

  triples="$(bm_scale_manifest_field "$scale" triples)"
  vcf="$(python3 -c '
import json, sys
print(json.load(open(sys.argv[1]))["sourceVcf"]["path"])
' "$(bm_scale_manifest "$scale")")"

  bm_step "$scale: $triples triples, source $(basename "$vcf")"

  for cell in $CELLS; do
    engine="${cell%%:*}"
    kind="${cell#*:}"

    artifact="$(bm_scale_artifact "$scale" "$kind")" || {
      bm_skip "$EXPERIMENT" "${scale}__${engine}__${kind}" \
        "the store has no '$kind' artifact for scale '$scale'"
      continue
    }

    # Feasibility guard, recorded rather than silent.
    if [[ "$engine" == "comunica" && "$triples" != "unknown" ]] \
       && (( triples > BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES )); then
      bm_skip "$EXPERIMENT" "${scale}__${engine}__${kind}" \
        "comunica-sparql-file loads the graph into memory; $triples triples is above the \
BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES=$BM_SCALE_MEMORY_ENGINE_MAX_TRIPLES ceiling. \
Raise it to run anyway."
      continue
    fi

    bm_scale_disk_ok "$triples" "$kind" "${scale}__${engine}__${kind}__disk" || continue

    for rep in $(seq 1 "$REPS"); do
      label="${scale}__${engine}__${kind//./_}__r${rep}"
      # bm_run_raw creates $BM_RESULTS/<exp>/<label>/out before the command
      # runs, which is what --out needs to exist.
      bm_run_raw "$EXPERIMENT" "$label" -- \
        python3 "$BM_TOOL" \
          --mode validation \
          --input "$vcf" \
          --rdf "$artifact" \
          --sample-representation expanded \
          --info-representation structured \
          --validation-engine "$engine" \
          --validation-queries "$QUERIES" \
          --validation-id "${scale}_${engine}_${rep}" \
          --image "$BM_IMAGE_REF" \
          --no-build \
          --out "$BM_RESULTS/$EXPERIMENT/$label/out"
      bm_record_outcome "$label"
    done
  done
done

bm_info "Done. Build the dataset with:
  python3 $BM_ROOT/analysis/scale_retrieval.py $EXPERIMENT

It reports, per scale/engine/artifact/query: median query seconds over the
replicates, engine setup seconds, the oracle's cost for the same work, and the
answer-agreement flag. Check answersAgree before quoting any timing -- a fast
wrong answer is not a result."
