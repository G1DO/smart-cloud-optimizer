# Contributing

Application changes target **`main`** only. The default `release/ccpe-v1.0`
branch is a separate paper artifact; select `main` explicitly when opening
an application PR. This repo is a single-user localhost demo — see
[threat model](docs/security/threat-model.md) before connecting real data.

## PRs: title, body, trailers

- Title: `<scope>: <what changed>` (e.g. `docs: clarify sync recovery`).
  Keep it specific; no `WIP` in the title at merge time.
- Body must state: what changed, why, and verification actually run
  (commands + outcomes, including baseline failures). Template:
  [.github/pull_request_template.md](.github/pull_request_template.md).
- Every PR body ends with a trailer line. Use `Closes #<n>` when the PR
  resolves the issue, `Refs #<n>` when it only relates:
  `Closes #12` / `Refs #12`. No issue → `Refs N/A - <reason>`
  (e.g. small doc fix). GitHub preserves the PR body on squash-merge,
  so the trailer is the audit link. Next 2 PRs must carry trailers;
  baseline at time of writing: 0 `Closes`/`Refs` trailers in 112 commits.

## Before opening

- Start with [README setup](README.md#run--docker), then
  `README.md` Verify for commands. Verbs: `pyproject.toml [tool.poe.tasks]`, `Makefile`.
- Run the relevant checks and report results in the PR:
  `pytest`, frontend `lint`/`build` when touched, `git diff --check`,
  `python scripts/check_secrets.py`,
  `python scripts/verify_schema_restore.py` when storage/schema changes.
  Same checks run in CI on `main` (see `.github/workflows/`).
- Update affected technical docs in the same PR as code. Docs are minimal:
  root `README.md` + `docs/architecture/*.mmd` + `data-model.md` + `threat-model.md` + 1 ADR.
  `operations/runbook.md` absent pre-prod.
- Never add credentials, personal data, account identifiers, or runtime
  database changes. Keep `.env` and snapshots out of Git. Redact logs
  before sharing.

For vulnerability reporting use [SECURITY.md](SECURITY.md) — private route
only, never public issues/PRs.
