# Workstream A: implementation plan for the real-data use case

*2026-09-28. This replaces the outline of workstream A in
[`jbms-revision-plan.md`](jbms-revision-plan.md) §3 with an implementation
strategy. It takes into account what the first real run showed (§3.1). Review
references (M1–M8, m1–m11, claims-table rows 1–12, §5) point to
[`jbms-review-vcf-rdfizer.md`](jbms-review-vcf-rdfizer.md).*

## Progress

**Decisions (2026-09-28):**
- the full plan, with three arms;
- the downloads are approved;
- the Ensembl contact is elias.crum@ugent.be;
- N is chosen from phase-1 costs.

Everything is tested on vcf-bench-1 or vcf-bench-2.

| Phase | Status |
| --- | --- |
| 1. Arm 1, identity and query | **Done 2026-09-28: AGREE, 7,211/7,211** |
| 2. Generalize, then govern arm 1 | **Done 2026-09-28: AGREE for all four requesters** |
| 3. Arm 2, cohort | **Done 2026-09-28: AGREE for all four requesters (N = 104)** |
| 4. Arm 3, whole genome | **Done 2026-09-30: AGREE; equals HG005's arm-1 answer (1,496/1,496)** |
| 5. Release | **Prepared 2026-09-30**: `release/v3.3.0` (`5d3adb1`), not pushed; arm 1–2 rerun not done |
| 6. Measure and write | **Done 2026-09-30**: effort, change scenarios, figure, Results subsection (on `feature/acmg-use-case`) |

**Log:**
- **2026-09-26: arm 1 derived and baseline run** (v3.2.0 image, bench-1).
  - 5 genomes and ClinVar (331,453 records) derived, with 0 REF mismatches.
  - Baseline: 7,211 carriers, 0 reportable.
  - Fixed two bugs: ClinVar has no `##contig` lines, and a SIGPIPE inverted the
    contig-style test.
- **2026-09-28: QLever probe.** Trailing `VALUES` fails open, so parameters go
  inline (§4.1).
- **2026-09-28: phase 1 code.**
  - The cancer rule is record-based (REF extent overlaps a span) in both
    routes, and contig-style-proof.
  - `run_query.py` streams each input into QLever as its own named graph, with
    no concatenated copy.
  - The link stage reads the VCF.
  - `compare.py` reports requesters not yet run instead of counting them as
    agreeing.
  - Tests on bench-1: use case 22/22 in the v3.2.0 image, including QLever
    parity; tool 950 passed, 25 skipped; spdi plug-in 4/4.
- **2026-09-28: QLever planner pathology.** `carriers.rq`, written as one group
  of about 20 patterns, stalled on a 26-triple graph.
  - Cause: QLever's exhaustive planner grows exponentially with the patterns in
    a group (0.1 s → 1.7 s → 24.5 s as the three `hasInfoValue` branches are
    added, all returning 0 rows). Above its threshold, the greedy planner picks
    a cross product instead.
  - Fix: two subqueries (genome calls; ClinVar annotations) joined on the SPDI
    IRI, with the gene list applied after the join.
  - Applies to any query the tool ships for QLever, including P2's selectors.
- **2026-09-28: phase 1 result** (bench-1; v3.2.0 image; linker tree base
  `f266db5`, diff `3096da348db31ac8`).
  - **The RDF route equals the bcftools baseline: 7,211/7,211 unrestricted
    carriers.**
  - Costs:
    - convert: 18–21 s per genome, 98 s for ClinVar;
    - link: about 1 s per genome, 25 s for ClinVar;
    - baseline: 5 s.
  - Links:
    - `spdi`: coverage 1.0 on every file (331,413 for ClinVar);
    - `rsid-dbsnp`: 9,951 on NB72462M and 10,316 on NG131FQA1I.
  - Query: 42.5M triples, of which ClinVar is 33.1M. QLever setup 136 s; query
    174.7 s, 172.3 s and 1.5 s.
- **Open from phase 1:**
  - The third replicate came from QLever's result cache, so replicates need a
    cache clear between them (or cold and warm reported apart) before any
    timing is quoted.
  - The ClinVar subquery (the whole 331k-record table) dominates query time.
    Try restricting it to linked variants without re-coupling the planner.
  - N is provisionally 100: conversion about 35 min, linking under 2 min.
    Confirmed after phase 2 measures governance.
- **2026-09-28: phase 2 code.**
  - L1: `vcfl:contigAliases` on interval joins.
  - L2: the `ensembl-genes-grch38` linker. The Ensembl 116 GFF3 is 108 MB,
    SHA-256 `08e881d9…`; downloaded once on bench-1 and cached by digest.
  - P1: parameters become inline `VALUES`, for rdflib and endpoints alike.
  - P2: the shipped `LinkedSelector`, failing closed without links.
  - P3: `--endpoint` streaming for `evaluate` and `check`, plus an `oracle`
    command, with memory bounded by SQLite.
  - The generality guard.
  - `generate.py` states the cancer panel as 28 Ensembl IRIs, not SPARQL.
  - `run_query.py` clears QLever's cache before every replicate.
  - The existing function signatures are kept, so rdflib graphs still work.
- **Tests on bench-1:**
  - tool: 956 passed, 25 skipped;
  - policy: 32/32 in memory, 9/9 on QLever. On QLever the streaming executor
    equals the in-memory one for every requester and both sample profiles, and
    catches the mutations;
  - spdi 4/4;
  - genes 2/2, against an independent GFF3 scan;
  - use case 22/22.
- **Findings:**
  - rdflib misevaluates `OPTIONAL` with `!BOUND` when `VALUES` binds the
    predicate and returns no row, so the fail-closed guard would fail open on
    rdflib. It uses `FILTER NOT EXISTS`, which is correct on both engines.
  - NBR2 is `ncRNA_gene` in Ensembl, and BRCA1's first base also lies in a
    second protein-coding gene (ENSG00000108830). So the gene tests take their
    expectations from the GFF3, not from assumptions.
  - Ensembl 116's GFF3 BRCA1 span equals `regions.json`'s: 17:43,044,292–43,170,245.
- **2026-09-28: first arm-1 governance run.**
  - The clinical view was right: HG005 and NB72462M, 19,625 records.
  - Its check refused with exit 2, because `LinkedSelector`'s fail-closed guard
    found no gene links in the oracle graph. That is the guard working.
  - Fix: serve the genome link graphs beside the oracle. The linker computed
    them from the VCF text, so the oracle stays independent of the conversion.
  - `check.txt` now captures stderr.
- **2026-09-28: phase 2 result** (bench-1; linker tree diff `537d198359fca5db`).
  - **The routes agree for every requester:** unrestricted 7,211/7,211,
    clinical 2,878/2,878, cardio 2,988/2,988, biobank 1,987/1,987.
  - Every view is checked on QLever (structural checks, plus the oracle with
    its links) and passes.
  - Govern, streamed on QLever for all five genomes: 32 s (clinical), 39 s
    (cardio), 35 s (biobank). No rdflib touches the data.
  - Gene links per genome: 10,350–12,800.
  - Query: setup about 130 s; each replicate starts cold and takes 172–181 s,
    now consistent.
  - Tests after the final change: tool 956 passed, 25 skipped; policy 32/32
    in memory, 9/9 on QLever; use case 22/22.
- **N = 100 confirmed.**
  - Per genome: governance about 7 s per requester, conversion about 20 s.
  - Arm 2 should take a few hours unattended.
- **Still open:** the ClinVar subquery (about 170 s) dominates query time.
- **2026-09-28: phase 3 started.**
  - Cohort (`make_cohort.py`, seed 20260928): 104 unrelated participants, 4
    from each of 26 populations.
  - Simulated consents: health/medical 33, general 23, general + clinical 20,
    clinical 18, disease-specific 6; 4 withdrawn.
  - Metadata: PED 97 KB, unrelated index 982 KB; digests in `cohort.json`.
  - `fetch_cohort.sh` reads the panel's ACMG regions by remote tabix, one
    chromosome at a time.
  - The harness takes `BM_ACMG_ARM=cohort`, which gives arm 2 its own case,
    policy, results and derived inputs. `generate.py` takes a case file.
  - Tests: use case 27/27 in the image, adding the cohort selection and a
    local-panel fetch.
- **2026-09-28: fetch.**
  - 19 chromosomes read by remote tabix. chrX's panel file is named `.v2`,
    handled by `panel_overrides` and tested.
- **2026-09-28: tier 3 live (`rsid-ensembl`) on the PGP genomes.**
  - Run with elias.crum@ugent.be as contact, at 2 requests/s, cached.
  - First run: a 30 s read timeout on one batch.
  - Tool: `vcfl:requestTimeout` (1–600 s, default 30), tested. The run copy
    uses 120 s and a budget of 110.
  - Next runs: Ensembl returns HTTP 500 for one batch of NB72462M after the
    framework's three backed-off retries. It fails closed, publishing no
    partial linkset.
  - Stopped there to spare the service. Everything received so far is cached,
    and NG131FQA1I has not run yet.
- **2026-09-28: tier 3 on MyVariant.info (`rsid-myvariant`, new).**
  - A shipped manifest and a 30-line resolver: batches of 1,000 rsIDs, 1
    request/s. An rsID is linked to its dbSNP IRI only when a returned dbSNP
    record carries it. 2 unit tests; on bench-1, linking suites 61/61 and
    the full tool suite 959 passed, 25 skipped.
  - The framework (session, cache, budgets, fail-closed) is unchanged.
  - Tool tree `vcf-rdfizer-myvariant` (`tool_source_myvariant.txt`); cells
    `link_myvariant__<genome>`.

  | Genome | Unique rsIDs | Requests (all HTTP 200) | Wall | Bytes | Calls confirmed / tier-1 links |
  | --- | --- | --- | --- | --- | --- |
  | NB72462M | 9,772 | 10 | 58 s | 2.7 MB | 9,223 / 9,951 |
  | NG131FQA1I | 10,111 | 11 | 42 s | 2.9 MB | 9,479 / 10,316 |

  - Tier 3 is a strict subset of tier 1. The unconfirmed 641 and 717 rsIDs:
    a sample of 3, looked up on NCBI's RefSNP API, are all merged into other
    rsIDs. Tier 1 rewrites stale identifiers without noticing
    (`tier1_vs_tier3_myvariant.json`).
- **2026-09-28: arm 2, first run failed in govern.**
  - The source endpoint's QLever index filled bench-1's disk (14 GB free)
    after 910M triples. The cause: each participant file kept the 1000 Genomes
    panel's ~70 INFO fields (frequencies over all 3,202 samples). That gives
    ~800 triples per record, ~8.2M per participant, ~95% of it INFO.
  - Fix: `derive.sh drop-info`, for arm 2 only. That INFO is the panel's, not
    the participant's. Tested (28/28). The harness's `serve` now keeps the
    dying endpoint's log.
  - Rerun from derive. The failed run is kept as
    `17_use_case_acmg__cohort__failed_panel_info_disk` and
    `derived_cohort__panel_info`.
- **2026-09-28: phase 3 done. AGREE:** unrestricted 173,102/173,102;
  clinical 63,529; cardio 92,870; biobank 48,207 (each equal to the baseline).
  - Genomes: 1.15M records, 70.3M triples. With ClinVar and the links, 103.7M
    triples in the unrestricted index.
  - Stage totals on bench-1 (sums of cells): derive 21 min, convert 31, link 22,
    baseline 1.2.
  - Endpoints: the source index took ~90 s, the oracle ~35 s.

  | Requester | Records released / withheld | Evaluate | Check | View (gz) |
  | --- | --- | --- | --- | --- |
  | clinical | 421,991 / 728,297 | 23 min | 9 min, PASS | 194 MB |
  | cardio | 685,928 / 464,360 | 26 min | 22 min, PASS | 315 MB |
  | biobank | 356,835 / 793,453 | 21 min | 9 min, PASS | 164 MB |

  - Query (QLever, 3 cold replicates): setup 142–185 s, replicates 182–206 s.
    The unrestricted query covers 103.7M triples, so query time barely grows
    from arm 1's ~6M (172–181 s). The ClinVar subquery dominates (open item).
  - **Bottleneck:** governance is Python-bound. `stream_view` and `check_stream`
    run at 100% CPU with QLever idle: ~20× the triples cost ~40× arm 1's time.
    Fix before arm 3 (a whole genome is 4–5× this cohort).
- **2026-09-28: faster streaming, and the panel's frequencies recorded once.**
  - Tool (tree `vcf-rdfizer-stream`, `tool_source_stream.txt`):
    - `Evaluation.released` checks two merged sets per ancestor. It no longer
      scans all 109 rules, walking each IRI one character at a time.
    - `stream_view` filters the inputs in parallel (forked workers, one gzip
      member each).
    - `check_stream` uses the same merged sets, skips repeated subjects, and
      batches its SQLite inserts.
    - `view` keeps the per-rule `decide`, so the equivalence tests still
      compare two independent implementations.
  - Tests on bench-1: tool 964 passed, 25 skipped (+5); policy 32/32 in memory
    and 9/9 on QLever; use case 33/33 (+5).
  - Same views, byte for byte (MD5 of each decompressed `view.nt.gz`):

    | Requester | Evaluate, before → after | Check, before → after |
    | --- | --- | --- |
    | clinical | 1,367 → 131 s | 520 → 217 s |
    | cardio | 1,618 → 165 s | 1,307 → 338 s |
    | biobank | 1,231 → 134 s | 528 → 220 s |

    All three requesters now govern in ~20 min, down from ~110. The check is
    single-process and is now the larger share.
  - Panel file (`cohort.json` → `panel`):
    - 68,635 sites carried by the cohort, with `AF` and the 5 population AFs;
      `AC` and `AN` dropped as cohort recounts.
    - 6.5M triples, 35 MB gzip. That replaces the ~850M triples of panel INFO
      spread over the participants.
    - Costs: derive 86 s, convert 32 s, link 5 s.
  - `cohort/rare.rq` gives the carriers whose variant has panel AF < 0.01: three
    files joined by one SPDI IRI. The baseline looks the same frequency up by
    CHROM, POS, REF and ALT, and `compare` gates both lists.
  - **AGREE**:
    - carriers: unchanged, 173,102 / 63,529 / 92,870 / 48,207;
    - rare: unrestricted 4,154, clinical 1,621, cardio 2,198, biobank 1,144.
  - Query timings (index of 62–110M triples, 3 cold replicates each):
    - setup 144–196 s;
    - carriers 176–202 s;
    - rare 169–174 s.
  - The first pass is kept as `*__before_panel_stream`.
- **2026-09-29: SQLite out of the RDF paths (tree `vcf-rdfizer-semantic`).**
  - Profile of one clinical check (cProfile, ~2.8× slowdown): the oracle's
    per-rule `decide` took ~48%, the view stream ~40%, SQLite ~4%. bench-1
    scales 5.3× on 8 vCPUs; no throttling.
  - Linking from RDF reads the graph with SPARQL through any store:
    `vcf-rdfizer-link run --endpoint`, or a file loaded into a temporary
    on-disk Oxigraph store holding only the join fields. The reader's
    assumptions are declared queries. pyoxigraph (≥ 0.3.18) is now a
    dependency; it is on PyPI and conda-forge.
  - `check --endpoint` needs `--view-endpoint`. The check counts the served
    triples against the view's lines, then asks for dangling references with
    one `FILTER NOT EXISTS`. The harness serves each view on :7203.
  - `decide` stays per-rule but finds ancestors once per term.
  - The runner's join scratch stays in SQLite: it is a dedup buffer, not data.
  - Arm 2 govern rerun: every check PASS, and every view identical by MD5.

    | Requester | Evaluate | Check (incl. ~30–55 s view index) |
    | --- | --- | --- |
    | clinical | 131 → 59 s | 217 → 174 s |
    | cardio | 165 → 80 s | 338 → 296 s |
    | biobank | 134 → 72 s | 220 → 182 s |

  - `read_tsv` removed (no caller; dead code).
  - Linking unit tests: 102 (+40 in `test_linking_edges_unit.py`, one per
    refusal and edge path). Line+branch coverage of the linking code, resolvers
    included, rose from 86% to 99%. Left uncovered: the pyoxigraph < 0.4
    branch (run by the image's 0.3.18 suite, 49/49), one defensive `except`,
    and `__main__`. Tool suite 1,006 passed, 25 skipped.
- **2026-09-29: phase 4 (arm 3) started on bench-2.**
  - Space:
    - Docker build cache pruned (23.6 GB; no images removed).
    - 3.2.0 pulled; digest `b7793bde…` checked.
    - ClinVar, the reference and the GFF3 fetched into `~/vrdev-test`. Their
      SHA-256 digests equal bench-1's.
    - 83 GB free.
  - Design: arms 1–2's pipeline, not the 3.1.0 HDT.
    - `derive.sh all` normalises the whole genome: 3,856,856 → 3,887,810
      records (30,954 split, 18,624 realigned, ~1.3%). The raw HDT would have
      given those records other SPDI IRIs.
    - `wgs/case.json` is HG005 with its arm-1 consent (clinical care only), so
      the cardio and biobank views are empty. `check` needs no view endpoint
      for an empty view.
  - First conversion failed: disk full, after ~35 min.
    - `--rdf-storage-mode plain` writes the whole graph uncompressed before
      gzipping it; `HG005.acmg.nt` reached 43.9 GB.
    - The govern guard then stopped the run correctly (55 GB needed, 39 free).
    - The partial `.nt` was deleted; the cell's logs are kept as
      `convert__HG005__failed_plain_disk`.
    - The harness now converts `space-optimized` (same triples, no uncompressed
      copy). Resumed with tool `578c2be` and harness `ae2c9c57`.
  - Second pass, to the end of govern:

    | Stage | Time | Result |
    | --- | --- | --- |
    | convert | 53 min | 2.8 GB gzip |
    | link | 7.5 min | 5.70M links (SPDI for 3,887,200 calls, genes for 1,704,921) |
    | oracle | — | 35.0M triples |
    | source index | 44 min | ~670M triples |
    | clinical | 38 min evaluate, check PASS | all 3,887,810 records, 668,061,347 triples |
    | cardio, biobank | 28 min each, check PASS | empty views |

    - Peak memory 12.9 GB.
    - One genome evaluates on two workers (one per input file). Splitting a
      large file by byte range would restore the parallelism.
  - Query stage, first attempt:
    - run_query's per-graph `GROUP BY ?g` count exceeded QLever's memory budget
      at ~670M triples. The empty reply was read as JSON.
    - Fixed (`bc7a7ca8`): each input's lines are counted as it streams in, the
      index total uses a plain `COUNT(*)`, and every engine status is checked.
      The cells are kept as `*__failed_count_groupby`.
    - The resume then rebuilt governance's endpoints for no requester (stopped).
      Fixed (`b863b439`): govern skips its endpoints when every requester is done.
- **2026-09-30: phase 4 done.**
  - AGREE: unrestricted 1,496/1,496; clinical 1,496; cardio 0; biobank 0.
  - HG005's whole-genome carriers equal its arm-1 carriers key for key (1,496;
    none only in either). The ~400× larger input changed nothing.
  - Query:
    - unrestricted and clinical indexes: 701M triples, setup ~45 min;
    - carriers replicates 205–209 s, against ~180 s in arm 1 (the ClinVar
      subquery still dominates);
    - cardio and biobank (ClinVar only): 133 s setup.
  - Totals: 14 cells, 4.6 h of cell wall time; results 11 GB.
  - Peaks since the storage fix: 13.1 GB RAM, and 34 GB of disk (49 GB still
    free).
  - Provenance: tool `578c2be`, then harness `68f546b0` → `ae2c9c57` →
    `bc7a7ca8` → `b863b439` (each resume appended to `harness_source.txt`).
- **2026-09-30: phase 5 prepared (release, without the arm 1–2 rerun).**
  - `release/v3.3.0` off `feature/spdi-linker`: `scripts/release.py 3.3.0`
    run; the policy plug-in is 0.2.0, with its roadmap renumbered (v0.2 is the
    endpoint executor).
  - On bench-2: tool suite 1,007 passed; `--check-tag v3.3.0` passes.
  - The conda sha256 stays a placeholder until the tag exists.
  - Push, PR, tag and feedstock are yours.
- **2026-09-30: phase 6 done.**
  - `effort.py` (bench-2, v3.3.0 tree), committed with `effort.json`:
    - authored rules: RDF 72 lines (policy 41, query 31), baseline 131;
    - withdrawal, new purpose (POA) and cardiac panel are data edits of
      similar size in both routes;
    - the HFE C282Y rule costs 3 lines of code in the baseline and none in the
      RDF route;
    - every scenario is verified on a fixture (15–20 cells, 3 distinct
      outcomes).
  - Paper (`BioMedSem_2026/paper`):
    - a Results subsection replaces §3.7 and the policy demonstrator, with
      `fig-usecase` and tables for linking, answers, cost and effort;
    - the abstract, capability table, Discussion, §4.3 and availability
      statements are updated;
    - 5 references added;
    - builds with no undefined references.
  - Branches rebased onto origin/main (`ed489248`). The rebased harness commits
    are content-identical to the ones arm 3 recorded:
    - `68f546b0` → `0d7b318e`
    - `ae2c9c57` → `53973b5c`
    - `bc7a7ca8` → `e2ceea67`
    - `b863b439` → `6380bcb4`

- **2026-10-01: review text fixes, PRs, and the M8 restructure.**
  - Text-level review fixes committed on `feature/acmg-use-case` (`1b4b62f6`).
  - PRs opened:
    - VCF-RDFizer#30, release v3.3.0, rebased onto #29, with #29's options
      documented;
    - vcf-rdfizer-testing#7, the spdi/genes/endpoint plug-in tests;
    - #8, the use case and the paper;
    - #9 (draft, stacked on #8), the M8 restructure.
  - #30's coverage job found a real bug: pyoxigraph's `bulk_extend` rejects an
    empty batch on Linux. A fix is in progress, uncommitted, in the
    `vcf-rdfizer-wt-spdi` worktree, and was not written in this session.
  - M8 (`b4976288`):
    - contributions list;
    - re-sectioned as Implementation / Evaluation design / Results / Discussion;
    - `supplementary.tex` (S1–S5);
    - interpretive Discussion and a new abstract.

    The body falls from about 39 pages to 23.
  - Waiting on SLICES (502): the C2 core-profile mutation score and the C3
    NG131FQA1I paired QLever validation.
- **2026-10-01 (later): the two review runs**, on bench-2, v3.1.0 (`d3b34d5`),
  under `~/vrdev-test/review-runs`.
  - **C2 is done.**
    - Queries only: 96/113, reproducing the archive.
    - Default (`core`) profile: also 96/113. Its shapes detect none of the 17
      mutations the queries miss; only the full set catches them.
    - Paper updated (`0a873502`).
  - **C3, first attempt:** the in-memory shapes starved bench-2 of memory
    (98.6% used, no swap, no OOM kill), and it needed a hard reset. That is
    v3.1.0's artifact-sized gate again: the 277 MB file passed the 512 MiB gate.
  - **C3 rerun** with `--no-shacl` and a memory watchdog: 58,231,176 triples,
    14.6 min, at least 25.7 GB always available.
    - Status MISMATCH: 10/13 queries exact, rapper PASS, engines agree.
    - Q9/Q10: 30,910 `PhaseSet` resources from GATK `PS`. The oracle's
      documented gap (`KNOWN_UNMODELLED`), still open in v3.3.0, so not a
      conversion error.
    - Q11 (record digest), resolved 2026-10-02:
      - `diag_q11.py`: the graph equals the VCF text for every field of all
        250,000 records.
      - `diag_q11b.py`: canonical QUAL (trailing zeros stripped) reproduces
        QLever's 256 buckets exactly: 0 differences, against 788 as written.
      - 1,998 records are affected. This is QLever's canonical `STR()` of
        `xsd:decimal`, not a conversion error.
  - Paper: `0a873502` (C2) and `b5fdbf83` (C3) on `paper/m8-tighten`, in
    vcf-rdfizer-testing#10.
  - Tool TODO:
    - an oracle that models phase sets, SV events and gVCF blocks;
    - an engine-independent Q11;
    - streaming shape checks.


    The mapping is appended to `harness_source.txt` on bench-2.
  - Not done:
    - the §5.4 recurrence query (rare.rq is the second cross-file query
      instead);
    - the v3.3.0 tag commit is an author query in the paper.

---

## 0. Short answers

**Are we using full genomes?**

- **For the use case: no.** Neither did the original plan. A1 says: "Restrict
  five real GRCh38 genomes to the ACMG SF v3.2 gene regions". The use case runs
  on each genome's 81 ACMG gene spans (7.1 Mb). That's also how
  secondary-findings analysis is done clinically: a lab interrogates the gene
  list, not the whole genome.
- **For scale: yes, one genome.** A separate *scale arm* applies the same policy
  and linkers to the whole HG005 genome (657M triples). The reviewer's criticism
  of the policy work is specifically that it "shows nothing about scale
  (evaluation is in memory)" (row 3). This arm also checks that restricting to
  gene spans doesn't change HG005's answer.

**Why not full genomes throughout?** Five whole genomes are about 4–5 billion
triples, judging by file size (HG005 alone is 657M). Converting them is not the
problem: the N-Triples part of HG005's 16.07 h run took about 1.6 h, since
HDT/COTTAS took the other 14.5 h. What doesn't fit is everything downstream:

| Stage | Five whole genomes | Five gene-span genomes (measured) |
| --- | --- | --- |
| Policy evaluation | Impossible in v0.1.0: in memory, refuses above 5M triples | ~1M triples per file, well inside the limit |
| Release views (3 requesters) | Up to 3 copies of ~20–30 GB of gzip N-Triples | Small |
| SPARQL index per query run (×4) | Billions of triples, each index larger than bench-1's 27 GB free disk | Minutes |
| What the question needs | The 81 genes | The 81 genes |

So the answer is gene spans for the question, and one whole genome to prove
the machinery scales. The scale arm needs a streaming policy executor (§4.4),
which is the main new tool feature in this plan.

**How is the code kept general?** Everything is split into three layers. The
tool never mentions ACMG, ClinVar, a participant or a requester (§2).

---

## 1. What this workstream must demonstrate

These are the acceptance criteria, taken from the review's own wording.

| Review | What it asks | Pass criterion for this workstream |
| --- | --- | --- |
| **M1**, §8.1 | "At least one end-to-end use case on real data that needs what RDF provides" | Real VCFs → RDF → links to real external resources → a clinically recognizable question → under the policy layer |
| **M1** | "Report correctness against a conventional pipeline … and the effort and time of each route" | Identical carrier lists from the RDF route and a bcftools route, for every requester, plus wall time and effort for each (§5.5) |
| **M5** | "Explain how records describing the same variant in different files become joinable … Show one cross-file query that works" | Shared SPDI identifiers across all files. Two cross-file queries: carriers (genome ↔ ClinVar) and recurrence (genome ↔ genome) |
| **Row 1** | "No query joins external data or spans two files" | Both queries above do |
| **Row 2**, §5 | Linking produced "no real links"; run tier 1 and 3 on real rsIDs, and tier 2 "on a real gene annotation" | Real link counts and coverage per genome, for every tier, replacing §3.7's null result |
| **Row 3** | Policy "on a toy cohort … nothing about scale (evaluation is in memory) … not part of the evaluated release" | Real genomes, a cohort of about 100, a whole-genome run, and a released tool version (v3.3.0) |
| **M8**, §5 | "Decide the fate of the policy demonstrator" | It becomes the central use case |

Not in this workstream: M2/M3 (performance, workstream B), M4 (converter
comparison, D4), M6 (validation scope, C) and M7 (RML, D3).

---

## 2. Design principle: three layers

```text
┌─ Tool (shipped in VCF-RDFizer, generic, tested in CI) ─────────────────────────┐
│  linking framework: Token / Interval / Allele joins, sequence maps, tiers 1–3  │
│  policy engine: select → partition → decide; in-memory and streaming executors  │
│  VCF Core profile: region, variant and linked-entity selectors (Turtle)        │
├─ Deployment configuration (Turtle/JSON a user writes; no code) ────────────────┤
│  linker manifests (spdi, ensembl-genes), an ODRL policy, a purpose vocabulary   │
├─ Experiment (vcf-rdfizer-testing only; this paper) ────────────────────────────┤
│  use_case.json, generate.py, derive/baseline/compare, the harness              │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Rule:** a feature goes in the tool only if a user with a different
question, gene panel, cohort or vocabulary would need it unchanged. The
consequences:

| Hard-coded today | Where it moves | How |
| --- | --- | --- |
| The 28 cancer-gene spans, inlined as SPARQL `VALUES` in `policy.ttl` | Configuration: a list of Ensembl gene IRIs | A shipped `LinkedSelector` (§4.2) over gene links (§3.2). The policy then states the panel, not coordinates |
| The GRCh38 → RefSeq table exists only for SPDI | Tool: `vcfl:SequenceMap` becomes the framework's contig-alias mechanism for any join | §3.1 |
| Assembly string and SPDI base IRI duplicated in `generate.py` and `derive.sh` | Experiment: read once from `use_case.json` and the linker manifest | Refactor |
| The DUO hierarchy hand-coded in `baseline_carriers.py` | **Stays.** The baseline must not share code with the RDF route, or their agreement means nothing | — |

A cheap guard enforces the rule: a tool test fails if any shipped module or
profile contains the strings `ACMG`, `ClinVar`, `DUO_0000043` or a participant
ID.

---

## 3. Linking: implementation

### 3.0 What already exists

- **`vcfl:AlleleJoin` and the `spdi` linker**, on branch `feature/spdi-linker`
  (tested; not yet merged).
  - Every ALT with explicit bases gets a trimmed SPDI IRI through a
    digest-pinned `SequenceMap`. So `chr17` and `17` give the same identifier.
  - The link is recorded as computed, not verified.
  - Known answers: 4 of 7 ClinVar classes match NCBI's SPDI exactly. The three
    repeat-context classes differ from NCBI's contextual form but denote the
    same allele.
- **Tiers 1–3:** `rsid-dbsnp`, `gene-demo` (synthetic) and `rsid-ensembl`
  (live, with rate limits and a budget).

### 3.1 L1: contig aliasing for interval joins

**Problem.** Interval joins match chromosome names exactly (datalinking.md §4:
"`1` and `chr1` are different"). Ensembl's gene annotation says `17`; four of
our genomes say `chr17`. So a real gene linker would link nothing on them.

**Change.** A manifest may declare `vcfl:contigAliases <map.tsv>`, pointing at
a `SequenceMap` with its own digest. Both sides (the record's CHROM and the
GFF3's seqid) are resolved to the sequence accession before matching. A name
the map doesn't list stays literal, which keeps today's behaviour. This is the
same TSV format and parser as SPDI, with no new concepts.

**Tests (tool):** `chr17` and `17` records both hit a gene declared on `17`;
an unmapped contig still matches literally; a digest mismatch fails closed.

### 3.2 L2: a real gene-annotation linker

A shipped manifest, `ensembl-genes-grch38`:
- **Join:** `IntervalJoin` over the **Ensembl release 116 GRCh38 GFF3**,
  referenced by HTTPS URL and SHA-256. The framework already downloads, caches
  and verifies it: one request, then cache hits.
- **Features:** `featureType gene`, `idAttribute gene_id`.
- **Output:** `vcfl:overlapsGene <https://identifiers.org/ensembl:ENSG…>`.
- **Aliases:** it uses L1 with the shipped GRCh38 map.

This is the "tier 2 on a real gene annotation" that §5 of the review asks for.
The policy's gene-panel rule (§4.2) stands on it.

The GFF3 file size is to be confirmed with a HEAD request; about 50 MB is
expected. Downloading it needs your approval.

### 3.3 Running every tier on real data

| Linker | Tier | Inputs | What the paper reports |
| --- | --- | --- | --- |
| `spdi` | 2 (allele) | every genome and ClinVar | Links and coverage; files joined by shared identifiers |
| `ensembl-genes-grch38` | 2 (interval) | every genome | Genes linked per record; agreement with ClinVar `GENEINFO` |
| `rsid-dbsnp` | 1 | the two PGP genomes (real rsIDs) | Links; noted as an identifier rewrite, not position-verified |
| `rsid-ensembl` | 3 (live) | the two PGP genomes | Failed closed: a persistent HTTP 500 on one batch |
| `rsid-myvariant` | 3 (live) | the two PGP genomes | Service-confirmed links; the response digests; requests and bytes transferred |

**Network etiquette.** The live tier uses the manifest's budgets (2
requests/s, batches of 100, at most 100 requests per run), caches every
response and replays offline. That comes to about 100 requests per PGP genome,
spread over roughly a minute.

It also needs a contact e-mail sent to Ensembl in the request headers. **You
choose that address**; I won't use one without your say-so.

### 3.4 Linking without parsing the RDF

`--mode link --rdf` parses the whole aggregate with rdflib's N-Triples parser.
That's slow even at 1M triples per genome, and hours at 657M. The framework can
already link from the VCF (`vcf-rdfizer-link run -i x.vcf`), deriving the same
subject IRIs the converter mints. **Every arm links that way**, and the
harness's link stage switches from `--rdf <graph>` to `-i <derived VCF>`.

Correctness comes from the policy `check`: a link whose subject isn't in the
base graph shows up as a dangling reference. No new tool code is needed.

### 3.5 Tests

- **Tool CI** (`test/test_linking_unit.py`): L1, and the L2 manifest's
  validation.
- **`plugin-tests/genes/`** (vcf-rdfizer-testing, run by hand):
  - known answers on real loci: a *BRCA1* variant links to ENSG00000012048
    under both contig styles;
  - a *NBR2*/*BRCA1* overlap links to both genes.

---

## 4. Policy: implementation

### 4.0 What already exists

v0.1.0 (released in v3.2.0):
- **The model:** select → partition → decide. Selectors are SPARQL, declared in
  Turtle, and ownership is declared in the profile. ODRL deny-wins with default
  deny, DUO purposes, a release manifest, and `check` (structural checks plus a
  VCF-text oracle).
- **The limit:** rdflib in memory, refusing inputs above 5M triples.

### 4.1 P1: list-valued selector parameters

**Problem.** Parameters bind one value each (`initBindings`). A gene panel is a
set, which is why the demo inlined its coordinates into a policy-local query.

**Change.** Every parameter is injected as an **inline `VALUES` block at the
start of the selector query's outer `WHERE` group**. This covers single values
and lists (e.g. `vcfp:entities ( <g1> <g2> )`), and replaces rdflib's
`initBindings` entirely.
- Terms are serialized by the RDF library, never by string pasting.
- The selector query is parsed once at load time, a few hundred characters
  and no data. A query whose outer group can't be located is refused.
- Parameters must be referenced in that outer group, not inside a subquery,
  whose scope a `VALUES` block cannot reach. This is documented in the profile
  and caught by the equivalence test.

**Why inline and not trailing.** This was verified on QLever `bfd5741` (the
image's build) and on rdflib, 2026-09-28. v0.1.0 binds parameters with rdflib's
`initBindings`, which pre-binds variables and is not standard SPARQL. Standard
SPARQL 1.1 joins a *trailing* `VALUES` clause *after* the `WHERE` clause, so a
`FILTER` inside `WHERE` sees those variables unbound.

The shipped `RegionSelector` written with a trailing `VALUES` returned
**no rows on both engines**; with `initBindings`, or with inline `VALUES`, it
returned the expected record. On an endpoint the naive port would make every
region rule select nothing, so **a prohibition would silently release the
region it protects**. That is a fail-open bug, caught here by a probe rather
than in a release.

### 4.2 P2: `vcfp:LinkedSelector`, shipped in the VCF Core profile

The selector means: records whose call carries `?predicate` to any of
`?entities`.

```turtle
ex:cancer-panel a odrl:Asset , vcfp:GraphSelection ;
    vcfp:selector [ a vcfp:LinkedSelector ;
                    vcfp:predicate vcfl:overlapsGene ;
                    vcfp:entities ( ensembl:ENSG00000012048 ensembl:ENSG00000139618 … ) ] .
```

**What it covers.** The same selector covers several kinds of rule, all written
as data:
- a gene panel (`overlapsGene`);
- a list of named variants (`sameVariantAs` to SPDI or dbSNP IRIs), e.g.
  "withhold APOE ε4";
- anything a future linker emits.

**It fails closed.** Its `vcfp:violations` query returns a row when the graph
contains *no* `?predicate` triple at all. So a policy evaluated without its
link graph is refused rather than silently releasing everything. This is the
policy-side form of the design doc's warning that "an under-matching join
looks exactly like a true negative".

**Effect on the experiment.** `generate.py` stops writing SPARQL. `policy.ttl`
becomes readable Turtle: five consents, and one prohibition naming 28 Ensembl
genes.

### 4.3 P3: a streaming executor

This implements Tier 3 of `privacy-policy-design.md` §5 ("post-hoc, over an
existing artifact … memory scales with the number of in-scope records, not the
graph"). The declarations don't change; only where they execute does.

```text
                    ┌──────────────── SPARQL 1.1 endpoint (QLever, Fuseki, …) ──┐
policy.ttl ─► rules │ selector queries → selected roots                         │
profile.ttl ──────► │ ownership path   → owned IRIs (explicit)                  │
                    │ unit query       → per-record report rows                 │
                    └───────────────────────────────┬───────────────────────────┘
                                                    │ owned sets (size ∝ selection)
graph.nt.gz ── one streaming pass: decide(subject), decide(object ∈ node space) ─► view.nt.gz
```

**Design:**
1. **Selection runs on an endpoint.** `--endpoint URL` means any SPARQL 1.1
   endpoint. The harness starts QLever from the image; users can bring their
   own. Parameters reach the endpoint as inline `VALUES` (§4.1).

   **The experiment uses this mode in every arm, not only the scale arm**
   (§4.5). The rdflib executor stays in the tool as the reference
   implementation for fixture-size equivalence tests and tiny inputs, and is
   never run on a data graph in this paper.
2. **Decision logic is shared, not duplicated.** `decide()` is the same
   deny-wins function over owned sets. With `vcfp:iriSubtree`, ownership is a
   prefix test (`ancestors()`), so a withdrawn file is one prefix, not millions
   of IRIs. Memory is bounded by the selections: a gene panel is a few thousand
   records.
3. **The profile declares a node space** (`vcfp:nodeSpace "file://"`). v0.1.0
   withholds a triple whose object is a withheld node of the graph, and keeps
   vocabulary IRIs such as `vcfc:FiltersPassed`. In memory it can ask "is this
   object a subject somewhere?". A stream can't, so the profile says which IRIs
   the graph mints. That's generic: any profile declares its own.
4. **Byte preservation.** Kept lines are written unchanged, so digests and
   determinism carry over. The manifest records the input and output digests.
5. **`check` at scale:**
   - prohibited content and default deny are checked in the same stream;
   - dangling references are checked by one SPARQL query over the view on the
     endpoint;
   - the VCF-text oracle streams the VCF into a small record graph (about 7
     triples per record), loads it into the endpoint and runs the same
     selectors.

**The correctness test that matters: equivalence.** On the example cohort and
on the five gene-span genomes, the streaming executor must produce **the same
view (as a sorted triple set), decisions and summary** as the in-memory one.
That test, not a new oracle, is what licenses using it on a whole genome.

**What stays out of scope, stated in the paper:**
- sample-level rules in *condensed* graphs, which need vector masking (design
  doc §8);
- query-time enforcement, which the design doc ranks as secondary for a tool
  whose output is files people take away.

### 4.4 Tests

| Component | Where | What |
| --- | --- | --- |
| P1 parameter injection | tool CI | Single and list values render as one inline `VALUES` block in the outer `WHERE` group; injection-safe for IRIs and literals with special characters; a query with no locatable outer group is refused |
| P1 scoping regression | `plugin-tests/policy/` (in the image, against QLever) | The shipped `RegionSelector` selects exactly the in-region records on QLever. The same selector with a trailing `VALUES` is shown to select nothing, so the test documents the failure mode it guards against |
| P2 `LinkedSelector` | tool CI + `plugin-tests/policy/` | Gene panel and named-variant cases; refuses a graph without the link predicate |
| P3 streaming executor | `plugin-tests/policy/` | Equivalence with the in-memory executor on the example cohort (both sample profiles); all existing mutation tests pass through `check --endpoint` |
| Generality guard | tool CI | No experiment strings in shipped code or profiles (§2) |
| QLever parity (experiment) | `test_use_case.py`, in the image | `carriers.rq` and the recurrence query return the same rows on QLever as on rdflib for the synthetic graphs. This catches dialect differences (regex escaping, `STR()` comparisons, unbound versus empty `GROUP_CONCAT`) before a real run does |

### 4.5 Where every query runs, and why not rdflib or Comunica

**Decision: QLever evaluates every query over data.** rdflib stays for two jobs
only:
- parsing configuration (policies, profiles and linker manifests, all
  kilobytes);
- serving as the reference executor in fixture-size equivalence tests.

No data graph in this paper is loaded into rdflib.

| What is queried | Today | Plan | Scale in this plan |
| --- | --- | --- | --- |
| The use-case questions (carriers, recurrence) | QLever, over one file `run_query.py` concatenates | QLever. One index per requester, built from the views plus ClinVar and its links, with **one named graph per file** (`-f <file> -g <file IRI>`), streamed with no concatenated copy | Arm 1 ~20M triples; arm 2 ~110M; arm 3 one whole-genome view |
| Policy selection, ownership, unit report | rdflib in memory (5M-triple cap) | QLever endpoint. **One index per arm**, over the base graphs plus link graphs, shared by all three requesters | Same as above; arm 3 ~660M |
| Policy `check`: dangling references, VCF oracle | rdflib | Streaming pass, plus queries on the same QLever index | — |
| Linking input | rdflib N-Triples parser (`read_rdf`) | Read from the VCF (`read_vcf`), which derives the same subject IRIs; no RDF parsing | ~10k records per genome; ~4M for arm 3 |
| Configuration (Turtle) | rdflib | rdflib | Kilobytes |

**Verified on the image's QLever (`bfd5741`, 2026-09-28):**
- the index builder takes several `-f` inputs and stdin (`-f -`);
- `-g` gives each file its own named graph, and `GRAPH ?g` keeps file
  boundaries at query time;
- the profile's SPARQL works: the `hasCall/hasSampleCall?` ownership path
  (including the zero-length case), `GROUP_CONCAT` with `OPTIONAL`, `STR()`
  comparisons, and cross-file joins;
- `VALUES` scoping behaves as described in §4.1.

**Cost.** The paper's own measurement is 22.8 s of QLever setup for 17.1M
triples. Extrapolated, that's under a minute per index for arm 1 and a few
minutes for arm 2. Arm 3 is measured, not assumed: the same index serves
workstream B3's whole-genome queries.

**Why not Comunica.**
- The image's Comunica engines serve one source each, and the file engine
  loads its source into memory. On the 17.1M-triple slice that endpoint failed
  to start (the `_await_bind` crash that kept workstream 14 to QLever above the
  small scale). Arm 2 is about six times larger, and arm 3 about forty times.
- What Comunica would add is *query-time federation across separate files
  without merging them*. The per-file named graphs keep each file's identity
  inside one QLever index instead.
- The cross-file claim the review asks for (M5) rests on shared SPDI
  identifiers, not on which engine joins them.

**Optional:** on arm 1 only (six sources), run the carriers query through
Comunica over per-file HDT views, which are memory-mapped rather than loaded.
That shows the same answer from separate files federated at query time. It's
off the critical path and costs about half a day.

---

## 5. The experiment

### 5.1 Question, and what the first run changed

> *Which participants carry a ClinVar-classified variant in an ACMG SF v3.2
> gene, and what may each requester see?*

The first run (five genomes, gene spans, bcftools route) found **no ClinVar
pathogenic variant in any of the five genomes**. That was verified as biology,
not matching: every position hit has genuinely different alleles. It's the
expected result for five unselected people.

The question now returns every classification, and reports the pathogenic
subset separately. Result so far:
- 7,211 carriers overall;
- clinical care 2,878, disease-specific research 2,988, general research 1,987;
- reportable: 0.

The cohort arm (§5.2) is where a non-empty reportable subset is expected.

**One definition to fix before the RDF route runs.** "In a cancer gene" must
mean the same thing in both routes:
- The RDF policy withholds a *record overlapping a cancer-gene span*.
- The baseline today withholds a *carrier row whose reported ClinVar gene is a
  cancer gene*.

They differ for records that overlap two genes. Fix: both use the record-based
rule, the baseline through `bcftools view -T cancer.bed`. The compare gate
would catch the difference, but it's cheaper to define it once.

### 5.2 Three arms

| Arm | Inputs | Size | What it proves |
| --- | --- | --- | --- |
| **1. Heterogeneous** (derived; baseline done) | Five real genomes from three sources (PGP ×2, GIAB ×2, precisionFDA ×1), three variant callers, two naming conventions | ~10k records each; ClinVar 331k | Integration across files that disagree on conventions |
| **2. Cohort** (new) | About 100 individuals from the **1000 Genomes high-coverage** call set (NYGC, GRCh38, open access); unrelated samples only, stratified across the 26 populations, seeded | ~10k records each, ~1M triples each | Cohort scale; a non-empty reportable subset; the policy at cohort breadth. This is the review's own suggestion: "a … 1000 Genomes slice with simulated consents" |
| **3. Whole genome** (new) | HG005 whole genome, decompressed from the HDT already on bench-2 (through stdout; the file output is broken) | 657M triples | The streaming executor and linkers at genome scale, with time and peak memory; HG005's whole-genome answer equals its arm-1 answer |

**Arm 2 inputs.** Only the ACMG regions are fetched, through the remote tabix
index:
- one chromosome at a time and sequentially;
- then split into one file per person (`bcftools view -s S -c1`), mirroring
  per-participant deposit, which the paper states.

The exact files and transfer size are to be confirmed with HEAD requests and
approved before downloading.

**Consents.**
- Arm 1 keeps its five hand-written consents.
- Arm 2's consents come from a seeded generator in `use_case.json`: stated
  proportions of general, health/medical, disease-specific and clinical-only
  consent, plus a withdrawal rate. They're labelled simulated everywhere.
- The generator is experiment code; the tool never sees it.

### 5.3 The two routes, and the gate

| | RDF route | bcftools baseline |
| --- | --- | --- |
| **Variant identity** | `spdi` links; no contig renaming needed | Rename contigs to ClinVar's naming; `annotate --pair-logic exact` |
| **Gene attribution** | `ensembl-genes-grch38` links | BED intersection |
| **Consent** | `policy.ttl` through `vcf-rdfizer-policy`; one checked view per requester | `baseline_carriers.py` |
| **The question** | One SPARQL query per requester, under QLever | `bcftools query` plus the script |

**`compare.py` is the gate.** The carrier lists must be identical for every
requester and every arm. No timing or effort number is reported until they
are.

### 5.4 The cross-file query (M5)

Beyond carriers (genome ↔ ClinVar), a second query only shared identity makes
cheap: **which ClinVar-classified variants recur in two or more participants,
and how many carriers of each does every requester see?**

The RDF route groups by the SPDI IRI across all views. The baseline needs
`bcftools merge` followed by counting. Both must agree.

### 5.5 Measuring effort, honestly (M1)

Wall time comes per stage from `bench.json`. Effort is measured two ways:

1. **What a user authors:**
   - RDF route: lines of hand-written configuration (the policy's rules and the
     query);
   - baseline: lines of script.

   The Turtle's gene list and the BED file are counted as data, not logic.
2. **Change scenarios.** Three realistic changes are applied to both routes,
   counting the lines each has to change:
   - a participant withdraws;
   - a new requester with a new purpose;
   - the panel changes from cancer genes to cardiac genes.

   In the RDF route each is one policy edit. In the baseline each touches
   script logic. That is the auditability argument, measured rather than
   asserted.

Where the baseline is shorter, the paper says so (plan §7 risk).

### 5.6 Outputs and the paper figure

- **Per arm:** `comparison.json`, a requester × participant `grid.tsv`, link
  statistics per linker, and per-stage cost.
- **Arm 3:** time, peak memory and output sizes for linking and each
  requester's streaming evaluation.
- **The figure** (plan A7): the files joined by shared SPDI identifiers, the
  policy layer, and the per-requester answer. It replaces §3.7 and absorbs
  §3.8.

---

## 6. How this answers the review

| Review item | What the reviewer said | What we show | Evidence | Paper |
| --- | --- | --- | --- | --- |
| **M1** | No demonstration of the benefit | Three arms of real genomes; real ClinVar and Ensembl links; a clinical question under consent; identical answers from a conventional pipeline; time and effort for both routes | `comparison.json`; the effort table | New §3.x, replacing §3.7 and §3.8 |
| **M5** | File-scoped IRIs block cross-file identity | SPDI identifiers shared across 106 files and ClinVar; two cross-file queries; VRS named as next step | Link statistics; the recurrence query | §2.1 identity paragraph; §3.x |
| **Row 1** | No query joins external data or spans files | Both queries do | — | Abstract; §4.3 "we show" becomes true |
| **Row 2**, §5 | No real links | All four linkers on real data, with counts and coverage | `link__*` reports | §3.x linking paragraph |
| **Row 3** | Toy cohort; in memory; outside the release | Real genomes; about 100 participants; a 657M-triple genome through the streaming executor; tool release v3.3.0 | Arm 2 and 3 results; the equivalence test | §3.x; Table 8 row becomes "evaluated" |
| **M8**, §5 | Decide the policy demonstrator's fate | It becomes the central use case | — | Contributions list |
| §2 "Why RDF?" | Only self-consistency queries were evaluated | A question VCF tooling answers only with renaming, annotation and a consent script | The change-scenario table | Discussion: "when does the RDF route pay?" |
| **m3** (partial) | Condensed at cohort scale untested | Not addressed: the cohort uses per-participant expanded files; condensed sample-level masking is stated as future work | — | Limitations |

---

## 7. Order of work, effort and machines

| Phase | Work | Effort | Machine |
| --- | --- | --- | --- |
| **1. Arm 1, identity and query** | Clone `feature/spdi-linker` into VM scratch. Fix the §5.1 cancer-gene definition. Convert; link from the VCF (spdi, rsid-dbsnp); build the QLever index; run the unrestricted query; compare against the baseline's unrestricted list. This validates identity, linking and the query on real data, with no policy and no rdflib | 1 d | bench-1 |
| **2. Generalize, then govern arm 1** | L1 contig aliases; L2 gene linker; P1 inline-`VALUES` parameters; P2 `LinkedSelector`; P3 endpoint executor (needed now, since no data goes through rdflib); equivalence and parity tests; the generality guard. Then govern arm 1 on QLever and compare all four requester lists | 3 d | local + bench-1 |
| **3. Arm 2, cohort** | Fetch 1000G regions; split; seeded consents; all stages; tier 3 live on the PGP genomes | 1.5 d + ~1 d unattended | bench-1 |
| **4. Arm 3, scale** | HG005 whole genome: decompress the HDT, link from the VCF, build the QLever index, stream each requester's view, check. Record time and peak memory | 1 d + ~0.5 d unattended | bench-2 (68 GB free; HG005 artifacts are there, and the QLever index doubles as workstream B3's) |
| **5. Release** | v3.3.0 with the linker, aliases, gene manifest and P1–P3. Final re-run of arms 1–2 on it, so every number has one provenance | 0.5 d | both |
| **6. Measure and write** | Effort and change scenarios; figure; results section (plan A7) | 1.5 d | — |

**Total: about 8.5 working days plus about 1.5 unattended VM days.**

**Minimum viable version (about 7.5 days): drop phase 4.**
- P3 is no longer optional, because it's how governance avoids rdflib in
  every arm. Dropping it would mean evaluating in memory.
- Without arm 3, the paper shows cohort breadth (about 100 files), and states
  that graph-scale governance was not measured.

Phase 1 comes first on purpose. The two bugs found so far (ClinVar's missing
contig headers, and the SIGPIPE that inverted a test) were invisible at fixture
scale. So was the `VALUES` scoping in §4.1. Five files are the cheap place to
find the next ones.

---

## 8. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| The cohort still gives few reportable findings | Report the number honestly. The question returns all classifications either way, and the governance grid is already informative on arm 1 |
| QLever's SPARQL differs from the reference executor somewhere the fixtures don't reach | The parity and equivalence tests run on the real arm-1 files as well as the fixtures. Any difference blocks the run; it isn't a result |
| One index per requester is slow to build at cohort scale | Measured in phase 2 on arm 1 before arm 2 starts. The fallback is one shared index with a named graph per requester's view, which trades build time for index size |
| The streaming and in-memory executors disagree | Nothing is released on the streaming path until the equivalence test passes; the difference is a bug to fix, not a result |
| The routes disagree on an edge case | The compare gate reports it; fix the definition in `use_case.json` (§5.1 is one already found) |
| 1000G remote reads are slow or rate-limited | Sequential, one chromosome at a time, resumable (the harness skips finished cells). Or reduce N |
| Tier 3 (Ensembl) is unavailable | Cached responses replay offline; report the tier as run on the cached responses, dated |

## 9. Decisions needed from you

1. **Shape:** the three arms as described, or the minimum viable version? -- three arms
2. **Downloads:** each needs approval once exact sizes are confirmed by HEAD
   request: -- sounds okay
   - the Ensembl 116 GRCh38 GFF3 (about 50 MB expected);
   - the ACMG regions of the 1000 Genomes high-coverage call set.
3. **Contact e-mail** for the live Ensembl tier: which address, if any. -- elias.crum@ugent.be
4. **Cohort size:** start at about 100, or pick N from the phase-1 cost
   measurements? -- pick N
