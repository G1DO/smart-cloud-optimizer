<!-- PR title: `<scope>: <what changed>`. Target: `main` only. -->
## What / why

- What changed:
- Why:

## Verification (Delivery+Verification)

Commands actually run + outcomes (include baseline failures separately):

- [ ] `python -m pytest tests/ -v`
- [ ] frontend `npm run lint` / `npm run build` (if touched)
- [ ] `git diff --check`
- [ ] `python scripts/check_secrets.py`
- [ ] `python scripts/verify_schema_restore.py` (if storage/schema touched)
- [ ] Docs updated in same PR (if behavior changed)

## Trailer (required — Closes/Refs where supported)

<!-- Keep exactly one line. GitHub preserves this on squash-merge. -->

Refs #<n> - <reason> <!-- or: Closes #<n> -->
