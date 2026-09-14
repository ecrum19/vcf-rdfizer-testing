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
byexp = collections.defaultdict(set)
for r in rows:
    if not r.get("skipped"):
        byexp[r["experiment"]].add(r.get("host", "UNKNOWN"))
print("experiment                 hosts")
split = False
for e in sorted(byexp):
    hs = sorted(byexp[e]); print("  %-26s %s" % (e, ", ".join(hs)))
    if len(hs) > 1: split = True
print()
print("cells:", len(rows))
print("hosts seen:", sorted({r.get("host","UNKNOWN") for r in rows}))
print("tool commits:", sorted({r.get("tool_commit","?")[:8] for r in rows if not r.get("skipped")}))
print("images:", sorted({r.get("image_ref","?") for r in rows if not r.get("skipped")}))
assert not split, "an experiment spans two hosts -- its internal comparisons are confounded"
assert "UNKNOWN" not in {r.get("host","UNKNOWN") for r in rows}, "a cell has no host"
print("\nOK: every experiment lives on exactly one host")
PY
```

Three things this catches, all of which silently corrupt results:

- **an experiment on both hosts** — its within-experiment comparison is then
  cross-hardware, which is the one thing the split must never do
- **cells with no `host`** — produced before host recording existed, so they
  cannot be attributed
- **more than one `tool_commit` or `image_ref`** — a dataset spanning two
  builds. Expect exactly one of each; if not, find out which cells differ
  before reporting anything

---

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

## Step 7 — archive for Zenodo

`merged/` after Step 5 is already the right shape: the artifacts were pruned
and are regenerable from each cell's recorded argv and `tool_commit`, while the
timing, staging and manifest data — the part that is *not* regenerable — is all
present and small.

```bash
tar czf biomedsem-results-$(date +%Y%m%d).tar.gz \
    merged/ archive_tool8b1b4a8/ benchmarks/RUN_PLAN.md benchmarks/README.md
du -sh biomedsem-results-*.tar.gz
```

Include `RUN_PLAN.md` and `README.md`: they record which host ran what, which
tool commit, and why the corpus was truncated. Without them the numbers are not
reproducible.
