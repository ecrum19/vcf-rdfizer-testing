#!/usr/bin/env bash
# Plan §5.2 and §5.3 — phase separation, and the modes nothing else touches.
#
# §5.2  Conversion is minutes; validation is hours. Never let them share a run.
#       Phase A converts with validation OFF; Phase B validates the artifacts
#       Phase A already produced. A re-runnable Phase B means a validation bug
#       costs you Phase B, not the six hours of conversion in front of it — and
#       it exercises --mode validation, which the old suite never did.
#
# §5.3  One small-input smoke run each for --mode tsv, compress, decompress,
#       index and validation. 08_robustness.sh gives most of these a purpose
#       beyond smoke (round-trip, determinism, idempotence); this script is the
#       bare "does it run at all" pass plus the phase-separation demonstration.
#
# Usage: ./12_modes_smoke.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="12_modes_smoke"
INPUT="${BM_SMOKE_INPUT:-test-1k.vcf}"

if ! bm_have_vcf "$INPUT"; then
  bm_die "smoke input not available: $INPUT"
fi
VCF="$(bm_vcf "$INPUT")"

# --------------------------------------------------------------------------
bm_banner "§5.3 --mode tsv"
bm_run "$EXPERIMENT" "mode_tsv" -- \
  --mode tsv --input "$VCF"
bm_expect_ok

# --------------------------------------------------------------------------
bm_banner "§5.2 Phase A — conversion, validation OFF"
bm_run "$EXPERIMENT" "phaseA_convert" -- \
  --mode full --input "$VCF" \
  --rdf-storage-mode space-optimized \
  --hdt-strategy partitioned \
  --representations hdt,cottas \
  --rdf-compression gzip \
  --artifact-compression none \
  --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
bm_expect_ok

PHASE_A_OUT="$BM_RESULTS/$EXPERIMENT/phaseA_convert/out"
AGGREGATE="$(bm_first_file "$PHASE_A_OUT" '*.nt.gz' 3)"
HDT="$(bm_first_file "$PHASE_A_OUT" '*.hdt' 3)"
COTTAS="$(bm_first_file "$PHASE_A_OUT" '*.cottas' 3)"

bm_step "aggregate: ${AGGREGATE:-none}"
bm_step "hdt:       ${HDT:-none}"
bm_step "cottas:    ${COTTAS:-none}"

# --------------------------------------------------------------------------
bm_banner "§5.2 Phase B — validation against Phase A's artifacts"

# --mode validation needs the source VCF and the graph to check it against.
if [[ -n "$AGGREGATE" ]]; then
  bm_run "$EXPERIMENT" "phaseB_validate_aggregate" -- \
    --mode validation --input "$VCF" --rdf "$AGGREGATE" \
    --sample-representation expanded \
    --validation-engine "${BM_VALIDATION_ENGINES:-all}"
  bm_expect_ok
else
  bm_skip "$EXPERIMENT" "phaseB_validate_aggregate" "Phase A produced no .nt.gz aggregate"
fi

# --------------------------------------------------------------------------
bm_banner "§5.3 --mode compress / decompress / index"

if [[ -n "$AGGREGATE" ]]; then
  bm_run "$EXPERIMENT" "mode_compress" -- \
    --mode compress --rdf "$AGGREGATE" \
    --rdf-compression brotli --representations hdt \
    --artifact-compression none \
    --hdt-strategy partitioned
  bm_expect_ok

  bm_run "$EXPERIMENT" "mode_decompress" -- \
    --mode decompress --compressed-input "$AGGREGATE"
  bm_expect_ok
else
  bm_skip "$EXPERIMENT" "mode_compress" "no aggregate from Phase A"
  bm_skip "$EXPERIMENT" "mode_decompress" "no aggregate from Phase A"
fi

if [[ -n "$HDT" ]]; then
  # --mode index writes in place; it is the deliberate exception to the
  # no-overwrite collision policy, because regenerating an index is its purpose.
  bm_run "$EXPERIMENT" "mode_index_hdt" -- \
    --mode index --hdt "$HDT"
  bm_expect_ok
else
  bm_skip "$EXPERIMENT" "mode_index_hdt" "Phase A produced no .hdt"
fi

if [[ -n "$COTTAS" ]]; then
  bm_run "$EXPERIMENT" "mode_index_cottas" -- \
    --mode index --cottas "$COTTAS"
  bm_expect_ok
else
  bm_skip "$EXPERIMENT" "mode_index_cottas" "Phase A produced no .cottas"
fi

bm_info "Done. Every mode the plan lists in §5.3 now has a recorded run.
At scale, prefer --validation-engine qlever or --validate-artifacts hdt;
--validation-engine all belongs on small inputs only, where cross-engine
agreement is the actual deliverable (§4.1)."
