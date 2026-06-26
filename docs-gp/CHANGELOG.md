# Thesis Polishing — Change Log

**Document:** *AWS Cost Intelligence System* (OptiCloud) — Graduation Project Thesis
**Source artifact:** `AWS Cost Intelligence System.docx` → `AWS Cost Intelligence System.POLISHED.docx`
**Scope:** conservative, surgical copy-edit. Design and layout preserved byte-for-byte.

---

## Summary

This pass edited **55 prose segments across all 8 chapters/sections** (front matter, Chapters 1–6, References), handled **32 true-emoji code points** (16 replaced, 15 removed, 1 variation selector stripped), and corrected **3 document-metadata fields** in `docProps/core.xml`. The scope was deliberately conservative: every change is grammar, register, technical accuracy, or formatting hygiene that does not alter meaning the authors intended. **Zero numbers were changed** — every forecasting MAPE value, savings figure, recall claim, and test count was kept exactly as the team wrote it; where a number contradicts the canonical paper artifacts (`paper/results.json`, `paper/cv_results.csv`) it was **flagged, not edited** (see `OPEN_QUESTIONS.md`). No reference entries were added or removed, no citations/DOIs/authors/years were invented, the Arabic abstract text was left untouched (flagged for native-speaker review), and the cover page (space-based alignment) was treated as immutable. The document's styles, fonts, fields, images, and run structure are unchanged; the assembly audit recorded **0 hard failures**.

Per-segment edit counts by chapter (from `revision-audit.json`): front matter 2, Ch.1 4, Ch.2 3, Ch.3 8, Ch.4 4, Ch.5 21, Ch.6 12, References 1 → **55 total**. (Ch.3 includes two cross-document consistency fixes added in the consistency pass: P0806.S0 dropped the imprecise "for non-compute services" scope, and P0885.S1 corrected the Forecasts UI bullet "horizon selector (7–90 days)" → "(7, 14, 30, 60, or 90 days)" with "automatic model training", matching the Ch.5 corrections.)

---

## 1. Grammar / spelling / punctuation — 5 segments

Spelling typos, capitalization, a missing sentence space, and a missing article.

- **P0734.S0 (Ch.3, table cell)** — spelling
  - before: `metrices`
  - after: `metrics`
- **P0924.S0 (Ch.3, table cell)** — spelling
  - before: `forcasting (fallback)`
  - after: `forecasting (fallback)`
- **P0836.S0 (Ch.3, table cell)** — capitalization / proper-noun spelling
  - before: `nAt gateway`
  - after: `NAT Gateway`
- **P0654.S4 (Ch.3)** — missing sentence space (run-on at a sentence boundary)
  - before: `… regardless of the data source.Although the system architecture …`
  - after: `… regardless of the data source. Although the system architecture …`
- **P1772.S3 (Ch.6)** — missing article
  - before: `… combining Binary LP solver for compute rightsizing …`
  - after: `… combining a Binary LP solver for compute rightsizing …`

---

## 2. Register / de-hype (removed hype adjectives, softened marketing tone) — 7 segments

Removed filler intensifiers and marketing verbs ("ideal", "democratizes", "fully functional", "robust"/"robustness" as filler, "significant" as filler).

- **P1813.S0 (Ch.6)** — marketing verb
  - before: `OptiCloud democratizes AWS cost optimization:`
  - after: `OptiCloud broadens access to AWS cost optimization:`
- **P1798.S0 (Ch.6)** — overclaim adjective
  - before: `The P95 metric with 30% headroom proved ideal, avoiding over-engineering …`
  - after: `The P95 metric with 30% headroom proved effective, avoiding over-engineering …`
- **P1359.S0 (Ch.4)** — "robustness" as filler (no numbers touched: ~90% CPU, 10.4 vCPUs, 1.3×, 8 vCPUs all preserved)
  - before: `… rather than generating an incorrect recommendation, demonstrating the robustness of the edge case handling.`
  - after: `… rather than generating an incorrect recommendation, demonstrating correct handling of this edge case.`
- **P1431.S0 (Ch.4)** — filler intensifier
  - before: `During implementation, four significant technical challenges were encountered and resolved.`
  - after: `During implementation, four technical challenges were encountered and resolved.`
- **P0448.S1 (Ch.1)** — overclaim softened (also ties to the broken-demo gap; see `OPEN_QUESTIONS.md` §B)
  - before: ` Provide a fully functional demo experience using pre-loaded synthetic data …`
  - after: ` Provide a demo experience using pre-loaded synthetic data …`

(Also in this category: **P1546.S1** "fully functional environment … complete … already pre-calculated" → "environment preloaded … pre-calculated"; **P1892.S0** "robust, modular design" → "modular design".)

---

## 3. Emoji removal — 32 code points handled (16 replaced, 15 removed, 1 stripped)

Source inventory (`emoji-hits.json`): **23 × U+2705 ✅, 7 × U+274C ❌, 1 × U+26A0 ⚠, 1 × U+FE0F** variation selector = 32. Assembly applied (`assembly-log.json`): `emoji_replaced=16`, `emoji_removed=15`, plus the U+FE0F strip. **Zero true emoji remain.** Every touched run was re-fonted to Times New Roman to match surrounding body text.

| Action | Count | Location | Mapping |
|---|---|---|---|
| Replace | 16 | Ch.2, Table 2.2 (feature-gap comparison matrix) | `✅` → `Yes`, `❌` → `No` (meaningful table cells; re-fonted to Times New Roman) |
| Remove | 15 | Ch.4 test-results table; Ch.6 objective list; the lone ⚠ in Ch.4 | decorative `✅` deleted, and the single `⚠` (U+26A0 — the only Segoe UI Symbol run) deleted; runs re-fonted to Times New Roman |
| Strip | 1 | Ch.4, adjacent to a test-table run (snippet `"️ 26 passing, 1 failing"`) | inline U+FE0F variation selector removed |

Rationale: the ✅/❌ in Table 2.2 carry comparison meaning, so they were converted to plain words rather than dropped; the rest were purely decorative status/checklist glyphs inappropriate for a formal thesis and were removed without changing any adjacent text.

---

## 4. AI-tell removal (contractions, "successfully", "comprehensive", em-dash / stacked-transition trims) — 9 segments

- **P1824.S1 (Ch.6)** — contraction
  - before: ` — Synthetic data doesn't include multi-AZ failover costs …`
  - after: ` — Synthetic data does not include multi-AZ failover costs …`
- **P0438.S0 (Ch.1)** — filler verb "leveraging", stacked "Furthermore", em-dash pair → commas (meaning unchanged)
  - before: `By leveraging machine learning … from the user. Furthermore, handling multi-account AWS environments and complex pricing strategies — areas typically requiring dedicated cloud engineers — is a core design goal …`
  - after: `By applying machine learning … from the user. Handling multi-account AWS environments and complex pricing strategies, areas that typically require dedicated cloud engineers, is a core design goal …`
- **P1767.S0 (Ch.6)** — "successfully" + "comprehensive"
  - before: `This project successfully developed OptiCloud, a comprehensive AWS Cost Intelligence System that combines …`
  - after: `This project developed OptiCloud, an AWS Cost Intelligence System that combines …`
- **P0047.S0 (English Abstract)** — removed "successfully", "significantly", "intelligent (automation)", and a hollow "The results indicate that …" opener; tightened wording. All numbers and model names preserved (≈10–18% MAPE, ~$590, 19 recommendations, Seasonal Naive / ETS / Prophet, Gemini 2.5 Flash).
  - before (closing): `The developed system successfully integrates … The results indicate that intelligent automation can significantly reduce cloud waste, improve cost visibility, and support both new and existing AWS users …`
  - after (closing): `By unifying forecasting, anomaly detection, optimization, and AI-based guidance in a single interactive dashboard, the system reduces cloud waste, improves cost visibility, and helps both new and existing AWS users …`

(Also in this category: **P1769.S0** "successfully completed" → "completed"; **P1776.S3** "comprehensive visualizations" → "visualizations"; **P1795.S0** "successfully covered" → "covered"; **P1462.S0** two "successfully" + "robustness" removed; **P1891.S0** "successfully demonstrates … significantly reduce" → "demonstrates … reduce".)

---

## 5. Terminology / acronym unification — naming decision recorded; acronym fixes flagged

**Naming decision (intentional, applied consistently):** formal title **"AWS Cost Intelligence System"**, product name **"OptiCloud"**. Both are used deliberately (title in headings/abstract, "OptiCloud" in prose). The code/README name **"Smart Cloud Optimizer" was NOT introduced** into the thesis. No prose segment required a name change.

**Acronym-table fixes were flag-only** (editing rows risks breaking table structure) and are routed to `OPEN_QUESTIONS.md` §D:
- duplicate **MILP** row (P0300.S0 / P0349.S0);
- duplicate **UI** row (P0329.S0 / P0375.S0);
- inaccurate expansion **"SQLite = Structured Query Language Lite"** (P0325.S0 — SQLite is not an acronym);
- **GWA** expansion plural fix (P0343.S0 "Grid Workload Archive" → "Grid Workloads Archive") to match the References fix below.

---

## 6. Citations / references — 2 segments changed; the rest flagged

- **P1925.S0 (References)** — canonical-name fix (the "GWA name fix")
  - before: `Bitbrains GWA-T-12. "Grid Workload Archive." `
  - after: `Bitbrains GWA-T-12. "Grid Workloads Archive." `
  - (Canonical archive name is plural — `iosup2008gwa`; trailing space preserved.)
- **P0526.S0 (Ch.2)** — softened an orphan, untraceable attribution (no source invented; the 63% and 30–35% figures preserved)
  - before: `… Furthermore, research by RightScale found that 63% of small-to-medium enterprises lack adequate cloud cost visibility …`
  - after: `… Industry surveys further report that 63% of small-to-medium enterprises lack adequate cloud cost visibility …`

**Flagged, NOT changed** (no reference entries added/removed; adding paragraphs would break formatting preservation): Flexera year 2023 vs verified 2024 (P1918), untraceable Gartner entry (P1919 / in-text P0526), unverified Liu CSUR-2025 (P1917 / P0560), Cortez SOSP-2017 absent from the curated bib (P1915 / P0524), orphan Kaggle datasets zoya77 (P0565) and programmer3 (P0575), and the uncited "several recent works" (P0586). All detailed in `OPEN_QUESTIONS.md` §C. The thesis's informal author–title citation style was intentionally **kept** (not converted to numbered IEEE).

---

## 7. Figure / table captioning & cross-references — 3 segments

Table caption verb-phrases normalized to noun-phrase / lowercase mid-sentence form, matching sibling captions. Dot leaders and page numbers preserved byte-exact.

- **P0249.S0 (List of Tables)** — caption typo
  - before: `Table 2.2 Highlights the key functional gaps ………………………………28`
  - after: `Table 2.2 Key functional gaps ………………………………28`
- **P0561.S0 (Ch.2)** — caption capitalization
  - before: `Table 2.1 Summarizes the performance of all five forecasting models`
  - after: `Table 2.1 summarizes the performance of all five forecasting models`
- **P0621.S0 (Ch.2)** — caption capitalization
  - before: `Table 2.2 Highlights the key functional gaps`
  - after: `Table 2.2 highlights the key functional gaps`

(Note: separate, unfixed table-number copy-paste errors in Ch.4 — P1307.S0 / P1355.S0 — require a structural fix and are flagged in `OPEN_QUESTIONS.md` §F.)

---

## 8. Transitions / flow — 1 segment

- **P1791.S0 (Ch.6)** — repetition / awkward parallelism repaired (the design claim itself is flagged separately in §B)
  - before: `… maximized recall to ensure all cost anomalies were excluded … While this trades off slightly higher false positives, this is acceptable because:`
  - after: `… maximized recall to ensure all cost anomalies were excluded … While this admits slightly higher false positives, the trade-off is acceptable because:`

---

## 9. Code-grounded technical corrections — 26 segments

Corrections to **technical descriptions** (never numbers) that were verifiably wrong against the codebase. Three themes:

### (a) Password hashing — 5 segments
Thesis said bare "HMAC-SHA256"; code uses **PBKDF2-HMAC-SHA256, per-user random 16-byte salt, 260,000 iterations** (`storage/db.py:638-665`).
- **P0749.S0 (Ch.3)**
  - before: `Passwords are hashed using HMAC-SHA256 with a random 32-byte salt, stored as a salt:hash string.`
  - after: `Passwords are hashed using PBKDF2-HMAC-SHA256 with a per-user random 16-byte salt and 260,000 iterations, stored as a salt:hash string.`
- **P0447.S1 (Ch.1)**
  - before: `… secure registration and login system using HMAC-SHA256 password hashing. `
  - after: `… secure registration and login system using PBKDF2-HMAC-SHA256 (260,000 iterations, per-user random salt) password hashing. `
- (Same fix, terse form, at **P1054.S0** Ch.4, **P1544.S1** Ch.5, **P1774.S3** Ch.6: `HMAC-SHA256` → `PBKDF2-HMAC-SHA256`.)

### (b) Optimizer rule scope — 1 segment
- **P0457.S1 (Ch.1)** — 2 of the 8 rules act on EC2/RDS (compute), so "non-compute" is false (`optimizer/rules.py:52,135`)
  - before: ` — A Binary LP solver (PuLP/CBC) handles compute rightsizing, while eight heuristic rules handle threshold-based decisions for non-compute services.`
  - after: ` — A Binary LP solver (PuLP/CBC) handles compute rightsizing, while eight service-specific heuristic rules handle threshold-based decisions.`

### (c) Chapter 5 dashboard UI mechanics — 19 segments
The Forecasts/Settings/Home descriptions were corrected to match the actual UI (`dashboard/forecasts.py`, `settings.py`, `home.py`). Representative:
- **P1584.S0 / P1584.S1** — forecast horizon control
  - before: `Forecast horizon (slider):` + ` 7 to 90 days`
  - after: `Forecast horizon (dropdown):` + ` 7, 14, 30, 60, or 90 days`  (`st.selectbox` of discrete values, not a continuous slider)
- **P1585.S0 / P1589.S0** — no "Generate Forecast" button (forecast runs on render)
  - before: `Generate forecast button` / `User clicks "Generate Forecast"`
  - after: `Automatic forecast (no separate generate button)` / `The forecast runs automatically once a model and horizon are selected`
- **P1644–P1647** — System Status section (only 3 read-outs exist; the 4 claimed ones do not)
  - before: `Database path and size` / `Last data collection time` / `Number of users in system` / `Available API quota`
  - after: `Demo Mode status` / `AWS Region` / `Database backend (SQLite)` / `No database path, data-collection time, user count, or API quota is displayed.`
- **P1560.S1** — Home cost chart does not overlay anomalies
  - before: ` — Shows daily costs with anomalies highlighted`
  - after: ` — Shows daily costs over the trailing 30 days`
- **P1690.S0** — adding an account does not start background collection (insert-only)
  - before: `The system begins collecting 12 months of historical data in the background`
  - after: `The new connection is saved to OptiCloud's account list`

(Remaining Ch.5 corrections in this group: **P1550.S0**, **P1558.S0**, **P1563.S0**, **P1581.S1**, **P1587.S0**, **P1597.S1**, **P1648.S1**, **P1692.S0**, **P1719.S0** — all remove false auto-model-selection, "full access" demo, anomaly-table, and live-sync-progress claims while preserving every number.) Chapter 3's parallel design claim **P0768.S0** ("implements an automatic model selection strategy" → "is designed to use …") is also in this group; the underlying design-vs-implementation gap is flagged in `OPEN_QUESTIONS.md` §B.

---

## 10. Metadata fix (`docProps/core.xml`) — 3 fields

The file's Office document properties had stale, chapter-draft values. Corrected (`assembly-log.json`):

| Field | Before | After |
|---|---|---|
| `dc:title` | `Chapter one` | `AWS Cost Intelligence System` |
| `dc:subject` | `Introduction` | `Graduation Project Thesis` |
| `cp:keywords` | *(empty)* | `cloud cost optimization; AWS; time-series forecasting; anomaly detection; linear programming; machine learning` |

Creator (`Ahmed Sameh`) and all created/modified dates were **kept unchanged**.

---

## 11. "→" arrow decisions — all 14 retained

All 14 `→` (U+2192) occurrences (`emoji-hits.json` `arrow_hits`) were reviewed and **retained**. Unlike the decorative emoji, these arrows convey meaningful relationships, render in their existing body font, and are standard in technical writing. They fall into three semantic groups:

1. **Decision-tree / pipeline mappings** — e.g. `Less than 2 weeks of data →`, `Naive → Seasonal Naive → ETS`, `(EC2, RDS) → Binary LP solver …`, `(Lambda, S3, DynamoDB, NAT, ELB) → Eight targeted heuristic rules`.
2. **Navigation paths** — e.g. `Sidebar navigation → "Costs"` / `"Forecasts"` / `"Recommendations"` / `"Settings"`.
3. **Transformations / progressions** — e.g. `Upgrade gp2→gp3`, `Start with read-only recommendations → Low-risk automated actions →`.

Decision: replacing these with words ("to", "then", "maps to") would reduce clarity for no formatting benefit, so they were left in place.

---

## What was explicitly NOT changed

- **All numbers** — MAPE tables, savings %, test counts, recall claims, cost extrapolations — kept verbatim; contradictions vs the canonical paper artifacts are flagged in `OPEN_QUESTIONS.md` §A, never silently edited.
- **The Arabic abstract** (P0050–P0054) — text, RTL run properties, Latin terms, and numbers preserved; flagged for native-speaker review (§F).
- **The cover page** (space-based alignment) and **field-generated TOC / List of Figures** — immutable; cover typos flagged in §E, field refresh noted in §F.
- **Reference entries** — none added/removed; no citation, DOI, author, venue, or year invented.
- **Document design** — styles, fonts, numbering, images, headers/footers, and run structure are byte-preserved; the deterministic audit recorded `hard_fail: []`.
