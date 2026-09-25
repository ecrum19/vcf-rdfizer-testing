# Pulling and aggregating the results

Exact steps to collect the BioMedSem run from both VMs into one dataset.
Run every command **from your laptop**, in `~/PhD_Things/vcf-rdfizer-testing`,
unless a step says otherwise. Nothing here writes to the VMs.

The VMs sit behind a jump host, so every remote command uses:

```bash
BENCH1="-J proxy@bastion2.slices-be.eu ubuntu@10.10.209.2"
BENCH2="-J proxy@bastion2.slices-be.eu ubuntu@10.10.211.185"
```

Re-derive the IPs if the experiment is recreated:
`slices bi ssh vcf-bench-1 --experiment realfed --proxy on --show command`
(needs `source ~/slices-venv/bin/activate`, and `ssh-add ~/.ssh/id_ed25519-2`).

> **If `ssh -J` fails with `administratively prohibited: open failed`**, the
> bastion is not currently forwarding to the VMs. That is a SLICES-side toggle,
> not a key problem. Every `ssh`/`rsync`/`scp` below then fails until you
> re-enable it. Run this once per VM first, and keep the session going:
>
> ```bash
> source ~/slices-venv/bin/activate
> for vm in vcf-bench-1 vcf-bench-2; do
>   slices bi ssh "$vm" --experiment realfed --proxy on -- -o BatchMode=yes 'hostname'
> done
> ```
>
> If plain `ssh -J` still refuses afterwards, run remote commands through the
> CLI instead — arguments after `--` are passed straight to ssh:
> `slices bi ssh vcf-bench-1 --experiment realfed --proxy on -- -o BatchMode=yes 'CMD'`.
> For `rsync`, that grant has to be active; there is no CLI passthrough for it.

---

## Step 0 — confirm both runs are actually finished

Do not pull a live run: a cell without `bench.json` is a half-written cell.

```bash
for H in "$BENCH1 bench-1" "$BENCH2 bench-2"; do
  set -- $H; host="${@: -1}"; conn="${*:1:$#-1}"
  echo "== $host"
  ssh $conn 'pgrep -af "run_all|bms_share|vcf_rdfizer\.py" || echo "  idle"
             tail -2 ~/vcf-rdfizer-testing/benchmarks_outputs/share.log'
done
```

**Proceed only when both print `idle` and a `share finished` line.** If a host
is still running, wait; `share.log` names the experiment in progress.

Then check nothing failed silently:

```bash
for conn in "$BENCH1" "$BENCH2"; do
  ssh $conn 'python3 - <<PY
import json, glob, os
root = os.path.expanduser("~/vcf-rdfizer-testing/benchmarks_outputs")
bad = skip = tot = 0
for p in glob.glob(os.path.join(root, "*", "*", "bench.json")):
    d = json.load(open(p)); tot += 1
    if d.get("skipped"): skip += 1
    elif d.get("exit_code"): bad += 1; print("  FAIL", d["experiment"], d["cell"])
print("  %s: %d cells, %d failed, %d skipped" % (os.uname().nodename, tot, bad, skip))
PY'
done
```

A few skips are expected and legitimate (the cohort-scale guard, and
`rules__custom` unless `BM_CUSTOM_RULES` was set). Failures are not — read
`<cell>/stderr.log` before aggregating, because a failed cell still produces a
row and will silently enter your tables.

---

## Step 0b — re-capture provenance on each host

Each host records `00_environment/provenance.<host>.<commit>.json` when it starts
a share. bench-1 changes commit at its `04 -> 07` handover, so run this once both
hosts are idle to capture the final state. Files are named per host **and**
commit, so nothing is overwritten and every state is kept:

```bash
for ip in 10.10.209.2 10.10.211.185; do
  ssh -J proxy@bastion2.slices-be.eu ubuntu@$ip \
    'python3 ~/vcf-rdfizer-testing/benchmarks/analysis/provenance.py'
done
```

Expect two files per host if that host changed commit mid-run, one if it did not.
All of them ship with the dataset.

---

## Step 1 — pull both results trees into one directory

```bash
mkdir -p merged
rsync -av --info=progress2 -e "ssh -J proxy@bastion2.slices-be.eu" \
  ubuntu@10.10.209.2:vcf-rdfizer-testing/benchmarks_outputs/ merged/
rsync -av --info=progress2 -e "ssh -J proxy@bastion2.slices-be.eu" \
  ubuntu@10.10.211.185:vcf-rdfizer-testing/benchmarks_outputs/ merged/
```

Two hosts into one directory is safe **because no experiment ran on both**.
Verify that rather than trusting it — see Step 3.

Also pull the §1 archive from bench-1. It is the old-tool storage-mode data
(n=5 on `test-larger`), kept separate because its cell labels collide with the
profile's:

```bash
rsync -av -e "ssh -J proxy@bastion2.slices-be.eu" \
  ubuntu@10.10.209.2:vcf-rdfizer-testing/benchmarks_outputs__tool8b1b4a8/ \
  archive_tool8b1b4a8/
```

Finally pull the set-aside trees. The handover watchers **never delete**: data
that must stay out of the merge is moved to a timestamped sibling instead. These
are not results, but they are the record of what actually ran, so they belong in
the Zenodo tarball:

```bash
for ip in 10.10.209.2 10.10.211.185; do
  for d in benchmarks_outputs__offsplit benchmarks_outputs__partial; do
    rsync -av -e "ssh -J proxy@bastion2.slices-be.eu" \
      "ubuntu@$ip:vcf-rdfizer-testing/$d/" "setaside/$d/" 2>/dev/null || true
  done
  rsync -av -e "ssh -J proxy@bastion2.slices-be.eu" \
    --include='benchmarks_outputs_calibration__*' --include='*/' --exclude='*' \
    "ubuntu@$ip:vcf-rdfizer-testing/" "setaside/calibration_snapshots/" 2>/dev/null || true
done
```

`__offsplit/` holds experiments that were started on the wrong host before the
split was rebalanced; `__partial/` holds cells with no `bench.json`, i.e. cells
interrupted mid-flight. Neither may enter `merged/`.

---

## Step 2 — rescue the environment manifests (do this before anything else)

**Both hosts write `00_environment/manifest.json`, so the second rsync
overwrites the first.** One host's environment record is already lost at this
point unless you pull them separately. Do that now:

```bash
mkdir -p merged/00_environment
for pair in "10.10.209.2 bench-1" "10.10.211.185 bench-2"; do
  set -- $pair
  scp -o ProxyJump=proxy@bastion2.slices-be.eu \
    ubuntu@$1:vcf-rdfizer-testing/benchmarks_outputs/00_environment/manifest.json \
    merged/00_environment/manifest.$2.json
done
ls merged/00_environment/
```

You want `manifest.bench-1.json` **and** `manifest.bench-2.json`. The
single `manifest.json` left by rsync is one host's, arbitrarily; delete it so
nobody cites it as if it described the whole run:

```bash
rm -f merged/00_environment/manifest.json
```

---

## Step 3 — verify the merge before you compute anything

```bash
python3 - <<'PY'
import json, glob, collections
rows = [json.load(open(p)) for p in glob.glob("merged/*/*/bench.json")]
byexp, bycommit = collections.defaultdict(set), collections.defaultdict(set)
for r in rows:
    if r.get("skipped"): continue
    byexp[r["experiment"]].add(r.get("host", "UNKNOWN"))
    bycommit[r["experiment"]].add(str(r.get("tool_commit", "?"))[:8])
print("%-26s %-14s %s" % ("experiment", "host", "tool commit(s)"))
split = False
for e in sorted(byexp):
    hs, cs = sorted(byexp[e]), sorted(bycommit[e])
    print("  %-24s %-14s %s" % (e, ", ".join(hs), ", ".join(cs)))
    if len(hs) > 1: split = True
print()
print("cells:", len(rows))
print("hosts seen:", sorted({r.get("host","UNKNOWN") for r in rows}))
print("image TAGS (not unique -- see below):",
      sorted({r.get("image_ref","?") for r in rows if not r.get("skipped")}))
assert not split, "an experiment spans two hosts -- its internal comparisons are confounded"
assert "UNKNOWN" not in {r.get("host","UNKNOWN") for r in rows}, "a cell has no host"
print("\nOK: every experiment lives on exactly one host")
PY
```

**The one hard rule is the assert: no experiment may span two hosts.** Both VMs
enforce it at handover by moving any foreign experiment out of
`benchmarks_outputs/` before that host starts its share.

### Two tool commits are expected

This is a documented property of the run, not a fault. The dataset contains both
`025fb7d` and `be658a2`:

| commit | cells |
| --- | --- |
| `025fb7d` | bench-1 `04`; bench-2 `01` and the `s1…s1024` rungs of `03` |
| `be658a2` | bench-2 `03` top rung onward + `05 06 09 10 13`; bench-1 `07 08 12` |
| `a3679e1` | bench-1 `11` (re-run on the fixed oracle), `09` and `13` |

`11_covering_set` is deliberately a third commit. On `be658a2` its row 2
(`--info-representation raw`) could not pass validation: the oracle was never
told how the graph was built and scored every run against a structured
expectation. That failure also aborted rows 3-6, so the experiment recorded 2 of
6 rows. It was re-run on `a3679e1` (merged to main as `d44b3de`), which carries the
fix. That re-run then exposed a second problem — the six-row table never
actually covered every option pair — so the table is now ten rows and `11`
records 10 of 10, all exiting 0.

Two superseded runs are kept and must **not** enter `merged/`:
`benchmarks_outputs__superseded/11_covering_set__buggy_oracle__*` (2 cells, the
broken oracle) and `.../11_covering_set__6row__*` (6 cells, valid but a narrower
table).

Nothing else needed re-running, and this was checked rather than assumed: the
bug only bites when a cell both validates **and** uses raw INFO. Across every
recorded `command` on both hosts, exactly one cell met both conditions.
`07_representation_axes` uses raw in 6 cells but never validates;
`12_modes_smoke` validates but never uses raw.

Why they combine safely:

- The commits differ in `vcf_rdfizer.py` by **one docstring hunk and no
  executable line**, so conversion timing cannot depend on which one ran.
- They differ substantively in `src/validation/validation_runner.py`
  (`ad4c6c6`, the comunica warm-up retry). **Every experiment that runs
  validation — `06 09 11 12 13` — is on `be658a2`**, so no validation number is
  ever compared across the boundary.
- `03` is the only experiment whose cells straddle it, and `03` runs
  `--mode full --representations hdt` with no validation at all.

Verify that rather than trusting the table:

```bash
cd ~/PhD_Things/vcf-rdfizer
git diff --numstat 025fb7d be658a2 -- vcf_rdfizer.py   # expect: 6  1  (docstring)
git diff 025fb7d be658a2 -- vcf_rdfizer.py \
  | grep -E '^[+-]' | grep -vE '^[+-][+-]|^[+-][[:space:]]*(\*|#|"""|$)'
# expect: only prose lines. Any real code here invalidates the argument above.
```

### The image tag is not a unique identifier

Both hosts tagged their image `vcf-rdfizer:local-025fb7d`, but each built it
independently, about five hours apart:

| host | image id | built |
| --- | --- | --- |
| bench-1 | `sha256:b645120b7270…` | 2026-09-13 19:17 +02:00 |
| bench-2 | `sha256:0082fe2cf42f…` | 2026-09-13 14:21 +02:00 |

So `image_ref` in `bench.json` says nothing about which bits ran, and must not be
cited as provenance. The real record is
`merged/00_environment/provenance.<host>.<commit>.json` — image digest, full
layer list, both repo heads, kernel, CPU and RAM, one file per host per commit.
**Cite the digest.** The manuscript should say the image was built per host from
the stated commit and that the builds are not bit-reproducible.

If you want stronger evidence that the two images contain the same code, compare
the installed tree directly — do this only when no cell is timing:

```bash
for ip in 10.10.209.2 10.10.211.185; do
  ssh -J proxy@bastion2.slices-be.eu ubuntu@$ip \
    "docker run --rm --entrypoint sh vcf-rdfizer:local-025fb7d -c \
     'find / -name \"*.py\" -path \"*vcf*\" -type f 2>/dev/null | sort | xargs sha256sum | sha256sum'"
done
```

Equal digests mean the two images carry identical Python sources and the only
difference is build metadata.

Three things the check catches, all of which silently corrupt results:

- **an experiment on both hosts** — its within-experiment comparison becomes
  cross-hardware, the one thing the split must never produce
- **cells with no `host`** — produced before host recording existed, so they
  cannot be attributed
- **a commit split other than the one tabled above** — that means something moved
  mid-run that nobody planned. Find the cells before reporting anything.

## Step 4 — the calibration check

Each host ran an identical `12_modes_smoke` cell. Compare them, and **report
the number** rather than asserting the hosts are equivalent:

```bash
for pair in "10.10.209.2 bench-1" "10.10.211.185 bench-2"; do
  set -- $pair
  ssh -J proxy@bastion2.slices-be.eu ubuntu@$1 'python3 - <<PY
import json, glob, os
for p in glob.glob(os.path.expanduser("~/vcf-rdfizer-testing/benchmarks_outputs_calibration/12_modes_smoke/*/bench.json")):
    d = json.load(open(p))
    if d.get("cell") == "phaseA_convert":
        print("  %-10s phaseA_convert %6.1fs" % (d.get("host"), d.get("wrapper_wall_seconds", 0)))
PY'
done
```

Each host may have **more than one** calibration tree. The live one is
`benchmarks_outputs_calibration/`; snapshots taken before a handover are
`benchmarks_outputs_calibration__pre_rebalance_<stamp>/` (bench-2) and
`benchmarks_outputs_calibration__025fb7d_<stamp>/` (bench-1). The snapshots are
the `025fb7d` calibration, the live tree the `be658a2` one — so you can compare
hosts at matched commits instead of assuming the commit made no difference.

Within a few percent: cross-experiment comparisons are fine. Further apart:
they still stand *within* an experiment, but any figure putting a bench-1
experiment beside a bench-2 one needs the difference stated.

---

## Step 5 — build the tidy dataset

`BM_RESULTS` is honoured by the analysis scripts, so point it at `merged/`:

```bash
export BM_RESULTS="$PWD/merged"
python3 benchmarks/analysis/collect_metrics.py --all
```

This writes `merged/<experiment>/tidy.csv` and `tidy.json`. It reads only
`bench.json` and `out/run_metrics/**`, so pruned artifact trees do not matter.

Then the per-claim outputs:

```bash
# C1 -- equivalence, both metrics. State which you pre-committed to.
python3 benchmarks/analysis/equivalence.py 01_storage_mode --margin 0.10
python3 benchmarks/analysis/equivalence.py 01_storage_mode --margin 0.10 \
        --metric wrapper_wall_seconds

# C2 -- structure ratio across the sample ladder, and the S=1 equivalence
python3 benchmarks/analysis/fit_scaling.py 03_sample_representation \
        --x samples --y triples --group mode --cell-filter __structure
python3 benchmarks/analysis/equivalence.py 03_sample_representation \
        --cell-filter s1__ --margin 0.10

# C3 -- records slope
python3 benchmarks/analysis/fit_scaling.py 04_scaling_records --x records --y wall_seconds

# C4 -- breadth and input descriptions
python3 benchmarks/analysis/describe_inputs.py --corpus
python3 benchmarks/analysis/datasets.py corpus 05_corpus_breadth
```

---

## Step 6 — the two things to check in the output

**Truncated corpus cells.** §3.2 ran most files truncated to 250k records;
their labels end `__first250000`. One file was converted whole. A breadth table
that does not distinguish them overstates the claim:

```bash
python3 -c "
import json,glob
for p in sorted(glob.glob('merged/05_corpus_breadth/*/bench.json')):
    d=json.load(open(p))
    if d.get('skipped'): print('  SKIP  ', d['cell']); continue
    print('  %-8s %s' % ('TRUNC' if '__first' in d['cell'] else 'WHOLE', d['cell']))"
```

**The §1 archive is a different tool.** `archive_tool8b1b4a8/` was produced on
`8b1b4a8`, before the VCF 4.5 accessor work; `merged/` is all `025fb7d`. Do not
combine them into one table. The archive is the stronger §1 evidence (n=5 on
`test-larger` plus an HG005 pair) and remains usable because the claim is a
*ratio* and a tool change moves both arms together — but say which tool
produced which number.

---

## The optional experiments are not part of this

14, 15 and 16 are in no profile and are not part of the manuscript campaign, so
none of the steps above apply to them. Two things to remember anyway:

* **Do not archive the scale store.** `BM_SCALE_STORE` holds tens of gigabytes
  of built graphs. Archive each `manifest.json` instead — it records the source
  VCF digest, the triple count, every artifact's sha256, and the tool commit
  and image digest that produced it, which is what makes the store
  reproducible. The artifacts themselves are regenerable from that record, in
  hours.
* **Do not merge 16's timings into the campaign dataset.** `q01`-`q13` are
  byte-identical to v3.1.0 and so are comparable with Figure 6, but the runs
  are `TIMING_ONLY` by construction — they carry no validation verdict, and a
  dataset that mixes them with validated cells would report a pass rate over
  cells that never claimed one. `analysis/scale_retrieval.py` keeps them in
  their own file for that reason.

## Step 7 — archive for Zenodo

`merged/` after Step 5 is already the right shape: the artifacts were pruned
and are regenerable from each cell's recorded argv and `tool_commit`, while the
timing, staging and manifest data — the part that is *not* regenerable — is all
present and small.

```bash
tar czf biomedsem-results-$(date +%Y%m%d).tar.gz \
    merged/ archive_tool8b1b4a8/ setaside/ \
    benchmarks/RUN_PLAN.md benchmarks/AGGREGATION.md benchmarks/README.md
du -sh biomedsem-results-*.tar.gz
```

Include `RUN_PLAN.md`, `AGGREGATION.md` and `README.md`: they record which host
ran what, which tool commit and image digest, and why the corpus was truncated.
Without them the numbers are not reproducible.

`setaside/` is included deliberately. It holds the cells that were moved out of
the merge — work started on the wrong host before the split was rebalanced, and
cells interrupted mid-flight. None of it is a result, and none of it enters a
table, but shipping it is what makes the claim "no experiment spans two hosts"
checkable by a reader instead of merely asserted.
