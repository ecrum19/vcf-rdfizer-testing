# VCF-RDFizer v3.3.1 rerun on vcf-bench-2 (2026-10-08 to 2026-10-09)

The same release and harness as vcf-bench-1 (see [its README](../../vcf-bench-1/v331-rerun/README.md)),
driver role `bench2`.

| Job | What | Wall | Result |
|---|---|---|---|
| `bridge` | v3.3.1 converts the 100,000-record HG005 slice to N-Triples; its sorted triples are compared with the v3.1.0 N-Triples-only rerun's | 3 min | Identical: 17,098,746 triples, sorted SHA-256 `661578e7...94ed` for both (`bridge/sorted_triples.sha256`). Both releases write the same graph. |
| `consumer_wgs` | The consumer WGS validation run (first 250,000 records of NG131FQA1I) with the v3.3.1 validator on QLever, default shapes | 1.8 h | PASS: every comparison and preflight check agrees, and SHACL reports 0 violations (`results/consumer_wgs__NG131FQA1I__first250000/out/run_metrics/*/reports/validation/`) |
| `arm3` | Experiment 17, Arm 3: the complete HG005 VCF | 6.7 h | Both routes agree on every carrier list and record count; the clinical view holds all 3,887,810 records |
| `arm4` | Experiment 17, Arm 4: NB72462M under layered consent | in progress | Archived here when it completes |

## Arm 4 so far

- **First run.** Derive, convert, link, and baseline completed. The run then stopped at govern's disk pre-check, which needs about 55 GB; 48 GB was free.
- **Second attempt.** The `bench2-arm4-resume` role (the stages `govern query compare`; see the driver) ran with 56 GB free. It filled the disk while indexing the first view.
- **Space cleared.** With the user's approval, space was cleared on the host; every removal is logged in `~/vrdev-test/deleted-2026-10-08.txt` there. Arm 3's graphs were among them, removed after its run records were copied off.
- **Running now.** The resume was restarted at 05:43 UTC on 2026-10-09 with 94 GB free.
- **Driver copies.** `run_v331.before-resume.sh` is the driver as it first ran; `run_v331.sh` adds the stage override and the resume role.

## Not included

The 6 files listed in [`excluded-files.tsv`](excluded-files.tsv): the bridge's and the consumer run's
graphs, and Arm 3's `decisions.csv` and `records.tsv`. They stay on the host. Their SHA-256 is added
once Arm 4 has finished; hashing them now would compete with its timed stages.
