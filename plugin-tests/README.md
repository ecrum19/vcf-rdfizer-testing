# Plug-in tests

Tests for VCF-RDFizer plug-ins, kept here so each plug-in's code
(in [VCF-RDFizer](https://github.com/ecrum19/VCF-RDFizer)) and its verification
are maintained apart. They run by hand; there is no CI for them.

| Directory | Plug-in | Covers |
| --- | --- | --- |
| `policy/` | `vcf-rdfizer-policy` | The select → partition → decide engine on the example cohort (both sample profiles), its generality (a selector declared in Turtle, a non-VCF graph with a property-path partition, a SKOS purpose vocabulary), and mutation tests that `check` must catch |

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
