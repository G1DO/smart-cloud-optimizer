# Reproducibility — CCPE software artifact

Manuscript: *The Price of Conservatism in Cloud Optimization: An Empirical
Evaluation of Right-Sizing and Reservation Policies*  
Target journal: CCPE (Concurrency and Computation: Practice and Experience)

This public release contains the **implemented software stack** used in the
paper (optimizer, forecasting helpers, storage layer, sanitized synthetic
database) under the MIT License. It does **not** include the manuscript folder
(`paper/`), internal submission docs (`docs/`), application UI, live AWS
collection tooling, or the paper-side experiment scripts that regenerate
tables and figures.

---

## Quick start

```bash
git clone https://github.com/G1DO/smart-cloud-optimizer.git
cd smart-cloud-optimizer
git checkout release/ccpe-v1.0   # or tag ccpe-submission-v1.0 when published
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# optional exact env:
# pip install -r requirements-lock.txt
```

Exercise the committed optimizer entry point (requires the sanitized DB):

```bash
python -m optimizer --user-id aws-SYNTHETIC-001
```

---

## What is included

| Path | Role |
| --- | --- |
| `optimizer/` | MILP / heuristics cost engine |
| `ml_engine/` | Forecasting helpers used by the platform |
| `storage/` | SQLite access layer |
| `data/cloud_optimizer.db` | Sanitized synthetic account (`aws-SYNTHETIC-001` only) |
| `scripts/` | Release safety helpers (audit / DB sanitize) |
| `config.py` | Shared paths and instance specs |
| `requirements.txt`, `requirements-lock.txt` | Dependencies |

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
| CBC | optional; install `coinor-cbc` (Debian/Ubuntu: `sudo apt install coinor-cbc`) |

---

## Data

- **Synthetic DB:** `data/cloud_optimizer.db` — synthetic EC2/RDS-style
  resources only; no live AWS credentials, no personal data.
- **GWA public traces:** not redistributed here. Obtain from
  [GWA traces](https://atlarge-research.com/gwa-traces) if needed for
  independent study. Paper-side restore scripts are **not** in this release.
- **Azure Public Dataset V2:** not part of the manuscript or this artifact.

---

## What is not in this release

1. Manuscript sources, PDF, and LaTeX build (`paper/` excluded).
2. Paper evidence scripts that regenerate JSON/TeX/figures.
3. Application frontend, dashboard, AWS collectors, and AI advisor modules.
4. Internal submission checklists (`docs/`).

Manuscript experiment regeneration materials can be requested from the
corresponding author for editorial/review use.

---

## Citation and archive

- **Code repository:** `https://github.com/G1DO/smart-cloud-optimizer/tree/release/ccpe-v1.0`
- **Release tag:** `ccpe-submission-v1.0` (upon public push)
- **Zenodo DOI:** to be added after institutional archive upload
