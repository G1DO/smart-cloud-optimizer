# Smart Cloud Optimizer

OptiCloud is an AWS cloud cost optimization platform built with a FastAPI backend and a Next.js frontend. It supports authentication, demo data, AWS account connection settings, cost dashboards, forecasts, anomalies, and AI-guided recommendation generation.

Demo Mode loads synthetic AWS cost data so the app can be explored without AWS credentials. Normal user accounts start with empty dashboards until an AWS account is connected from Account Settings.

## Tech Stack

- Backend: Python 3.12, FastAPI, SQLite, pandas, Prophet, statsmodels, PuLP, Google Gemini
- Frontend: Next.js 16, React 19, TypeScript, Plotly, Three.js
- Database: SQLite at `data/cloud_optimizer.db`

## Prerequisites

- Git
- Python 3.12 or higher
- Node.js 20 or higher
- npm
- Optional: AWS credentials or IAM role details for real AWS collection
- Optional: Google Gemini API key for AI recommendation generation

## Clone The Project

```bash
git clone <repository-url>
cd smart-cloud-optimizer
```

## Backend Setup

Create and activate a virtual environment from the project root:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Update `.env` only if AI recommendations or real AWS settings are needed:

```env
GOOGLE_API_KEY=your_google_gemini_api_key_here
GOOGLE_MODEL=gemini-2.5-flash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=SYNTHETIC-001
DEMO_MODE=true
ONBOARDING_API_TOKEN=
```

`DEMO_MODE` defaults to `true` (synthetic demo data); set it to `false` to enable
real AWS collection. `ONBOARDING_API_TOKEN` is optional and empty by default; when
set, the AI onboarding endpoints require a matching `X-API-Token` header.

Start the FastAPI backend:

```bash
uvicorn backend_api.main:app --reload --host 127.0.0.1 --port 8000
```

The backend health check is available at `http://127.0.0.1:8000/health`.

## Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
```

Create the local frontend environment file:

Windows PowerShell:

```powershell
Copy-Item .env.local.example .env.local
```

macOS/Linux:

```bash
cp .env.local.example .env.local
```

Start the Next.js app:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Authentication Modes

- Login: sign in with an existing email and password.
- Sign Up: create a new account. Passwords are stored with PBKDF2-HMAC-SHA256 hashing.
- Try Demo Mode: open a preloaded synthetic AWS workspace without registration.

Demo Mode shows sample costs, forecasts, anomalies, and recommendations. New or existing real accounts show empty dashboard states until AWS account connection data is configured.

## Run with Docker

The whole stack runs with Docker Compose. The committed demo SQLite DB ships
inside the backend image and is bind-mounted from `./data`, so any runtime
changes persist on the host.

Core stack (FastAPI backend + Next.js frontend):

```bash
docker compose up --build
```

Add the legacy Streamlit dashboard (optional `full` profile, reuses the backend
image):

```bash
docker compose --profile full up --build
```

URLs:

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs (health: http://localhost:8000/health)
- Streamlit (full profile only): http://localhost:8501

Configuration is optional — defaults run in demo mode with no AI key. To set
env vars (e.g. `GOOGLE_API_KEY`), copy the template and edit it:

```bash
cp .env.docker.example .env
```

Note: `NEXT_PUBLIC_API_BASE_URL` is a frontend **build** arg (set in
`docker-compose.yml`) because Next.js inlines it into the browser bundle; it
must stay host-reachable (`http://localhost:8000`).

## Useful Commands

Run backend tests:

```bash
python -m pytest tests/ -v
```

Run frontend lint:

```bash
cd frontend
npm run lint
```

Build the frontend:

```bash
cd frontend
npm run build
```

Run the legacy Streamlit dashboard, if needed:

```bash
streamlit run app.py
```

Run the optimizer module manually:

```bash
python -m optimizer --user-id aws-SYNTHETIC-001
```

Forecasting has no working CLI yet: `python -m ml_engine` is a non-functional
placeholder that prints a notice and exits with status 1. Run forecasts via the
dashboard Forecasts page or the FastAPI `GET /api/forecast` endpoint instead.

Generate synthetic demo data into the SQLite database (`config.DB_PATH`):

```bash
python -m data_generation.synthetic --days 365 --user-id aws-SYNTHETIC-001
```

This writes rows for the given `--user-id`; it is intended for a fresh/empty
database. Re-running overwrites that user's existing rows by primary key (it does
not delete other rows).

## Project Structure

```text
smart-cloud-optimizer/
  backend_api/            FastAPI routes and API startup
  frontend/               Next.js app
  storage/                SQLite schema, auth, and data access helpers
  aws_collector/          AWS data collection modules
  ml_engine/              Forecasting and anomaly detection
  optimizer/              Cost optimization rules and LP solver
  ai_module/              Guided questions and Gemini recommendations
  dashboard/              Legacy Streamlit dashboard
  data/                   SQLite database and synthetic data
  tests/                  Backend and data tests
  requirements.txt        Python dependencies
  .env.example            Backend environment template
```

## Known Limitations and Security Notes

These are deliberate, documented limitations of the current demo build, not bugs to
work around. The app is intended for **localhost use with synthetic data**.

- **Auth is client-trust / single-user-demo oriented.** Login and sign-up verify a
  PBKDF2-hashed password but issue **no token or session cookie**. Every backend
  data and settings endpoint trusts a `user_id` query parameter with no server-side
  authorization check, so any client could read another user's data by supplying
  their `user_id`. This is **not safe for multi-tenant or public deployment** — a
  real deployment must add token/session auth and derive `user_id` server-side.
- **AWS account connections are not verified or persisted server-side.** Connection
  details entered in the UI are held client-side only; they are **not** persisted by
  the backend and are **not** verified via `sts:AssumeRole`. The "Connected" status
  is cosmetic in this demo. Real STS verification and server-side persistence are not
  yet implemented.
- **AI onboarding endpoint guards.** The `/api/ai-onboarding/generate` endpoint
  rejects prompts longer than 4000 characters (HTTP 400) and returns HTTP 502 when
  the upstream AI call fails (for example, when `GOOGLE_API_KEY` is unset). Setting
  `ONBOARDING_API_TOKEN` requires callers to send a matching `X-API-Token` header;
  it is off by default so the demo works with no token.

## Git Notes

Do not commit real secrets. The repository ignores `.env`, `.env.local`, virtual environments, `node_modules`, Next.js build output, and SQLite runtime files.

The files that should be committed for reproducible setup are:

- `requirements.txt`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.env.example`
- `frontend/.env.local.example`

