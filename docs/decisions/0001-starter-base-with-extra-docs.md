# ADR 0001: Ultra-minimal docs — root README + 9 required files

- Status: Accepted
- Date: 2026-10-20
- Branch: `main`
- Supersedes: Starter-base draft with engines/pipeline/local-runtime companions

## Context

`main` is a substantive single-user localhost system (persistent SQLite, Auth/sensitive firing, no prod). Starter requires for substantive: `README.md`, 6x `.mmd` + `data-model.md`, `threat-model.md` (Auth fires), verbs, `verify.yml`. Operations `runbook/slo/recovery` absent until prod. Template wants ~6 pages heuristic, merge over add, absent over stub.

Previous detail pages (`engines/`, `data-pipeline.md`, `local-runtime.md`, `api/`, `reference/configuration.md`, `development/`, `security/README.md`, `arch/README.md`, `report.pdf`) duplicated code facts and inflated review burden. Root README can carry run/verify/ops as pointers with code canonical.

## Decision

Keep 10 versioned docs only:

- `README.md` — pointer + run + verify + index, code links only, no pastes
- `docs/architecture/c1-system-context.mmd`, `c2-containers.mmd`, `c3-components.mmd`, `sequence.mmd`, `state.mmd`, `deployment.mmd`
- `docs/architecture/data-model.md` — generator from `storage/db.py`, compat proof
- `docs/security/threat-model.md` — Auth fires
- This ADR

Delete: `docs/README.md`, `arch/README.md`, `api/http.md`, `api/storage.md`, `data-pipeline.md`, `engines/*`, `development/*`, `operations/local-runtime.md`, `runbook.md` (N/A pre-prod), `reference/configuration.md`, `security/README.md`, `project-report.pdf` (release asset). Fold essential facts into root README; code is canonical for schemas, contracts, config, identity, sync order, LP formulation.

## Consequences

- One home per fact: intent in root, diagrams in `.mmd`, schemas in `storage/db.py`, decisions here.
- Fewer files to rot; docs PRs touch root or 1 `.mmd`.
- Risk: root grows; mitigate by links not copies, 150-line cap. Engine LP detail lives in `optimizer/engine.py`, sync order in `aws_collector/runner.py`, identity in `backend_api/routers/connections.py`.

## Verification

- `git ls-files docs/` = 9 files above.
- `python3 scripts/check_no_pasted_diagrams.py` green (no fences).
- `python3 scripts/check_secrets.py` + `verify_schema_restore.py` green.
