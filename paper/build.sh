#!/usr/bin/env bash
# Rebuild the paper: pdflatex -> bibtex -> pdflatex -> pdflatex.
# Assumes pdflatex/bibtex are on PATH (e.g. ~/.TinyTeX/bin/x86_64-linux).
# Run make_figures.py first if the database or figures changed.
set -e
cd "$(dirname "$0")"
pdflatex -interaction=nonstopmode -file-line-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -file-line-error main.tex
pdflatex -interaction=nonstopmode -file-line-error main.tex
echo "Built main.pdf ($(pdfinfo main.pdf 2>/dev/null | awk '/Pages/{print $2}') pages)"
