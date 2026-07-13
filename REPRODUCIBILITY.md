# Reproducibility — CCPE manuscript artifact

Manuscript: *The Price of Conservatism in Cloud Optimization: An Empirical
Evaluation of Right-Sizing and Reservation Policies*  
Target journal: CCPE (Concurrency and Computation: Practice and Experience)

This document describes how to reproduce the paper's empirical evidence from
this repository. **No manuscript number is hand-typed** — all values flow from
generated JSON/TeX files into LaTeX macros.

---

## Quick start

```bash
git clone <PUBLIC_REPO_URL>
cd cloud-gp
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Synthetic-account evidence (~10 s)
venv/bin/python paper/evidence_experiments.py
venv/bin/python paper/catalog_comparison.py
venv/bin/python paper/make_figures.py
venv/bin/python paper/policy_sim.py

# Optional: GWA public traces (~7–8 min including download)
export TRACE_DIR="$PWD/traces"
./paper/fetch_traces.sh "$TRACE_DIR"
venv/bin/python paper/external_validation.py --trace-dir "$TRACE_DIR"
venv/bin/python paper/study2_reproducibility.py --trace-dir "$TRACE_DIR"
venv/bin/python paper/policy_sim.py --csv paper/trace_rnd_hourly.csv \
  --prefix extPol --suffix _ext --gamma-star 0.63

# Journal PDF (requires LaTeX: pdflatex + bibtex)
./paper/journal/build_final_journal.sh
```

For an exact environment, use `pip install -r requirements-lock.txt` (full
freeze from the authors' Linux test machine).

Verify outputs: `python scripts/hash_paper_artifacts.py`

---

## Environment

| Component | Recorded version (2026-07-13) |
| --- | --- |
| Python | 3.12.3 |
| OS | Linux x86_64 |
| numpy | 1.26.4 |
| pandas | 3.0.3 |
| scipy | 1.17.1 |
| PuLP | 3.3.2 |
| Prophet | 1.3.0 |
| statsmodels | 0.14.6 |
| pmdarima | 2.1.1 |
| CBC | optional; install `coinor-cbc` (Debian/Ubuntu: `sudo apt install coinor-cbc`; macOS: `brew install coin-or-tools/coinor/cbc`) |

LaTeX: `pdflatex`, `bibtex` (e.g. TeX Live / TinyTeX).

---

## Data inputs

### 1. Synthetic AWS account (committed)

- **File:** `data/cloud_optimizer.db`
- **User id:** `aws-SYNTHETIC-001`
- **Content:** Synthetic EC2/RDS-style resources and metrics derived from
  open-source traces and catalog artifacts — not a live AWS account.

### 2. GWA workload traces (download required)

| Archive | VMs | License / source |
| --- | ---: | --- |
| `gwa_t_12_fastStorage.zip` | 1,250 | [GWA traces](https://atlarge-research.com/gwa-traces) |
| `gwa_t_12_rnd.zip` | 500 | same |
| `gwa_t_13_materna.zip` | 547 | same |

```bash
./paper/fetch_traces.sh "$TRACE_DIR"
```

Checksums and runtimes: `paper/trace_provenance.md`.

### 3. AWS catalog snapshot

- **Module:** `paper/aws_catalog.py`
- **Snapshot date:** 2026-06-30 (28 EC2 types, us-east-1)
- **Not** live AWS API calls during reproduction.

### 4. Not included (by design)

- **Azure Public Dataset V2** — removed from the CCPE manuscript.
- **Commercial recommender outputs** — not available; paper uses labeled
  paper-side replay baselines only.

---

## Claim → evidence mapping

| Manuscript section | Script | Primary outputs |
| --- | --- | --- |
| Synthetic MILP / baselines / runtime | `paper/evidence_experiments.py` | `results_baselines.json`, `table_baselines.tex`, `results_runtime.json` |
| EC2 catalog scope | `paper/catalog_comparison.py` | `results_catalog_comparison.json`, `table_catalog_comparison.tex` |
| Study I figures / forecasting CV | `paper/make_figures.py` | `results.json`, `numbers.tex`, `figures/*.pdf` |
| Study II GWA right-sizing | `paper/external_validation.py` | `results_external.json`, `numbers_external.tex` |
| Study II CIs / baseline grid | `paper/study2_reproducibility.py` | `table_external_baselines.tex`, `trace_provenance.md` |
| Study III policy simulation | `paper/policy_sim.py` | `results_policy.json`, `results_policy_ext.json` |
| Final PDF | `./paper/journal/build_final_journal.sh` | `paper/journal/final/journal_final.pdf` |

---

## Expected runtimes and storage

| Stage | Approx. time | Disk |
| --- | ---: | ---: |
| `pip install -r requirements.txt` | 2–5 min | ~1 GB venv |
| Synthetic scripts (4 commands) | < 30 s | DB ~15 MB |
| GWA fetch + extract | ~3 min | ~430 MB |
| GWA validation + study2 | ~5 min | +outputs |
| Journal LaTeX build | 1–3 min | ~1 MB PDF |

---

## Non-reproducible / reviewer-action items

1. **GWA traces** — must be downloaded; script errors if `$TRACE_DIR` is missing.
2. **CBC solver** — install `coinor-cbc` before running MILP experiments (see Environment table).
3. **`make_figures.py --with-sarimax`** — optional and slow; not required for default numbers.

---

## Citation and archive

- **Code repository:** see GitHub release tag `ccpe-submission-v1.0`
- **Zenodo DOI:** to be added after archive upload
