#!/usr/bin/env bash
# Real-data use case: ACMG secondary findings across five genomes and ClinVar.
#
# A standalone investigation, not part of the suite: run_all.sh does not run
# it, and no profile includes it. The design, definitions and expected outputs
# are in benchmarks/use_case/acmg/README.md; read that first.
#
#   "Which participants carry a ClinVar pathogenic or likely-pathogenic variant
#    in an ACMG SF v3.2 gene, and what may each requester see?"
#
# Two routes answer it from the same derived inputs and the same definitions
# (use_case/acmg/use_case.json), and neither reads the other's work:
#
#   RDF route        convert -> link (spdi, rsid-dbsnp) -> govern (one release
#                    view per requester) -> one SPARQL query per requester
#   baseline route   bcftools annotate/view/query -> a consent script
#
# The experiment passes only if both give identical carrier lists for every
# requester. Timings and step counts are reported beside that, never instead.
#
# Stages, in order; BM_ACMG_STAGES selects a subset:
#
#   fetch     download ClinVar and the GRCh38 reference (~1.1 GB; explicit
#             opt-in: it is NOT in the default stage list)
#   derive    restrict each input to the ACMG gene spans and normalise it
#   convert   VCF-RDFizer, expanded, one cell per input
#   link      the spdi linker on all six graphs, rsid-dbsnp on the PGP genomes
#   govern    vcf-rdfizer-policy evaluate + check, per requester and genome
#   query     carriers.rq over each requester's view (and over everything,
#             as the "unrestricted" answer), under QLever
#   baseline  the bcftools route
#   compare   the two routes' carrier lists, requester by requester
#
# Usage:
#   BM_ACMG_STAGES=fetch ./17_use_case_acmg.sh           # once per host
#   BM_IMAGE_VERSION=3.2.0 ./17_use_case_acmg.sh         # everything else
#   BM_ACMG_STAGES="query compare" ./17_use_case_acmg.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

CASE_DIR="$BM_ROOT/use_case/acmg"
# Which arm: arm1, the five heterogeneous genomes (use_case.json), or cohort,
# arm 2's 1000 Genomes participants (cohort/cohort.json, from make_cohort.py).
# Each arm has its own results and derived inputs; they share the downloads.
ARM="${BM_ACMG_ARM:-arm1}"
case "$ARM" in
  arm1)   CASE_JSON="$CASE_DIR/use_case.json"; POLICY="$CASE_DIR/policy.ttl"; SUFFIX="" ;;
  cohort) CASE_JSON="$CASE_DIR/cohort/cohort.json"; POLICY="$CASE_DIR/cohort/policy.ttl"; SUFFIX="__cohort" ;;
  *)      bm_die "unknown BM_ACMG_ARM: $ARM (expected arm1 or cohort)" ;;
esac
EXPERIMENT="17_use_case_acmg$SUFFIX"
STAGES="${BM_ACMG_STAGES:-derive convert link govern query baseline compare}"
REPLICATES="${BM_REPS:-3}"
DATA="${BM_ACMG_DATA:-$BM_VCF_DATA/use_case}"       # downloaded inputs
DERIVED="${BM_ACMG_DERIVED:-$BM_DERIVED/acmg$SUFFIX}"   # derived inputs
# Where the participants' VCFs are: the corpus for arm 1, fetch_cohort's output for arm 2.
INPUTS="$BM_VCF_DATA"; [[ "$ARM" == cohort ]] && INPUTS="$DATA/cohort"
EXP_DIR="$BM_RESULTS/$EXPERIMENT"
REFERENCE="$DATA/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna"

case_field() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d[k]
print(d)' "$CASE_JSON" "$1"; }
participant_ids() { python3 -c 'import json,sys
print(" ".join(p["id"] for p in json.load(open(sys.argv[1]))["participants"]))' "$CASE_JSON"; }
participant_input() { python3 -c 'import json,sys
print(next(p["input"] for p in json.load(open(sys.argv[1]))["participants"] if p["id"]==sys.argv[2]))' "$CASE_JSON" "$1"; }
# The shared annotation files, joined to the genomes by SPDI: ClinVar, and the
# panel's frequencies when the case declares them (arm 2).
annotation_ids() { python3 -c 'import json,sys
print("clinvar panel" if "panel" in json.load(open(sys.argv[1])) else "clinvar")' "$CASE_JSON"; }
panel_fields() { python3 -c 'import json,sys
print(",".join("INFO/" + f for f in json.load(open(sys.argv[1]))["panel"]["fields"]))' "$CASE_JSON"; }
QUERIES="/case/${POLICY#"$CASE_DIR"/}"; QUERIES="${QUERIES%/*}"   # beside the policy, in the container
requesters() { python3 -c 'import json,sys
print(" ".join(json.load(open(sys.argv[1]))["policy"]["requesters"]))' "$CASE_JSON"; }
requester_field() { python3 -c 'import json,sys
print(json.load(open(sys.argv[1]))["policy"]["requesters"][sys.argv[2]][sys.argv[3]])' "$CASE_JSON" "$1" "$2"; }
policy_cli() { "${PYTHON:-python3}" "$(dirname -- "$BM_TOOL")/vcf_rdfizer_policy.py" "$@"; }

# Cells are never rewritten: bm_run refuses an existing --out, by design. A
# stage therefore skips what it already has, which makes an interrupted or
# partly failed run resumable by re-running the same command -- the convention
# 15_scale_prepare already follows for the scale store. To redo a cell, move it
# aside (keeping it as evidence) or point BM_RESULTS at a new root.
have_cell() { [[ -d "$EXP_DIR/$1" ]]; }
skip_done() {
  have_cell "$1" || return 1
  bm_step "$1 — already recorded, skipping"
}

# The converted aggregate for an input stem, or empty.
graph_for() { bm_first_file "$EXP_DIR/convert__$1/out" "$1.acmg.nt.gz" 4; }
# Plain in the first runs, gzipped since (stage_link); either is read the same way.
links_for() { bm_first_file "$EXP_DIR/link__$1/out" "*.links.nt*" 4; }

# The image runs bcftools and the query engines. The corpus and the case files
# are mounted read-only; derived inputs and results are the only writable paths,
# and the container runs as the host user so nothing it writes is root-owned.
in_image() {
  local label="$1"; shift
  bm_run_raw "$EXPERIMENT" "$label" -- \
    docker run --rm --init --entrypoint "" --user "$(id -u):$(id -g)" -e HOME=/tmp \
      -v "$INPUTS:/inputs:ro" -v "$CASE_DIR:/case:ro" -v "$DATA:/data:ro" \
      -v "$DERIVED:/derived" -v "$EXP_DIR:/results" \
      "$BM_IMAGE_REF" "$@"
}

# --------------------------------------------------------------------------
stage_fetch() {
  bm_banner "fetch — ClinVar $(case_field clinvar.release) and the GRCh38 reference"
  mkdir -p "$DATA"
  local clinvar="$DATA/clinvar.vcf.gz"
  if [[ ! -s "$clinvar" ]]; then
    curl -fL --retry 3 -o "$clinvar.part" "$(case_field clinvar.url)"
    curl -fsL -o "$clinvar.md5" "$(case_field clinvar.md5_url)"
    [[ "$(md5sum < "$clinvar.part" | cut -d' ' -f1)" == "$(cut -d' ' -f1 "$clinvar.md5")" ]] \
      || bm_die "ClinVar download does not match its published md5"
    mv "$clinvar.part" "$clinvar"
  fi
  if [[ ! -s "$REFERENCE" ]]; then
    curl -fL --retry 3 "$(case_field reference.url)" | gzip -dc > "$REFERENCE.part"
    mv "$REFERENCE.part" "$REFERENCE"
    curl -fsL -o "$REFERENCE.fai" "$(case_field reference.fai_url)"
  fi
  # Pin what was fetched: the paper cites these digests.
  python3 - "$DATA" "$EXP_DIR/inputs.json" <<'PY'
import hashlib, json, pathlib, sys
data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()
out.parent.mkdir(parents=True, exist_ok=True)
json.dump({p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(data.iterdir())
           if p.suffix in (".gz", ".fna", ".fai")}, out.open("w"), indent=2)
PY
  bm_step "pinned: $EXP_DIR/inputs.json"
}

# Arm 2's inputs: the ACMG regions of the 1000 Genomes panel for the cohort's
# samples, read remotely by tabix, one chromosome at a time (fetch_cohort.sh).
# An explicit stage, like fetch: it is not in the default list.
stage_fetch_cohort() {
  bm_banner "fetch_cohort — ACMG regions of the 1000 Genomes panel, $(participant_ids | wc -w) samples"
  [[ "$ARM" == cohort ]] || bm_die "fetch_cohort is arm 2's; set BM_ACMG_ARM=cohort"
  skip_done "fetch_cohort" && return 0
  mkdir -p "$DATA/cohort"
  bm_run_raw "$EXPERIMENT" "fetch_cohort" -- \
    docker run --rm --init --entrypoint "" --user "$(id -u):$(id -g)" -e HOME=/tmp \
      -v "$CASE_DIR:/case:ro" -v "$DATA/cohort:/cohort" "$BM_IMAGE_REF" \
      bash /case/fetch_cohort.sh "/case/${CASE_JSON#"$CASE_DIR"/}" /case/acmg_sf_v3.2.GRCh38.bed /cohort
  bm_expect_ok
}

stage_derive() {
  bm_banner "derive — restrict to the ACMG gene spans, normalise"
  [[ -s "$REFERENCE" && -s "$DATA/clinvar.vcf.gz" ]] \
    || bm_die "inputs not fetched; run BM_ACMG_STAGES=fetch first"
  mkdir -p "$DERIVED"
  local id input drop=""
  # Arm 2's INFO is the panel's, not the participant's (derive.sh).
  [[ "$ARM" == cohort ]] && drop=drop-info
  for id in $(participant_ids); do
    skip_done "derive__$id" && continue
    input="$(participant_input "$id")"
    [[ -s "$INPUTS/$input" ]] || bm_die "input not in $INPUTS: $input"
    in_image "derive__$id" \
      bash /case/derive.sh "/inputs/$input" "$id" /derived \
        "/data/$(basename -- "$REFERENCE")" /case/acmg_sf_v3.2.GRCh38.bed $drop
    bm_expect_ok
  done
  if ! skip_done "derive__clinvar"; then
  in_image "derive__clinvar" \
    bash /case/derive.sh /data/clinvar.vcf.gz clinvar /derived \
      "/data/$(basename -- "$REFERENCE")" /case/acmg_sf_v3.2.GRCh38.bed
  bm_expect_ok
  fi
  [[ " $(annotation_ids) " == *" panel "* ]] || return 0
  # The panel's frequencies, once: the sites a participant carries, no
  # genotypes, only the declared fields. Then derived like any other input.
  if ! skip_done "derive__panel_sites"; then
  in_image "derive__panel_sites" bash -c \
    'bcftools view -c1 -Ou /inputs/cohort.acmg.vcf.gz | bcftools view -G -Ou \
       | bcftools annotate -x "^$1" -Oz -o /derived/panel.sites.vcf.gz' _ "$(panel_fields)"
  bm_expect_ok
  fi
  if ! skip_done "derive__panel"; then
  in_image "derive__panel" \
    bash /case/derive.sh /derived/panel.sites.vcf.gz panel /derived \
      "/data/$(basename -- "$REFERENCE")" /case/acmg_sf_v3.2.GRCh38.bed
  bm_expect_ok
  fi
}

stage_convert() {
  bm_banner "convert — VCF-RDFizer, expanded, one cell per input"
  local id
  for id in $(participant_ids) $(annotation_ids); do
    skip_done "convert__$id" && continue
    [[ -s "$DERIVED/$id.acmg.vcf" ]] || { bm_skip "$EXPERIMENT" "convert__$id" "not derived"; continue; }
    bm_run "$EXPERIMENT" "convert__$id" -- \
      --mode full --input "$DERIVED/$id.acmg.vcf" \
      --sample-representation expanded \
      --rdf-storage-mode plain --rdf-compression gzip --representations none
    bm_expect_ok
  done
}

# The spdi linker ships in a later release than the one this experiment was
# written against. Until the tool checkout has it, the stage records a skip
# rather than failing, exactly as 14 does for an image without its runner.
stage_link() {
  bm_banner "link — spdi on every graph, rsid-dbsnp on the PGP genomes"
  if ! "${PYTHON:-python3}" "$(dirname -- "$BM_TOOL")/vcf_rdfizer_link.py" list 2>/dev/null | grep -q '^spdi '; then
    bm_skip "$EXPERIMENT" "link__spdi" "the tool checkout has no spdi linker ($BM_TOOL)"
    return 0
  fi
  # Linking reads the derived VCF, not the converted graph: the runner derives
  # the converter's subject IRIs from it, and parsing N-Triples would cost far
  # more (workstream-a-implementation.md §3.4). govern's check catches any link
  # whose subject the graph does not contain.
  local id linkers
  for id in $(participant_ids) $(annotation_ids); do
    skip_done "link__$id" && continue
    [[ -s "$DERIVED/$id.acmg.vcf" ]] || { bm_step "link__$id: not derived yet"; continue; }
    # Genomes also get gene links: the policy's cancer panel selects on them.
    [[ " $(annotation_ids) " == *" $id "* ]] && linkers=spdi || linkers=spdi,ensembl-genes-grch38
    python3 -c 'import json,sys
sys.exit(0 if any(p["id"]==sys.argv[2] and p["rsids"] for p in json.load(open(sys.argv[1]))["participants"]) else 1)' \
      "$CASE_JSON" "$id" && linkers="$linkers,rsid-dbsnp"
    # The linker writes plain N-Triples; a whole genome's links are ~1 GB of
    # them, so the cell keeps them gzipped (with the linker's JSON report).
    bm_run_raw "$EXPERIMENT" "link__$id" -- bash -c '
      set -euo pipefail
      work="$(mktemp -d)"; trap "rm -rf \"$work\"" EXIT
      "$1" "$2" run -i "$3" --link "$4" --offline -o "$work/$5.links.nt"
      mkdir -p "$6"
      gzip -1 -c "$work/$5.links.nt" > "$6/$5.links.nt.gz"
      mv "$work/$5.links.json" "$6/"' _ \
      "${PYTHON:-python3}" "$(dirname -- "$BM_TOOL")/vcf_rdfizer_link.py" "$DERIVED/$id.acmg.vcf" \
      "$linkers" "$id.acmg" "$EXP_DIR/link__$id/out"
    bm_expect_ok
  done
}

# A QLever endpoint over files under EXP_DIR, in the image, on 127.0.0.1:<port>.
# Named containers, so a server left by an interrupted run is replaced, not duplicated.
serve() {
  local name="$1" port="$2"; shift 2
  local -a inputs=()
  local file
  for file in "$@"; do inputs+=("$(in_container "$file")"); done
  docker rm -f "acmg-$name" >/dev/null 2>&1 || true
  # No --rm: a container that dies while indexing keeps its log for the error below.
  docker run -d --name "acmg-$name" --entrypoint "" --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$CASE_DIR:/case:ro" -v "$EXP_DIR:/results:ro" -p "127.0.0.1:$port:$port" "$BM_IMAGE_REF" \
    /opt/pycottas-venv/bin/python /case/serve.py --port "$port" --scratch-dir /tmp/serve "${inputs[@]}" >/dev/null
  local waited=0
  until curl -sf -o /dev/null "http://127.0.0.1:$port/?query=ASK%7B%7D"; do
    if [[ "$(docker inspect -f '{{.State.Running}}' "acmg-$name" 2>/dev/null)" != true ]]; then
      docker logs --tail 5 "acmg-$name" >&2 2>&1 || true
      unserve "$name"
      bm_die "the $name endpoint exited while indexing (its last log lines are above)"
    fi
    (( (waited += 5) < 3600 )) || bm_die "the $name endpoint was not ready after an hour"
    sleep 5
  done
  bm_step "$name endpoint ready on :$port after ~${waited}s"
}
unserve() { docker rm -f "acmg-$1" >/dev/null 2>&1 || true; }

# Governance runs on QLever, never on an in-memory graph (plan §4.5). One
# endpoint serves every genome and its links; a second serves the oracle graph
# written straight from the VCF text, beside the same link graphs. The links
# belong there: the policy's gene panel selects on them, and the linker computed
# them from the VCF text too, so the oracle stays independent of the conversion.
# Each requester gets one streamed view of the cohort, checked before use; a
# third endpoint serves that view while its check runs.
stage_govern() {
  bm_banner "govern — one release view per requester, on QLever, checked"
  local -a source=() links=() vcfs=()
  local id requester out
  for id in $(participant_ids); do
    [[ -n "$(graph_for "$id")" && -n "$(links_for "$id")" ]] || bm_die "govern: $id is not converted and linked"
    source+=("$(graph_for "$id")" "$(links_for "$id")")
    links+=("$(links_for "$id")")
    vcfs+=("$DERIVED/$id.acmg.vcf")
  done
  mkdir -p "$EXP_DIR/oracle"
  local oracle; oracle="$(bm_first_file "$EXP_DIR/oracle" "oracle.nt*" 1)"
  if [[ -z "$oracle" ]]; then
    oracle="$EXP_DIR/oracle/oracle.nt.gz"
    policy_cli oracle --vcf "${vcfs[@]}" -o "$oracle"
  fi
  serve source 7201 "${source[@]}"
  serve oracle 7202 "$oracle" "${links[@]}"
  for requester in $(requesters); do
    skip_done "govern__$requester" && continue
    out="$EXP_DIR/govern__$requester/out"
    bm_run_raw "$EXPERIMENT" "govern__$requester" -- \
      "${PYTHON:-python3}" "$(dirname -- "$BM_TOOL")/vcf_rdfizer_policy.py" evaluate \
        --endpoint http://127.0.0.1:7201/ --rdf "${source[@]}" --policy "$POLICY" \
        --assignee "$(requester_field "$requester" assignee)" \
        --purpose "$(requester_field "$requester" purpose)" -o "$out"
    bm_expect_ok
    # The check asks the view's own endpoint about the view as a whole (dangling references).
    serve view 7203 "$out/view.nt.gz"
    policy_cli check --endpoint http://127.0.0.1:7201/ --oracle-endpoint http://127.0.0.1:7202/ \
      --view-endpoint http://127.0.0.1:7203/ --view "$out" --rdf "${source[@]}" --policy "$POLICY" \
      > "$EXP_DIR/govern__$requester/check.txt" 2>&1 \
      || { unserve source; unserve oracle; unserve view
           bm_die "the $requester view failed its check; see $EXP_DIR/govern__$requester/check.txt"; }
    unserve view
  done
  unserve source; unserve oracle
}

# Paths as the container sees them (EXP_DIR is mounted at /results).
in_container() { printf '/results/%s\n' "${1#"$EXP_DIR"/}"; }

stage_query() {
  bm_banner "query — carriers.rq (and rare.rq) under QLever, per requester"
  local id requester path
  # The annotation files and their links go beside every requester's graphs.
  local -a shared=() queries=(--query "$QUERIES/carriers.rq")
  for id in $(annotation_ids); do
    [[ -n "$(graph_for "$id")" && -n "$(links_for "$id")" ]] \
      || { bm_skip "$EXPERIMENT" "query" "$id not converted and linked"; return 0; }
    shared+=("$(in_container "$(graph_for "$id")")" "$(in_container "$(links_for "$id")")")
  done
  [[ -s "$(dirname -- "$POLICY")/rare.rq" ]] && queries+=(--query "$QUERIES/rare.rq")

  local -a everything=("${shared[@]}")
  for id in $(participant_ids); do
    everything+=("$(in_container "$(graph_for "$id")")" "$(in_container "$(links_for "$id")")")
  done
  if ! skip_done "query__unrestricted"; then
  in_image "query__unrestricted" /opt/pycottas-venv/bin/python /case/run_query.py \
    "${queries[@]}" --out /results/query/unrestricted --replicates "$REPLICATES" \
    --scratch-dir /tmp/acmg-query \
    "${everything[@]}"
  bm_expect_ok
  fi

  for requester in $(requesters); do
    skip_done "query__$requester" && continue
    path="$EXP_DIR/govern__$requester/out/view.nt.gz"
    # No cell before govern has run: a recorded skip would block the real run.
    [[ -s "$path" ]] || { bm_step "query__$requester: no release view yet"; continue; }
    in_image "query__$requester" /opt/pycottas-venv/bin/python /case/run_query.py \
      "${queries[@]}" --out "/results/query/$requester" --replicates "$REPLICATES" \
      --scratch-dir /tmp/acmg-query \
      "${shared[@]}" "$(in_container "$path")"
    bm_expect_ok
  done
}

stage_baseline() {
  bm_banner "baseline — bcftools and a consent script"
  skip_done "baseline" && return 0
  # shellcheck disable=SC2046
  in_image "baseline" bash /case/baseline.sh /derived /results/baseline "/case/${CASE_JSON#"$CASE_DIR"/}" \
    $(participant_ids)
  bm_expect_ok
}

stage_compare() {
  bm_banner "compare — the two routes' carrier lists"
  python3 "$CASE_DIR/compare.py" "$EXP_DIR" "$CASE_JSON"
}

mkdir -p "$EXP_DIR" "$DERIVED"
for stage in $STAGES; do
  case "$stage" in
    fetch|fetch_cohort|derive|convert|link|govern|query|baseline|compare) "stage_$stage" ;;
    *) bm_die "unknown stage: $stage" ;;
  esac
done
