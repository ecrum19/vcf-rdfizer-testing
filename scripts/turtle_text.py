"""Cut a Turtle file into its top-level statements, with the standard library only.

The query catalog uses it to show each SHACL shape as written, and the site build
(which has no rdflib in CI) to show each ODRL rule as written.
"""
from __future__ import annotations


def turtle_statements(text: str) -> list[tuple[int, int]]:
    """The 1-based (first, last) line of every top-level Turtle statement.

    A statement ends at a '.' outside strings, IRIs, comments and brackets, so the
    '.' in a SPARQL string, a comment or a decimal does not end one."""
    spans, start, line, depth, i, n = [], None, 1, 0, 0, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif c in "\"'":
            start = start or line
            quote = c * 3 if text.startswith(c * 3, i) else c
            i += len(quote)
            while i < n and not text.startswith(quote, i):
                line += text[i] == "\n"
                i += 2 if text[i] == "\\" else 1
            i += len(quote)
            continue
        elif c == "<":
            start = start or line
            i = text.index(">", i)
        elif not c.isspace():
            start = start or line
            depth += c in "[("
            depth -= c in "])"
            if c == "." and depth == 0 and (i + 1 == n or text[i + 1].isspace()):
                spans.append((start, line))
                start = None
        i += 1
    if start is not None:
        raise SystemExit(f"unterminated Turtle statement starting at line {start}")
    return spans


def statement_text(lines: list[str], first: int, last: int) -> tuple[int, str]:
    """A statement's lines with the comment written directly above it (a banner of ## does not
    belong to it), as (first line, text)."""
    while first > 1 and lines[first - 2].lstrip().startswith("#") and not lines[first - 2].lstrip().startswith("##"):
        first -= 1
    return first, "\n".join(lines[first - 1:last]) + "\n"
