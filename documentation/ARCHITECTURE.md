# Architecture

The application on `main` uses a TypeScript/Next.js browser UI and a Python
FastAPI backend. The [README diagrams](../README.md#how-it-works) show the runtime
flow. The optional Streamlit UI calls the Python engines directly.

## Boundaries

| Component | Responsibility |
| --- | --- |
| `frontend/` | Next.js routes, client state, Plotly charts, HTTP calls to the backend |
| `backend_api/` | FastAPI routes for auth, connections/sync, costs, dashboard, forecasting, recommendations, settings, and AI onboarding |
| `cloud_optimizer/` | Shared Python configuration, paths, root `.env` loading |
| `storage/` | SQLite schema, migrations, authentication helpers, connection and data APIs |
| `aws_collector/` | boto3 clients and per-service collectors for live AWS data |
| `data_generation/` | Synthetic fixtures and a CLI that seeds SQLite |
| `ml_engine/` | Time-series preparation, forecasting, anomaly detection, evaluation |
| `optimizer/` | Inventory/metrics/pricing-based LP and rule recommendations |
| `ai_module/` | Questionnaire-based recommendations using Gemini |
| `dashboard/` | Optional legacy Streamlit application |

Use the running backend's generated http://localhost:8000/docs for HTTP contracts.
See [Modules](MODULES.md) for implementation entry points and
[Configuration](CONFIGURATION.md) for environment settings.

## Persistence and computation

Most Python components access `data/cloud_optimizer.db` through `storage`.
The forecast router currently opens SQLite directly; recommendations and
connections also execute SQL on storage-created connections. The storage facade
is the preferred shared interface, but it is not an enforced access boundary.
Per-user runtime settings are stored separately; see [Runtime settings](#runtime-settings).

`ensure_schema()` creates missing tables/indexes and adds missing AWS credential
columns for older databases. `create_schema()` is destructive. See
[Storage API](STORAGE_API.md) for transaction ownership and
[Data schemas](DATA_SCHEMAS.md) for table details.

The optimizer reads observed inventory, metrics, and pricing; it does not consume
ML forecast output. Optimization replaces stored recommendations for the selected
user. Forecasting and Gemini recommendations are separate computations. See
[optimizer constraints and usage](optimizer.md) before interpreting savings.

## Data sources

The demo workspace uses existing synthetic data in SQLite. The current tracked
generator creates fixtures for tests and demos; it does not download the research
datasets listed in [Data resources](DATA_RESOURCES.md), and it does not reproduce
the historical committed fixture byte-for-byte.

The Next.js connection form stores access keys in SQLite; see
[connection identity and verification](#connection-identity-and-verification)
for the separate test, save, and workspace-selection behavior. The collector
supports both key-based connections and legacy IAM-role connections. Sync runs
in a background thread, clears the selected account's previous data, then
collects month ranges newest first. See [Data pipeline](DATA_PIPELINE.md) for
write behavior.

## Connection identity and verification

Registration creates a `usr-…` identity. In the primary web flow,
[the connection router](../backend_api/routers/connections.py) saves a connection
under `aws-<account_id>`, the same workspace ID used for collected data. After
save, [the frontend session helper](../frontend/app/lib/session.ts) switches the
stored active identity to that workspace. Web connections are not attached to
the registered `usr-…` identity. The legacy
[Streamlit settings page](../dashboard/settings.py) instead attaches role-based
connections to its authenticated owner and selects an AWS workspace separately.

**Test connection** calls STS to resolve the supplied keys' account. Testing and
saving are separate operations: save resolves the account through STS only when
no account ID is supplied. With a supplied account ID, save validates its format
and stores the connection without rechecking the keys against that account.
A saved connection is therefore not proof of verified AWS access or ownership.
Sync creates an AWS session from the stored credentials and can fail later.

## Trust and operational limits

Passwords use PBKDF2-HMAC-SHA256 with random salts. The HTTP API currently trusts
client-supplied user IDs and issues no authenticated session. Browser identity is
kept in localStorage; `user_id` filtering alone is not authorization. The legacy
Streamlit auth gate uses its own session state.

This build is for localhost development with synthetic data. Stored AWS keys are
plaintext, and the tracked database also contains personal/account metadata.
The [README security notes](../README.md#known-limitations--security-notes)
describe these limits and the optional AI endpoint token guard. Keep credentials
and runtime data out of commits.

## Runtime settings

[backend_api/routers/settings.py](../backend_api/routers/settings.py) stores
per-user preferences in `backend_api/runtime_settings.json`. The settings API
validates and saves them, but engines and the collector do not read that file:
saving a budget, collection interval, retention period, or model preference does
not change their current behavior. Request parameters and Python configuration
remain the active inputs.

The file is local runtime state and is excluded from Git and the backend image
build context, together with temporary/corrupt copies. In Compose only
`/app/data` is on a named volume; runtime settings live in the backend container's
writable layer and are lost on container recreation. Database volume retention
does not preserve them.

Writes replace the file atomically and serialize within one process. A malformed
JSON file is renamed to `runtime_settings.json.corrupt`, after which reads use
defaults until new settings are saved. To recover preferences, stop the backend,
preserve the corrupt copy outside Git, repair or restore valid JSON with the
same user-to-settings mapping, and restart. Repeated malformed reads can replace
the previous `.corrupt` copy; preserve it before attempting recovery.
