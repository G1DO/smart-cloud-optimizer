# IEEE Journal Paper — Smart Cloud Optimizer

*A Data-Driven Capacity-Reservation System for Cloud Cost Optimization under
Intermittent Demand Surges.*

An IEEEtran **journal-mode** manuscript (target: IEEE TNSM / IEEE TCC, Q1)
that frames this project through the capacity-reservation model of Chen, Lei
& Moinzadeh, *"Cost Optimization in Cloud Computing: Capacity Reservation for
Intermittent Random Demand Surges,"* Production and Operations Management
33(6), 2024 — and evaluates it three ways:

- **Study I** — the synthetic 365-day account shipped with the repo
  (forecasting CV with per-fold sd/MASE/DM tests + optimizer savings).
- **Study II** — external validation on **real traces**: Bitbrains GWA-T-12
  (fastStorage 1,250 VMs; Rnd 500 VMs) and Materna GWA-T-13 (547 VMs), with
  the system's MILP priced against a **verified AWS catalog**
  (`aws_catalog.py`, Price List snapshot 2026-06-30) — plus a 237k-VM
  **Azure Public Dataset V2** boundary-condition study (`azure_validation.py`:
  max-based percentiles + unmeasured memory flip right-sizing cost-negative;
  reservations still save 34.8%).
- **Study III** — an out-of-sample policy simulation (γ sweep) quantifying
  the "price of conservatism": deployed p95×1.3 fractile vs. newsvendor
  1−γ vs. SAA stochastic program vs. dual-capacity (K₀,K₁; observable-state
  and causal variants, with threshold and minimum-hold sensitivity) vs.
  clairvoyant.

## Reproducibility contract

**No number in the paper is hand-typed.** The build chain, from raw data to
PDF:

```bash
# 0) once: fetch the public traces (~430 MB, archive maintainers' mirror)
./fetch_traces.sh /path/to/traces

# 1) real-trace study -> numbers_external.tex, external_mape_tabular.tex,
#    fig_ext_series.pdf, trace_rnd_hourly.csv, results_external.json
../venv/bin/python external_validation.py --trace-dir /path/to/traces

# 2) Azure vmtable study (~440 MB download; see script docstring for URL)
../venv/bin/python azure_validation.py --vmtable /path/to/vmtable.csv.gz

# 3) policy simulation, synthetic + real -> numbers_policy*.tex,
#    policy_tabular*.tex, fig_policy_gamma*.pdf, results_policy*.json
../venv/bin/python policy_sim.py
../venv/bin/python policy_sim.py --csv trace_rnd_hourly.csv \
    --prefix extPol --suffix _ext --gamma-star 0.63 --holds 1,6,24,168

# 4) synthetic-account study -> numbers.tex, mape_tabular.tex, figures/*,
#    results.json, cv_results.csv
../venv/bin/python make_figures.py

# 5) LaTeX (pdflatex + bibtex, e.g. TinyTeX on PATH)
./build.sh
```

Everything is deterministic (Prophet's interval sampling is seeded); editing
the database or traces and re-running updates figures *and* prose numbers
consistently.

## Files

| File | Purpose |
|------|---------|
| `main.tex` | the manuscript (IEEEtran `journal`) |
| `references.bib` | 93 entries — all DOI/arXiv-verified (Crossref); zero fabricated |
| `paperlib.py` | shared eval lib: per-fold walk-forward CV (MAPE/MASE/coverage), Diebold–Mariano + HLN, newsvendor/SAA/dual-capacity policy primitives |
| `make_figures.py` | Study I: figures, `numbers.tex`, `mape_tabular.tex`, `results.json`, `cv_results.csv` |
| `external_validation.py` | Study II: trace parsing, MILP right-sizing, trace CV → `numbers_external.tex`, … |
| `azure_validation.py` | Study II-C: Azure vmtable boundary-condition study → `numbers_azure.tex`, … |
| `policy_sim.py` | Study III: policy replay + SAA baselines + sensitivity → `numbers_policy*.tex`, … |
| `aws_catalog.py` | verified 28-type AWS us-east-1 price/spec catalog (snapshot-dated) |
| `fetch_traces.sh` | pinned download of Bitbrains GWA-T-12 + Materna GWA-T-13 |
| `REVIEW.md` | adversarial peer-review report + changelog |
| `build.sh` | pdflatex → bibtex → pdflatex ×2 |

`reference/reference.pdf` (the modeled paper) and downloaded `traces/` are
**not** committed (copyright / size); `fetch_traces.sh` restores the traces.

## Honesty notes (stated in the paper's Threats section)

- Study I's dollar figures are method-illustrative (synthetic account).
- Study II prices 2013–2016 VMs at 2026 AWS rates under a like-for-like
  mapping; percentages transfer, absolute dollars are indicative.
- Study III's HEUR policy reads the deployed fractile as a
  reservation-sizing rule **the deployed system does not execute** — that is
  the point being quantified, not a description of the system.
- ETS vs. seasonal-naive accuracy is **not statistically separable** at the
  30-day horizon (DM p=0.198); the paper claims selection, not superiority.
- Author names/emails are fill-in placeholders.
