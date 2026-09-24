# Smart Cloud Optimizer (OptiCloud)

An AWS cost-analysis and recommendation application: a Next.js dashboard calls a
FastAPI backend for collection, forecasting, anomaly detection, and optimization.
It recommends changes; it does not apply them to AWS.

**Use this build on a single-user local machine with synthetic data.** The HTTP
API trusts client-supplied identities and stored AWS keys are plaintext. Read the
[security boundaries](docs/security/README.md) before connecting an account.

Application development targets **`main`**. GitHub's default
`release/ccpe-v1.0` is a separate paper software artifact; clone `main` explicitly:

```bash
git clone --branch main https://github.com/G1DO/smart-cloud-optimizer.git
cd smart-cloud-optimizer
```

[Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111)
owns project intent and decisions. Start with the
[technical documentation](docs/README.md), [contribution guide](CONTRIBUTING.md),
or [historical thesis archive](docs-gp/README.md).

## Prerequisites

Python 3.12+, Node.js 20.9+, npm, and Git for manual setup; Docker with Compose
for the container setup. Python dependencies are in [requirements.txt](requirements.txt),
and frontend dependencies/scripts in [package.json](frontend/package.json) and
its committed lockfile. The Python image uses 3.12; the frontend uses Next.js 16,
React 19, and TypeScript.

## Quick start

### Option A — Docker (simplest)

Runs the stack with the demo SQLite DB baked into the backend image. Published
ports bind to `127.0.0.1`. Exploring stored demo data needs no external credentials;
Gemini-backed recommendations require an API key.

```bash
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Backend health | http://localhost:8000/health |

Add the optional legacy Streamlit dashboard (the `full` profile reuses the backend image):

```bash
docker compose --profile full up --build   # adds Streamlit on http://localhost:8501
```

To set env vars (e.g. `GOOGLE_API_KEY`), copy the template and edit it:

```bash
cp .env.docker.example .env
```

Notes:
- The DB lives in a **named volume** `optimizer-data` (not a host bind mount). The destructive `docker compose down -v` removes the database volume; the next start seeds it again from the image. Runtime settings have a separate lifetime described in [local operations](docs/operations/local-runtime.md#runtime-settings-recovery).
- `NEXT_PUBLIC_API_BASE_URL` is a frontend **build** arg (Next.js inlines it into the browser bundle), so it must be host-reachable (`http://localhost:8000`) — never the in-network service name `backend`.

### Option B — Manual (backend + frontend)

Commands below are for **macOS/Linux**. On **Windows PowerShell**, swap `source venv/bin/activate` for `.\venv\Scripts\Activate.ps1` and `cp` for `Copy-Item`.

**1. Backend** (from the repo root):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional: only needed for AI / real AWS
uvicorn backend_api.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health: http://127.0.0.1:8000/health · API docs: http://127.0.0.1:8000/docs

**2. Frontend** (second terminal):

```bash
cd frontend
npm ci
cp .env.local.example .env.local
npm run dev -- --hostname 127.0.0.1  # http://localhost:3000
```

> Run Python commands from the repo root with the venv active — `cloud_optimizer` and the other application packages resolve from there.

## First use

Open http://localhost:3000 and choose **Try Demo Mode** to view the existing
`aws-SYNTHETIC-001` workspace. New registrations begin with empty dashboards.
**Account Settings → Connections** can test/save AWS keys and start a sync;
[testing, saving, and workspace selection are distinct](docs/architecture/README.md#connection-identity-and-verification).
Collection replaces prior account data incrementally, so read the
[data pipeline](docs/architecture/data-pipeline.md) before syncing.

Forecasting runs from the Forecasts page or HTTP API; the ML CLI is a placeholder.
Use the [optimizer guide](docs/architecture/engines/optimizer.md#usage) for a
command-line experiment on a disposable database copy.

## Develop and maintain

- [Development checks](docs/development/README.md): Python tests, frontend lint/build, and contract verification.
- [Architecture](docs/architecture/README.md): components, identity, persistence, and engine boundaries.
- [API contracts](docs/api/http.md) and [configuration](docs/reference/configuration.md): generated reference and active inputs.
- [Local operations](docs/operations/local-runtime.md): diagnostics, data preservation, and recovery.
- [Security](docs/security/README.md) and [vulnerability reporting](SECURITY.md): current trust limits and reporting route.

Keep runtime data, credentials, and `.env` files out of commits. Environment
examples and dependency manifests/lockfiles are tracked for reproducible setup.
