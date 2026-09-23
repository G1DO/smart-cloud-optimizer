# Smart Cloud Optimizer (OptiCloud)

An AI-powered AWS cost-optimization platform: a **FastAPI** backend wrapping four engines (cost optimizer, ML forecaster, AI advisor, AWS collector) behind a **Next.js** dashboard. It collects real AWS cost/usage data (or ships synthetic demo data), forecasts spend, detects anomalies, and recommends right-sizing and pricing changes.

> **Demo Mode (default).** The app ships with a pre-loaded synthetic AWS dataset (committed in the demo DB) — no AWS credentials needed. Sign in, or click **Try Demo Mode**, to explore costs, forecasts, anomalies, and recommendations immediately. Real user accounts start with empty dashboards until an AWS account is connected from **Account Settings**.

Technical guides: [documentation index](documentation/INDEX.md),
[development and checks](documentation/DEVELOPMENT.md),
[contributing](CONTRIBUTING.md). Graduation documents and their revision records:
[paper archive](docs-gp/README.md).
[Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111)
owns project intent and decisions. Application PRs target `main`; the GitHub
default `release/ccpe-v1.0` contains the separate paper artifact.

---

## How it works

Three tiers: a browser-side **Next.js UI (:3000)** talks over HTTP/JSON to the **FastAPI backend (:8000)**. Engines and the AWS collector use the `storage` facade. Some API routes also access SQLite directly; see [Architecture](documentation/ARCHITECTURE.md).

```mermaid
flowchart LR
  Browser["Browser"]
  NextUI["Next.js UI<br/>(port 3000)"]

  subgraph BE["FastAPI backend (port 8000)"]
    API["FastAPI routers<br/>(trust-based user_id)"]
    Storage["storage facade<br/>(shared data API)"]
    Optimizer["optimizer<br/>(PuLP right-sizing + rules)"]
    ML["ml_engine<br/>(forecasts / anomalies)"]
    AImod["ai_module<br/>(Gemini advisor)"]
    Collector["aws_collector<br/>(boto3 pipeline)"]
  end

  DB[("SQLite DB<br/>data/cloud_optimizer.db")]
  Synthetic["data_generation.synthetic<br/>(demo seed)"]
  AWS["AWS<br/>(Cost Explorer / CloudWatch via boto3)"]
  Gemini["Google Gemini<br/>(AI recommendations)"]

  Browser --> NextUI
  NextUI -->|"HTTP / JSON"| API
  API --> Storage
  API --> Optimizer
  API --> ML
  API --> AImod
  API --> Collector
  Optimizer --> Storage
  ML --> Storage
  AImod --> Storage
  Collector --> Storage
  Storage --> DB
  API -->|"route-specific SQL"| DB

  Collector -. "real mode" .-> AWS
  AImod -. "AI calls" .-> Gemini
  Synthetic -. "demo mode" .-> Storage

  classDef ext stroke-dasharray:5 5,stroke:#888,color:#444;
  class AWS,Gemini,Synthetic ext;
```

*Next.js calls FastAPI, whose routes call the engines and query SQLite. AWS and Gemini are optional external integrations; the synthetic generator provides demo fixtures.*

**Legend.** Solid arrows show calls and data access; dashed edges show optional AWS, Gemini, and demo-seeding paths. Runtime settings also persist separately in `backend_api/runtime_settings.json`.

When the UI opens a dashboard page, it fetches a single JSON endpoint keyed by a plain `user_id` query param (no token — see [Security Notes](#known-limitations--security-notes)):

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Next.js UI (port 3000)
    participant API as FastAPI router (port 8000)
    participant ST as storage facade
    participant DB as SQLite + engines

    U->>UI: Open dashboard page, e.g. /dashboard/costs
    UI->>API: GET /api/costs with user_id query param (no token, trust-based)
    API->>ST: ensure_schema then get_* reads
    ST->>DB: SELECT from data/cloud_optimizer.db
    Note over API,DB: On compute - ml_engine forecast, optimizer.optimize, ai_module Gemini
    DB-->>API: rows as list of dicts
    API-->>UI: JSON payload
    UI-->>U: Render Plotly charts and KPIs
```

*Runtime path of a dashboard page: browser fetch to a FastAPI router keyed by user_id, storage/engine reads from SQLite, JSON back to the Next.js UI, then Plotly charts render.*

---

## Tech stack

| Layer | Choices |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Engines | PuLP (right-sizing LP) · Prophet / statsmodels / pmdarima (forecasts) · Google Gemini via `google-genai` (AI advisor) · boto3 (AWS collector) |
| Data | SQLite (stdlib `sqlite3`, no ORM) at `data/cloud_optimizer.db` |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Plotly, Three.js |
| Packaging | pip + `requirements.txt` (backend) · npm (frontend) · Docker Compose |

**Prerequisites:** Git, Python 3.12+, Node.js 20.9+, npm. *Optional:* AWS access keys for real collection; a Google Gemini API key for AI recommendations.

---

## Quick start

### Option A — Docker (simplest)

Runs the whole stack with the demo SQLite DB baked into the backend image. Defaults to demo mode with no AI key required.

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
- The DB lives in a **named volume** `optimizer-data` (not a host bind mount). The destructive `docker compose down -v` removes the database volume; the next start seeds it again from the image. Runtime settings have a separate lifetime described in [Architecture](documentation/ARCHITECTURE.md#runtime-settings).
- `NEXT_PUBLIC_API_BASE_URL` is a frontend **build** arg (Next.js inlines it into the browser bundle), so it must be host-reachable (`http://localhost:8000`) — never the in-network service name `backend`.

### Option B — Manual (backend + frontend)

Commands below are for **macOS/Linux**. On **Windows PowerShell**, swap `source venv/bin/activate` for `.\venv\Scripts\Activate.ps1` and `cp` for `Copy-Item`.

**1. Backend** (from the repo root):

```bash
python -m venv venv
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
npm run dev                   # http://localhost:3000
```

> Run Python commands from the repo root with the venv active — `cloud_optimizer` and the other application packages resolve from there.

---

## Data & modes

Authentication options in the UI:

- **Login** — existing email + password (passwords hashed with PBKDF2-HMAC-SHA256).
- **Sign Up** — new account; password must be 8+ chars with an uppercase letter, a digit, and a symbol.
- **Try Demo Mode** — opens the synthetic `aws-SYNTHETIC-001` workspace with no registration.

The platform has two **data sources** — synthetic demo data and live AWS collection — but both write through the same `storage` facade into the same SQLite DB:

```mermaid
flowchart TD
    Start["How does data enter the DB?"]
    Start -->|"demo workspace (default)"| Synth["data_generation.synthetic<br/>(seeds the committed demo DB)"]
    Start -->|"connect AWS account, then Sync"| Collector["aws_collector CollectorRunner<br/>(background boto3 sync, 12 months)"]
    AWS["Real AWS account APIs<br/>(Cost Explorer / EC2 / CloudWatch / STS)"] -->|"boto3 pull"| Collector
    Synth -->|"insert_*"| Storage["storage facade<br/>(storage/__init__.py)"]
    Collector -->|"insert_*"| Storage
    Storage --> DB[("SQLite<br/>data/cloud_optimizer.db")]
    DB --> Engines["Engines<br/>(optimizer / ml_engine / ai_module)"]
    Engines --> API["FastAPI backend<br/>(port 8000)"]
    API --> UI["Next.js dashboard UI<br/>(port 3000)"]
```

*Two data-source paths — the synthetic generator (demo) vs live boto3 collection (real connect) — both write through the storage facade into the same SQLite DB, then flow to engines and the UI.*

**Connecting a real AWS account.** From **Account Settings → Connections**, paste AWS access keys. **Test connection** checks access through STS; saving and testing are separate. **Sync** uses stored credentials in a background thread that pulls **12 months** of cost/usage data via `aws_collector`. See [connection identity and verification](documentation/ARCHITECTURE.md#connection-identity-and-verification) for account resolution and workspace ownership. Data is keyed as `aws-<account_id>`; the demo user is `aws-SYNTHETIC-001`.

---

## Commands

| Task | Command |
| --- | --- |
| Run stack (Docker) | `docker compose up --build` |
| Run stack + Streamlit | `docker compose --profile full up --build` |
| Backend (dev) | `uvicorn backend_api.main:app --reload --host 127.0.0.1 --port 8000` |
| Frontend (dev) | `cd frontend && npm run dev` |
| Backend tests (all) | `python -m pytest tests/ -v` |
| Backend tests (one file) | `pytest tests/test_optimizer.py` |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend build | `cd frontend && npm run build` |
| Legacy Streamlit dashboard | `python -m streamlit run dashboard/app.py` → http://localhost:8501 |
| Optimizer (CLI) | [Run on a disposable DB copy](documentation/optimizer.md#usage) |
| Seed synthetic demo data | [Generator and write behavior](documentation/DATA_PIPELINE.md#synthetic-data) |

Notes:
- **Forecasting has no working CLI.** With `--user-id`, `python -m ml_engine` prints a placeholder notice and exits 1. Run forecasts via the dashboard Forecasts page or `GET /api/forecast`.
- The synthetic seeder updates matching target-user rows and global pricing. It leaves unmatched rows in place; use a disposable database for experiments.

---

## Project structure

```text
smart-cloud-optimizer/
  backend_api/        FastAPI app + 8 routers (auth, connections, costs,
                      dashboard, forecast, recommendations, settings, ai-onboarding)
  frontend/           Next.js 16 app (App Router, Plotly charts, Three.js globe)
  storage/            Shared SQLite schema and data API
  aws_collector/      boto3 collection pipeline (CollectorRunner + per-service collectors)
  ml_engine/          Forecasting (Prophet/SARIMAX/ETS/Naive) + anomaly detection
  optimizer/          Cost engine: PuLP right-sizing LP + rule-based heuristics
  ai_module/          Guided questions + Gemini recommendation generation
  dashboard/          Legacy Streamlit dashboard
  data_generation/    Deterministic synthetic-data generator + CLI
  data/               Committed demo SQLite database
  documentation/      Current implementation, development, and reference guides
  docs-gp/            Historical thesis revisions and editing records
  tests/              pytest suite
  cloud_optimizer/    Shared config + root .env loading (config.py)
  dashboard/app.py    Streamlit entry point
  docker-compose.yml  Backend + frontend (+ optional Streamlit) orchestration
  requirements.txt    Python dependencies
```

---

## Configuration

Use the [configuration reference](documentation/CONFIGURATION.md) for environment
variables, active inputs, and legacy display-only constants. Backend configuration
loads the root `.env`; the frontend API URL is embedded at build time. Web runtime
settings are saved preferences, with the limits described in
[Architecture](documentation/ARCHITECTURE.md#runtime-settings).

Templates: [local backend](.env.example), [Docker](.env.docker.example),
and [frontend](frontend/.env.local.example).

---

## Known limitations & security notes

These are deliberate, documented limitations of the current build. The app is intended for **localhost use with synthetic data**.

- **Auth is trust-based — no tokens or sessions.** Login/sign-up verify a PBKDF2-hashed password but issue **no token or session cookie**. Every data and settings endpoint trusts a `user_id` query parameter with **no server-side authorization check**, so any client could read another user's data by supplying their `user_id`. The login route has only an in-process, per-IP throttle (10 failures / 300s → HTTP 429). This is **not safe for multi-tenant or public deployment** — a real deployment must add token/session auth and derive `user_id` server-side, and configure CORS for the chosen credential transport.
- **AWS credentials are stored in plaintext.** The connection form sends AWS access keys to the backend, which persists them **in the SQLite DB in plaintext**. Connection responses omit secret fields and expose only the last 4 chars of the access key id; sync reads credentials server-side. Saving does not always verify AWS access; see [connection identity and verification](documentation/ARCHITECTURE.md#connection-identity-and-verification). Do not point this at a shared or public host with real credentials.
- **The committed demo DB contains real data.** `data/cloud_optimizer.db` ships with the synthetic demo user **plus** a real personal email (PII) and a real AWS account id / IAM role ARN in plaintext. Do not add more real account data to the committed DB.
- **AI onboarding guards.** `POST /api/ai-onboarding/generate` rejects prompts longer than 4000 characters (HTTP 400) and returns HTTP 502 when the upstream Gemini call fails (e.g. `GOOGLE_API_KEY` unset). When `ONBOARDING_API_TOKEN` is set, callers must send a matching `X-API-Token` header; it is off by default so the demo works with no token.
- **Settings are file-backed, not in the DB.** Per-user runtime settings persist to `backend_api/runtime_settings.json`. Reads are always allowed; writes/resets are read-only for demo users and for users without a connected AWS account. Settings are not wired into the engines or collector, and Compose does not persist this file across container recreation; see [runtime settings](documentation/ARCHITECTURE.md#runtime-settings).
- **Frontend auth is client-only.** Session identity lives entirely in browser `localStorage` — there is no Next.js middleware or server-side route protection, so any `/dashboard` route is reachable and falls back to the synthetic demo user.

---

## Git notes

Do not commit real secrets. The repo ignores `.env`, `.env.local`, virtual environments, `node_modules`, and Next.js build output. Commit these for reproducible setup:

- `requirements.txt`
- `frontend/package.json`, `frontend/package-lock.json`
- `.env.example`, `.env.docker.example`, `frontend/.env.local.example`
