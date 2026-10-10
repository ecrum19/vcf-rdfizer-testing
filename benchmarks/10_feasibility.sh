#!/usr/bin/env bash
# Plan §3.7 — conversion under a requested memory ceiling.
#
# Three configurations (the defaults; smaller chunks; smaller chunks with
# condensed samples), each under requested Docker memory ceilings of 8, 16 and
# 31 GB, recording which complete and the memory each used. The default input is
# NG1N86S6FC.vcf.gz; the base campaign's biomedsem profile used the
# 1,000,000-record HG005 rung (BM_FEASIBILITY_INPUT). All nine of its cells
# completed.
#
# This is the ONLY script in the suite that deliberately imposes a memory
# ceiling. Everywhere else a constrained run is a contaminated measurement
# (§4.4).
#
# The ceiling is applied to the tool's Docker containers via DOCKER_MEMORY,
# which the wrapper's own container invocations honour if supported; when it
# does not, this script records the run as unconstrained rather than pretending
# the ceiling applied. Check the recorded 'ceiling_applied' field before
# reporting any cell. No base-campaign cell recorded the ceiling as applied, so
# the paper reports the memory those runs used, not survival under enforced
# limits.
#
# Usage:
#   ./10_feasibility.sh
#   BM_CEILINGS="8g 16g" BM_FEASIBILITY_INPUT=HG005_GRCh38.vcf.gz ./10_feasibility.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="10_feasibility"
INPUT="${BM_FEASIBILITY_INPUT:-NG1N86S6FC.vcf.gz}"
CEILINGS="${BM_CEILINGS:-8g 16g 31g}"

if ! bm_have_vcf "$INPUT"; then
  bm_skip "$EXPERIMENT" "all_cells" \
    "feasibility input not available: $INPUT.
This experiment needs a large corpus file: bash scripts/download_test_data.sh
Or set BM_FEASIBILITY_INPUT to a smaller one — and say so in the manuscript,
because the claim is about a file that does not fit comfortably."
  exit 0
fi
VCF="$(bm_vcf "$INPUT")"

bm_banner "§3.7 feasibility matrix: $(basename "$VCF")"
bm_step "ceilings: $CEILINGS"

# Three configurations spanning "no accommodation" to "everything documented".
run_config() {
  local ceiling="$1" config="$2"; shift 2
  local label="${config}__${ceiling}"
  DOCKER_MEMORY="$ceiling" DOCKER_MEMORY_SWAP="$ceiling" \
    bm_run "$EXPERIMENT" "$label" -- "$@"

  # Record the ceiling alongside the result, and whether it could be applied.
  python3 - "$BM_RESULTS/$EXPERIMENT/$label/bench.json" "$ceiling" "$config" <<'PYEOF'
import json, pathlib, shutil, subprocess, sys
path, ceiling, config = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
record = json.loads(path.read_text())
# The wrapper builds its own docker commands; whether it forwards a memory
# ceiling is a property of the pinned release. Record what we asked for and
# leave verification to the reader rather than asserting it silently.
record["memory_ceiling_requested"] = ceiling
record["config"] = config
record["ceiling_applied"] = None  # verify in stdout.log / docker inspect
record["ceiling_note"] = (
    "Requested via DOCKER_MEMORY/DOCKER_MEMORY_SWAP. Confirm the pinned "
    "release forwards these to its container invocations before reporting "
    "this cell as a constrained run."
)
path.write_text(json.dumps(record, indent=2) + "\n")
PYEOF
}

for ceiling in $CEILINGS; do
  bm_banner "ceiling $ceiling"

  # (a) Defaults: no accommodation beyond the shipped settings.
  run_config "$ceiling" "defaults" \
    --mode full --input "$VCF" \
    --representations hdt --rdf-compression none \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"

  # (b) The documented low-peak chunk settings from the manuscript.
  run_config "$ceiling" "lowpeak_chunks" \
    --mode full --input "$VCF" \
    --rdf-storage-mode space-optimized --hdt-strategy partitioned \
    --representations hdt --rdf-compression none \
    --chunk-min-bytes 67108864 \
    --chunk-target-bytes 134217728 \
    --chunk-max-bytes 268435456 \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"

  # (c) Low-peak chunks plus the condensed representation. Only meaningful on a
  #     multi-sample input; on a single-sample file it should match (b), which
  #     is itself a useful negative control.
  run_config "$ceiling" "lowpeak_condensed" \
    --mode full --input "$VCF" \
    --sample-representation condensed \
    --rdf-storage-mode space-optimized --hdt-strategy partitioned \
    --representations hdt --rdf-compression none \
    --chunk-min-bytes 67108864 \
    --chunk-target-bytes 134217728 \
    --chunk-max-bytes 268435456 \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
done

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/datasets.py feasibility $EXPERIMENT

Reading the results:
  * exit_code 0            completed
  * exit_code -9 or 137    the kernel or Docker OOM-killer intervened. This is
                           NOT an invalid-RDF result; check stderr_tail,
                           max_rss_kb and the workspace samples in
                           stages/partitioned/<sample>.json before suspecting
                           the data.
  * anything else          read stderr.log; it is a different failure."
