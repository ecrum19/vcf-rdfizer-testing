# Query catalog

Every query the experiments ran, with the code that computes its expected answer without
RDF, and every SHACL shape the validator applies. The results site shows them in the
"Queries and oracles" sections of RQ1–RQ3 and in RQ1's "Preflight checks and SHACL shapes"
section (`#rq1-checks`, which the paper links to).

| File | What it is |
| --- | --- |
| `notes.json` | Written by hand: for each query, a one-line summary, the oracle as pseudo-code, notes, and where the exact query text and oracle code live (a VCF-RDFizer release tag or a commit of this repository, with line ranges) |
| `catalog.json` | Generated from `notes.json` by `scripts/build_query_catalog.py`, which copies in the exact query text and oracle code. The site build reads only this file, because CI has no VCF-RDFizer clone |

Groups:

- **validation**: Q1–Q13, run in every validation run. VCF-RDFizer v3.1.0 for the core benchmark, v3.3.1 for later runs. Q11 and the oracle behind Q9 and Q10 differ between the two releases, and both versions are shown.
- **preflight**: the integrity checks run before the comparisons.
- **shacl-core**, **shacl-consistency**, **shacl-sparql**: the three SHACL profiles. Each names one shapes file
  in `notes.json` rather than listing items; the script turns every node shape in it into an item with its
  exact Turtle text and its constraints in words, and refuses to write if the shapes it cut out do not add up
  to the file's graph. The default (`core`) profile runs whenever shapes are enabled; `full` adds the other
  two. The shapes are identical in v3.1.0 and v3.3.1.
- **usecase**: the linked workflow's carriers and rare-variant queries. The comparator is the conventional workflow.
- **converters**: Q1–Q8 ported to each converter's vocabulary (experiment 18).
- **regional**: R1–R5 and the VCF-side readers (experiment 14).

On the site, each section has a link target (`#rq1-queries`, `#rq1-checks`, `#rq2-queries`,
`#rq3-queries`), and so does each query and shape: the group's research question and the item's id,
lower-cased with hyphens, for example `#rq1-q03-titv` or `#rq1-shacl-core-vcfrecordshape`.

After editing `notes.json`, rebuild with a VCF-RDFizer clone that has the release tags (the script
needs rdflib):

```bash
python3 scripts/build_query_catalog.py --tool-repo ../VCF-RDFizer
```

The script refuses to write if a cited file, tag or line range does not exist.
