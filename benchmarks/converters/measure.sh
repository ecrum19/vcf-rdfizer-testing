#!/bin/sh
# measure.sh <time-file> <stdout-file> <command> [args...]
#
# The entry point of every converter container in compose.yaml. It runs one command under
# BusyBox `time -v`, which reports wall time and peak resident set size (ru_maxrss, the quantity
# GNU time reports). BusyBox is the static build from the pinned Debian snapshot, mounted
# read-only at /meter, so the measurement is identical in every container and no converter's
# image has to be modified to carry it. The command's stdout goes to <stdout-file>, because most
# converters write their RDF there; stderr stays on the container's stderr.
set -eu
time_file="$1"; stdout_file="$2"; shift 2
exec /meter/busybox time -v -o "$time_file" "$@" > "$stdout_file"
