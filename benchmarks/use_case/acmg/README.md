# Use case: ACMG secondary findings across participant VCFs and ClinVar

> *Which participants carry a ClinVar-classified variant in an ACMG SF v3.2
> gene, and what may each requester see?*

This is workstream A of the JBMS revision plan
([`tool-docs/jbms-revision-plan.md`](../../../tool-docs/jbms-revision-plan.md)).
It is the paper's demonstration that VCF-RDFizer is *useful*, not just correct.
The question is clinically recognisable, it needs data from outside the VCFs,
it spans several files, and it has a consent dimension: secondary findings are
exactly what consent codes govern.

The question asks for ClinVar's *classification* rather than only its
pathogenic variants, because the claim under test is that variant identity,
external annotation and consent can be made declarative and checkable — not
that five individuals' VCFs contain a clinical finding. They do not, and the run
says so (see **Reportable** below).

It runs through [`../../17_use_case_acmg.sh`](../../17_use_case_acmg.sh), a
standalone investigation outside `run_all.sh`.

## Two routes, one answer

Both routes read the same derived inputs and the same definitions
([`use_case.json`](use_case.json)), and neither reads the other's work.

| | RDF route | Baseline route |
| --- | --- | --- |
| Variant identity | The `spdi` linker gives each normalised record a global SPDI IRI (`vcfl:sameVariantAs`). Participant VCFs and ClinVar share it whatever their contig names | Rename contigs to ClinVar's, then `bcftools annotate --pair-logic exact` |
| Clinical meaning | ClinVar converted with structured INFO, so `CLNSIG`, `CLNREVSTAT` and `GENEINFO` are queryable values | `bcftools annotate -c INFO/CLNSIG,...` |
| Consent | ODRL in [`policy.ttl`](policy.ttl), applied by `vcf-rdfizer-policy`, one checked release view per requester | [`baseline_carriers.py`](baseline_carriers.py), a hand-written consent table |
| The question | One SPARQL query, [`carriers.rq`](carriers.rq), per requester, under QLever | `bcftools view` + `query`, then the script |

**The experiment passes only if both routes give identical carrier lists for
every requester** (`compare.py`). Timings and step counts are reported beside
that, never instead of it. Where the baseline is shorter, the paper says so.
The RDF route's claim is that identity, meaning and consent become explicit,
declarative and checkable, not that it is always less code.

## Inputs

| Participant | Source | Contigs | rsIDs |
| --- | --- | --- | --- |
| NB72462M | PGP huF7A4DE (Nebula Genomics, GATK) | `chr1` | yes |
| NG131FQA1I | PGP huFFFE77 (Dante Labs, GATK) | `chr1` | yes |
| HG002 | GIAB HG002, precisionFDA Truth Challenge v2 submission 0GOOR (CLC) | `1` | no |
| HG004 | GIAB HG004 v4.2.1 benchmark | `chr1` | no |
| HG005 | GIAB HG005 v4.2.1 benchmark | `chr1` | no |
| ClinVar | 2026-09-13 weekly archive (GRCh38, public domain) | `1` | — |

- **Genes:** the 81 ACMG SF v3.2 genes ([`acmg_sf_v3.2.genes.txt`](acmg_sf_v3.2.genes.txt)),
  from the table NCBI publishes. The regions are each gene's full span from
  Ensembl release 116, 7.1 Mb in total, pinned once by
  [`make_regions.py`](make_regions.py) into
  [`acmg_sf_v3.2.GRCh38.bed`](acmg_sf_v3.2.GRCh38.bed) and
  [`regions.json`](regions.json). GLA and OTC are on chrX, which the GIAB
  benchmark files do not cover.
- **Reference:** `GCA_000001405.15_GRCh38_no_alt_analysis_set`, the reference
  the GIAB files declare.
- **Derivation** ([`derive.sh`](derive.sh), inside the image) does three things:
  - restricts each file to the gene spans;
  - splits multi-allelic records;
  - left-aligns against the reference and drops records whose REF disagrees
    with it (counted in `<id>.derive.json`).

  Contig names stay as the source wrote them, because reconciling them is part
  of the problem. `##reference` is set to the reference actually used, since the
  sources declare a lab path or nothing.

### Arm 2: a 1000 Genomes cohort

`make_cohort.py` selects 104 unrelated participants from the 1000 Genomes
high-coverage call set, 4 from each of its 26 populations, with the seed in
`use_case.json`. It draws their simulated consents from the stated mix. The
result, `cohort/cohort.json`, is a complete case file, committed; `generate.py`
writes its `cohort/policy.ttl`.

`BM_ACMG_ARM=cohort` runs every stage on it, starting with `fetch_cohort`,
which reads only the ACMG regions of the panel, remotely by tabix, one
chromosome at a time.

The panel's ~90 INFO fields describe all 3,202 of its samples, not the
participant, so each participant's file drops INFO (`derive.sh drop-info`).
Kept, they were 93% of every participant's triples (92.6–92.7% measured across all 104). The frequencies the
question can use are recorded once instead: `panel.acmg.vcf`, a sites-only file
of the sites any participant carries, with the fields `cohort.json` names under
`panel`. It is linked by SPDI like ClinVar, so `cohort/rare.rq` (the carriers
whose variant has panel `AF` < 0.01) joins three files by one identifier. The
baseline looks the same frequency up by CHROM, POS, REF and ALT, and `compare`
gates both lists.

```bash
BM_ACMG_ARM=cohort BM_ACMG_STAGES="fetch_cohort derive convert link baseline govern query compare" \
  BM_IMAGE_VERSION=3.2.0 ./17_use_case_acmg.sh
```

### Arm 3: one complete VCF

`make_wgs.py` writes `wgs/case.json`: arm 1's question, participant (HG005)
and consent, unchanged. `BM_ACMG_ARM=wgs` runs the same stages, except that
`derive.sh` keeps every record of HG005's VCF (`all` in place of the regions); ClinVar
stays restricted. Only the scale changes, so HG005's carriers must equal its
arm-1 carriers. HG005 consents to clinical care only, so two of the three
views are empty: their evaluation still streams the whole graph, and their
check needs no view endpoint.

Each large stage first checks the disk it will need (`need_space`: about 20
GB for convert, 55 for govern, 35 for query) and stops instead of filling it.

```bash
BM_ACMG_ARM=wgs BM_ACMG_STAGES="derive convert link baseline govern query compare" \
  BM_IMAGE_VERSION=3.2.0 ./17_use_case_acmg.sh
```

### Arm 4: one complete VCF, layered consent, four requesters

Arms 1–3 govern whole files, so arm 3's complete HG005 VCF was all or nothing. Arm 4
asks the same question of the complete NB72462M VCF under rules that each target
a different kind of selection. [`make_layered.py`](make_layered.py) writes
`layered/case.json`; `generate.py` writes its policy and `purposes.ttl`.

| Rule | Target | Withheld from |
| --- | --- | --- |
| Consent: clinical care and general research | the file | nobody |
| Cancer-predisposition genes (28) | gene links (`LinkedSelector`) | research |
| Disease-specific research sees only the 40 cardiovascular genes | the panel's complement, a selector declared in the policy | the cardiovascular consortium |
| APOE (chr19:44,903,787–44,909,396, Ensembl 116) | `RegionSelector` | everyone but the participant's own physician |
| DSP chr6:7,569,314 C>G (uncertain significance) | its SPDI identity | the biobank, by name |

The four requesters are the participant's own physician, the clinical lab, the
cardiovascular consortium and the biobank. Each receives a different,
non-empty part of the VCF's records.

"Only the participant's own physician" is a purpose, declared in
`purposes.ttl` as narrower than clinical care, not a named assignee. ODRL has
no "everyone except", so a rule written per assignee would release APOE to any
clinical requester it did not list. A purpose-based prohibition fails closed.

The region rule binds the contig as the file writes it (`chr19`), as the
shipped `RegionSelector` does. A file that wrote `19` would escape it. The
variant rule targets the SPDI identity, so it has no such gap.

Besides the carriers, `compare` checks each view record for record: the
baseline counts what every requester may see over all of the VCF's records
(`baseline/records.tsv`), and each count must equal the records the view
released.

```bash
BM_ACMG_ARM=layered BM_ACMG_STAGES="derive convert link govern query baseline compare" \
  BM_IMAGE_VERSION=3.3.0 ./17_use_case_acmg.sh
```

### Effort

`effort.py` measures what each route asks its author to write (arm 1: rules and
data, apart), then applies four changes to both routes as real edits: a
withdrawal, a requester with a new purpose, a cardiac panel in place of the
cancer one, and a rule on one variant. It counts the lines each changes, and
checks that both edited routes still release the same records to every
requester on a fixture. The result is committed as `effort.json`.

```bash
VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 effort.py out/
```

## Definitions

These are in `use_case.json`, and both routes implement them:

- **Classification:** the first term of `CLNSIG`, reported rather than filtered
  on. `Pathogenic|risk_factor` classifies as `Pathogenic`;
  `Conflicting_classifications_of_pathogenicity` as itself.
- **Reportable:** the subset classified `Pathogenic`, `Likely_pathogenic` or
  `Pathogenic/Likely_pathogenic` — counted in `summary.json`, never used as a
  filter. **In this cohort it is empty**, and that is a result rather than a
  gap: five unselected individuals, against a roughly 1–3% per-person rate of
  reportable ACMG secondary findings. It was checked against the alternative
  explanation: where a participant's VCF does meet a pathogenic ClinVar record's position,
  the alleles genuinely differ (an SNV against a 23-base insertion, a deletion
  against an SNV), so this is biology and not a representation mismatch.
- **Review status:** not `no_assertion_criteria_provided` or an unclassified
  status (at least one star).
- **Gene:** a `GENEINFO` symbol that is in the ACMG list.
- **Carrier:** the GT has a non-zero allele, and FILTER is `PASS` or missing.

## The policy: simulated consents on real VCFs

The consents are **simulated**, and every output says so. Nobody consented to
anything here.

| Participant | Consent |
| --- | --- |
| NB72462M | general research (GRU) and clinical care (CC) |
| NG131FQA1I | health/medical research (HMB) |
| HG002 | general research |
| HG004 | general research, then withdrew |
| HG005 | clinical care only |

**Cohort rule:** variants in the 28 cancer-predisposition genes are released
only for clinical care. The target is a selector type declared in the policy
file (`ex:InGeneSpans`), not shipped with the plug-in. That shows the plug-in's
declared selectors working on real data.

The requesters are a clinical genetics lab (CC), a cardiovascular consortium
(disease-specific research, DS) and a biobank researcher (GRU).
[`generate.py`](generate.py) writes `policy.ttl` and `carriers.rq` from
`use_case.json`; don't edit either by hand.

## Running it

```bash
BM_ACMG_STAGES=fetch ./17_use_case_acmg.sh      # ClinVar + reference, ~1.1 GB, once per host
BM_IMAGE_VERSION=3.2.0 ./17_use_case_acmg.sh    # derive … compare
```

Every stage skips a cell it already has, so re-running the same command
resumes an interrupted run. To redo one cell, move it aside — keeping a failed
cell is usually worth more than deleting it — or point `BM_RESULTS` elsewhere.

**The link stage needs the `spdi` linker**, which is not in v3.2.0. It is on
VCF-RDFizer's `feature/spdi-linker` branch, planned for v3.3.0. The link and
govern stages run host-side, from the tool checkout that `VCF_RDFIZER` points
at, so that checkout must have the linker. Until it does, the link stage
records a skip, and govern, query and compare skip after it. derive, convert
and baseline need only the v3.2.0 image.

### The live tier: MyVariant.info

On arm 1, `link_myvariant` runs the tier-3 `rsid-myvariant` linker on the two
PGP files, whose ID columns carry rsIDs, and
[`compare_myvariant.py`](compare_myvariant.py) sets its links against those of
`rsid-dbsnp`, which rewrites every rsID without checking it. The stage does not
query the service by default. The linker replays recorded responses with
`--offline` from `BM_MYVARIANT_CACHE` (default: `myvariant-cache/` beside this
file, laid out as the linker's `--links-cache`), and a request the recording
cannot answer stops the cell. The linker keys each response by its request,
which depends only on the file's rsIDs, so a recording made from the same
derived VCFs answers every request.

The paper's recording is the 21 responses MyVariant.info returned on
2026-09-28: one POST per batch of up to 1,000 rsIDs, 10 for NB72462M and 11 for
NG131FQA1I. Each cell's `*.links.json` lists every response's SHA-256. To query
the service instead:

```bash
BM_ALLOW_NETWORK=1 BM_CONTACT_EMAIL=you@your-institution.org BM_ACMG_STAGES=link_myvariant ./17_use_case_acmg.sh
```

The linker then sends at most one request a second and 30 per file, names the
address in its User-Agent, and keeps the responses in the cell's `out/cache/`,
a recording for the next run. Its counts can differ from the paper's as
MyVariant.info's data changes.

### Outputs

Everything is written under `benchmarks/results/17_use_case_acmg/`:

| Path | Contents |
| --- | --- |
| `inputs.json` | Size and SHA-256 of every downloaded input |
| `derive__<id>/`, `convert__<id>/`, `link__<id>/` | One `bench.json` per cell (wall time, command, image digest) |
| `govern__<requester>/` | The requester's streamed view (`out/view.nt.gz`), decisions, manifest, and `check.txt`. Evaluated and checked on QLever endpoints (the participant VCFs' graphs with their links; the VCF-text oracle), never in memory |
| `query/<requester>/` | `carriers.tsv`, `timing.json` (engine setup, then per-replicate query time) |
| `baseline/` | `carriers.<requester>.tsv`, `summary.json` (per requester, the classification spread, and the reportable subset) |
| `comparison.json`, `grid.tsv` | Agreement per requester, and carriers per requester and participant |
| `link_myvariant__<id>/` | Arm 1's tier-3 links (`out/<id>.myvariant.links.nt`) and the linker's report: requests, cache hits, and every response's SHA-256 |
| `tier1_vs_tier3_myvariant.json` | Per PGP file: tier-1 and tier-3 link counts, and the tier-1 links and rsIDs the service did not confirm |

## Tests

```bash
VCF_RDFIZER_SRC=/path/to/VCF-RDFizer python3 test_use_case.py
```

The central test runs `policy.ttl` through the plug-in and
`baseline_carriers.py` over every requester and participant, and requires the
same releases. The two consent implementations are independent, so this is
the test that catches one of them misreading `use_case.json`. The other tests
cover the baseline's rules, the query's filters over synthetic graphs, and the
comparison keys.

The `Derive` and `Baseline` tests need bcftools and skip without it. To run them
inside the image:

```bash
docker run --rm --entrypoint "" -v "$PWD:/case" ecrum19/vcf-rdfizer:3.2.0 \
  sh -c 'cd /tmp && /opt/pycottas-venv/bin/python /case/test_use_case.py Derive Baseline'
```
