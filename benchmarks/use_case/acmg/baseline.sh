#!/usr/bin/env bash
# The conventional route: bcftools plus a consent script, no RDF.
#
# Runs INSIDE the VCF-RDFizer image (it needs bcftools):
#
#   baseline.sh <derived-dir> <out-dir> <use_case.json> <ids...>
#
# Each step is what a bioinformatician would write for this question:
#
#   1. rename contigs to ClinVar's naming (chr1 -> 1), where the file differs
#   2. annotate each genome with ClinVar's CLNSIG, CLNREVSTAT and GENEINFO,
#      matching CHROM, POS, REF and ALT exactly
#   3. keep FILTER PASS or missing, and genotypes carrying the ALT
#   4. query one row per carrier genotype
#   5. apply the significance, review-status, gene and consent rules
#      (baseline_carriers.py)
#   6. with a panel (arm 2), also list the carriers of variants the panel
#      calls rare, looking each one's frequency up by CHROM, POS, REF and ALT
#
# It reads the derived inputs and use_case.json, never the RDF or the policy,
# so its agreement with the RDF route is evidence rather than an echo.

set -euo pipefail

derived="$1" out_dir="$2" case_json="$3"; shift 3
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
clinvar="$derived/clinvar.acmg.vcf.gz"
mkdir -p "$out_dir"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

for c in $(seq 1 22) X Y; do printf 'chr%s\t%s\n' "$c" "$c"; done > "$work/chr_to_plain"

: > "$out_dir/genotypes.tsv"
for id in "$@"; do
  genome="$derived/$id.acmg.vcf.gz"
  # Step 1: ClinVar names contigs 1..22, X; rename only a file that differs.
  #
  # `|| true` because `head -1` closes the pipe and bcftools then dies of
  # SIGPIPE with status 141. Under `set -o pipefail` that status becomes the
  # pipeline's, so writing this as an `if` condition silently inverted the
  # test: every chr-style genome went unrenamed and matched nothing against
  # ClinVar, while the small fixtures in the tests stayed under the 64 KiB pipe
  # buffer and never tripped it. The harness documents the same trap in
  # lib/common.sh's bm_cat_vcf.
  first_chrom="$(bcftools view -H "$genome" 2>/dev/null | head -1 | cut -f1 || true)"
  [[ -n "$first_chrom" ]] || { echo "baseline: $id has no records" >&2; exit 1; }
  if [[ "$first_chrom" == chr* ]]; then
    bcftools annotate --rename-chrs "$work/chr_to_plain" -Oz -o "$work/$id.vcf.gz" "$genome"
    bcftools index "$work/$id.vcf.gz"
    genome="$work/$id.vcf.gz"
  fi
  # Steps 2-4.
  bcftools annotate -a "$clinvar" -c INFO/CLNSIG,INFO/CLNREVSTAT,INFO/GENEINFO \
      --pair-logic exact -Ou "$genome" \
    | bcftools view -f PASS,. -i 'INFO/CLNSIG!="." && GT="alt"' -Ou \
    | bcftools query -i 'GT="alt"' \
        -f "$id\t%CHROM\t%POS\t%REF\t%ALT\t%INFO/CLNSIG\t%INFO/CLNREVSTAT\t%INFO/GENEINFO[\t%GT]\n" \
    >> "$out_dir/genotypes.tsv"
done

# Step 6's frequencies, as the panel file states them.
panel=()
if [[ -s "$derived/panel.acmg.vcf.gz" ]]; then
  field="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["panel"]["rare"]["field"])' "$case_json")"
  bcftools query -f "%CHROM\t%POS\t%REF\t%ALT\t%INFO/$field\n" "$derived/panel.acmg.vcf.gz" > "$out_dir/panel.tsv"
  panel=("$out_dir/panel.tsv")
fi

# Steps 5 and 6.
python3 "$here/baseline_carriers.py" "$case_json" "$here/acmg_sf_v3.2.genes.txt" \
  "$out_dir/genotypes.tsv" "$out_dir" "${panel[@]}"
