#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

texfile="journal_draft.tex"
base="journal_draft"

pdflatex -interaction=nonstopmode -halt-on-error "$texfile"
bibtex "$base"
pdflatex -interaction=nonstopmode -halt-on-error "$texfile"
pdflatex -interaction=nonstopmode -halt-on-error "$texfile"

if command -v pdfinfo >/dev/null 2>&1; then
  pdfinfo "${base}.pdf" | awk '/^Pages:/ {print "Pages: " $2}'
fi
