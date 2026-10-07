"""Which results make a shape batch non-conforming: severity counts and a sample."""
import collections, sys
from pathlib import Path
sys.path.insert(0, "/src/src/validation")
import validation_runner as V
b = Path("/work/batches")
ok, text = V._validate_shacl_task((b / "context.nt", sorted(b.glob("batch-*.nt"))[0],
                                   [Path("/data/shacl/vcf-core-vocabulary.shacl.ttl")],
                                   Path("/data/ontology/vcf-core-vocabulary.bundle.ttl")))
results = V.parse_shacl_results(text)
print("conforms", ok, collections.Counter(r["severity"] for r in results))
paths = collections.Counter(l.split("Result Path:",1)[1].strip() for l in text.splitlines() if "Result Path:" in l)
print(paths.most_common(10))
for r in results[:2]: print(r["text"][:900], "\n---")
