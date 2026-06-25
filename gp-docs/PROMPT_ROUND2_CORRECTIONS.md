# MASTER PROMPT (ROUND 2) — Apply the OPEN_QUESTIONS Corrections Without Touching the Design

Paste everything below the horizontal rule into Claude Code as a single prompt. It is self-contained.

This is a **follow-up** to the first polishing pass. The first pass cleaned the prose and produced `…POLISHED.docx`, `CHANGELOG.md`, `PRESERVATION_REPORT.md`, and `OPEN_QUESTIONS.md`. **This pass applies the approved resolutions to OPEN_QUESTIONS** — most importantly, it replaces the contradicted forecasting/test results with the **real, reproducible numbers from the project's own `paper/` artifacts** — while keeping the visual design byte-faithful.

---

## Mission
You are working in this graduation-project repository. Your job is to take the already-polished thesis and apply a **specific, approved set of corrections** (listed below) so that every reported number, abbreviation, citation, and cover-page detail is accurate and internally consistent — **without changing the visual design** (fonts, sizes, heading styles, page layout, Table of Contents, headers, footers, cover page, figures). You improve only *words and their correctness*; the on-page look stays identical except for a small, explicit list of approved structural fixes that are logged and guarded.

The guiding decision from the team is: **use the real, reproducible numbers.** Where the thesis contradicts the project's own canonical data (`paper/results.json`, `paper/cv_results.csv`, `paper/numbers.tex`, `paper/mape_tabular.tex`) or the runtime code, **correct the thesis to match reality.** Do not invent anything; where a number has no source, relabel it as illustrative or flag it — never fabricate.

You MUST do this rigorously by orchestrating with the **Workflow tool + fan-out subagents + an independent adversarial verification pass and a preservation guard** — not a single linear edit.

---

## STEP 0 — Orient yourself (do this first; do not trust hardcoded paths)
The first pass may have run in a different folder than this one. Find reality before editing:
1. Locate the docs folder (it may be `gp-docs/`, `docs-gp/`, or similar) and, inside it, the **already-polished** thesis (a `*POLISHED*.docx`). **Edit the POLISHED file**, not the original. If no POLISHED file exists, fall back to the original thesis `.docx` and say so.
2. Locate the immutable baseline `…/work/ORIGINAL.docx` from pass 1 (or, if absent, treat the untouched original `.docx` as the baseline and copy it to `…/work/ORIGINAL.docx`).
3. Locate the canonical data: `paper/results.json`, `paper/cv_results.csv`, `paper/numbers.tex`, `paper/mape_tabular.tex`, and the source code (`ml_engine/`, `optimizer/`, `dashboard/`, `aws_collector/`, `tests/`).
4. Confirm tooling: `python-docx` + `lxml` (install if missing; if install fails, use raw-XML run-level edits). Check whether `pytest` runs so you can get **live** test counts.
5. Re-use the pass-1 working artifacts if present (`…/work/structure.json`, `segments/`, `assemble.py`, `preservation_guard.py`). If they are gone, rebuild the run/segment model exactly as pass 1 did (unzip, map paragraphs→runs with global indices, validate a lossless round-trip) before editing.

> **Verify, don't trust.** Re-read each `paper/` value and re-run `pytest` yourself. The numbers quoted in this prompt are the expected ground truth, but the live artifacts win if they ever differ — and you must log any difference.

---

## THE #1 CONSTRAINT — PRESERVE THE DESIGN (unchanged from pass 1)
The current fonts/formatting are mandated by the college. **Treat the visual design as immutable.** You may change *text content*; you may **not** change how anything looks, except for the short **Approved Structural Changes** list in the next section. Specifically, do NOT change (for any paragraph, edited or not): fonts (body stays **Times New Roman**; keep the existing `Cambria Math` equation run; introduce no new font), font sizes (`w:sz`/`w:szCs`), named styles and style references, bold/italic/underline, colour, spacing, indentation, alignment, list numbering, tab stops (including the TOC dot-leader tabs), the cover/title page layout, headers/footers, page-number fields, section properties/breaks, page geometry/margins, and the six embedded images (byte-identical, in place). Keep all plumbing parts (`styles.xml`, `theme1.xml`, `numbering.xml`, `settings.xml`, `webSettings.xml`, `fontTable.xml`, `footnotes.xml`, `endnotes.xml`, `customXml/*`, all `*.rels`, `[Content_Types].xml`) **byte-identical**. Edit only `<w:t>` text (plus `docProps/core.xml` and the approved structural changes). Carry the original run's full `<w:rPr>` onto any run you split/join. Re-zip losslessly; the file must open in Microsoft Word with no repair prompt.

### Approved Structural Changes (the ONLY permitted non-text edits — each must be logged)
These were explicitly approved by the team. Apply them losslessly (clone neighbouring formatting where needed) and record each in the changelog; everything else stays text-only:
1. **Delete the duplicate "MILP" abbreviation row** and the **duplicate "UI" abbreviation row** in the List of Abbreviations (remove exactly one of each duplicate table row).
2. **Restyle "5.2.1 Prerequisites" from Heading 2 → Heading 3** so it matches its sibling sub-headings (`5.2.2`, etc.).
3. **Remove the unsupported long-horizon rows** (120/180/240/300-day) from the forecasting MAPE table — see correction A1 — because no data supports them; adjust the surrounding prose accordingly. (If removing rows is risky in the table structure, instead relabel those rows' values as "—" / "not evaluated" and note it; pick the lossless option and log which.)
4. **(Optional, only if the team wants the references complete)** Add a missing reference entry **only** by cloning an existing reference paragraph's exact `rPr`/`pPr` and editing its text. If you are not fully confident it stays lossless, **do not add it — flag it** in OPEN_QUESTIONS instead.

Update the pass-1 `preservation_guard.py` so its allow-list permits **exactly** these logged structural changes (and the `core.xml` + `<w:t>` text changes) and **fails on any other drift**. Run it as a hard gate (see final phase).

---

## THE CANONICAL NUMBERS (ground truth — verify against `paper/` then apply)

**Forecasting cross-validation MAPE (%), from `paper/cv_results.csv`** — this is the real table:

| Model | h=7 | h=14 | h=21 | h=30 | h=45 | h=60 | h=90 |
|---|---|---|---|---|---|---|---|
| **SeasonalNaive** | **10.18** | **10.84** | 11.85 | 12.28 | 12.14 | 12.66 | 12.91 |
| **ETS** (selected/best overall) | 11.28 | 11.24 | **11.54** | **11.20** | **11.38** | **11.39** | **12.15** |
| Prophet | 14.41 | 20.47 | 22.11 | 20.93 | 19.31 | 19.70 | 18.08 |
| Naive | 25.16 | 27.90 | 27.51 | 27.26 | 27.47 | 27.87 | 27.38 |

- **Best overall model = ETS, ≈11.2% MAPE.** SeasonalNaive wins the shortest horizons (7, 14 d); **Prophet is one of the worst (14–22%), never the winner.** The thesis's "Prophet best, 7.9–9.8%" is wrong and must be replaced.
- Holdout: ETS, 12.0% MAPE, 97% coverage. CV config = 120-day initial / 30-day step (matches the paper's offline CV).

**Cost / system numbers, from `paper/results.json` + `paper/numbers.tex`:**
- Dataset: **365 days** (2024-07-01 → 2025-06-30); mean daily $74.64; annual total $27,243.31. *(Thesis "425 days" → 365.)*
- Anomalies: **5 surges** via a **global μ+2σ threshold = $120.38** (max z = 6.9). *(There is NO "100% recall" and NO "NAB-validated" artifact — remove both; keep "5 anomalies detected"; attribute the detector correctly as the global μ+2σ surge threshold.)*
- Recommendations: **19 total** (10 AI-assisted). Total monthly savings **$590.40**. Flagged cost $1,074.83 → after $484.43 = **54.9%** of flagged spend.
- Total monthly bill **$2,189.48** across **42 resources** (8 EC2). **Savings = 26.97% (≈27%) of the $2,189.48 bill.** *(Thesis "29.5%" used a $2,000 made-up denominator → use 27% of $2,189.48, or state both explicitly.)*
- Savings by type: Right-size (MILP) 2 → $362.81; Reserved/pricing switch 6 → $208.42; Delete unused 3 → $10.00; NAT→VPC endpoint 2 → $5.67; EBS 4 → $2.60; S3 1 → $0.79; Lambda 1 → $0.11. By severity: High 8 → $370.52; Medium 9 → $214.21; Low 2 → $5.67.
- **Test counts: do NOT hardcode — run `pytest` and report the live result.** The known live result was ≈**217 collected, 217 passing, 0 failing, plus 1 collection error** (`test_synthetic.py` imports a missing `data_generation` package, so its tests never run). The thesis's "277 tests / 276 passing / 1 failing" is wrong. Describe the collection error honestly. AI-module tests = **12** (thesis said 13). Use whatever `pytest` actually prints, and reconcile every per-file count and total to it.
- The AI "$875.25" example, the "$59,040/month" and "$708,480/year across 100 companies", and "140–240 hours/year saved" are **projections/illustrative LLM output with no artifact** → label each explicitly as an *illustrative estimate/projection*, do not present as measured results.

---

## THE CORRECTIONS TO APPLY (grouped; segment IDs are from pass-1 `OPEN_QUESTIONS.md` — locate by ID and by surrounding text)

> Policy for every item: **make the smallest edit that makes it true.** Never change a number to something unverified. Where the fix is a number, use the canonical value above (after confirming it in `paper/`). Where a claim has no supporting artifact, relabel as illustrative or flag — do not delete meaning silently.

### A — Results / numbers (CRITICAL — use the real numbers)
- **A1 — Forecasting MAPE table (Table 4.4, segs P1174–P1233):** rebuild every cell from `cv_results.csv` (table above). Set winners to **SeasonalNaive (h7, h14)** and **ETS (h21–h90)**. **Remove the 120/180/240/300-day rows** (approved structural change #3) and fix the prose "nine forecast horizons" (P1172.S0) to the real count (seven). Reword any "Prophet best for short horizons" caption/note.
- **A2 — "Prophet best / 7.9–9.8% MAPE" everywhere** (P1238.S1; abstract P0047.S0; Ch.3 P0765.S1, P0774.S1, P0917.S0, P0919.S0; Ch.6 P1770.S3, P1789.S1): rewrite to **ETS ≈11.2% (best overall), SeasonalNaive best at 7–14 days.** In the abstract, replace any Prophet/7.9–9.8% claim with the ETS ≈11–13% reality.
- **A3 — Dataset length (P1150.S1):** "425 days" → **365 days**.
- **A4 — Training-size MAPE table (Table 4.5, P1245–P1284):** no shipped artifact reproduces these. **Relabel the table/caption as results from an earlier `forecasting_models.md` run (illustrative, not from the canonical CV)** and soften the dependent prose (P1289.S2). Do not present as reproducible. If the team prefers, flag for removal instead.
- **A5 — Test suite (Table 4.8 & §4.9; P1378, P1418, P1419, P1386/P1390/P1394/P1398/P1402/P1410/P1414, P1423; recurs P0459.S1, P0947.S0, P1781.S0, P1066.S0):** run `pytest`, then rewrite the counts, the per-file rows, and totals to the **live numbers**. Add the existing-but-omitted files (`test_aws_config.py`, `test_components.py`, `test_transforms.py`). Replace "1 failing test in `test_optimizer.py`" with the truth (optimizer passes; the real issue is the `test_synthetic.py` **collection error** from the missing `data_generation` package). Fix `test_auth.py` count.
- **A6 — AI-module "13 tests" (P1369.S0, P1462.S0):** → **12** (or the live count).
- **A7 — "$875.25" AI example (P1374.S0):** mark as an illustrative example or remove the exact figure.
- **A8 — "100% recall" + "NAB CloudWatch validated" (P1771.S3; recurs P1074.S0, P1158–P1162, P1293.S0, P1311.S0, P1827.S1):** remove the recall and NAB-validation claims; attribute detection to the **global μ+2σ surge threshold (5 surges)**. Keep the "5 anomalies" count.
- **A9 — "29.5% cost reduction" (P1803.S3):** → **26.97% (≈27%) of the $2,189.48 bill**, or state both the $590.40 saving and the $2,189.48 base explicitly.
- **A10 — Portfolio extrapolations (P1804.S0, P1805.S0, P1811.S1):** label "$59,040/month", "$708,480/year across 100 companies", and "140–240 hours/year" explicitly as **illustrative projections/estimates**.
- **A11 — Resource itemization (Table 4.3, P1111–P1143):** reconcile the itemized count to **42** resources (low priority).

### B — Design vs implementation (use real numbers / honest framing)
For each, either reframe as explicit **design intent** ("the system is designed to…") or correct to the runtime reality; flag the few that are pure narrative judgment. Default to the honest, runtime-accurate wording:
- **B1 — Automatic model-selection tree** (abstract P0047.S0; P0442.S1, P0455.S1; §3.4.4 P0767–P0776, P0786.S0, P0941.S0; Ch.5 P1581.S1, P1587.S0, P1597.S1; Ch.6 P1786.S2, P1789.S1, P1892.S0): the app uses a **manual model dropdown defaulting to Prophet**; the "data-age → model" tree exists only in docs. Reframe as "designed to / offline analysis" or correct to manual selection. Also fix P0442.S1 naming only 3 of the 5 models (the five are Naive, SeasonalNaive, ETS, Prophet, SARIMAX).
- **B2 — CV "120-day/30-day, best-model-per-horizon"** (P0455.S1, P0786.S0, P0941.S0, P1151.S1, P1152.S1): clarify these describe the **paper's offline CV**, not a runtime feature (the app's CV defaults differ).
- **B3 — "Anomalies excluded from training"** (P0756.S0, P1311.S0, P1791.S0, P1827.S1): the forecast path does not exclude anomalies. Reframe as design intent or correct.
- **B4 — Demo-mode login** (P1545.S1, P1546.S1, P1550.S0): the demo user `demo@cis.asu.edu.eg` is absent from the shipped DB → soften/qualify, or note the team should seed it.
- **B5 — "Adding an account triggers background collection"** (P1690.S0, P1691 heading, P1692.S0; P0451.S4, P0438.S0): it does not; collection is run manually. Correct the prose and **rename the "5.4.3 … Background Process" heading** if it implies automatic collection.
- **B6 — Ch.5 UI specifics** (P1590, P1595, P1606, P1627, P1628, P1632, P1634, P1635, P1701): correct each to the actual UI (e.g., spinner not progress bar; no password-change; status emoji not "last sync time"; no save-as-PDF). Where unsure, flag.
- **B7 — Minor imprecisions** (P0873.S0 `extract_json`; P0714.S0 STS timeout/retry; P0859/P0861/P0864 questionnaire option wording): tighten to match code or flag.

### C — Citations (fix in-place text; do not invent sources)
- **C1 — Flexera year** (ref P1918.S0; in-text P0432.S0, P0526.S0): 2023 → **2024**.
- **C2 — Gartner entry** (ref P1919.S0; in-text P0526, P0432.S0): untraceable → cite Flexera only or remove; **flag** if unsure.
- **C3 — RightScale "63%"** (P0526.S0, P0433.S0): keep the softened "industry surveys report…" wording or drop the figure; flag for a real source.
- **C4 — Liu et al. CSUR-2025** (ref P1917, in-text P0560): verify title/authors/DOI `10.1145/3719003` before relying on it; flag.
- **C5 — Cortez "Resource Central" SOSP-2017** (ref P1915, in-text P0524): real paper; confirm the entry is acceptable.
- **C6 — Orphan Kaggle datasets** (P0565 zoya77; P0575 programmer3; Table 4.2): add reference entries (only via approved-clone) or drop the inline attributions; flag.
- **C7 — "Several recent works" (P0586):** cite 1–2 specific works or soften.
- **C8 — Gemini docs attribution (ref P1922.S0):** "Google Cloud" → Google AI / ai.google.dev (optional).
- **C9 — Reference-list formatting** (P1919.S0 style mismatch; P1924 missing trailing segment): normalise to match sibling entries (structural-formatting; do losslessly or flag).
- Keep the thesis's informal author–year citation style; **do not** convert to numbered IEEE.

### D — List of Abbreviations
- **D1 — Delete the duplicate MILP row** (P0300.S0 / P0349.S0 → keep one). *(Approved structural change.)*
- **D2 — Delete the duplicate UI row** (P0329.S0 / P0375.S0 → keep one). *(Approved structural change.)*
- **D3 — "SQLite"** (P0325.S0): "Structured Query Language Lite" → **"Lightweight embedded SQL database engine"** (or remove the row — SQLite is not an acronym).
- **D4 — "GWA"** (P0343.S0): "Grid Workload Archive" → **"Grid Workloads Archive"** (plural).

### E — Cover page (text-only word fixes; do not disturb the space-based alignment)
- **E1** "Dr.Hafez Moawad" → **"Dr. Hafez Moawad"** (P0023.S0).
- **E2** "computer" → **"Computer"**, "Science" → **"Sciences"** (P0025.S0, P0029, P0030, P0036) to match the acknowledgments.
- **E3** "the degree of bachelors" → **"the degree of Bachelor's"** (P0007.S0).
- **E4** "Computer System Department" → likely **"Computer Systems Department"** (P0024.S0, P0029, P0034) — **low confidence; flag for confirmation** rather than forcing.

### F — Front matter & structure
- **F1 — Arabic abstract** (P0050–P0054): leave the text unchanged; **flag for a native Arabic-speaker review** (formal MSA, mirrors the finalized English). Do not auto-translate or reorder.
- **F2 — Heading "5.2.1 Prerequisites"** (P1520.S0): restyle Heading 2 → **Heading 3**. *(Approved structural change #2.)*
- **F3 — TOC / List of Figures / List of Tables** are field-generated: after edits, they need refreshing in Word (Ctrl+A → F9). You cannot refresh Word fields programmatically — **add a clear note** to the deliverables telling the team to refresh fields and re-check page numbers. If LibreOffice is available, you may regenerate fields headlessly as a convenience, but the team must still verify in Word.
- **F4 — Ch.4 table caption swaps** (P1307.S0, P1355.S0): fix the mislabeled "Table 4.5/4.6" captions so each caption sits over the correct table.
- **F5 — Cover metadata** (supervisor/committee/date): **flag for the team to confirm** they are final.

### G — Title convention (confirm, change nothing)
Keep the two intentional names — formal title **"AWS Cost Intelligence System"** and product name **"OptiCloud"** — applied consistently; **do not** introduce the code's third name "Smart Cloud Optimizer." Note this as confirmed in the changelog.

---

## ORCHESTRATION PLAN (Workflow tool + fan-out subagents + adversarial verification)
Drive the whole job through the **Workflow tool**. Persist intermediate artifacts under `…/work/` so it is auditable and resumable.
1. **Phase 0 — Orient & baseline:** do STEP 0; snapshot the POLISHED file you will edit; confirm the baseline and the canonical artifacts; rebuild/reuse the run-segment model; validate a lossless round-trip.
2. **Phase 1 — Ground-truth (fan-out, read-only):** independent subagents re-extract the canonical numbers from `paper/`, run `pytest` for live test counts, and read the relevant code paths (forecaster/anomaly/optimizer/dashboard) so every correction is evidence-backed. Produce a `corrections-ground-truth.md`. **Any value that disagrees with this prompt's quoted numbers → use the artifact and log the difference.**
3. **Phase 2 — Apply corrections (fan-out by section A–G):** one subagent per group edits its segments per the list above, returning run-aligned revised text + a per-change log + any flags. No skeleton change beyond the Approved Structural Changes. Conservative, minimal edits.
4. **Phase 3 — Consistency pass (single agent):** ensure a corrected number is updated **everywhere** it recurs (e.g., the ETS-best fact and the live test count appear in abstract, Ch.3, Ch.4, Ch.6); unify terminology; ensure table/figure numbers and cross-references still resolve.
5. **Phase 4 — Adversarial verification (independent fan-out, before assembly):** independent red-team subagents try to break it: a **fact-checker** re-confirms every changed number against `paper/`/`pytest`; a **no-fabrication auditor** confirms no invented source/number; a **meaning-preservation auditor** confirms only the intended claims changed. A **deterministic number audit** diffs old vs new segments and FAILS on any numeric change that is not on the approved correction list. Loop Phases 2→4 until clean.
6. **Phase 5 — Assembly (single agent, only writer of XML):** write revised text back to exact runs (inherit original `rPr`); apply the Approved Structural Changes losslessly; fix `docProps/core.xml` only if still needed; re-zip losslessly to a new `…CORRECTED.docx` (keep POLISHED and ORIGINAL intact).
7. **Phase 6 — Preservation guard (independent, HARD gate):** run the updated `preservation_guard.py` comparing ORIGINAL vs CORRECTED. It must PASS: identical part inventory except the allowed parts; no new font; Times New Roman + Cambria Math intact; all size/style/numbering/tab/section multisets invariant except the logged Approved Structural Changes; byte-identical media and plumbing; valid ZIP; opens in Word with no repair. Any other drift = fail → fix and repeat.

---

## Deliverables (in the docs folder)
1. **`…CORRECTED.docx`** — the corrected thesis. POLISHED and ORIGINAL remain untouched.
2. **`CHANGELOG_ROUND2.md`** — every correction by category (A–G), with before→after values and counts, plus the list of Approved Structural Changes applied.
3. **`PRESERVATION_REPORT_ROUND2.md`** — the guard results (pass/fail per check) and the baseline-vs-corrected fingerprint diff.
4. **`OPEN_QUESTIONS_ROUND2.md`** — what remains for humans: the Arabic-abstract native review, the low-confidence "Computer Systems Department" name, cover metadata/date confirmation, any citation that needs a real source (Gartner, RightScale 63%, Liu et al., Kaggle datasets), and anything you had to flag instead of fix.

---

## Guardrails (non-negotiable)
- **Use the real numbers; never fabricate.** Every changed metric must trace to `paper/` or live `pytest`. No invented citation/DOI/author/year/metric. Unsourced claims get relabeled as illustrative or flagged — never deleted silently.
- **Never change the visual design** beyond the explicit Approved Structural Changes list, each logged and guarded. A design regression fails the task.
- **Preserve author intent**; make minimal, surgical edits; keep the chapter/section skeleton (apart from the approved row/heading fixes).
- **When uncertain about a fact or a formatting risk, stop and flag — do not guess.**

## Definition of Done (all must be true)
- [ ] Workflow ran all phases; Phases 1 and 4 fanned out subagents; Phase 4 used independent adversarial verifiers; Phase 6 ran the preservation guard.
- [ ] `…CORRECTED.docx` opens in Word with no repair prompt and is visually identical to the original except the logged Approved Structural Changes.
- [ ] **Preservation guard passed** (no new font; TNR + Cambria Math intact; all formatting multisets invariant except the logged structural changes; byte-identical media/plumbing).
- [ ] Forecasting table and all "best model / MAPE" prose now match `cv_results.csv` (ETS ≈11.2% best; Prophet not best); dataset = 365 days.
- [ ] Test counts match a live `pytest` run; the `data_generation` collection error described honestly; AI tests = 12 (or live count).
- [ ] Savings stated as 26.97%/≈27% of $2,189.48 (or both figures); projections labeled illustrative; "100% recall"/NAB claims removed; detector attributed to the μ+2σ surge threshold (5 surges).
- [ ] Abbreviations fixed (no duplicate MILP/UI; SQLite + GWA corrected); citations fixed in place (Flexera 2024, etc.) with unsourced ones flagged; cover typos fixed (E4 flagged).
- [ ] Heading 5.2.1 restyled to Heading 3; mislabeled Ch.4 table captions fixed; a clear "refresh TOC/lists (Ctrl+A → F9) in Word" note included.
- [ ] All four deliverables produced.

Begin with STEP 0 / Phase 0. Do not skip the adversarial verification (Phase 4) or the preservation guard (Phase 6) — they keep this both accurate and safe for the college font.
