# Configuration

Environment variables, constants, and operational modes. The separate
[web runtime settings](ARCHITECTURE.md#runtime-settings) are saved preferences;
they do not currently configure the engines or collector.

---

## Two Config Files

The project has two separate config files with no overlap:

| File | Scope | What it controls |
| --- | --- | --- |
| `cloud_optimizer/config.py` | Project-wide | Paths, constants, env vars, ML settings, logging |
| `aws_collector/config.py` | AWS only | boto3 session, service clients, region discovery |

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `DEMO_MODE` | `true` | Legacy Streamlit status label; does not select data or control collection |
| `AWS_REGION` | `us-east-1` | Default AWS region |
| `AWS_ACCOUNT_ID` | `SYNTHETIC-001` | Account ID (overridden automatically in real mode) |
| `OPENAI_API_KEY` | (empty) | OpenAI API key (legacy, unused) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model (legacy, unused) |
| `GOOGLE_API_KEY` | (empty) | Google API key for AI recommendations (Gemini) |
| `GOOGLE_MODEL` | `gemini-2.5-flash` | Google Gemini model for AI module |
| `ONBOARDING_API_TOKEN` | (empty) | Optional `X-API-Token` gate on `POST /api/ai-onboarding/generate` |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Frontend backend URL, embedded at build time |

Set backend variables in the repository-root `.env` file or export them before running.
`cloud_optimizer/config.py` resolves that file and the database path relative to
the repository root, independently of the current working directory. Existing
environment variables take precedence over `.env` values.

The frontend uses `frontend/.env.local`; Docker uses build arguments for its
public API URL. See the [README configuration table](../README.md#configuration)
and the checked-in environment templates. The Next.js UI currently sends no
`X-API-Token`; enabling the optional onboarding gate requires clients to supply it.

---

## Modes

### Demo Mode (click "Try Demo Mode" on login screen)

- No AWS credentials needed
- Database ships with pre-loaded synthetic data
- The TypeScript UI selects the `aws-SYNTHETIC-001` workspace
- Gemini-backed features still require a valid API key

### Real Mode (register + connect AWS account in Settings)

- The Next.js form accepts access keys (and an optional session token). The
  backend verifies them through STS, stores them server-side, and syncs using
  `AWSConfig.from_keys()`.
- Legacy Streamlit connections use IAM role ARNs. The collector also supports
  these stored connections through `AWSConfig.from_role()`.
- Needs IAM permissions: `ce:GetCostAndUsage`, `ce:GetAnomalies`, `cloudwatch:GetMetricStatistics`, `ec2:Describe*`, `pricing:GetProducts`, `rds:Describe*`, `lambda:ListFunctions`, `s3:ListBuckets`, `sts:GetCallerIdentity`, `elasticloadbalancing:Describe*`

### How mode switching works

Demo and connected-account data share SQLite. The web UI selects a workspace;
`DEMO_MODE=false` is not required to connect AWS through FastAPI. HTTP endpoints
trust the supplied user ID, so the client login screen does not enforce data
authorization. See the [security notes](../README.md#known-limitations--security-notes).

---

## Constants

### Paths

| Constant | Value | Description |
| --- | --- | --- |
| `PROJECT_ROOT` | repo root | Base directory |
| `DATA_DIR` | `data/` | Parent data directory |
| `DB_PATH` | `data/cloud_optimizer.db` | SQLite database path |

### Collection

| Constant | Value | Description |
| --- | --- | --- |
| `DEFAULT_COLLECTION_MONTHS` | `12` | How many months of history to collect |
| `DEFAULT_SYNTHETIC_DAYS` | `365` | Days of sample data to generate |
| `API_TIMEOUT` | `30` | AWS API call timeout (seconds) |
| `MAX_RETRIES` | `3` | Retry count for failed API calls |
| `CHUNK_SIZE` | `100` | Batch size for bulk operations |

### ML

| Constant | Value | Description |
| --- | --- | --- |
| `FORECAST_HORIZON_DAYS` | `30` | How far ahead to forecast |
| `MIN_TRAINING_DAYS` | `30` | Minimum data needed for training |
| `COLD_START_DAYS` | `30` | Days of cost data needed for the legacy Streamlit Home dashboard |
| `SEASONALITY_PERIOD` | `7` | Weekly seasonality cycle |

The Streamlit Home page shows its questionnaire or saved AI recommendations while
fewer than 30 days of cost data are available. It shows collection progress after
the first day of data; accounts with no data do not see an empty progress bar.

### Optimization

| Constant | Value | Description |
| --- | --- | --- |
| `DEFAULT_BUDGET_CAP` | `5000.0` | Monthly LP budget, applied separately to EC2 and RDS; see [optimizer](optimizer.md) |
| `SPOT_RELIABILITY` | `False` | Whether to trust Spot instances for critical workloads |

### Supported Services

See the current constants in [cloud_optimizer/config.py](../cloud_optimizer/config.py).
The optimizer's own service-filter names are defined by `ALL_SERVICES` in
[optimizer/engine.py](../optimizer/engine.py).

---

## AWS Collector Config

`aws_collector/config.py` manages boto3 clients as a singleton:

```text
AWSConfig (singleton)
  ├── session          boto3.Session
  ├── ce               Cost Explorer client
  ├── ec2              EC2 client (default region)
  ├── cloudwatch       CloudWatch client (default region)
  ├── pricing          Pricing client (always us-east-1)
  ├── s3               S3 client
  ├── account_id       From STS
  └── regions          From ec2.describe_regions()
```

Regional clients are created on-demand via `get_ec2_client(region)`, `get_rds_client(region)`, `get_lambda_client(region)`, `get_cloudwatch_client(region)`.

---

## Logging

Configured via `setup_logging()` in `cloud_optimizer/config.py`:

```text
Format: %(asctime)s | %(name)s | %(levelname)s | %(message)s
Example: 2025-06-15 14:30:00 | aws_collector.cost_collector | INFO | Fetched daily costs for 2025-05
```

Modules generally use `logger = logging.getLogger(__name__)`; CLI entry points
also print summaries directly.
