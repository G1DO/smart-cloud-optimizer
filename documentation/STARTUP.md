# Startup Guide

## Prerequisites

- Python 3.12+
- pip

## 1. Create virtual environment & install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Environment variables (optional)

The project runs in **demo mode** by default (synthetic data, no AWS credentials needed).

To configure, export these before running:

```bash
# Demo mode (default: true) — set to false for real AWS data
export DEMO_MODE=true

# Required only when DEMO_MODE=false
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012

```

## 3. Launch the dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Pages: Home, Costs, Forecasts, Recommendations, Settings.

## 4. CLI tools

**Run optimizer** (generates cost-saving recommendations):

```bash
python -m optimizer --user-id aws-SYNTHETIC-001
```

**Run ML forecasting** (placeholder — use the dashboard Forecasts page instead):

```bash
python -m ml_engine --user-id aws-SYNTHETIC-001
```

## 5. Run tests

```bash
pytest
```
