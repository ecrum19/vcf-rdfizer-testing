#!/usr/bin/env bash
# pack_v331.sh [--no-hash] [skip-prefix...]
#
# Packs the run records of the v3.3.1 rerun under ~/vrdev-test/v331 into ~/vrdev-test/v331-records.tar.gz,
# the way the archive keeps every experiment: run records in, generated data out. Left out, and
# listed with size (and SHA-256 unless --no-hash) in excluded-files.tsv inside the tarball:
# graphs and VCFs (.nt, .nt.gz, .hdt, .cottas, .vcf, .vcf.gz, .csi, .tbi), the per-record
# decisions.csv and records.tsv, and any other file over 5 MB. The tool source, harness, scratch,
# and derived inputs are not packed at all. Paths starting with a skip prefix are left out too
# (a job still running).
set -euo pipefail
hash=1
if [[ "${1:-}" == "--no-hash" ]]; then hash=0; shift; fi
skip=("$@")
cd "$HOME/vrdev-test/v331"
list="$(mktemp)"
manifest=excluded-files.tsv
printf 'bytes\tsha256\tpath\n' > "$manifest"
while IFS= read -r -d '' f; do
  case "$f" in ./v3.3.1.tar.gz|./harness-*.tar.gz|./$manifest) continue ;; esac
  for s in "${skip[@]+"${skip[@]}"}"; do [[ "$f" == "./$s"* ]] && continue 2; done
  size=$(stat -c %s "$f")
  name=$(basename "$f")
  if [[ "$name" =~ \.(nt|nt\.gz|hdt|cottas|cottas\.gz|vcf|vcf\.gz|csi|tbi)$ || "$name" == decisions.csv \
        || "$name" == records.tsv || $size -gt 5000000 ]]; then
    sum=-
    (( hash )) && sum=$(sha256sum "$f" | cut -c1-64)
    printf '%s\t%s\t%s\n' "$size" "$sum" "${f#./}" >> "$manifest"
  else
    printf '%s\0' "$f" >> "$list"
  fi
done < <(find . \( -path ./vcf-rdfizer-v3.3.1 -o -path ./vcf-rdfizer-testing -o -path ./tmp -o -path ./derived \) \
           -prune -o -type f -print0)
printf '%s\0' "./$manifest" >> "$list"
tar --null -T "$list" -czf "$HOME/vrdev-test/v331-records.tar.gz"
rm -f "$list"
echo "packed $(tar -tzf "$HOME/vrdev-test/v331-records.tar.gz" | grep -vc '/$') files," \
     "$(stat -c %s "$HOME/vrdev-test/v331-records.tar.gz") bytes; left out $(($(wc -l < "$manifest") - 1)) files"
