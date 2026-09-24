# Configuration

Environment variables, constants, and operational modes. The separate
[web runtime settings](../architecture/README.md#runtime-settings) are saved preferences;
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
| `AWS_REGION` | `us-east-1` | Shared display value in legacy Streamlit Settings; does not configure boto3 sessions |
| `AWS_ACCOUNT_ID` | `SYNTHETIC-001` | Legacy constant; the collector gets the active account from STS |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | (unset) | boto3 credentials for CLI collection or the principal assuming a legacy role; web connections use stored keys |
| `AWS_DEFAULT_REGION` | (unset locally; `us-east-1` in Compose) | Region for default boto3 sessions; web connections pass their own region |
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

The frontend uses `frontend/.env.local`; Compose builds it with
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in
[docker-compose.yml](../../docker-compose.yml). This URL must be reachable from the
browser, and changing it requires rebuilding the frontend. Templates:
[local backend](../../.env.example), [Docker](../../.env.docker.example), and
[frontend](../../frontend/.env.local.example). The Next.js UI currently sends no
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
  backend stores them server-side and syncs using `AWSConfig.from_keys()`.
  Testing is separate from saving; see
  [Connection identity and verification](../architecture/README.md#connection-identity-and-verification).
- Legacy Streamlit connections use IAM role ARNs. The collector also supports
  these stored connections through `AWSConfig.from_role()`.
- STS identity resolution alone does not establish permission to collect data.
  The service reads are defined by [AWSConfig](../../aws_collector/config.py) and
  the [collectors](../../aws_collector/collectors); the repository does not ship a
  complete IAM policy. Check backend logs for denied collection calls.

### How mode switching works

Demo and connected-account data share SQLite. The web UI selects a workspace;
`DEMO_MODE=false` is not required to connect AWS through FastAPI. HTTP endpoints
trust the supplied user ID, so the client login screen does not enforce data
authorization. See the [security notes](../security/README.md).

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
| `DEFAULT_COLLECTION_MONTHS` | `12` | Declared default; the runner, CLI, and sync route currently specify 12 independently |
| `DEFAULT_SYNTHETIC_DAYS` | `365` | Days of sample data to generate |
| `API_TIMEOUT` | `30` | Displayed in legacy Settings; not passed to boto3 clients |
| `MAX_RETRIES` | `3` | Displayed in legacy Settings; not passed to boto3 clients |
| `CHUNK_SIZE` | `100` | Declared but unused by collection/storage |

The collector does not apply these timeout/retry constants; its clients use
boto3's resolved configuration. Changing these constants does not change AWS
request timeouts, retries, or batching.

### ML

| Constant | Value | Description |
| --- | --- | --- |
| `FORECAST_HORIZON_DAYS` | `30` | Displayed in legacy Settings; HTTP requests and model methods define their own horizons |
| `MIN_TRAINING_DAYS` | `30` | Legacy Streamlit forecast gate; the HTTP router independently requires 30 observations |
| `COLD_START_DAYS` | `30` | Days of cost data needed for the legacy Streamlit Home dashboard |
| `SEASONALITY_PERIOD` | `7` | Displayed in legacy Settings; forecasters define their own seasonality |

The Streamlit Home page shows its questionnaire or saved AI recommendations while
fewer than 30 days of cost data are available. It shows collection progress after
the first day of data; accounts with no data do not see an empty progress bar.

### Optimization

| Constant | Value | Description |
| --- | --- | --- |
| `DEFAULT_BUDGET_CAP` | `5000.0` | Monthly LP budget, applied separately to EC2 and RDS; see [optimizer](../architecture/engines/optimizer.md) |
| `SPOT_RELIABILITY` | `False` | Displayed in legacy Settings; not consumed by the optimizer |

### Supported Services

See the current constants in [cloud_optimizer/config.py](../../cloud_optimizer/config.py).
The optimizer's own service-filter names are defined by `ALL_SERVICES` in
[optimizer/engine.py](../../optimizer/engine.py).

---

## AWS Collector Config

`aws_collector/config.py` constructs session-specific `AWSConfig` instances.
`get_config()` and `init_config()` also expose a shared instance for default
callers; `from_keys()` and `from_role()` construct separate connection instances.

```text
AWSConfig
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
