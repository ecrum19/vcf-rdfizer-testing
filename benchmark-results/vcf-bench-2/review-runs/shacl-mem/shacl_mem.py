"""Peak memory of one shape batch, at two sizes, inside the image."""
import gzip, resource, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, "/opt/vcf-rdfizer/validation")
import validation_runner as V

work = Path("/work"); graph = work / "g.nt"
if not graph.exists():
    with gzip.open("/graph/NG131FQA1I_first250000.nt.gz", "rb") as src, graph.open("wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 24)
batches = work / "batches"
if not batches.exists():
    batches.mkdir()
    t = time.time(); context, parts = V.write_shacl_batches(graph, batches, 2147)
    print(f"split into {len(parts)} batches in {time.time() - t:.0f} s", flush=True)
parts = sorted(batches.glob("batch-*.nt")); context = batches / "context.nt"
four = work / "four.nt"
if not four.exists():
    with four.open("wb") as out:
        for p in parts[:4]:
            out.write(p.read_bytes())
shapes = [Path("/data/shacl/vcf-core-vocabulary.shacl.ttl")]
ontology = Path("/data/ontology/vcf-core-vocabulary.bundle.ttl")
for label, batch in (("1 batch", parts[0]), ("4 batches", four)):
    lines = sum(1 for _ in batch.open()) + sum(1 for _ in context.open())
    code = ("import resource,sys,time; sys.path.insert(0,'/opt/vcf-rdfizer/validation'); import validation_runner as V; "
            "from pathlib import Path; t=time.time(); "
            f"ok,_=V._validate_shacl_task((Path('{context}'),Path('{batch}'),[Path('{shapes[0]}')],Path('{ontology}'))); "
            "print(ok, round(time.time()-t), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    print(label, f"{lines:,} triples ->", out.stdout.strip() or out.stderr.strip()[-400:], flush=True)
