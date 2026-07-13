# Adversarial Peer Review — Rounds 2–3 (journal upgrade)

> **Round-3 verdict (confirmation review, three lenses + verification):**
> **minor revision — upgraded from major revision.** Updated mock scores:
> novelty **3**, significance **3→4**, soundness **3→4**, clarity **4**,
> reproducibility **4→5**. All round-3 minor findings were applied (see §6).



*A Data-Driven Capacity-Reservation System for Cloud Cost Optimization under
Intermittent Demand Surges* — IEEEtran journal manuscript (12 pp), target
IEEE TNSM / IEEE TCC (Q1).

**Method.** Multi-agent pipeline: (1) a 32-agent literature workflow
(Crossref-verified all 35 existing references — 0 errors; swept 8 topics
across 2023–2026; added 58 verified entries; venue analysis); (2) three new
experimental studies (real-trace validation on 2,297 VMs, out-of-sample
policy simulation with an SP baseline, statistical-rigor upgrade); (3) an
abstract judge panel (3 drafts × 3 lenses); (4) a six-lens adversarial
review (Reviewer-2, methods/statistics, number integrity, citation
integrity, IEEE presentation, writing) with refute-first verification of
every major finding; (5) all confirmed findings fixed and re-verified.

> **Honest framing.** No process guarantees acceptance. This pass maximized
> the controllable factors and removed every avoidable rejection reason,
> under a hard constraint: weak results are reported, never inflated.

---

## 1. Where the paper moved (previous review → now)

Round 1 (conference version) verdict: **borderline / workshop-accept** with
three residual weaknesses. All three were addressed with substance, not
prose:

| Round-1 weakness | Resolution |
|---|---|
| Synthetic, single-account evaluation | **Study II added**: Bitbrains GWA-T-12 (fastStorage 1,250 VMs; Rnd 500 VMs) + Materna GWA-T-13 (547 VMs), MILP right-sizing vs. like-for-like baseline over a verified, snapshot-dated AWS catalog (γ=0.63 real): 33.6%/33.1%/74.2% savings (58.3%/58.0%/83.8% with 1-yr RI). Forecasting on the real aggregate reported honestly (MASE ≈ 1; regime shifts dominate). |
| Narrow novelty (static sizing; no (s,S)) | **Study III added**: out-of-sample γ-sweep policy simulation. Price of conservatism: the p95×1.3 fractile *read as reservation sizing* realizes 101.8% (synthetic) / 153.5% (trace) of on-demand cost vs. 73.6%/86.2% for the newsvendor fractile. Dual-capacity (K₀,K₁) — the static core of (s,S) — is worth +0.8 pts on synthetic but +8.5 pts on real demand, and a **causal** activation variant retains +8.1 of those points; on synthetic one-day spikes the causal variant *loses* value. Surge persistence is the enabling condition — an original, defensible empirical finding. |
| No external baseline | **SAA stochastic program added** (Chaisiri/Bülbül-style two-stage SP): recovers the newsvendor quantile to ≤0.57%, cross-validating closed form, simulator, and solver. Framed as validation, not competition; no commercial head-to-head (disclosed). |

Statistical rigor added throughout: per-fold sd, MASE, DM tests with HLN
correction (+ Wilcoxon), interval coverage; the ETS-vs-seasonal-naive null
(p=0.198) is disclosed in the abstract itself.

## 2. Round-2 review verdict (pre-fix)

Reviewer-2 lens scores: novelty **3**, significance **3**, soundness **3**,
clarity **4**, reproducibility **4** → **major revision** (explicitly "not
reject": *"unusually honest and verifiable … all four contribution claims
backed … delta over Chen–Lei–Moinzadeh defensible in kind"*).

## 3. Confirmed findings and resolutions (all fixed and re-verified)

**Substance (fixed with code + new experiments):**
- DUAL used a contemporaneous surge signal while the protocol claimed "no
  policy sees the future" → protocol now flags the observable-state
  assumption explicitly; **DUALC (causal, one-period lag) implemented and
  reported everywhere**; tables bold only policies needing no
  contemporaneous knowledge.
- "No number is hand-typed" was falsified by ~7 derived literals → all now
  macro-bound (`\polSurgeTrain/Test`, `\polDualGain`, `\polNvSave`,
  `\extTotalVms`, `\extAnyBestMape`, `\polHeurBreakeven`,
  `\minFolds`, gap-capture fractions, …). Claim is literally true again.
- Blanket "no model is statistically separable" rested on one test → two
  additional DM tests run (Prophet vs. both baselines); claims scoped to
  the tested pairs.
- Split-dependence of Study III → train-fraction sweep (0.5–0.7) added;
  NV saving stays within 26.1–26.4% (synthetic) / 12.5–16.0% (trace).
- "Byte-for-byte" reproducibility claim → **verified empirically**: all
  three scripts re-run and diffed byte-identical (Prophet seeding fixed by
  the stats pass; policy sim and external validation double-run checked).

**Framing/overclaims (fixed in prose):**
- "p95 idiom *is* used for commitment sizing in practice" (uncited) →
  reframed as a cautionary bound on naive fractile transfer, with the
  correct contrast to commercial recommenders.
- "captured more than half of the NV→bound gap" → actually 37% → now
  macro-bound (`\extPolDualGapCapture`).
- Contribution 1 called p95×1.3 an "empirical **critical** fractile"
  (contradicting the paper's own point that it is *not* cost-optimal) →
  "fixed empirical fractile".
- Forecasting was causally disconnected from the dollar figures but C1
  implied it fed sizing → C1, Section IV-A, and Algorithm 1 now position
  forecasting as monitoring/interval/surge context; sizing uses empirical
  quantiles.
- Threats bullet "system realizes static newsvendor sizing" (internal
  contradiction) → "static fixed-fractile sizing (q0.95×1.3) with always-on
  gating".
- "calibrated intervals" (99% vs 95% nominal) → "conservative,
  over-covering"; Fig. 3 caption no longer claims "most accurate" overall;
  abstract "MAPE bottoms at 52.1%" scoped via `\extAnyBestMape` (48.2%);
  savings ranges now use the true minimum endpoint (Rnd) everywhere;
  "consistently across datasets" qualified; fold counts corrected (6–9).

**Citation integrity (all 83 cited keys verified; 3 mis-descriptions fixed):**
- huang2025reservation (URD contract pricing, not usage-commitment),
  deochake2024abacus (budget enforcement, not commitment purchasing),
  sachidananda2024erlang (microservice autoscaling policy choice, not
  "several-fold serverless" claim) — all reworded to match sources.
- rzadca2020autopilot slack numbers rephrased as the cross-sectional
  comparison the paper actually reports (23% vs 46%).
- jiang2022colocated author list corrected against Crossref; two arXiv
  @misc entries now render identifiers.
- "only public traces with provisioned+used per VM" → "among the few",
  with the Alibaba distinction stated.

**Presentation:** figure numbering matches citation order (service-share
moved); Table V γ-grid aligned with Tables VI–VII; self-contained captions;
Materna-Trace-3 naming unified; MILP/MAPE/MASE/RI/SP expanded at first use;
fractile/quantile/percentile equivalence stated; MILP-decomposition note
added to Study II (no budget cap → per-VM selection).

## 4. Build & reproducibility verification (final)

```
pdflatex → bibtex → pdflatex ×2       12 pages (at the TCC cap)
LaTeX errors / undefined refs:        0 / 0
BibTeX warnings:                      0    (93 entries, 83 cited, all verified)
Overfull boxes:                       1    (0.84pt, bibliography — cosmetic)
Determinism (byte-identical double runs):
  make_figures.py                     PASS (verified during stats pass)
  policy_sim.py (both invocations)    PASS
  external_validation.py              PASS (numbers, tables, CSV, JSON)
```

## 5. Honest final assessment

**Strengths a reviewer will credit:** real-trace validation with verified
real prices; an original, quantified finding (price of conservatism; value
of the two-tier structure gated on surge persistence, with a causal
variant); mutual validation of closed form and SP; statistical honesty
including in-abstract null disclosure; total machine-generated
reproducibility; clean IEEE presentation.

**Weaknesses that remain (disclosed in Threats, not fixable by writing):**
1. Trace era (2013/2016) and two providers; no live-account deployment.
2. No commercial head-to-head (Compute Optimizer, commitment optimizers).
3. The (s,S) cancellation/renewal dynamics are still not implemented or
   simulated — DUAL/DUALC are the static core.
4. Study III abstracts instance granularity and contract terms; synthetic
   arm treats the whole bill as reservable.
5. 6–9 folds limit statistical power; model-ranking claims are
   deliberately weak.

**Bottom line.** The manuscript is now a credible Q1 systems-measurement
submission: sound, well-positioned, statistically honest, fully
reproducible, with genuine new evidence layered on the operationalization.
The strongest surviving objection is "incremental over Chen et al. + no
commercial comparison," which the candid Threats section pre-empts. Venue
recommendation from the literature workflow: **FGCS** (best fit, Elsevier
format) or **IEEE TNSM** (best IEEE Q1 fit; manuscript is already in
IEEEtran journal format), with CCGrid as the conference fallback.

---

## 6. Round 3 — additions and confirmation review

**Substance added after round 2:**
- **Azure Public Dataset V2 study** (`azure_validation.py`, 237,272
  long-running VMs of 2.7M, 2019): right-sizing alone is cost-negative
  (−3.8%) because Azure reports p95 of 5-min *maxima* and no memory usage;
  reservations still save 34.8%. Reported as a boundary condition: the
  fractile rule's value is contingent on metric semantics; the γ-lever is
  robust across all four datasets. MILP-equivalence asserted on a 2,000-VM
  subsample; double-run byte-identical.
- **DUALC hardening**: surge-threshold sweep (μ+kσ, k∈{1.5,2,2.5}: trace
  gains stay positive, 2.7–8.1 pts) and minimum-hold sensitivity (6h→6.6,
  24h→4.1, 168h→−7.9 pts) — empirically quantifying why the reference
  model's cancellation flexibility matters.
- **Commercial-recommender positioning** from fetched primary docs
  (AWS RI / Savings Plans / Azure reservations recommenders replay
  historical usage and maximize savings — verified quotes, access-dated
  @misc entries): in the paper's single-resource abstraction this reduces
  to the SAA baseline, so F4 doubles as indirect validation of commercial
  practice; F1's contrast with fractile sizing is now citable.
- Architecture figure no longer overclaims "(s,S) reservation" (now
  "fixed-fractile + always-on RI gating"); Fig. 1 caption matches.

**Round-3 confirmation review:** three lenses (Reviewer-2 re-read,
number-integrity, presentation), refute-first verification. Zero blockers,
zero majors. Verdict: **minor revision**; all 13 minors applied, including:
Azure VM-accounting reconciliation; scoping "gains remain positive" to the
trace; the 34.8%-is-net-of-right-sizing-loss clause; the RI upper-bound
caveat (right-censored lifetimes vs one-year commitments); "with contracts
sized ignoring the term constraint" qualifier; "is exactly"→"reduces to";
abstract to ≤250 words; F1–F4 paragraph breaks; stray cite-space;
references.bib.bak removed.

**Final build:** 12 pages, 0 errors, 0 undefined references, 0 BibTeX
warnings, one 0.84pt bibliography overfull (cosmetic). Reviewer-2's summary:
*"The Azure result STRENGTHENS the story … The DUALC treatment removes the
observable-state objection that capped soundness … recommendation: minor
revision (accept after the minor edits)."* The minor edits are applied.
