#!/usr/bin/env bash
set -euo pipefail

paper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
final_dir="$paper_dir/final"
tex_name="conference_final.tex"
base_name="conference_final"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'ERROR: required command not found: %s\n' "$1" >&2
    exit 127
  fi
}

require_command python3
require_command pdflatex
require_command bibtex
require_command pdfinfo
if ! command -v pandoc >/dev/null 2>&1; then
  printf '%s\n' \
    'ERROR: Pandoc is required to generate conference_final.docx.' \
    'Install Pandoc and rerun this script.' >&2
  exit 127
fi

python3 "$paper_dir/generate_final_sources.py" conference

build_dir="$(mktemp -d "$final_dir/.conference-build.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT

(
  cd "$final_dir"
  pdflatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -output-directory="$build_dir" "$tex_name"
  openout_any=a bibtex "$build_dir/$base_name"
  pdflatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -output-directory="$build_dir" "$tex_name"
  pdflatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -output-directory="$build_dir" "$tex_name"
)

install -m 0644 "$build_dir/$base_name.pdf" "$final_dir/$base_name.pdf"
python3 "$paper_dir/docx_tools.py" conference

pages="$(pdfinfo "$final_dir/$base_name.pdf" | awk '/^Pages:/ {print $2}')"
printf 'Built %s (%s pages)\n' \
  "$final_dir/$base_name.pdf" "$pages"
printf 'Built %s\n' "$final_dir/$base_name.docx"
