# Paper Outline — mapped to the Smart Cloud Optimizer project

Section-by-section outline of `main.tex`, showing what each section argues and
**which real project artifact / data backs it**. Everything cited in the
numerical study is computed by `numerical_study.py` from
`data/cloud_optimizer.db` (account `aws-SYNTHETIC-001`); nothing is invented.

**Working title:** *Cost-Aware Capacity Reservation for Cloud Workloads with
Intermittent Random Demand Surges: An Integrated Forecasting–Optimization
System.*

**One-line thesis:** Your system makes the reserve-vs-on-demand decision with
a heuristic; we give the *optimal* policy (newsvendor + utilization threshold),
prove the heuristic is its special case, and show both work on real data.

---

## Abstract
Problem (base + intermittent surges) → approach (reserved base + on-demand/spot
surges) → method (newsvendor + threshold policy; forecasting + MILP system) →
results (12.1% MAPE; 26.7–50.0% model savings; $590/mo system savings) →
significance (connects OM theory to FinOps practice).

## §1 Introduction
- Cloud spend & FinOps motivation → `README.md`, refs `storment2023finops`,
  `deochake2023cloud`, `armbrust2010view`.
- The base-plus-surge problem and the menu (on-demand/reserved/spot) → real
  pricing tiers in `instance_pricing` (37%/60%/70% discounts).
- **The gap:** industry uses the "reserve if running > 60 days" heuristic →
  this is literally `optimizer/rules.py:check_ec2_pricing` (`min_running_days
  = 60`). We replace it with the optimal threshold.
- **4 contributions:** (1) the reservation model, (2) threshold subsumes the
  heuristic, (3) the integrated system, (4) reproducible study.

## §2 Related Work (7 themes → 23 verified refs)
FinOps/economics · pricing mechanisms · provisioning under uncertainty ·
workload forecasting · newsvendor & reservation contracts · right-sizing ·
LP/MILP. See `references.bib`. Closest siblings: `chen2024cost` (the
reference), `qu2024cloud`, `chen2023cloud`.

## §3 Model
- Notation table (Table 1).
- **Demand model** `D_t = d_b + S_t M_t` (base + intermittent surge) →
  justified empirically in §6.1 from `daily_costs`.
- **Procurement options** & per-period cost `c_t(Q) = (1-δ)Q + (D_t-Q)^+` →
  prices from `instance_pricing`; numéraire `p = 1`.
- Assumption 1 (price ordering `s < r < p`, empirical-CDF consistency).

## §4 Optimal Capacity Reservation (the formal model — proofs in App. A)
- **Prop 1 (newsvendor):** `Q* = F⁻¹(δ)`, critical ratio = δ. ← validated in
  §6.3 (closed form vs. grid search agree to $0.03/day).
- **Cor 1 (monotonicity):** reserve more when δ is larger. ← Fig 4 sweep.
- **Prop 2 (break-even):** reserve iff utilization `u ≥ 1-δ` (0.63 / 0.40 at
  real tiers). ← formalizes `rules.py` 60-day rule.
- **Prop 3 (surges):** supplementary reservation iff surge fraction
  `ρ ≥ 1-δ_s`. ← mirrors `chen2024cost` duration insight.
- **Prop 4 (spot):** effective cost `(1-β)s + βp`; SLA caps spot share. ←
  `SPOT_DISCOUNT_FACTOR = 0.7` in `pricing_constants.py`.

## §5 The Smart Cloud Optimizer System (the applied contribution)
- §5.1 Architecture (Fig "arch") → `README.md` architecture diagram; 31 tables
  in `storage/db.py`.
- §5.2 **Forecasting** — 5 models (Naive, SeasonalNaive, ETS, Prophet,
  SARIMAX), walk-forward CV (60/14/7), MAPE/RMSE/MAE; anomaly detection
  (z-score w=30, 3σ; IQR 1.5×) → `ml_engine/forecaster.py`, `evaluator.py`,
  `anomaly.py`. Output distribution feeds Prop 1.
- §5.3 **Right-sizing MILP** (eqs. 9–13): binary `x_ij`, min on-demand cost,
  assignment + vCPU + memory + budget constraints, P95 CPU × 1.3 headroom, CBC
  solver → `optimizer/compute_lp.py` (exact).
- §5.4 **10 rules** + dedup → `optimizer/rules.py`, `engine.py`. Pricing-switch
  rule = empirical Prop 2.
- §5.5 **LLM advisor** (Gemini, greenfield provisioning) → `ai_module/`.

## §6 Numerical Study (all numbers from `numerical_study.py`)
- §6.1 **Demand characterization** (Fig 1): 365 days, base $64.7, peak 3.06×
  median, 5 surge days (1.4%), weekday $84.4 vs weekend $50.1. ← confirms §3.
- §6.2 **Forecasting accuracy** (Table 2, Fig 5): ETS best, MAPE 12.1%;
  seasonal models beat naive 2×.
- §6.3 **Newsvendor optimum & savings** (Tables 3; Figs 2,3): closed form ≈
  grid; coverage F(Q*) = 0.370 = δ; save 26.7%/50.0% vs on-demand; reserve-peak
  is 60–63% worse than optimal.
- §6.4 **Discount sensitivity** (Fig 4): Q* and savings rise with δ.
- §6.5 **End-to-end case study** (Table 4): 19 recs + 10 LLM recs;
  $590.4/mo = 54.9% of addressable spend; right-sizing + pricing-switch = 97%.
  ← `recommendations`, `ai_recommendations` tables.

## §7 Managerial Insights (bulleted, imperative)
Reserve to a quantile not the peak · reserve more when discounts deepen ·
replace 60-day rule with `u ≥ 1-δ` · match surge coverage to surge frequency ·
forecast the distribution then optimize.

## §8 Conclusion
Summary + limitations (single synthetic account; static given forecast) +
future work (production multi-account data; dynamic purchase/renew/cancel with
cancellation fees & secondary marketplace per `chen2024cost`; joint
right-sizing + pricing-plan program).

## Appendix A — Proofs
Props 1–4 (newsvendor FOC & convexity; break-even algebra; surge corollary;
spot expectation + SLA layering).

---

## Files in `paper/`
| File | What it is |
|------|-----------|
| `main.tex` | Full LaTeX manuscript (14 pp). Build: `latexmk -pdf main.tex`. |
| `references.bib` | 24 verified BibTeX entries. |
| `numerical_study.py` | Regenerates every figure + `figures/results.json`. |
| `figures/*.pdf` | 5 figures (vector) used by `main.tex`; `.png` mirrors. |
| `figures/results.json` | All computed numbers (single source of truth). |
| `STYLE_GUIDE.md` | How the draft mirrors the reference paper's style. |
| `OUTLINE.md` | This file. |

## TODO before submission
- [ ] Fill author names/affiliations in `main.tex`.
- [ ] Confirm target venue; swap document class to its template if needed.
- [ ] (Optional) read the SSRN preprint to match exact section headings.
- [ ] (Optional) deepen the dynamic policy (cancellation/renewal/marketplace).
- [ ] (Optional) validate on a real (non-synthetic) AWS account.
