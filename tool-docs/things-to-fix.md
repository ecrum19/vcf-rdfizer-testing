

The main issue remaining for me is the positioning. 

The paper is at its strongest when it is about **a verifiable semantic transformation of VCF data, with source-based checks, structural validation, fault injection, a realistic linked-data use case, and a clear assessment of the computational trade-offs**. That is already a solid contribution. It is not a product or a clinical workflow (yet), I would therefore *be careful not to oversell* the clinical reanalysis, PGx and governance aspects as if these are fully demonstrated applications. 

They are good motivating scenarios, but the *current experiments do not validate them end-to-end*. Related to this, I would also reconsider “governable” in the title. 

- [x] “Policy-aware” or similar would be better consistent with what we actually test. Governable had different connotations in the regulatory world. This is not to annoy potential bioinformatics/clinical workflow background expertise reviewers if we will get any.

The second important point is reproducibility and what exactly we mean by “verified”. 

- [x] We should make sure the exact evaluated code, configurations, versions and any (*dirty-tree*) changes are frozen and archived with a persistent identifier, and remove the remaining author queries.
- [x] (doing this currently and will include a zenodo DOI and a "versions used to assessment" statement)

- [ ] I would also write down more explicitly what the validation establishes: *agreement with source-derived queries, structural conformance (via SHACL correct ?), and preservation across serialization*.
- [ ] Please make it more clear HOW the linking demonstration was done (the appraoch, the queries, etc.) and where to find additional details for readers...
- [ ] The same sort of more clear definitions are needed for the methods of validation, query writing, and HOW we assessed if the "oracle" workflows using cy2vcf/bcftools were equivalent to the SPARQL queries we used? How do the "traditional" cy2vcf workflows look and are they defined somewhere?

This is strong validation, but it is not full value-by-value semantic equivalence, so being precise here will actually strengthen the paper rather than make it appear weak in my opinion. This is I usually appreciate when I review papers, where authors dont claim full validation but explicitly state what they mean by it.

- [x] Finally, I would suggest to look once more at the comparison with existing VCF-to-RDF tools. At the moment this is mainly documentation-based, this is certainly acceptable if we clearly present it that way, but
- [x] one direct comparison with the closest usable alternative on a common input would substantially strengthen the novelty argument. I am guessing we might judge this is too much to add now, then I would simply tone down any implication that we have experimentally demonstrated superiority over the other converters.
- [ ] The same applies to the large-scale performance results: where we only have single full-WGS runs, in that instance we might consider either replicate the key measurements or keep our conclusions qualitative. (clarify this)

The rest is mostly tightening: 
- [ ] clearly distinguish expected rejection of malformed input from unsupported valid VCF cases,
- [ ] make the independence of the RDF and conventional comparison workflows a bit more east to grasp, and
- [ ] cleaning up the remaining author queries/formatting issues etc.
- [ ] I also would not hide the scalability limitations — actually *I think the finding that RDF might not be the right solution for every workload is one of the more credible and useful aspects of the paper*.

So in short, I would avoid expanding the scope further as the paper already has a strong core; the main job remined in the coming few days now is to sharpen that core and make sure we claim exactly what we have demonstrated.

---

## Revision plan for the unchecked items — 11 October 2026

This plan covers the **eight unchecked items only**. The original reviewer text and checkbox states are preserved. Several requests are already partly addressed; the actions below tighten the existing passages rather than add another discussion of the same point. Locations refer to the current sources; section titles and LaTeX labels remain useful if line numbers move. These are proposed revisions, not completed reviewer responses.

### 1. Define exactly what “validated” or “verified” establishes

**Current state:** This is largely present, especially the explicit limits in the RQ1 results and discussion. The remaining improvement is a consistent, prominent definition; “preservation across serialization” must not overstate a triple-count check.

**Main locations:** [Conversion and validation: decoding, L170](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:170), followed by Q1–Q13 and SHACL (`subsec:conversion`); [RQ1 validation boundary, L271](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:271); [Validation discussion, L509](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:509); check the abstract's [Results summary, L47](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:47) for consistency.

**Supplementary locations:** [S4.1 validation specification, L459](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:459); [hash-bucket limitation, L504](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:504); [Table S6 / tab:validation-results, L521](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:521); [S4.3 oracle dependencies, L578](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:578).

**Plan:** Put a concise three-part definition at the end of the main validation-method paragraph, then use the same terminology in RQ1 and S4:

| Evidence | What the text may claim | What it must not imply |
| --- | --- | --- |
| Source-derived Q1–Q13 comparisons | Equality of the specified normalized summaries, including hash-bucket summaries | Exhaustive field-by-field or semantic equivalence; compensating hash-bucket changes can escape detection |
| SHACL | Conformance to the enabled shapes at the tested scale | Conformance to every VCF rule, biological correctness, or full-profile validation of complete WGS graphs |
| Native decoding/count checks | Successful decoding with the expected triple count | Equality of every decoded triple; distinguish this from the separate packaging round-trip/digest test |

In S4, add an explicit “does not establish” column or short paragraph beside the **existing** assessment table, not another overlapping table. Keep the 152 decode/count checks, the single packaging round trip, and cross-engine query agreement distinct. Say that the layers **together still do not prove exhaustive semantic equivalence**, rather than only that none does so alone. Retain the 113-fault result's small-graph and constructed-fault-set qualifications.

### 2. Show how the linking and policy demonstration was performed

**Current state:** The input scenarios and broad workflow are described, but readers must infer how the query, linksets, and requester views connect. S5 gives the concepts without an explicit route to the executable experiment.

**Main locations:** [Linking and policy extensions, L208](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:208) (`subsec:extensions`); [RQ2 Design, L286](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:286) (`subsec:results-workflow`), especially the workflow, scenario, and rare-query paragraphs; [pointer to supplementary methods, L307](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:307).

**Supplementary locations:** [S5.1 and Figure S2 / fig:linking-framework, L583](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:583); [S5.2 application methods, L626](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:626); [S5.4 stage definitions, L809](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:809).

**Plan:**

- Restructure the existing RQ2 design into a short sequence: **prepare VCFs → convert → add SPDI/gene links → evaluate policies and materialize requester views → query → compare answers**. Name the inputs at their point of use: participant VCFs, ClinVar, the reference/Ensembl resources, and the separate Scenario 2 frequency VCF. Preserve the distinction between gene-span slices (Scenarios 1–2) and complete participant VCFs (3–4).
- Explain what the application query asks: ALT-carrying calls with FILTER `PASS` or `.`, linked to a qualifying ClinVar classification in one of the 81 ACMG genes; the rare query also joins panel AF and requires AF < 0.01. The result unit is a participant–variant–gene match, not a diagnosis or clinical finding. Distinguish the ClinVar gene annotation used to select matches from the Ensembl overlap links used by gene-based policy selectors.
- State where policies enter: scenario specifications generate ODRL Turtle; the policy plug-in applies requester/purpose rules to write a permitted view **before** QLever runs the application query. The query joins that view to shared annotations/linksets. Policies are not an implicit feature of every SPARQL query or query engine.
- In S5.2, add one compact table mapping **stage → input → operation → output**, reusing Figure S2. Include a short annotated query excerpt or pseudocode for the SPDI join and AF extension. End with direct, revision-pinned links to the executable queries, scenario definitions, and driver; the main text should point specifically to this subsection and figure. Describe stage timing boundaries once in S5.4 and cross-reference them.

**Implementation to cite/check:** `benchmarks/17_use_case_acmg.sh` (driver); `benchmarks/use_case/acmg/derive.sh`, `run_query.py`, `carriers.rq`, `cohort/carriers.rq`, `cohort/rare.rq`; the four scenario JSON/policy pairs (`use_case.json`, `cohort/cohort.json`, `wgs/case.json`, `layered/case.json`, each with its `policy.ttl`). Use the README for navigation, but check details against these scripts and the evaluated run manifests; its older measurements must not become new current-campaign results.

### 3. Explain how the VCF oracle and SPARQL questions were paired

**Current state:** Q1–Q13 and normalization are documented, but the route from a question to two implementations and a comparison is not explicit. The source-validation oracle and the conventional linking baseline are different workflows and should be named separately. Use **cyvcf2** consistently (the reviewer wrote “cy2vcf”).

**Main locations:** [Conversion and validation: paired questions, L173](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:173); [RQ1 Design, L240](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:240) (`subsec:results-fidelity`); [RQ2 baseline distinction, L297](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:297); [validation discussion, L504](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:504).

**Supplementary locations:** [S4.1 and Table S5 / tab:queries, L459](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:459); [S4.1 comparison rules, L501](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:501); [S4.3 sensitivity and dependencies, L566](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:566); [S5.2 conventional application workflow, L626](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:626). Cross-reference the existing S2.2 query-adaptation rules where relevant, without reopening the checked converter-comparison task.

**Plan:**

- Add a short main-text methods explanation: define the question and eligible records/fields; compute the answer directly from VCF; implement the corresponding graph query for the selected representation; normalize both results to the same schema; compare keys and values, reporting missing, extra, or differing rows. Separate this from preflight integrity checks and SHACL, which do not have paired VCF answers.
- In S4.1, extend the existing 13-query specification with compact pointers to the **source computation and `.rq` implementation**, plus shared inclusion/missing-value rules. Explain that the oracle is Python computation over cyvcf2, bcftools and, where necessary, raw VCF text; it is not 13 independent bcftools commands. Q9–Q10 additionally need representation-dependent expected inventories, and the IRI-bound digest questions share selected representation expectations.
- Add one worked example: for Q4, `bcftools query -f '%FILTER\n'` supplies exact strings; Python counts by status and full string; SPARQL groups distinct records by those same fields. Both distinguish `PASS`, `.`, and failed codes, preserving combined codes. Normalize counts to integers, compare canonical keys and counts, and show where a mismatch would appear. This establishes agreement for the specified question on tested inputs, not a proof that the two programs are equivalent for every possible VCF.
- Identify evidence supporting the pairing: documented definitions, relevant unit/fixture tests, cross-engine results, and the 113 constructed faults. State their limits as in item 1; shared definitions can still be wrong in both routes. Explain applicability exclusions rather than counting inapplicable Q5/Q6 results as successes.
- Give readers a reproducible trail in S4: in the **vcf-rdfizer repository**, the evaluated validator's `parse_vcf`, census helpers, `normalize`, and `compare_rows` in `src/validation/validation_runner.py`, plus `src/validation/queries/common/`, `expanded/`, and `condensed/` (the worked example is `common/q04_filter_distribution.rq`). In the **testing repository**, point to one completed validation directory containing `parser.json`, `sparql.json`, `normalized/`, and `comparison.json`. Link the versions used by the relevant experiments, not only the latest source tree. Keep oracle correctness separate from the single-question versus batched timing protocol in S9.3/S9.4.
- In S5.2, describe the **application baseline** separately: bcftools harmonizes/annotates exact alleles, then Python selects carriers and applies simulated consent rules. Point to `baseline.sh`, `baseline_carriers.py`, and `compare.py`. Consolidate its shared/independent steps with item 6 rather than duplicating the explanation.

### 4. Clarify the evidence from single full-WGS runs

**Current state:** Replicate information exists but is spread across methods, captions, and the supplement. Repeated queries on one built graph are different from repeated end-to-end conversion runs.

**Main locations:** [RQ3 design, L370](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:370); [mapping-memory result, L398](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:398); [16.07-hour HG005 result, L405](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:405); [whole-HG005 retrieval, L436](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:436); [Scope and next steps, L537](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:537).

**Supplementary locations:** [S6.1 replicate counts, L884](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:884); [S6.3 inference limit, L1071](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1071); [S9.1 fits and Figure S5, L1219](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1219); [S9.2 complete corpus conversion, L1265](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1265); [Table S17 / tab:retrieval-scale, L1308](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1308); [Table S11 / tab:usecase-costs, L821](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:821).

**Plan:**

- **Recommended: clarify the existing evidence, without adding experiments.** Keep the observed numbers but label single conversion/setup/view measurements `n=1`; describe them as workload-specific observations, not estimates of general WGS performance or run-to-run variability.
- In S6/S9, provide a compact replicate ledger by **stage and configuration**: the record-count series has three replicates at each smaller HG005 size and one complete-VCF run; large-graph query repetitions reuse the built graph; linked-workflow query medians use three executions while those repetitions do not repeat conversion/link/view stages. Keep the separate corpus conversion configuration distinct. Verify counts for every setup stage, including index builds, from the timing records before assigning an `n`.
- Explain the sample sizes used in the scaling fit and what its confidence interval measures. It does not supply uncertainty for a single complete-VCF runtime. Qualify the bounded-memory observation as **mapping-stage memory over the tested inputs**.

**Suggested wording:** “The complete-HG005 conversion in this scaling series was measured once; its runtime and resource use are descriptive observations. Repeated queries on the resulting index measure query variability, not repeatability of the full conversion pipeline.”

**Alternative only if stronger performance claims are retained:** repeat the specific full conversion/setup stages under the same pinned configuration, then update their summaries and figures. Do not describe more query executions as replicated full-WGS conversions.

### 5. Separate malformed-input rejection from unsupported or untested valid cases

**Current state:** The difficult-input table separates truncated gzip from passing fixtures, but the distinction between input validity, conversion support, configuration refusal, resource guards, and validation coverage is still scattered.

**Main locations:** [RQ1 difficult-input result, L283](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:283); [Table 1 / tab:contract, L182](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:182); [scope of untested inputs, L537](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:537).

**Supplementary locations:** [S7 version/field coverage, L1108](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1108); [S7 and Table S15 / tab:difficult-inputs, L1126](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1126); [Table S12 status definitions, L948](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:948); [S10 unsupported option combinations, L1395](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1395); [S8 malformed-fixture history, L1200](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1200).

**Plan:**

- In the main result, explicitly separate **10 converted/validated fixtures** from **one diagnosed decompression rejection**. Neither rejection nor a skipped run is evidence of RDF fidelity.
- Give Table S15 an input-class/expected-behaviour distinction, with fixture validity checked against its declarations. Preserve the archive's `recorded` status for truncated gzip and explain separately why its observed rejection was appropriate; do not relabel it as a pre-asserted `refused` result.
- In S7/S10, distinguish: corrupt input; unsupported option combinations (such as single-HDT with COTTAS); resource-guarded/unexecuted inputs; and valid constructs whose representation or validation coverage is limited. Symbolic and breakend ALT values are retained by conversion but lack complete gene-link/policy coverage. Local-allele semantics are outside completed oracle coverage; that is not evidence that all such valid inputs are rejected.
- Keep the original malformed sites-only fixture and its correction in S8; present the corrected sites-only result in the current coverage table. Do not claim that one correctly rejected gzip establishes comprehensive malformed-VCF detection—the malformed sites-only header was accepted without a warning.

### 6. Explain which comparison steps are shared and which are independent

**Current state:** The main text and S5.2 already say that preprocessing and the case definition are shared. They do not yet make the three different checks easy to distinguish: source-comparison validation, the policy plug-in's release check, and the conventional application baseline.

**Main locations:** [RQ2 comparison design, L297](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:297); [release-check description, L221](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:221); [Scenario 2 limitation, L315](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:315).

**Supplementary locations:** [S5.1 policy checks, L620](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:620); [S5.2 comparison workflows, L632](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:632); [S4.3 source-oracle dependence, L578](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:578). Implementation evidence: `benchmarks/use_case/acmg/derive.sh`, `baseline.sh`, `baseline_carriers.py`, and `compare.py`.

**Plan:** Replace the short main independence statement with one concrete sentence and add a small **shared inputs → two implementations → comparison** table in S5.2:

| Shared | RDF implementation | Conventional implementation |
| --- | --- | --- |
| Derived/normalized VCF inputs, reference data, ACMG list, ClinVar release, case definition, simulated policy specification | RDF conversion; SPDI links; ODRL evaluation; SPARQL over requester views | bcftools exact allele annotation; separately implemented Python selection and consent rules; position/allele frequency lookup |

State that the baseline reads the derived VCF and case specification, not RDF outputs or the ODRL policy file. `compare.py` compares normalized **match-tuple sets** and separately compares **released-record counts**; count agreement is not record-set equality. Explain that the minimal graph built from VCF text bypasses conversion but is assessed with the same policy machinery; it is not the separate conventional baseline. Shared preprocessing and rule definitions can still produce shared blind spots. The policy plug-in's release check also shares the gene links, explaining why it missed the Scenario 2 over-release that the conventional baseline detected.

**Suggested main wording:** “The workflows share normalized input VCFs, reference resources, and the task and policy specifications, but implement matching and release separately: SPDI/ODRL/SPARQL in the RDF workflow and bcftools/Python in the conventional workflow. Agreement therefore tests the downstream implementations, not the shared assumptions.”

### 7. Resolve remaining author queries and formatting issues

**Current state:** There is **one active author query**, in main-text Funding. The supplement defines the query macro but has no active invocation. The main source also contains six editorial TODO comments, some beside prose that already appears to address them.

**Main locations:** [Funding query, L606](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:606); TODOs at [aims, L59](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:59), [ODRL motivation, L215](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:215), [discussion introduction, L442](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:442), [application wording, L456](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:456), [validation opening, L505](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:505), and [deployment wording, L528](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:528).

**Supplementary locations:** [unused author-query macro, L40](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:40); Figure `fig:usecase-overview` and Tables `tab:builds`, `tab:difficult-inputs`, and `tab:retrieval-scale` for the final layout pass.

**Plan:** Obtain the missing funding confirmation from B.B., R.T., and G.E.; resolve the visible query only after that. Review each TODO against its adjacent prose, removing comments whose requested change is already satisfied. Keep substantive edits tied to the unchecked reviewer items above. After the text changes, compile both documents together, verify cross-document references and figure numbering, and inspect floats, long tables, captions, and PDF bookmarks. The latest main build reports an overfull vertical box on page 4; inspect that page before adjusting spacing.

Preserve the existing editorial rule that historical defect/fix narratives belong in S8 (`sec:issues`). Remaining examples to relocate or replace with a short cross-reference are the main RQ1 defect paragraph, S4.2's initial consumer-oracle history, S5.1's selector-placement fix, and S5.4's pre-release timing/fix comparison. Keep current limitations visible where they qualify a current result.

**Completion check:** no active author queries, unresolved references, stale TODOs, or material clipping in either final PDF. The funding answer is an author-supplied dependency, not text to guess. The archive/DOI item is already checked and is outside this plan.

### 8. Keep scalability limits visible and tied to specific workloads

**Current state:** The abstract, RQ3, deployment discussion, and conclusion already state that RDF is not preferable for every workload. Retain that balance and make the limits explicit rather than adding a new limitations essay.

**Main locations:** [abstract workload result, L50](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:50); [RQ2 setup and view costs, L350](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:350); [RQ3 optional-artifact cost, L405](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:405); [one-pass versus repeated questions, L409](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:409); [large-graph engine failures, L438](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:438); [deployment discussion, L517](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:517); [conclusion, L554](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/current_short.tex:554).

**Supplementary locations:** [S5.4 stage costs / Table S11, L809](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:809); [S7 unconverted full cohort, L1120](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1120); [S9.1 projected workspace, L1245](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1245); [S9.3 incomplete native-engine workloads, L1304](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1304); [S9.4 amortization, L1379](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1379); [S10 memory-limit qualification, L1405](/Users/eliascrum/PhD_Things/vcf-rdfizer-testing/BioMedSem_2026/paper/supplementary.tex:1405).

**Plan:** Use the existing discussion to connect three observed limits: storage expansion, expensive preparation/release views, and workloads where direct VCF access wins. Retain the batch comparison (12.4 s VCF versus 17.1 s QLever), the single-run 16.07-hour artifact-heavy conversion, the 55–70-minute Scenario 4 view writing, and the incomplete native-engine workloads, with the stage and replication qualifications from item 4. Keep the approximately 11-question crossover explicitly tied to repeated full-file scans; it does not apply to one-pass batching or every indexed regional workload. State that the full 2,504-sample cohort was not converted, deeper SHACL profiles were tested only on small graphs, and longitudinal update costs were not measured. No new performance experiment is needed if conclusions stay within those bounds.

### Suggested order of work

1. Clarify the two experimental workflows and their executable definitions (items 2, 3, 6).
2. Align validation claims and input/outcome categories with those definitions (items 1, 5).
3. Label replication by stage and tighten performance conclusions (items 4, 8).
4. Resolve funding/editorial notes, compile both manuscripts, and inspect their references and layout (item 7).

Keep all eight reviewer boxes unchecked until the corresponding manuscript revisions and checks are complete; this document records the plan only.
