#!/usr/bin/env python3
"""BioInterchange's line-delimited JSON-LD to N-Quads, offline.

    python3 -I bi_jsonld_to_nquads.py <context.json> <in.ldj> <out.nq>

BioInterchange writes one JSON-LD document per line, each naming a remote context under
raw.githubusercontent.com/BioInterchange/BioInterchangeC/context/, which now returns 404. Every
context file at the pinned commit is byte-identical, so the one given here (vcf-f1.json from that
commit) is inlined in place of the URL, and any other remote document is refused.

A line that is not valid JSON (BioInterchange writes strings without escaping them) cannot be
read as JSON-LD by anything. It is skipped, and its line number and the parser's message are
written to <out.nq>.invalid.json, so the loss is counted rather than hidden.

PyLD, not rdflib: rdflib's JSON-LD parser turns a null @list into rdf:nil, which would turn a FILTER
of "." into PASS. Blank-node labels are prefixed with the line number, because each line is a
separate document whose labels would otherwise collide.
"""
import json
import re
import sys

from pyld import jsonld

CONTEXT_PREFIX = "https://raw.githubusercontent.com/BioInterchange/BioInterchangeC/context/"
BLANK = re.compile(r"_:b(\d+)")


def refuse(url, options=None):
    raise RuntimeError(f"remote document requested: {url}")


def main() -> int:
    context = json.load(open(sys.argv[1], encoding="utf-8"))["@context"]
    jsonld.set_document_loader(refuse)
    invalid = []
    lines = 0
    with open(sys.argv[2], encoding="utf-8") as source, open(sys.argv[3], "w", encoding="utf-8") as sink:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            lines += 1
            try:
                document = json.loads(line)
            except json.JSONDecodeError as error:
                invalid.append({"line": number, "error": str(error), "start": line[:160]})
                continue
            named = document.get("@context")
            if not (isinstance(named, str) and named.startswith(CONTEXT_PREFIX)):
                raise SystemExit(f"line {number}: unexpected @context {named!r}")
            document["@context"] = context
            quads = jsonld.to_rdf(document, {"format": "application/n-quads"})
            sink.write(BLANK.sub(lambda match: f"_:l{number}b{match.group(1)}", quads))
    with open(sys.argv[3] + ".invalid.json", "w", encoding="utf-8") as report:
        json.dump({"lines": lines, "invalid": len(invalid), "invalidLines": invalid}, report, indent=2)
    print(f"{lines} JSON-LD documents, {len(invalid)} not valid JSON and skipped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
