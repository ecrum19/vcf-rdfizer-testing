#!/usr/bin/env bash
# Provenance rerun with the published VCF-RDFizer v3.3.1 (tag b25fb7b, image
# ecrum19/vcf-rdfizer:3.3.1) of every reported result that was not produced by
# a published release. One host role per call:
#   bench1  arm 1, regional retrieval, arm 2 (cohort)
#   bench2  v3.3.1-vs-v3.1.0 conversion check, consumer WGS validation, arm 3, arm 4
#   bench3  large-graph retrieval on the existing v3.1.0 graphs
# Waits until the image can be pulled, then runs its queue one job at a time.
# Writes only under ~/vrdev-test/v331; inputs are read in place.
set -uo pipefail
ROLE="$1"
V="$HOME/vrdev-test/v331"; L="$V/run.log"; mkdir -p "$V/results" "$V/derived" "$V/tmp"
IMAGE="ecrum19/vcf-rdfizer:3.3.1"
TOOL_URL="https://github.com/ecrum19/VCF-RDFizer/archive/refs/tags/v3.3.1.tar.gz"
TOOL_SHA="873a8cda3b495bc96dfc7342a7d531baff527e55e3a1d15bf9038aeb9f6c4172"
HARNESS="6f2239ff7c527573e9ab221514eea71374089ddc"
log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }

# ---- the published image, by digest ------------------------------------------
until docker pull -q "$IMAGE" > /dev/null 2>&1; do log "waiting for $IMAGE"; sleep 300; done
log "image $(docker image inspect "$IMAGE" --format '{{index .RepoDigests 0}}')"

# ---- v3.3.1 source and the harness --------------------------------------------
if [[ ! -d "$V/vcf-rdfizer-v3.3.1" ]]; then
  curl -sL -o "$V/v3.3.1.tar.gz" "$TOOL_URL"
  echo "$TOOL_SHA  $V/v3.3.1.tar.gz" | sha256sum -c --quiet || { log "tool archive checksum mismatch"; exit 1; }
  tar -xzf "$V/v3.3.1.tar.gz" -C "$V" && mv "$V/VCF-RDFizer-3.3.1" "$V/vcf-rdfizer-v3.3.1"
  echo "VCF-RDFizer v3.3.1 (tag commit b25fb7b), archive sha256 $TOOL_SHA" > "$V/vcf-rdfizer-v3.3.1/SOURCE.txt"
fi
if [[ ! -d "$V/vcf-rdfizer-testing" ]]; then
  tar -xzf "$V/harness-${HARNESS:0:8}.tar.gz" -C "$V"
  echo "vcf-rdfizer-testing $HARNESS (benchmarks/, scripts/)" > "$V/vcf-rdfizer-testing/SOURCE.txt"
fi
TOOL="$V/vcf-rdfizer-v3.3.1/vcf_rdfizer.py"; B="$V/vcf-rdfizer-testing/benchmarks"
PY="$HOME/vrdev-test/venv/bin/python"; [[ -x "$PY" ]] || PY="$HOME/vrdev-test/layered/venv/bin/python"
common_env=(VCF_RDFIZER="$TOOL" PYTHON="$PY" BM_IMAGE_VERSION=3.3.1 BM_RESULTS="$V/results")

# ---- one job, timed, with the memory watchdog of the earlier runs ---------------
job() {  # job <name> <command...>
  local name="$1"; shift; local pid t0 rc
  [[ -e "$V/done.$name" ]] && { log "$name already done, skipping"; return 0; }
  docker ps -q | sort > "$V/containers_before.$name"
  log "$name start"; t0=$(date +%s)
  "$@" > "$V/$name.stdout.log" 2> "$V/$name.stderr.log" & pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    local avail; avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    echo "$(date -u +%FT%TZ) $avail $(df --output=avail -BG "$V" | tail -1 | tr -dc 0-9)" >> "$V/resources.$name.tsv"
    if (( avail < 2000000 )); then
      log "$name watchdog: MemAvailable ${avail} kB, stopping"
      kill "$pid" 2>/dev/null
      comm -13 "$V/containers_before.$name" <(docker ps -q | sort) | xargs -r docker kill > /dev/null
      break
    fi
    sleep 60
  done
  wait "$pid"; rc=$?
  log "$name exit $rc after $(( $(date +%s) - t0 )) s"
  [[ $rc -eq 0 ]] && touch "$V/done.$name"
  return 0
}

arm() {  # arm <arm1|cohort|wgs|layered> <use-case data dir>
  ( cd "$B" && env "${common_env[@]}" BM_ACMG_ARM="$1" BM_VCF_DATA="$HOME/vcf-rdfizer-testing/vcf_data" \
      BM_ACMG_DATA="$2" BM_ACMG_DERIVED="$V/derived/$1" BM_ACMG_SERVE_TIMEOUT=14400 \
      BM_ACMG_STAGES="${ARM_STAGES:-derive convert link baseline govern query compare}" ./17_use_case_acmg.sh )
}

bridge() {  # v3.3.1 conversion of the 100,000-record slice against the v3.1.0 N-Triples-only rerun
  local out="$V/bridge" ref="$HOME/vrdev-test/nt-only/convert__rep1/out/HG005_GRCh38_r100000/HG005_GRCh38_r100000.nt.gz"
  python3 "$TOOL" --mode full --input "$HOME/vcf-rdfizer-testing/vcf_data/derived/HG005_GRCh38_r100000.vcf.gz" \
    --sample-representation expanded --rdf-storage-mode space-optimized --representations none \
    --rdf-compression gzip --artifact-compression none --spark-partitions 8 --image "$IMAGE" --no-build \
    --out "$out/out" || return 1
  local new="$out/out/HG005_GRCh38_r100000/HG005_GRCh38_r100000.nt.gz"
  {
    echo "v3.3.1  $(zcat "$new" | LC_ALL=C sort -S 4G -T "$V/tmp" | tee >(wc -l > "$V/tmp/n331") | sha256sum | cut -c1-64) lines=$(sleep 1; cat "$V/tmp/n331")"
    echo "v3.1.0  $(zcat "$ref" | LC_ALL=C sort -S 4G -T "$V/tmp" | tee >(wc -l > "$V/tmp/n310") | sha256sum | cut -c1-64) lines=$(sleep 1; cat "$V/tmp/n310")"
  } > "$out/sorted_triples.sha256"
  [[ "$(awk 'NR==1{print $2}' "$out/sorted_triples.sha256")" == "$(awk 'NR==2{print $2}' "$out/sorted_triples.sha256")" ]]
}

consumer_wgs() {  # the consumer WGS validation run, as reported, with the published release
  python3 "$TOOL" --mode full --input "$HOME/vcf-rdfizer-testing/vcf_data/derived/NG131FQA1I_first250000.vcf.gz" \
    --sample-representation expanded --rdf-storage-mode space-optimized --rdf-compression gzip \
    --representations none --validate --validation-engine qlever --image "$IMAGE" --no-build \
    --out "$V/results/consumer_wgs__NG131FQA1I__first250000/out"
}

regional() {  # the regional experiment on the v3.1.0 graphs that 13_query_cost built
  local q="$HOME/vcf-rdfizer-testing/benchmarks_outputs/13_query_cost"
  ( cd "$B" && env "${common_env[@]}" BM_VCF_DATA="$HOME/vcf-rdfizer-testing/vcf_data" \
      BM_DERIVED="$HOME/vcf-rdfizer-testing/vcf_data/derived" \
      BM_REGIONAL_RDF_SLICE="$q/large__r1/out/HG005_GRCh38_r100000/HG005_GRCh38_r100000.nt.gz" \
      BM_REGIONAL_RDF_SMALL="$q/small__r1/out/test-10k/test-10k.nt.gz" ./14_regional_access.sh )
}

scale() {  # large-graph retrieval on the existing v3.1.0 graphs: the cells reported
  # (16_scale_retrieval.sh is not executable in the harness tree, so run it with bash)
  ( cd "$B" && export "${common_env[@]}" BM_SCALE_STORE="$HOME/vcf-rdfizer-testing/scale_store" &&
    BM_SCALE_CELLS="qlever:nt.gz qlever:hdt qlever:cottas" BM_REPS=3 bash 16_scale_retrieval.sh whole &&
    BM_SCALE_CELLS="qlever:nt.gz" BM_REPS=3 bash 16_scale_retrieval.sh r1000000 &&
    BM_SCALE_CELLS="hdt:hdt cottas:cottas" BM_REPS=1 BM_SCALE_NODE_HEAP_MB=24576 bash 16_scale_retrieval.sh r1000000 )
}

inputs() {  # record what each job reads
  sha256sum "$@" 2>/dev/null > "$V/inputs.$ROLE.sha256"
}

case "$ROLE" in
  bench1)
    inputs "$HOME/vcf-rdfizer-testing/vcf_data/use_case/clinvar.vcf.gz" "$HOME/vcf-rdfizer-testing/vcf_data/derived/HG005_GRCh38_r100000.vcf.gz"
    job arm1 arm arm1 "$HOME/vcf-rdfizer-testing/vcf_data/use_case"
    job regional regional
    job arm2 arm cohort "$HOME/vcf-rdfizer-testing/vcf_data/use_case" ;;
  bench2)
    inputs "$HOME/vrdev-test/acmg-data/clinvar.vcf.gz" "$HOME/vcf-rdfizer-testing/vcf_data/NB72462M.vcf.gz" \
      "$HOME/vcf-rdfizer-testing/vcf_data/HG005_GRCh38.vcf.gz" "$HOME/vcf-rdfizer-testing/vcf_data/derived/NG131FQA1I_first250000.vcf.gz"
    job bridge bridge
    job consumer_wgs consumer_wgs
    job arm3 arm wgs "$HOME/vrdev-test/acmg-data"
    job arm4 arm layered "$HOME/vrdev-test/acmg-data" ;;
  bench3)
    job scale scale ;;
  bench2-arm4-resume)
    # Arm 4 stopped at govern's disk pre-check (48 GB free, ~55 needed) after derive, convert,
    # link, and baseline had completed; space was freed and the remaining stages run here.
    ARM_STAGES="govern query compare" job arm4_resume arm layered "$HOME/vrdev-test/acmg-data" ;;
  *) echo "unknown role $ROLE" >&2; exit 2 ;;
esac
log "V331-$ROLE-DONE"
