# Configuration

All settings, environment variables, and operational modes.

---

## Two Config Files

The project has two separate config files with no overlap:

| File | Scope | What it controls |
| --- | --- | --- |
| `config.py` (root) | Project-wide | Paths, constants, env vars, ML settings, logging |
| `aws_collector/config.py` | AWS only | boto3 session, service clients, region discovery |

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `DEMO_MODE` | `true` | `true` = use sample data, `false` = connect to real AWS |
| `AWS_REGION` | `us-east-1` | Default AWS region |
| `AWS_ACCOUNT_ID` | `SYNTHETIC-001` | Account ID (overridden automatically in real mode) |
| `OPENAI_API_KEY` | (empty) | OpenAI API key for the AI recommendation module |
| `OPENAI_MODEL` | `gpt-4o-mini` | Which OpenAI model to use |

Set these in a `.env` file or export them before running.

---

## Modes

### Demo Mode (`DEMO_MODE=true`)

- No AWS credentials needed
- Sample data must be generated first: `python -m data_generation.synthetic`
- Data is read from SQLite DB (`data/cloud_optimizer.db`)
- All modules (ML, AI, optimizer, dashboard) work identically

### Real Mode (`DEMO_MODE=false`)

- Requires configured AWS credentials (`~/.aws/credentials` or env vars)
- Collector runs against live AWS APIs
- Needs IAM permissions: `ce:GetCostAndUsage`, `ce:GetAnomalies`, `cloudwatch:GetMetricStatistics`, `ec2:Describe*`, `pricing:GetProducts`, `rds:Describe*`, `lambda:ListFunctions`, `s3:ListBuckets`, `sts:GetCallerIdentity`, `elasticloadbalancing:Describe*`

### How mode switching works

Both modes write to the same SQLite database through `storage.insert_*()`. Downstream modules read via `storage.get_*()` and don't care which source produced the data. The `DEMO_MODE` flag controls whether `aws_collector` attempts real AWS connections.

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
| `SEASONALITY_PERIOD` | `7` | Weekly seasonality cycle |

### Optimization

| Constant | Value | Description |
| --- | --- | --- |
| `DEFAULT_BUDGET_CAP` | `5000.0` | Monthly budget constraint (USD) |
| `SPOT_RELIABILITY` | `False` | Whether to trust Spot instances for critical workloads |

### Supported Services

```python
SUPPORTED_SERVICES = [
    "ec2", "rds", "lambda", "s3", "ebs",
    "nat_gateway", "alb", "nlb",
]
```

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

Configured via `setup_logging()` in root `config.py`:

```text
Format: %(asctime)s | %(name)s | %(levelname)s | %(message)s
Example: 2025-06-15 14:30:00 | aws_collector.cost_collector | INFO | Fetched daily costs for 2025-05
```

Every module uses `logger = logging.getLogger(__name__)`. No `print()` calls anywhere.
