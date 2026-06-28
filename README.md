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
```

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

Run optimizer and forecasting modules manually:

```bash
python -m optimizer --user-id aws-SYNTHETIC-001
python -m ml_engine --user-id aws-SYNTHETIC-001
```

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

## Git Notes

Do not commit real secrets. The repository ignores `.env`, `.env.local`, virtual environments, `node_modules`, Next.js build output, and SQLite runtime files.

The files that should be committed for reproducible setup are:

- `requirements.txt`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.env.example`
- `frontend/.env.local.example`

