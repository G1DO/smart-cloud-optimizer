# Legacy Streamlit Startup

The primary TypeScript/FastAPI application starts with the
[README quick start](../README.md#quick-start). This guide covers the optional
legacy Python UI in `dashboard/`.

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

For real collection, configure boto3 credentials for the principal that assumes
the connection's role; see [Configuration](CONFIGURATION.md#environment-variables).
Set the default boto3 region before running:

```bash
export AWS_DEFAULT_REGION=us-east-1
```

For AI recommendations, separately set `GOOGLE_API_KEY` in the environment or
root `.env`. Gemini requires this key even when using synthetic data.

## 3. Launch the dashboard

```bash
python -m streamlit run dashboard/app.py
```

Opens at `http://localhost:8501` with a **login screen**:

- **Login** -- Sign in with email and password
- **Register** -- Create a new account (password hashed with PBKDF2-HMAC-SHA256)
- **Try Demo Mode** -- Explore with pre-loaded synthetic data (no account required)

After authentication, the sidebar shows 5 pages: Home, Costs, Forecasts, Recommendations, Settings. An **account switcher** in the sidebar lets you select which AWS account to view.

## 4. Connecting an AWS account

After registering, go to **Settings** and use the "Add AWS Account" form:

1. Enter your AWS Account ID and IAM Role ARN
2. Click "Test Connection" to verify access
3. Click "Add Account" to save

The caller needs `sts:AssumeRole`, and the role needs permissions for the AWS
services being collected. This form tests role access with STS. The primary
Next.js UI instead accepts access keys; see [Configuration](CONFIGURATION.md).

## 5. CLI tools

Use the [optimizer example](optimizer.md#usage) to generate recommendations in a
disposable database copy. Optimization replaces existing recommendations.

Run forecasting from the Forecasts page. The ML CLI is a placeholder that prints
a notice and exits with status 1 when a user ID is supplied.

## 6. Run tests

```bash
python -m pytest tests/ -v
```

See [Development](DEVELOPMENT.md) for the full application checks.
