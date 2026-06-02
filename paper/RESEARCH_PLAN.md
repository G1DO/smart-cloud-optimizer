# Research Plan — Forecast-Integrated Capacity Reservation

**Working title.** *Reserving Under Uncertainty You Estimated Yourself:
Forecast-Integrated Capacity Reservation for Cloud Workloads with
Intermittent Demand Surges.*

**Target quartile.** Q1 — primary venue **IEEE Transactions on Cloud
Computing** (IF ≈ 5.0, CiteScore 11.3, SJR Q1); secondary OR/MS outlets if the
theory is strong (see §9).

---

## 1. The one-sentence thesis
The reference paper (Chen, Lei & Moinzadeh 2024) reserves capacity at the
discount-quantile of a **known** demand distribution; in practice that
distribution is **forecast** and therefore wrong, so we develop the theory and
system of *forecast-integrated* reservation — quantifying how forecast error
turns into excess cost (**regret**), how much history you need before
reserving, and why you should forecast the **δ-quantile directly** rather than
the mean — and we validate it on public cloud traces.

## 2. Why this is novel (positioning — be honest about prior art)
- **Known vs. learned distribution.** The reference and classical newsvendor
  assume `F` is given. The *data-driven newsvendor* literature studies learning
  `F` from data — Levi, Roundy & Shanthikumar (2007, sampling-based bounds);
  Liyanage & Shanthikumar (2005, operational statistics); Ban & Rudin (2019,
  *The Big Data Newsvendor*); Oroojlooyjadid, Snyder & Takáč (2020, deep
  newsvendor). **We must cite these prominently** — our novelty is *not*
  "data-driven newsvendor."
- **What is genuinely new here:**
  1. **Cloud cost structure.** We specialize the analysis to the
     reserved/on-demand/spot menu, where the critical ratio equals the
     reservation discount (`CR = δ`) and reservation carries a multi-year
     commitment. The regret bound below is specific to this structure.
  2. **Non-i.i.d., seasonal, surge-prone demand.** The data-driven newsvendor
     theory is largely i.i.d.; cloud demand is weekly-seasonal, autocorrelated,
     and right-skewed by intermittent surges. We extend the regret analysis to
     this regime (effective sample size, conditional/seasonal quantiles).
  3. **A working forecaster in the loop.** We don't assume an estimator — we
     plug in a real forecasting engine (ETS/SARIMAX/Prophet, already in
     `ml_engine`) and measure realized regret on real traces.

## 3. Research questions
- **RQ1.** How much extra cost (regret) does forecast error in the demand
  distribution cause, relative to the oracle reservation `Q*`?
- **RQ2.** How many periods of history `n` are needed before forecast-based
  reservation is within ε of optimal? (Sample complexity / "warm-up".)
- **RQ3.** Should you forecast the **mean** or the **δ-quantile** of demand for
  the reservation decision, given surge-induced skewness?
- **RQ4.** Does a finite-sample **safety correction** to the plug-in quantile
  reduce realized cost on real workloads?

## 4. Theoretical contributions (the math — this is the Q1 engine)
Notation as in `main.tex`: demand `D_t`, CDF `F`, density `f`, on-demand price
`p`, discount `δ`, reserved level `Q`, horizon `T`. Per-period expected cost
`g(Q) = (1-δ)pQ + p·E[(D-Q)^+]`, convex, with `g'(Q) = p(F(Q)-δ)` and
`g''(Q) = p·f(Q)`. Oracle optimum `Q* = F^{-1}(δ)` (Prop. 1 in the draft).

**T1 — Regret decomposition.** For any estimated reservation `Q̂` close to
`Q*`, a second-order expansion of the (convex) cost gives the per-period
*regret*
> `Regret(Q̂) = g(Q̂) - g(Q*) ≈ ½ · p · f(Q*) · (Q̂ - Q*)²`.
Taking expectations over the estimator, `E[Regret] ≈ ½ p f(Q*)·MSE(Q̂)`.
**Interpretation:** forecast error hurts most when the demand density at the
critical quantile `f(Q*)` is large (many days clustered near the reservation
level) — a cloud-specific, testable insight.

**T2 — Sample complexity (RQ2).** If `Q̂` is the empirical δ-quantile of `n`
(approximately) i.i.d. samples, its asymptotic variance is
`Var(Q̂) ≈ δ(1-δ)/(n·f(Q*)²)`. Substituting into T1,
> `E[Regret] ≈ p·δ(1-δ) / (2 n f(Q*)) = O(1/n)`,
*decreasing* in the density `f(Q*)`. This yields a concrete "how much history
before you reserve" rule and a closed-form ε-optimal `n`.

**T3 — Mean vs. quantile forecasting (RQ3).** Surges make demand right-skewed,
so for `δ < 0.5` the optimum `Q*` sits below the mean. We show a plug-in policy
that forecasts the **mean** and assumes symmetric error is *biased* by an
amount that grows with the skewness, whereas **directly forecasting the
conditional δ-quantile** (pinball/quantile loss) is consistent for `Q*` by
construction. Practical payoff: add a quantile-loss head to the forecaster.

**T4 — Finite-sample safety correction (RQ4).** Following operational
statistics (Liyanage & Shanthikumar 2005), the cost-optimal *data-driven*
fractile is generally **not** the plug-in fractile `F̂^{-1}(δ)`. We derive a
correction `Q̂ → Q̂ + b(n, skew)` minimizing expected cost under estimation
variance, and show it dominates the naive plug-in.

**T5 — Seasonal / non-i.i.d. extension.** Weekly seasonality reduces the
effective sample size to `n_eff < n`; we replace `n` in T2 with `n_eff` (a
function of autocorrelation) and analyze **conditional reservation** (separate
quantiles per day-of-week). This formally explains why seasonal forecasters
(ETS at 12.1% MAPE vs. naive 30%, already in our results) lower reservation
regret.

> Proofs are short specializations of convexity + sample-quantile asymptotics —
> tractable for a student with advisor support. The risk is **over-claiming**;
> T1–T2 are the safe core, T3–T5 are the differentiators.

## 5. Data — public cloud traces (no private data needed)
Map each trace's aggregate per-interval resource usage to the demand series
`D_t`; take reserved/on-demand/spot prices from public AWS/Azure price lists to
set `δ` (and `δ_s`). Recommended, in priority order:
1. **Azure Public Dataset** (VM traces, 2017 & 2019) — CPU utilization + VM
   lifetimes; the standard cloud-capacity benchmark.
2. **Google cluster-data** (Borg, 2011 & 2019) — task resource usage; highly
   cited; strong seasonality at cell level.
3. **Alibaba cluster-trace** (2018/2020/2022) — co-located online+batch;
   pronounced surges — ideal stress test for the surge model.
4. *(Optional)* **Bitbrains / Grid Workloads Archive** — small business-critical
   VM traces for a quick third dataset.

Use ≥2 traces so reviewers see the results aren't trace-specific. *I can write
the loaders that turn each trace into the `daily_costs`-style series your
pipeline already consumes.*

## 6. Method / system changes (reuses your codebase)
- **Forecaster (`ml_engine/forecaster.py`).** You already emit predictive
  intervals (`lower`/`upper`) — i.e., approximate quantiles. Add a **direct
  δ-quantile forecaster** (quantile regression or gradient boosting with
  pinball loss) and expose `predict_quantile(δ)`.
- **Reservation policy (new, small module).** `Q̂ = predict_quantile(δ)`, with
  the T4 safety correction; residual demand to on-demand/spot per Props. 3–4.
- **Evaluator (`ml_engine/evaluator.py`).** Add a **cost-regret** metric
  (realized `$` vs. oracle hindsight `Q*`) alongside MAPE/RMSE/MAE.

## 7. Evaluation plan (what convinces reviewers)
- **Baselines:** (a) reserve-to-peak; (b) reserve-the-mean; (c) static
  δ-quantile of all history; (d) the "60-day" heuristic; (e) oracle `Q*`
  (hindsight lower bound).
- **Metrics:** realized cost, **regret vs. oracle**, % over on-demand,
  service-level (unmet-at-reserved) — averaged over rolling origins.
- **Experiments:** (1) regret vs. history length `n` → *verify the O(1/n)
  rate of T2 empirically*; (2) mean- vs. quantile-forecast policy (T3);
  (3) with/without seasonal conditioning (T5); (4) sensitivity to `δ`, surge
  frequency, forecaster choice; (5) cross-trace generalization.
- **Reproducibility:** extend `numerical_study.py`; release code + trace
  pre-processing.

## 8. Step-by-step workflow (phases)
1. **Formalize** T1–T2 cleanly (1–2 wks). Get the advisor to sanity-check the
   proofs early — this is the make-or-break.
2. **Trace pipeline** — loaders for Azure + Google → `D_t` series (1 wk).
3. **Quantile forecaster + regret evaluator** in `ml_engine` (1–2 wks).
4. **Experiment 1 (verify O(1/n))** — the headline empirical confirmation of
   the theory (1 wk).
5. **T3–T5** + remaining experiments (2–3 wks).
6. **Write-up** — fold into the existing `main.tex` scaffold; reposition
   Related Work around the data-driven newsvendor lineage (1–2 wks).
7. **Internal review → submit.**

## 9. Target venues
| Venue | Quartile | Fit |
|---|---|---|
| **IEEE Trans. Cloud Computing** | Q1 | Best fit: theory + system + cloud traces. |
| IEEE Trans. Services Computing | Q1 | If we emphasize the service/provisioning angle. |
| Future Generation Computer Systems | Q1 | Systems + evaluation heavy. |
| *Production & Operations Mgmt / M&SOM* | Q1 (OR/MS) | Only if T1–T5 become the centerpiece (pure-theory bar). |

## 10. Risks & scope control
- **Biggest risk: over-claiming novelty.** Mitigate by citing Levi et al.,
  Ban & Rudin, Liyanage & Shanthikumar up front and framing the contribution
  as *cloud-specialized + seasonal + system-validated*.
- **Keep scope tight:** T1+T2 + Experiment 1 on two traces is already a
  paper. T3–T5 strengthen it; cut them if time runs short.
- **Synthetic data is not enough for Q1** — the public traces are the fix.

---
### Immediate next step (pick one and I'll start)
- **(A)** Build the **Azure/Google trace loaders** + the **δ-quantile
  forecaster** + a script that **empirically verifies the O(1/n) regret
  bound (T2)** — the strongest single demo of the idea.
- **(B)** Draft the **new theory section** (T1–T5 with proofs) into `main.tex`.
- **(C)** Add the **verified citations** (data-driven newsvendor lineage) to
  `references.bib` and rewrite Related Work around this angle.
