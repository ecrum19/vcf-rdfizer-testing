#!/usr/bin/env bash
# Shared helpers for the VCF-RDFizer benchmark suite.
#
# Source this, do not execute it:
#   source "$(dirname "$0")/lib/common.sh"
#
# Every experiment script uses bm_run() so that all runs are recorded the same
# way: fresh --out per cell (the wrapper refuses to overwrite planned
# artifacts), a sampled peak host workspace footprint, the tool commit, and the
# exact command line. Analysis reads only what bm_run writes.

set -euo pipefail

# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
BM_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BM_ROOT="$(cd -- "$BM_LIB_DIR/.." && pwd -P)"          # benchmarks/
BM_REPO="$(cd -- "$BM_ROOT/.." && pwd -P)"             # vcf-rdfizer-testing/
BM_RESULTS="${BM_RESULTS:-$BM_ROOT/results}"
BM_DERIVED="${BM_DERIVED:-$BM_REPO/vcf_data/derived}"
BM_VCF_DATA="${BM_VCF_DATA:-$BM_REPO/vcf_data}"
BM_SAMPLE_INTERVAL="${BM_SAMPLE_INTERVAL:-5}"          # workspace sampler, seconds
BM_DRY_RUN="${BM_DRY_RUN:-0}"

# --------------------------------------------------------------------------
# Docker image: local build by default, pinned release on request
# --------------------------------------------------------------------------
# Two modes, and exactly one is active per session:
#
#   LOCAL (default)   Build the image once from the tool checkout and tag it
#                     with the commit that built it — vcf-rdfizer:local-<sha>.
#                     This is what you want while developing: it tests the code
#                     you are actually changing, and the tag records which
#                     commit that was.
#
#   PINNED            Set BM_IMAGE_VERSION=1.1.0 to use a published release
#                     instead. The tool pulls exactly that tag. This is what a
#                     future reproduction run uses.
#
# Whichever mode is active, the image is resolved ONCE per session and every
# cell then runs with `--image <exact ref> --no-build`. Two reasons that
# matters: `--build` on each cell would rebuild the image for all 30 cells of
# experiment 01, and `--no-build` guarantees a cell can never silently rebuild
# into something different halfway through a sweep.
#
# For reference, the tool's own resolution order is: --build, then a local
# image, then a pull if --image-version was given, then --no-build errors,
# then build-if-Dockerfile-else-pull. The consequence worth knowing is that a
# bare `:latest` NEVER pulls — so an unpinned published image would silently be
# whatever happens to be on the machine.
BM_IMAGE_VERSION="${BM_IMAGE_VERSION:-}"     # set -> pinned published release
BM_IMAGE="${BM_IMAGE:-ecrum19/vcf-rdfizer}"  # repo for the pinned mode
BM_LOCAL_IMAGE="${BM_LOCAL_IMAGE:-}"         # override the local tag
BM_REBUILD="${BM_REBUILD:-0}"                # force a rebuild in local mode

# --------------------------------------------------------------------------
# Tool resolution
# --------------------------------------------------------------------------
# Prefer an explicit VCF_RDFIZER; else a sibling checkout; else the installed
# console script. Benchmarks must know exactly which one ran, so the resolved
# path and its git commit go into every bench.json.
bm_resolve_tool() {
  if [[ -n "${VCF_RDFIZER:-}" ]]; then
    BM_TOOL_KIND="explicit"; BM_TOOL="$VCF_RDFIZER"; return 0
  fi
  local candidate
  for candidate in "$BM_REPO/../vcf-rdfizer/vcf_rdfizer.py" \
                   "$BM_REPO/../VCF-RDFizer/vcf_rdfizer.py"; do
    if [[ -f "$candidate" ]]; then
      BM_TOOL_KIND="checkout"
      BM_TOOL="$(cd -- "$(dirname -- "$candidate")" && pwd -P)/$(basename -- "$candidate")"
      return 0
    fi
  done
  if command -v vcf-rdfizer >/dev/null 2>&1; then
    BM_TOOL_KIND="installed"; BM_TOOL="$(command -v vcf-rdfizer)"; return 0
  fi
  bm_die "no VCF-RDFizer found. Set VCF_RDFIZER=/path/to/vcf_rdfizer.py"
}

# The argv prefix that invokes the tool.
bm_tool_argv() {
  case "$BM_TOOL_KIND" in
    installed) printf '%s\n' "$BM_TOOL" ;;
    *)         printf '%s\n%s\n' "${PYTHON:-python3}" "$BM_TOOL" ;;
  esac
}

# The image arguments every measured run gets. Kept in one place so no
# experiment script can forget to pin, and so the exact reference is visible in
# the recorded command line of every cell.
#
# BM_IMAGE_REF is resolved once, at the bottom of this file.
bm_image_argv() {
  printf '%s\n%s\n%s\n' "--image" "$BM_IMAGE_REF" "--no-build"
}

# True when this session builds from the checkout rather than pulling a release.
bm_image_is_local() { [[ -z "$BM_IMAGE_VERSION" ]]; }

# The local tag encodes the commit that built it, so the image reference alone
# says which source produced a result. A dirty tree gets `-dirty`, and is
# rebuilt every session because the tag cannot distinguish two dirty trees.
bm_local_image_tag() {
  if [[ -n "$BM_LOCAL_IMAGE" ]]; then printf '%s\n' "$BM_LOCAL_IMAGE"; return 0; fi
  local dir short dirty=""
  dir="$(dirname -- "$BM_TOOL")"
  if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    short="$(git -C "$dir" rev-parse --short HEAD)"
    git -C "$dir" diff --quiet 2>/dev/null || dirty="-dirty"
    printf 'vcf-rdfizer:local-%s%s\n' "$short" "$dirty"
  else
    printf 'vcf-rdfizer:local\n'
  fi
}

bm_image_digest() {
  local value
  # A failed `docker image inspect` can still emit a blank line on stdout, so
  # each candidate is captured and checked rather than chained with ||.
  value="$(docker image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' \
    "$BM_IMAGE_REF" 2>/dev/null | tr -d '\n' || true)"
  if [[ -n "$value" ]]; then printf '%s\n' "$value"; return 0; fi
  value="$(docker image inspect --format '{{.Id}}' "$BM_IMAGE_REF" 2>/dev/null | tr -d '\n' || true)"
  if [[ -n "$value" ]]; then printf '%s\n' "$value"; return 0; fi
  printf 'not-present-locally\n'
}

# Build the local image once per session. No-op when it already exists, unless
# BM_REBUILD=1 or the working tree is dirty (whose tag cannot be trusted to
# mean one particular state).
bm_ensure_local_image() {
  bm_image_is_local || return 0
  [[ "$BM_DRY_RUN" == "1" ]] && return 0

  local dockerfile_dir
  dockerfile_dir="$(dirname -- "$BM_TOOL")"
  if [[ ! -f "$dockerfile_dir/Dockerfile" ]]; then
    bm_die "local image mode needs a Dockerfile in $dockerfile_dir.
Either point VCF_RDFIZER at a source checkout, or pin a published release:
  export BM_IMAGE_VERSION=1.1.0"
  fi

  local exists=0
  docker image inspect "$BM_IMAGE_REF" >/dev/null 2>&1 && exists=1
  local dirty=0
  [[ "$BM_IMAGE_REF" == *-dirty ]] && dirty=1

  if (( exists )) && [[ "$BM_REBUILD" != "1" ]] && (( ! dirty )); then
    bm_step "image $BM_IMAGE_REF already built"
    return 0
  fi

  if (( dirty )); then
    bm_warn "the tool checkout has uncommitted changes, so $BM_IMAGE_REF is
rebuilt every session and does not identify one particular source state.
Commit before a run whose numbers you intend to publish."
  fi

  bm_info "Building $BM_IMAGE_REF (once for this session)"
  if ! docker build -t "$BM_IMAGE_REF" "$dockerfile_dir" > "${BM_BUILD_LOG:-/dev/stdout}" 2>&1; then
    bm_die "docker build failed for $BM_IMAGE_REF${BM_BUILD_LOG:+ (see $BM_BUILD_LOG)}"
  fi
}

bm_tool_commit() {
  local dir
  case "$BM_TOOL_KIND" in
    installed) printf 'installed:%s\n' "$($BM_TOOL --version 2>/dev/null | head -1)"; return 0 ;;
  esac
  dir="$(dirname -- "$BM_TOOL")"
  if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    printf '%s%s\n' \
      "$(git -C "$dir" rev-parse HEAD)" \
      "$(git -C "$dir" diff --quiet 2>/dev/null || printf -- '-dirty')"
  else
    printf 'unknown\n'
  fi
}

# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------
bm_die()  { printf 'benchmark error: %s\n' "$*" >&2; exit 1; }
bm_warn() { printf 'benchmark warning: %s\n' "$*" >&2; }
bm_info() { printf '\033[1m==>\033[0m %s\n' "$*"; }
bm_step() { printf '    - %s\n' "$*"; }

bm_now_epoch() { date -u +%s; }
bm_now_iso()   { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Directory size in bytes, portable. GNU du has -b; BSD/macOS du does not, and
# its -k is the only unit both agree on. Never use `du -sb` in this suite.
bm_dir_bytes() {
  local target="$1" kib
  [[ -e "$target" ]] || { printf '0\n'; return 0; }
  kib="$(du -sk "$target" 2>/dev/null | awk 'NR==1{print $1}')"
  [[ -n "$kib" ]] || kib=0
  printf '%s\n' "$(( kib * 1024 ))"
}

bm_file_bytes() {
  local target="$1"
  [[ -f "$target" ]] || { printf '0\n'; return 0; }
  # wc -c is portable where stat's flags are not.
  wc -c < "$target" | tr -d ' '
}

bm_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || bm_die "required command not found: $1${2:+ ($2)}"
}

# Escape a string for embedding in JSON.
bm_json_escape() {
  python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))'
}

# JSON array of the remaining arguments.
bm_json_argv() {
  python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.argv[1:]))' "$@"
}

# --------------------------------------------------------------------------
# Peak workspace sampler
# --------------------------------------------------------------------------
# Samples the size of the run's --out tree, which is where the aggregate lives
# and therefore where plain vs space-optimized actually differs on the host.
#
# It does NOT see the ephemeral Docker volume used by the partitioned stage.
# That workspace is reported by the tool itself in
# stages/partitioned/<sample>.json ("workspace free-space samples"), which
# collect_metrics.py reads separately. Peak *host* footprint and peak *volume*
# footprint are two different numbers; do not add them or use one for the other.
bm_sampler_start() {
  local target="$1" out_file="$2"
  : > "$out_file"
  (
    while :; do
      printf '%s\t%s\n' "$(bm_now_epoch)" "$(bm_dir_bytes "$target")" >> "$out_file"
      sleep "$BM_SAMPLE_INTERVAL"
    done
  ) &
  BM_SAMPLER_PID=$!
}

bm_sampler_stop() {
  if [[ -n "${BM_SAMPLER_PID:-}" ]] && kill -0 "$BM_SAMPLER_PID" 2>/dev/null; then
    kill "$BM_SAMPLER_PID" 2>/dev/null || true
    wait "$BM_SAMPLER_PID" 2>/dev/null || true
  fi
  BM_SAMPLER_PID=""
}

bm_sampler_peak() {
  local out_file="$1"
  [[ -s "$out_file" ]] || { printf '0\n'; return 0; }
  awk -F'\t' 'BEGIN{m=0} {if ($2+0 > m) m=$2+0} END{print m}' "$out_file"
}

# --------------------------------------------------------------------------
# bm_run: the single entry point for every measured invocation
# --------------------------------------------------------------------------
# Usage: bm_run <experiment> <cell-label> -- <tool arguments without --out>
#
# Creates $BM_RESULTS/<experiment>/<cell-label>/, passes it as --out, samples
# the workspace, and writes bench.json. Returns the tool's exit code; it does
# NOT abort the script, because a refusal or an OOM is frequently the result an
# experiment is looking for (see 09_awkward_inputs.sh and 10_feasibility.sh).
bm_run() {
  local experiment="$1" label="$2"; shift 2
  [[ "${1:-}" == "--" ]] || bm_die "bm_run: expected -- before tool arguments"
  shift

  local cell_dir="$BM_RESULTS/$experiment/$label"
  if [[ -e "$cell_dir" ]]; then
    bm_die "cell already exists: $cell_dir
Each cell needs a fresh --out (the wrapper refuses to overwrite planned
artifacts). Move or remove it, or set BM_RESULTS to a new root."
  fi
  mkdir -p "$cell_dir"

  local out_dir="$cell_dir/out"
  local samples="$cell_dir/workspace_bytes.tsv"
  # Portable read loop rather than mapfile, so nothing here needs bash 4.
  local -a argv=()
  local token
  if [[ "${BM_RUN_RAW:-0}" == "1" ]]; then
    # The caller supplies the whole command line, including its own image
    # reference and mounts. Used by experiments that drive something other
    # than the wrapper CLI -- 14_regional_access runs a runner inside the
    # image directly, because the wrapper has no mode for it. Everything else
    # about the cell is recorded identically, so the two kinds of cell land in
    # the same dataset.
    argv+=("$@")
  else
    while IFS= read -r token; do argv+=("$token"); done < <(bm_tool_argv)
    argv+=("$@")
    while IFS= read -r token; do argv+=("$token"); done < <(bm_image_argv)
    argv+=(--out "$out_dir")
  fi

  bm_step "$label"
  if [[ "$BM_DRY_RUN" == "1" ]]; then
    bm_json_argv "${argv[@]}" > "$cell_dir/command.json"
    printf '%s\n' "${argv[*]}" > "$cell_dir/command.txt"
    python3 -c '
import json, pathlib, sys
pathlib.Path(sys.argv[1], "bench.json").write_text(json.dumps(
    {"experiment": sys.argv[2], "cell": sys.argv[3], "dry_run": True,
     "skipped": True, "reason": "BM_DRY_RUN=1",
     "command": json.loads(pathlib.Path(sys.argv[1], "command.json").read_text())},
    indent=2) + "\n")
' "$cell_dir" "$experiment" "$label"
    # So the assertions below stay no-ops rather than failing on a plan-only run.
    BM_LAST_RC=0
    BM_LAST_DIR="$cell_dir"
    BM_LAST_DRY_RUN=1
    return 0
  fi
  BM_LAST_DRY_RUN=0

  bm_json_argv "${argv[@]}" > "$cell_dir/command.json"
  printf '%s\n' "${argv[*]}" > "$cell_dir/command.txt"

  mkdir -p "$out_dir"
  bm_sampler_start "$out_dir" "$samples"

  local start end rc=0
  start="$(bm_now_epoch)"
  set +e
  "${argv[@]}" > "$cell_dir/stdout.log" 2> "$cell_dir/stderr.log"
  rc=$?
  set -e
  end="$(bm_now_epoch)"

  bm_sampler_stop

  BM_LAST_RC="$rc"
  BM_LAST_DIR="$cell_dir"

  # All fourteen values the record unpacks, in order. Two things here are not
  # optional. The image trio is what lets a number be attributed to a build.
  # The host is what lets it be attributed to a MACHINE: experiments are split
  # across benchmark VMs to run in parallel, and a merged dataset whose rows
  # cannot say which machine produced them cannot support a timing claim.
  python3 - "$cell_dir" "$experiment" "$label" "$rc" "$start" "$end" \
    "$(bm_sampler_peak "$samples")" "$(bm_dir_bytes "$out_dir")" \
    "$(bm_tool_commit)" "$BM_TOOL" \
    "$BM_IMAGE_REF" "$BM_IMAGE_DIGEST" "$BM_IMAGE_MODE" \
    "$(hostname)" <<'PYEOF'
import json, pathlib, sys
_args = sys.argv[1:]
if len(_args) != 14:
    # This went wrong once already: the record grew three fields and the shell
    # call did not, so every cell in every experiment died on "not enough
    # values to unpack (expected 13, got 10)". Say which side is short.
    raise SystemExit(
        "bm_run: record expects 14 values, shell passed %d. "
        "The python heredoc and its argument list are out of sync." % len(_args)
    )
(cell, experiment, label, rc, start, end, peak, final, commit, tool,
 image_ref, image_digest, image_mode, host) = _args
cell = pathlib.Path(cell)
record = {
    "experiment": experiment,
    "cell": label,
    "exit_code": int(rc),
    "started_epoch": int(start),
    "ended_epoch": int(end),
    "wrapper_wall_seconds": int(end) - int(start),
    "peak_out_tree_bytes": int(peak),
    "final_out_tree_bytes": int(final),
    "tool_commit": commit,
    "tool_path": tool,
    "image_ref": image_ref,
    "image_digest": image_digest,
    "image_mode": image_mode,
    "host": host,
    "command": json.loads((cell / "command.json").read_text()),
}
(cell / "bench.json").write_text(json.dumps(record, indent=2) + "\n")
PYEOF

  if (( rc != 0 )); then
    bm_step "  exit $rc (recorded; see $cell_dir/stderr.log)"
  fi
  return 0
}

# Run a command line verbatim, recorded exactly as bm_run records a wrapper
# invocation. The cell's output directory is $BM_RESULTS/<exp>/<label>/out and
# is created before the command runs, so the caller can mount it.
bm_run_raw() {
  local experiment="$1" label="$2"; shift 2
  [[ "${1:-}" == "--" ]] || bm_die "bm_run_raw: expected -- before the command"
  shift
  # Do not create the cell here: bm_run refuses a cell that already exists, and
  # it creates out/ itself before the command runs, which is early enough for a
  # bind mount.
  BM_RUN_RAW=1 bm_run "$experiment" "$label" -- "$@"
}

# Abort unless the last bm_run succeeded. Use in experiments where a failure
# invalidates everything downstream; omit where a non-zero exit is the result.
# Record what the experiment asserted about a cell, so a reader of bench.json
# does not have to infer it from the exit code.
#
# Exit codes alone are ambiguous here. 06's refusal cells exit 2 *because the
# refusal is the thing being tested*, and 09 runs awkward fixtures where a
# refusal is a valid recorded outcome -- yet both looked identical to a genuine
# failure, so the campaign summary reported five failures that were not.
#
# "ok"        the run was asserted to succeed
# "refusal"   the run was asserted to fail, with a specific message
# "recorded"  no assertion: the exit code is data, not a verdict
#
# Absence of a marker means the same as "ok": a non-zero exit is a failure.
# That is deliberate -- 13_query_cost asserts nothing and its three cottas
# mismatches were real, so silence must not be read as permission to fail.
bm_record_assertion() {
  local kind="$1" note="${2:-}"
  [[ "${BM_LAST_DRY_RUN:-0}" == "1" ]] && return 0
  [[ -f "${BM_LAST_DIR:-}/bench.json" ]] || return 0
  python3 - "$BM_LAST_DIR" "$kind" "$note" <<'PY' || true
import json, pathlib, sys
path = pathlib.Path(sys.argv[1], "bench.json")
try:
    record = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
record["assertion"] = sys.argv[2]
if sys.argv[3]:
    record["assertion_note"] = sys.argv[3]
path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
PY
}

# No assertion: the exit code is an observation. Use this where a refusal is a
# legitimate result rather than a defect, so it is recorded as such instead of
# being inferred from a comment in the script.
bm_record_outcome() {
  bm_record_assertion "recorded" "${1:-}"
}

# Cells that failed, reported once when the experiment ends.
BM_FAILED_CELLS=()

# Record a failed cell and CONTINUE. The experiment still exits non-zero, via
# the EXIT trap below, so run_all.sh flags it exactly as before.
#
# This used to be an immediate bm_die, and that made one bad cell hide every
# cell after it. 11_covering_set's row 2 failed, rows 3-6 never ran, and the
# sweep recorded 2 of 6 rows -- so its whole point, a coverage property, could
# not even be measured. The failure was worth knowing; losing the four rows
# after it was not.
#
# Continuing is safe because every inter-cell dependency in this suite is
# already guarded by an artifact-existence check that calls bm_skip with a
# reason (see 08_robustness's roundtrip/index chains and 12_modes_smoke's
# Phase B). Those guards, not this abort, are what stop a missing artifact from
# cascading. If you add a cell that consumes an earlier cell's output, guard it
# the same way rather than relying on this function to stop the script.
bm_expect_ok() {
  [[ "${BM_LAST_DRY_RUN:-0}" == "1" ]] && return 0
  bm_record_assertion "ok"
  [[ "${BM_LAST_RC:-1}" == "0" ]] && return 0
  local dir="${BM_LAST_DIR:-?}" cell exp
  cell="$(basename -- "$dir" 2>/dev/null || printf '?')"
  exp="$(basename -- "$(dirname -- "$dir")" 2>/dev/null || printf '?')"
  BM_FAILED_CELLS+=("${exp}/${cell} exit=${BM_LAST_RC:-?}  ${dir}/stderr.log")
  bm_warn "cell failed, continuing: ${exp}/${cell} exit=${BM_LAST_RC:-?}
See ${dir}/stderr.log"
  return 0
}

# Report every failed cell once, and make the experiment exit non-zero so
# run_all.sh still lists it under "Experiments that exited non-zero".
_bm_report_failed_cells() {
  local rc=$?
  trap - EXIT
  if (( ${#BM_FAILED_CELLS[@]} )); then
    printf '\nCells that failed in %s:\n' "${EXPERIMENT:-this experiment}" >&2
    printf '  %s\n' "${BM_FAILED_CELLS[@]}" >&2
    printf 'Every other cell still ran and is recorded.\n' >&2
    [[ "$rc" == "0" ]] && rc=1
  fi
  exit "$rc"
}
trap _bm_report_failed_cells EXIT

# Abort unless the last bm_run failed with the given message fragment.
bm_expect_refusal() {
  local fragment="$1"
  [[ "${BM_LAST_DRY_RUN:-0}" == "1" ]] && return 0
  [[ "${BM_LAST_RC:-0}" != "0" ]] || bm_die "expected a refusal but the run succeeded: ${BM_LAST_DIR:-?}"
  grep -qF -- "$fragment" "${BM_LAST_DIR}/stderr.log" \
    || bm_die "refusal did not mention '$fragment': ${BM_LAST_DIR}/stderr.log"
  # Only once both checks pass: a cell marked "refusal" is one where the
  # refusal was demanded and delivered, not merely one that exited non-zero.
  bm_record_assertion "refusal" "$fragment"
}

# --------------------------------------------------------------------------
# Input resolution
# --------------------------------------------------------------------------
# Resolve a corpus or fixture name to an absolute path. Accepts an absolute
# path, a name under vcf_data/, one under vcf_data/derived/, or a fixture from
# the tool checkout's test/test_vcf_files/.
# Locate an input without dying. Prints the path and returns 0, or returns 1.
# This is the primitive; bm_vcf and bm_have_vcf are both built on it.
#
# Keep it that way. An earlier version had bm_have_vcf call bm_vcf with stderr
# redirected, which looks like a safe probe and is not: a redirection is not a
# subshell, so bm_die's `exit 1` tore down the whole script — silently, because
# the message went to /dev/null. Every "input missing -> skip the cell" path in
# the suite depends on this function not exiting.
bm_find_vcf() {
  local name="$1" candidate
  # -s, not -f: an empty file is not an input. A corpus file truncated to zero
  # -- by an interrupted download, a full disk, a botched copy -- passes -f and
  # then produces a cell built from no records rather than a skip, which is far
  # harder to notice than a missing input.
  #
  # -s follows symlinks, which matters here: the corpus files are symlinks to
  # their upstream names (HG005_GRCh38.vcf.gz -> HG005_GRCh38_1_22_v4.2.1_...),
  # so the test must ask about the target rather than the 41-byte link. `du -h`
  # on those links reports 0, which reads alarmingly like a truncated file and
  # is not one.
  if [[ "$name" == /* ]]; then
    [[ -s "$name" ]] || return 1
    printf '%s\n' "$name"
    return 0
  fi
  for candidate in "$BM_VCF_DATA/$name" "$BM_DERIVED/$name" \
                   "$(dirname -- "$BM_TOOL")/test/test_vcf_files/$name"; do
    if [[ -s "$candidate" ]]; then printf '%s\n' "$candidate"; return 0; fi
  done
  return 1
}

# Resolve an input or abort. Use only where a missing input is fatal.
bm_vcf() {
  local resolved
  if resolved="$(bm_find_vcf "$1")"; then
    printf '%s\n' "$resolved"
    return 0
  fi
  bm_die "input not found: $1
Looked in $BM_VCF_DATA, $BM_DERIVED, and the tool checkout's test/test_vcf_files.
Corpus files are downloaded by scripts/download_test_data.sh; derived ladders
are built by benchmarks/02_derive_ladders.sh."
}

# True when the named input exists. Never exits.
bm_have_vcf() { bm_find_vcf "$1" >/dev/null; }

# First existing file matching a glob under a directory, or empty. `find`
# returns non-zero on a missing directory, which under `set -e` would abort the
# script mid-experiment, so every lookup goes through here.
bm_first_file() {
  local root="$1" pattern="$2" depth="${3:-3}"
  [[ -d "$root" ]] || { printf '\n'; return 0; }
  find "$root" -maxdepth "$depth" -name "$pattern" 2>/dev/null | head -1
}

# Skip a cell with a recorded reason rather than failing the sweep.
# Stream a VCF, gzipped or not.
#
# A reader that stops early (awk `exit`, head) closes this pipe and the
# decompressor is killed with SIGPIPE -> 141, which under `set -euo pipefail`
# aborts the whole script. It only bites when the source is large enough that
# the decompressor is still streaming when the reader quits, which is why it
# went unnoticed until 1000G_phase3_chr20.vcf.gz (327 MB gzipped, 18.4 GB
# inflated). A truncated read is intended at every call site, so 141 is
# success; any other status still propagates.
bm_cat_vcf() {
  local rc=0
  case "$1" in
    *.gz) gzip -dc -- "$1" || rc=$? ;;
    *)    cat -- "$1" || rc=$? ;;
  esac
  if (( rc == 141 )); then return 0; fi
  return "$rc"
}

# Sample-column count from a VCF header. Reads only as far as #CHROM.
bm_vcf_samples() {
  bm_cat_vcf "$1" | awk -F'\t' '/^#CHROM/ { print (NF > 9 ? NF - 9 : 0); exit }'
}

# Skip a cell whose sample count makes the expanded representation infeasible.
#
# The expanded representation emits per sample per record, so cost is
# records x samples. A cohort file is small on disk and enormous once expanded:
# 1000G_phase3_chr20 is 327 MB gzipped, but at 1,812,841 records x 2,504
# samples it reached 23 GB after 20,000 variants (1.1%) -- about 2.1 TB for the
# whole file, against a 189 GB volume. Unguarded it fills the disk and dies,
# and because every experiment loop is serial, everything after it waits behind
# a cell that cannot finish.
#
# Guard on samples rather than bytes, because the fan-out is per-sample. Only
# `expanded` is affected; `condensed` is ~S + (V x F) and stays tractable, so a
# cohort file still gets its condensed cell -- which is the comparison §2 is
# actually making.
#
# Returns 0 when it skipped (caller should `continue`), 1 to proceed.
bm_skip_if_cohort_scale() {
  local experiment="$1" label="$2" vcf="$3" mode="${4:-expanded}"
  [[ "$mode" == "expanded" ]] || return 1
  local max="${BM_CORPUS_MAX_SAMPLES:-1000}" samples
  samples="$(bm_vcf_samples "$vcf")"
  [[ -n "$samples" ]] || return 1
  (( samples > max )) || return 1
  bm_skip "$experiment" "$label" \
    "$samples sample columns exceeds BM_CORPUS_MAX_SAMPLES=$max; the expanded representation emits records x samples calls, which does not fit this volume. The condensed cell for the same input still runs. Raise BM_CORPUS_MAX_SAMPLES to force it."
  return 0
}

bm_skip() {
  local experiment="$1" label="$2" reason="$3"
  local cell_dir="$BM_RESULTS/$experiment/$label"
  mkdir -p "$cell_dir"
  python3 -c '
import json, pathlib, sys
pathlib.Path(sys.argv[1], "bench.json").write_text(
    json.dumps({"experiment": sys.argv[2], "cell": sys.argv[3],
                "skipped": True, "reason": sys.argv[4]}, indent=2) + "\n")
' "$cell_dir" "$experiment" "$label" "$reason"
  bm_step "$label — SKIPPED: $reason"
}

bm_banner() {
  printf '\n=== %s ===\n' "$*"
}

bm_resolve_tool

# One image reference for the whole session, resolved before anything runs.
if bm_image_is_local; then
  BM_IMAGE_REF="$(bm_local_image_tag)"
  BM_IMAGE_MODE="local-build"
else
  BM_IMAGE_REF="${BM_IMAGE}:${BM_IMAGE_VERSION}"
  BM_IMAGE_MODE="pinned-release"
fi

# Build now if needed, so the first cell does not pay for it and a build
# failure surfaces before any measurement is taken.
bm_ensure_local_image

# Resolved once, so 30 cells do not each shell out to Docker.
BM_IMAGE_DIGEST="$(bm_image_digest)"
