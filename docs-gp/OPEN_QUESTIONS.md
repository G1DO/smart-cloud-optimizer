# Open Questions — Items for the Human Team

**Document:** *AWS Cost Intelligence System* (OptiCloud) — Graduation Project Thesis

This is the consolidated, deduplicated list of everything the team must **supply, confirm, or reconcile** before the thesis is final. It merges all per-chapter `*.flags.md` files with every CONTRADICTED / UNVERIFIED item from the four code-grounded briefs (`ground-truth-A/B/C/D.md`).

**How to read this:** the polishing pass deliberately **did not change any number, citation, reference entry, Arabic text, cover-page text, or document style.** Where a claim is contradicted by the canonical paper artifacts (`paper/results.json`, `paper/cv_results.csv`, `paper/numbers.tex`, `paper/main.tex`) or by the runtime code, it is recorded below with thesis value, canonical/actual value, segment ID, and a recommended action — for **you** to decide and apply, not for the editor to apply silently.

Priority legend: **A = critical** (factual results that will not withstand review) · B = design/implementation reconciliation · C = citations · D = abbreviations · E = cover page · F = front matter & structural · G = decision confirmation.

---

## A. CRITICAL — results / numbers contradicted by the canonical paper artifacts

> **Do NOT silently change these.** The thesis presents an older forecasting/test run; the paper's `results.json` / `cv_results.csv` are the canonical, reproducible source. Every item is left in the thesis text unchanged. Decide per item: (i) replace with canonical values, (ii) relabel the source/provenance, or (iii) supply the missing generating artifact.

### A1. Chapter 4, Table 4.4 — entire MAPE-by-horizon table (segments P1174–P1233)
The whole table comes from `documentation/forecasting_models.md` (older run) and is contradicted by `paper/cv_results.csv`.

| Cell | Thesis value | Canonical value | Segment |
|---|---|---|---|
| Prophet @ 7 d | 7.9% | **14.41%** | P1184.S0 |
| Prophet @ 14 d | 9.8% | **20.47%** | P1190.S0 |
| Prophet @ 30 d | 9.5% | **20.93%** | P1196.S0 |
| Winners @ 7 / 14 / 30 d | Prophet / Prophet / Prophet | **SeasonalNaive (7,14), ETS (30)** | P1185 / P1191 / P1197 |
| ETS @ 7 d / 30 d | 9.2% / 10.4% | **11.28% / 11.20%** | P1183 / P1195 |
| SeasonalNaive @ 7 d | 16.0% | **10.18%** | P1182 |
| Naive @ 7 d | 40.5% | **25.16%** | P1181 |
| Horizon rows 120 / 180 / 240 / 300 d | listed | **absent** (canonical CV max horizon = 90 d) | P1210–P1233 |

Canonical overall winner = **ETS, ~11.2% MAPE**; **Prophet is never the winner** (2nd-worst at every horizon). **Action:** replace the table with canonical values, or explicitly relabel it as the older `forecasting_models.md` run and reconcile the surrounding prose (incl. P1172.S0 "all four main models across nine forecast horizons" — canonical CV has only 7 horizons).

### A2. "MAPE as low as 7.9%" / "Prophet best for short horizons" (P1238.S1; recurs at P0047.S0 abstract, Ch.3 P0765.S1 / P0774.S1 / P0917.S0 / P0919.S0, Ch.6 P1770.S3 / P1789.S1)
- **Thesis:** Prophet best, 7.9–9.8% MAPE short-term.
- **Canonical:** best = ETS ~11.2%; Prophet 2nd-worst (14.4–22.1%). The 7.9–9.8% range **does not appear anywhere** in `results.json` / `cv_results.csv`.
- **Action:** rewrite the finding from the canonical CV, or supply the artifact that produced 7.9–9.8%. (Abstract's broader "≈10–18%" is only loosely supportable — upper bound 18% comes from the training-size table, not per-horizon CV.)

### A3. Cross-validation dataset length "425 days" (P1150.S1)
- **Thesis:** 425 days. **Canonical:** `results.json` n_days = **365** (2024-07-01 → 2025-06-30); fold counts are consistent with 365.
- **Action:** reconcile to 365.

### A4. Chapter 4, Table 4.5 — training-size MAPE (P1245–P1284)
- Values (e.g. Prophet @ 7 d = 1015%, ETS @ 7 d = 297%) match `forecasting_models.md` but **no supporting JSON/CSV is shipped** in `paper/`. Conclusion prose P1289.S2 derives from it.
- **Action:** attach the generating artifact, or remove/relabel the table as non-reproducible.

### A5. Test-suite results — "277 tests / 276 passing / 1 failing" (P1378.S0, P1418.S0, P1419.S0; recurs Ch.1 P0459.S1, Ch.3 P0947.S0, Ch.6 P1781.S0, project listing P1066.S0)
- **Thesis:** 277 tests, 276 passing, 1 failing (claimed in `test_optimizer.py`).
- **Live run:** **217 collected, 217 passed, 0 failed**, **+1 collection error** (`test_synthetic.py` imports the missing `data_generation` package; its 60 source tests never run). There is **no** failing optimizer test.
  - Per-file counts 3 / 8 / 45 / 25 / 12 / 13 (P1386 / P1390 / P1394 / P1398 / P1402 / P1410) vs **actual 8 / 14 / 38 / 24 / 0(error) / 12**.
  - `test_auth.py` = **144** (P1414) vs **actual 20** (major mismatch).
  - "1 failing test in test_optimizer.py" (P1423.S0) — actual 27/27 pass; the real failure is the `test_synthetic.py` collection error (different file, different failure type).
  - Table 4.8 **omits** `test_aws_config.py` (7), `test_components.py` (25), `test_transforms.py` (42), which exist and pass.
- **Action:** rewrite Table 4.8 and §4.9 to the live counts (217 passing) and describe the collection error honestly; correct all dependent totals.

### A6. AI module "13 tests, all passing" (P1369.S0)
- **Thesis:** 13. **Actual:** `test_ai_module.py` collects **12** (all pass).
- **Action:** change 13 → 12 (recurs in summary P1462.S0).

### A7. AI sample estimate "$875.25" (P1374.S0)
- Appears **only** in the thesis — absent from `results.json`, `numbers.tex`, `main.tex`, and code. Non-deterministic LLM output.
- **Action:** mark as an illustrative example or remove the exact figure.

### A8. "100% recall on injected anomalies" + "NAB CloudWatch validated" (P1771.S3; recurs Ch.4 P1074.S0 / P1158–P1162 / P1293.S0 / P1311.S0, Ch.6 P1827.S1)
- **Thesis:** Z-Score + IQR union validated against NAB CloudWatch with 100% recall.
- **Canonical:** no recall metric and no NAB-validation artifact exist anywhere. The only computed quantity is **n_surges = 5 via a global μ+2σ threshold** (`main.tex:337,385`) — a different detector from the Z-Score/IQR union the thesis credits (method-vs-metric mismatch).
- **Action:** remove "100% recall" and "NAB-validated", or supply the artifact; reconcile the detector attribution. (The count "5 anomalies detected" itself is safe.)

### A9. Chapter 6 "29.5% cost reduction" (P1803.S3)
- **Thesis:** 29.5% (= 590.40 / **$2,000** hypothetical denominator).
- **Canonical:** **26.97%** of the **$2,189.48** inventory bill (`\savingsPctBill{27.0}`).
- **Action:** use the canonical denominator, or state both explicitly.

### A10. Portfolio extrapolations & time-savings (P1804.S0 / P1805.S0; P1811.S1)
- "$59,040 / month" and "$708,480 / year across 100 companies" = arithmetic of 590.40 × 100 × 12 — a projection, not a measured result. "140–240 hours/year saved per customer" has no supporting artifact.
- **Action:** label explicitly as illustrative projections/estimates.

### A11. (low impact) Chapter 4, Table 4.3 resource itemization (P1111–P1143)
- Itemized counts sum to **41** vs `results.json` n_resources = **42**. No explicit total is printed.
- **Action:** reconcile the itemization (low priority).

---

## B. DESIGN vs IMPLEMENTATION gaps — claims kept; confirm intent

> These describe a documented *design* that the shipped runtime code does not implement. Methodology prose was preserved (and softened where it asserted a live feature); confirm whether to (i) keep as design intent with a clear "designed to" framing, or (ii) revise to match the runtime.

1. **Automatic model-selection tree** — abstract P0047.S0; Ch.1 P0442.S1 / P0455.S1; Ch.3 §3.4.4 P0767–P0776 (esp. P0768.S0) + P0786.S0 / P0941.S0; Ch.5 P1581.S1 / P1587.S0 / P1597.S1; Ch.6 P1786.S2 / P1789.S1 / P1892.S0.
   - **Runtime:** Forecasts page is a **manual dropdown defaulting to Prophet** (`forecasts.py:47-57`); no code maps data-age → model. The "Naive → SeasonalNaive → ETS" tree lives only in `documentation/forecasting_models.md`. Note P0442.S1 also names only 3 of the 5 implemented forecasters. The "<2 weeks → Naive" branch is unreachable (forecasting is gated at `MIN_TRAINING_DAYS = 30`).
   - **Action:** confirm "designed to" framing, or revise to the manual-selection reality.
2. **CV config "120-day initial / 30-day step" and best-model-per-horizon selection** — Ch.1 P0455.S1; Ch.3 P0786.S0 / P0941.S0; Ch.4 P1151.S1 / P1152.S1.
   - **Runtime:** `evaluator.time_series_cv` defaults are `initial=60, horizon=14, step=7`; no caller passes 120/30; no auto best-select is wired in (the 120/30 *does* match the paper's CV config, but not the app).
   - **Action:** confirm these describe the paper's offline CV, not a runtime feature.
3. **"Anomalies excluded from training before fitting"** — Ch.3 P0756.S0; Ch.4 P1311.S0; Ch.6 P1791.S0 / P1827.S1.
   - **Runtime:** `ml_engine/anomaly.py` is never imported by the forecast path; forecasts fit on raw `daily_costs`. Anomalies are read only for display.
   - **Action:** confirm whether to keep as intended design or revise.
4. **Demo Mode login is broken in the shipped artifact** — Ch.5 P1545.S1 / P1546.S1 / P1550.S0 (the strongest "full access" claims were softened, not asserted broken).
   - `_enter_demo_mode` logs in as **`demo@cis.asu.edu.eg`**, which is **absent from the shipped DB** (only `aws-SYNTHETIC-001` and one real account exist) → silent failure.
   - **Action:** seed the demo user into the shipped DB, or revise the claim.
5. **Adding an AWS account does NOT trigger background collection** — Ch.5 P1690.S0 / P1691 (heading "5.4.3 Data Collection Background Process") / P1692.S0; related Ch.1 P0451.S4 / P0438.S0.
   - `add_aws_connection` only inserts a row; no collector/thread/subprocess starts from the dashboard. Real collection requires manually running `python -m aws_collector.main` (which uses a default boto3 session and ignores the stored role ARN). Settings never updates a "Last sync time". Prose was softened; the **heading P1691 still says "Background" — confirm or rename.**
6. **Chapter 5 UI claims left unchanged (not in the apply-list) — confirm or revise:** "live progress indicator" (P1590), "MAPE/RMSE/MAE on validation data" on the Forecasts page (P1595 — comparison shows only Avg/Total + "vs Historical"; backtesting is "coming soon"), priority/confidence conflation (P1606), "Password change option" (P1627 — not implemented), "Account creation date" (P1628 — not shown), "Connection name (editable)" (P1632), "Last sync time and status" (P1634 — only a status emoji), per-connection "Test connection button" (P1635 — only on the add form), "save as PDF / bookmark" (P1701 — no such feature).
7. **Minor implementation imprecisions** — `extract_json()` "direct JSON parsing first" (Ch.3 P0873.S0 — code does boundary detection only); STS "valid for one hour" + "three retries / 30-second timeout" (Ch.3 P0714.S0 — 1 h is the AWS default, `DurationSeconds` not set; retry/timeout constants exist but per-call application unverified); questionnaire option wording (Ch.3 P0859.S0 "IoT" / P0861.S0 "16/7" / P0864.S0 availability labels — the count of 9 is correct, but the option strings differ from `guided_questions.py`).
8. **RESOLVED in the consistency pass** — Ch.3 P0806.S0 ("…for non-compute services…") was corrected to drop the imprecise scope, and Ch.3 P0885.S1 "horizon selector (7–90 days)" → "(7, 14, 30, 60, or 90 days)" with "automatic model training", matching the Ch.1/Ch.5 corrections. No further action. (Ch.3 P0885.S1 "live progress indicator" wording is also covered by item B6/P1590 below — the Forecasts page shows a spinner, not a progress bar.)

---

## C. CITATIONS to supply or verify

> The editor may not add reference entries (adding paragraphs breaks the document's formatting preservation) and may not invent any citation, DOI, author, venue, or year. These need a human decision.

1. **Flexera year mismatch** — reference P1918.S0 dates "State of the Cloud Report" to **2023**; verified locator (`flexera2024soc`, `paper/main.tex:84`) is **2024**. In-text at Ch.1 P0432.S0 and Ch.2 P0526.S0. **Action:** align to the verified 2024.
2. **Gartner entry untraceable** — reference P1919.S0 ("Cloud Cost Optimization Strategies", 2023): no traceable publication, absent from `references.bib`; in-text at P0526 / P0432.S0 supports half the "30–35% wasted" claim. **Action:** replace with a citable source, cite only Flexera, or remove.
3. **RightScale "63%" orphan** — Ch.2 P0526.S0 (also Ch.1 P0433.S0): no RightScale entry anywhere; figure untraceable. Editor softened the prose to "industry surveys further report that 63% …" (number preserved). **Action:** add a verifiable source or drop the figure.
4. **Liu et al. CSUR-2025 — needs verification** — reference P1917.S0–S2 (in-text P0560): not in `references.bib`; supported only by `documentation/DATA_RESOURCES.md` (doc-stated DOI `10.1145/3719003`, unconfirmed). **Action:** confirm exact title/authors/DOI before relying on it.
5. **Cortez "Resource Central" SOSP-2017** — reference P1915.S0–S2 (in-text P0524): real, well-known paper but **absent from the curated `references.bib`** (the "2M VMs / CPU < 20%" figures rest on documentation only). **Action:** confirm a proper entry is acceptable as listed.
6. **Orphan Kaggle datasets cited in-text with no reference entry** — zoya77 "Cloud Workload Job Traces" / 3,562 records (Ch.2 P0565); programmer3 "Cloud Resource Usage for Anomaly Detection" / 1,440 rows (Ch.2 P0575). Also appear as dataset attributions in Ch.4 Table 4.2. **Action:** add reference entries or drop the inline attributions.
7. **"Several recent works" uncited** — Ch.2 P0586. **Action:** cite 1–2 specific hybrid-optimization works or soften. (Minor, optional: general-technique claims P0574 "Isolation Forest / LSTM / One-Class SVM" and P0580 "rule-based expert systems" carry no citation — acceptable as background, a reviewer may flag.)
8. **Minor attribution slip** — reference P1922.S0 attributes the Gemini API docs to "Google Cloud"; the docs live under Google AI / ai.google.dev. **Action:** optional fix (URL segment is a hyperlink and was not touched).
9. **Citation-style note (no action required for correctness)** — Chapter 2 uses informal author–year prose with an **unnumbered, un-DOI'd** author–title reference list; the companion paper uses numbered IEEE/BibTeX. Recommendation (brief D §4): **keep the thesis's informal style as-is**; do not convert. A verified, DOI-bearing reference pool exists in `ground-truth-D.md §3` if migration is ever desired.
10. **Reference-list formatting** — P1919.S0 is styled as `body` while every other entry is `list`; P1924 lacks the trailing-space `S2` segment its siblings have. **Action:** fix in the formatting pass (structural, not editable as text).

---

## D. List of Abbreviations issues (rows not auto-edited — table-structure risk)

1. **Duplicate "MILP" row** — P0300.S0 / P0349.S0 (both = "Mixed Integer Linear Programming"). **Action:** remove one.
2. **Duplicate "UI" row** — P0329.S0 / P0375.S0 (both = "User Interface"). **Action:** remove one.
3. **Inaccurate expansion "SQLite = Structured Query Language Lite"** — P0325.S0. SQLite is **not** an acronym (it is a self-contained, file-based SQL engine — "SQL" + "lite"). **Action:** correct (e.g., "Lightweight embedded SQL database engine") or remove the row.
4. **"GWA = Grid Workload Archive"** — P0343.S0. Canonical name is **"Grid Workloads Archive"** (plural; matches the applied References fix P1925). **Action:** apply the plural here too.

---

## E. Cover page (treated as immutable; FLAG ONLY)

> The cover uses space-based alignment; editing it risks breaking layout. Confirm whether to correct these in the team's master copy.

1. **"Dr.Hafez Moawad" — missing space** (P0023.S0) vs "Dr. Hafez Moawad" in the acknowledgments.
2. **"Faculty of computer & Information Science" — lowercase "computer"** and singular "Science" (P0025.S0; recurs P0029 / P0030 / P0036); the acknowledgments capitalize "Faculty of Computer & Information Sciences".
3. **"the degree of bachelors"** (P0007.S0) — should be "Bachelor's" / "Bachelor of".
4. **"Computer System Department"** (P0024.S0; recurs P0029 / P0034) — likely "Computer Systems Department" (plural). *Low confidence on the canonical department name — please confirm.*

---

## F. Front matter & structural items

1. **Arabic abstract needs native-speaker review** — P0050–P0054 (segments P0050.S0 / S2, P0051.S0 / S2 / S4, P0052.S0 / S2 / S11 / S14, P0053.S0 / S2). Left textually unchanged (RTL run properties, Latin terms, and numbers preserved). Low-risk candidates noted by the editor: P0050.S0 "بشكل عام" reads as filler and "الحوسبة السحابية" repeats. **Action:** a native Arabic speaker should review for formal-MSA register and confirm it mirrors the finalized English meaning. Do not reorder segments.
2. **Heading-level inconsistency "5.2.1 Prerequisites"** (P1520.S0) is **Heading 2** while its sibling "5.2.2 Installation and Launch" (P1528) is **Heading 3**. Cannot be fixed without changing styles. **Action:** restyle P1520 to Heading 3.
3. **TOC / List of Figures / List of Tables are field-generated.** After any heading or caption text changes (e.g., the Table 2.x caption fixes), open the document and **refresh fields (Ctrl+A, then F9)** so the generated lists reflect the new text.
4. **Table caption / number copy-paste errors (Ch.4)** — P1307.S0 caption "Table 4.5 … Training Data Size" sits under the Anomaly Severity table (should be "Table 4.6"); P1355.S0 caption "Table 4.6: Anomaly Severity" sits under the cost-savings breakdown. **Action:** fix the captions/numbers (structural; out of text-edit scope). Also note: Ch.3 Figure 3.1 renders as "Figure 3.0.1" via a field-numbering artifact (not editable).
5. **Space-based heading alignment** — P0492.S0 (Ch.2) and P0961.S0 (Ch.4) use large internal space runs for layout; treated as immutable like the cover. **Action:** confirm acceptable.
6. **Cover metadata** — supervisor/committee names and the submission date appear on the cover. **Action:** confirm they are final and correct.
7. **Missing `data_generation` package (context, not a thesis edit)** — README/QUICKSTART/STARTUP and 3 dashboard pages reference `python -m data_generation.synthetic`, but no such package ships; the committed SQLite DB is the only data source. This underpins the "pre-loaded synthetic data" premise. **Action:** awareness only; ensure no thesis instruction tells a reader to generate data this way.

---

## G. Canonical-title decision — confirm

The thesis uses two intentional names, applied consistently:
- **Formal title:** "AWS Cost Intelligence System" (headings, abstract, cover).
- **Product name:** "OptiCloud" (prose).

The code/README's third name, **"Smart Cloud Optimizer", was deliberately NOT introduced** into the thesis. **Action:** confirm this two-name convention is the intended final decision.
