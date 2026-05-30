# Style Guide — Mirroring Chen, Lei & Moinzadeh (2024)

This guide analyzes the style of the reference paper and documents how
`main.tex` reproduces it. Use it when revising the draft or writing follow-up
sections so the manuscript stays stylistically consistent.

## The reference paper

> Chen, S., Lei, J., & Moinzadeh, K. (2024). **"Cost Optimization in Cloud
> Computing: Capacity Reservation for Intermittent Random Demand Surges."**
> *Production and Operations Management*, 33(6), 1265–1284.
> DOI: [10.1177/10591478241251614](https://doi.org/10.1177/10591478241251614)
> · SSRN working paper [3784812](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3784812)

**Genre.** It is an *analytical operations-management* paper in the
*Production and Operations Management* (POM) tradition: a stylized stochastic
model, structural results proved as propositions/theorems, a numerical study
that sweeps parameters to extract comparative statics, and a managerial-
insights payoff. It contains **no software or empirical system** — the
contribution is the model and its policy.

> **Note on access.** The full text is paywalled (SAGE) and SSRN/ResearchGate
> block automated download, so verbatim section headings and the exact
> notation table could not be extracted programmatically. The structure below
> is the standard POM analytical-paper template, corroborated against four
> independent abstract/summary sources. **Open the SSRN preprint in a browser
> to copy exact headings, the notation table, and proof formatting** if you
> want a byte-for-byte match.

## The model in one paragraph (so we position against it correctly)

A firm meets a **stationary base demand** plus **intermittent random surges**.
It buys **base contracts** (standard-length, e.g. 1-year, reserved instances)
for the base and **supplementary contracts** (standard or shorter reserved
instances) for surges. With deterministic surge / inter-surge durations and
random surge magnitude (cancellation allowed), the optimal supplementary
capacity is a **newsvendor (critical-fractile)** quantity and the
purchase/renew/cancel decision is a **two-threshold policy**; the paper then
extends to stochastic durations and compares a **secondary marketplace** with
cancellation-only platforms. Key levers: **discount rate, cancellation fee,
surge/inter-surge durations**.

## Structural template (what to mirror)

| # | Reference (POM analytical) | Our `main.tex` section |
|---|----------------------------|------------------------|
| 1 | **Introduction** — motivation, gap, bulleted contributions | §1 Introduction (4 contribution bullets) |
| 2 | **Literature Review** — themed paragraphs | §2 Related Work (5 themed paragraphs) |
| 3 | **Model** — notation table, assumptions, cost components | §3 Model (notation table, Assumption 1, demand & cost eqs.) |
| 4 | **Analysis** — propositions/theorems; deterministic case first | §4 Optimal Capacity Reservation (Props 1–4) |
| 5 | **Extensions** — stochastic durations, marketplace | §4.3–4.4 (surges, spot tier) + §8 future work |
| 6 | **Numerical study** — parameter sweeps → insights | §6 Numerical Study (6 subsections, 5 figures, 3 tables) |
| 7 | **Managerial insights / Conclusion** | §7 Managerial Insights + §8 Conclusion |
| 8 | **Appendix** — proofs | Appendix A (proofs of Props 1–4) |

The one deliberate divergence: we add **§5 (the system)**, because our
contribution is an *applied system + model*, not a pure model. It sits between
the analysis and the numerical study so the experiments can exercise it.

## Stylistic conventions to keep

1. **Formal, impersonal, present tense.** "We model… We show that…
   The optimal level is…". No first-person anecdotes; no marketing language.
2. **Notation table early** (our Table 1), every symbol defined once.
3. **Assumptions are numbered and explicit** (our Assumption 1) before the
   analysis uses them.
4. **Results as numbered Propositions/Corollaries**, each stated crisply with
   the *economic interpretation* in the following paragraph, and the **proof
   deferred to the appendix**. The reference leads with the newsvendor result
   and a threshold policy — we mirror this exactly (Prop 1 newsvendor, Prop 2
   threshold).
5. **Comparative statics are the payoff.** State how the optimum moves with
   each parameter (discount ↑ ⇒ reserve more; surge fraction ↑ ⇒ reserve
   supplementary). The reference's headline insights are all of this form.
6. **Numerical study sweeps parameters** and reports *percentages and
   directions*, not just point numbers. End each finding with the managerial
   takeaway.
7. **Managerial insights as a bulleted list**, each bullet a one-line
   imperative ("Reserve to a demand quantile, not to the peak").
8. **Tie every claim to a reference** in Related Work; group citations by
   theme.
9. **Figures/tables:** `booktabs` rules (no vertical lines), vector PDF
   figures, captions that state the takeaway, not just the contents.

## Abstract recipe (the reference's shape, reused in our draft)

1 sentence problem → 1 sentence approach (base + supplementary) → 2 sentences
method/results (newsvendor + threshold; forecasting + MILP) → 1 sentence
quantified payoff → 1 sentence broader significance. Keywords line at the end.

## Things to fill in before sharing with the doctor

- **Author names & affiliations** — placeholders `[Author One]`, `[Advisor]`,
  etc. in `main.tex`.
- **Target venue** — if submitting to a specific journal/conference, swap the
  `article` class for that venue's template (the content/structure transfers).
- Decide whether to **deepen the dynamic policy** (cancellation fees, renewal,
  secondary marketplace) to match the reference's two-threshold result more
  closely — currently summarized as future work in §8.
