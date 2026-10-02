#!/usr/bin/env bash
# Derive one use-case input: restrict to the ACMG gene spans, then normalise.
#
# Runs INSIDE the VCF-RDFizer image (it needs bcftools), one call per input:
#
#   derive.sh <input.vcf.gz> <id> <out-dir> <reference.fna> <regions.bed|all> [drop-info]
#
# Writes <out-dir>/<id>.acmg.vcf.gz (+ .csi) for the bcftools baseline,
# <out-dir>/<id>.acmg.vcf for conversion, and <out-dir>/<id>.derive.json.
#
# Two decisions worth knowing:
#
# * Contig names are left as the source wrote them. GIAB and the PGP genomes
#   say chr1; the HG002 submission and ClinVar say 1. Normalisation needs the
#   reference's names, so those files are renamed for `bcftools norm` and
#   renamed back afterwards. The heterogeneity is real, and reconciling it is
#   part of what each route has to do.
# * ##reference is replaced with the reference this script normalised against.
#   The files declare a lab path (file:///mnt/ssd/.../hg38.fa) or nothing, so a
#   policy's assembly check could otherwise never pass on real data.
# * `all` in place of the regions keeps the whole genome (arm 3); it is
#   normalised exactly like a restricted input.
# * `drop-info` removes every INFO field. Arm 2 uses it: the 1000 Genomes
#   panel's ~70 INFO fields describe all 3,202 samples, not the participant,
#   and made up 93% of each participant's triples (measured).

set -euo pipefail

input="$1" id="$2" out_dir="$3" reference="$4" bed="$5" drop_info="${6:-}"
reference_name="GCA_000001405.15_GRCh38_no_alt_analysis_set"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out_dir"

# The source's contig style, from its first record (headers are not reliable:
# some files declare no ##contig lines at all).
first_chrom="$(bcftools view -H "$input" 2>/dev/null | head -1 | cut -f1 || true)"
case "$first_chrom" in
  chr*) style=chr ;;
  "")   echo "derive: $input has no records" >&2; exit 1 ;;
  *)    style=plain ;;
esac

for c in $(seq 1 22) X Y; do printf 'chr%s\t%s\n' "$c" "$c"; done > "$work/chr_to_plain"
awk -F'\t' '{ print $2 "\t" $1 }' "$work/chr_to_plain" > "$work/plain_to_chr"
printf 'chrM\tMT\n' >> "$work/chr_to_plain"
printf 'MT\tchrM\n' >> "$work/plain_to_chr"

if [[ "$style" == plain ]]; then
  [[ "$bed" == all ]] || sed 's/^chr//' "$bed" > "$work/regions.bed"
  to_reference=(bcftools annotate --rename-chrs "$work/plain_to_chr" -Ou -)
  from_reference=(bcftools annotate --rename-chrs "$work/chr_to_plain" -Ou -)
else
  [[ "$bed" == all ]] || cp "$bed" "$work/regions.bed"
  to_reference=(bcftools view -Ou -)
  from_reference=(bcftools view -Ou -)
fi

# -T streams the whole file (no index needed; some inputs are plain gzip).
#
# The subset is written as VCF text rather than BCF. ClinVar's VCF declares no
# ##contig lines at all; htslib adds them to the in-memory header while parsing,
# which is too late for BCF, whose header is written before the first record --
# the result is a file whose records name contigs its own header does not
# declare, and reading it back fails with "Invalid CONTIG id 0". VCF text needs
# no such dictionary, so the subset survives and the header is repaired below.
regions=(-T "$work/regions.bed"); [[ "$bed" == all ]] && regions=()
bcftools view "${regions[@]}" -Ov -o "$work/in_regions.vcf" "$input" 2>"$work/view.log"
grep -cv '^#' "$work/in_regions.vcf" > "$work/in_regions" || echo 0 > "$work/in_regions"
if [[ "$drop_info" == drop-info ]]; then
  bcftools annotate -x INFO -Ov -o "$work/no_info.vcf" "$work/in_regions.vcf"
  mv "$work/no_info.vcf" "$work/in_regions.vcf"
fi

# Supply any missing contig declarations from the reference index, in this
# file's naming style. Without them the pipeline cannot write BCF and, more
# importantly, the .csi index the baseline needs cannot be built.
if ! grep -qm1 '^##contig=' "$work/in_regions.vcf"; then
  awk -v style="$style" -v OFS="" '
    { name = $1
      if (style == "plain") { sub(/^chr/, "", name); if (name == "M") name = "MT" }
      print "##contig=<ID=", name, ",length=", $2, ">" }' "$reference.fai" > "$work/contigs"
  awk -v contigs="$work/contigs" '
      /^#CHROM/ { while ((getline line < contigs) > 0) print line }
      /^#/ { print }' "$work/in_regions.vcf" > "$work/header.in"
  { cat "$work/header.in"; grep -v '^#' "$work/in_regions.vcf" || true; } > "$work/repaired.vcf"
  mv "$work/repaired.vcf" "$work/in_regions.vcf"
fi

"${to_reference[@]}" < "$work/in_regions.vcf" \
  | bcftools norm -f "$reference" -m -any -c x -Ou - 2> "$work/norm.log" \
  | "${from_reference[@]}" \
  | bcftools sort -T "$work" -Oz -o "$work/sorted.vcf.gz" - 2>/dev/null

# Replace ##reference with the one used above (reheader keeps every record).
bcftools view -h "$work/sorted.vcf.gz" \
  | awk -v ref="$reference_name" '
      /^##reference=/ { next }
      /^#CHROM/ { print "##reference=" ref }
      { print }' > "$work/header"
bcftools reheader -h "$work/header" -o "$out_dir/$id.acmg.vcf.gz" "$work/sorted.vcf.gz"
bcftools index -f "$out_dir/$id.acmg.vcf.gz"
bcftools view -Ov -o "$out_dir/$id.acmg.vcf" "$out_dir/$id.acmg.vcf.gz"

records="$(bcftools view -H "$out_dir/$id.acmg.vcf.gz" | wc -l)"
samples="$(bcftools query -l "$out_dir/$id.acmg.vcf.gz" | paste -sd, -)"
# norm reports "Lines   total/split/joined/realigned/mismatch_removed/dup_removed/skipped: a/b/..."
norm_line="$(grep -E '^Lines' "$work/norm.log" | tail -1 | tr -s ' \t' ' ')"
python3 - "$out_dir/$id.derive.json" "$id" "$input" "$style" "$(cat "$work/in_regions")" \
  "$records" "$samples" "$norm_line" "$reference_name" "$(bcftools --version | head -1)" "${drop_info:+yes}" <<'PY'
import json, sys
out, pid, source, style, in_regions, records, samples, norm, reference, tool, dropped = sys.argv[1:]
counts = {}
if ":" in norm:
    names, values = norm.split(":", 1)
    keys = names.split()[-1].split("/")
    counts = dict(zip(keys, (int(v) for v in values.split("/"))))
json.dump({"id": pid, "source": source, "contig_style": style,
           "records_in_regions": int(in_regions), "records_out": int(records),
           "samples": samples.split(",") if samples else [], "norm": counts,
           "reference": reference, "bcftools": tool, "info_dropped": dropped == "yes"},
          open(out, "w"), indent=2)
PY
echo "derive: $id -> $records records ($style contigs)"
