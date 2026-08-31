#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "Usage: $0 [--queries-dir DIR] --output-dir DIR RDF_FILE_OR_DIR [...]" >&2
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
QUERIES_DIR="$SCRIPT_DIR/queries"
OUTPUT_DIR=""

while (($#)); do
  case "$1" in
    --queries-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      QUERIES_DIR="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "$OUTPUT_DIR" || $# -eq 0 ]]; then
  usage
  exit 2
fi

command -v comunica-sparql-file >/dev/null 2>&1 || {
  echo "comunica-sparql-file is not installed" >&2
  exit 127
}

mkdir -p "$OUTPUT_DIR"

sources=()
for source_path in "$@"; do
  if [[ -f "$source_path" ]]; then
    sources+=("$source_path")
  elif [[ -d "$source_path" ]]; then
    while IFS= read -r -d '' rdf_file; do
      sources+=("$rdf_file")
    done < <(find "$source_path" -type f -name '*.nt' -print0 | sort -z)
  else
    echo "RDF source does not exist: $source_path" >&2
    exit 2
  fi
done

if ((${#sources[@]} == 0)); then
  echo "No .nt files were found" >&2
  exit 2
fi

mapfile -d '' query_files < <(find "$QUERIES_DIR" -maxdepth 1 -type f -name '*.rq' -print0 | sort -z)
if ((${#query_files[@]} == 0)); then
  echo "No .rq files were found under $QUERIES_DIR" >&2
  exit 2
fi

failures=0
for query_file in "${query_files[@]}"; do
  query_name="$(basename "$query_file" .rq)"
  result_file="$OUTPUT_DIR/$query_name.sparql.json"
  timing_file="$OUTPUT_DIR/$query_name.time.txt"

  echo "Running $query_name" >&2
  if [[ -x /usr/bin/time ]] && /usr/bin/time --version >/dev/null 2>&1; then
    /usr/bin/time -v comunica-sparql-file \
      "${sources[@]}" \
      -f "$query_file" \
      -t application/sparql-results+json \
      >"$result_file" 2>"$timing_file"
  else
    comunica-sparql-file \
      "${sources[@]}" \
      -f "$query_file" \
      -t application/sparql-results+json \
      >"$result_file" 2>"$timing_file"
  fi
  exit_code=$?
  if ((exit_code != 0)); then
    echo "$query_name failed with exit $exit_code; see $timing_file" >&2
    failures=$((failures + 1))
  fi
done

((failures == 0))
