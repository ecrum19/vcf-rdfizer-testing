"""Q11 diagnosis: compare the graph's literal lexical forms with the VCF text, per record.
Reads the run's .nt.gz and the source slice; writes nothing but stdout."""
import gzip, re, sys, collections
nt, vcf = sys.argv[1], sys.argv[2]
V = "https://w3id.org/vcf-core/vocab#"
rec_p = {V+"chrom":"chrom", V+"pos":"pos", V+"recordId":"id", V+"ref":"ref", V+"alt":"alt", V+"hasCall":"call"}
call_p = {V+"qual":"qual", V+"filter":"filter", V+"infoRaw":"info"}
line_re = re.compile(r'^<([^>]*)> <([^>]*)> (.*) \.$')
lit_re = re.compile(r'^"((?:[^"\\]|\\.)*)"(?:\^\^<([^>]*)>|@[\w-]+)?$')
def unesc(s): return s.encode('latin-1','backslashreplace').decode('unicode_escape') if '\\' in s else s
recs = collections.defaultdict(dict); calls = collections.defaultdict(dict); dts = collections.Counter()
with gzip.open(nt, 'rt', encoding='utf-8') as f:
    for line in f:
        m = line_re.match(line.rstrip('\n'))
        if not m: continue
        s, p, o = m.groups()
        if p in rec_p:
            k = rec_p[p]
            if k == "call": recs[s]["call"] = o[1:-1]
            else:
                lm = lit_re.match(o); recs[s][k] = unesc(lm.group(1)) if lm else o
        elif p in call_p:
            lm = lit_re.match(o); k = call_p[p]
            calls[s][k] = unesc(lm.group(1)) if lm else o
            if k == "qual": dts[lm.group(2) if lm else "IRI"] += 1
print("records in graph:", len(recs), "qual datatypes:", dict(dts))
by_pos = {}
for r, d in recs.items():
    c = calls.get(d.get("call"), {})
    by_pos[(d.get("chrom"), d.get("pos"), d.get("ref"), d.get("alt"))] = (r, d, c)
diff = collections.Counter(); examples = collections.defaultdict(list); n = 0
with gzip.open(vcf, 'rt', encoding='utf-8') as f:
    for line in f:
        if line.startswith('#'): continue
        col = line.rstrip('\n').split('\t'); n += 1
        key = (col[0], col[1], col[3], col[4])
        if key not in by_pos: diff["record not found"] += 1; continue
        r, d, c = by_pos[key]
        graph = {"id": d.get("id"), "qual": c.get("qual"), "filter": c.get("filter"), "info": c.get("info")}
        for name, idx in (("id",2),("qual",5),("filter",6),("info",7)):
            if graph[name] != col[idx]:
                diff[name] += 1
                if len(examples[name]) < 4: examples[name].append((col[idx][:80], (graph[name] or "")[:80]))
print("VCF records:", n); print("fields differing (VCF text vs graph lexical form):", dict(diff))
for k, v in examples.items(): print(" ", k, v)
