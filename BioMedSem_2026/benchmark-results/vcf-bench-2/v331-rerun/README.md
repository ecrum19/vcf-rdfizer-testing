# VCF-RDFizer v3.3.1 rerun on vcf-bench-2 (2026-10-08 to 2026-10-10)

The same release and harness as vcf-bench-1 (see [its README](../../vcf-bench-1/v331-rerun/README.md)),
driver role `bench2`.

| Job | What | Wall | Result |
|---|---|---|---|
| `bridge` | v3.3.1 converts the 100,000-record HG005 slice to N-Triples; its sorted triples are compared with the v3.1.0 N-Triples-only rerun's | 3 min | Identical: 17,098,746 triples, sorted SHA-256 `661578e7...94ed` for both (`bridge/sorted_triples.sha256`). Both releases write the same graph. |
| `consumer_wgs` | The consumer WGS validation run (first 250,000 records of NG131FQA1I) with the v3.3.1 validator on QLever, default shapes | 1.8 h | PASS: every comparison and preflight check agrees, and SHACL reports 0 violations (`results/consumer_wgs__NG131FQA1I__first250000/out/run_metrics/*/reports/validation/`) |
| `arm3` | Experiment 17, Arm 3: the complete HG005 VCF | 6.7 h | Both routes agree on every carrier list and record count; the clinical view holds all 3,887,810 records |
| `arm4`, `arm4_resume` | Experiment 17, Arm 4: the complete NB72462M VCF under layered consent, four requesters | 1.8 h, then 19.1 h | Both routes agree on every carrier list and record count; every view passed its check (`results/17_use_case_acmg__layered/comparison.json`). See below |

## Arm 4

The result matches the pre-release run on vcf-bench-3 (`../../vcf-bench-3/use-case/17_use_case_acmg__layered/`)
in every count:

| Requester | Matches | Records released | Records withheld |
| --- | ---: | ---: | ---: |
| All (no policy) | 1,382 | | |
| own physician (OP) | 1,382 | 5,063,417 | 0 |
| clinical (CC) | 1,382 | 5,063,411 | 6 |
| cardio (DS) | 722 | 6,397 | 5,057,020 |
| biobank (GRU) | 983 | 5,060,897 | 2,520 |

The converted graph (1,209,739,110 triples) and the link counts are the same too. Only timings differ, as
expected on another host:
- each view took 55-70 min to write (pre-release run: 55-74 min);
- queries took 226-233 s, and 187 s for the 6,397-record DS view (pre-release run: 181-184 s and 146 s).

How it ran:
- **First run (`arm4`).** Derive, convert, link and baseline completed. The run then stopped at govern's disk
  pre-check, which needs about 55 GB; 48 GB was free (exit 1).
- **First resume** (`attempt1-arm4-resume-diskfull/`). The `bench2-arm4-resume` role runs the stages
  `govern query compare`; see the driver. It started with 56 GB free and filled the disk while indexing the
  first view.
- **Space cleared.** With the user's approval, space was cleared on the host; every removal is logged in
  `~/vrdev-test/deleted-2026-10-08.txt` there. Arm 3's graphs were among them, removed after its run records
  were copied off.
- **Second resume** (`attempt2-arm4-resume-stopped/`). It was stopped at the start of govern, by request, to
  clear more space first.
- **Reported resume.** It restarted at 05:43 UTC on 2026-10-09 with 94 GB free, and finished with exit 0 at
  00:47 UTC on 2026-10-10. Its cells and the first run's derive, convert, link and baseline cells are in
  `results/17_use_case_acmg__layered/`.
- **Driver copies.** `run_v331.before-resume.sh` is the driver as it first ran; `run_v331.sh` adds the stage
  override and the resume role.

## Not included

The 20 files listed in [`excluded-files.tsv`](excluded-files.tsv), with size and SHA-256. They stay on
the host:
- the bridge's and the consumer run's graphs;
- Arm 3's `decisions.csv` and `records.tsv`;
- Arm 4's converted graphs, link sets, release views, oracle graph, `decisions.csv` and `records.tsv`.

Arm 3's own graphs were removed from the host to make room for Arm 4, after its run records had been archived.
