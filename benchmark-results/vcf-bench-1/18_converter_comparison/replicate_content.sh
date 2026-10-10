#!/usr/bin/env bash
# Replicate content check for experiment 18's reported run: VCF-RDFizer's sorted triples per
# replicate, and which BioInterchange JSON-LD lines differ between replicates.
R=~/vrdev-test/conv/run-e3743590/results/18_converter_comparison
T=~/vrdev-test/conv/run-e3743590/work/tmp; mkdir -p "$T"
OUT=$R/replicate-content.txt; : > "$OUT"
for n in HG005_GRCh38_r100000 1000G_10000r_s16; do
  for r in 1 2 3; do
    f=$R/convert__vcf-rdfizer__${n}__r$r/out/$n/$n.nt.gz
    echo "vcf-rdfizer $n r$r sorted-triples-sha256 $(zcat "$f" | LC_ALL=C sort -S 2G -T "$T" | sha256sum | cut -c1-64)" >> "$OUT"
  done
done
for n in HG005_GRCh38_r100000 1000G_10000r_s16; do
  a=$R/convert__biointerchange__${n}__r1/out/graph.ldj
  for r in 2 3; do
    b=$R/convert__biointerchange__${n}__r$r/out/graph.ldj
    echo "biointerchange $n r1-vs-r$r differing-lines $(diff "$a" "$b" | grep -c '^<') of $(wc -l < "$a")" >> "$OUT"
  done
  diff "$a" "$R/convert__biointerchange__${n}__r2/out/graph.ldj" | grep '^<' | cut -c1-220 | head -4 | sed "s/^/  $n example: /" >> "$OUT"
done
echo DONE >> "$OUT"
