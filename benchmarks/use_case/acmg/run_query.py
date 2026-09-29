#!/usr/bin/env python3
"""Answer a SPARQL query over a set of graphs with QLever.

Runs INSIDE the VCF-RDFizer image, with the image's Python (the QLever engine
lives in its validation runner):

    run_query.py --query carriers.rq [--query rare.rq] --out <dir> --replicates 3 graph.nt[.gz] ...

Each input is streamed into the index through a FIFO as a named graph of its
own (urn:vcf-rdfizer:input:<file name>), so no concatenated copy is written and
every triple keeps the file it came from. A query without GRAPH sees them all.

Writes <out>/<query>.tsv (the query's own columns) and <out>/<query>.json per
query, and <out>/timing.json: setup, triples per input, then each query's
replicate wall times. Every query runs against the same index. Setup and query
time are reported separately, never summed. QLever's result cache is cleared
before every replicate, so each one is a cold query.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/vcf-rdfizer/validation")
import validation_runner as V  # noqa: E402

COUNT_PER_GRAPH = "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g"


def graph_iri(path: Path) -> str:
    return "urn:vcf-rdfizer:input:" + path.name


def index_command(graphs: list[Path], fifos: list[Path]) -> str:
    """A qlever-index command reading each graph, from its FIFO, into its own named graph.

    {index} and {memory} are filled in by the engine (QLEVER_INDEX_COMMAND).
    """
    builder = os.environ.get("QLEVER_INDEX_BUILDER_BIN", f"{V.QLEVER_BIN_DIR}/qlever-index")
    argv = [builder, "-i", "{index}", "-m", "{memory}"]
    for graph, fifo in zip(graphs, fifos):
        argv += ["-f", str(fifo), "-F", "nt", "-g", graph_iri(graph)]
    return " ".join(shlex.quote(part) for part in argv)


def stream(graphs: list[Path], work: Path) -> tuple[list[Path], list[subprocess.Popen]]:
    """Start one decompressor per graph, each writing into a FIFO the index builder reads.

    The shell opens the FIFO, so a writer blocks in its own process until the
    builder gets to that input, never in this one. gzip -f passes plain files through.
    """
    fifos, writers = [], []
    for number, graph in enumerate(graphs):
        fifo = work / f"input{number}.nt"
        os.mkfifo(fifo)
        fifos.append(fifo)
        writers.append(subprocess.Popen(
            f"gzip -dcf {shlex.quote(str(graph))} > {shlex.quote(str(fifo))}", shell=True))
    return fifos, writers


def clear_cache(port: int) -> None:
    """Empty QLever's result cache: otherwise a repeated query is answered from it."""
    urllib.request.urlopen(f"http://127.0.0.1:{port}/?cmd=clear-cache", timeout=60).read()


def write_rows(bindings: list[dict], columns: list[str], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for binding in bindings:
            writer.writerow([binding.get(c, {}).get("value", "") for c in columns])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--query", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--query-timeout", type=int, default=3600)
    parser.add_argument("--memory-gb", type=int, default=8)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/work"))
    parser.add_argument("graphs", type=Path, nargs="+")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    columns = {}
    for query in args.query:
        select = next(line for line in query.read_text(encoding="utf-8").splitlines() if line.startswith("SELECT"))
        columns[query.stem] = [token.lstrip("?") for token in select.split() if token.startswith("?")]
    timing = {"engine": "qlever", "graphs": [g.name for g in args.graphs],
              "replicates": {name: [] for name in columns}, "cache": "cleared before each replicate"}

    with tempfile.TemporaryDirectory(dir=args.scratch_dir) as work:
        work = Path(work)
        fifos, writers = stream(args.graphs, work)
        os.environ["QLEVER_INDEX_COMMAND"] = index_command(args.graphs, fifos)
        (work / "raw").mkdir()
        engine = V.build_engine("qlever", args.graphs[0], raw_dir=work / "raw", scratch=work,
                                options={"query_timeout": args.query_timeout,
                                         "memory_gb": args.memory_gb})
        try:
            with engine:
                # A writer that failed or was cut off means an input is missing
                # from the index; nothing queried over it would be reportable.
                failed = [g.name for g, w in zip(args.graphs, writers) if w.wait() != 0]
                if failed:
                    raise RuntimeError(f"inputs not fully read into the index: {failed}")
                timing["setup_seconds"] = engine.setup_seconds
                count = work / "count.rq"
                count.write_text(COUNT_PER_GRAPH, encoding="utf-8")
                rows = V.bindings(Path(engine.execute("count", count)["rawResult"]))
                timing["triples_per_graph"] = {r["g"]["value"].rsplit(":", 1)[1]: int(r["n"]["value"])
                                               for r in rows}
                timing["triples"] = sum(timing["triples_per_graph"].values())
                for query in args.query:
                    name = query.stem
                    for replicate in range(1, args.replicates + 1):
                        clear_cache(engine.port)
                        envelope = engine.execute(f"{name}__r{replicate}", query)
                        timing["replicates"][name].append(envelope["wallSeconds"])
                        if envelope["status"] != "PASS":
                            timing["error"] = f"{name}: " + (envelope.get("error") or "engine execution failed")
                            break
                        if replicate == 1:
                            write_rows(V.bindings(Path(envelope["rawResult"])), columns[name],
                                       args.out / f"{name}.tsv")
                            shutil.copy(envelope["rawResult"], args.out / f"{name}.json")
                    if "error" in timing:
                        break
        finally:
            for writer in writers:
                if writer.poll() is None:
                    writer.kill()

    (args.out / "timing.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: timing.get(k) for k in ("triples", "setup_seconds", "replicates")}))
    return 1 if "error" in timing else 0


if __name__ == "__main__":
    raise SystemExit(main())
