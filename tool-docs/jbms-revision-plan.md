# JBMS revision plan

*Plan for addressing [`jbms-review-vcf-rdfizer.md`](jbms-review-vcf-rdfizer.md), a
simulated expert review (major revision) of the BioMedSem manuscript. Written
2026-09-25. Section numbers (§) refer to the review; "M" and "m" are its major
and minor issues.*

---

## 1. The diagnosis, and the strategy

The review's verdict is that the paper shows the tool **works** (validation) and
what it **costs** (benchmarks), but not why a life-science user should **pay**
that cost. The introduction promises three things RDF gives variant data:

- linkage to external knowledge;
- region- and variant-level governance;
- declarative queries across files.

None of them is demonstrated on real data with an evaluated release. Two of
the paper's own results also cut against its storage story: the
HDT/COTTAS builds take 14.5 of the 16.07 h whole-genome run, yet the artifact
barely changes query time.

Four moves address almost everything, in this order of leverage:

1. **Demonstrate the value once, on real data, end to end** (workstream A). One
   use case, in which several real genomes are linked to a real knowledge
   resource through shared variant identifiers and queried together under
   per-participant consent, answers claims 1–3 of the review's table, M1 and
   M5, and turns the policy demonstrator from an add-on into the paper's
   centrepiece. This is where most of the new effort should go.
2. **Make every performance claim conditional and honest** (B). Most of this is
   rewording existing numbers. The experiments it needs are already built
   (`14_regional_access.sh`) or have their inputs on disk (the whole-genome
   HDT/COTTAS on vcf-bench-2).
3. **Scope the validation and positioning claims to what was shown** (C, D).
   This is mostly text, plus two cheap runs.
4. **Cut to the contribution** (E). Move the campaign bookkeeping to
   supplementary material, write a contributions list, and make the Discussion
   interpretive. The target is about 20 pages of body text, down from about 36.

What we do **not** do is try to answer every point with new engineering. The
review lists more experiments than one revision can carry. §6 records what we
defer, and why.

---

## 2. What the revised paper will argue

The contributions list, which the paper currently lacks (M8), is the spine of
the revision. Each contribution names the evidence behind it, and every
workstream exists to make one of these rows true:

| # | Contribution | Evidence (revised paper) | Status |
| --- | --- | --- | --- |
| C1 | **Faithful, verified conversion.** VCF → VCF Core RDF, validated by a paired SPARQL/VCF oracle, SHACL shapes and fault injection | 988 paired comparisons, the 113-mutant experiment, determinism; scope stated precisely (C1–C3) | Exists; needs scoping |
| C2 | **Cohort-scale modelling, measured.** Expanded vs condensed sample profiles, and why triple counts mislead | Fig. 4 (triples against bytes; COTTAS added by the running ladder), Eq. 1 | Exists; COTTAS series landing |
| C3 | **Linked, governed, cross-file variant data, on real genomes** | New use case (A): real genomes plus ClinVar, joined through shared identifiers and answered under consent policies, against a conventional pipeline | **New — the central addition** |
| C4 | **A cost model with guidance.** When conversion, HDT, COTTAS and SPARQL pay off, and when a VCF tool is the better choice | Honest retrieval comparison (cold/warm, selective queries, tabix arm, break-even), large-artifact querying, sizes against the source VCF (B) | Partly exists; reframe plus two runs |

**Out of the headline:** host calibration, the configuration covering set,
operating modes, the memory sweep and the issues log. They remain as evidence
of software quality, in supplementary material (E).

---

## 3. Workstreams, ranked by impact per unit of effort

Effort is engineering or writing days. "VM" marks machine time that runs
unattended.

### Prerequisite P — a release that contains what the paper reports

**What:** cut **v3.2.0**. New features justify a minor version.
- **Includes:** merged PR #26 (policy plug-in), PR #23 (regional runner and
  tabix, already on `main`), PR #24 (COTTAS indexes), the missing-token scope
  fix, the non-UTF-8 input fix (#27, once merged), and the linker added in A2.

**Why:** the policy demonstrator is "after the release", and the regional arm
cannot run on v3.1.0. Reviewers object when a paper's centrepiece is outside
the evaluated release (claims-table row 3).

**Provenance rule for the paper:**
- The campaign (§3.1–§3.6) stays on v3.1.0, as run.
- The new experiments (A, B2, B3, C2, C3) run on v3.2.0.
- The paper says so in one sentence, and each figure caption names its version.
- Nothing is re-run just to change a version number.

**Effort:** 0.5 d, following the existing release process (tag, PyPI/Conda,
Docker digest).

### A — Show the value on real data (highest impact; addresses M1, M5, rows 1–3)

> **Implementation detail: [`workstream-a-implementation.md`](workstream-a-implementation.md)
> (2026-09-28).** It keeps the gene-span inputs below. It adds a 1000 Genomes cohort
> arm and a whole-genome scale arm, and broadens the question to every ClinVar
> classification, because the five genomes carry no pathogenic variant. It also
> moves the gene panel out of SPARQL into generic tool features (a `LinkedSelector`,
> a real gene linker with contig aliasing, and a streaming policy executor).

**The use case:** *"Which participants carry a ClinVar pathogenic or
likely-pathogenic variant in an ACMG secondary-findings gene, and what may each
requester see?"*

It is clinically recognizable, needs data outside the VCF, spans several files,
and has a natural consent dimension (secondary findings are exactly what
consent codes govern).

| Step | What | Uses | Effort |
| --- | --- | --- | --- |
| A1 | **Inputs.** Restrict five real GRCh38 genomes to the ACMG SF v3.2 gene regions (81 genes; the regions come from a public gene annotation): two PGP genomes with real rsIDs (NB72462M, NG131FQA1I) and three GIAB (HG002, HG004, HG005, no rsIDs). Normalize with `bcftools norm -f GRCh38.fa -m-`. Take the ClinVar GRCh38 VCF (public domain) for the same regions. Small, so conversion takes minutes | `02_derive_ladders`-style derivation | 0.5 d |
| A2 | **Shared variant identity (M5).** A new offline linker, `spdi`, emits `vcfl:sameVariantAs <SPDI IRI>` for every normalized record. The GRCh38 chromosome → RefSeq accession table is static, and SNVs and left-normalized indels map directly. Records for the same variant in different files, including ClinVar's, then share one IRI. This is the direct answer to "file-scoped IRIs cannot integrate". VRS computed identifiers are named as the next step (§6) | Linker plug-in framework (tier-2 pattern, digest-pinned table) | 1–1.5 d incl. tests in `plugin-tests/` |
| A3 | **Convert and link.** The five genomes (expanded) and ClinVar (sites-only, structured INFO, so `CLNSIG` and `CLNREVSTAT` become queryable literals). Run `spdi` on all six, and `rsid-dbsnp` / `rsid-ensembl` on the two PGP genomes, which turns §3.7's null result into real links (review §5) | v3.2.0 | 0.5 d (+VM) |
| A4 | **Govern.** Reuse the policy plug-in unchanged, on real genomes: per-participant consents (simulated, stated as such), one withdrawal, and the incidental-findings rule over the ACMG regions, expressed with the shipped region selector or one declared gene-set selector. The plug-in's generality (Turtle-declared selectors) is shown on real data rather than only claimed | policy plug-in | 0.5 d |
| A5 | **Query.** One SPARQL query per requester: carriers of P/LP ClinVar variants in ACMG genes, joined across the six graphs through the SPDI links, over each requester's release view. Report the carrier list, and time per query under QLever | existing engines | 0.5 d |
| A6 | **Baseline.** The same answer through a conventional pipeline: `bcftools isec`/`annotate -a clinvar`, `bcftools view -i 'CLNSIG~"athogenic"'`, plus a script applying the consent table. Report: identical carrier lists (**required**), steps and lines of code for each route, and wall time. State plainly where the conventional route is simpler; the paper's argument is that RDF makes the consent- and integration-bearing parts declarative and auditable, not that it is always shorter | bcftools in the image | 1 d |
| A7 | **Write-up.** A new Results subsection that replaces §3.7's plumbing test and absorbs §3.8. A figure: the six graphs, the shared SPDI identifiers, the policy layer, and the per-requester answer. The policy section moves from "post-release demonstrator" to "evaluated in v3.2.0" | — | 1 d |

**Total: about 5–6 days.** This single workstream fixes the review's top
priority (§8 item 1), gives the paper its thread from motivation to
conclusion, and makes the §4.3 "we show that…" sentence true.

**Scope guard:** one use case, done completely, beats three done partially.
Resist adding pharmacogenomics or federation with a live endpoint here; they
go in Future Work.

### B — Make the performance case honest (addresses M2, M3, row 8–9)

| Step | What | Effort |
| --- | --- | --- |
| B1 | **Reframe the retrieval result (text, existing numbers).** Report cold and warm: QLever's 22.8 s setup is index construction, so a single cold question loses to the 11.5 s parser. Add the break-even including conversion (about 45 questions on the 100k slice; never, for one batch). Rewrite the abstract's "2.5–2300×" sentence with its conditions. State that under the default engine HDT and COTTAS are transport formats, not query indexes | 0.5 d |
| B2 | **Selective questions and the tabix arm.** `14_regional_access.sh` is implemented and smoke-tested on both scales. Run the full sweep on vcf-bench-1 with v3.2.0. It answers "selective" with data (1 kb–10 Mb windows) and adds the indexed-VCF baseline the AUTHOR QUERY promises. The placeholder then becomes a result either way (see `proposal-indexed-regional-access-arm.md`) | 0.5 d + ~1.5 h VM |
| B3 | **Query the whole-genome artifacts directly.** The 657M-triple HDT (4.6 GB) and COTTAS (1.5 GB) are still on vcf-bench-2, so there is nothing to rebuild. Run the regional questions and a few Q1–Q13 against them with the HDT and COTTAS engines, and QLever for reference. Report cold start, query time and peak memory. This tests the one regime where HDT/COTTAS should earn their build time: on-disk querying of a graph larger than an engine wants in RAM. Expect some engines to be impractical at this scale; that is a result too | 1 d + VM |
| B4 | **Size against the source VCF, and guidance (text).** Add expansion relative to the input VCF (e.g. whole genome: 10.88 GB final tree against the 139 MB `.vcf.gz`, about 78×). Add a short guidance table: build nothing or gzip N-Triples for batch QC; COTTAS to archive or ship; HDT, COTTAS or QLever for repeated selective querying, depending on B3. It turns the storage results from a table of numbers into advice (M2d) | 0.5 d |

**Total: about 2.5 days, half of it text.** B2 and B3 run on different VMs in
parallel.

### C — Scope and strengthen the validation claims (addresses M6, row 5–6)

| Step | What | Effort |
| --- | --- | --- |
| C1 | **State the scope (text).** Value-level paired validation ran on fixtures and slices up to 17.1M triples; the corpus and the whole genome had triple-count and decode checks. Say so in the abstract and §3.5 | 0.25 d |
| C2 | **The default-profile mutation score.** The archive has queries-only (96/113) and the full SHACL profile (113/113), but not the **default (core)** profile users actually run. One `08_robustness` mutation cell with `--shacl-profile core` settles it in minutes | 0.25 d |
| C3 | **Paired validation on one heterogeneous real file.** Run `--validate` (QLever) on one PGP 250k slice, NG131FQA1I, which has real rsIDs and a different caller from GIAB. This closes the "heterogeneity was never value-checked" gap (row 6) with one cell | 0.25 d + VM |
| C4 | **Engine agreement counted properly.** Report agreement only where two or more engines ran: 25 validations, all agreeing. `paper-assets/figures/count_validation.py` already counts them | 0.1 d |
| C5 | **Digest strength (Q11–Q13).** Replacing the 256-bucket histograms with a full-hash order-independent aggregate is a tool change that would invalidate the campaign's digest results. **Defer** (§6), and state the limitation precisely in §3.5 | text only |

**Total: about 1 day.**

### D — Positioning and claims (addresses §3 points 2, 4–6; M4, M7; row 4, 12)

| Step | What | Effort |
| --- | --- | --- |
| D1 | **Non-RDF alternatives.** A paragraph in the Introduction or Related Work on Hail, GEMINI, TileDB-VCF, relational and columnar stores, GA4GH Beacon/htsget and FHIR Genomics. When a variant store is the right tool, and what RDF adds: standards-based policy, shared identifiers, federation, schema-independent integration. Workstream A then *shows* two of these | 0.5 d |
| D2 | **Separate the tool from the vocabulary paper.** One sentence in the Introduction and a short "target model" paragraph: this paper contributes the converter, its validation layer and representations; the vocabulary is the companion SWAT4HCLS paper, with its status stated | 0.25 d |
| D3 | **RML versus emitters, honestly (M7).** The run metrics already separate the sources. In the 10k-record rung the Python emitters wrote about 1.63M of 1.72M triples (samples 710k, INFO 913k, header 4k), so RML produced at most about 5%. Report the split in a sentence. Reframe the claim: RML declares the backbone (file, record, call, header), the emitters handle row-dependent typing, and extension happens through plug-ins with declared behaviour (linkers, and the policy plug-in's Turtle selectors). Change the Table 1 "Extensible mappings" ✓ to a qualified mark with a footnote | 0.5 d |
| D4 | **Comparison with prior converters (M4).** Timebox 1 day per tool: convert the 100k HG005 slice with TogoVar VCF2RDF (Rust) and SPARQLing Genomics `vcf2rdf` (C). Report time, size and triples, and which of the paired queries each output can answer. If a tool will not build within its timebox, report that factually, and reword Table 1 and §1 as a feature comparison rather than a claim of superiority. **Minimum:** the rewording (0.25 d). **Target:** at least one measured comparison | 0.25–2 d |

**Total: about 1.5–3.5 days**, depending on D4.

### E — Structure and length (addresses M8, §5)

| Step | What | Effort |
| --- | --- | --- |
| E1 | **Contributions list** (§2 above) at the end of the Introduction, each item pointing at its evidence. Move Table 8 (capability status) forward, next to it | 0.25 d |
| E2 | **Re-section:** Implementation / Evaluation design (the current §2.3–2.4 plus the new use case) / Results / Discussion | 0.5 d |
| E3 | **Move to supplementary material:** §3.1 host calibration and Table 4 (campaign cells) in detail; §3.9 (covering set, modes, memory sweep); §3.11 (issues log), keeping one paragraph in §3.5 on the three real defects the validation caught; §2.2 toolchain pins, chunk sizes, image digests and commit hashes (a reproducibility appendix) | 1 d |
| E4 | **An interpretive Discussion:** when to use VCF-RDFizer, and when not; when each representation pays (B4); what the condensed profile gives up (m3); what the use case shows. Remove the number-for-number repetition of Results | 1 d |
| E5 | **The abstract** rewritten around problem → demonstrated benefit (A) → honest cost (B) → conclusion (m9), after A–D land | 0.25 d |

**Total: about 3 days.** Do E last, after A–D; E3 can start early.

### F — Minor issues (the fast wins, all text)

| m | Fix |
| --- | --- |
| m1 | Remove the revision key, the AUTHOR QUERY (replaced by B2's result), "(This will change in future version)", the placeholder funding, and "one the"; render the Declarations as unnumbered back matter |
| m2 | "stays smaller than the input VCF" → the actual crossover (Fig. 4b; about 256 samples) |
| m3 | State what the condensed profile gives up at cohort scale (genotypes in literals). If time allows, time Q5/Q6 on the 2,504-sample condensed graph (0.5 d + VM; optional) |
| m4 | Fig. 4a: label "×390 from 1 to 2,504 samples" as distinct from panel (c)'s expanded ÷ condensed ratio |
| m5 | **Explain the 6 h against 16.07 h:** the records ladder built HDT only, while the corpus run built HDT and COTTAS. State which representations each experiment built |
| m6 | "pre-registered" → cite the committed protocol, or say "fixed before the run, in commit …" |
| m7 | Report the expanded profile's per-sample increment (a linear fit with an intercept) next to the exponent |
| m8 | Identify "test-larger" (269M triples) in §3.3 and Fig. 3b |
| m9 | See E5 |
| m10 | Zenodo DOIs for the v3.2.0 release and the benchmark archive; cite them in Data and Code availability |
| m11 | Neutral wording for Table 1 footnote b |

**Total: about 1 day**, apart from the optional m3 timing.

---

## 4. Order of work

The critical path is A (new engineering), with experiment runs overlapping it.
Text-only work fills the gaps.

| Phase | Work | Machines |
| --- | --- | --- |
| **1. Quick wins (≈2 d)** | F (all minor text fixes); B1, B4; C1, C4; D2, D3; start E3 (moving material to supplementary) | — |
| **2. Release and launch runs (≈1 d)** | P (v3.2.0, after #26 and #27 merge). Launch: C2 (mutation, core profile) and C3 (validation of NG131FQA1I) on vcf-bench-1; B2 (regional sweep) on vcf-bench-1; B3 (whole-genome artifacts) on vcf-bench-2 once the COTTAS ladder finishes | bench-1: C2, C3, B2 · bench-2: B3 |
| **3. The use case (≈5–6 d)** | A1–A6 while the runs complete; D4 in parallel if a second person is available, otherwise after A | bench-1: A3 conversions |
| **4. Write (≈3 d)** | A7; D1, D4 write-up; E1, E2, E4, E5; regenerate figures with `make_figures.py`; update Table 8 | — |
| **5. Check (≈1 d)** | Re-run the sub-agent review on the revised paper, and check every row of the review's claims table against the new text | — |

**Total: about 12–14 working days**, with about 4 of them dependent on A.

**Minimum viable revision** (if time forces a cut): P + A (without A6's
line-count comparison) + B1–B2 + C1–C2 + D1–D3 + E + F. That keeps every
*major* issue addressed except M4, which falls back to rewording, and drops
about 3 days.

---

## 5. Response map: every issue to its fix

| Review item | Addressed by | Paper change |
| --- | --- | --- |
| M1 no demonstrated benefit | A | New use-case section and figure; §4.3 claim now true |
| M2 value of HDT/COTTAS | B1, B3, B4 | QLever setup explained; whole-genome querying; guidance table; sizes against VCF |
| M3 retrieval framing | B1, B2 | Cold/warm, break-even, selective queries, tabix arm; abstract reworded |
| M4 no converter comparison | D4 | Measured comparison, or Table 1 reworded as a feature comparison |
| M5 cross-file identity | A2, A5 | SPDI linker; a cross-file query that works; VRS as future work |
| M6 validation scope | C1–C5 | Scope stated; core-profile score; one real-file validation; agreement counted properly |
| M7 RML extensibility | D3 | RML/emitter split reported; claim reframed; Table 1 mark qualified |
| M8 structure and length | E1–E5, D2 | Contributions list; re-sectioned; supplementary material; interpretive Discussion |
| §3 pt 2 alternatives | D1 | Related-work paragraph |
| §3 pt 5 companion paper | D2 | Scope sentence and status |
| §5 linking null results | A3 | Real rsID links (PGP) and resolution; SPDI for GIAB |
| §5 policy outside release | P, A4 | Released in v3.2.0; exercised on real genomes |
| m1–m11 | F | As listed |

---

## 6. Deliberately deferred (and what we say instead)

| Item | Why not now | What the paper says |
| --- | --- | --- |
| VRS computed identifiers | They need SeqRepo and the VRS normalizer, a heavy dependency, for a gain over SPDI that the use case does not need | SPDI now; VRS named as the next identifier layer |
| Full-hash digest aggregates (C5) | They would invalidate the campaign's Q11–Q13 results and require re-running 78 validations | The limitation stated precisely; flagged for the next release |
| Whole 2,504-sample cohort conversion | About 2 TB expanded; the condensed profile is feasible but days of VM time for a scale point already argued from Eq. 1 | The feasibility argument stays; the condensed cohort remains future work |
| Federation with live SPARQL endpoints (UniProt, Wikidata) | A single live service makes a result non-reproducible offline; SPDI and ClinVar already show integration | Future Work, with the linker tiers as the mechanism |
| Enforced memory caps | The harness cannot confirm Docker forwards them | The sweep moves to supplementary material, with its caveat |

---

## 7. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A6: the bcftools baseline is shorter than the RDF route | Medium | That is fine, and should be said. The argument is auditability, declarative consent and integration, not brevity. Report both honestly |
| A2: indel normalization edge cases break SPDI matching with ClinVar | Medium | Normalize both sides with the same `bcftools norm`; report the SNV and indel match rates separately; test in `plugin-tests/` |
| B3: HDT/COTTAS engines are impractical at 657M triples | Medium-high | Still a result: it bounds when the representations help. Timebox each engine; report what completed |
| D4: prior converters will not build | Medium | 1-day timebox each; fall back to rewording (already costed) |
| The release slips behind PR review | Low | The campaign stays on v3.1.0 regardless; only the new experiments need v3.2.0 |
| Scope creep in A | High | One use case, done completely (§3 A, scope guard) |
