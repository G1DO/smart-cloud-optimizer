# Historical paper artifacts

This directory preserves the graduation-paper documents (`.docx`), revision
changelogs, preservation reports, and open questions from earlier editing runs.
The recorded claims, validation numbers, and follow-ups refer to those revisions;
they are not the current application specification or an active engineering
backlog. References to `work/` describe ignored editing scratch files.

For current application behavior, use the
[technical documentation index](../docs/README.md). Product context and
durable project decisions belong in
[Notion](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111); accepted
engineering work and review belong in GitHub. The separate
[`release/ccpe-v1.0` branch](https://github.com/G1DO/smart-cloud-optimizer/tree/release/ccpe-v1.0)
contains the separate reproducibility software artifact. Its
[README](https://github.com/G1DO/smart-cloud-optimizer/blob/release/ccpe-v1.0/README.md)
explicitly excludes the manuscript. Thesis references to `paper/results.json`,
`paper/cv_results.csv`, or `paper/main.tex` are historical; those files are absent
from both current `main` and `release/ccpe-v1.0`.

## Find a thesis revision

| Revision | Document | Editing record | Questions recorded after that pass |
| --- | --- | --- | --- |
| Original | [AWS Cost Intelligence System.docx](<AWS Cost Intelligence System.docx>) | Baseline preserved for comparison | — |
| Round 1: prose polish | [POLISHED.docx](<AWS Cost Intelligence System.POLISHED.docx>) | [Changelog](CHANGELOG.md), [preservation report](PRESERVATION_REPORT.md) | [Round 1 questions](OPEN_QUESTIONS.md) |
| Round 2: factual corrections | [CORRECTED.docx](<AWS Cost Intelligence System.CORRECTED.docx>) | [Changelog](CHANGELOG_ROUND2.md), [preservation report](PRESERVATION_REPORT_ROUND2.md) | [Round 2 questions](OPEN_QUESTIONS_ROUND2.md) |

`CORRECTED.docx` is the latest recorded editing output, not a declaration that
the thesis is ready for submission. Start with the Round 2 questions for the
remaining review recorded at that time; some Round 1 questions were addressed
by Round 2. Keep the documents and their revision records together when using
or comparing them.

The preservation reports record earlier checks. Their referenced `work/` guard
scripts and machine output are not tracked here, so those complete editing runs
cannot be reproduced from this directory alone. Preserve the reports as history
rather than treating their pass counts as current validation. Current test
commands live in the [development guide](../docs/development/README.md).

## Research history

[Dataset references](data-resources.md) and [recorded model/optimizer observations](research-notes.md)
were moved here from the application guides to keep research history separate
from current technical contracts. Their original limitations and numerical tables
are preserved; they are not current reproducible evidence. Use the linked Notion
project for new research conclusions and decisions.
