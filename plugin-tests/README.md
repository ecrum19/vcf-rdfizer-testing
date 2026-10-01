# Plug-in tests

Tests for VCF-RDFizer plug-ins, kept here so each plug-in's code
(in [VCF-RDFizer](https://github.com/ecrum19/VCF-RDFizer)) and its verification
are maintained apart. They run by hand; there is no CI for them.

| Directory | Plug-in | Covers |
| --- | --- | --- |
| `policy/` | `vcf-rdfizer-policy` | The select → partition → decide engine on the example cohort (both sample profiles), its generality (a selector declared in Turtle, a non-VCF graph with a property-path partition, a SKOS purpose vocabulary), and mutation tests that `check` must catch. `test_policy_endpoint.py` runs the streaming executor against QLever (inside the image): inline parameters, equality with the in-memory executor, `check_stream`'s mutations, `LinkedSelector` |
| `genes/` | `ensembl-genes-grch38` | Real Ensembl 116 loci around *BRCA1* link exactly to the genes an independent scan of the GFF3 finds, under both contig styles, including a base inside two genes. Needs the cached GFF3; never downloads |
| `spdi/` | the `spdi` linker | Real ClinVar BRCA1 variants of every class against NCBI's own SPDI (recorded, so the suite is offline). Outside repeats the identifier is NCBI's exactly; inside one it is the trimmed form, which must still denote NCBI's allele. Also checks that `17` and `chr17` give the same IRI |

## Running

Each suite needs a VCF-RDFizer source checkout, for the plug-in's package and
its `examples/`, and `rdflib`:

```bash
VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 plugin-tests/policy/test_policy.py
```

Without `VCF_RDFIZER_SRC`, a suite looks for a sibling checkout named
`VCF-RDFizer` or `vcf-rdfizer` beside this repository. That is the same
convention the benchmark harness uses for `VCF_RDFIZER`.

To run a suite against a specific branch, check that branch out in the tool
checkout first. There is no pinning here, by design: the suite tests whatever
the checkout contains.
