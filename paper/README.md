# IEEE Conference Paper — Smart Cloud Optimizer

*A Data-Driven Capacity-Reservation System for Cloud Cost Optimization under
Intermittent Demand Surges.*

An IEEEtran two-column conference paper that frames this project through the
capacity-reservation model of Chen, Lei & Moinzadeh, *"Cost Optimization in
Cloud Computing: Capacity Reservation for Intermittent Random Demand Surges,"*
Production and Operations Management 33(6), 2024 (base/supplementary reserved
contracts, on-demand spillover, the newsvendor critical fractile, and the
two-threshold `(s,S)` policy) — but grounds every number in this repository's
real database and forecasting/optimization code.

## Reproducibility contract

**No number in the paper is hand-typed.** `make_figures.py` reads
`../data/cloud_optimizer.db`, runs the project's own `ml_engine` forecasters and
reads the optimizer's `recommendations`, and emits:

- `figures/*.pdf` — the six vector figures used in the paper
- `numbers.tex` — every quantity as a `\newcommand` macro that `main.tex` uses
- `mape_tabular.tex` — the full MAPE table (Table II), generated so no cell is typed
- `results.json` — the same numbers, machine-readable
- `cv_results.csv` — the per-(model, horizon) walk-forward MAPE table

Editing the database and re-running the script updates the figures *and* the
prose numbers consistently.

## Files

| File | Purpose |
|------|---------|
| `main.tex` | the paper (IEEEtran, `\conference`) |
| `references.bib` | bibliography — reference's own citations + verified additions (DOIs) |
| `make_figures.py` | regenerates figures, `numbers.tex`, `results.json`, `cv_results.csv` |
| `numbers.tex` | **generated** — `\input` by `main.tex` |
| `mape_tabular.tex` | **generated** — full Table II, `\input` by `main.tex` |
| `figures/` | **generated** vector PDFs |
| `REVIEW.md` | adversarial peer-review report + changelog |
| `build.sh` | one-shot rebuild (figures → LaTeX) |
| `main.pdf` | compiled output |

`reference/reference.pdf` (the modeled paper) is **not** committed — it is
copyrighted source material; place your own copy there if you want to re-derive
the structural blueprint.

## Prerequisites

1. **Python** with the project's scientific stack (matplotlib, pandas, numpy,
   statsmodels, prophet, pmdarima, pulp). From the repo root:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt        # or: numpy<2 pandas matplotlib statsmodels prophet pmdarima pulp
   ```
2. **LaTeX** with the IEEEtran class. A no-root option used to produce this
   paper is TinyTeX:
   ```bash
   # install TinyTeX (user-space), then:
   tlmgr install ieeetran cite algorithm2e algorithmicx algorithms relsize \
       booktabs caption multirow microtype
   ```
   Ensure `pdflatex` and `bibtex` are on `PATH`.

## Rebuild

```bash
# from repo root, with the venv active and pdflatex on PATH:
cd paper
../venv/bin/python make_figures.py        # ~2 min (Prophet CV dominates)
./build.sh                                 # pdflatex -> bibtex -> pdflatex x2
```

`make_figures.py --with-sarimax` additionally benchmarks SARIMAX (slow: minutes
per cross-validation fold; excluded from the paper for that reason).

The build is clean: 0 LaTeX errors, 0 undefined references, 0 BibTeX warnings,
0 overfull boxes, 7 pages.

## Honesty note

The evaluation workload is the **synthetic** dataset shipped with the project,
modeled on public cloud traces (Bitbrains GWA-T-12, Numenta Anomaly Benchmark),
**not** a live AWS account. Absolute dollar figures illustrate the method; the
methodology transfers. The deployed system realizes the *static* newsvendor
sizing, not the full `(s,S)` cancellation/renewal dynamics. Both points are
stated in the paper's *Threats to Validity* section. Author names/emails are
fill-in placeholders.
