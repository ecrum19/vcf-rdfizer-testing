#!/usr/bin/env bash
# Converter comparison on a shared input — experiment 18.
#
# Runs INSIDE the runner container of benchmarks/converters/compose.yaml. Start it with
#   CONV_DATA=/path/to/vcf_data benchmarks/converters/run.sh
# See benchmarks/converters/README.md for what is measured and why.
#
# The paper's converter table was built from public documentation. This runs every converter
# that can still be obtained on the same two inputs as VCF-RDFizer, and applies the paper's own
# measurements to each output: the validator's content questions Q01-Q08 against the oracle,
# conversion wall time and peak resident memory, triples, and gzipped N-Triples size.
#
# Steps, each recorded as a cell under $BM_RESULTS/18_converter_comparison/:
#   environment/            host, Docker, the resolved compose file, image IDs, file checksums
#   convert__<tool>__<input>__r<n>     one conversion (BM_REPS replicates, interleaved by tool)
#   jsonld__biointerchange__<input>    BioInterchange's JSON-LD to N-Quads, offline (PyLD)
#   normalise__<tool>__<input>         replicate 1's output streamed to N-Triples by Jena riot
#   compare__<tool>__<input>           Q01-Q08 against the oracle, in the VCF-RDFizer image
#
# Nothing here floats: every image, artifact, and package is pinned in converters/pins.env.
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONV="$HERE/converters"
set -a; source "$CONV/pins.env"; set +a

EXPERIMENT=18_converter_comparison
OUT="$BM_RESULTS/$EXPERIMENT"
WORK="$CONV_WORK"
REPS="${BM_REPS:-3}"
#: name:assembly, where the assembly is the one TogoVar's config generator is told.
INPUTS=(HG005_GRCh38_r100000:GRCh38 1000G_10000r_s16:GRCh37)
TOOLS=(vcf-rdfizer jvarkit togovar sparqling-genomics biointerchange)
#: The SHA-256 every input must have, from BioMedSem_2026/benchmark-results/vcf-input-sizes.json.
declare -A INPUT_SHA256=(
  [HG005_GRCh38_r100000]=13f5a187a4af390cab6e609c546059188b036ca9e25577c85b6e1b9af048f4ae
  [1000G_10000r_s16]=e8833c94f08aafedc0dd64ec9377cb96f809f48b674ef3162c284ffa57c30f1c
)

mkdir -p "$OUT" "$WORK"/{home,dl,inputs,meter,scratch,togovar}
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$OUT/driver.log"; }
die() { log "ERROR: $*"; exit 1; }
sha() { sha256sum "$1" | cut -c1-64; }
dc() { docker compose -f "$CONV/compose.yaml" --env-file "$CONV/pins.env" --profile step "$@"; }
#: Run one service as a measured step: dc_run <service> <time-file> <stdout-file> <command...>
dc_run() { local service="$1"; shift; dc run --rm -T "$service" "$@"; }

# ---------------------------------------------------------------------------
# 1. Environment and the measuring binary
# ---------------------------------------------------------------------------
ENV_DIR="$OUT/environment"
[[ -e "$ENV_DIR" ]] && die "$ENV_DIR exists: every run needs a fresh BM_RESULTS"
mkdir -p "$ENV_DIR"
log "experiment 18 start; harness commit $CONV_REPO_COMMIT"
{
  docker info --format 'host={{.Name}} kernel={{.KernelVersion}} os={{.OperatingSystem}} cpus={{.NCPU}} memory_bytes={{.MemTotal}} cgroup={{.CgroupVersion}}'
  docker version --format 'docker_server={{.Server.Version}} docker_client={{.Client.Version}}'
  docker compose version
} > "$ENV_DIR/host.txt"
cp "$CONV/pins.env" "$ENV_DIR/pins.env"
echo "$CONV_REPO_COMMIT" > "$ENV_DIR/harness-commit.txt"
( cd "$CONV_REPO" && find benchmarks/18_converter_comparison.sh benchmarks/lib benchmarks/converters \
    -type f -print0 | sort -z | xargs -0 sha256sum ) > "$ENV_DIR/harness-files.sha256"
dc config > "$ENV_DIR/compose.resolved.yaml"

cp /usr/bin/busybox "$WORK/meter/busybox"
echo "$(sha "$WORK/meter/busybox")  busybox $(busybox | head -1)" > "$ENV_DIR/meter.txt"

# ---------------------------------------------------------------------------
# 2. Upstream artifacts and images, each checked against its pin
# ---------------------------------------------------------------------------
#: A converter that cannot be obtained is recorded here and skipped, not fatal: whether a tool
#: can still be installed is itself a result of this experiment.
unavailable() {  # unavailable <tool> <reason>
  printf '%s\t%s\n' "$1" "$2" >> "$ENV_DIR/unavailable.tsv"
  log "UNAVAILABLE $1: $2"
  local kept=() tool
  for tool in "${TOOLS[@]}"; do [[ "$tool" == "$1" ]] || kept+=("$tool"); done
  TOOLS=("${kept[@]}")
}

#: fetch <url> <pinned sha256 or empty> <destination>. An empty pin is allowed only with
#: CONV_ALLOW_UNPINNED=1 (a development run), and the measured value is recorded either way.
fetch() {
  local url="$1" pin="$2" dest="$3" measured
  [[ -s "$dest" ]] || curl -fsSL --retry 3 -o "$dest" "$url"
  measured="$(sha "$dest")"
  echo "$measured  $url" >> "$ENV_DIR/artifacts.sha256"
  if [[ -z "$pin" ]]; then
    [[ "${CONV_ALLOW_UNPINNED:-0}" == "1" ]] || die "no pinned SHA-256 for $url (measured $measured)"
    log "UNPINNED $url measured $measured"
  elif [[ "$measured" != "$pin" ]]; then
    die "SHA-256 mismatch for $url: pinned $pin, measured $measured"
  fi
}

log "VCF-RDFizer $CONV_VCFRDFIZER_VERSION: release source and image"
fetch "$CONV_VCFRDFIZER_SOURCE_URL" "$CONV_VCFRDFIZER_SOURCE_SHA256" "$WORK/dl/vcf-rdfizer-$CONV_VCFRDFIZER_VERSION.tar.gz"
if [[ ! -d "$WORK/vcf-rdfizer-$CONV_VCFRDFIZER_VERSION" ]]; then
  tar -xzf "$WORK/dl/vcf-rdfizer-$CONV_VCFRDFIZER_VERSION.tar.gz" -C "$WORK"
  mv "$WORK/VCF-RDFizer-$CONV_VCFRDFIZER_VERSION" "$WORK/vcf-rdfizer-$CONV_VCFRDFIZER_VERSION"
fi
export VCF_RDFIZER="$WORK/vcf-rdfizer-$CONV_VCFRDFIZER_VERSION/vcf_rdfizer.py"
export BM_IMAGE_VERSION="$CONV_VCFRDFIZER_VERSION"
docker pull -q "ecrum19/vcf-rdfizer:$CONV_VCFRDFIZER_VERSION" > /dev/null
# The tag the CLI is given must be the digest the comparison uses.
docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' \
    "ecrum19/vcf-rdfizer:$CONV_VCFRDFIZER_VERSION" | grep -qx "$CONV_VCFRDFIZER_IMAGE" \
  || die "ecrum19/vcf-rdfizer:$CONV_VCFRDFIZER_VERSION does not resolve to $CONV_VCFRDFIZER_IMAGE"

log "TogoVar and the comparison image, by digest"
dc pull -q togovar vcf-rdfizer

log "SPARQLing Genomics $CONV_SG_VERSION: upstream release image tarball"
fetch "$CONV_SG_TARBALL_URL" "$CONV_SG_TARBALL_SHA256" "$WORK/dl/sparqling-genomics-$CONV_SG_VERSION-docker.tar.gz"
loaded="$(docker load -i "$WORK/dl/sparqling-genomics-$CONV_SG_VERSION-docker.tar.gz" | tee "$ENV_DIR/sparqling-genomics-load.txt" \
  | sed -nE 's/^Loaded image( ID)?: //p' | tail -1)"
if [[ -n "$loaded" ]]; then
  docker tag "$loaded" "vcf-conv/sparqling-genomics:$CONV_SG_VERSION"
else
  unavailable sparqling-genomics "docker load printed no image for the release tarball"
fi

log "Building the riot normaliser"
dc build --progress plain riot > "$ENV_DIR/build.riot.log" 2>&1 || die "riot build failed; see $ENV_DIR/build.riot.log"
for service in jvarkit biointerchange; do
  log "Building $service"
  dc build --progress plain "$service" > "$ENV_DIR/build.$service.log" 2>&1 \
    || unavailable "$service" "image build failed; see environment/build.$service.log"
done

for service in riot "${TOOLS[@]}"; do   # TOOLS includes vcf-rdfizer, the comparison image
  image="$(dc config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"][sys.argv[1]]["image"])' "$service")"
  printf '%s\t%s\t%s\n' "$service" "$image" \
    "$(docker image inspect --format '{{.Id}} {{json .RepoDigests}}' "$image")" >> "$ENV_DIR/images.tsv"
done
[[ " ${TOOLS[*]} " == *" jvarkit "* ]] \
  && dc_run jvarkit /dev/null "$ENV_DIR/jvarkit-build-sha256.txt" cat /opt/jvarkit/build-sha256.txt

# VCF-RDFizer's questions are copied into this repository; they must be the image's own.
dc run --rm -T vcf-rdfizer sh -c 'cd /opt/vcf-rdfizer/validation/queries &&
  sha256sum common/q0[123478]_*.rq expanded/q0[56]_*.rq' | sed -E 's#  (common|expanded)/#  #' | sort -k2 \
  > "$ENV_DIR/vcf-rdfizer-queries.image.sha256"
( cd "$CONV/queries/vcf-rdfizer" && sha256sum q0*.rq | sort -k2 ) > "$ENV_DIR/vcf-rdfizer-queries.repo.sha256"
cmp -s "$ENV_DIR/vcf-rdfizer-queries.image.sha256" "$ENV_DIR/vcf-rdfizer-queries.repo.sha256" \
  || die "queries/vcf-rdfizer differs from the image's validator queries"

# ---------------------------------------------------------------------------
# 3. Inputs: verified, rewritten as BGZF and tabix-indexed (TogoVar requires a .tbi). The rewrite
#    changes only the compression, never the text: every converter reads the same VCF bytes, and
#    the SHA-256 of the decompressed text is recorded alongside the file's.
# ---------------------------------------------------------------------------
for spec in "${INPUTS[@]}"; do
  name="${spec%%:*}" assembly="${spec##*:}"
  src="$CONV_DATA/derived/$name.vcf.gz" vcf="$WORK/inputs/$name.vcf.gz"
  [[ -s "$src" ]] || die "input not found: $src"
  [[ "$(sha "$src")" == "${INPUT_SHA256[$name]}" ]] || die "$name does not have its recorded SHA-256"
  dc run --rm -T vcf-rdfizer sh -c "gzip -dc '$src' > '${vcf%.gz}' && bgzip -c '${vcf%.gz}' > '$vcf' &&
    tabix -f -p vcf '$vcf'"
  printf '%s\t%s\t%s\n' "$name" "$(sha "$vcf")" "$(sha "${vcf%.gz}")" >> "$ENV_DIR/inputs.sha256"
  log "input $name ($assembly) verified and indexed"
  # TogoVar's conversion config, generated by TogoVar itself, and the CHROM mapping its Q01 needs.
  dc_run togovar "$WORK/togovar/$name.config.time.txt" "$WORK/togovar/$name.config.yaml" \
    vcf2rdf generate config --assembly "$assembly" "$vcf"
  python3 - "$WORK/togovar/$name.config.yaml" > "$WORK/togovar/$name.chrom-values.rq" <<'PY'
import sys, yaml
config = yaml.safe_load(open(sys.argv[1]))
rows = [f'(<{entry["reference"]}> "{chrom}")'
        for chrom, entry in (config.get("reference") or {}).items() if entry and entry.get("reference")]
print("VALUES (?seq ?chrom) { " + " ".join(rows) + " }")
PY
done

# ---------------------------------------------------------------------------
# 4. Conversions: BM_REPS replicates, the tools interleaved within each replicate
# ---------------------------------------------------------------------------
source "$HERE/lib/common.sh"
#: A raw cell's bench.json names the VCF-RDFizer image (bm_run_raw records the session's image);
#: converter.json names the image this cell actually ran.
record_image() {  # record_image <cell> <service>
  awk -F'\t' -v s="$2" '$1 == s {printf "{\"service\": \"%s\", \"image\": \"%s\", \"imageId\": \"%s\"}\n", $1, $2, $3}' \
    "$ENV_DIR/images.tsv" > "$1/converter.json"
}
native_output() {  # native_output <tool> <input> <cell>
  case "$1" in
    vcf-rdfizer)        printf '%s\n' "$3/out/$2/$2.nt.gz" ;;
    jvarkit|togovar)    printf '%s\n' "$3/out/graph.ttl" ;;
    sparqling-genomics) printf '%s\n' "$3/out/graph.nt" ;;
    biointerchange)     printf '%s\n' "$3/out/graph.ldj" ;;
  esac
}
for rep in $(seq 1 "$REPS"); do
  for spec in "${INPUTS[@]}"; do
    name="${spec%%:*}" vcf="$WORK/inputs/${spec%%:*}.vcf.gz"
    for tool in "${TOOLS[@]}"; do
      label="convert__${tool}__${name}__r${rep}"
      cell="$OUT/$label"
      case "$tool" in
        vcf-rdfizer)
          # The release CLI, with the options of the paper's N-Triples-only rerun.
          bm_run "$EXPERIMENT" "$label" -- --mode full --input "$vcf" \
            --sample-representation expanded --rdf-storage-mode space-optimized \
            --representations none --rdf-compression gzip --artifact-compression none \
            --spark-partitions 8 ;;
        jvarkit)
          # --hide '' writes ALT, FILTER and GT, which the default hides.
          bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
            --env-file "$CONV/pins.env" --profile step run --rm -T jvarkit \
            "$cell/out/time.txt" "$cell/out/graph.ttl" \
            java -jar /opt/jvarkit/jvarkit.jar vcf2rdf --hide '' "$vcf" ;;
        togovar)
          # --no-normalize keeps POS, REF and ALT as written in the VCF.
          bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
            --env-file "$CONV/pins.env" --profile step run --rm -T togovar \
            "$cell/out/time.txt" "$cell/out/graph.ttl" \
            vcf2rdf convert --no-normalize --config "$WORK/togovar/$name.config.yaml" "$vcf" ;;
        sparqling-genomics)
          # The defaults already write INFO, FORMAT and the header.
          bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
            --env-file "$CONV/pins.env" --profile step run --rm -T sparqling-genomics \
            "$cell/out/time.txt" "$cell/out/graph.nt" \
            /bin/vcf2rdf -i "$vcf" ;;
        biointerchange)
          # Reads only an uncompressed file whose name ends in .vcf; no option changes what it writes.
          bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
            --env-file "$CONV/pins.env" --profile step run --rm -T biointerchange \
            "$cell/out/time.txt" "$cell/out/stdout.txt" \
            biointerchange -o "$cell/out/graph.ldj" "${vcf%.gz}" ;;
      esac
      [[ "$tool" == vcf-rdfizer ]] || record_image "$cell" "$tool"
      native="$(native_output "$tool" "$name" "$cell")"
      if [[ "$BM_LAST_RC" == "0" && -s "$native" ]]; then
        printf '%s\t%s\n' "$(sha "$native")" "$(stat -c %s "$native")" > "$cell/native.tsv"
      fi
      log "$label exit $BM_LAST_RC"
    done
  done
done

# ---------------------------------------------------------------------------
# 5. Normalise replicate 1 of each output to N-Triples, then compare
# ---------------------------------------------------------------------------
for spec in "${INPUTS[@]}"; do
  name="${spec%%:*}" vcf="$WORK/inputs/${spec%%:*}.vcf.gz"
  for tool in "${TOOLS[@]}"; do
    native="$(native_output "$tool" "$name" "$OUT/convert__${tool}__${name}__r1")"
    if [[ ! -s "$native" ]]; then
      bm_skip "$EXPERIMENT" "normalise__${tool}__${name}" "replicate 1 wrote no output"
      continue
    fi
    if [[ "$tool" == biointerchange ]]; then
      label="jsonld__${tool}__${name}"
      cell="$OUT/$label"
      bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
        --env-file "$CONV/pins.env" --profile step run --rm -T biointerchange \
        "$cell/out/time.txt" "$cell/out/stdout.txt" \
        python3 -I "$CONV/bi_jsonld_to_nquads.py" /opt/biointerchange/vcf-f1.json "$native" "$cell/out/graph.nt"
      record_image "$cell" biointerchange
      if [[ "$BM_LAST_RC" != "0" ]]; then
        log "$label: the JSON-LD could not be read (exit $BM_LAST_RC); see $cell/stderr.log"
        continue
      fi
      native="$cell/out/graph.nt"
    fi
    case "$native" in *.ttl) syntax=turtle ;; *) syntax=ntriples ;; esac
    label="normalise__${tool}__${name}"
    cell="$OUT/$label"
    bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
      --env-file "$CONV/pins.env" --profile step run --rm -T riot \
      "$cell/out/time.txt" "$cell/out/stdout.txt" \
      sh "$CONV/riot_normalise.sh" "$syntax" "$native" "$cell/out/graph.nt" "$cell/out/riot-warnings.log.gz"
    record_image "$cell" riot
    # riot's warnings by kind: the offending IRI or literal and its position are stripped.
    zcat "$cell/out/riot-warnings.log.gz" | python3 -c '
import collections, re, sys
kinds = collections.Counter()
for line in sys.stdin:
    match = re.search(r"\b(WARN|ERROR)\s+riot\s+::\s+\[[^]]*\]\s*(.*)", line)
    if match:
        message = re.sub(r"<[^>]*>|\"[^\"]*\"", "<…>", match.group(2)).strip()
        kinds[(match.group(1), message)] += 1
for (level, message), count in kinds.most_common():
    print(f"{level}\t{count}\t{message}")
' > "$cell/riot-warnings.tsv"
    if [[ "$BM_LAST_RC" != "0" ]]; then
      log "$label: riot could not read the output (exit $BM_LAST_RC); see $cell/stderr.log"
      continue
    fi
    graph="$cell/out/graph.nt.gz"
    gzip -n -6 -c "$cell/out/graph.nt" > "$graph"
    printf 'triples\t%s\nnt_bytes\t%s\nnt_gz_bytes\t%s\nvcf_gz_bytes\t%s\n' \
      "$(grep -c . "$cell/out/graph.nt")" "$(stat -c %s "$cell/out/graph.nt")" \
      "$(stat -c %s "$graph")" "$(stat -c %s "$vcf")" > "$cell/sizes.tsv"
    rm "$cell/out/graph.nt"

    binds=()
    [[ "$tool" == togovar ]] && binds=(--bind "CHROM_VALUES=$WORK/togovar/$name.chrom-values.rq")
    label="compare__${tool}__${name}"
    # The interpreter the release CLI runs its validator with: the image's venv, which has cyvcf2.
    bm_run_raw "$EXPERIMENT" "$label" -- docker compose -f "$CONV/compose.yaml" \
      --env-file "$CONV/pins.env" --profile step run --rm -T vcf-rdfizer \
      /opt/pycottas-venv/bin/python "$CONV/compare_converters.py" --tool "$tool" --vcf "$vcf" --graph "$graph" \
      --queries "$CONV/queries/$tool" --out "$OUT/$label/out" \
      --scratch "$WORK/scratch/$tool-$name" "${binds[@]}"
    record_image "$OUT/$label" vcf-rdfizer
    log "$label exit $BM_LAST_RC"
  done
done

python3 "$CONV/summarize.py" "$OUT"
log "experiment 18 done"
