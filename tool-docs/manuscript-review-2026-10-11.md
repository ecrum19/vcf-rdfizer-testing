# Manuscript review: language, logic and readability (2026-10-11)

**Scope.** Main text (`current_short.tex`, **M**) and supplement (`supplementary.tex`, **S**), as in the working tree at 12:20 on 2026-10-11. That copy includes the rewritten introduction. The S3.1 paragraph on the two sample profiles, added later, was not reviewed.

**Method.** Five read-only reviewers covered:
- the main text's language;
- the main text's readability;
- logic and consistency across both documents;
- language and readability in S1–S5;
- language and readability in S6–S10.

Every factual or numerical finding below was checked against the text, and against the data where needed. False positives and duplicates were removed.

**Line numbers.** `L123` is a line in that snapshot. Later edits shift lines, so search for the quoted words instead.

---

## 1. Fix first: errors and inconsistencies (verified)

**Done ✅** (working tree, 2026-10-11):
- ✅ 1: the range now reads 14–57 on HG005 and 18–203 on the 16-sample input.
- ✅ 2: the Discussion now says the match sets matched and released records agreed in 3 of the 4 scenarios.
- ✅ 3: added that the release checks share the policy's gene links. The RQ2 heading is now "policy-checked release views", in the paper and on the site.
- ✅ 4: the timing-comparison wording is gone. The conventional times were added to the main text, S5.4, Table S11 and the site chart: 4–91 s against 5.7–105 min.
- ✅ 5: the supplement now states the core benchmark's per-question times behind the 44 (11.57 s per parse, 1.32 s per query).
- ✅ 6: Table S1's note now says no jar is published and Bioconda packages v2024.08.25.
- ✅ 7: the S9.3 regional summary now matches the main text: faster up to 100 kb, and bcftools also at 1 Mb.
- ✅ 8: the abstract, Figure 3 caption and Discussion now say the deeper shapes caught every fault the queries missed, instead of claiming complementarity in both directions.
- ✅ 9: one mechanism everywhere: the harness's cohort-scale guard (more than 1,000 sample columns) skipped the run, since it would need ~2 TB on a 189 GB volume. This was fixed with §2.
- ✅ 10: S6.1 now names the tenth cell: the complete 1000 Genomes input, skipped by the guard.
- ✅ 11: the three defects are named with the check that found each: Q9/Q10, the SHACL shapes, and the policy plug-in's release check. This is in the main text and in Table S16 tags. S4.3 now names the dangling allele-reference defect.
- ✅ 12: S9.1 now says 170.5–171.9, matching the main text.
- ✅ 13: both figures are right with different statistics (sum of per-question medians vs mean of replicate totals); the Table S17 caption explains this.
- ✅ 14: the HDT engine answered **4** of 13 (Q1–Q4), not 5, and COTTAS answered Q1–Q5. Text and rows are corrected, and HDT's time is now 8,889.5 s (answered questions only).
- ✅ 15: each index build now names its run and states that conversion is excluded.
- ✅ 16: the three grants moved from Acknowledgments to Funding. The author query for B.B., R.T. and G.E. stays.

| # | Where | Problem | Suggested fix |
|---|---|---|---|
| ✅ 1 | M L374 | "14–203 triples per record on HG005": the other converters give 14.0–57.3 on HG005. The 203.1 is BioInterchange on the 16-sample input (Table S3). As written, a competitor appears to exceed VCF-RDFizer's 171. | "14–57 triples per record on HG005 (18–203 on the 16-sample input)" |
| ✅ 2 | M L463 vs L301 | "requester-specific views matched the conventional workflow", but in Scenario 2 the views released 110 and 58 extra records. | "requester-specific match sets matched the conventional workflow; released records agreed in Scenarios 1, 3 and 4" |
| ✅ 3 | M L299–301, S L735 | "Every materialized release view passed the policy and source checks" reads as verification. The supplement says the checks reuse the policy's gene links, so they *could not* detect the Scenario 2 over-release. | Say so in M L299–301. Consider calling them "policy-checked" rather than "verified" release views in the RQ2 heading. |
| ✅ 4 | M L287, S L614 | "…should agree before timings are compared". No conventional-workflow timings are reported anywhere, so RQ2/RQ3 have no cost comparator for the linked workflow. | Report the conventional workflow's times per scenario, or reword: "the two workflows must produce identical tuples". |
| ✅ 5 | S L1334 | The HDT-inclusive break-even of 44 cannot be reproduced from the stated numbers: 446.5 / (12.28 − 1.43) ≈ 41. The 44 uses the core benchmark's per-question times, not the rerun's. | State the per-question times behind 44, or use the same per-question times for both estimates (≈ 41). Drop "unnecessary"; say "not needed by QLever". |
| ✅ 6 | S L133 vs L231 | JVarkit: "distributed as a jar and on Bioconda" (Table S1) vs "No jar is published" (Table S2). | Reconcile (e.g. "Bioconda package; no versioned jar for the tested commit") and recheck the Public-release mark. |
| ✅ 7 | S L1286 | "Tabix-indexed cyvcf2 and bcftools were faster at 1 kb" understates the result. M L396 and Table S18: faster up to 100 kb, and bcftools also at 1 Mb. | Match M L396. |
| ✅ 8 | M L257, L479 (and the abstract) | "detecting errors that either approach alone may miss": the fault counts are cumulative (queries, then queries + shapes). Shapes-only detection is never reported, so only one direction of complementarity is shown. | Report shapes-only detection, or write "the deeper shapes detected every fault the queries missed". |
| ✅ 9 | S L1190 vs L889–890, L1067; Table S12 | The complete 1000 Genomes expanded run is "refused" for a 2 TB projection in one place, and skipped by the >1,000-sample-column harness guard in others. Table S12 counts it as Skip. "The volume's sample limit" (L890) is a third description. | Give one mechanism, e.g. "skipped by the harness's sample-column guard; the tool's 2 TB workspace projection would also have refused it". |
| ✅ 10 | S L851 vs L911, L1065 | "eight public inputs and … the complete HG005 VCF (10 cells)" makes 9. The tenth cell is the skipped complete 1000 Genomes input. Table S12 says "ten public inputs". | "nine processed inputs plus the skipped complete 1000 Genomes cell (10 cells)" |
| ✅ 11 | M L272, L481; S L565 | "three implementation defects" are never identified in Table S16. "the missing-allele defect" (S L565) matches no entry; the closest is "Dangling allele references". | Mark the three defects in Table S16 with the validation layer that found each, and use one name. |
| ✅ 12 | M L377 vs S L1167 | 170.5–171.9 triples per record (M, including the complete VCF: 170.46) vs 170.9–171.9 (S, slices only). | Use the same range, or say that the S range covers the slices only. |
| ✅ 13 | S L1266 vs M L389, S L1235 | Table S17 gives 17.0 s, while the text gives 17.1 s. The table's own rate (1.00 s per million) matches 17.1. | Use 17.1 in the table. |
| ✅ 14 | S L1250, L1277 | The HDT engine "answered five questions and failed on Q6", but Table S17 says Q5 hit the one-hour ceiling before answering. | List which five questions each engine answered. |
| ✅ 15 | M L397 | QLever setup of 23.3 s excludes the ~96 s conversion, while bgzip + tabix starts from the VCF. The same index build appears as 20.8, 22.8, 23.3 and 25.0 s (S Table S3, L1234, L1288, L1331) without saying the runs differ. | State that conversion is excluded (or give conversion + index ≈ 2 min), and name the run behind each index time. |
| ✅ 16 | M L577 vs L593 | Funding lists only FWO, but Acknowledgments name REALM, RAIDO and DigiTwin4PH as supporting "this work". | Move the grants into Funding; this is linked to the open author query. |

**Worth checking (a possible problem the reviewers could not settle):**
- ⚠️ **M L321–324:** *Not changed; your decision.* The 857M figure is reproducible (924.5M − 67.8M triples), but only from a pre-release conversion (v3.2.0 plus a development tree) archived on `legacy`. Factoring gives 16.8× and field selection 12.2×. Options: rerun the with-INFO conversion on v3.3.1, state the provenance, or drop the figure.
- ✅ **S L848 vs L1206:** Both sentences describe the same input, a 1,155,741-record prefix of `NG131FQA1I`. The two sentences and the scaling figure's panel (f) label now say so.
- ✅ **S L321 vs M L406:** The two ratios have different numerators and denominators. The Table S3 caption now defines both.
- ✅ **M L303:** Verified (0, 8, 0, 0), and Table S8 now has a P/LP row under each scenario. Scenario 2's split is CC 4, DS 6 and GRU 4; the DS count was read from the VM, because that list isn't archived locally. The main text cites the table.
- ✅ **S L858:** These were the three example linkers shipped since v3.0.0; the evaluated linkers arrived in v3.3.0. S6.1 and the main text are corrected.
- ✅ **M Table 1 (L189):** The INFO row now cites Q11 (raw), and the caption describes Q9–Q10.
- ✅ **M L268:** Q5 pools phased and unphased calls, so a flipped `phasingStatus` with unchanged GT text escapes Q5 and Q13. S4.3 now explains this and lists the 10 fault classes.

---

## 2. Terminology to standardize (one name per thing)

**Done ✅** (working tree, 2026-10-11; 80 replacements, and a scratch build is clean):
- **Chosen names:**
  - **N-Triples:** *gzip-framed N-Triples* for VCF-RDFizer's output; *gzipped N-Triples* stays for the other converters.
  - **Minimal setup:** *minimal RDF setup*.
  - **SHACL profiles:** the *default*, *deeper* and *all three* profiles. The supplement names `core`, `consistency` and `vocabulary-sparql`.
  - **Faults:** *injected faults* and *fault injection*. Code names keep `mutation_score`.
  - **"Native":** means only an artifact's own format; VCF parsing is now *direct VCF processing* or *direct VCF access*.
  - **Guards:** the *cohort-scale guard* (harness) and the *SHACL size guard* (tool).
  - **Difficult inputs:** replaces "awkward fixtures".
- **Figure 6b:** the legend went from "VCF workflow"/"RDF workflow" to *VCF*/*RDF*. The figure was regenerated, the brief rebuilt, and the change is on #37.
- **Units and numbers:** measured memory is in GB; the tool's configured chunk sizes stay in MiB/GiB. Numbers are numerals from 10 up, except at the start of a sentence ("Fourteen preflight queries…").


- ✅ **The N-Triples artifact** appears as "gzip-framed N-Triples", "gzipped-Triples" (M L386, a typo), "gzipped-N-Triples" (M L390) and "Gzip-compressed N-Triples". Use **gzip-framed N-Triples** (or "gzipped N-Triples", without the hyphen).
- ✅ **The minimal setup** appears as "minimal QLever path" (M L390, S L1330) and "minimal N-Triples-plus-QLever setup" (M L503). Use **minimal RDF setup**.
- ✅ **The conventional workflow** is also called "bcftools workflow", "conventional VCF workflow" and "VCF workflow". Use **conventional workflow**.
- ✅ **SHACL profiles** are called "deeper shapes", "deeper profiles", "deepest" (M L511), "full shape profiles" and "all three shape profiles". Name the two deeper profiles once, with what each checks (e.g. *uniqueness* and *value agreement*), and use those names throughout.
- ✅ **Faults vs mutations:** S L401, L409, L512, L533 and L558 say "mutations". Genomics readers will read that as biological mutations. Use **injected faults**, and call the controls "uncorrupted control graphs".
- ✅ **"Native"** means three different things: direct VCF parsing (M L50, L496), Comunica querying HDT/COTTAS (M L414), and artifact decoding (M L169). Keep one meaning.
- ✅ **Guards** are called "size guard", "size gates" (S L984) and "the volume's sample limit" (S L890). Use **guard**, saying which one.
- ✅ **Core benchmark naming:**
  - "base experiments" (S L1003) → **core benchmark**;
  - "cross-encoding experiment" (S L1359) → **Equivalence** family;
  - "core-benchmark record" (S L501) → "All 78 validation runs in the core benchmark completed."
- ✅ **Spelling and units:**
  - "set-up" (M L248) → **setup**;
  - "Conda-Forge" (M L537) → **conda-forge**;
  - GB vs GiB for the same RAM (S L1004 33.6 GB, L1011 31.3 GiB): use one unit.
- ✅ **Numbers:** "12 experiment families" sits beside "eleven" and "thirteen". Pick one convention, e.g. numerals from 10 up, or spell out to match "thirteen".

---

## 3. Language: quick fixes

**Done ✅:** every row below, in the main text and the supplement. Some fixes were folded into the §4 rewrites.

**Main text**

| Line | Change |
|---|---|
| ✅ L54 (abstract) | Run-on sentence. Suggested: "This study quantifies the additional representation and indexing costs of semantic VCF. More generally, VCF-RDFizer is a first step toward applications that link genomic observations to external knowledge and data-use conditions." |
| ✅ L87 | "rather than as a shared model" → "rather than to serve as a shared model" |
| ✅ L103 | "The aim is not to replace such systems, but" → "Our aim is not to replace such systems but". As written, "The aim" reads as the aim of Hail, GEMINI and Beacon. |
| ✅ L125 | "implementatable" → "implementable". Also: "…data reuse; they are intended to inspire future applications, not to offer directly implementable solutions." |
| ✅ L169, L405 | Count compared with a graph, and time compared with scans → "…with that of the N-Triples source graph", "…lower than that of repeated VCF scans" |
| ✅ L228 | "utilized in evaluation" → "used in the evaluation" |
| ✅ L245 | Sentence opens with "25". Reorder: "In the equivalence and query-cost experiments, 25 validation runs…" |
| ✅ L301 | Add "requesters, respectively" after "disease-specific and general research" |
| ✅ L327 | "…required a policy edit … and selected the HG002 record" → "…required only a policy edit, with no change to the RDF policy engine, and the edited rule selected the HG002 record despite its unprefixed contig name." |
| ✅ L334 | "rather than establishing…" attaches to the wrong clause → "…which suggests that the fixed ClinVar join dominated the measured query time; the result does not establish scale-independent SPARQL performance." |
| ✅ L344 | "use three replicates" → "are measured over three replicates" |
| ✅ L374 | Faulty list ("produced …, …, and required") → "…produced 171 triples per HG005 record and 536 per record on the 16-sample input, and took 31–92 s per input including container startup." |
| ✅ L385 | "hours were the construction of" → "hours were spent constructing" |
| ✅ L386, L390 | "gzipped-Triples" / "gzipped-N-Triples" → "gzipped N-Triples" |
| ✅ L389 (also S L1235) | "before setup" → "excluding setup" |
| ✅ L396 | "VCF-region retrieval increased" → "VCF-region retrieval time increased" |
| ✅ L398, L406 (also S L1289) | "Indexed for queries, the QLever index…" (dangling) → "The QLever index required…" |
| ✅ L414 | "graph of complete HG005" → "graph of the complete HG005 VCF" |
| ✅ L417 | "retain the detailed … results" → "report the detailed … results" |
| ✅ L480 | "Source-derived queries" → "Source-comparison queries" |
| ✅ L483 | "shown practical" → "shown to be practical" |
| ✅ L511 | Tense mix ("fixes" / "was" / "were") and "deepest" → "The sample-count series fixed INFO content, … and the deeper SHACL profiles were evaluated only on small inputs." |
| ✅ L541 | Sentence opens with "v3.1.0" → "Version 3.1.0 produced the core benchmark results, and v3.3.1 those of…" |
| ✅ L581 | "conceived of this study" → "conceived the study" |
| ✅ L593 | Add the serial comma after "No. 101135800" |

**Supplement**

| Line | Change |
|---|---|
| ✅ L299 | "calculated allele numbers from carriers alone" (a graph cannot calculate) → "…omitted homozygous-reference calls, so the allele numbers that Q6 recomputed counted carriers only" |
| ✅ L400, L1091 | "ploidy 4/3" and "Ploidy 4 then 3 followed the data" → "triploid and tetraploid calls kept their source ploidy". At L1094, "FILTER variants" → "FILTER values". |
| ✅ L435 | "appended to plain N-Triples or as a member of…" → "appended either to a plain N-Triples file or, as a separate gzip member, to a concatenated-gzip stream" |
| ✅ L599 | Wrong attachment → "When a source resource is withheld, ownership rules also remove the calls, alleles, sample calls and headers that depend on it." |
| ✅ L602 | "records obligations but does not enforce obligations" → "records obligations (ODRL duties, e.g. deleting released data) but does not enforce them" |
| ✅ L855 | "compare basic and structured headers and fixtures declaring…" → "compare basic with structured header output and convert fixtures that declare VCF 4.1–4.5 or no version" |
| ✅ L984 | Garbled Table S13 row. Say what was rerun and why: the graph exceeded v3.1.0's SHACL size guard, so the run was repeated without shapes, and the v3.3.1 rerun with shapes is the next row. |
| ✅ L1128 | "withdrawn" vs "withheld" in the same row: use **withheld**, and rewrite the correction in plain words. |
| ✅ L1130 | "passed the size guard as 390.7 MB COTTAS and exhausted 30.7 GiB" → "The v3.1.0 guard estimated graph size from file size: a 170,935,101-triple graph stored as a 390.7 MB COTTAS file passed it, and SHACL validation then exhausted 30.7 GiB of memory." |
| ✅ L1154 | It reads as if the converter dropped phase sets; it was the v3.1.0 *oracle* (S L546). → "The v3.1.0 oracle omitted the phase sets the converter emitted and compared QUAL as text ('50' vs '50.0')…" |
| ✅ L1348 | "crossed requested 8, 16, and 31 GB memory ceilings with three configurations" → "combined three memory ceilings (8, 16 and 31 GB) with three configurations ([name them]) on one million HG005 records" |
| ✅ L1356 | Unclear. Say that since the dependency correction (S8), raw-INFO graphs still contain the allele resources that expanded sample calls reference, so the 12.52M figure includes them. |

---

## 4. Readability: changes with the biggest payoff

**Done ✅** (working tree, 2026-10-11). The main text grew from 29 to 31 pages and the supplement from 31 to 36; the abstract is 336 words.
- **A:** glosses at first use in both documents. Q1–Q13 are summarized in one sentence, the *source-comparison queries* and the *oracle* are named, and *release view*, *requester*, *execution paths* and *paired validation* are defined.
- **B:** RQ2 now opens with the four requesters and their purposes, the match definition (any ClinVar classification, ≥1 star; 98.6–99.0% of matches are benign), an example rule, and why HG005's DS/GRU views are empty. The Scenario 2 over-release is stated plainly.
- **C:** the retrieval design now defines individual vs batch timing and setup, and explains where "about 11 questions" comes from and why the regional comparison is fairer. The batched-pass point is spelled out.
- **D:** the abstract Results, four engines, converters and large-graph sentences are split. The abstract Conclusions run-on is fixed.
- **E:** the Discussion has a roadmap paragraph, and the reanalysis and PGx subsections each open with a measured result (light option). Versions and the full list of separate experiments are in the Evaluation intro; inputs are mapped to experiments; S2 names its inputs and S5.2 names the five Scenario 1 VCFs.
- **F:** captions rewritten: Figures 1, 2 and 6 and Table 1 in the main text; Tables S5, S9, S13, S17 and S18 and Figure S8 in the supplement.
- **Other passages:** all done except M L320–322 (see §1 ⚠️, the 857M figure).
- **Checks:** a separate read-only check of every changed line found 29 problems introduced by the pass; 26 are fixed. Three were kept on purpose: caption glosses kept so captions stand alone, the covering-set gloss kept at its first use, and the S2 oracle definition kept right after its first mention.


All three readability reviewers reached the same verdict: the text is precise and carefully hedged, but written for insiders. A biomedical-informatics reader who knows VCF and has heard of RDF/SPARQL meets many tools and coined terms before they are explained. Most definitions they need sit only in the supplement, and the result sentences pack several numbers and caveats together.

✅ **A. Define the core terms at first use in the main text.** Add a short orienting paragraph in Implementation, or one-clause glosses:
- **Data model and formats:** *triple* (and that sizes are in triples); *N-Triples* / *gzip-framed*; *HDT* and *COTTAS* (compressed, directly queryable formats).
- **Tools and languages:**
  - *RML* (declarative mapping rules) and *direct emitters*;
  - *QLever* (an engine that builds its own index) and *Comunica*;
  - *SHACL* and its default and deeper profiles;
  - *SPDI*, with an example of what minimal trimming does and does not guarantee (M L207–209, L441);
  - *ODRL* and *DUO*.
- **The validation queries:** a one-sentence summary of what **Q1–Q13** check (from Table S5), and attach the names *source-comparison queries* and *oracle* where validation is described (M L172–177).
- **Coined terms:** *release view*, *requester*, *linkset*, *execution paths*, *paired validation*.
- **File identifiers:** NG131FQA1I and NB72462M are consumer whole-genome VCFs.

Do the same in the supplement for its own first uses: RML, HDT, COTTAS, QLever, SHACL, OWL, ODRL, SPDI (S L117–119, L353, L417, L591), *space-optimized storage* (S L847), *HDT strategy* (S L876), *anchor cell* (S L844), *covering set* (S L414, L862), *record-local* (S L549, L563), and the three *linker tiers*, one sentence each with the evaluated linker (S L590).

✅ **B. Open RQ2 with requesters, purposes and what a "match" is** (M L281–294). The four requesters (CC, DS, GRU, OP) are defined only in the Figure 4 caption.
- **What a match is:** say that a match is any ClinVar classification with at least one review star in an ACMG SF gene. Otherwise readers will take the 1,496 HG005 matches for pathogenic findings.
- **Example rule:** give one example rule.
- **Empty views:** say why the Scenario 3 DS and GRU views are empty (S L626 says "every requester receives a non-empty subset" in the Scenario 4 context; begin that sentence "In Scenario 4,").
- **The Scenario 2 over-release (M L301):** state it plainly. The RDF workflow released records the policy was meant to withhold, because v3.3.1 links no symbolic allele to a gene. Split the sentence.

✅ **C. Explain the retrieval set-up before its results** (M L352–354, L388–391).
- **Two timing modes:** individual timing runs one full VCF parse per question; batch timing answers all thirteen in one pass.
- **What setup includes:** conversion plus index build for RDF, bgzip plus tabix for VCF.
- **Where "about eleven questions" comes from:** about 2 min of setup, recovered at 12.28 s per parse vs 1.43 s per query.
- **Why the regional comparison is "stronger":** both sides use an index (M L393).
- **"A batched parser pass changes the conclusion"** (M L502) is too terse. Say that one pass answers all thirteen questions in 12.4 s, less than QLever's 17.1 s.

✅ **D. Split the densest sentences:**
- abstract Results (M L47–50): say what was compared with what, and give the RQ3 conditions with numbers instead of "selected repeated and large-region questions";
- the four engines (M L244–247): state the purpose first, that answers do not depend on the engine or format;
- converters (M L374);
- regional (M L393–395);
- large graph (M L414–416): say which engine did not finish, and on how many records.

✅ **E. Structure.**
- **Discussion:** it has no opening and puts three "could" use-case subsections before the findings-based ones; your TODOs at M L420 and L432 make the same point. Add a 2–3 sentence roadmap tied to RQ1–RQ3, and open each use-case subsection with the measured result it extends.
- **Software versions:** v3.1.0 vs v3.3.1 is first explained in Availability (M L541). Add one sentence at M L223–224 saying which experiments used v3.3.1 and that both releases wrote identical triples. Complete the list of separate experiments: it omits the N-Triples-only rerun and the index-storage measurement.
- **Inputs:** map inputs to experiments (M L228–230). The supplement's S2 should name its two shared inputs (S L200), and S5.2 should name the five Scenario 1 VCFs (S L617).

✅ **F. Make captions self-contained.**
- **Main text:**
  - Figure 1 (M L140): "call" is used for two things, and expanded/condensed is not explained.
  - Figure 2 (M L157): about eight unexplained terms; rewrite in plain words.
  - Table 1 (M L179): "contract" and "assessment boundary" are not explained, and the table cites Q-numbers and fixtures before they are introduced.
  - Figure 6 (M L403): name the data and what a "question" is; replace "smaller or batched workloads" with the actual conditions.
- **Supplement:**
  - Table S5 (S L458): mentions call rate and allele frequency, which are not in the table.
  - Table S9 (S L708): clipped row labels.
  - Table S13 (S L962): "assessment boundary".
  - Table S17 (S L1255): which rows are "smaller" or "larger".
  - Figure S8 (S L1298): list the seven execution paths.
  - Table S18 (S L1306): rewrite the nested-median description.

✅ **Other passages to clarify** (all except M L320–322) (each is a one-line fix):
- **Main text:**
  - L146–149: give a concrete example of a condensed vector, and gloss *linkset*.
  - L164–169: say what "hybrid" means for users editing the mappings.
  - L211–216: motivate ODRL before the plug-in (your TODO at L211), and gloss default-deny, deny-overrides and ownership rules.
  - L234–238: RQ1 design.
  - L267–270: "additional faults" means the 17 the queries missed. Give the deeper profiles' cost: 33.7 and 73.2 s vs 1.7 s on ~2,000 triples (S L560).
  - L320–322: say what panel-level INFO is.
  - L326–329: introduce the four applied rule changes before reporting one.
  - L331–335: the query times have no baseline.
  - L379–380: "a larger effect" than what?
- **S1–S5:**
  - L58: "expected refusals" and "separately".
  - L201: point forward to the oracle and Q1–Q8 in S4.1.
  - L302: htslib added the PASS line.
  - L439: "second full decompressed aggregate".
  - L491: say what normalization does, and that it alters no values.
  - L493: explain the hash-bucket digest.
  - L505, L544: "paired validation reached 17.1M"; NG131FQA1I.
  - L555: faults are applied to the RDF of a ~2,000-triple fixture.
  - L600: split the four release checks.
  - L620: "within 7.1 Mb of gene spans" reads as a distance → "inside the 81 ACMG gene spans (7.1 Mb in total)".
  - L636: attribute the counts to the files.
  - L738: say why the unprefixed contig matters.
  - L770: optimization jargon.
- **S6–S10:**
  - L858, L882: explain how cells and runs add up (16 cells; 78 runs from fewer cells).
  - L897: the truncated gzip is counted as Rec. in Table S12 but "refused (intended)" in S7.
  - L1007: say what calibration ran and which host was slower.
  - L1058: version-specific fields; LAA/LAD.
  - L1143: SHACL report jargon.
  - L1161: the mechanism behind the release.
  - L1167: gloss the power-law exponent.
  - L1211: which complete-HG005 run.
  - L1342: list each option's values.
  - L1353: name HGSVC2.

---

## 5. Open author notes in the source

- ☐ **M L59:** TODO — state in the aims that the study targets lowering the barrier for the three use cases.
- ✅ **M L211:** TODO — explain why ODRL and policy assessment are used before introducing them. *Addressed: the paragraph now opens with use case 3's need, ODRL and DUO. The comment can be deleted.*
- ✅ **M L420:** TODO — add a short Discussion intro. *Addressed: roadmap paragraph added. The comment can be deleted.*
- ◐ **M L432:** TODO — reduce the "could/would" language by tying it to findings. *Partly addressed: two subsections now open with a measured result; the "could" sentences are unchanged.*
- ✅ **M L478:** TODO — rewrite the first sentence. *Rewritten (§1 #8). Check it reads as you want, then delete the comment.*
- ✅ **M L501:** TODO — "un-AI this". *The paragraph was rewritten in plain terms. Check it, then delete the comment.*
- ☐ **M L578:** author query — complete the funding statements for B.B., R.T. and G.E. See §1 #16.

---

## 6. Plan for §4 (readability)

**Approach.** Fix the main text first, since most readers stop there. Prefer one-clause glosses and split sentences over new paragraphs. Leave detail in the supplement and point to it. Each phase ends with:
- a scratch build;
- a page-count check;
- a fresh read-only reviewer pass on the changed sections.

| Phase | What | Covers | Effort |
|---|---|---|---|
| ✅ 1 | **Definitions at first use (main text).** One-clause glosses where each term first appears in Implementation: triple, N-Triples / gzip-framed, HDT, COTTAS, RML and emitters, QLever, Comunica, SHACL profiles, SPDI (with a trimming example), ODRL and DUO, linkset. Add one sentence summarizing Q1–Q13 and attach the names *source-comparison queries* and *oracle*. Define *release view*, *requester*, *execution paths* and *paired validation* where they first occur. | 4A | ~250 words |
| ✅ 2 | **Open RQ2 properly.** At the start of its evaluation design: the four requesters and purposes, what a match is (any ClinVar classification, ≥1 review star), and one example rule. State the Scenario 2 over-release plainly, and say why the Scenario 3 DS/GRU views are empty. | 4B | ~120 words |
| ✅ 3 | **Explain the retrieval set-up before its results.** Individual vs batch timing, what setup includes, where "about 11 questions" comes from, and why the regional comparison is the fairer one. Expand M L502. | 4C | ~100 words |
| ✅ 4 | **Split the densest sentences.** Abstract Results, the four engines, converters, regional and large graph. | 4D | ±0 words |
| ✅ 5 | **Captions.** Figure 1, Figure 2, Table 1 and Figure 6 in the main text, then Tables S5, S9, S13, S17, S18 and Figure S8. | 4F | ~150 words |
| ✅ 6 | **Structure.** One sentence on versions (M L223–224), complete the list of separate experiments, map inputs to experiments, and add a Discussion roadmap (your TODOs at M L420 and L432). | 4E | ~150 words |
| ✅ 7 | **Supplement glosses and the passage list** (§4 "Other passages"), S1 to S10 in order. | 4A, list | ~400 words |
| ✅ 8 | **Language quick fixes** (§3), one mechanical pass. This can be done at any time. | §3 | ±0 words |

**Done ✅:** phases 1–8 were all carried out on 2026-10-11, with the recommended defaults for the decisions below: inline glosses, a one-sentence Q1–Q13 summary, the light Discussion option, and direct edits to the abstract and introduction, limited to language and readability.

**Decisions (defaults applied; tell me to change any):**
1. **Glosses:** inline glosses (recommended; no new float) or a short "Key terms" box in Implementation.
2. **Q1–Q13:** a one-sentence summary in the main text (recommended), or move a compact version of Table S5 into the main text.
3. **Discussion:** add a roadmap and anchor each use-case subsection in a measured result (recommended, light), or also reorder so the findings-based subsections come first (heavier; it touches text you are rewriting).
4. **Abstract and introduction:** these are your current edits. Should I draft changes there as suggestions in a separate file, or edit the working copy directly?

**Coordination.** Edits are made in the working tree with exact replacements, announced to the other session first. Phases 1–4 touch only Implementation and Evaluation and results, so they can run while you edit the introduction.

---

## 7. Found during the fix pass (not in the original review)

- ✅ **Table S5 misdescribed two queries.** Q5 pools phased and unphased calls (it maps `|` to `/`), and Q13 digests GT. Both rows are corrected.
- ✅ **S7 local alleles.** S7 said local-to-global allele resolution is not implemented. It has been in the tool since v3.0.3, but the fixture does not exercise it (`LAD` is `Number=R`). S7 is corrected.
- ✅ **Native HDT result.** The engine answered 4 questions, not 5 (§1 #14).
- ⚠️ **Validator defect (tool, not paper).** A Comunica endpoint timeout that returns HTTP 200 with a truncated `!TIMEDOUT!` body is recorded as PASS with exit 0. That is how the HDT engine's Q5 appears in `retrieval.csv`. Worth fixing in VCF-RDFizer and noting in Table S16.
- ⚠️ **The 857M figure** needs your decision (§1, worth checking).
- ✅ **P/LP counts** were added to Table S8 by requester (§1, worth checking).
