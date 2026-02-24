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

The project runs in **demo mode** by default (pre-loaded synthetic data, no AWS credentials needed).

To configure for real AWS data, export these before running:

```bash
# Required only for real AWS data collection
export AWS_REGION=us-east-1
export GOOGLE_API_KEY=your-key-here  # For AI recommendations (Gemini)
```

## 3. Launch the dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501` with a **login screen**:

- **Login** -- Sign in with email and password
- **Register** -- Create a new account (password hashed with HMAC-SHA256)
- **Try Demo Mode** -- Explore with pre-loaded synthetic data (no account required)

After authentication, the sidebar shows 5 pages: Home, Costs, Forecasts, Recommendations, Settings. An **account switcher** in the sidebar lets you select which AWS account to view.

## 4. Connecting an AWS account

After registering, go to **Settings** and use the "Add AWS Account" form:

1. Enter your AWS Account ID and IAM Role ARN
2. Click "Test Connection" to verify access
3. Click "Add Account" to save

The role must allow the permissions listed in the README (Cost Explorer, CloudWatch, EC2, etc.).

## 5. CLI tools

**Run optimizer** (generates cost-saving recommendations):

```bash
python -m optimizer --user-id aws-SYNTHETIC-001
```

**Run ML forecasting** (placeholder -- use the dashboard Forecasts page instead):

```bash
python -m ml_engine --user-id aws-SYNTHETIC-001
```

## 6. Run tests

```bash
pytest
```
