// VCF-RDFizer results site. Loads the JSON built by scripts/build_site_data.py
// and renders every chart with Vega-Lite. Nothing here computes a reported
// number from scratch: values come from the data files, and the build's tests
// pin them to the paper. Prose quotes them through {placeholders} filled from
// facts.json, so no number is written into this file or the page.
"use strict";

const DATASETS = ["campaign", "fidelity", "scaling", "retrieval", "usecase", "converters", "facts"];
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

// The paper's requester abbreviations (Figure 4): own physician (OP), clinical care (CC),
// disease-specific research (DS), general research use (GRU).
const REQUESTERS = [
  ["unrestricted", "All (no policy)"], ["own_physician", "Own physician (OP)"], ["clinical", "Clinical care (CC)"],
  ["cardio", "Disease-specific (DS)"], ["biobank", "General research (GRU)"],
];
const REQUESTER_LABEL = Object.fromEntries(REQUESTERS);
const REQUESTER_SHORT = { unrestricted: "All", own_physician: "OP", clinical: "CC", cardio: "DS", biobank: "GRU" };
const armShort = (arm) => ({ arm2rare: "Scenario 2, rare" })[arm] || `Scenario ${arm.slice(3)}`;
const REQUESTER_ORDER = REQUESTERS.map(([, label]) => label);
const armLabel = (arm) => ({
  arm1: fill("Scenario 1: {arm1Genomes} gene-span slices"), arm2: fill("Scenario 2: cohort of {cohort}"),
  arm2rare: "Scenario 2: rare in the panel", arm3: fill("Scenario 3: complete {wholeGenome} VCF"),
  arm4: fill("Scenario 4: complete {arm4Participant} VCF"),
})[arm] || arm;

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
    title: "Detection of injected faults by validation layer",
    help: "{faults} targeted changes to coordinates, alleles, filters, metadata, phasing, sample indexes and relationships were injected into a converted graph. Bars give the number detected by the source-comparison queries alone, with the default SHACL profile, and with all shape profiles.",
    rows: () => {
      const s = D.fidelity.mutation.scores;
      return [
        { layer: "Source-comparison queries", detected: s.queries.detected, total: s.queries.total },
        { layer: "Queries and default SHACL profile", detected: s.core.detected, total: s.core.total },
        { layer: "Queries and all shape profiles", detected: s.full.detected, total: s.full.total },
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
    title: "The {faultClasses} mutation classes not detected by the source-comparison queries",
    help: "Each row is a mutation class that the source-comparison queries do not detect. Cells give the number of its mutations detected by each shape profile. The default profile checks cardinality and datatypes and detects none of them; the full profile set adds uniqueness and value-agreement constraints.",
    caption: "The full profile set requires self-joins over the graph; {campaignVersion} applies it only on request and only to small inputs.",
    rows: () => D.fidelity.mutation.missedByQueries.flatMap((m) => [
      { class: m.class.replace(/_/g, " "), profile: "Default profile", caught: m.core, mutations: m.mutations },
      { class: m.class.replace(/_/g, " "), profile: "All shape profiles", caught: m.full, mutations: m.mutations },
    ]),
    columns: [{ key: "class", label: "Mutation class" }, { key: "profile", label: "Shape profile" }, { key: "caught", label: "Detected", num: true }, { key: "mutations", label: "Mutations", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 300,
        transform: [{ calculate: "datum.caught / datum.mutations", as: "share" }],
        encoding: {
          y: { field: "class", type: "nominal", title: null },
          x: { field: "profile", type: "nominal", title: null, sort: ["Default profile", "All shape profiles"], axis: { orient: "top", labelAngle: 0 } },
          tooltip: [{ field: "class", title: "Mutation class" }, { field: "profile", title: "Shape profile" }, { field: "caught", title: "Detected" }, { field: "mutations", title: "Mutations" }],
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

  matches: {
    title: "Matches each requester may receive, by scenario",
    help: "Participant–variant–gene matches to a ClinVar classification in an {geneList} gene that each requester may receive under the simulated consents, with the share of the unrestricted answer. The RDF and conventional workflows returned identical match sets in every cell. Only Scenario 4 includes the participant's own physician as a requester.",
    rows: () => {
      const out = [];
      for (const [arm, data] of Object.entries(D.usecase.arms)) {
        const sets = [[arm, data.carriers]];
        if (Object.keys(data.rare || {}).length) sets.push([`${arm}rare`, data.rare]);
        for (const [key, matches] of sets) {
          for (const [r, label] of REQUESTERS) {
            const c = matches[r];
            if (!c) continue;
            out.push({ arm: armLabel(key), armShort: armShort(key), requester: label, requesterShort: REQUESTER_SHORT[r],
                       matches: c.rdf, conventional: c.baseline, agree: c.agree ? "identical" : "DIFFER",
                       share: matches.unrestricted.rdf ? c.rdf / matches.unrestricted.rdf : null });
          }
        }
      }
      return out;
    },
    columns: [{ key: "arm", label: "Scenario" }, { key: "requester", label: "Requester" }, { key: "matches", label: "RDF workflow", num: true, format: (v) => num(v) },
      { key: "conventional", label: "Conventional workflow", num: true, format: (v) => num(v) }, { key: "agree", label: "Match sets" }],
    spec(t, rows, width) {
      // A phone gets the paper's short labels (Figure 4) and counts only, so the five columns stay legible.
      const narrow = width < 600;
      return {
        data: { values: rows }, height: 240,
        encoding: {
          y: { field: narrow ? "armShort" : "arm", type: "nominal", sort: null, title: null, axis: { labelLimit: 260 } },
          x: { field: narrow ? "requesterShort" : "requester", type: "nominal", sort: narrow ? Object.values(REQUESTER_SHORT) : REQUESTER_ORDER,
               title: null, axis: { orient: "top", labelAngle: 0, labelLimit: 150 } },
          tooltip: [{ field: "arm", title: "Scenario" }, { field: "requester", title: "Requester" }, { field: "matches", title: "RDF workflow", format: "," },
            { field: "conventional", title: "Conventional workflow", format: "," }, { field: "agree", title: "Match sets" }, { field: "share", title: "Share of unrestricted", format: ".0%" }],
        },
        layer: [
          { mark: { type: "rect", stroke: t.surface, strokeWidth: 2, cornerRadius: 3 },
            encoding: { color: { field: "share", type: "quantitative", scale: { domain: [0, 1], range: t.seq },
              legend: { title: "Share of unrestricted", format: ".0%", direction: "horizontal", gradientLength: 160 } } } },
          { mark: { type: "text", fontWeight: 600 },
            encoding: {
              text: { value: { expr: narrow ? "datum.matches >= 1000 ? format(datum.matches / 1000, '.1f') + 'k' : format(datum.matches, ',')"
                : "format(datum.matches, ',') + (datum.requester == 'All (no policy)' ? '' : '  (' + format(datum.share, '.0%') + ')')" } },
              color: { condition: { test: "datum.share >= 0.5", value: t.onSeqStrong }, value: t.text },
            } },
        ],
      };
    },
  },

  participants: {
    title: "Scenario 1: matches per participant and requester",
    help: "Per-file consents determine each answer: {consents}. The cohort rule restricts the {restrictedGenes} cancer-predisposition genes to clinical care.",
    rows: () => {
      const g = D.usecase.arms.arm1.grid;
      return Object.entries(g.rows).flatMap(([requester, counts]) =>
        counts.map((c, i) => ({ requester: REQUESTER_LABEL[requester] || requester, participant: g.participants[i], carriers: c })));
    },
    columns: [{ key: "participant", label: "Participant" }, { key: "requester", label: "Requester" }, { key: "carriers", label: "Matches", num: true, format: (v) => num(v) }],
    spec(t, rows, width) {
      const max = Math.max(...rows.map((r) => r.carriers));
      return {
        data: { values: rows }, height: 190,
        encoding: {
          y: { field: "requester", type: "nominal", sort: REQUESTER_ORDER, title: null, axis: { labelLimit: 160 } },
          x: { field: "participant", type: "nominal", sort: null, title: null, axis: { orient: "top", labelAngle: width < 600 ? -40 : 0 } },
          tooltip: [{ field: "participant", title: "Participant" }, { field: "requester", title: "Requester" }, { field: "carriers", title: "Matches", format: "," }],
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
    title: "Lines added and removed by each applied change",
    help: "Four changes were applied to both workflows as edits; after each, both workflows were rerun on a fixture and had to release the same records. Bars to the right of zero are lines added and to the left lines removed (non-blank, non-comment lines), summed over the files each workflow changes.",
    caption: "Initially authored rules, excluding data: RDF workflow {rdfRules}; conventional workflow {baselineRules}.",
    rows: () => D.usecase.effort.scenarios.flatMap((s) => ["rdf", "baseline"].flatMap((route) => {
      const files = Object.entries(s.edits[route]);
      const added = files.reduce((a, [, e]) => a + e.added, 0);
      const removed = files.reduce((a, [, e]) => a + e.removed, 0);
      const touched = files.filter(([, e]) => e.added || e.removed).map(([f, e]) => `${f} +${e.added}/−${e.removed}`).join("; ");
      const label = route === "rdf" ? "RDF workflow" : "Conventional workflow";
      return [{ scenario: s.summary, route: label, kind: "added", lines: added, files: touched },
              { scenario: s.summary, route: label, kind: "removed", lines: -removed, files: touched }];
    })),
    columns: [{ key: "scenario", label: "Change" }, { key: "route", label: "Workflow" }, { key: "kind", label: "" }, { key: "lines", label: "Lines", num: true, format: (v) => num(Math.abs(v)) }, { key: "files", label: "Files" }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 260,
        encoding: {
          y: { field: "scenario", type: "nominal", sort: null, title: null, axis: { labelLimit: 320 } },
          yOffset: { field: "route", sort: ["RDF workflow", "Conventional workflow"] },
          x: { field: "lines", type: "quantitative", title: "Lines removed ← → lines added" },
          color: { field: "route", type: "nominal", scale: { domain: ["RDF workflow", "Conventional workflow"], range: [t.series[0], t.series[1]] }, title: null },
          tooltip: [{ field: "scenario", title: "Change" }, { field: "route", title: "Workflow" }, { field: "kind", title: "Lines" }, { field: "files", title: "Files" }],
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
    title: "Stage costs of the RDF workflow by scenario",
    help: "Shown for the clinical-care requester (CC), which is present in every scenario. Conversion and linking are performed once per scenario and include ClinVar; release-view writing, validation and indexing, and the query (median of {queryReplicates} runs), are performed per requester. The data table lists every requester.",
    caption: "Most linked-workflow cost occurs before the first query and increases with the scenario's graph size, whereas query time remains close to the fixed cost of the ClinVar join.",
    rows: () => {
      const stages = [["convert", "Conversion"], ["link", "Linking"], ["view", "View writing"], ["check", "View validation"], ["index", "View indexing"], ["query", "Query"]];
      return Object.entries(D.usecase.arms).flatMap(([arm, data]) => {
        const c = data.costs;
        return Object.entries(c.requesters).flatMap(([requester, r]) => stages.map(([key, stage]) => ({
          arm: armLabel(arm), requester: REQUESTER_LABEL[requester] || requester, requesterKey: requester, stage,
          seconds: key === "convert" || key === "link" ? c[key] : r[key] ?? null,
          perArm: key === "convert" || key === "link",
        }))).filter((row) => !row.perArm || row.requesterKey === "clinical");
      }).map((row) => ({ ...row, label: secs(row.seconds) }));
    },
    columns: [{ key: "arm", label: "Scenario" }, { key: "requester", label: "Requester" }, { key: "stage", label: "Stage" }, { key: "seconds", label: "Time", num: true, format: (v) => secs(v) }],
    spec(t, rows, width) {
      const shown = rows.filter((r) => r.requesterKey === "clinical" && r.seconds > 0);
      return {
        data: { values: shown }, height: 300,
        encoding: {
          y: { field: "stage", type: "nominal", sort: ["Conversion", "Linking", "View writing", "View validation", "View indexing", "Query"], title: null },
          yOffset: { field: "arm", sort: null },
          x: { field: "seconds", type: "quantitative", scale: { type: "log" }, title: "Seconds (log scale)",
               axis: { values: [10, 100, 1000, 10000], format: "," } },
          color: { field: "arm", type: "nominal", title: null, sort: null, scale: { range: t.series } },
          tooltip: [{ field: "arm", title: "Scenario" }, { field: "stage", title: "Stage" }, { field: "label", title: "Time" }],
        },
        layer: [
          { mark: "point" },
          ...(width >= 600 ? [{ mark: { type: "text", align: "left", dx: 9, fontSize: 10 }, encoding: { text: { field: "label" }, color: { value: t.muted } } }] : []),
        ],
      };
    },
  },

  converters: {
    title: "Agreement of each converter's graph with the source-derived oracle",
    help: "Each cell is one content question on one input, translated to the converter's vocabulary and compared with the same source-derived oracle, normalization, comparator and QLever build used for VCF-RDFizer. A question is reported as not represented when the graph lacks the required information.",
    ownWidth: true,
    rows: () => {
      const tools = Object.fromEntries(D.converters.tools.map((x) => [x.id, x.name]));
      const inputs = Object.fromEntries(D.converters.inputs.map((x) => [x.id, x.label]));
      const questions = Object.fromEntries(D.converters.questions.map((x) => [x.id, x.label]));
      const outcome = { PASS: "Matches the oracle", MISMATCH: "Differs from the oracle", NOT_REPRESENTED: "Not represented" };
      return D.converters.outcomes.map((o) => ({
        tool: tools[o.tool] || o.tool, input: inputs[o.input] || o.input, question: questions[o.question].split(" ")[0],
        questionLabel: questions[o.question], outcome: outcome[o.status] || o.status,
        mark: { PASS: "✓", MISMATCH: "×", NOT_REPRESENTED: "–" }[o.status] || "?",
      }));
    },
    columns: [{ key: "input", label: "Input" }, { key: "tool", label: "Converter" }, { key: "questionLabel", label: "Question" }, { key: "outcome", label: "Outcome" }],
    spec(t, rows, width) {
      const toolOrder = D.converters.tools.map((x) => x.name);
      const qOrder = D.converters.questions.map((x) => x.label.split(" ")[0]);
      const sideBySide = width >= 760;
      const cell = Math.max(22, Math.min(width > 1000 ? 58 : 46, ((sideBySide ? (width - 180) / 2 : width - 180) - 30) / qOrder.length));
      return {
        data: { values: rows },
        facet: { [sideBySide ? "column" : "row"]: { field: "input", type: "nominal", title: null, sort: D.converters.inputs.map((x) => x.label),
          header: { labelFontSize: 12, labelFontWeight: 600, labelColor: t.text, labelAnchor: "start", labelOrient: "top" } } },
        spec: {
          width: cell * qOrder.length, height: Math.round(cell * 0.68) * toolOrder.length,
          encoding: {
            y: { field: "tool", type: "nominal", sort: toolOrder, title: null, axis: { labelLimit: 170 } },
            x: { field: "question", type: "nominal", sort: qOrder, title: null, axis: { orient: "top", labelAngle: 0 } },
            tooltip: [{ field: "tool", title: "Converter" }, { field: "input", title: "Input" }, { field: "questionLabel", title: "Question" }, { field: "outcome", title: "Outcome" }],
          },
          layer: [
            { mark: { type: "rect", stroke: t.surface, strokeWidth: 2, cornerRadius: 3 },
              encoding: { color: { field: "outcome", type: "nominal", title: null,
                scale: { domain: ["Matches the oracle", "Differs from the oracle", "Not represented"], range: [t.series[0], t.series[1], t.grid] } } } },
            { mark: { type: "text", fontWeight: 700, fontSize: 13 },
              encoding: { text: { field: "mark" }, color: { condition: { test: "datum.outcome == 'Not represented'", value: t.muted }, value: t.onSeqStrong } } },
          ],
        },
        resolve: { scale: { x: "shared", y: "shared" } },
      };
    },
  },

  records: {
    title: "Record scaling of conversion cost",
    help: "Each line is one measure of conversion on the HG005 record-count series ({ladder} records, {ladderReplicates} replicates each, then the complete {wholeRecords}-record VCF), relative to its value on the smallest input. Medians of the replicates.",
    rows: () => {
      const r = D.scaling.records;
      const measures = { triples: "Triples", wall: "End-to-end time", disk: "Peak workspace", rss: "Mapping-stage resident memory" };
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
               axis: { values: D.scaling.records.rungs, labelExpr: `datum.value == ${D.scaling.records.wholeFileRecords} ? '${D.facts.wholeRecords} (complete)' : format(datum.value, '~s')` } },
          y: { field: "growth", type: "quantitative", scale: { type: "log" }, title: "Growth relative to the smallest input" },
          color: { field: "measure", type: "nominal", title: null, sort: ["Triples", "End-to-end time", "Peak workspace", "Mapping-stage resident memory"] },
          tooltip: [{ field: "measure" }, { field: "records", format: "," }, { field: "value" }, { field: "growth", title: "× smallest", format: ".1f" }],
        },
        layer: [{ mark: "line" }, { mark: "point" }],
      };
    },
  },

  samples: {
    title: "Sample representation: triples and stored bytes",
    help: "The same {sampleRecords} 1000 Genomes records converted with {samplesMin} to {samplesMax} sample columns under both profiles. Select a measure: condensed triple counts remain nearly constant while its stored bytes grow, because per-sample values are encoded in vector literals.",
    rows: () => {
      const s = D.scaling.samples;
      const measures = { triples: "Triples", nt: "Gzip-framed N-Triples (bytes)", hdt: "HDT (bytes)" };
      const out = [];
      for (const [profile, label] of [["expanded", "Expanded"], ["condensed", "Condensed"]]) {
        s[profile].x.forEach((n, i) => {
          for (const [k, m] of Object.entries(measures)) out.push({ samples: n, profile: label, measure: m, value: s[profile][k][i] });
        });
      }
      s.condensed.x.forEach((n, i) => {
        for (const m of ["Gzip-framed N-Triples (bytes)", "HDT (bytes)"]) out.push({ samples: n, profile: "Input VCF", measure: m, value: s.condensed.vcf[i] });
      });
      return out;
    },
    columns: [{ key: "measure", label: "Measure" }, { key: "profile", label: "Series" }, { key: "samples", label: "Samples", num: true, format: (v) => num(v) }, { key: "value", label: "Value", num: true, format: (v) => num(v) }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 280,
        params: [{ name: "measure", value: "Triples",
          bind: { input: "select", options: ["Triples", "Gzip-framed N-Triples (bytes)", "HDT (bytes)"], name: "Measure " } }],
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
    title: "Peak workspace by storage mode",
    help: "Paired runs of the plain and space-optimized storage modes on the same inputs. Both produce identical triples and final artifact sizes; space-optimized storage reduces only the peak transient workspace, with a {spaceTimeCost} increase in time.",
    rows: () => {
      const names = { slice: "HG005 slice", larger: "test-larger" };
      return Object.entries(D.scaling.storage).flatMap(([key, modes]) => Object.entries(modes).map(([mode, m]) => ({
        input: `${names[key] || key} (${millions(m.triples)} triples)`, mode: mode === "plain" ? "Plain" : "Space-optimized",
        gb: m.peakBytes / 1e9, time: secs(m.wallSeconds),
      })));
    },
    columns: [{ key: "input", label: "Input" }, { key: "mode", label: "Storage mode" }, { key: "gb", label: "Peak workspace (GB)", num: true, format: (v) => num(v, 2) }, { key: "time", label: "End-to-end time", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 130,
        encoding: {
          y: { field: "input", type: "nominal", title: null },
          x: { field: "gb", type: "quantitative", scale: { type: "log" }, title: "Peak workspace (GB, log scale)", axis: { values: [0.1, 1, 10, 100], format: "~g" } },
          tooltip: [{ field: "input", title: "Input" }, { field: "mode", title: "Storage mode" }, { field: "gb", title: "Peak workspace (GB)", format: ".2f" }, { field: "time", title: "End-to-end time" }],
        },
        layer: [
          { mark: { type: "rule", color: t.grid, strokeWidth: 3 }, encoding: { detail: { field: "input" } } },
          { mark: "point", encoding: { color: { field: "mode", type: "nominal", title: null, scale: { domain: ["Plain", "Space-optimized"], range: [t.context, t.series[0]] } } } },
        ],
      };
    },
  },

  representations: {
    title: "Artifact size relative to gzip-framed N-Triples",
    help: "For each corpus input (first {corpusRecords} records; HG005 complete), the size of the HDT and COTTAS artifacts built from the same graph, divided by the size of the gzip-framed N-Triples. Hover for construction times.",
    rows: () => D.scaling.corpus.flatMap((r) => {
      const input = `${r.name.replace("(whole)", "(complete)")} · ${millions(r.triples)}`;
      return [{ input, artifact: "COTTAS", ratio: r.cottas / r.nt, build: secs(r.cottas_s) },
              { input, artifact: "HDT", ratio: r.hdt / r.nt, build: secs(r.hdt_s) }];
    }),
    columns: [{ key: "input", label: "Input" }, { key: "artifact", label: "Artifact" }, { key: "ratio", label: "× N-Triples", num: true, format: (v) => num(v, 2) }, { key: "build", label: "Construction time", num: true }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 260,
        encoding: {
          y: { field: "input", type: "nominal", sort: null, title: null },
          x: { field: "ratio", type: "quantitative", scale: { domain: [0, 2] }, title: "Size ÷ gzip-framed N-Triples" },
          tooltip: [{ field: "input", title: "Input" }, { field: "artifact", title: "Artifact" }, { field: "ratio", title: "× N-Triples", format: ".2f" }, { field: "build", title: "Construction time" }],
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
    title: "Individual questions: indexed QLever queries and full cyvcf2 parses",
    help: "Each question on the {sliceTriples}-triple graph of {sliceRecords} HG005 records, mean of {engineReplicates} replicates. Each cyvcf2 answer requires a full parse of the VCF. QLever times exclude the {qleverIndex} index build. The last row compares the {questions}-question batch, which one cyvcf2 pass answers.",
    rows: () => {
      const r = D.retrieval;
      const rows = r.perQuestion.map((q) => ({ question: q.label, sparql: q.sparql, parser: q.parser, speedup: q.parser / q.sparql }));
      rows.push({ question: fill("{questions}-question batch").replace(/^./, (c) => c.toUpperCase()), sparql: r.batch.sparql, parser: r.batch.parser, speedup: r.batch.parser / r.batch.sparql });
      return rows;
    },
    columns: [{ key: "question", label: "Question" }, { key: "sparql", label: "Indexed QLever query", num: true, format: (v) => secs(v) }, { key: "parser", label: "Full cyvcf2 parse", num: true, format: (v) => secs(v) },
      { key: "speedup", label: "Parse time ÷ query time", num: true, format: (v) => `${num(v, v >= 10 ? 0 : 1)}×` }],
    spec(t, rows) {
      const long = rows.flatMap((r) => [{ ...r, side: "Indexed QLever query", seconds: r.sparql }, { ...r, side: "Full cyvcf2 parse", seconds: r.parser }]);
      return {
        data: { values: long }, height: 360,
        encoding: {
          y: { field: "question", type: "nominal", sort: null, title: null },
          x: { field: "seconds", type: "quantitative", scale: { type: "log" }, title: "Seconds (log scale)",
               axis: { values: [0.001, 0.01, 0.1, 1, 10, 100], format: "~g" } },
          tooltip: [{ field: "question", title: "Question" }, { field: "sparql", title: "Indexed QLever query (s)", format: ".3f" }, { field: "parser", title: "Full cyvcf2 parse (s)", format: ".2f" }, { field: "speedup", title: "Parse time ÷ query time", format: ",.1f" }],
        },
        layer: [
          { mark: { type: "rule", color: t.grid, strokeWidth: 3 }, encoding: { detail: { field: "question" } } },
          { mark: "point", encoding: { color: { field: "side", type: "nominal", title: null, scale: { domain: ["Indexed QLever query", "Full cyvcf2 parse"], range: [t.series[0], t.context] } } } },
        ],
      };
    },
  },

  engines: {
    title: "Query time by SPARQL engine",
    help: "Total time for the {questions} questions on the {fixtureTriples}-triple fixture graph under each SPARQL engine: mean of {engineRuns} runs ({engineArtifacts} artifacts in each of {engineReplicates} replicates), with the range. All engines returned the same answers in every run.",
    rows: () => Object.entries(D.retrieval.engines).map(([engine, e]) => ({
      engine: { qlever: "QLever", comunica: "Comunica (N-Triples)", cottas: "Comunica (COTTAS, DuckDB)", hdt: "Comunica (HDT)" }[engine] || engine,
      mean: e.mean, min: e.min, max: e.max, runs: e.runs,
    })).sort((a, b) => a.mean - b.mean),
    columns: [{ key: "engine", label: "Engine" }, { key: "mean", label: "Mean", num: true, format: (v) => secs(v) }, { key: "min", label: "Minimum", num: true, format: (v) => secs(v) }, { key: "max", label: "Maximum", num: true, format: (v) => secs(v) }],
    spec(t, rows) {
      return {
        data: { values: rows }, height: 150,
        encoding: {
          y: { field: "engine", type: "nominal", sort: null, title: null },
          tooltip: [{ field: "engine", title: "Engine" }, { field: "mean", format: ".1f", title: "Mean (s)" }, { field: "min", format: ".1f", title: "Minimum (s)" }, { field: "max", format: ".1f", title: "Maximum (s)" }],
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
    title: "QLever query time per million triples, up to {maxTriples} triples",
    help: "QLever time for the {questions} questions (sum of per-question medians) divided by the graph size in millions of triples. The data table lists the host on which each graph was queried.",
    rows: () => D.retrieval.costBySize.map((r) => ({
      graph: { small: "Fixture", large: "HG005 slice", whole: "Complete HG005 VCF" }[r.graph] || r.graph.replace(/^r(\d+)$/, (_, n) => `${num(Number(n) / 1e6)}M records`),
      triples: r.triples, seconds: r.seconds, perMillion: r.perMillion, host: r.host })),
    columns: [{ key: "graph", label: "Graph" }, { key: "triples", label: "Triples", num: true, format: (v) => num(v) }, { key: "seconds", label: "All questions", num: true, format: (v) => secs(v) },
      { key: "perMillion", label: "Seconds per million triples", num: true, format: (v) => num(v, 2) }, { key: "host", label: "Host" }],
    spec(t, rows) {
      const ranked = [...rows].sort((a, b) => a.triples - b.triples).map((r, rank) => ({ ...r, rank }));
      return {
        data: { values: ranked }, height: 220,
        encoding: {
          x: { field: "triples", type: "quantitative", scale: { type: "log", domain: [5e5, 1.5e9] }, title: "Triples (log scale)", axis: { values: [1e6, 1e7, 1e8, 1e9], format: "~s" } },
          y: { field: "perMillion", type: "quantitative", scale: { zero: true }, title: "Seconds per million triples" },
          tooltip: [{ field: "graph", title: "Graph" }, { field: "triples", format: ",", title: "Triples" }, { field: "seconds", format: ".1f", title: "Seconds" }, { field: "perMillion", format: ".2f", title: "Seconds per million triples" }, { field: "host", title: "Host" }],
        },
        layer: [
          { mark: { type: "line", color: t.series[0] } },
          { mark: { type: "point", color: t.series[0] } },
          // Labels alternate above and below the line, and the largest graph's is right-aligned, so
          // neighbouring labels do not collide in a narrow card.
          { mark: { type: "text", dy: -14, color: t.muted }, transform: [{ filter: "datum.rank % 2 == 0" }], encoding: { text: { field: "graph" } } },
          { mark: { type: "text", dy: 16, color: t.muted }, transform: [{ filter: `datum.rank % 2 == 1 && datum.rank < ${rows.length - 1}` }],
            encoding: { text: { field: "graph" } } },
          { mark: { type: "text", dy: 16, dx: 6, align: "right", color: t.muted }, transform: [{ filter: `datum.rank % 2 == 1 && datum.rank == ${rows.length - 1}` }],
            encoding: { text: { field: "graph" } } },
        ],
      };
    },
  },

  regional: {
    title: "Regional queries: QLever and tabix-indexed VCF access",
    help: "Median over {regionalQuestions} regional questions of each question's median across {regionalWindows} windows ({regionalScanWindows} for full parses of the unindexed VCF) and {regionalReplicates} replicates. All execution paths apply the same POS-based selection; across both graphs, {regionalExecutions} executions produced {regionalFailures} failures and {regionalDisagreements} disagreements. Select a graph to compare the smaller fixture.",
    rows: () => {
      const arms = { qlever: "QLever (RDF)", "cyvcf2-indexed": "cyvcf2 + tabix", "bcftools-indexed": "bcftools + tabix", "cyvcf2-scan": "cyvcf2, full parse" };
      return Object.values(D.retrieval.regional).flatMap((data) => Object.entries(data.ms).flatMap(([arm, sizes]) =>
        Object.entries(sizes).map(([size, ms]) => ({ graph: `${num(data.records)} records`, arm: arms[arm] || arm, window: Number(size), ms }))));
    },
    columns: [{ key: "graph", label: "Graph" }, { key: "arm", label: "Execution path" }, { key: "window", label: "Window (bp)", num: true, format: (v) => num(v) }, { key: "ms", label: "Median (ms)", num: true, format: (v) => num(v, 1) }],
    spec(t, rows) {
      const graphs = Object.values(D.retrieval.regional).sort((a, b) => b.records - a.records).map((g) => `${num(g.records)} records`);
      return {
        data: { values: rows }, height: 300,
        params: [{ name: "graph", value: graphs[0], bind: { input: "select", options: graphs, name: "Graph " } }],
        transform: [{ filter: "datum.graph == graph" }],
        encoding: {
          x: { field: "window", type: "quantitative", scale: { type: "log" }, title: "Window size (bp, log scale)", axis: { values: [1e3, 1e5, 1e6, 1e7], format: "~s" } },
          y: { field: "ms", type: "quantitative", scale: { type: "log" }, title: "Milliseconds (log scale)" },
          color: { field: "arm", type: "nominal", title: null,
                   sort: ["QLever (RDF)", "bcftools + tabix", "cyvcf2 + tabix", "cyvcf2, full parse"] },
          tooltip: [{ field: "arm", title: "Execution path" }, { field: "window", format: ",", title: "Window (bp)" }, { field: "ms", format: ".1f", title: "Median (ms)" }],
        },
        layer: [{ mark: "line" }, { mark: "point" }],
      };
    },
  },
};

// Charts render into a block-level .chart element: vega-embed turns the element it is given into
// an inline-block, which inside the modal collapsed to the width of its content and drew nothing.
// No export menu: the data table under each chart, and the archive, are the data.
async function renderChart(host, { id = host.dataset.chart, big = false } = {}) {
  const def = CHARTS[id];
  const title = fill(def.title);
  const help = fill(def.help);
  const caption = def.caption ? `<p class="chart-caption">${esc(fill(def.caption))}</p>` : "";
  const t = tokens();
  const rows = def.rows();
  if (big) {
    host.innerHTML = `<div class="chart" role="img" aria-label="${esc(title)}"></div>${caption}`;
  } else {
    host.innerHTML = `
      <div class="chart-head"><h3>${esc(title)}</h3>
        <div class="chart-actions">
          <span class="metric-help" tabindex="0" role="note" aria-label="${esc(help)}" data-help="${esc(help)}">i</span>
          <button type="button" class="ghost" data-expand="${id}" aria-label="Expand: ${esc(title)}">Expand</button>
        </div></div>
      <div class="chart" role="img" aria-label="${esc(title)}"></div>
      ${caption}
      <details class="data-table"><summary>Data table</summary><div class="table-wrap">${table(def.columns, rows)}</div></details>`;
  }
  const target = host.querySelector(".chart");
  const spec = def.spec(t, rows, target.clientWidth || 800);
  spec.$schema = "https://vega.github.io/schema/vega-lite/v5.json";
  if (!def.ownWidth) {
    spec.width = "container";
    spec.autosize = { type: "fit-x", contains: "padding" };
  }
  spec.config = vlConfig(t);
  // On a narrow screen a horizontal legend runs off the card: stack it below the chart instead.
  if ((target.clientWidth || 800) < 600) spec.config.legend = { ...spec.config.legend, orient: "bottom", direction: "vertical" };
  if (big && spec.height) spec.height = Math.round(spec.height * 1.6);
  await vegaEmbed(target, spec, { actions: false, renderer: "svg" });
}

function renderAllCharts() {
  const charts = [...document.querySelectorAll("[data-chart]")].map((card) => renderChart(card));
  const modal = document.getElementById("focusModal");
  if (modal.open && modal.dataset.chart) charts.push(renderChart(document.getElementById("focusContent"), { id: modal.dataset.chart, big: true }));
  return Promise.all(charts);
}

// --------------------------------------------------------------- tables and KPIs
function renderKpis() {
  const v = D.fidelity.validation;
  const m = D.fidelity.mutation.scores;
  const arms = Object.values(D.usecase.arms);
  const agreeing = arms.filter((a) => Object.values(a.carriers).every((c) => c.agree)).length;
  const largest = Math.max(...D.retrieval.costBySize.map((r) => r.triples));
  const ownPassed = D.converters.questions.filter((q) => D.converters.outcomes
    .filter((o) => o.tool === "vcf-rdfizer" && o.question === q.id).every((o) => o.status === "PASS")).length;
  const kpis = [
    ["RQ1", `${num(v.comparisons.PASS)} / ${num(v.comparisons.PASS)}`, fill("applicable SPARQL results agreed exactly with their source-derived counterparts; {comparisonsOther} more verified not applicable")],
    ["RQ1", `${m.queries.detected} · ${m.core.detected} · ${m.full.detected}`, `of ${m.full.total} injected faults detected: source-comparison queries · with the default SHACL profile · with all shape profiles`],
    ["RQ2", `${agreeing} / ${arms.length} scenarios`, "with identical requester-specific match sets from the RDF and conventional workflows"],
    ["RQ3", `${ownPassed} / ${D.converters.questions.length}`, fill("content questions matched the source-derived oracle on both inputs; {converterAllPass} was the only converter to match all")],
    ["RQ3", `${millions(largest)} triples`, "largest graph queried; QLever query time remained approximately linear in graph size"],
    ["RQ3", `≈ ${D.facts.breakEven} questions`, fill("break-even of the minimal RDF setup for the {sliceRecords}-record HG005 slice")],
  ];
  document.getElementById("kpiGrid").innerHTML = kpis
    .map(([tag, value, label]) => `<div class="kpi"><div class="kpi-tag">${esc(tag)}</div><div class="value">${esc(value)}</div><div class="label">${esc(label)}</div></div>`).join("");
}

function renderEvidence() {
  const v = D.fidelity.validation;
  const m = D.fidelity.mutation.scores;
  const total = (c) => Object.values(c).reduce((a, b) => a + b, 0);
  const rows = [
    { check: "N-Triples syntax (rapper)", passed: `${v.rapper.PASS ?? 0} / ${total(v.rapper)}`, what: "The serialization is syntactically valid N-Triples" },
    { check: `Source-comparison queries (${D.facts.qRange})`, passed: `${v.comparisons.PASS} / ${total(v.comparisons)}`, what: "Normalized SPARQL results equal the source-derived answers; the remainder are verified not applicable" },
    { check: "Consistency invariants", passed: `${v.invariants.PASS} / ${total(v.invariants)}`, what: "Internal consistency checks, for example transitions plus transversions equal biallelic SNVs" },
    { check: "Engines per validation run", passed: Object.entries(v.enginesAnswering).map(([k, n]) => `${n} runs with ${k}`).join(", "), what: "Cross-engine agreement is tested in the runs answered by several engines" },
    { check: "Native decoding", passed: `${(v.decode["hdt:pass"] ?? 0) + (v.decode["cottas:pass"] ?? 0)} pass`, what: `${v.decode["hdt:pass"] ?? 0} HDT and ${v.decode["cottas:pass"] ?? 0} COTTAS artifacts decode to the triple count of the source graph` },
    { check: "Default SHACL profile", passed: `${v.shacl.validations} runs, ${v.shacl.violations} violations`, what: `On graphs up to ${D.facts.shaclMaxTriples} triples, ${secs(v.shacl.seconds[0])}–${secs(v.shacl.seconds[1])} per run` },
    { check: "Injected faults (queries / + default profile / + all profiles)", passed: `${m.queries.detected} / ${m.core.detected} / ${m.full.detected} of ${m.full.total}`, what: "Sensitivity of the validation layer to deliberate corruptions" },
  ];
  document.getElementById("evidenceTable").innerHTML = table(
    [{ key: "check", label: "Check" }, { key: "passed", label: "Result", num: true }, { key: "what", label: "What it establishes" }], rows);
  const real = D.fidelity.realGenome;
  const verdict = (s) => `<span class="status ${s === "PASS" ? "pass" : "fail"}">${esc(s === "PASS" ? "equal" : "mismatch")}</span>`;
  const sh = real.shacl;
  document.getElementById("realGenomeTable").innerHTML =
    `<p class="table-meta">${num(real.triples)} triples, validated on QLever with the ${esc(D.facts.useCaseVersion)} validator. ` +
    `Default shapes were validated in ${num(sh.batches)} record batches (${sh.minutes} min): ${num(sh.violations)} violations and ${num(sh.advisories)} non-blocking recommendations.</p>` +
    table([{ key: "query", label: "Question", format: (q) => pretty(q) },
      { key: "status", label: "SPARQL result and source-derived answer", html: (r) => verdict(r.status) }], real.queries);
  document.getElementById("fidelitySource").innerHTML = `Sources: <code>${esc(real.source)}</code>, the campaign's validation reports and <code>08_robustness/mutation_score*</code>.`;
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
    ...Object.keys(arms).map((arm) => ({ key: arm, label: `Scenario ${arm.slice(3)} VCFs`, num: true, format: cell })),
    { key: "clinvar", label: "ClinVar", num: true, format: cell },
  ], rows) + `<p class="table-meta">${esc(fill("Linked records of eligible records; the gene linker counts records within a gene span from {ensembl}. The MyVariant.info tier confirmed {myvariantShare} of the rsID links in the {myvariantGenomes} PGP files, replaying the {myvariantRequests} recorded service responses."))}</p>`;
  document.getElementById("usecaseSource").innerHTML = `Sources: ${Object.values(arms).map((a) => `<code>${esc(a.source)}</code>`).join(", ")} and <code>benchmarks/use_case/acmg</code>.`;
}

function renderRecords() {
  const rows = Object.entries(D.usecase.arms).flatMap(([arm, a]) => REQUESTERS.filter(([r]) => a.records[r]).map(([r, label]) => {
    const c = a.records[r];
    return { arm: armLabel(arm), requester: label, rdf: c.rdf, conventional: c.baseline, difference: c.rdf - c.baseline, agree: c.agree };
  }));
  const verdict = (r) => `<span class="status ${r.agree ? "pass" : "fail"}">${r.agree ? "equal" : `${r.difference > 0 ? "+" : ""}${num(r.difference)} in the RDF view`}</span>`;
  document.getElementById("recordsTable").innerHTML = table([
    { key: "arm", label: "Scenario" }, { key: "requester", label: "Requester" },
    { key: "rdf", label: "RDF release view", num: true, format: (v) => num(v) },
    { key: "conventional", label: "Conventional workflow", num: true, format: (v) => num(v) },
    { key: "agree", label: "Released records", html: verdict },
  ], rows) + `<p class="table-meta">${esc(fill("Records released to each requester. The additional records in {recordArmsDiffer} are symbolic structural-variant records in restricted genes, to which VCF-RDFizer {useCaseVersion} links no gene; no match changed."))}</p>`;
}

// --------------------------------------------------------------- break-even
const BREAK_EVEN_FIELDS = [
  ["conversion", "Conversion to gzip-framed N-Triples (s)"],
  ["index", "QLever indexing (s)"],
  ["parser", "Full cyvcf2 parse per question (s)"],
  ["sparql", "Indexed QLever query per question (s)"],
];
// The defaults are the paper's minimal setup (Section S9.4): the N-Triples-only rerun's conversion
// and QLever index, its median per-question parse and mean per-question query.
function defaultsForBreakEven() {
  const b = D.retrieval.breakEven;
  return { conversion: b.conversion, index: b.index, parser: b.scan, sparql: b.query };
}
function breakEven(v) {
  const saving = v.parser - v.sparql;
  return saving > 0 ? (v.conversion + v.index) / saving : Infinity;
}
function renderBreakEven() {
  const defaults = defaultsForBreakEven();
  const box = document.getElementById("breakEvenInputs");
  box.innerHTML = BREAK_EVEN_FIELDS.map(([key, label]) =>
    `<label>${esc(label)}<input type="number" min="0" step="any" id="be-${key}" value="${defaults[key].toFixed(key === "sparql" ? 2 : 1)}" /></label>`).join("") +
    `<label>&nbsp;<button type="button" id="be-reset">Reset to measured values</button></label>`;
  const update = () => {
    const v = Object.fromEntries(BREAK_EVEN_FIELDS.map(([k]) => [k, Number(document.getElementById(`be-${k}`).value)]));
    const n = breakEven(v);
    const out = document.getElementById("breakEvenResult");
    if (!Number.isFinite(n)) {
      out.innerHTML = "With these values the indexed query is not faster than a full parse, so the RDF setup is <strong>not amortized</strong> by query time.";
      return;
    }
    out.innerHTML = `Break-even after approximately <strong>${num(n, 0)} separately executed questions</strong> (${num(n, 1)}): ` +
      `${secs(v.conversion + v.index)} of additional RDF setup against a saving of ${secs(v.parser - v.sparql)} per question. ` +
      `The estimate assumes a full VCF parse for each question; one cyvcf2 pass answers all ${D.facts.questions} questions ` +
      `in ${secs(D.retrieval.batch.parser)}, so a single batch does not reach break-even. ` +
      `Including HDT construction in the setup, as in the base campaign, raises the estimate to ${D.facts.breakEvenWithHdt} questions.`;
  };
  box.addEventListener("input", update);
  document.getElementById("be-reset").addEventListener("click", () => {
    for (const [k] of BREAK_EVEN_FIELDS) document.getElementById(`be-${k}`).value = defaults[k].toFixed(k === "sparql" ? 2 : 1);
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
  const content = document.getElementById("focusContent");
  document.addEventListener("click", async (event) => {
    const id = event.target.closest("[data-expand]")?.dataset.expand;
    if (!id) return;
    document.getElementById("focusModalTitle").textContent = fill(CHARTS[id].title);
    modal.dataset.chart = id;
    content.innerHTML = "";
    modal.showModal();
    await renderChart(content, { id, big: true });
  });
  document.getElementById("focusClose").addEventListener("click", () => modal.close());
  // A click on the backdrop (the dialog element itself, outside its box) closes it too.
  modal.addEventListener("click", (event) => {
    const box = modal.getBoundingClientRect();
    const inside = event.clientX >= box.left && event.clientX <= box.right && event.clientY >= box.top && event.clientY <= box.bottom;
    if (event.target === modal && !inside) modal.close();
  });
  modal.addEventListener("close", () => { content.innerHTML = ""; delete modal.dataset.chart; });
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
    `Base campaign: VCF-RDFizer ${D.facts.campaignVersion}; linked workflow, retrieval reruns, consumer WGS validation run and converter comparison: ${D.facts.useCaseVersion}. ` +
    `Site built ${meta.builtAt.replace("T", " ").replace("+00:00", " UTC")}` +
    (meta.repoCommit ? ` from commit ${meta.repoCommit}.` : ".");
  if (meta.repoCommit) document.getElementById("commitLink").href = `${REPO}/tree/${meta.repoCommit}`;
  for (const el of document.querySelectorAll("[data-fill]")) el.textContent = D.facts[el.dataset.fill] ?? "N/A";
  renderKpis();
  renderEvidence();
  renderLinking();
  renderRecords();
  renderBreakEven();
  renderExplorer();
  renderHosts();
  document.getElementById("retrievalSource").textContent = "Sources: 18_converter_comparison; 04_scaling_records, " +
    "03_sample_representation, 01_storage_mode and 05_corpus_breadth, through scripts/figure_data.py; 13_query_cost and the " +
    "N-Triples-only rerun (vcf-bench-2/nt-only); 14_regional_access and 16_scale_retrieval from the v3.3.1 rerun.";
  wireModal();
  await renderAllCharts();
  darkQuery.addEventListener("change", renderAllCharts);
}

main().catch((error) => {
  document.getElementById("dataMeta").textContent = `Could not load the data: ${error.message}`;
  console.error(error);
});
