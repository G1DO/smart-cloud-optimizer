#!/usr/bin/env bash
# Fetch the real public cloud traces used by paper/external_validation.py.
#
# Bitbrains GWA-T-12 (Shen, van Beek & Iosup, CCGrid 2015) and Materna
# GWA-T-13 (Kohne et al.), served by the archive maintainers' mirror at
# atlarge-research.com (the original gwa.ewi.tudelft.nl is offline).
# Data courtesy of Bitbrains IT Services Inc. / Materna GmbH and the
# Grid Workloads Archive.
#
# Usage: ./fetch_traces.sh [target_dir]   (default: ./traces)
set -e
TARGET="${1:-traces}"
mkdir -p "$TARGET"
cd "$TARGET"

BASE="https://atlarge-research.com/gwa-traces"
for f in gwa_t_12_fastStorage.zip gwa_t_12_rnd.zip gwa_t_13_materna.zip; do
    [ -f "$f" ] || curl -fL --retry 3 -o "$f" "$BASE/$f"
done

unzip -qn gwa_t_12_fastStorage.zip -d gwa-t-12-fastStorage
unzip -qn gwa_t_12_rnd.zip -d gwa-t-12-rnd
unzip -qn gwa_t_13_materna.zip -d gwa-t-13-materna
echo "Traces ready under $(pwd)"
