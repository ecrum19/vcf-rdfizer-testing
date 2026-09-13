#!/usr/bin/env bash
# Plan §3.2 — corpus breadth: a stratified table, deliberately not a curve.
#
# The ten real files answer "does this handle real, heterogeneous VCFs?", not
# "how does cost scale?". They differ in variant class, sample count, assembly,
# caller and VCF version, so NO cross-family regression is fitted here — see
# §3.2 for why, and say so in the manuscript. Declining to fit a model you
# cannot justify reads as rigor, not as a missing result.
#
# One configuration, every available corpus file, one repetition each. The
# analysis normalizes by EMITTED TRIPLES rather than input bytes: input bytes is
# exactly what makes HGSVC2 incomparable, since sequence-resolved SV alleles
# mean many bytes per record.
#
# Usage: ./05_corpus_breadth.sh

source "$(dirname -- "${BASH_SOURCE[0]}")/lib/common.sh"

EXPERIMENT="05_corpus_breadth"

# family:file — the family label lands in the analysis table's strata column.
CORPUS="
sv_batch:HGSVC2.vcf.gz
cohort:1000G_phase3_chr20.vcf.gz
giab_single:HG004_GRCh38.vcf.gz
giab_single:HG005_GRCh38.vcf.gz
giab_single:0GOOR_HG002.vcf.gz
consumer_wgs:NG1N86S6FC.vcf.gz
consumer_wgs:NG131FQA1I.vcf.gz
consumer_wgs:NB72462M.vcf.gz
consumer_wgs:60820188475559.vcf.gz
consumer_wgs:60820188474283.vcf.gz
"

# §3.2 asks whether the tool handles real, heterogeneous VCFs. That is a
# COVERAGE claim about feature diversity -- INFO/FORMAT/FILTER structures,
# variant types -- not a timing claim about file length, and nine whole corpus
# files at expanded is the single most expensive block in the plan (days).
#
# BM_CORPUS_MAX_RECORDS truncates each file to its first N data records,
# keeping the header and therefore the declared fields intact. Files named in
# BM_CORPUS_WHOLE are exempt, so at least one real file can still be converted
# end to end. Truncated cells carry a __firstN suffix in their label: this
# weakens the claim from "converted ten whole cohorts" to "handled the features
# of ten cohorts, and one of them whole", and a results table must not hide
# which one it is.
MAX_RECORDS="${BM_CORPUS_MAX_RECORDS:-}"
WHOLE_FILES="${BM_CORPUS_WHOLE:-}"

corpus_input() {          # echo "<path> <label-suffix>"
  local input="$1" vcf="$2" stem="$3"
  if [[ -z "$MAX_RECORDS" ]]; then printf '%s 
' "$vcf"; return 0; fi
  case " $WHOLE_FILES " in *" $input "*) printf '%s 
' "$vcf"; return 0 ;; esac
  local target="$BM_DERIVED/${stem}_first${MAX_RECORDS}.vcf.gz"
  if [[ ! -f "$target" ]]; then
    mkdir -p "$BM_DERIVED"
    bm_cat_vcf "$vcf" | awk -v n="$MAX_RECORDS" '
      /^#/ { print; next }
      kept < n { print; kept++; next }
      { exit }' | gzip -c > "$target"
  fi
  printf '%s __first%s
' "$target" "$MAX_RECORDS"
}

bm_banner "§3.2 corpus breadth (one config, one rep per file)"
[[ -n "$MAX_RECORDS" ]] && bm_step "truncating to first $MAX_RECORDS records (whole: ${WHOLE_FILES:-none})"

for entry in $CORPUS; do
  family="${entry%%:*}"; input="${entry##*:}"
  stem="${input%%.*}"
  if ! bm_have_vcf "$input"; then
    bm_skip "$EXPERIMENT" "${family}__${stem}__missing" "corpus input not available: $input"
    continue
  fi
  vcf="$(bm_vcf "$input")"

  # §3.2 runs everything at expanded, so a cohort-scale input cannot complete.
  bm_skip_if_cohort_scale "$EXPERIMENT" "${family}__${stem}__too_many_samples" \
    "$vcf" expanded && continue

  read -r vcf suffix <<< "$(corpus_input "$input" "$vcf" "$stem")"
  bm_run "$EXPERIMENT" "${family}__${stem}${suffix:-}" -- \
    --mode full \
    --input "$vcf" \
    --sample-representation expanded \
    --rdf-storage-mode space-optimized \
    --hdt-strategy partitioned \
    --representations hdt,cottas \
    --rdf-compression none \
    --artifact-compression none \
    --spark-partitions "${BM_SPARK_PARTITIONS:-8}"
done

bm_info "Done. Build the structured dataset with:
  python3 $BM_ROOT/analysis/collect_metrics.py $EXPERIMENT
  python3 $BM_ROOT/analysis/describe_inputs.py --corpus
  python3 $BM_ROOT/analysis/datasets.py corpus $EXPERIMENT

describe_inputs.py emits the structural descriptors (records, samples, sample
calls, allele shape, INFO/FORMAT key counts, VCF version) that go NEXT TO the
cost in the same row. Without them an off-trend file reads as noise; with them
it reads as explained."
