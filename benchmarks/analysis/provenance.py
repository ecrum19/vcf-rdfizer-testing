#!/usr/bin/env python3
"""Record, per host, the exact bits that produced this host's cells.

bench.json records tool_commit and an image *tag*. The tag is not unique: each
host built vcf-rdfizer:local-025fb7d independently, so the tags match while the
image IDs do not. For a publication the digest is the honest provenance, so it
is captured here alongside the git state.
"""
import json, os, socket, subprocess, datetime

def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:
        return "ERROR: %s" % e

HOME = os.path.expanduser("~")
TOOL = os.path.join(HOME, "VCF-RDFizer")
REPO = os.path.join(HOME, "vcf-rdfizer-testing")
host = socket.gethostname()

def _short_head(repo):
    return sh("git", "-C", repo, "rev-parse", "--short", "HEAD")

# Derive the tag from the checkout rather than hardcoding one. The first version
# of this script pinned vcf-rdfizer:local-025fb7d, so once bench-1 moved to
# a3679e1 and then 20d2cbb it kept recording the OLD image's digest against the
# new commits -- provenance that points at the wrong bits is worse than none.
IMAGE = "vcf-rdfizer:local-%s" % (_short_head(TOOL) or "unknown")

def git(repo, *args):
    return sh("git", "-C", repo, *args)

rec = {
    "recorded_at": datetime.datetime.now().astimezone().isoformat(),
    "host": host,
    "note": ("Image tags are identical across hosts but the images were built "
             "independently and their digests differ. Cite the digest, not the tag."),
    "tool_repo": {
        "head": git(TOOL, "rev-parse", "HEAD"),
        "head_short": git(TOOL, "rev-parse", "--short", "HEAD"),
        "branch": git(TOOL, "rev-parse", "--abbrev-ref", "HEAD"),
        "subject": git(TOOL, "log", "--oneline", "-1"),
        "dirty": git(TOOL, "status", "--porcelain"),
    },
    "harness_repo": {
        "head": git(REPO, "rev-parse", "HEAD"),
        "subject": git(REPO, "log", "--oneline", "-1"),
        "dirty": git(REPO, "status", "--porcelain", "--untracked-files=no"),
    },
    "images_present": [
        line.split(" ", 1)
        for line in sh(
            "docker", "images", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"
        ).splitlines()
        if line.startswith("vcf-rdfizer:")
    ],
    "image": {
        "tag": IMAGE,
        "id": sh("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"),
        "created": sh("docker", "image", "inspect", IMAGE, "--format", "{{.Created}}"),
        "layers": sh("docker", "image", "inspect", IMAGE, "--format",
                     "{{range .RootFS.Layers}}{{println .}}{{end}}").split(),
    },
    "platform": {
        "kernel": sh("uname", "-r"),
        "docker": sh("docker", "--version"),
        "python": sh("python3", "--version"),
        "cpu_model": sh("bash", "-c", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2-").strip(),
        "cpu_count": os.cpu_count(),
        "mem_total_kb": sh("bash", "-c", "grep MemTotal /proc/meminfo | awk '{print $2}'"),
    },
}

outdir = os.path.join(REPO, "benchmarks_outputs", "00_environment")
os.makedirs(outdir, exist_ok=True)
short = rec["tool_repo"]["head_short"] or "unknown"
path = os.path.join(outdir, "provenance.%s.%s.json" % (host, short))
with open(path, "w") as fh:
    json.dump(rec, fh, indent=2, sort_keys=True)
print("wrote", path)
print("  tool  ", rec["tool_repo"]["subject"])
print("  image ", rec["image"]["id"][:24], "created", rec["image"]["created"][:19])
