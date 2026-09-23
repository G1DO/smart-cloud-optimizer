# Contributing to the CCPE artifact

Target artifact changes at `release/ccpe-v1.0`, the repository's default branch.
The published `ccpe-submission-v1.0` tag records the archived submission; changes
to the branch do not update that archive. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
for setup, included components, and current technical behavior.

The canonical [Workflow](https://app.notion.com/p/3bb0a821b3cc817394cdf93a936a3612)
and [Documentation guidance](https://app.notion.com/p/3bb0a821b3cc815099acfd2d5e8b0859)
define the engineering process and documentation responsibilities. Keep this
repository's technical instructions current with the affected change.

## Local verification

Run from the repository root with the virtual environment activated:

```bash
python -m pip check
python -m compileall -q config.py storage optimizer ml_engine scripts
python scripts/audit_release_safety.py
git diff --check
```

Run the [copy-based optimizer example](REPRODUCIBILITY.md#quick-start) and
[forecasting example](REPRODUCIBILITY.md#current-technical-boundaries) to exercise
the storage, solver, and library boundaries. Inspect the saved
recommendations in the copied database and confirm the committed fixture is
unchanged. For changes to numerical behavior, additionally verify the affected
model, rule, or solver case; a successful smoke run does not establish forecast
accuracy or the manuscript's experimental results.

This artifact branch currently ships no automated test suite or project CI
workflow. The pytest settings in `pyproject.toml` apply to tests added here;
running pytest without tests is not a passing verification result. GitHub's
dependency graph update is not a replacement for behavioral checks.
There is no configured Markdown/link checker: preview changed Markdown on GitHub
and verify its local paths, anchors, and external destinations.

## Synthetic data and release safety

Keep the committed fixture synthetic. Never include live credentials, real account
data, or undisclosed sensitive vulnerability details in public issues or PRs.
The existing release audit scans files, database rows and raw database bytes, and
selected Git history for known patterns. Review its findings; a clean result is
not a guarantee that arbitrary input has been anonymized.

When preparing a replacement fixture, use the sanitizer on a separate output:

```bash
python scripts/sanitize_release_db.py \
  --source data/cloud_optimizer.db \
  --output data/cloud_optimizer.release.db
python scripts/audit_release_safety.py --path data/cloud_optimizer.release.db
```

Inspect the output before replacing any committed database. The sanitizer removes
non-synthetic user rows and connection rows, scrubs the synthetic user's email,
and rebuilds the database to remove deleted contents from free pages. Its
`--in-place` mode changes the source and creates a backup; those files may still
contain sensitive source data and must not be committed.

## Pull requests

Use a focused branch and describe the change, its reason, and the verification
actually performed, including any limits. Link an issue when one tracks the work.
Update affected technical docs in the same PR and inspect the diff for unintended
database changes or private material. Record self-review or obtain the review
appropriate to the change, and satisfy any checks and protections attached to the
PR before merging. Existing repository PR history uses merge commits.
