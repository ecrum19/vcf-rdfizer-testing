#!/usr/bin/env bash
# Plan §4.4 — awkward-input handling.
#
# A table of deliberately difficult real-VCF situations, each with the observed
# behaviour. BOTH outcomes are acceptable results: converted, or refused with a
# clear diagnostic. A crash or a silently wrong graph is not.
#
# This is what supports "does MANY useful VCF things", and it is honest about
# the edges — which is more convincing than a table of successes.
#
# Every fixture carries its own expectation in benchmarks/fixtures/FIXTURES.json
# (written by lib/make_fixtures.py). The analysis pairs observed against
# expected, so a change in behaviour is visible rather than reinterpreted.
#
# Usage: ./09_awkward_inputs.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="09_awkward_inputs"
FIXTURE_DIR="$BM_ROOT/fixtures"

if [[ ! -f "$FIXTURE_DIR/FIXTURES.json" ]]; then
  bm_step "fixtures missing; generating"
  python3 "$BM_ROOT/lib/make_fixtures.py" "$FIXTURE_DIR"
fi

bm_banner "§4.4 awkward inputs"

# Validation is on: a fixture that converts but produces a graph disagreeing
# with its own source is the failure mode this experiment exists to catch, and
# a bare exit code would not reveal it.
for fixture in "$FIXTURE_DIR"/awkward_*.vcf "$FIXTURE_DIR"/awkward_*.vcf.gz; do
  [[ -e "$fixture" ]] || continue
  name="$(basename -- "$fixture")"
  label="${name%%.*}"

  bm_run "$EXPERIMENT" "$label" -- \
    --mode full \
    --input "$fixture" \
    --rdf-storage-mode space-optimized \
    --hdt-strategy partitioned \
    --representations hdt \
    --rdf-compression none \
    --validate \
    --validate-artifacts all \
    --validation-engine "${BM_VALIDATION_ENGINES:-comunica}" \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
  # Deliberately no bm_expect_ok: a refusal is a valid, recorded outcome.
done

# --------------------------------------------------------------------------
# Extensibility, same spirit: one smoke run each for the two extension points.
# --------------------------------------------------------------------------
bm_banner "§4.4 extensibility smoke runs"

SMOKE_INPUT="${BM_SMOKE_INPUT:-test-100.vcf}"
if bm_have_vcf "$SMOKE_INPUT"; then
  vcf="$(bm_vcf "$SMOKE_INPUT")"

  # Custom rules. Note the documented interaction: rules consuming
  # sample_calls.tsv or sample_format_values.tsv are REJECTED in condensed
  # mode, by design, because running them would emit both graph shapes and
  # reintroduce the expansion condensed exists to avoid. A deliberate refusal
  # is a design result, not a gap — assert it rather than avoiding it.
  RULES="${BM_CUSTOM_RULES:-}"
  if [[ -n "$RULES" && -f "$RULES" ]]; then
    bm_run "$EXPERIMENT" "rules__custom_expanded" -- \
      --mode full --input "$vcf" --rules "$RULES" \
      --sample-representation expanded \
      --rdf-storage-mode space-optimized --hdt-strategy partitioned \
      --representations hdt --rdf-compression none

    bm_run "$EXPERIMENT" "rules__custom_condensed_expect_refusal" -- \
      --mode full --input "$vcf" --rules "$RULES" \
      --sample-representation condensed \
      --rdf-storage-mode space-optimized --hdt-strategy partitioned \
      --representations hdt --rdf-compression none
    # Only a helper-table mapping is refused; a mapping that touches neither
    # TSV is legal in condensed mode, so this is recorded, not asserted.
  else
    bm_skip "$EXPERIMENT" "rules__custom" \
      "set BM_CUSTOM_RULES=/path/to/rules.ttl to exercise a custom mapping.
Note: validation reports Q9-Q13 as MISMATCH for a correct custom mapping,
because the wrapper does not forward --mapping-policy (a known tool gap).
Read those five as report-only here."
  fi

  # Data linking, three tiers. `--mode link` is host-only and takes an existing
  # .nt/.nt.gz via --rdf, not a VCF via --input, so convert once first.
  if ! python3 -c "import rdflib" >/dev/null 2>&1; then
    bm_skip "$EXPERIMENT" "link__all_tiers" \
      "data linking requires rdflib: python3 -m pip install rdflib"
  else
    bm_run "$EXPERIMENT" "link__00_convert" -- \
      --mode full --input "$vcf" \
      --rdf-storage-mode plain \
      --representations none --rdf-compression none \
      --keep-rmlstreamer-rdf-output \
      --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
    bm_expect_ok

    link_rdf="$(bm_first_file "$BM_RESULTS/$EXPERIMENT/link__00_convert/out" '*.nt' 3)"
    if [[ -z "$link_rdf" ]]; then
      bm_skip "$EXPERIMENT" "link__all_tiers" "no .nt aggregate produced to link against"
    else
      # Tiers 1 and 2 need no network.
      for linker in rsid-dbsnp gene-demo; do
        bm_run "$EXPERIMENT" "link__${linker}" -- \
          --mode link --rdf "$link_rdf" --link "$linker" --offline
      done
      # Tier 3 resolves against the Ensembl HTTPS API.
      if [[ "${BM_ALLOW_NETWORK:-0}" == "1" ]]; then
        bm_run "$EXPERIMENT" "link__rsid-ensembl" -- \
          --mode link --rdf "$link_rdf" --link rsid-ensembl \
          --links-contact-email "${BM_CONTACT_EMAIL:?set BM_CONTACT_EMAIL for the Ensembl resolver}"
      else
        bm_skip "$EXPERIMENT" "link__rsid-ensembl" \
          "tier-3 linker needs network; set BM_ALLOW_NETWORK=1 and BM_CONTACT_EMAIL to run it"
      fi
    fi
  fi
else
  bm_skip "$EXPERIMENT" "extensibility" "smoke input not available: $SMOKE_INPUT"
fi

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/datasets.py awkward $EXPERIMENT

The table pairs each fixture's recorded expectation against what happened.
Report refusals as refusals — a clear diagnostic is a pass."
