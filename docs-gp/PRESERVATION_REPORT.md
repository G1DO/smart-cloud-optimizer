# PRESERVATION REPORT — AWS Cost Intelligence System (thesis polish)

**Result: PASS — the visual design is byte-faithful where untouched, and no new font was introduced.**

Compared `docs-gp/work/ORIGINAL.docx` (immutable baseline, SHA-256
`73ff50ab…d4ba`) against `docs-gp/AWS Cost Intelligence System.POLISHED.docx`.
The automated guard (`docs-gp/work/preservation_guard.py`) exits non-zero on any drift; it
reported **34 / 34 checks PASS** (`docs-gp/work/preservation-guard-result.json`).

Only **two** of the 27 package parts changed, both permitted:
`word/document.xml` (run-level `<w:t>` text edits + emoji refont) and
`docProps/core.xml` (metadata correction). Every other part is byte-identical.

---

## 1. Part inventory — PASS
- 27 parts in both files; identical set of names (no part added, removed, or renamed).
- Parts whose content differs: **exactly** `docProps/core.xml`, `word/document.xml`.
- (The original prompt estimated "28 parts"; the file actually contains 27. The full set
  matches the documented inventory otherwise.)

## 2. Byte-identity of untouched parts — PASS
SHA-256 identical for all of: `styles.xml`, `theme/theme1.xml`, `numbering.xml`,
`settings.xml`, `webSettings.xml`, `fontTable.xml`, `footnotes.xml`, `endnotes.xml`,
`header1.xml`, `header2.xml`, `footer1.xml`, `footer2.xml`, `customXml/*`, all `*.rels`,
`[Content_Types].xml`, and **all six media files**
(`image1.jpeg`, `image2.png` … `image6.png`) — byte-identical, same bytes, same order.

## 3. Formatting-token multisets (document + headers + footers) — PASS
Compared as multisets; **exact equality** required for every token class except `rFonts`:

| Token class | Original | Polished | Verdict |
|---|---|---|---|
| `w:sz` / `w:szCs` | unchanged multiset | unchanged | PASS (exact) |
| `w:pStyle` / `w:rStyle` ids | unchanged multiset | unchanged | PASS (exact) |
| `w:numPr` count | 274 | 274 | PASS |
| tab stops incl. `w:leader="dot"` | 64 dot-leaders | 64 | PASS |
| `w:sectPr` blocks (both) | 2, identical | 2, identical | PASS |

No font size was normalized, rounded, or cleaned; the `28`/`24`/`36`/`32`/`72`/`56`/`48`/`22`/`20`
half-point distribution is intact. No style id was added, renamed, deleted, or re-pointed; the
load-bearing ids (`font-claude-response-body`, `TOCHeading`, `Heading1/2/3`, `Caption`,
`ListParagraph`, `NoSpacing`, `NormalWeb`, `TOC1/2/3`, `TableofFigures`) all survive.

## 4. Fonts — PASS (controlled, no new family)
`w:rFonts` attribute-occurrence counts (ascii/hAnsi/cs/eastAsia across document + headers + footers):

| Font family | Original | Polished | Note |
|---|---|---|---|
| Times New Roman | 1439 | **1532** | +93 = the 31 emoji runs refonted to TNR (× ascii/hAnsi/cs); no TNR lost |
| Calibri | 72 | 72 | unchanged (pre-existing runs preserved) |
| Arial | 5 | 5 | unchanged |
| **Cambria Math** | 3 | **3** | the equation run — preserved exactly |
| Segoe UI Emoji | 90 | **0** | emoji removed (approved) |
| Segoe UI Symbol | 3 | **0** | the single `⚠` status run — removed + logged (approved) |

- **No new font family introduced** (no Aptos/Calibri leakage; polished font-family set ⊆
  baseline set). Times New Roman count *increased* only because emoji runs were refonted to TNR;
  no Times New Roman / Cambria Math / Calibri / Arial token was lost.
- The Segoe UI Symbol drop is the lone `⚠` (U+26A0) status glyph, which is a true status emoji;
  its removal is explicitly approved and logged here and in `CHANGELOG.md`.

## 5. Emoji gate — PASS
- True-emoji codepoints remaining (✅ U+2705, ❌ U+274C, ⚠ U+26A0, U+FE0F, U+1F000+): **0**.
- `Segoe UI Emoji` + `Segoe UI Symbol` font tokens remaining: **0**.
- Handling (no run deleted, so non-font token multisets stayed invariant): 16 Ch.2 Table 2.2
  cells → "Yes"/"No" in Times New Roman; 15 decorative ✅ (Ch.4 test table, Ch.6 objective list)
  emptied and refonted to TNR; 1 inline U+FE0F variation selector stripped from a text run.
- All 14 `→` (U+2192) arrows were reviewed and **retained** (meaningful mappings/pipelines/
  navigation paths; rendered in their existing font) — see `CHANGELOG.md` §11.

## 6. Validity — PASS (with one environmental caveat)
- Every XML part is well-formed (parsed with lxml).
- The ZIP is valid; `python-docx` 1.2.0 round-trip opens the polished file cleanly
  (1171 body paragraphs read). No Word repair prompt is expected (only `<w:t>` text and one
  metadata part changed; all relationships, content types, and structure untouched).
- **Caveat:** LibreOffice (`soffice`) is **not installed** in this environment
  (`/usr/bin/soffice` absent), so the PDF render-comparison (page count / heading / TOC / figure
  placement) described in the plan could not be run. It is replaced by the byte-identity proof of
  every layout-bearing part (styles, theme, numbering, sectPr, headers/footers, media) plus the
  token-multiset invariants above, which together establish that on-page layout cannot have moved
  for any untouched content. A final visual confirmation in Microsoft Word is recommended.

## 7. Metadata change (the one permitted non-text edit) — `docProps/core.xml`
| Field | From | To |
|---|---|---|
| `dc:title` | "Chapter one" | "AWS Cost Intelligence System" |
| `dc:subject` | "Introduction" | "Graduation Project Thesis" |
| `cp:keywords` | (empty) | "cloud cost optimization; AWS; time-series forecasting; anomaly detection; linear programming; machine learning" |

`dc:creator` / `cp:lastModifiedBy` ("Ahmed Sameh"), `cp:revision`, and both timestamps were
left unchanged. No supervisor or teammate name was invented.

---

## Explicit PASS lines (per the Definition of Done)
- **Headings:** PASS — `Heading1/2/3` style ids and all heading runs' `rPr` preserved; the
  CHAPTER-page large sizes (72/56/48) intact.
- **Table of Contents (and List of Figures):** PASS — field codes, `TOC1/2/3`/`TOCHeading`/
  `TableofFigures` styles, and the 64 dot-leader tab stops are byte/token-preserved. (Field
  *results* will refresh in Word via Ctrl+A → F9 if any heading text was changed; no page number
  was hand-edited.)
- **Headers / footers:** PASS — `header1/2.xml`, `footer1/2.xml` byte-identical.
- **Cover / title page:** PASS — cover-page text was treated as immutable (space-based column
  alignment); no cover run was edited (issues flagged in `OPEN_QUESTIONS.md` §E).
- **Figures / media:** PASS — all six media files byte-identical, same references.

**File sizes:** original 908,005 bytes → polished 898,928 bytes (smaller because emoji runs were
refonted/emptied and prose was tightened; no content or media lost).
