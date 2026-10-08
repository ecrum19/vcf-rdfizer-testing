# Experiment 18: converter comparison on a shared input (vcf-bench-1, 2026-10-08)

The reported run of [`benchmarks/18_converter_comparison.sh`](../../../../benchmarks/18_converter_comparison.sh).
The method, the porting rules, and each converter's model are in
[`benchmarks/converters/README.md`](../../../../benchmarks/converters/README.md).

| | |
|---|---|
| Harness | `vcf-rdfizer-testing` commit `e3743590` (`environment/harness-commit.txt`; every harness file's SHA-256 in `environment/harness-files.sha256`) |
| Host | vcf-bench-1: 8 CPUs, 31 GB, Ubuntu 24.04, Docker 29.7.2 (`environment/host.txt`) |
| When | 2026-10-08, 16:58–17:19 UTC |
| Replicates | 3 conversions per converter and input, interleaved by converter; Q1–Q8 compared on replicate 1 |
| Pins | `environment/pins.env`; every downloaded artifact matched its pinned SHA-256 (`environment/artifacts.sha256`), and no converter was unavailable |
| Images | `environment/images.tsv`: image ID and digest of every service; the resolved Compose file is `environment/compose.resolved.yaml` |
| Inputs | `environment/inputs.sha256`: each input's BGZF copy and its decompressed text. Both originals matched `vcf-input-sizes.json` before copying |

## Results

`summary/summary.md`, regenerated from the archived cells by `benchmarks/converters/summarize.py`:

| Converter | Input | Wall (s, median) | Peak RSS (GB) | Triples/record | N-Triples.gz ÷ VCF.gz | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VCF-RDFizer 3.3.1 | HG005 slice | 91.6 | 1.85 | 171.0 | 25.5 | pass | pass | pass | pass | pass | pass | pass | pass |
| | 1000G slice | 31.4 | 0.93 | 536.0 | 136.9 | pass | pass | pass | pass | pass | pass | pass | pass |
| JVarkit | HG005 slice | 2.2 | 0.43 | 14.0 | 2.1 | pass | pass | pass | pass | pass | pass | not in graph | not in graph |
| | 1000G slice | 1.4 | 0.30 | 102.0 | 18.2 | differs | differs | differs | differs | differs | differs | not in graph | not in graph |
| TogoVar | HG005 slice | 1.3 | 0.01 | 57.3 | 15.4 | pass | differs | differs | pass | not in graph | not in graph | not in graph | not in graph |
| | 1000G slice | 0.1 | 0.01 | 56.5 | 35.0 | differs | differs | differs | differs | not in graph | not in graph | not in graph | not in graph |
| SPARQLing Genomics | HG005 slice | 6.3 | 0.01 | 29.6 | 4.8 | pass | pass | pass | pass | pass | pass | pass | differs |
| | 1000G slice | 0.4 | 0.01 | 18.0 | 4.1 | differs | differs | differs | differs | differs | differs | pass | pass |
| BioInterchange | HG005 slice | 1.5 | 0.02 | 45.6 | 17.0 | pass | pass | pass | pass | pass | pass | differs | differs |
| | 1000G slice | 0.4 | 0.01 | 203.1 | 154.3 | pass | pass | pass | pass | pass | pass | pass | pass |

Wall time and peak RSS measure different spans:
- **Other converters:** BusyBox `time -v` around the converter process inside its container.
- **VCF-RDFizer:** its own run summary, which spans all its stages and their container start-ups.

Every "differs" was traced to the converter's graph, not to the port (`compare__*/out/comparison.json` holds the rows):

- **JVarkit, 1000G slice.** Five pairs of lines share CHROM, POS, and REF (for example `20:283049 C>CGAT` and `C>T`, both with ID `.`). JVarkit's record IRI `<urn:variant/CHROM:POS:REF>` merges each pair into one record:
  - 9,995 records instead of 10,000;
  - 5 extra MULTIALLELIC records;
  - every later count shifts accordingly.
- **TogoVar, 1000G slice.** The 13 symbolic-allele records are dropped (alleles outside `[ACGTURYKMSWBDHVN]`). The same 5 pairs merge, because TogoVar writes no record node and the pairs share reference, POS, REF, and ID. Result: 9,982 records.
- **TogoVar, HG005 slice.** `chr1:1663386 C>*,T` loses its `*` allele, so one MULTIALLELIC record reads as an SNV (Q2, Q3).
- **SPARQLing Genomics, 1000G slice.** A call is written only when it carries a non-reference allele:
  - Only the 1,401 of 10,000 records with at least one carrier are in the graph.
  - No hom-ref call is.
  - AN covers carriers only (Q6).
  - Only the first ALT allele is written, so a multiallelic record is recognised only when a written call carries an allele index of 2 or more: 19 of the 70 are (Q2).
- **SPARQLing Genomics, HG005 slice, Q8.** htslib adds a `PASS` FILTER definition the file does not declare: 10 FILTER lines instead of 9.
- **BioInterchange, HG005 slice, Q7 and Q8.** Its header document (line 2 of 100,003) is not valid JSON: the tool writes strings without escaping them. No JSON-LD reader can read that line, so the header is absent from the graph (`jsonld__biointerchange__HG005_GRCh38_r100000/out/graph.nt.invalid.json`). All 100,001 record documents parse.

"Not in graph" questions have their evidence in `benchmarks/converters/queries/<tool>/not_represented.json`.

**Replicates.** Each converter's three outputs are byte-identical except two:
- **VCF-RDFizer:** its gzip framing differs between replicates. Its sorted triples are identical in all three replicates of both inputs (HG005 `661578e7…`, the value of the v3.1.0/v3.3.1 conversion check; 1000G `90571ec6…`).
- **BioInterchange:** 2 of its 100,003 (and 10,003) lines differ, its `Context` and `Summary` documents, which hold run paths and timestamps.

`replicate_content.sh` made this check, and `replicate-content.txt` is its output.

**riot warnings** (`normalise__*/riot-warnings.tsv`). None prevented parsing:

| Converter | Warning | HG005 slice | 1000G slice |
|---|---|---|---|
| VCF-RDFizer | "Unwise IRI": `file://<name>.vcf#record/n` puts the file name where a host would be | 23,616,118 | 7,252,206 |
| SPARQLing Genomics | "Unwise IRI": `origin://<md5>@<k>` uses deprecated user info | 3,057,819 | 189,130 |
| JVarkit | "Bad IRI": `urn:variant/…` has an invalid URN namespace id | 601,008 | 510,177 |
| TogoVar, BioInterchange | none | | |

## Not included

The converted graphs, the N-Triples, and the raw riot warning logs. They are on vcf-bench-1 under
`~/vrdev-test/conv/run-e3743590/`, and the archived commands regenerate them.

## Development passes

Four one-replicate passes (2026-10-08, 16:05–16:58 UTC) found and fixed harness problems before this run. None of them is a result:
- JVarkit's git submodule.
- The Debian snapshot's missing bullseye security pool.
- A Docker 29 template.
- The plain-gzip HG005 slice, which tabix refuses.
- The validator interpreter.
- BusyBox's time format.
- BioInterchange's invalid JSON line.
- Two Q07 ports.
- riot's warning volume.

The commits on `experiment/converter-comparison` record each fix.
