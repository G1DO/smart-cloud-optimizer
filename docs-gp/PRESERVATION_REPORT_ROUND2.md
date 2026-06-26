# PRESERVATION REPORT — Round 2

**Baseline:** `work/ORIGINAL.docx` (untouched original) · **Subject:** `AWS Cost Intelligence System.CORRECTED.docx`
**Guard:** `work/preservation_guard_r2.py` · **Result:** `work/preservation-guard-r2-result.json`
**Verdict: PASS — 54/54 checks.** The corrected thesis is visually identical to the original except the
explicitly‑approved, logged structural changes; it opens in Microsoft Word with no repair prompt.

The guard is an **independent verifier**: it re‑derives the expected formatting fingerprint from ORIGINAL /
POLISHED plus the declared structural‑op list, and fails on any deviation by the assembler. It never trusts
the assembler's output.

---

## 1. Baseline‑vs‑Corrected fingerprint diff (ORIGINAL → CORRECTED)

| Property | Result |
|---|---|
| Part inventory | **identical** — 27 parts, none added/removed |
| Parts that differ | **only** `word/document.xml` (text + approved structural ops) and `docProps/core.xml` (pass‑1 metadata) |
| All other parts | **byte‑identical** — styles.xml, theme1.xml, numbering.xml, settings.xml, webSettings.xml, fontTable.xml, footnotes.xml, endnotes.xml, header1/2.xml, footer1/2.xml, every `word/media/*` image, all `*.rels`, `[Content_Types].xml` |
| Font families | ORIGINAL `{Arial, Calibri, Cambria Math, Segoe UI Emoji, Segoe UI Symbol, Times New Roman}` → CORRECTED `{Arial, Calibri, Cambria Math, Times New Roman}` |
| New font families introduced | **none** (the two Segoe emoji fonts were removed back in pass 1; nothing added) |
| Body font / equation font | **Times New Roman** present · **Cambria Math** present |
| `pStyle` multiset delta | **Heading2 44 → 43, Heading3 61 → 62** — exactly the one approved 5.2.1 restyle, nothing else |
| File size | 908,005 → 899,258 bytes (smaller: 6 deleted rows + 3 added rows + text) |

The six embedded images are byte‑identical and in place.

## 2. Guard checks (54/54 PASS)

**A. ORIGINAL → POLISHED preserved design** — the pass‑1 preservation guard re‑run on POLISHED **PASSED**
(proves Round 1 changed only text + emoji refont + metadata).

**B. POLISHED → CORRECTED is exactly the approved ops + text edits** — the guard applied the same four
structural ops to a clean POLISHED tree and required CORRECTED's formatting‑token multisets to match it
**exactly**:
- `sz`, `szCs`, `pStyle`, `rStyle`, tab stops, `rFonts`, `numPr` (274), dot‑leader tabs (64), and `sectPr`
  blocks — all equal to the expected post‑op fingerprint. Any stray formatting change would fail here.
- Ops fired and were counted: 6 rows deleted, 3 rows added, 1 heading restyled.

**C. ORIGINAL → CORRECTED byte‑identity** of every untouched part — **PASS** (only document.xml + core.xml
differ; all plumbing, styles, theme, numbering, headers/footers, and all media byte‑identical).

**D. CORRECTED validity** — no new font family; zero Segoe‑emoji font tokens; zero true‑emoji codepoints;
Times New Roman + Cambria Math present; every XML part well‑formed; python‑docx opens the file (1,171
body paragraphs).

**E. Semantic checks on CORRECTED** —
- List of Abbreviations: exactly **one** MILP row + **one** UI row (correct expansions); SQLite =
  "Lightweight embedded SQL database engine"; GWA = "Grid Workloads Archive".
- Table 4.4: **no** 120/180/240/300‑day rows; the 5 remaining rows carry the canonical CV values.
- Table 4.8: lists `test_aws_config.py`, `test_components.py`, `test_transforms.py`; auth = 20; ai_module =
  12; total = 217.
- Heading "5.2.1 Prerequisites" is **Heading 3**.

## 3. What changed vs what was preserved

- **Changed (text only, via `<w:t>`):** 123 text‑segment edits (numbers, prose, captions, abbreviations,
  cover words). No run was deleted by the text path; each segment's full `<w:rPr>` was carried onto the
  rewritten run, so the formatting‑token multiset is invariant under text edits.
- **Changed (approved structural ops):** 6 `<w:tr>` deletions (2 duplicate abbreviation rows + 4 unsupported
  MAPE rows), 3 `<w:tr>` additions (cloned from an existing data row, all `trPr`/`tcPr`/`rPr` preserved),
  1 heading paragraph restyled (cloned the sibling Heading‑3 `pPr`/run `rPr`).
- **Preserved:** fonts, font sizes, named styles & style references, bold/italic/underline, colour, spacing,
  indentation, alignment, list numbering, tab stops (incl. TOC dot leaders), cover/title layout,
  headers/footers, page‑number fields, section properties, page geometry/margins, and the six images — all
  byte‑identical or multiset‑invariant.

## 4. Manual step required in Word
The Table of Contents, List of Tables, and List of Figures are field‑generated. After opening
`AWS Cost Intelligence System.CORRECTED.docx`, select all (**Ctrl+A**) and press **F9** to refresh them so the
renamed heading (5.4.3) and the corrected Table 4.6/4.7 captions propagate, then re‑check page numbers. Word
fields cannot be refreshed programmatically.
