"""Q11, part 2: recompute the oracle's buckets with QUAL written canonically, and
compare with QLever's actual buckets. The record IRI comes from the graph (by key)."""
import gzip, hashlib, json, re, sys, collections
from decimal import Decimal
nt, vcf, raw = sys.argv[1:4]
V = "https://w3id.org/vcf-core/vocab#"
want = {V+"chrom", V+"pos", V+"ref", V+"alt"}
line_re = re.compile(r'^<([^>]*)> <([^>]*)> "((?:[^"\\]|\\.)*)"')
f = collections.defaultdict(dict)
with gzip.open(nt, 'rt', encoding='utf-8') as h:
    for line in h:
        m = line_re.match(line)
        if m and m.group(2) in want: f[m.group(1)][m.group(2)[len(V):]] = m.group(3)
iri = {(d["chrom"], d["pos"], d["ref"], d["alt"]): r for r, d in f.items() if len(d) == 4}
def strip0(q):
    if q == "." or "." not in q or "e" in q.lower(): return q
    q = q.rstrip("0"); return q[:-1] if q.endswith(".") else q
def keep1(q):
    s = strip0(q); return s + ".0" if q != "." and "." in q and "." not in s and "e" not in q.lower() else s
variants = {"as written": lambda q: q, "trailing zeros stripped": strip0, "one decimal kept": keep1}
counts = {k: collections.Counter() for k in variants}; changed = collections.Counter()
with gzip.open(vcf, 'rt', encoding='utf-8') as h:
    for line in h:
        if line.startswith('#'): continue
        c = line.rstrip('\n').split('\t'); r = iri[(c[0], c[1], c[3], c[4])]
        for k, fn in variants.items():
            q = fn(c[5]); changed[k] += q != c[5]
            b = hashlib.sha256("\x1f".join([r, c[0], c[1], c[2], c[3], c[4], q, c[6], c[7]]).encode()).hexdigest()[:2]
            counts[k][b] += 1
actual = {row["bucket"]["value"] if isinstance(row["bucket"], dict) else row["bucket"]:
          int(row["recordCount"]["value"] if isinstance(row["recordCount"], dict) else row["recordCount"])
          for row in json.load(open(raw))["results"]["bindings"]}
for k in variants:
    diff = sum(abs(counts[k][b] - actual.get(b, 0)) for b in set(counts[k]) | set(actual))
    print(f"{k:26s} QUAL values changed: {changed[k]:6d}   bucket differences vs QLever: {diff}")
