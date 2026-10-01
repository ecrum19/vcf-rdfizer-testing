#!/usr/bin/env bash
# Fetch arm 2's inputs: the ACMG regions of the 1000 Genomes high-coverage
# panel, for the cohort's samples only, then one VCF per participant.
#
# Runs INSIDE the VCF-RDFizer image (it needs bcftools):
#
#   fetch_cohort.sh <cohort.json> <regions.bed> <out-dir>
#
# The panel is read remotely through its tabix index, so only the index and the
# blocks overlapping the regions are transferred. One chromosome at a time, one
# connection, and resumable: a chromosome already fetched is not fetched again.
# `cohort.source.panel` is a template with {chrom}; `panel_overrides` names any
# chromosome whose file breaks the pattern (chrX's carries ".v2"). Either may be
# a local path, which is what the tests use.
#
# Each participant's file keeps only the ALT alleles that participant carries
# (-a) and only sites where they carry one (-c1), as a per-person deposit would.

set -euo pipefail

case_json="$1" bed="$2" out="$3"
mkdir -p "$out/chrom"
python3 - "$case_json" "$bed" "$out" <<'PY'
import json, sys
case, bed, out = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
source = case["cohort"]["source"]
with open(f"{out}/samples.txt", "w") as handle:
    handle.writelines(p["id"] + "\n" for p in case["participants"])
with open(f"{out}/panels.tsv", "w") as handle:
    for chrom in sorted({line.split("\t")[0] for line in open(bed) if line.strip()}):
        url = source.get("panel_overrides", {}).get(chrom, source["panel"].replace("{chrom}", chrom))
        handle.write(f"{chrom}\t{url}\n")
PY

# htslib saves a remote file's index in the working directory.
cd "$out/chrom"
for chrom in $(cut -f1 "$bed" | sort -uV); do
  [[ -s "$chrom.vcf.gz" ]] && continue
  awk -v c="$chrom" -F'\t' '$1 == c' "$bed" > "$chrom.bed"
  bcftools view -R "$chrom.bed" -S "$out/samples.txt" --force-samples -Oz -o "$chrom.vcf.gz.part" \
    "$(awk -v c="$chrom" -F'\t' '$1 == c { print $2 }' "$out/panels.tsv")"
  mv "$chrom.vcf.gz.part" "$chrom.vcf.gz"
  echo "fetch_cohort: $chrom"
done

cd "$out"
if [[ ! -s cohort.acmg.vcf.gz ]]; then
  # shellcheck disable=SC2046
  bcftools concat -Oz -o cohort.acmg.vcf.gz.part $(cut -f1 "$bed" | sort -uV | sed 's#.*#chrom/&.vcf.gz#')
  mv cohort.acmg.vcf.gz.part cohort.acmg.vcf.gz
  bcftools index -f cohort.acmg.vcf.gz
fi
while read -r sample; do
  [[ -s "$sample.vcf.gz" ]] && continue
  bcftools view -s "$sample" -a -c1 -Oz -o "$sample.vcf.gz.part" cohort.acmg.vcf.gz
  mv "$sample.vcf.gz.part" "$sample.vcf.gz"
done < samples.txt
echo "fetch_cohort: $(wc -l < samples.txt) participants, $(bcftools view -H cohort.acmg.vcf.gz | wc -l) sites"
