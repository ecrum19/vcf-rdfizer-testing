// VCF-RDFizer results site. Loads the JSON built by scripts/build_site_data.py
// and renders every chart with Vega-Lite. Nothing here computes a reported
// number from scratch: values come from the data files, and the build's tests
// pin them to the paper. Prose quotes them through {placeholders} filled from
// facts.json, so no number is written into this file or the page.
"use strict";

const DATASETS = ["campaign", "fidelity", "scaling", "retrieval", "usecase", "facts"];
const REPO = "https://github.com/ecrum19/vcf-rdfizer-testing";
const D = {};

// --------------------------------------------------------------- theme
// The categorical palette is the validated reference instance (light and dark
// steps of the same hues): all checks pass; aqua and yellow sit under 3:1 on the
// light surface, so every chart has a legend or direct labels and a data table.
const PALETTE = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500"],
};
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

function tokens() {
  const dark = darkQuery.matches;
  return {
    series: PALETTE[dark ? "dark" : "light"],
    context: dark ? "#6f6e69" : "#a8a69f",
    text: dark ? "#f2f2f0" : "#191919",
    muted: dark ? "#c3c2b7" : "#545454",
    grid: dark ? "#2c2c2a" : "#e1e0d9",
    axis: dark ? "#383835" : "#c3c2b7",
    surface: dark ? "#1a1a19" : "#fcfcfb",
    seq: dark ? ["#253447", "#86b6ef"] : ["#e8f0fb", "#1c5cab"],
    onSeqStrong: dark ? "#0d0d0d" : "#ffffff",
  };
}

function vlConfig(t) {
  return {
    background: null,
    font: '"Source Sans 3", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    view: { stroke: null },
    axis: {
      labelColor: t.muted, titleColor: t.muted, gridColor: t.grid, domainColor: t.axis,
      tickColor: t.axis, labelFontSize: 11, titleFontSize: 11, titleFontWeight: 600,
    },
    legend: { labelColor: t.muted, titleColor: t.muted, labelFontSize: 11, titleFontSize: 11, orient: "top" },
    header: { labelColor: t.muted, titleColor: t.muted },
    text: { color: t.text, fontSize: 11 },
    bar: { cornerRadiusEnd: 4 },
    line: { strokeWidth: 2 },
    point: { size: 80, filled: true, stroke: t.surface, strokeWidth: 2 },
    range: { category: t.series },
  };
}

// --------------------------------------------------------------- formatting
const num = (x, digits = 0) =>
  x == null || Number.isNaN(x) ? "N/A" : Number(x).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const secs = (s) => {
  if (s == null) return "N/A";
  if (s < 1) return `${num(s * 1000, 0)} ms`;
  if (s < 120) return `${num(s, s < 10 ? 2 : 1)} s`;
  if (s < 7200) return `${num(s / 60, 1)} min`;
  return `${num(s / 3600, 2)} h`;
};
const millions = (x) => `${num(x / 1e6, x < 1e6 ? 2 : x < 1e8 ? 1 : 0)}M`;
const fill = (text) => text.replace(/\{(\w+)\}/g, (_, key) => D.facts[key] ?? "N/A");
const pretty = (id) => id.replace(/^q(\d+)_/, "Q$1 ").replace(/_/g, " ");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function table(columns, rows) {
  const head = columns.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr>${columns.map((c) => {
    const v = c.html ? c.html(r) : esc(c.format ? c.format(r[c.key], r) : r[c.key] ?? "N/A");
    return `<td class="${c.num ? "num" : ""}">${v}</td>`;
  }).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

// --------------------------------------------------------------- charts
// Each chart: title, help (the ⓘ), optional caption, spec(t) and rows() for its table.
const CHARTS = {
  mutationScores: {
    title: "Injected faults detected, by validation layer",
    help: "{faults} targeted corruptions (wrong allele, coordinate, FILTER token, metadata, blank nodes, flipped phasing, corrupted sample index) were injected into a graph. Each bar counts how many the validation layer detected: the comparison queries alone, with the default SHACL profile, and with all three profiles.",
    rows: () => {
      const s = D.fidelity.mutation.scores;
      return [
        { layer: "Queries only", detected: s.queries.detected, total: s.queries.total },
        { layer: "+ default shapes (core)", detected: s.core.detected, total: s.core.total },
        { layer: "+ all three shape profiles", detected: s.full.detected, total: s.full.total },
      ];
    },
    columns: [{ key: "layer", label: "Layer" }, { key: "detected", label: "Detected", num: true }, { key: "total", label: "Injected", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 120,
        encoding: {
          y: { field: "layer", type: "nominal", sort: null, title: null },
          x: { field: "detected", type: "quantitative", scale: { domain: [0, rows[0].total] }, title: "Faults detected" },
          tooltip: [{ field: "layer", title: "Layer" }, { field: "detected", title: "Detected" }, { field: "total", title: "Injected" }],
        },
        layer: [
          { mark: { type: "bar", color: t.series[0], height: 18 } },
          { mark: { type: "text", align: "right", dx: -6, color: t.onSeqStrong, fontWeight: 600 },
            encoding: { text: { value: { expr: "datum.detected + ' / ' + datum.total" } } } },
        ],
      };
    },
  },

  mutationClasses: {
    title: "The {faultClasses} fault classes the queries cannot see",
    help: "Each row is a mutation class the comparison queries miss entirely. Cells show how many of its mutations each shape profile catches. The default profile checks cardinality and datatypes, so it catches none; the full set adds value agreement and uniqueness.",
    caption: "The full profile set self-joins the graph, so {campaignVersion} runs it only on request and only on small inputs.",
    rows: () => D.fidelity.mutation.missedByQueries.flatMap((m) => [
      { class: m.class.replace(/_/g, " "), profile: "Default (core)", caught: m.core, mutations: m.mutations },
      { class: m.class.replace(/_/g, " "), profile: "All three profiles", caught: m.full, mutations: m.mutations },
    ]),
    columns: [{ key: "class", label: "Mutation class" }, { key: "profile", label: "Shapes" }, { key: "caught", label: "Caught", num: true }, { key: "mutations", label: "Mutations", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 300,
        transform: [{ calculate: "datum.caught / datum.mutations", as: "share" }],
        encoding: {
          y: { field: "class", type: "nominal", title: null },
          x: { field: "profile", type: "nominal", title: null, sort: ["Default (core)", "All three profiles"], axis: { orient: "top", labelAngle: 0 } },
          tooltip: [{ field: "class", title: "Class" }, { field: "profile", title: "Shapes" }, { field: "caught", title: "Caught" }, { field: "mutations", title: "Mutations" }],
        },
        layer: [
          { mark: { type: "rect", stroke: t.surface, strokeWidth: 2, cornerRadius: 3 },
            encoding: { color: { field: "share", type: "quantitative", scale: { domain: [0, 1], range: t.seq }, legend: null } } },
          { mark: { type: "text", fontWeight: 600 },
            encoding: {
              text: { value: { expr: "datum.caught + ' / ' + datum.mutations" } },
              color: { condition: { test: "datum.share >= 0.5", value: t.onSeqStrong }, value: t.text },
            } },
        ],
      };
    },
  },

  carriers: {
    title: "Carriers each requester may see, by arm",
    help: "Cells count carriers of a ClinVar-classified variant in an {geneList} gene that each requester may see under the simulated consents, and the share of the unrestricted answer. The RDF route and the bcftools route returned identical lists in every cell.",
    rows: () => {
      const order = ["unrestricted", "clinical", "cardio", "biobank"];
      const labels = { arm1: fill("Arm 1: {arm1Genomes} genomes"), arm2: fill("Arm 2: {cohort}-person cohort"), arm2rare: "Arm 2: rare in panel", arm3: "Arm 3: whole genome" };
      const out = [];
      for (const [arm, data] of Object.entries(D.usecase.arms)) {
        const sets = [[arm, data.carriers]];
        if (Object.keys(data.rare || {}).length) sets.push([`${arm}rare`, data.rare]);
        for (const [key, carriers] of sets) {
          for (const r of order) {
            const c = carriers[r];
            if (!c) continue;
            out.push({ arm: labels[key], requester: r, carriers: c.rdf, baseline: c.baseline, agree: c.agree ? "identical" : "DIFFER",
                       share: carriers.unrestricted.rdf ? c.rdf / carriers.unrestricted.rdf : null });
          }
        }
      }
      return out;
    },
    columns: [{ key: "arm", label: "Arm" }, { key: "requester", label: "Requester" }, { key: "carriers", label: "RDF route", num: true, format: (v) => num(v) },
      { key: "baseline", label: "bcftools route", num: true, format: (v) => num(v) }, { key: "agree", label: "Lists" }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 190,
        encoding: {
          y: { field: "arm", type: "nominal", sort: null, title: null },
          x: { field: "requester", type: "nominal", sort: ["unrestricted", "clinical", "cardio", "biobank"], title: null, axis: { orient: "top", labelAngle: 0 } },
          tooltip: [{ field: "arm", title: "Arm" }, { field: "requester", title: "Requester" }, { field: "carriers", title: "RDF route", format: "," },
            { field: "baseline", title: "bcftools route", format: "," }, { field: "agree", title: "Lists" }, { field: "share", title: "Share of unrestricted", format: ".0%" }],
        },
        layer: [
          { mark: { type: "rect", stroke: t.surface, strokeWidth: 2, cornerRadius: 3 },
            encoding: { color: { field: "share", type: "quantitative", scale: { domain: [0, 1], range: t.seq }, legend: { title: "Share of unrestricted", format: ".0%" } } } },
          { mark: { type: "text", fontWeight: 600 },
            encoding: {
              text: { value: { expr: "format(datum.carriers, ',') + (datum.requester == 'unrestricted' ? '' : '  (' + format(datum.share, '.0%') + ')')" } },
              color: { condition: { test: "datum.share >= 0.5", value: t.onSeqStrong }, value: t.text },
            } },
        ],
      };
    },
  },

  participants: {
    title: "Arm 1: carriers per participant and requester",
    help: "How the per-file consents shape each answer: {consents}. The cohort rule keeps the {restrictedGenes} cancer genes for clinical care.",
    rows: () => {
      const g = D.usecase.arms.arm1.grid;
      return Object.entries(g.rows).flatMap(([requester, counts]) =>
        counts.map((c, i) => ({ requester, participant: g.participants[i], carriers: c })));
    },
    columns: [{ key: "participant", label: "Participant" }, { key: "requester", label: "Requester" }, { key: "carriers", label: "Carriers", num: true, format: (v) => num(v) }],
    spec(t, rows) {
      const max = Math.max(...rows.map((r) => r.carriers));
      return {
        data: { values: rows }, height: 190,
        encoding: {
          y: { field: "requester", type: "nominal", sort: ["unrestricted", "clinical", "cardio", "biobank"], title: null },
          x: { field: "participant", type: "nominal", sort: null, title: null, axis: { orient: "top", labelAngle: 0 } },
          tooltip: [{ field: "participant" }, { field: "requester" }, { field: "carriers", format: "," }],
        },
        layer: [
          { mark: { type: "rect", stroke: t.surface, strokeWidth: 2, cornerRadius: 3 },
            encoding: { color: { field: "carriers", type: "quantitative", scale: { domain: [0, max], range: t.seq }, legend: null } } },
          { mark: { type: "text", fontWeight: 600 },
            encoding: { text: { field: "carriers", format: "," },
                        color: { condition: { test: `datum.carriers >= ${max / 2}`, value: t.onSeqStrong }, value: t.text } } },
        ],
      };
    },
  },

  effort: {
    title: "Lines each change adds and removes",
    help: "Four realistic changes were applied to both routes as real edits, then both were re-run on a fixture and had to release the same records. Bars right of zero are lines added, left of zero lines removed, summed over the files each route touches.",
    caption: "Rules written in the first place, data excluded: RDF route {rdfRules}; bcftools route {baselineRules}.",
    rows: () => D.usecase.effort.scenarios.flatMap((s) => ["rdf", "baseline"].flatMap((route) => {
      const files = Object.entries(s.edits[route]);
      const added = files.reduce((a, [, e]) => a + e.added, 0);
      const removed = files.reduce((a, [, e]) => a + e.removed, 0);
      const touched = files.filter(([, e]) => e.added || e.removed).map(([f, e]) => `${f} +${e.added}/−${e.removed}`).join("; ");
      const label = route === "rdf" ? "RDF route" : "bcftools route";
      return [{ scenario: s.summary, route: label, kind: "added", lines: added, files: touched },
              { scenario: s.summary, route: label, kind: "removed", lines: -removed, files: touched }];
    })),
    columns: [{ key: "scenario", label: "Change" }, { key: "route", label: "Route" }, { key: "kind", label: "" }, { key: "lines", label: "Lines", num: true, format: (v) => num(Math.abs(v)) }, { key: "files", label: "Files" }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 260,
        encoding: {
          y: { field: "scenario", type: "nominal", sort: null, title: null, axis: { labelLimit: 320 } },
          yOffset: { field: "route", sort: ["RDF route", "bcftools route"] },
          x: { field: "lines", type: "quantitative", title: "Lines removed ← → lines added" },
          color: { field: "route", type: "nominal", scale: { domain: ["RDF route", "bcftools route"], range: [t.series[0], t.series[1]] }, title: null },
          tooltip: [{ field: "scenario", title: "Change" }, { field: "route" }, { field: "kind" }, { field: "files", title: "Files" }],
        },
        layer: [
          { mark: { type: "bar", height: { band: 0.8 } } },
          { mark: { type: "text", fontSize: 10, align: "left", dx: 4, color: t.muted }, transform: [{ filter: "datum.lines > 0" }],
            encoding: { text: { value: { expr: "'+' + datum.lines" } } } },
          { mark: { type: "text", fontSize: 10, align: "right", dx: -4, color: t.muted }, transform: [{ filter: "datum.lines < 0" }],
            encoding: { text: { value: { expr: "'−' + abs(datum.lines)" } } } },
        ],
      };
    },
  },

  usecaseCost: {
    title: "Cost of the RDF route by stage and arm",
    help: "Convert and link are totals over each arm's files (genomes, ClinVar and, in arm 2, the panel). View is the slowest requester's release view. Index and query are for the unrestricted requester: the index build, then the median of {queryReplicates} cold runs of the carriers query.",
    rows: () => {
      const labels = { arm1: "Arm 1", arm2: "Arm 2", arm3: "Arm 3" };
      const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
      return Object.entries(D.usecase.arms).flatMap(([arm, data]) => {
        const q = data.queries.unrestricted;
        return [
          ["convert", data.stageSeconds.convert], ["link", data.stageSeconds.link],
          ["release view", Math.max(...Object.values(data.stageSeconds.view))],
          ["index build", q ? q.setup : null], ["carriers query", q ? median(q.replicates.carriers) : null],
        ].map(([stage, seconds]) => ({ arm: labels[arm], stage, seconds, label: secs(seconds) }));
      });
    },
    columns: [{ key: "arm", label: "Arm" }, { key: "stage", label: "Stage" }, { key: "seconds", label: "Time", num: true, format: (v) => secs(v) }],
    spec(t, rows) {
      return {
        data: { values: rows.filter((r) => r.seconds) }, height: 300,
        encoding: {
          y: { field: "stage", type: "nominal", sort: ["convert", "link", "release view", "index build", "carriers query"], title: null },
          yOffset: { field: "arm" },
          x: { field: "seconds", type: "quantitative", scale: { type: "log", zero: false }, title: "Seconds (log scale)",
               axis: { values: [10, 100, 1000, 10000], format: "," } },
          color: { field: "arm", type: "nominal", title: null, scale: { range: t.series.slice(0, 3) } },
          tooltip: [{ field: "arm" }, { field: "stage" }, { field: "label", title: "Time" }],
        },
        layer: [
          { mark: "point" },
          { mark: { type: "text", align: "left", dx: 9, fontSize: 10 }, encoding: { text: { field: "label" }, color: { value: t.muted } } },
        ],
      };
    },
  },

  records: {
    title: "Growth with records: memory stays flat",
    help: "Each line is one measure of conversion on the HG005 ladder ({ladder} records, {ladderReplicates} replicates each, then the whole {wholeRecords}-record file), relative to its value on the smallest input. Medians of the replicates.",
    rows: () => {
      const r = D.scaling.records;
      const measures = { triples: "Triples", wall: "Wall time", disk: "Peak disk", rss: "Peak memory (mapping)" };
      return r.rungs.flatMap((n, i) => Object.entries(measures).map(([k, label]) => ({
        records: n, measure: label, growth: r.median[k][i] / r.median[k][0],
        value: k === "wall" ? secs(r.median[k][i]) : k === "triples" ? millions(r.median[k][i])
          : k === "disk" ? `${num(r.median[k][i] / 1e9, 2)} GB` : `${num(r.median[k][i] * 1024 / 1e9, 2)} GB`,
      })));
    },
    columns: [{ key: "records", label: "Records", num: true, format: (v) => num(v) }, { key: "measure", label: "Measure" }, { key: "value", label: "Value", num: true }, { key: "growth", label: "× smallest", num: true, format: (v) => num(v, 1) }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 280,
        encoding: {
          x: { field: "records", type: "quantitative", scale: { type: "log" }, title: "Records (HG005)",
               axis: { values: D.scaling.records.rungs, labelExpr: `datum.value == ${D.scaling.records.wholeFileRecords} ? '${D.facts.wholeRecords} (whole)' : format(datum.value, '~s')` } },
          y: { field: "growth", type: "quantitative", scale: { type: "log" }, title: "Growth relative to the smallest input" },
          color: { field: "measure", type: "nominal", title: null, sort: ["Triples", "Wall time", "Peak disk", "Peak memory (mapping)"] },
          tooltip: [{ field: "measure" }, { field: "records", format: "," }, { field: "value" }, { field: "growth", title: "× smallest", format: ".1f" }],
        },
        layer: [{ mark: "line" }, { mark: "point" }],
      };
    },
  },

  samples: {
    title: "Two sample profiles: triples against bytes",
    help: "The same {sampleRecords} 1000 Genomes records re-emitted against {samplesMin} to {samplesMax} sample columns. Switch the measure: the condensed profile's triples barely grow, but its stored bytes do, because per-sample values move into vector literals rather than disappearing.",
    rows: () => {
      const s = D.scaling.samples;
      const measures = { triples: "Triples", nt: "gzip N-Triples (bytes)", hdt: "HDT (bytes)" };
      const out = [];
      for (const [profile, label] of [["expanded", "Expanded"], ["condensed", "Condensed"]]) {
        s[profile].x.forEach((n, i) => {
          for (const [k, m] of Object.entries(measures)) out.push({ samples: n, profile: label, measure: m, value: s[profile][k][i] });
        });
      }
      s.condensed.x.forEach((n, i) => {
        for (const m of ["gzip N-Triples (bytes)", "HDT (bytes)"]) out.push({ samples: n, profile: "Input VCF", measure: m, value: s.condensed.vcf[i] });
      });
      return out;
    },
    columns: [{ key: "measure", label: "Measure" }, { key: "profile", label: "Series" }, { key: "samples", label: "Samples", num: true, format: (v) => num(v) }, { key: "value", label: "Value", num: true, format: (v) => num(v) }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 280,
        params: [{ name: "measure", value: "Triples",
          bind: { input: "select", options: ["Triples", "gzip N-Triples (bytes)", "HDT (bytes)"], name: "Measure " } }],
        transform: [{ filter: "datum.measure == measure" }],
        encoding: {
          x: { field: "samples", type: "quantitative", scale: { type: "log" }, title: fill("Sample columns ({sampleRecords} records)"), axis: { values: D.scaling.samples.expanded.x } },
          y: { field: "value", type: "quantitative", scale: { type: "log" }, title: null, axis: { format: "~s" } },
          color: { field: "profile", type: "nominal", title: null,
                   scale: { domain: ["Expanded", "Condensed", "Input VCF"], range: [t.series[1], t.series[0], t.context] } },
          tooltip: [{ field: "profile" }, { field: "samples", format: "," }, { field: "measure" }, { field: "value", format: ",.0f" }],
        },
        layer: [{ mark: "line" }, { mark: "point" }],
      };
    },
  },

  storage: {
    title: "Peak disk by storage mode",
    help: "Paired runs of the plain and space-optimized storage modes on the same inputs. Both produce identical triples and final artifacts; space-optimized mode only lowers the temporary disk peak, at {spaceTimeCost} more time.",
    rows: () => {
      const names = { slice: "HG005 slice", larger: "test-larger" };
      return Object.entries(D.scaling.storage).flatMap(([key, modes]) => Object.entries(modes).map(([mode, m]) => ({
        input: `${names[key] || key} (${millions(m.triples)} triples)`, mode: mode === "plain" ? "Plain" : "Space-optimized",
        gb: m.peakBytes / 1e9, time: secs(m.wallSeconds),
      })));
    },
    columns: [{ key: "input", label: "Input" }, { key: "mode", label: "Mode" }, { key: "gb", label: "Peak disk (GB)", num: true, format: (v) => num(v, 2) }, { key: "time", label: "Wall time", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 130,
        encoding: {
          y: { field: "input", type: "nominal", title: null },
          x: { field: "gb", type: "quantitative", scale: { type: "log" }, title: "Peak disk workspace (GB, log)", axis: { values: [0.1, 1, 10, 100], format: "~g" } },
          tooltip: [{ field: "input" }, { field: "mode" }, { field: "gb", title: "Peak GB", format: ".2f" }, { field: "time", title: "Wall time" }],
        },
        layer: [
          { mark: { type: "rule", color: t.grid, strokeWidth: 3 }, encoding: { detail: { field: "input" } } },
          { mark: "point", encoding: { color: { field: "mode", type: "nominal", title: null, scale: { domain: ["Plain", "Space-optimized"], range: [t.context, t.series[0]] } } } },
        ],
      };
    },
  },

  representations: {
    title: "Artifact size relative to the gzip N-Triples",
    help: "For each corpus input (first {corpusRecords} records; HG005 whole), the size of the HDT and COTTAS artifacts built from the same graph, divided by the stored gzip N-Triples. Hover for build times.",
    rows: () => D.scaling.corpus.flatMap((r) => [
      { input: `${r.name} · ${millions(r.triples)}`, artifact: "COTTAS", ratio: r.cottas / r.nt, build: secs(r.cottas_s) },
      { input: `${r.name} · ${millions(r.triples)}`, artifact: "HDT", ratio: r.hdt / r.nt, build: secs(r.hdt_s) },
    ]),
    columns: [{ key: "input", label: "Input" }, { key: "artifact", label: "Artifact" }, { key: "ratio", label: "× N-Triples", num: true, format: (v) => num(v, 2) }, { key: "build", label: "Build time", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 260,
        encoding: {
          y: { field: "input", type: "nominal", sort: null, title: null },
          x: { field: "ratio", type: "quantitative", scale: { domain: [0, 2] }, title: "Size ÷ stored gzip N-Triples" },
          tooltip: [{ field: "input" }, { field: "artifact" }, { field: "ratio", title: "× N-Triples", format: ".2f" }, { field: "build", title: "Build time" }],
        },
        layer: [
          { mark: { type: "rule", color: t.axis, strokeDash: [4, 3] }, encoding: { x: { datum: 1 }, y: null } },
          { mark: { type: "rule", color: t.grid, strokeWidth: 3 }, encoding: { detail: { field: "input" } } },
          { mark: "point", encoding: { color: { field: "artifact", type: "nominal", title: null, scale: { domain: ["COTTAS", "HDT"], range: [t.series[0], t.series[1]] } } } },
        ],
      };
    },
  },

  perQuestion: {
    title: "Per question: SPARQL (QLever) against a VCF scan (cyvcf2)",
    help: "Each question answered on the {sliceTriples}-triple HG005 graph ({sliceRecords} records), mean of {engineReplicates} replicates. cyvcf2 must scan the VCF whichever question it is. QLever's times exclude its one-time {qleverIndex} index build; the last row compares the whole {questions}-question batch, where one parser pass answers everything.",
    rows: () => {
      const r = D.retrieval;
      const rows = r.perQuestion.map((q) => ({ question: q.label, sparql: q.sparql, parser: q.parser, speedup: q.parser / q.sparql }));
      rows.push({ question: `All ${r.perQuestion.length}, one batch`, sparql: r.batch.sparql, parser: r.batch.parser, speedup: r.batch.parser / r.batch.sparql });
      return rows;
    },
    columns: [{ key: "question", label: "Question" }, { key: "sparql", label: "QLever", num: true, format: (v) => secs(v) }, { key: "parser", label: "cyvcf2", num: true, format: (v) => secs(v) },
      { key: "speedup", label: "Speed-up", num: true, format: (v) => `${num(v, v >= 10 ? 0 : 1)}×` }],
    spec(t, rows) {
      const long = rows.flatMap((r) => [{ ...r, side: "SPARQL (QLever)", seconds: r.sparql }, { ...r, side: "VCF scan (cyvcf2)", seconds: r.parser }]);
      return {
        data: { values: long }, height: 360,
        encoding: {
          y: { field: "question", type: "nominal", sort: null, title: null },
          x: { field: "seconds", type: "quantitative", scale: { type: "log" }, title: "Seconds (log scale)",
               axis: { values: [0.001, 0.01, 0.1, 1, 10, 100], format: "~g" } },
          tooltip: [{ field: "question" }, { field: "sparql", title: "QLever (s)", format: ".3f" }, { field: "parser", title: "cyvcf2 (s)", format: ".2f" }, { field: "speedup", title: "Speed-up", format: ",.1f" }],
        },
        layer: [
          { mark: { type: "rule", color: t.grid, strokeWidth: 3 }, encoding: { detail: { field: "question" } } },
          { mark: "point", encoding: { color: { field: "side", type: "nominal", title: null, scale: { domain: ["SPARQL (QLever)", "VCF scan (cyvcf2)"], range: [t.series[0], t.context] } } } },
        ],
      };
    },
  },

  engines: {
    title: "The engine sets the cost",
    help: "The {questions} questions on the {fixtureTriples}-triple graph under each SPARQL engine: mean of {engineRuns} runs ({engineArtifacts} artifacts in each of {engineReplicates} replicates), with the range. All engines agreed in every run.",
    rows: () => Object.entries(D.retrieval.engines).map(([engine, e]) => ({
      engine: { qlever: "QLever", comunica: "Comunica", cottas: "COTTAS engine", hdt: "HDT engine" }[engine] || engine,
      mean: e.mean, min: e.min, max: e.max, runs: e.runs,
    })).sort((a, b) => a.mean - b.mean),
    columns: [{ key: "engine", label: "Engine" }, { key: "mean", label: "Mean", num: true, format: (v) => secs(v) }, { key: "min", label: "Min", num: true, format: (v) => secs(v) }, { key: "max", label: "Max", num: true, format: (v) => secs(v) }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 150,
        encoding: {
          y: { field: "engine", type: "nominal", sort: null, title: null },
          tooltip: [{ field: "engine" }, { field: "mean", format: ".1f", title: "Mean (s)" }, { field: "min", format: ".1f" }, { field: "max", format: ".1f" }],
        },
        layer: [
          { mark: { type: "bar", color: t.series[0], height: 16 }, encoding: { x: { field: "mean", type: "quantitative", title: `${D.facts.qRange} total (s)` } } },
          { mark: { type: "rule", color: t.muted }, encoding: { x: { field: "min", type: "quantitative" }, x2: { field: "max" } } },
          { mark: { type: "text", align: "left", dx: 6, color: t.muted },
            encoding: { x: { field: "max", type: "quantitative" }, text: { value: { expr: "format(datum.mean, '.1f') + ' s'" } } } },
        ],
      };
    },
  },

  costBySize: {
    title: "QLever cost per million triples, to {maxTriples} triples",
    help: "The {questions} questions' QLever time (sum of per-question medians) divided by the graph's size in millions of triples. The data table lists the host each graph ran on.",
    rows: () => D.retrieval.costBySize.map((r) => ({
      graph: { small: "Fixture", large: "HG005 slice", whole: "Whole genome" }[r.graph] || r.graph.replace(/^r(\d+)$/, (_, n) => `${num(Number(n) / 1e6)}M records`),
      triples: r.triples, seconds: r.seconds, perMillion: r.perMillion, host: r.host })),
    columns: [{ key: "graph", label: "Graph" }, { key: "triples", label: "Triples", num: true, format: (v) => num(v) }, { key: "seconds", label: "All questions", num: true, format: (v) => secs(v) },
      { key: "perMillion", label: "s per million", num: true, format: (v) => num(v, 2) }, { key: "host", label: "Host" }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 220,
        encoding: {
          x: { field: "triples", type: "quantitative", scale: { type: "log", domain: [5e5, 1.5e9] }, title: "Triples (log scale)", axis: { values: [1e6, 1e7, 1e8, 1e9], format: "~s" } },
          y: { field: "perMillion", type: "quantitative", scale: { zero: true }, title: "Seconds per million triples" },
          tooltip: [{ field: "graph" }, { field: "triples", format: "," }, { field: "seconds", format: ".1f", title: "Seconds" }, { field: "perMillion", format: ".2f", title: "s per million" }, { field: "host" }],
        },
        layer: [
          { mark: { type: "line", color: t.series[0] } },
          { mark: { type: "point", color: t.series[0] } },
          { mark: { type: "text", dy: -14, color: t.muted }, encoding: { text: { field: "graph" } } },
        ],
      };
    },
  },

  regional: {
    title: "Region-restricted questions: SPARQL against indexed VCF access",
    help: "Median over {regionalQuestions} region questions of each question's median across {regionalWindows} windows ({regionalScanWindows} for the unindexed scan) and {regionalReplicates} replicates. Every arm answers the same POS-based window, and across both graphs {regionalExecutions} executions produced {regionalFailures} failures and {regionalDisagreements} disagreements. Switch the graph to compare the smaller fixture.",
    rows: () => {
      const arms = { qlever: "QLever (SPARQL)", "cyvcf2-indexed": "cyvcf2, indexed", "bcftools-indexed": "bcftools, indexed", "cyvcf2-scan": "cyvcf2, unindexed scan" };
      return Object.values(D.retrieval.regional).flatMap((data) => Object.entries(data.ms).flatMap(([arm, sizes]) =>
        Object.entries(sizes).map(([size, ms]) => ({ graph: `${num(data.records)} records`, arm: arms[arm] || arm, window: Number(size), ms }))));
    },
    columns: [{ key: "graph", label: "Graph" }, { key: "arm", label: "Arm" }, { key: "window", label: "Window (bp)", num: true, format: (v) => num(v) }, { key: "ms", label: "Median (ms)", num: true, format: (v) => num(v, 1) }],
    spec(t, rows) {
      const graphs = Object.values(D.retrieval.regional).sort((a, b) => b.records - a.records).map((g) => `${num(g.records)} records`);
      return {
        data: { values: rows }, height: 300,
        params: [{ name: "graph", value: graphs[0], bind: { input: "select", options: graphs, name: "Graph " } }],
        transform: [{ filter: "datum.graph == graph" }],
        encoding: {
          x: { field: "window", type: "quantitative", scale: { type: "log" }, title: "Window size (bp, log)", axis: { values: [1e3, 1e5, 1e6, 1e7], format: "~s" } },
          y: { field: "ms", type: "quantitative", scale: { type: "log" }, title: "Milliseconds (log)" },
          color: { field: "arm", type: "nominal", title: null,
                   sort: ["QLever (SPARQL)", "cyvcf2, indexed", "bcftools, indexed", "cyvcf2, unindexed scan"] },
          tooltip: [{ field: "arm" }, { field: "window", format: "," }, { field: "ms", format: ".1f", title: "ms" }],
        },
        layer: [{ mark: "line" }, { mark: "point" }],
      };
    },
  },
};

async function renderChart(card, big = false) {
  const id = card.dataset.chart;
  const def = CHARTS[id];
  const title = fill(def.title);
  const help = fill(def.help);
  const t = tokens();
  const rows = def.rows();
  if (!big) {
    card.innerHTML = `
      <div class="chart-head"><h3>${esc(title)}</h3>
        <div class="chart-actions">
          <span class="metric-help" tabindex="0" role="note" aria-label="${esc(help)}" data-help="${esc(help)}">i</span>
          <button type="button" class="ghost" data-expand="${id}">Expand</button>
        </div></div>
      <div class="chart" role="img" aria-label="${esc(title)}"></div>
      ${def.caption ? `<p class="chart-caption">${esc(fill(def.caption))}</p>` : ""}
      <details class="data-table"><summary>Data table</summary><div class="table-wrap">${table(def.columns, rows)}</div></details>`;
  }
  const target = big ? card : card.querySelector(".chart");
  const spec = def.spec(t, rows);
  spec.$schema = "https://vega.github.io/schema/vega-lite/v5.json";
  spec.width = "container";
  spec.autosize = { type: "fit-x", contains: "padding" };
  spec.config = vlConfig(t);
  if (big && spec.height) spec.height = Math.round(spec.height * 1.6);
  await vegaEmbed(target, spec, { actions: { export: true, source: false, compiled: false, editor: false }, renderer: "svg" });
}

function renderAllCharts() {
  return Promise.all([...document.querySelectorAll("[data-chart]")].map((card) => renderChart(card)));
}

// --------------------------------------------------------------- tables and KPIs
function renderKpis() {
  const v = D.fidelity.validation;
  const m = D.fidelity.mutation.scores;
  const arms = Object.values(D.usecase.arms);
  const agreeing = arms.filter((a) => Object.values(a.carriers).every((c) => c.agree)).length;
  const largest = Math.max(...D.retrieval.costBySize.map((r) => r.triples));
  const kpis = [
    [`${D.campaign.totals.cells} cells`, `benchmark campaign, ${num(D.campaign.totals.hours, 1)} h of wall time`],
    [`${num(v.comparisons.PASS)} / ${num(Object.values(v.comparisons).reduce((a, b) => a + b, 0))}`, "paired SPARQL–VCF comparisons exactly equal (the rest not applicable)"],
    [`${m.queries.detected} · ${m.core.detected} · ${m.full.detected}`, `of ${m.full.total} injected faults detected: queries · + default shapes · + all shapes`],
    [`${agreeing} / ${arms.length} arms`, "use case: RDF and bcftools routes identical for every requester"],
    [`${millions(largest)} triples`, "largest graph queried; QLever cost stays linear"],
    [`≈ ${num(breakEven(defaultsForBreakEven()), 0)} questions`, fill("for converting the {sliceRecords}-record slice to pay off (see the calculator)")],
  ];
  document.getElementById("kpiGrid").innerHTML = kpis
    .map(([value, label]) => `<div class="kpi"><div class="value">${esc(value)}</div><div class="label">${esc(label)}</div></div>`).join("");
}

function renderEvidence() {
  const v = D.fidelity.validation;
  const m = D.fidelity.mutation.scores;
  const total = (c) => Object.values(c).reduce((a, b) => a + b, 0);
  const rows = [
    { check: "N-Triples syntax (rapper)", passed: `${v.rapper.PASS ?? 0} / ${total(v.rapper)}`, what: "The serialization parses" },
    { check: `Paired SPARQL vs cyvcf2 (${D.facts.qRange})`, passed: `${v.comparisons.PASS} / ${total(v.comparisons)}`, what: "Exact equality of normalized results; the rest are verified not applicable" },
    { check: "Cross-check invariants", passed: `${v.invariants.PASS} / ${total(v.invariants)}`, what: "E.g. transitions + transversions = biallelic SNVs" },
    { check: "Engines answering", passed: Object.entries(v.enginesAnswering).map(([k, n]) => `${n} with ${k}`).join(", "), what: "Agreement is a real comparison only where several engines answered" },
    { check: "Native decode and triple count", passed: `${(v.decode["hdt:pass"] ?? 0) + (v.decode["cottas:pass"] ?? 0)} pass`, what: `${v.decode["hdt:pass"] ?? 0} HDT and ${v.decode["cottas:pass"] ?? 0} COTTAS artifacts decode back to the source count` },
    { check: "Default SHACL profile", passed: `${v.shacl.validations} runs, ${v.shacl.violations} violations`, what: `On graphs up to ${D.facts.shaclMaxTriples} triples, ${secs(v.shacl.seconds[0])}–${secs(v.shacl.seconds[1])} each` },
    { check: "Injected faults (queries / + core / + full)", passed: `${m.queries.detected} / ${m.core.detected} / ${m.full.detected} of ${m.full.total}`, what: "A suite that cannot fail proves nothing by passing" },
  ];
  document.getElementById("evidenceTable").innerHTML = table(
    [{ key: "check", label: "Check" }, { key: "passed", label: "Result", num: true }, { key: "what", label: "What it establishes" }], rows);
  const real = D.fidelity.realGenome;
  const rerun = Object.fromEntries(real.rerun.queries.map((q) => [q.query, q.status]));
  const why = {
    q09_predicate_census: fill("{phaseSets} phase sets from GATK's PS field, which the {campaignVersion} oracle did not count"),
    q10_class_census: "the same phase sets, as vcfc:PhaseSet resources",
    q11_record_digest: fill("QLever prints a decimal QUAL canonically: {qualDiffer} digest buckets differed as written, none once trailing zeros are dropped from the {qualChanged} QUAL values that have them"),
  };
  const verdict = (s) => `<span class="status ${s === "PASS" ? "pass" : "fail"}">${esc(s === "PASS" ? "equal" : "mismatch")}</span>`;
  const sh = real.rerun.shacl;
  document.getElementById("realGenomeTable").innerHTML =
    `<p class="table-meta">${num(real.triples)} triples on QLever. ${D.facts.campaignVersion} validated without shapes; every field of every record was also compared directly with the VCF text: no differences. ` +
    `The corrected validator's rerun also checked the default shapes, in ${num(sh.batches)} record batches over ${sh.minutes} min: ${num(sh.violations)} violations.</p>` +
    table([{ key: "query", label: "Question", format: (q) => pretty(q) },
      { key: "status", label: D.facts.campaignVersion, html: (r) => verdict(r.status) },
      { key: "rerun", label: "Corrected validator", html: (r) => verdict(rerun[r.query]) },
      { key: "why", label: `Cause of the ${D.facts.campaignVersion} mismatch`, format: (_, r) => why[r.query] || "" }], real.queries);
  document.getElementById("fidelitySource").innerHTML = `Sources: <code>${esc(real.source)}</code>, <code>${esc(real.rerun.source)}</code>, the campaign's validation reports and <code>08_robustness/mutation_score*</code>.`;
}

function renderLinking() {
  const arms = D.usecase.arms;
  const linkers = [...new Set(Object.values(arms).flatMap((a) => Object.keys(a.linking.genomes || {})))];
  const rows = linkers.map((id) => ({ linker: id,
    ...Object.fromEntries(Object.entries(arms).map(([arm, a]) => [arm, a.linking.genomes?.[id]])),
    clinvar: arms.arm1.linking.clinvar?.[id] }));
  const cell = (v) => (v ? `${num(v.linked)} of ${num(v.eligible)}` : "—");
  document.getElementById("linkingTable").innerHTML = table([
    { key: "linker", label: "Linker" },
    { key: "arm1", label: "Arm 1 genomes", num: true, format: cell }, { key: "arm2", label: "Arm 2 genomes", num: true, format: cell },
    { key: "arm3", label: "Arm 3 genome", num: true, format: cell }, { key: "clinvar", label: "ClinVar", num: true, format: cell },
  ], rows) + `<p class="table-meta">${esc(fill("Linked calls of eligible calls; the gene linker counts calls in a gene span from {ensembl}. The live tier (MyVariant.info) confirmed {myvariantShare} of the {myvariantGenomes} PGP genomes' rsID links in {myvariantRequests} batched requests."))}</p>`;
  document.getElementById("usecaseSource").innerHTML = `Sources: <code>${esc(arms.arm1.source)}</code>, <code>${esc(arms.arm2.source)}</code>, <code>${esc(arms.arm3.source)}</code> and <code>benchmarks/use_case/acmg</code>.`;
}

// --------------------------------------------------------------- break-even
const BREAK_EVEN_FIELDS = [
  ["conversion", "Conversion, once (s)"],
  ["index", "QLever index build, once (s)"],
  ["parser", "VCF scan per question (s)"],
  ["sparql", "SPARQL per question (s)"],
];
function defaultsForBreakEven() {
  const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const q = D.retrieval.perQuestion;
  return {
    conversion: D.scaling.records.meanWall[1],
    index: D.retrieval.batch.setup,
    parser: median(q.map((x) => x.parser)),
    sparql: q.reduce((a, x) => a + x.sparql, 0) / q.length,
  };
}
function breakEven(v) {
  const saving = v.parser - v.sparql;
  return saving > 0 ? (v.conversion + v.index) / saving : Infinity;
}
function renderBreakEven() {
  const defaults = defaultsForBreakEven();
  const box = document.getElementById("breakEvenInputs");
  box.innerHTML = BREAK_EVEN_FIELDS.map(([key, label]) =>
    `<label>${esc(label)}<input type="number" min="0" step="any" id="be-${key}" value="${defaults[key].toFixed(key === "sparql" ? 3 : 1)}" /></label>`).join("") +
    `<label>&nbsp;<button type="button" id="be-reset">Reset to measured</button></label>`;
  const update = () => {
    const v = Object.fromEntries(BREAK_EVEN_FIELDS.map(([k]) => [k, Number(document.getElementById(`be-${k}`).value)]));
    const n = breakEven(v);
    const out = document.getElementById("breakEvenResult");
    if (!Number.isFinite(n)) {
      out.innerHTML = "SPARQL is not faster per question here, so converting <strong>never</strong> pays off on speed alone.";
      return;
    }
    out.innerHTML = `Converting pays off after <strong>${num(Math.ceil(n))} questions</strong>: ` +
      `${secs(v.conversion + v.index)} paid once, against ${secs(v.parser - v.sparql)} saved per question. ` +
      `For a single batch of ${D.facts.questions} it ${n <= D.retrieval.perQuestion.length ? "already" : "does not"} pay.`;
  };
  box.addEventListener("input", update);
  document.getElementById("be-reset").addEventListener("click", () => {
    for (const [k] of BREAK_EVEN_FIELDS) document.getElementById(`be-${k}`).value = defaults[k].toFixed(k === "sparql" ? 3 : 1);
    update();
  });
  update();
}

// --------------------------------------------------------------- explorer
const FILTERS = [["exp", "Experiment", "experiment"], ["host", "Host", "host"], ["status", "Status", "status"]];
function renderExplorer() {
  const cells = D.campaign.cells;
  const params = new URLSearchParams(location.search);
  const controls = document.getElementById("explorerControls");
  controls.innerHTML = FILTERS.map(([param, label, key]) => {
    const values = [...new Set(cells.map((c) => c[key]))].sort();
    return `<label>${label}<select data-param="${param}"><option value="">All</option>${values.map((v) =>
      `<option ${params.get(param) === v ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;
  }).join("") + `<label>Search cells<input type="search" data-param="q" value="${esc(params.get("q") || "")}" placeholder="e.g. HG005" /></label>`;
  const update = () => {
    const state = Object.fromEntries([...controls.querySelectorAll("[data-param]")].map((el) => [el.dataset.param, el.value]));
    const url = new URLSearchParams(location.search);
    for (const [k, v] of Object.entries(state)) (v ? url.set(k, v) : url.delete(k));
    history.replaceState(null, "", `${location.pathname}${url.toString() ? `?${url}` : ""}${location.hash}`);
    const shown = cells.filter((c) => FILTERS.every(([p, , key]) => !state[p] || c[key] === state[p])
      && (!state.q || c.cell.toLowerCase().includes(state.q.toLowerCase())));
    document.getElementById("explorerMeta").textContent = `${shown.length} of ${cells.length} cells`;
    document.getElementById("explorerTable").innerHTML = table([
      { key: "experiment", label: "Experiment" },
      { key: "cell", label: "Cell", html: (c) => `<a href="${esc(c.url)}">${esc(c.cell)}</a>` },
      { key: "host", label: "Host" }, { key: "status", label: "Status" },
      { key: "wallSeconds", label: "Wall time", num: true, format: (v) => secs(v) },
      { key: "toolCommit", label: "Commit", html: (c) => `<code>${esc(c.toolCommit || "N/A")}</code>` },
    ], shown);
  };
  controls.addEventListener("input", update);
  if (FILTERS.some(([p]) => params.get(p)) || params.get("q")) document.getElementById("explorer").open = true;
  update();
}

function renderHosts() {
  const rows = Object.entries(D.campaign.hosts).map(([host, p]) => ({ host, cpu: `${p.cpu_model} (${p.cpu_count} cores)`,
    memory: `${num(Number(p.mem_total_kb) / 1e6, 1)} GB`, kernel: p.kernel, docker: p.docker }));
  document.getElementById("hostTable").innerHTML = table(
    [{ key: "host", label: "Host" }, { key: "cpu", label: "CPU" }, { key: "memory", label: "Memory", num: true }, { key: "kernel", label: "Kernel" }, { key: "docker", label: "Docker" }], rows) +
    `<p class="table-meta">Harness commit <code>${esc(D.campaign.harnessCommit)}</code>.</p>`;
}

// --------------------------------------------------------------- modal
function wireModal() {
  const modal = document.getElementById("focusModal");
  document.addEventListener("click", async (event) => {
    const id = event.target.closest("[data-expand]")?.dataset.expand;
    if (!id) return;
    document.getElementById("focusModalTitle").textContent = fill(CHARTS[id].title);
    const content = document.getElementById("focusContent");
    content.innerHTML = "";
    content.dataset.chart = id;
    modal.showModal();
    await renderChart(content, true);
  });
  document.getElementById("focusClose").addEventListener("click", () => modal.close());
}

// --------------------------------------------------------------- start
async function main() {
  const responses = await Promise.all(DATASETS.map((name) => fetch(`./data/${name}.json`).then((r) => {
    if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`);
    return r.json();
  })));
  DATASETS.forEach((name, i) => { D[name] = responses[i]; });
  const meta = D.campaign.meta;
  document.getElementById("dataMeta").textContent =
    `Campaign: VCF-RDFizer ${D.facts.campaignVersion} (${D.facts.campaignImage}). Site built ${meta.builtAt.replace("T", " ").replace("+00:00", " UTC")}` +
    (meta.repoCommit ? ` from commit ${meta.repoCommit}.` : ".");
  if (meta.repoCommit) document.getElementById("commitLink").href = `${REPO}/tree/${meta.repoCommit}`;
  for (const el of document.querySelectorAll("[data-fill]")) el.textContent = D.facts[el.dataset.fill] ?? "N/A";
  renderKpis();
  renderEvidence();
  renderLinking();
  renderBreakEven();
  renderExplorer();
  renderHosts();
  for (const [id, text] of [["conversionSource", "04_scaling_records, 03_sample_representation, 01_storage_mode and 05_corpus_breadth, through scripts/figure_data.py"],
    ["retrievalSource", "13_query_cost, 14_regional_access (vcf-bench-1) and 16_scale_retrieval (vcf-bench-3)"]]) {
    document.getElementById(id).textContent = `Sources: ${text}.`;
  }
  wireModal();
  await renderAllCharts();
  darkQuery.addEventListener("change", renderAllCharts);
}

main().catch((error) => {
  document.getElementById("dataMeta").textContent = `Could not load the data: ${error.message}`;
  console.error(error);
});
