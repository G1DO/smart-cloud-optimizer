#!/usr/bin/env bash
# Rebuild the IEEE conference draft.
# Assumes pdflatex and bibtex are on PATH.
set -e
cd "$(dirname "$0")"
pdflatex -interaction=nonstopmode -file-line-error conference_draft.tex
bibtex conference_draft
pdflatex -interaction=nonstopmode -file-line-error conference_draft.tex
pdflatex -interaction=nonstopmode -file-line-error conference_draft.tex
echo "Built conference_draft.pdf"
