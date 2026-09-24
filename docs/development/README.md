# Development Guide

Use the [README](../../README.md#quick-start) for setup. Run Python commands from
the repository root with the virtual environment active.

Application PRs target **`main`**; the default `release/ccpe-v1.0` branch contains
the separate paper artifact. Keep changes focused, update affected technical
documentation, and describe what changed, why, and the verification actually run.
Report pre-existing failures separately from regressions and respect any target
branch checks or review requirements. Use [SECURITY.md](../../SECURITY.md) for
vulnerability reporting.

## Checks

```bash
python -m pip check
python -m pytest tests/ -v
python -m compileall -q backend_api cloud_optimizer aws_collector storage \
  data_generation ml_engine optimizer ai_module dashboard
git diff --check
```

The pytest suite covers storage/authentication, AWS configuration and connections,
synthetic generation, forecasting, optimization, AI helpers, legacy dashboard
behavior, and frontend/backend contracts. Discover the current test inventory
with `python -m pytest --collect-only -q`. Tests use local fixtures and mocked
services; they require no live AWS or AI credentials.

For the TypeScript frontend, use the committed lockfile:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

The scripts are defined in [package.json](../../frontend/package.json). For changes
to request/response behavior, also exercise the affected page with the backend
running. FastAPI generates the current endpoint and model reference at
http://localhost:8000/docs and http://localhost:8000/openapi.json.

There is currently no repository CI or documentation validation tool configured.
Use the [schema generator](../architecture/data-model.md) and
[storage signature lookup](../api/storage.md#current-signatures) when changing those
contracts; [HTTP reference generation](../api/http.md) also works without starting
the server or touching the tracked database.
Check changed Markdown links and anchors, preview rendering, and verify commands
against the implementation. Report commands and outcomes in the PR, including
any baseline failure; keep existing tests and validation intact.

## Project patterns

- Follow the surrounding Python or TypeScript style. Python uses type hints and
  module loggers; lazy imports also occur for optional or expensive integrations.
- Shared paths, `.env` loading, and constants live in
  [cloud_optimizer/config.py](../../cloud_optimizer/config.py). AWS session/client
  construction lives in [aws_collector/config.py](../../aws_collector/config.py).
- Prefer the `storage` facade for database access. Some API routes currently use
  SQL directly; see [Architecture](../architecture/README.md). Data keyed by `user_id`
  does not provide server-side authorization.
- Use `ensure_schema()` for additive initialization. `create_schema()` drops and
  recreates tables and belongs only in disposable fixtures. See the
  [storage contract](../api/storage.md#transaction-contract) for commit ownership.
- Keep tests independent of external services. Use pytest temporary paths for
  writes and mocks for AWS/AI calls. Do not regenerate the tracked database as
  part of routine testing.
- Read [optimizer usage](../architecture/engines/optimizer.md#usage) before running a write operation;
  both optimization and collection can replace existing stored results.

Python dependencies live in [requirements.txt](../../requirements.txt);
[pyproject.toml](../../pyproject.toml) configures pytest and coverage. Update the
numeric/ML pins together when changing that stack, then verify imports and the
relevant forecasting tests.
