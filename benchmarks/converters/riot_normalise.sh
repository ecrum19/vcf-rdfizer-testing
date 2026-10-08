#!/bin/sh
# riot_normalise.sh <syntax> <in> <out.nt> <warnings.log.gz>
#
# Streams one converter's native RDF to N-Triples with Jena riot. riot warns once per offending
# IRI, which is millions of lines on some outputs (4.6 GB for one graph), so its stderr is
# compressed as it is written; the driver counts the warnings by kind. riot's own exit status is
# returned, not the compressor's.
set -eu
syntax="$1" in="$2" out="$3" warnings="$4"
fifo="$(mktemp -u)"
mkfifo "$fifo"
gzip -c < "$fifo" > "$warnings" &
compressor=$!
set +e
riot --syntax="$syntax" --output=nt "$in" > "$out" 2> "$fifo"
status=$?
set -e
wait "$compressor"
rm -f "$fifo"
exit "$status"
