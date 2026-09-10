#!/usr/bin/env bash
# Plan §4.3 — robustness evidence, most of which already exists unused.
#
#   1. Mutation score        the strongest quantified claim in the repo
#   2. Round-trip identity   compress -> decompress -> same triples
#   3. Determinism           same input + config twice -> same digest
#   4. Index idempotence     re-indexing changes nothing
#
# The mutation score is the headline. docs/vcf-coverage.md records 96/113 (85%)
# across 60 named mutations with every gap enumerated in
# test/validation_mutations.py. That is a quantified statement that the
# validation suite would DETECT corruption of specific VCF elements — far
# beyond "we ran it and it exited 0". A paper reporting 85% with the gaps listed
# is trusted more than one reporting nothing.
#
# Usage:
#   ./08_robustness.sh              # everything
#   ./08_robustness.sh fixtures     # only regenerate fixtures
#   ./08_robustness.sh mutation
#   ./08_robustness.sh roundtrip
#   ./08_robustness.sh determinism
#   ./08_robustness.sh index

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="08_robustness"
WHICH="${1:-all}"
INPUT="${BM_ROBUSTNESS_INPUT:-test-larger.vcf.gz}"
FIXTURE_DIR="$BM_ROOT/fixtures"
TOOL_DIR="$(dirname -- "$BM_TOOL")"

# --------------------------------------------------------------------------
run_fixtures() {
  bm_banner "Regenerating fixtures"
  python3 "$BM_ROOT/lib/make_fixtures.py" "$FIXTURE_DIR"
}

# --------------------------------------------------------------------------
# 1. Mutation score, regenerated against the pinned commit.
# --------------------------------------------------------------------------
run_mutation() {
  bm_banner "§4.3 mutation score"
  if [[ ! -f "$TOOL_DIR/test/test_validation_mutation_unit.py" ]]; then
    bm_skip "$EXPERIMENT" "mutation_score" \
      "mutation harness not found in $TOOL_DIR/test — needs a tool checkout, not an installed package"
    return 0
  fi
  local dest="$BM_RESULTS/$EXPERIMENT/mutation_score"
  mkdir -p "$dest"

  # The harness needs rdflib; without it every mutation test skips and the
  # score would be silently reported as 0/0.
  if ! python3 -c "import rdflib" >/dev/null 2>&1; then
    bm_skip "$EXPERIMENT" "mutation_score" \
      "rdflib is not installed, so the mutation harness would skip every case.
Install it first: python3 -m pip install rdflib"
    return 0
  fi

  bm_step "running the mutation harness (this takes a few minutes)"
  set +e
  ( cd -- "$TOOL_DIR" && \
    VCF_RDFIZER_MUTATION_REPORT="$dest/mutation-score.json" \
    python3 -m unittest test.test_validation_mutation_unit ) \
    > "$dest/stdout.log" 2> "$dest/stderr.log"
  local rc=$?
  set -e

  python3 - "$dest" "$rc" "$(bm_tool_commit)" <<'PYEOF'
import json, pathlib, sys
dest, rc, commit = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
report = dest / "mutation-score.json"
record = {"experiment": "08_robustness", "cell": "mutation_score",
          "exit_code": rc, "tool_commit": commit}
if report.exists():
    try:
        record["mutation_report"] = json.loads(report.read_text())
    except json.JSONDecodeError:
        record["mutation_report_error"] = "report is not valid JSON"
else:
    record["mutation_report_error"] = "harness wrote no report"
(dest / "bench.json").write_text(json.dumps(record, indent=2) + "\n")
print(f"  score report -> {report}")
PYEOF

  bm_step "cite the score AND the remaining-gaps list; the gaps are the honest limitation"
}

# --------------------------------------------------------------------------
# 2. Round-trip identity: compress -> decompress -> same triple count.
#    Cheap, strong, and it exercises two modes the old suite never touched.
# --------------------------------------------------------------------------
run_roundtrip() {
  bm_banner "§4.3 round-trip identity"
  bm_have_vcf "$INPUT" || { bm_skip "$EXPERIMENT" "roundtrip" "input not available: $INPUT"; return 0; }
  local vcf; vcf="$(bm_vcf "$INPUT")"

  # Produce an uncompressed aggregate to round-trip.
  bm_run "$EXPERIMENT" "roundtrip__01_convert" -- \
    --mode full --input "$vcf" \
    --rdf-storage-mode plain \
    --representations none --rdf-compression none \
    --keep-rmlstreamer-rdf-output \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  bm_expect_ok

  local aggregate
  aggregate="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/roundtrip__01_convert/out" '*.nt' 3)"
  if [[ -z "$aggregate" ]]; then
    bm_skip "$EXPERIMENT" "roundtrip__incomplete" \
      "no .nt aggregate to round-trip${BM_DRY_RUN:+ (BM_DRY_RUN=1 produces no artifacts)}"
    return 0
  fi
  bm_step "aggregate: $(basename "$aggregate")"

  bm_run "$EXPERIMENT" "roundtrip__02_compress" -- \
    --mode compress --rdf "$aggregate" \
    --rdf-compression gzip --representations hdt \
    --artifact-compression none \
    --hdt-strategy partitioned
  bm_expect_ok

  local packed
  packed="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/roundtrip__02_compress/out" '*.nt.gz' 3)"
  if [[ -z "$packed" ]]; then
    bm_skip "$EXPERIMENT" "roundtrip__incomplete" "compress mode produced no .nt.gz"
    return 0
  fi

  bm_run "$EXPERIMENT" "roundtrip__03_decompress" -- \
    --mode decompress --compressed-input "$packed"
  bm_expect_ok

  local decoded
  decoded="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/roundtrip__03_decompress/out" '*.nt' 4)"
  if [[ -z "$decoded" ]]; then
    bm_skip "$EXPERIMENT" "roundtrip__incomplete" "decompress produced no .nt"
    return 0
  fi

  python3 "$BM_ROOT/analysis/compare_graphs.py" \
    --label roundtrip \
    --out "$BM_RESULTS/$EXPERIMENT/roundtrip__verdict.json" \
    "$aggregate" "$decoded" \
    || bm_warn "ROUND-TRIP MISMATCH — see roundtrip__verdict.json. This is a
real finding, not a script error: record it and investigate before publishing."
}

# --------------------------------------------------------------------------
# 3. Determinism: the same input and configuration twice must produce the same
#    canonicalized graph. One extra run; nearly free.
# --------------------------------------------------------------------------
run_determinism() {
  bm_banner "§4.3 determinism"
  bm_have_vcf "$INPUT" || { bm_skip "$EXPERIMENT" "determinism" "input not available: $INPUT"; return 0; }
  local vcf; vcf="$(bm_vcf "$INPUT")"

  local pass
  for pass in a b; do
    bm_run "$EXPERIMENT" "determinism__${pass}" -- \
      --mode full --input "$vcf" \
      --rdf-storage-mode plain \
      --representations none --rdf-compression none \
      --keep-rmlstreamer-rdf-output \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
    bm_expect_ok
  done

  local nt_a nt_b
  nt_a="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/determinism__a/out" '*.nt' 3)"
  nt_b="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/determinism__b/out" '*.nt' 3)"
  if [[ -z "$nt_a" || -z "$nt_b" ]]; then
    bm_skip "$EXPERIMENT" "determinism__incomplete" "one or both passes produced no aggregate"
    return 0
  fi

  python3 "$BM_ROOT/analysis/compare_graphs.py" \
    --label determinism \
    --out "$BM_RESULTS/$EXPERIMENT/determinism__verdict.json" \
    "$nt_a" "$nt_b" \
    || bm_warn "NON-DETERMINISTIC OUTPUT — see determinism__verdict.json. Two
identical invocations produced different graphs; record it and investigate."
}

# --------------------------------------------------------------------------
# 4. Index idempotence: --mode index on an existing artifact changes nothing
#    observable. This is also the one mode whose whole purpose is to overwrite,
#    so it is the deliberate exception to the collision policy.
# --------------------------------------------------------------------------
run_index() {
  bm_banner "§4.3 index idempotence"
  bm_have_vcf "$INPUT" || { bm_skip "$EXPERIMENT" "index" "input not available: $INPUT"; return 0; }
  local vcf; vcf="$(bm_vcf "$INPUT")"

  bm_run "$EXPERIMENT" "index__01_build" -- \
    --mode full --input "$vcf" \
    --rdf-storage-mode space-optimized \
    --hdt-strategy partitioned \
    --representations hdt --rdf-compression none \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  bm_expect_ok

  local hdt
  hdt="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/index__01_build/out" '*.hdt' 3)"
  if [[ -z "$hdt" ]]; then
    bm_skip "$EXPERIMENT" "index__incomplete" "no .hdt produced to re-index"
    return 0
  fi

  local before after
  before="$(python3 "$BM_ROOT/analysis/compare_graphs.py" --digest-only "$hdt")"

  # --mode index writes in place, so it takes the existing tree as --out.
  bm_run "$EXPERIMENT" "index__02_reindex" -- \
    --mode index --hdt "$hdt"
  bm_expect_ok

  after="$(python3 "$BM_ROOT/analysis/compare_graphs.py" --digest-only "$hdt")"

  python3 - "$BM_RESULTS/$EXPERIMENT/index__verdict.json" "$before" "$after" <<'PYEOF'
import json, pathlib, sys
out, before, after = sys.argv[1:4]
verdict = {"cell": "index_idempotence", "digest_before": before,
           "digest_after": after, "identical": before == after}
pathlib.Path(out).write_text(json.dumps(verdict, indent=2) + "\n")
print(f"  index idempotence: {'IDENTICAL' if before == after else 'CHANGED'}")
PYEOF
}

case "$WHICH" in
  fixtures)    run_fixtures ;;
  mutation)    run_mutation ;;
  roundtrip)   run_roundtrip ;;
  determinism) run_determinism ;;
  index)       run_index ;;
  all)         run_fixtures; run_mutation; run_roundtrip; run_determinism; run_index ;;
  *) bm_die "usage: $0 [all|fixtures|mutation|roundtrip|determinism|index]" ;;
esac

bm_info "Done. Verdicts are in $BM_RESULTS/$EXPERIMENT/*__verdict.json"
