#!/usr/bin/env bash
set -euo pipefail

paper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$paper_dir/build_final_conference.sh"
"$paper_dir/journal/build_final_journal.sh"

required_outputs=(
  "$paper_dir/final/conference_final.tex"
  "$paper_dir/final/conference_final.pdf"
  "$paper_dir/final/conference_final.docx"
  "$paper_dir/journal/final/journal_final.tex"
  "$paper_dir/journal/final/journal_final.pdf"
  "$paper_dir/journal/final/journal_final.docx"
)

for output in "${required_outputs[@]}"; do
  if [[ ! -s "$output" ]]; then
    printf 'ERROR: expected final output is missing or empty: %s\n' \
      "$output" >&2
    exit 1
  fi
done

printf '%s\n' 'Built all final conference and journal outputs.'
