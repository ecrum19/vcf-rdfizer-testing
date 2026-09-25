#!/usr/bin/env bash
# Shared state for the optional scale experiments (15 prepare, 16 retrieval).
#
# The one job here is the STORE: a directory of built graphs, each with a
# manifest, that outlives any single benchmark run. 15 writes it, 16 reads it,
# and neither knows anything about the other beyond this contract:
#
#   $BM_SCALE_STORE/<scale>/<dataset>/<dataset>.nt.gz     queryable artifacts
#                                    /<dataset>.hdt
#                                    /<dataset>.cottas
#   $BM_SCALE_STORE/<scale>/manifest.json                 what they are
#
# manifest.json is the interface. It records the source VCF and its digest, the
# triple count, the tool commit and image digest that produced the graph, the
# build wall time, and a digest of every artifact. A query run reads it to know
# what it is querying and copies the provenance into its own results, so a
# retrieval number is never separated from the identity of the graph it came
# from.

# Where built graphs live. Outside $BM_RESULTS by default -- see the header of
# 15_scale_prepare.sh for why that separation is deliberate.
BM_SCALE_STORE="${BM_SCALE_STORE:-$BM_REPO/scale_store}"

# scale-id : input file. Both rungs of the plan: the 1M-record slice first
# because it is cheap enough to prove the pipeline, then the whole genome.
BM_SCALE_SET="${BM_SCALE_SET:-r1000000:HG005_GRCh38_r1000000.vcf.gz whole:HG005_GRCh38.vcf.gz}"

bm_scale_ids() {
  local entry
  for entry in $BM_SCALE_SET; do printf '%s ' "${entry%%:*}"; done
}

bm_scale_input() {
  local wanted="$1" entry
  for entry in $BM_SCALE_SET; do
    [[ "${entry%%:*}" == "$wanted" ]] && { printf '%s\n' "${entry#*:}"; return 0; }
  done
  return 1
}

# Refuse to generate on a local build. A graph in the store is expensive enough
# that it will be reused for months; it must be traceable to a published image
# rather than to whatever the checkout happened to be that afternoon.
bm_scale_require_pinned_image() {
  if bm_image_is_local; then
    bm_die "scale generation requires a pinned published image.
The store keeps graphs that cost hours to build and will be queried long after
this session, so they must be traceable to a release rather than to a local
build of the current checkout. Re-run with:
  BM_IMAGE_VERSION=3.1.0 $0 $*
Set BM_SCALE_ALLOW_LOCAL_IMAGE=1 to override, and expect to explain why."
  fi
}
if [[ "${BM_SCALE_ALLOW_LOCAL_IMAGE:-0}" == "1" ]]; then
  bm_scale_require_pinned_image() { bm_warn "scale store built from a LOCAL image: $BM_IMAGE_REF"; }
fi

bm_scale_manifest() { printf '%s/%s/manifest.json\n' "$BM_SCALE_STORE" "$1"; }

bm_scale_manifest_complete() {
  local path; path="$(bm_scale_manifest "$1")"
  [[ -s "$path" ]] || return 1
  python3 - "$path" <<'PY'
import json, sys
try:
    m = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
# "complete" means every artifact it claims is still on disk. A manifest whose
# artifacts were deleted to free space must not read as a usable store entry.
import pathlib
if not m.get("complete"):
    sys.exit(1)
for entry in m.get("artifacts", {}).values():
    if not pathlib.Path(entry["path"]).is_file():
        sys.exit(1)
sys.exit(0)
PY
}

bm_scale_manifest_field() {
  local path; path="$(bm_scale_manifest "$1")"
  [[ -s "$path" ]] || { printf 'unknown\n'; return 0; }
  python3 -c '
import json, sys
m = json.load(open(sys.argv[1]))
print(m.get(sys.argv[2], "unknown"))
' "$path" "$2"
}

# Write the manifest from a finished build cell. Reads the tool'"'"'s own metrics
# rather than re-deriving anything: the triple count comes from the run record,
# not from counting lines.
bm_scale_write_manifest() {
  local scale="$1" vcf="$2" cell_dir="$3"
  python3 - "$scale" "$vcf" "$cell_dir" "$BM_SCALE_STORE/$scale" \
            "$(bm_scale_manifest "$scale")" "$BM_IMAGE_REF" "$(bm_image_digest)" <<'PY'
import hashlib, json, pathlib, sys, time

scale, vcf, cell_dir, store, manifest_path, image_ref, image_digest = sys.argv[1:8]
store = pathlib.Path(store)
cell = pathlib.Path(cell_dir)

def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

bench = json.loads((cell / "bench.json").read_text())

# The tool writes one directory per dataset under --out.
datasets = [p for p in store.iterdir() if p.is_dir() and p.name != "run_metrics"]
if len(datasets) != 1:
    raise SystemExit(f"expected exactly one dataset directory under {store}, found {len(datasets)}")
dataset = datasets[0]

artifacts = {}
for suffix, kind in ((".nt.gz", "nt.gz"), (".hdt", "hdt"), (".cottas", "cottas")):
    path = dataset / f"{dataset.name}{suffix}"
    if path.is_file():
        artifacts[kind] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

# Triple count from the run record, so the manifest and the campaign's own
# metrics can never disagree.
triples = bench.get("output_triples")
if triples is None:
    metrics = sorted(store.glob("run_metrics/*/metrics.csv"))
    if metrics:
        import csv
        rows = list(csv.DictReader(open(metrics[-1])))
        if rows:
            triples = rows[-1].get("output_triples")

manifest = {
    "scale": scale,
    "complete": True,
    "writtenEpoch": int(time.time()),
    "sourceVcf": {"path": str(pathlib.Path(vcf).resolve()), "sha256": sha256(vcf)},
    "dataset": dataset.name,
    "triples": int(triples) if triples not in (None, "") else None,
    "artifacts": artifacts,
    "provenance": {
        "toolCommit": bench.get("tool_commit"),
        "imageRef": image_ref,
        "imageDigest": image_digest,
        "host": bench.get("host"),
        "buildWallSeconds": bench.get("wrapper_wall_seconds"),
        "buildCell": str(cell),
        "command": bench.get("command"),
    },
}
pathlib.Path(manifest_path).write_text(json.dumps(manifest, indent=2) + "\n")
print(f"manifest: {manifest_path}")
PY
}

# Resolve one artifact of one scale, or empty when the store does not have it.
bm_scale_artifact() {
  local scale="$1" kind="$2" path
  path="$(bm_scale_manifest "$scale")"
  [[ -s "$path" ]] || return 1
  python3 -c '
import json, sys
m = json.load(open(sys.argv[1]))
entry = m.get("artifacts", {}).get(sys.argv[2])
if not entry:
    sys.exit(1)
print(entry["path"])
' "$path" "$kind"
}
