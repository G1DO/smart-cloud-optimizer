# CHANGELOG — Round 2 (Corrections Pass)

**Document:** *AWS Cost Intelligence System* (OptiCloud) — Graduation Project Thesis
**Input:** `AWS Cost Intelligence System.POLISHED.docx` (Round‑1 output) · **Output:** `AWS Cost Intelligence System.CORRECTED.docx`
**Baseline for the preservation guard:** `work/ORIGINAL.docx` (untouched original)
**Date:** 2026‑06‑26

This pass applied the approved OPEN_QUESTIONS resolutions: it replaced contradicted forecasting/test
results with the project's own canonical numbers (`paper/results.json`, `paper/cv_results.csv`,
`paper/numbers.tex`) and a **live `pytest` run**, fixed citations/abbreviations/cover typos, and made the
honest design‑vs‑implementation reframings — **without changing the visual design** beyond a short list of
explicitly‑approved, logged structural edits. Every changed metric traces to a canonical artifact or the
live test run; nothing was fabricated.

**Totals:** 123 text‑segment edits (40 deterministic table/abbreviation/cover edits + 83 prose edits) and
4 approved structural operations (6 rows deleted, 3 rows added, 1 heading restyled). Preservation guard:
**54/54 PASS**. Full machine‑readable before→after list: `work/final-changes-manifest.json`.

How it was produced (auditable, reproducible): re‑extracted the run/segment model from POLISHED
(`work/extract_r2.py` → `structure-r2.json`); deterministic numeric/table/cover patches authored with hard
assertions against the canonical sources (`work/gen_det_patches.py`); prose corrections produced by a
fan‑out workflow (8 chapter agents → consistency pass → 3 adversarial verifiers); independent ground‑truth
re‑verification fan‑out (45 agreements, 0 discrepancies); deterministic patch audit (`work/audit_prose_patches.py`);
assembly (`work/assemble_r2.py`) and preservation guard (`work/preservation_guard_r2.py`).

---

## Approved Structural Changes (the ONLY non‑text edits — each logged + guarded)

| # | Operation | Detail | Driver |
|---|---|---|---|
| 1 | Delete duplicate **MILP** abbreviation row | removed the 2nd "MILP = Mixed Integer Linear Programming" row (kept the first) | D1 |
| 1 | Delete duplicate **UI** abbreviation row | removed the 2nd "UI = User Interface" row (kept the first) | D2 |
| 2 | Restyle **"5.2.1 Prerequisites"** Heading 2 → Heading 3 | cloned sibling 5.2.2's paragraph + run properties (drops the direct `sz=28`/`szCs=28`) so it now renders identically to its Heading‑3 siblings; the literal "5.2.1" text is unchanged (no auto‑renumber) | F2 |
| 3 | Delete **4 unsupported MAPE rows** (120/180/240/300‑day) from Table 4.4 | those horizons do not exist in the canonical CV (max horizon = 90 d) | A1 |
| 4 | Add **3 omitted test‑suite rows** to Table 4.8 | `test_aws_config.py` (7), `test_components.py` (25), `test_transforms.py` (42) — exist and pass but were missing; added by lossless clone of an existing data row, inserted before the total row | A5 |

The preservation guard's allow‑list permits **exactly** these four operations (plus `<w:t>` text edits and the
pass‑1 `core.xml`/emoji changes) and **fails on any other drift**. (#4 extends the explicitly‑approved list of
the brief to satisfy A5's "add the omitted files"; it is lossless and flagged in OPEN_QUESTIONS_ROUND2.)

---

## A — Results / numbers (use the real, reproducible numbers)

### A1 — Forecasting MAPE Table 4.4 (rebuilt from `paper/cv_results.csv`)
Every value cell rebuilt to the canonical 2‑decimal CV MAPE; winners recomputed as the per‑horizon minimum.
The 120/180/240/300‑day rows were deleted (structural #3). Intro prose P1172 "all four main models across
**nine** forecast horizons" → "across **five of the seven** forecast horizons evaluated".

| Horizon | naive | seasonal naive | ets | prophet | winner (was → now) |
|---|---|---|---|---|---|
| 7 d  | 40.5%→**25.16%** | 16.0%→**10.18%** | 9.2%→**11.28%** | 7.9%→**14.41%** | Prophet → **Seasonal Naive** |
| 14 d | 22.9%→**27.90%** | 17.9%→**10.84%** | 10.5%→**11.24%** | 9.8%→**20.47%** | Prophet → **Seasonal Naive** |
| 30 d | 25.7%→**27.26%** | 14.6%→**12.28%** | 10.4%→**11.20%** | 9.5%→**20.93%** | Prophet → **ETS** |
| 60 d | 25.5%→**27.87%** | 14.9%→**12.66%** | 10.8%→**11.39%** | 22.2%→**19.70%** | ETS (unchanged) |
| 90 d | 25.8%→**27.38%** | 13.1%→**12.91%** | 12.0%→**12.15%** | 12.4%→**18.08%** | ETS (unchanged) |

### A2 — "Prophet best / 7.9–9.8% MAPE" → ETS reality (everywhere)
Rewrote the forecasting headline across the abstract, Ch.3 (§3.4.4 + Table 3.4 metric), Ch.4 (§4.5 findings
bullets), and Ch.6 to: **ETS best overall ≈11.2% MAPE; Seasonal Naive most accurate at 7–14 days (~10–11%);
Prophet among the least accurate (~14–22%).** Representative:
- Ch.4 P1238.S1: "achieves the best accuracy for short horizons … MAPE as low as 7.9%" → "is among the least accurate of the four models, with MAPE ranging from roughly 14% to 22% and never winning at any horizon".
- Ch.3 §3.4.4 P0774: "Prophet … best accuracy (MAPE: 7.9–9.8%)" → "Seasonal Naive and ETS … best accuracy (MAPE: ~10–12%)"; ETS long‑horizon "MAPE: 10.8–20.6%" → "~11–12%".
- Ch.6 P1770/P1787/P1788/P1789/P1821 ranges all reconciled to the ETS reality.
- Ch.2 lit‑review (P0535) and Table 2.1 Prophet cell (P0555): "~7.9–9.8%" → "~14–22%".

### A3 — Dataset length P1150: "425 days" → **365 days**.

### A4 — Training‑size Table 4.5 relabelled illustrative
Caption P1285 → "… (30‑day forecast, **illustrative**)"; dependent prose P1289.S2 reframed: these are
"illustrative results from an earlier offline forecasting analysis rather than the canonical walk‑forward
cross‑validation". Ch.3 P0765 ">1,000% MAPE" attributed to the illustrative training‑size analysis (Table 4.5).

### A5 — Test suite (live `pytest`: 217 passed, 0 failed, +1 collection error)
Table 4.8 cells corrected to live counts and the 3 omitted suites added (structural #4):

| file | before → now | file | before → now |
|---|---|---|---|
| test_config.py | 3 → **8** | test_ai_module.py | 13 → **12** |
| test_date_utils.py | 8 → **14** | test_auth.py | 144 → **20** |
| test_ml_utils.py | 45 → **38** | test_aws_config.py | (added) **7** |
| test_storage.py | 25 → **24** | test_components.py | (added) **25** |
| test_optimizer.py | status "26 passing, 1 failing" → **All passing** (27) | test_transforms.py | (added) **42** |
| test_synthetic.py | "12 / All passing" → "**— / Collection error**" | **total** | 277 / "276 passing" → **217 / "217 passing (+1 collection error)"** |

Prose: §4.9 narrative and Ch.1/Ch.3/Ch.6 recurrences "277 tests" → **217**; P1423 "1 failing test in
test_optimizer.py is a known edge case" → "the test suite reports no failures; … test_optimizer.py passes all
27 of its tests" and the only issue is the `test_synthetic.py` collection error (missing `data_generation`
package). AI‑module "13 tests" (P1369) → **12**.

### A6 — AI‑module tests "13" → **12** (P1369; recurs in the Ch.6 conclusion P1462).

### A7 — AI "$875.25" example labelled illustrative (P1374): "… an estimated monthly cost of **$875.25
produced by the language model (a non‑deterministic … illustrative example)**".

### A8 — Anomaly detection: "100% recall" + NAB‑validation removed
Attributed to the **global μ+2σ surge threshold (≈$120.38/day; max z‑score 6.9), five surges** (P1162, P1293,
P1771). NAB/Kaggle overclaims softened from "used to validate" → "informed the design / public reference
benchmark" (P0565, P0575, P1074). The count of five anomalies is preserved.

### A9 — Cost reduction "29.5%" → **~27% (26.97%) of the $2,189.48 bill** (P1803); the hypothetical $2,000
denominator replaced with the actual $2,189.48 bill across 42 resources.

### A10 — Portfolio extrapolations labelled illustrative: "$59,040 **projected** total monthly savings
(100 × $590.40)", "$708,480 **projected** annual savings", "an **estimated** 140–240 hours/year saved".

### A11 — Table 4.3 resource itemization (sums to 41 vs canonical 42): **flagged**, not fabricated (see
OPEN_QUESTIONS_ROUND2).

### Ch.6 conclusion P1462 — consolidated to the corrected facts (ETS ≈11.2%; user‑selected model with ETS
default; five surges via μ+2σ; 12 AI tests; 217 tests); "across **8** AWS services" → "across **six** AWS
services" (n_services_billed = 6; 8 was the EC2 instance count).

## B — Design vs implementation (honest framing)
- **B1** model selection: "automatic model selection" reframed to design‑intent / offline analysis (manual
  dropdown, ETS recommended default) in the abstract, Ch.1 (P0442 also now names all five models: Naive,
  Seasonal Naive, ETS, Prophet, SARIMAX), Ch.3 §3.4.4 (P0768 "automatic" dropped), Ch.6, and the Ch.2
  novelty paragraph (P0594). Table 4.9 cell P1441 "Implemented model selection tree …" → "Designed a
  model‑selection strategy by data age …".
- **B2** the 120/30‑day CV described as the **offline** (paper) cross‑validation, not a runtime feature (P0455).
- **B3** "anomalies excluded from training" reframed as design intent (P1791, P1827).
- **B4** Demo Mode honestly caveated: the `demo@cis.asu.edu.eg` account must be seeded or "Try Demo Mode"
  fails silently (P1550).
- **B5** "adding an account triggers background collection" corrected to manual collection; heading **5.4.3
  "Data Collection Background Process" → "Running Data Collection"** (P1690/P1691).
- **B6** Ch.5 UI specifics corrected: spinner not progress bar (P1590); Forecasts MAPE/RMSE/MAE "coming
  soon, not yet shown" (P1595); Priority filter high/medium/low not "confidence" (P1606); password change
  "not yet implemented" (P1627); account creation date "not currently displayed" (P1628); Test Connection
  only on the Add form (P1635); save‑as‑PDF/bookmark reframed (P1701). (Horizon dropdown / no‑Generate‑button
  / PBKDF2 already fixed in pass 1 — left as‑is.)
- **B7** `extract_json` boundary‑detection only (P0873); STS 1 h default / DurationSeconds not set (P0714);
  questionnaire option wording tightened to the code (P0861/P0864).

## C — Citations (fixed in place; no sources invented)
- **C1** Flexera "State of the Cloud Report" **2023 → 2024** (reference P1918); in‑text Gartner attribution
  for "30–35% wasted" removed so it cites Flexera only (P0432, P0526).
- **C2** Gartner reference (untraceable) — **flagged** (left in list; remove in the master copy).
- **C3** RightScale "63%" — kept the softened "industry surveys report …" wording; **flagged** for a source.
- **C4** Liu et al. CSUR‑2025 — **flagged** (DOI/title unconfirmed).
- **C5** Cortez "Resource Central" SOSP‑2017 — confirmed real; left as‑is, **flagged** (absent from curated bib).
- **C6** orphan Kaggle datasets (zoya77/programmer3) — inline attributions softened to "from Kaggle"; **flagged**.
- **C7** "Several recent works …" softened (P0586).
- **C8/C9** — Gemini docs attribution + P1919/P1924 formatting **flagged** (structural, not risked).

## D — Abbreviations
- **D1/D2** duplicate MILP + UI rows deleted (structural #1).
- **D3** SQLite: "Structured Query Language Lite" → "**Lightweight embedded SQL database engine**".
- **D4** GWA: "Grid Workload Archive" → "**Grid Workloads Archive**" (matches reference P1925).

## E — Cover page (text‑only; alignment preserved)
- **E1** "Dr.Hafez Moawad" → "Dr. Hafez Moawad".
- **E2** "Faculty of computer & Information Science," → "Faculty of **Computer** & Information **Sciences**,"
  in all three occurrences (P0025, P0030, P0035). On the two‑column line P0030 the inter‑column gap was
  reduced by one space to preserve the right‑column alignment.
- **E3** "the degree of bachelors" → "the degree of **Bachelor's**".
- **E4** "Computer System**s** Department?" — **flagged** (low confidence), not forced.

## F — Front matter & structure
- **F2** heading 5.2.1 restyled to Heading 3 (structural #2).
- **F4** Ch.4 caption numbering fixed: the Anomaly‑Severity table caption "Table 4.5 … Training Data Size" →
  "**Table 4.6: Anomaly Severity Classification**"; the Optimizer‑results table caption "Table 4.6: Anomaly
  Severity" → "**Table 4.7: Optimizer Results**" (numbers confirmed by the front‑matter List of Tables and the
  in‑text references P1243→4.5, P1317→4.7).
- **F1/F3/F5** — Arabic abstract, field refresh, and cover metadata: **flagged** (see OPEN_QUESTIONS_ROUND2).

## G — Title convention (confirmed, unchanged)
Formal "AWS Cost Intelligence System" + product "OptiCloud" kept consistently; the code's third name "Smart
Cloud Optimizer" was **not** introduced.

---
> **After opening in Word:** select all (Ctrl+A) and press **F9** to refresh the Table of Contents, List of
> Tables, and List of Figures so the renamed heading 5.4.3 and the Table 4.6/4.7 caption fixes propagate, then
> re‑check page numbers. (Word fields cannot be refreshed programmatically.)
