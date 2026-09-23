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
git checkout release/ccpe-v1.0
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Use tag `ccpe-submission-v1.0` instead of the branch when reproducing the
[published archive](https://github.com/G1DO/smart-cloud-optimizer/releases/tag/ccpe-submission-v1.0).
For its recorded full environment, install `requirements-lock.txt` in a fresh
virtual environment instead of `requirements.txt`.

Exercise the optimizer on a disposable copy of the sanitized database:

```bash
artifact_tmp=$(mktemp -d)
cp data/cloud_optimizer.db "$artifact_tmp/cloud_optimizer.db"
python -m optimizer --user-id aws-SYNTHETIC-001 \
  --db-path "$artifact_tmp/cloud_optimizer.db"
python scripts/audit_release_safety.py --path "$artifact_tmp/cloud_optimizer.db"
```

The command prints a recommendation summary and saves recommendations in the
copy. Keep `artifact_tmp` set in the same shell for the example below; the
temporary directory can be removed after inspection. The committed database
should remain unchanged (`git diff --exit-code -- data/cloud_optimizer.db`).

Use `python -m optimizer --help` for the current CLI options.

---

## What is included

| Path | Role |
| --- | --- |
| `optimizer/` | MILP / heuristics cost engine |
| `ml_engine/` | Forecasting helpers used by the platform |
| `storage/` | SQLite access layer |
| `data/cloud_optimizer.db` | Sanitized synthetic account (`aws-SYNTHETIC-001` only) |
| `scripts/` | Release safety audit and database sanitization helpers |
| `config.py` | Shared paths and instance specs |
| `requirements.txt`, `requirements-lock.txt` | Dependencies |

---

## Current technical boundaries

The [optimizer](optimizer/engine.py) reads inventory, metrics, and stored pricing
through [SQLite storage](storage/db.py). It runs EC2/RDS right-sizing through
[PuLP and CBC](optimizer/compute_lp.py), combines those results with
[service-specific rules](optimizer/rules.py), and persists recommendations.
It does not collect live prices or apply changes to AWS resources.

Each run deletes **all previous recommendations for the selected user** before
writing and committing the new results, including when `--services` selects only
some services. Use a database copy for experiments. The budget cap is applied
separately to the EC2 and RDS solver runs; it is not a combined account-wide cap.
An infeasible solver returns no right-sizing assignments; other rules may still
produce recommendations. The printed savings sum can include alternative actions
for the same resource and is not a jointly validated savings plan.

Forecasting is a separate [Python library](ml_engine/__init__.py), not an input
to the optimizer. `python -m ml_engine --user-id aws-SYNTHETIC-001` is a
placeholder that exits with status 1.
The library loads historical costs, fits a model, and returns a DataFrame; callers
choose whether to persist it. For example, after the copy-based run above:

```bash
python - "$artifact_tmp/cloud_optimizer.db" <<'PY'
import sys
from pathlib import Path

import storage
from ml_engine import NaiveForecaster, load_cost_data

conn = storage.get_connection(Path(sys.argv[1]))
try:
    history = load_cost_data(conn, "aws-SYNTHETIC-001")
    forecast = NaiveForecaster().fit(history).predict(horizon=7)
    print(forecast.to_string(index=False))
finally:
    conn.close()
PY
```

The [schema and storage contracts](storage/db.py) are maintained in code;
`ensure_schema()` creates missing tables and applies the included compatibility
migration, while `create_schema()` drops and recreates tables. The optimizer CLI
expects an existing populated schema. Connections use WAL and foreign-key
enforcement. The retained account/credential storage helpers are legacy platform
code and store access-key secrets in plaintext; use synthetic data for this
artifact and do not populate it with live credentials.

## Environment

The recorded environment (2026-07-13) used Python 3.12.3 on Linux x86_64.
[requirements-lock.txt](requirements-lock.txt) is the package-version record;
[requirements.txt](requirements.txt) retains the numeric/ML compatibility pins.
Both dependency files were inherited from the broader platform and include
packages for omitted AWS, AI, API, and UI components. They are preserved for
environment continuity, not a claim that those components ship here.

Compute right-sizing uses PuLP's `PULP_CBC_CMD` solver. Check that its bundled
CBC executable is available in the installed environment:

```bash
python -c 'import pulp; assert pulp.PULP_CBC_CMD().available(), "PuLP CBC is unavailable"'
```

A system `cbc` installation alone does not change the solver selected by this code.

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
- **Published release:** [ccpe-submission-v1.0](https://github.com/G1DO/smart-cloud-optimizer/releases/tag/ccpe-submission-v1.0)
- **Zenodo DOI:** https://doi.org/10.5281/zenodo.21358415
