<!-- PR title: `<scope>: <what changed>`. Target: `main` only. -->
## What / why

- What changed:
- Why:

## Verification (Delivery+Verification)

Commands actually run + outcomes (include baseline failures separately):

- [ ] `python -m pytest tests/ -v`
- [ ] frontend `npm run lint` / `npm run build` (if touched)
- [ ] `git diff --check`
- [ ] `gitleaks detect --source . --config .gitleaks.toml --verbose`
- [ ] Docs updated in same PR (if behavior changed)

## Trailer (required — Closes/Refs where supported)

<!-- Keep exactly one line. GitHub preserves this on squash-merge. -->

Refs #<n> - <reason> <!-- or: Closes #<n> -->
