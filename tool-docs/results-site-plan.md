# Plan: an interactive results site for vcf-rdfizer-testing

A GitHub Pages site that shows the benchmark evidence behind the VCF-RDFizer paper
as interactive charts, each with an explanation of how to read it and what it
means. It is modelled on `ecrum19/fed-survey-results`: same organization and
look, with an Actions deployment instead of a committed `docs/` folder.

## 1. What to take from fed-survey-results, and what to change

| Keep | Change |
| --- | --- |
| One static page, no framework: `index.html`, `assets/app.js`, `assets/styles.css`, `data/*.json` | Build and deploy with GitHub Actions, so generated data is never committed |
| Layout: a hero linking to the paper, then a one-paragraph quick start, then KPI tiles | Generate the data with Python (stdlib only), matching the rest of this repository, instead of Node |
| Each section is a collapsible panel: an intro line, then a grid of chart cards | Draw charts with Vega-Lite (see decision 1) instead of about 5,000 lines of hand-built SVG |
| An ⓘ help text on every chart, plus a metric-definitions dictionary | Add an "Interpretation" box per section: what the evidence shows, its caveats, and links to the paper section and the archive files |
| A focus modal that expands a chart; filter and section state in the URL, so shared links reopen the same view | Add a build-time test that pins key values to the paper's numbers, so the site and the paper cannot drift apart |
| "Never fabricate": missing values show as N/A; old or superseded runs are excluded unless a toggle adds them | |
| Monochrome palette, hero gradient, Source Sans 3 | Add one validated categorical palette for engines, profiles and requesters; `prefers-color-scheme` dark mode |

## 2. Repository layout

```
site/
  index.html                 page shell and sections (hand-written)
  assets/app.js              loads data/*.json, renders specs, URL state, modal
  assets/styles.css          adapted from fed-survey-results
  assets/favicon.svg
  specs/*.vl.json            one Vega-Lite spec per chart, data-bound by name
  content/interpretation.html  per-section interpretation text (hand-written)
scripts/build_site_data.py   benchmark-results -> site/data/*.json (stdlib only)
test/test_site_data.py       builds into a temp dir; checks values and schema
.github/workflows/pages.yml  build, test, deploy
```

`site/data/` is gitignored and generated in CI. `make -C site` builds and serves it locally (`python3 -m http.server`).

## 3. Data pipeline

`build_site_data.py` reads only the archive under `BioMedSem_2026/benchmark-results/`. It makes no network calls and writes small, normalized JSON files. Each file carries `{source: [paths], generated_at, harness_commit, tool_commit, image_digest}`, so every chart can name its evidence.

| Output | Built from | Feeds |
| --- | --- | --- |
| `campaign.json` | `summary.json` → `cells`, `experiments`, `provenance`, `integrity` (all 382 cells, tagged live, superseded, stalled, …) | KPI tiles, campaign explorer, provenance |
| `fidelity.json` | every `reports/validation/*/summary.json` and `comparison.json`; `08_robustness/*/mutation-score.json`; `vcf-bench-2/review-runs/` | Fidelity section |
| `scaling.json` | `04_scaling_records/tidy.csv`, `03_sample_representation/tidy.csv`, `01_storage_mode/tidy.csv`, plus the fits from `benchmarks/analysis/fit_scaling.py` | Conversion-cost section |
| `representations.json` | 05 corpus cells from `summary.json` and stage JSON | Representations chart |
| `retrieval.json` | `13_query_cost` `benchmark.csv` files, `14_regional_access/regional.csv`, `vcf-bench-3/.../retrieval.csv` | Retrieval section |
| `usecase.json` | `vcf-bench-{1,2}/use-case/*` (`comparison.json`, `grid.tsv`, `query/*/timing.json`, `bench.json`, `links.json`, `check.txt`) and `benchmarks/use_case/acmg/effort.json` | Use-case section |

Where it can, the script reuses the logic of `make_figures.py` and the `benchmarks/analysis/` helpers rather than reimplementing it, so the site and the paper's figures compute values the same way.

**Drift guard.** `test_site_data.py` checks a short list of values against the paper:
- 143 live cells, 96.16 h;
- 984 of 988 comparisons; 1,144 invariants; 152 decode checks;
- mutation detection 96, 96 and 113 of 113;
- arm carriers 7,211, 173,102 and 1,496;
- 662.4M triples;
- 634.6 s at 657M triples;
- regional values at 1 kb and 10 Mb.

These are the numbers the paper audit verified. A change in the archive that alters one of them fails CI before deploy.

## 4. Site sections (in order)

Each section has the same parts:
- an intro line;
- the chart cards, each with an ⓘ;
- an **Interpretation** box covering what it shows, what it does not, and how it connects to the other sections;
- a footer with the paper section, the archive paths, and the commit or image that produced the data.

1. **Hero, quick start and KPIs.**
   - The title links to the paper or preprint.
   - The data line gives the v3.1.0 image digest, the harness commit, and when the site was built.
   - KPI tiles: cells and hours; paired comparisons; faults detected (queries / core / full); use-case agreement (3 of 3 arms); largest graph queried; break-even point.
2. **Fidelity: is the graph faithful?**
   - A validation-evidence table, with each row linked to its reports.
   - Mutation detection by class: each of the 10 classes the queries miss, against queries only, the core profile, and the full profile.
   - An engine-agreement matrix.
   - The real-genome validation: Q1–Q13 status for NG131FQA1I, with the two oracle limitations explained (phase sets, canonical QUAL).
   - Interpretation: what representation equivalence does and does not establish, and why the default shape profile matters.
3. **The use case: linked, governed genomes.**
   - A carriers heatmap: arm × requester, with "rare in panel" as a toggle.
   - Linking coverage per linker and arm.
   - Cost by stage per arm (convert, link, view, check, index, query) as stacked bars on a log-time toggle.
   - The governance speed-up in its two steps (20–27 min → 131–165 s → 59–80 s).
   - Effort: lines written, and the lines each of four changes adds or removes, as diverging bars for the two routes.
   - Interpretation: where the RDF route pays, and where it does not.
4. **Conversion cost.**
   - The record ladder on log-log axes, with the fitted exponent and a metric toggle (triples / bytes / workspace / time / RSS).
   - The sample ladder: triples against bytes for the expanded and condensed profiles, with a measure toggle that makes the point that triple counts mislead.
   - Peak workspace by storage mode.
   - Corpus representations: size relative to N-Triples, and build time, per input.
   - Interpretation: memory is bounded and disk scales, and what each representation buys.
5. **Retrieval cost.**
   - SPARQL against cyvcf2 per question: a dot plot with the index time shown separately.
   - The engine comparison.
   - Linear cost to 657M triples.
   - The regional crossover by window size, with arms toggleable.
   - **A break-even calculator**: inputs default to the measured values (conversion, index, parser scan, mean query time) and update the break-even question count live, with a sentence saying which assumption drives it.
   - Interpretation: when the RDF route pays, and when a VCF tool is better (the paper's guidance table, made interactive).
6. **Campaign explorer.**
   - A filterable table of every cell: experiment, host, status, tree (live, superseded, stalled, …), wall time, command, tool commit and image digest.
   - Each cell links to its folder in the archive on GitHub.
   - A toggle includes non-live trees, mirroring "old results" in fed-survey-results.
7. **Notes and provenance.**
   - Host specs (three hosts, including vcf-bench-3's OS difference).
   - Image digests, and what is not archived (the generated RDF).
   - Known limits: simulated consents, single-sample participants, the oracle gaps.
   - How to rebuild the site.

## 5. Deployment (`.github/workflows/pages.yml`)

- **Triggers:**
  - push to `main` touching `site/**`, `scripts/build_site_data.py` or `BioMedSem_2026/benchmark-results/**`;
  - `workflow_dispatch`;
  - pull requests (build and test only, no deploy).
- **Build job:**
  - `actions/checkout`, then `actions/setup-python` (3.12);
  - `python scripts/build_site_data.py --out site/data`;
  - `python -m unittest test.test_site_data`;
  - `actions/configure-pages`, then `actions/upload-pages-artifact` with `path: site`.
- **Deploy job:**
  - runs on `main` only;
  - `needs: build`;
  - `environment: github-pages`;
  - `actions/deploy-pages`.
- **Settings:**
  - `permissions: {contents: read, pages: write, id-token: write}`;
  - `concurrency: {group: pages, cancel-in-progress: true}`.
- **One-time step for you:** repository Settings → Pages → Source: **GitHub Actions**.

Notes:
- Vega and Vega-Lite load from jsDelivr with pinned versions. Nothing else is fetched at runtime.
- Asset URLs get the build's commit as a cache-busting query string. This replaces fed-survey-results' `Date.now()` trick, so caching still works between deploys.

## 6. Phases

| Phase | Work | Estimate |
| --- | --- | --- |
| 1 | `build_site_data.py` and the drift-guard test, for all six data files | 1 d |
| 2 | Page shell, styles, URL state, modal, Pages workflow; deploy an empty skeleton to prove the pipeline | 0.5 d |
| 3 | Charts, section by section (fidelity, use case, cost, retrieval, explorer) | 2–3 d |
| 4 | Interpretation text, written from the paper's Results and Discussion and extended where the site has room the paper does not | 1 d |
| 5 | Accessibility (keyboard, contrast, table fallback for every chart), mobile layout, a link check | 0.5 d |

## 7. Decisions (2026-10-02)

1. Charting: **Vega-Lite** (pinned: vega 5.30.0, vega-lite 5.21.0, vega-embed 6.26.0).
2. Paper link: **none for now**.
3. Non-live data: **left out** (no toggle).
4. PDFs: **not served**.
5. Location: **this repository's Pages** (`ecrum19.github.io/vcf-rdfizer-testing/`).

## 8. As built (first version)

Differences from the plan above:
- **Specs** are built in `site/assets/app.js`, one entry per chart, rather than in `site/specs/*.vl.json`. Each spec needs the theme tokens and its rows at render time.
- **Interpretation text** is in `site/index.html`.
- **The drift test** is `scripts/test_build_site_data.py`, beside the builder; the repository has no top-level `test/`.
- **The paper's figure data** moved from `make_figures.py` into `paper-assets/figures/figure_data.py` (stdlib), which both import. The four figure PDFs regenerate byte-identically.
- **Check durations** in the use case are not shown: they were derived from file mtimes, which a git checkout does not keep.
- **One-time setup:** Settings → Pages → Source: **GitHub Actions**.
