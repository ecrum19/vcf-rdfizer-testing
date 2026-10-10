#!/usr/bin/env bash
# 19_index_storage on vcf-bench-3, both scales, with the v3.3.1 release and
# harness a32b5304 (feature/index-storage), extracted to ~/vrdev-test/index-storage/harness.
#
# Inputs: the complete HG005 VCF from the corpus, and its N-Triples from the scale
# store (as 16_scale_retrieval queried them); the 100,000-record slice and the
# N-Triples of 13_query_cost/large__r1, both copied from vcf-bench-1 (SHA-256 checked
# against vcf-input-sizes.json and the source).
set -uo pipefail
cd ~/vrdev-test/index-storage/harness/benchmarks
export VCF_RDFIZER=$HOME/vrdev-test/index-storage/vcf-rdfizer-v3.3.1/vcf_rdfizer.py  # git archive b25fb7b
export BM_IMAGE_VERSION=3.3.1
export BM_RESULTS=$HOME/vrdev-test/index-storage/results
export BM_VCF_DATA=$HOME/vcf-rdfizer-testing/vcf_data
export BM_DERIVED=$HOME/vrdev-test/index-storage/derived
export BM_SCALE_STORE=$HOME/vcf-rdfizer-testing/scale_store
export BM_INDEX_RDF_SLICE=$HOME/vrdev-test/index-storage/inputs/HG005_GRCh38_r100000.nt.gz
date -u +"started %Y-%m-%dT%H:%M:%SZ"
./19_index_storage.sh
echo "19_index_storage exit=$?"
date -u +"finished %Y-%m-%dT%H:%M:%SZ"
