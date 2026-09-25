#!/usr/bin/env python3
"""Inspect the scale store that 15_scale_prepare.sh writes.

The store holds graphs that cost hours to build and are queried long after the
session that produced them. This is the tool for answering "what is in there,
and is it still intact" without reading JSON by hand.

``verify`` re-hashes every artifact against its manifest. That matters because
the failure mode here is silent: a truncated or partly-deleted artifact still
has a path and a plausible size, and querying it would produce timings for a
graph that is not the one the manifest describes.

Usage:
    python3 scale_store.py list             # what is built, and how big
    python3 scale_store.py verify [scale]   # re-hash artifacts (slow, exact)
    python3 scale_store.py show <scale>     # the whole manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys


def default_store() -> pathlib.Path:
    env = os.environ.get("BM_SCALE_STORE")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent.parent.parent / "scale_store"


def manifests(store: pathlib.Path) -> list[tuple[str, dict]]:
    if not store.is_dir():
        return []
    found = []
    for entry in sorted(store.iterdir()):
        path = entry / "manifest.json"
        if path.is_file():
            try:
                found.append((entry.name, json.loads(path.read_text())))
            except json.JSONDecodeError:
                found.append((entry.name, {"error": "unreadable manifest"}))
    return found


def human(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}PB"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cmd_list(store: pathlib.Path) -> int:
    found = manifests(store)
    if not found:
        print(f"no built graphs in {store}")
        print("build one with: ./15_scale_prepare.sh r1000000")
        return 0
    print(f"store: {store}\n")
    print(f"{'scale':<12}{'triples':>14}  {'artifacts':<34}{'built':>10}  provenance")
    for name, manifest in found:
        arts = manifest.get("artifacts", {})
        art_text = " ".join(
            f"{kind}:{human(entry['bytes'])}" for kind, entry in sorted(arts.items())
        )
        prov = manifest.get("provenance", {})
        build_h = prov.get("buildWallSeconds")
        build_text = f"{build_h / 3600:.2f}h" if isinstance(build_h, (int, float)) else "?"
        triples = manifest.get("triples")
        print(f"{name:<12}{triples if triples is not None else '?':>14}  "
              f"{art_text:<34}{build_text:>10}  "
              f"{(prov.get('toolCommit') or '?')[:7]} {prov.get('imageRef', '?')}")
        # A missing file is the thing most worth knowing, so say it here rather
        # than only under `verify`.
        for kind, entry in sorted(arts.items()):
            if not pathlib.Path(entry["path"]).is_file():
                print(f"  MISSING {kind}: {entry['path']}", file=sys.stderr)
    return 0


def cmd_verify(store: pathlib.Path, only: str | None) -> int:
    found = [(n, m) for n, m in manifests(store) if only in (None, n)]
    if not found:
        print(f"nothing to verify in {store}", file=sys.stderr)
        return 1
    bad = 0
    for name, manifest in found:
        print(f"{name}:")
        for kind, entry in sorted(manifest.get("artifacts", {}).items()):
            path = pathlib.Path(entry["path"])
            if not path.is_file():
                print(f"  {kind:<8} MISSING  {path}")
                bad += 1
                continue
            size = path.stat().st_size
            if size != entry["bytes"]:
                print(f"  {kind:<8} SIZE     {size} != {entry['bytes']} recorded")
                bad += 1
                continue
            actual = sha256(path)
            if actual != entry["sha256"]:
                print(f"  {kind:<8} DIGEST   {actual[:12]} != {entry['sha256'][:12]} recorded")
                bad += 1
            else:
                print(f"  {kind:<8} ok       {human(size)}  {actual[:12]}")
    if bad:
        print(f"\n{bad} artifact(s) do not match the manifest. Do not query them: "
              f"a timing from a graph that is not the recorded graph is not a result.",
              file=sys.stderr)
        return 1
    print("\nall artifacts match their manifests")
    return 0


def cmd_show(store: pathlib.Path, scale: str) -> int:
    for name, manifest in manifests(store):
        if name == scale:
            print(json.dumps(manifest, indent=2))
            return 0
    print(f"no manifest for scale {scale!r} in {store}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("list", "verify", "show"))
    parser.add_argument("scale", nargs="?", default=None)
    parser.add_argument("--store", type=pathlib.Path, default=None)
    args = parser.parse_args()
    store = args.store or default_store()

    if args.command == "list":
        return cmd_list(store)
    if args.command == "verify":
        return cmd_verify(store, args.scale)
    if not args.scale:
        parser.error("show needs a scale id")
    return cmd_show(store, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
