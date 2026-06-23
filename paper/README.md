# Smart Cloud Optimizer — IEEE Conference Paper

**Title:** *Forecast-Driven Capacity Reservation and Right-Sizing for Cloud
Cost Optimization under Intermittent Random Demand Surges*

This directory contains the LaTeX source, figures, and compiled PDF of the
conference paper written about this project. It is modeled on the narrative and
problem framing of Chen, Lei & Moinzadeh, *"Cost Optimization in Cloud
Computing: Capacity Reservation for Intermittent Random Demand Surges,"*
Production and Operations Management 33(6), 2024 — adapted to the IEEE
conference format and grounded in this system's real code, data, and results.

## Contents

| File | Description |
|------|-------------|
| `main.tex` | Paper source (IEEEtran `conference` class). |
| `references.bib` | Bibliography (19 references). |
| `make_figures.py` | Regenerates every figure from `data/cloud_optimizer.db` and the walk-forward CV results. |
| `figures/` | Generated PDF figures. |
| `main.pdf` | Compiled paper (6 pages + references). |

## All numbers are reproducible

Every quantitative claim is drawn from the project itself:

- **$590.40/month** total savings (≈26% of the ~$2,239/mo bill), 19
  recommendations — read live from the `recommendations` table.
- **Forecasting MAPE** (7.9% @ 7-day, etc.) — from
  `documentation/forecasting_models.md` walk-forward cross-validation.
- **30-day holdout MAPE (11.9%)** and **detected surges** — computed on the fly
  by `make_figures.py` over the daily-cost series.
- **P95 + 1.3× headroom** sizing and the 8 rules — from `optimizer/`.

## Build

Requires a TeX Live installation with the `ieeetran`, `booktabs`, and
`hyperref` packages, plus Python with `matplotlib`, `numpy`, and `pandas`.

```bash
# 1. (Re)generate figures from the project database
python make_figures.py

# 2. Compile the paper
pdflatex main.tex
bibtex   main
pdflatex main.tex
pdflatex main.tex
```

The output is `main.pdf`.

## Before submitting

- Fill in the real **author names**, **emails**, and **supervisor** in the
  author block of `main.tex`.
- Replace the venue-specific copyright/footer if the target conference requires
  it.
- If you have access to the original reference paper's PDF, verify the exact
  citation details in `references.bib` (entry `chen2024cost`).
