#!/usr/bin/env bash
# Capture the environment manifest. Run this FIRST and once per session.
#
# Every comparison in this suite assumes one machine, one pinned tool, one
# storage device and one parallelism setting. This script records what those
# were, so numbers from different sessions can be told apart later. Comparing
# runs without it is meaningless (plan §5.4).

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

MANIFEST_DIR="$BM_RESULTS/00_environment"
mkdir -p "$MANIFEST_DIR"
MANIFEST="$MANIFEST_DIR/manifest.json"

bm_banner "Environment manifest"

bm_step "tool: $BM_TOOL ($BM_TOOL_KIND)"
bm_step "commit: $(bm_tool_commit)"
bm_step "image:  $BM_IMAGE_REF ($BM_IMAGE_MODE)"
bm_step "digest: $BM_IMAGE_DIGEST"

# Host facts, collected portably. Missing values are recorded as null rather
# than guessed.
python3 - "$MANIFEST" "$BM_TOOL" "$BM_TOOL_KIND" "$(bm_tool_commit)" "$BM_REPO" \
  "$BM_IMAGE_REF" "$BM_IMAGE_DIGEST" "$BM_IMAGE_MODE" <<'PYEOF'
import json, os, pathlib, platform, shutil, subprocess, sys, time

(manifest_path, tool, tool_kind, tool_commit, repo,
 image_ref, image_digest, image_mode) = sys.argv[1:9]


def cmd(*argv):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def cpu_count():
    try:
        return os.cpu_count()
    except Exception:
        return None


def total_memory_bytes():
    # Linux
    meminfo = pathlib.Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    # macOS
    value = cmd("sysctl", "-n", "hw.memsize")
    return int(value) if value and value.isdigit() else None


def swap_state():
    swaps = pathlib.Path("/proc/swaps")
    if swaps.exists():
        lines = [l for l in swaps.read_text().splitlines()[1:] if l.strip()]
        return {"configured": bool(lines), "entries": len(lines)}
    return {"configured": None, "entries": None}


def repo_commit(path):
    out = cmd("git", "-C", path, "rev-parse", "HEAD")
    dirty = subprocess.run(["git", "-C", path, "diff", "--quiet"]).returncode != 0
    return f"{out}{'-dirty' if dirty and out else ''}" if out else None


def disk_free_bytes(path):
    try:
        usage = shutil.disk_usage(path)
        return {"total": usage.total, "free": usage.free}
    except OSError:
        return None


manifest = {
    "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "tool": {"path": tool, "kind": tool_kind, "commit": tool_commit},
    "image": {
        # The digest is the only thing that actually identifies what ran: two
        # machines can hold different images under the same tag, and the tool
        # only pulls when --image-version is given explicitly.
        "reference": image_ref,
        "digest": image_digest,
        "mode": image_mode,
        "reproducible": image_mode == "pinned-release" or not image_ref.endswith("-dirty"),
    },
    "testing_repo_commit": repo_commit(repo),
    "host": {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": cpu_count(),
        "total_memory_bytes": total_memory_bytes(),
        "swap": swap_state(),
        "hostname": platform.node(),
    },
    "software": {
        "python": sys.version.split()[0],
        "docker": cmd("docker", "--version"),
        "bcftools": cmd("bcftools", "--version"),
        "awk": cmd("awk", "--version") or cmd("awk", "-W", "version"),
        "git": cmd("git", "--version"),
        "bash": os.environ.get("BASH_VERSION"),
    },
    "storage": {
        "results_root": os.environ.get("BM_RESULTS"),
        "disk": disk_free_bytes(pathlib.Path(manifest_path).parent),
    },
    "pinned_settings": {
        # The plan requires these fixed across every comparison (§5.4). They are
        # recorded here so a later run can be checked against them, and because
        # a default is a policy that can change between releases: a manifest has
        # to name the mechanism that ran, not "the default".
        "rdf_storage_mode": "space-optimized (tool default since 2026-09-10; pinned explicitly by every script here)",
        "hdt_strategy": "partitioned (pinned explicitly; never 'auto' in a recorded run)",
        "spark_partitions": os.environ.get("BM_SPARK_PARTITIONS", "8"),
    },
    "notes": [
        "One experiment at a time. Two concurrent runs invalidate memory and timing.",
        "Local-build mode tags the image with the commit that built it. A dirty "
        "tree yields a '-dirty' tag that does not identify one source state; "
        "commit before a publishable run. Set BM_IMAGE_VERSION to reproduce "
        "against a published release instead.",
        "10_feasibility.sh is the only script that deliberately imposes a memory ceiling.",
    ],
}

pathlib.Path(manifest_path).write_text(json.dumps(manifest, indent=2) + "\n")
print(f"wrote {manifest_path}")

missing = [k for k, v in manifest["software"].items() if v is None]
if missing:
    print("  note: not detected -> " + ", ".join(missing))
PYEOF

# The tool's own system-condition reporter, if the repo ships it.
if [[ -f "$BM_REPO/scripts/report_system_conditions.py" ]]; then
  bm_step "system conditions -> $MANIFEST_DIR/system_conditions.txt"
  python3 "$BM_REPO/scripts/report_system_conditions.py" --format both \
    -o "$MANIFEST_DIR/system_conditions.txt" >/dev/null 2>&1 \
    || bm_warn "report_system_conditions.py failed; manifest.json still written"
fi

bm_info "Environment captured: $MANIFEST"
