# HTTP contracts

The [FastAPI app](../../backend_api/main.py) and its
[routers](../../backend_api/routers/) own endpoint and Pydantic model definitions.
With the backend running, use http://localhost:8000/docs for interactive reference
and http://localhost:8000/openapi.json for the machine-readable schema.

Generate the same schema without starting the server or running its database
initialization, from the repository root with Python dependencies installed:

```bash
python - <<'PYTHON'
import json
from backend_api.main import app
print(json.dumps(app.openapi(), indent=2))
PYTHON
```

Do not maintain a handwritten endpoint/schema inventory alongside this output.
Generated schemas describe input/output shapes; the important behavioral
contracts are linked below.

## Behavioral contracts

- [Identity and connections](../architecture/README.md#connection-identity-and-verification): registration identity, AWS workspace selection, and separate test/save behavior.
- [Security boundaries](../security/README.md): client-supplied user IDs, optional onboarding token, and plaintext credentials.
- [Data pipeline](../architecture/data-pipeline.md): sync is asynchronous and replaces prior account data incrementally.
- [Forecasting](../architecture/engines/forecasting.md): history requirements, caching, and comparison versus offline accuracy evaluation.
- [Optimization](../architecture/engines/optimizer.md): replacement writes, budget scope, and recommendation limits.
- [AI advisor](../architecture/engines/ai-advisor.md): failure responses, prompt guard, and persistence differences.
- [Runtime settings](../architecture/README.md#runtime-settings): saved preferences are not active engine inputs.

`GET /health` returns a static `{"ok": true}` response. It establishes HTTP
liveness, not database integrity or AWS/Gemini readiness. Use the
[operations guide](../operations/local-runtime.md) for diagnosis.

## Compatibility and verification

The browser UI and API are developed together on `main`. Routes use `/api/`
without a version segment; there is no published external-client compatibility
or deprecation policy. Do not infer a stable third-party contract from OpenAPI's
default version field.

When changing request/response behavior, update the affected frontend consumers,
[contract tests](../../tests/test_frontend_backend_contract.py), and behavioral
docs in the same PR. Describe consumer impact and any migration needed for saved
state; exercise the affected page with the backend running. The
[development guide](../development/README.md) owns check commands.
