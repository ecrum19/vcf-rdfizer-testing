#!/usr/bin/env bash
# Rerun experiment 09's sites-only cell with the corrected fixture, on
# vcf-bench-1, with the base campaign's release and arguments (2026-10-10).
#
# Run from the host's harness checkout (~/vcf-rdfizer-testing, harness 3b36985d,
# the commit the campaign ran), after replacing
# benchmarks/fixtures/awkward_sites_only.vcf with the corrected fixture
# (SHA-256 6e872d68...; written by lib/make_fixtures.py on main).
set -euo pipefail

cd ~/vcf-rdfizer-testing

# bm_run refuses a cell that already exists: set the first run aside.
superseded=benchmarks_outputs__superseded/09_awkward_inputs__malformed_sites_only__20260924T161103
mkdir -p "$superseded"
mv benchmarks_outputs/09_awkward_inputs/awkward_sites_only "$superseded/"

# The host's tool checkout had moved past the release, so run the release
# commit from its own worktree; bench.json then records d3b34d5 as the campaign did.
git -C ~/VCF-RDFizer worktree add --detach ~/VCF-RDFizer-d3b34d5 d3b34d5

cd benchmarks
VCF_RDFIZER=$HOME/VCF-RDFizer-d3b34d5/vcf_rdfizer.py \
BM_LOCAL_IMAGE=ecrum19/vcf-rdfizer:3.1.0 \
BM_RESULTS=$HOME/vcf-rdfizer-testing/benchmarks_outputs \
bash -c '
source lib/common.sh
# The arguments of 09_awkward_inputs.sh, for this one fixture.
bm_run 09_awkward_inputs awkward_sites_only -- \
  --mode full \
  --input "$BM_ROOT/fixtures/awkward_sites_only.vcf" \
  --rdf-storage-mode space-optimized \
  --hdt-strategy partitioned \
  --representations hdt \
  --rdf-compression none \
  --validate \
  --validate-artifacts all \
  --validation-engine "${BM_VALIDATION_ENGINES:-comunica}" \
  --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
echo "exit=$?"
bm_record_outcome "awkward input: a refusal is a valid outcome, not a defect"
' 2>&1 | tee ~/rerun_sites_only_20261010.log

# Keep the experiment's tidy table as it stood, then rebuild it with the host's collector.
cd ~/vcf-rdfizer-testing
cp benchmarks_outputs/09_awkward_inputs/tidy.csv "$superseded/tidy.before_rerun.csv"
cp benchmarks_outputs/09_awkward_inputs/tidy.json "$superseded/tidy.before_rerun.json"
python3 benchmarks/analysis/collect_metrics.py 09_awkward_inputs \
  --results "$HOME/vcf-rdfizer-testing/benchmarks_outputs"
