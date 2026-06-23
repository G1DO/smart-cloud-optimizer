# Adversarial Peer Review — *A Data-Driven Capacity-Reservation System for Cloud Cost Optimization under Intermittent Demand Surges*

**Target:** a reputable IEEE conference (applied systems / FinOps / cloud track).
**Method:** five concurrent review lenses (skeptical TPC "Reviewer-2", technical
soundness / number-integrity, citation integrity, IEEE presentation, writing
quality) over `paper/main.tex`, synthesized into one prioritized punch list, then
**all fixes applied and re-verified**. Every disputed citation DOI was
independently confirmed against Crossref; every number was re-derived by
re-running `make_figures.py` end-to-end.

> **Honest framing (stated up front).** No review process can *guarantee* IEEE
> acceptance — that is gated by genuine novelty, correct results, venue fit, and a
> partly subjective committee. What this pass did is remove every *avoidable*
> reason for rejection while holding a hard honesty constraint: weak results were
> **reframed, never inflated**, and the Threats-to-Validity section was kept and
> strengthened.

---

## 1. Mock Reviewer-2 report (scores + recommendation)

| Axis | Score (1–5) | Note |
|---|---|---|
| Novelty | **2** | Delta over Chen-Lei-Moinzadeh is narrow; the "empirical critical fractile" is a relabeling of a fixed P95×1.3 heuristic. Reframed as honest gap-quantification. |
| Soundness | **3** | Math, MILP, and CV are correct and reproducible; the headline was an additive upper bound (now disclosed as a range). |
| Clarity | **4** | Well-written, well-signposted; tightened further. |
| Significance | **2** | Single synthetic account; no external baseline. Now framed as illustrative. |
| Reproducibility | **4 → 5** | Pipeline regenerates every figure/number; after this pass, **every** in-text literal and table cell is macro-bound (was: 5 hand-typed values). |

**Overall recommendation:** **Borderline** — lean reject at a top-tier venue,
solid accept at an applied-FinOps / industry workshop track. **Not** desk-reject
material: on-topic, reproducible, honestly scoped, cleanly formatted.

**Reviewer-2 rationale (verbatim synthesis).**
> Competent, unusually honest engineering paper that operationalizes the
> Chen-Lei-Moinzadeh (POM 2024) capacity-reservation framework into a
> forecast→MILP→rules pipeline. Core objections: (1) the entire empirical case
> rests on a single **synthetic** account the system itself authored, so the
> headline "27% / \$590.40/month" is method-illustrative, not measured; (2) the
> 27% is an additive **upper bound** that double-counts resources flagged by two
> rules; (3) six references carried **wrong DOIs** resolving to unrelated papers.
> Residual weakness that survives any reasonable fix: the novelty delta over the
> reference is narrow — the reference's actual theoretical contribution (the
> two-threshold (s,S) dynamics) is explicitly *not* implemented, and there is no
> external baseline. The defensible contribution is the reproducible integration
> plus the honest gap-quantification, and the paper has been repositioned to say
> exactly that.

---

## 2. Prioritized punch list (as found) and resolution

Severity: **B** = blocker, **M** = major, **m** = minor. ✅ = fixed and verified.

### Blockers
| # | Finding | Resolution |
|---|---|---|
| B1 | **Six references carry wrong DOIs** resolving to unrelated papers (off-by-one INFORMS/Wiley/IEEE suffixes): `chen2021discount`, `arbabian2021capacity`, `wang2014optimal`, `nunez2021slack`, `huang2016surges`, `erkoc2005reservation`. | ✅ All six corrected and **independently re-verified against Crossref** (each original confirmed to resolve to a *different* paper; each correction confirmed to resolve to the cited title/authors/pages). |
| B2 | **Headline measured on a synthetic account the system ships**; confident dollar claims led the abstract while the caveat was buried. | ✅ Abstract, intro contribution 3, Setup, and Conclusion now **co-locate the synthetic caveat with the number** and label the dollars "method-illustrative, not a measured saving." Section V workload described as synthetic throughout. |

### Majors
| # | Finding | Resolution |
|---|---|---|
| M1 | **27% / \$590.40 is an additive upper bound** that can double-count resources flagged by two rules. | ✅ Computed the real overlap from the DB: the two dominant levers (RDS right-sizing, EC2 reservation) are on **disjoint** resources; the *only* double-count is **3 EBS volumes** flagged for both deletion and gp3-upgrade (\$2.00). Now reported as a **jointly-realizable \$588.40 → additive \$590.40 range** in abstract, §V-C, and Threats; new macros `\jointSavings`, `\overlapSavings`, `\numOverlap`. |
| M2 | **Two unreconciled bill figures** — \$2189.48/mo (inventory) vs \$27,243.31/yr (daily series). | ✅ Added a reconciliation sentence in §V-A (snapshot vs year-integrated; savings ratios use the inventory baseline). |
| M3 | **Novelty thin**: "empirical critical fractile" relabels a fixed P95×1.3 heuristic the paper itself shows is not cost-optimal. | ✅ Contribution 1 reframed as **exposing/quantifying the heuristic-vs-optimum gap** (a diagnostic motivating γ-aware tuning), with the integration as the central contribution. "exactly a critical-fractile" → "has the form of"; "elegant and complete" → "closed-form". |
| M4 | **No external baseline**; "none ties forecast to newsvendor" asserted, not shown. | ✅ Narrowed the negative-existence claim to "works we surveyed"; added a Savings-Plans/commitment-portfolio positioning (framed **complementary**, not beaten); added a **"No external baseline"** threat. |
| M5 | **"Surges are not forecastable" elevated to a "core message"** from one synthetic, injected surge. | ✅ Demoted to "consistent with the policy's premise," explicitly scoped to the synthetic workload ("not evidence that real-world surges are unforecastable"). |
| M6 | **Five hand-typed literals** contradicted the "every number regenerated" claim. | ✅ All macro-bound: `\billAfter`, `\savComputeTwo`, `\pctComputeTwo`, and the **entire MAPE table** now generated (`mape_tabular.tex`). The reproducibility claim is now literally true. |
| M7 | **Reserved-discount assumption unstated** behind the \$208.42 pricing lever. | ✅ Stated: catalog 1-yr reserved rate is **37% below on-demand (γ≈0.63)**, inside Table III's realistic band; new macros `\rsvGamma`, `\rsvDiscountPct`; added a "Reserved-pricing assumption" threat noting savings scale with 1−γ. |

### Minors (selected)
| # | Finding | Resolution |
|---|---|---|
| m1 | `chen2024capacity` cited only as SSRN working paper. | ✅ Added published locator: POM 33(6), pp. 1265–1284, DOI `10.1177/10591478241251614` (Crossref-verified); note softened to "Also available as SSRN…". |
| m2 | `dong2020ondemand` in bib but never cited. | ✅ Cited in §II stream 1 (committed/flexible supply analogue). |
| m3 | FOC of the newsvendor condition unstated; budget/memory MILP scope; "ten services" vs 6 billed. | ✅ Added "first-order condition of (1) rescaled by (t_s+t_d)/t_s"; budget cap noted optional/unset; memory constraint scoped to EC2; "ten AWS **resource types**". |
| m4 | (s,S) policy phrased as the system's. | ✅ Attributed to `[chen2024capacity]`. |
| m5 | Repeated base/supplementary/(s,S) litany; past tense; "precisely…exactly the regime". | ✅ Litany kept once (abstract), conclusion points to §II; "We turned" → "This paper turns"; softened "precisely/exactly". |
| m6 | Overfull AC equation (8.93pt); column hygiene; stale "Prophet" code comments. | ✅ AC equation re-broken (0 overfull); `microtype` added (underfull 16→4); `make_figures.py` Prophet→ETS comments fixed; `HOLDOUT_INTERVAL` renamed. |
| m7 | Flexera grey-literature cite lacked URL/access date. | ✅ Added URL + "accessed 2026". |
| m8 | Placeholder author block / `@example.edu`. | ⚠️ **Left as placeholder** — author identity is the authors' to fill (no PII fabricated). PDF metadata confirmed to leak no author info. |

---

## 3. Build verification (after fixes)

```
pdflatex → bibtex → pdflatex → pdflatex → pdflatex   (fixed point)
Pages:                 7        (within a 6–8 page IEEE limit)
LaTeX errors:          0
Undefined references:  0
"Rerun" warnings:      0
BibTeX warnings:       0        (35 entries, all cited resolve)
Overfull boxes:        0
Underfull boxes:       4        (cosmetic narrow-column justification)
```
`make_figures.py` re-run end-to-end: regenerated `numbers.tex`, `results.json`,
`cv_results.csv`, `mape_tabular.tex` **byte-identical** across runs → pipeline is
deterministic and reproducible. Every figure and number in the PDF traces to the
database via a single script.

---

## 4. Honest final verdict

**What now makes it competitive**
- **Citation integrity is clean** — zero fabricated/mismatched references; six
  real DOI errors fixed and Crossref-verified; the modeled reference now carries
  its published locator.
- **Honest, precise accounting** — the savings are a disclosed
  \$588.40–\$590.40 range with the exact \$2.00 overlap identified by resource;
  the two dominant levers are shown to be jointly realizable. This *strengthens*
  the result by pre-empting the "you double-counted" objection.
- **Reproducibility is now total** — every table cell and in-text number is
  machine-generated; the claim is no longer falsifiable by a hand-typed value.
- **Sharper, defensible positioning** — the contribution is the reproducible
  forecast→MILP→rules integration plus the quantified heuristic-vs-optimum gap,
  not an overclaimed new optimization insight. Soundness (math/MILP/CV) is
  correct and now clearly stated.
- **Clean IEEE presentation** — 7 pages, two-column, 0 overfull, 0 undefined,
  legible figures and tables.

**Residual weaknesses a reviewer may still raise (honestly unresolved)**
1. **Synthetic, single-account evaluation.** The strongest possible fix —
   running the pipeline on a genuinely external trace (e.g., real Bitbrains
   GWA-T-12 or an Azure/Google cluster trace) — was **not** done here; it
   requires a trace-conversion generator that does not ship with the artifact.
   This remains the binding limitation and is disclosed in the abstract and
   Threats. *Recommended next step before a top-tier submission.*
2. **Narrow novelty.** The reference's actual theoretical contribution (the
   two-threshold (s,S) cancellation/renewal dynamics) is not implemented; the
   deployed system is static newsvendor sizing with a fixed q=0.95. The paper
   now states this plainly rather than papering over it.
3. **No head-to-head baseline.** No comparison to AWS Compute Optimizer / a
   stochastic-programming reservation baseline on the same workload; positioning
   is "integration + policy-grounding," not "superiority." Disclosed as a threat.

**Bottom line.** As-is, this is a credible **borderline / workshop-accept** paper
that is now free of integrity, formatting, and overclaiming defects. To move it
from borderline toward accept at a competitive venue, the single highest-leverage
action is an **external-trace validation** (weakness 1); the framing is already
honest about why that is the open item.
