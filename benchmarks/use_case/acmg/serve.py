#!/usr/bin/env python3
"""Serve N-Triples files as a QLever SPARQL endpoint until stopped.

Runs INSIDE the VCF-RDFizer image; the harness publishes the port and points
vcf-rdfizer-policy's --endpoint at it:

    serve.py --port 7201 --scratch-dir /tmp/s graph.nt[.gz] ...

The index is built the way run_query.py builds it (each input streamed through
a FIFO into a named graph of its own), then qlever-server runs in the
foreground, so the container's lifetime is the endpoint's.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_query import V, index_command, stream  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--memory-gb", type=int, default=8)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/tmp/serve"))
    parser.add_argument("graphs", type=Path, nargs="+")
    args = parser.parse_args(argv)

    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    fifos, writers = stream(args.graphs, args.scratch_dir)
    index = args.scratch_dir / "index"
    command = index_command(args.graphs, fifos).format(index=index, memory=f"{args.memory_gb}G")
    os.environ["LD_LIBRARY_PATH"] = f"{V.QLEVER_LIB_DIR}:{os.environ.get('LD_LIBRARY_PATH', '')}"
    if os.system(command) != 0 or any(w.wait() != 0 for w in writers):
        print("index build failed", file=sys.stderr)
        return 1
    server = os.environ.get("QLEVER_SERVER_BIN", f"{V.QLEVER_BIN_DIR}/qlever-server")
    os.execv(server, [server, "-i", str(index), "-p", str(args.port), "-m", f"{args.memory_gb}G",
                      "-s", "3600s"])


if __name__ == "__main__":
    raise SystemExit(main())
