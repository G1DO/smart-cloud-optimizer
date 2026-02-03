# Smart Cloud Optimizer

AI-powered AWS cloud cost optimization platform. Collects real AWS data (or generates synthetic data for demo mode), forecasts usage with ML models, and recommends right-sizing and pricing strategies.

All data is stored in a single SQLite database (`data/cloud_optimizer.db`) accessed through the `storage.db` module.

## Quick Start

### Prerequisites

- Python 3.12+
- AWS credentials (for real data collection)

### Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Demo Mode (synthetic data)

```bash
# Generate synthetic data (writes to data/cloud_optimizer.db)
python -m data_generation.synthetic --days 365 --seed 42

# Run tests
python -m pytest tests/ -v
```

### Real Data Collection

```bash
# Requires configured AWS credentials
python -m aws_collector.main
```

## Project Structure

```
cloud-gp/
├── config.py                  # Project-wide settings (paths, DB_PATH, env)
├── app.py                     # Streamlit entry point (stub)
├── requirements.txt
│
├── aws_collector/             # AWS data collection pipeline
│   ├── config.py              # boto3 client configuration
│   ├── runner.py              # Thin orchestrator
│   ├── metrics.py             # CloudWatch helpers + metric maps
│   ├── transforms.py          # Data transformation helpers
│   ├── pricing_constants.py   # Pricing lookup constants
│   ├── main.py                # CLI entry point
│   └── collectors/            # Service collectors (11 files)
│       ├── base.py            # BaseCollector abstract class
│       ├── ec2.py, rds.py, lambda_.py, s3.py
│       ├── dynamodb.py, elasticache.py, ecs.py
│       ├── nat_gateway.py, elb.py
│       ├── cost.py            # Cost Explorer
│       └── pricing.py         # AWS Pricing API
│
├── data_generation/           # Synthetic data generation
│   └── synthetic.py           # Generates realistic AWS data into DB
│
├── storage/                   # Data persistence layer
│   └── db.py                  # SQLite gateway (30 tables, insert_*/get_* API)
│
├── ml_engine/                 # ML forecasting models
│   └── data_prep.py           # Data loading & feature engineering from DB
│
├── ai_module/                 # AI recommendation engine (stub)
├── optimizer/                 # Cost optimization logic (stub)
├── dashboard/                 # Streamlit dashboard (stub)
│
├── data/
│   ├── cloud_optimizer.db     # SQLite database (all data)
│
├── documentation/             # Detailed docs → start with INDEX.md
│
└── tests/
    ├── test_config.py
    ├── test_date_utils.py
    ├── test_storage.py
    └── test_synthetic.py
```

## Architecture

```
data_generation/synthetic.py ──┐
  (demo mode)                  │
                               ├──> storage.db.insert_*() ──> SQLite DB
aws_collector/                 │         │
  (real AWS)                ───┘         ├──> ml_engine   (reads via storage.db.get_*())
                                         ├──> optimizer   (reads via storage.db.get_*())
                                         ├──> ai_module   (reads via storage.db.get_*())
                                         └──> dashboard   (reads via storage.db.get_*())
```

All tables are keyed by `user_id` -- each AWS account's data is isolated.

## Collected Data

### Cost Explorer

- Daily total cost per user
- Cost by service (EC2, RDS, S3, Lambda, EBS, DynamoDB, ElastiCache, ECS, NATGateway, ELB)
- Cost by service and region

### CloudWatch Metrics

| Service       | Metrics                                                        |
|---------------|----------------------------------------------------------------|
| EC2           | CPUUtilization, NetworkIn/Out, DiskRead/WriteOps               |
| EBS           | ReadOps/WriteOps, ReadBytes/WriteBytes, IdleTime               |
| RDS           | CPUUtilization, ReadIOPS/WriteIOPS, Connections, FreeStorage   |
| ElastiCache   | CPUUtilization, Memory, Connections, CacheHits/Misses          |
| ECS           | CPUUtilization, MemoryUtilization, TaskCount                   |
| Lambda        | Invocations, Duration, Errors, Throttles, MemoryUsed           |
| DynamoDB      | ConsumedRCU/WCU, ThrottledRequests                             |
| S3            | BucketSizeBytes, NumberOfObjects                               |
| NAT Gateway   | BytesIn/Out, PacketsIn/Out, ActiveConnections                  |
| ELB/ALB       | RequestCount, HTTP 2xx/3xx/4xx/5xx, ProcessedBytes             |

### Pricing

- EC2 On-Demand, Reserved (1yr/3yr), Spot
- RDS instance pricing
- ElastiCache instance pricing

All data is stored in **SQLite** via the `storage.db` module (30 tables total).

## Configuration

| Variable         | Default       | Description                        |
| ---------------- | ------------- | ---------------------------------- |
| `DEMO_MODE`      | `true`        | Use synthetic data instead of AWS  |
| `AWS_REGION`     | `us-east-1`   | Default AWS region                 |
| `OPENAI_API_KEY` | --            | OpenAI key for AI recommendations  |
| `OPENAI_MODEL`   | `gpt-4o-mini` | Model for AI module                |

See [config.py](config.py) for all settings.

## Documentation

For detailed documentation, see [documentation/INDEX.md](documentation/INDEX.md).

| Document | Description |
|----------|-------------|
| [QUICKSTART](documentation/QUICKSTART.md) | Setup and first run |
| [ARCHITECTURE](documentation/ARCHITECTURE.md) | System design |
| [MODULES](documentation/MODULES.md) | File-by-file breakdown |
| [DATA_SCHEMAS](documentation/DATA_SCHEMAS.md) | Database tables |
| [STORAGE_API](documentation/STORAGE_API.md) | Storage function reference |

## Requirements

- `boto3` -- AWS SDK
- `pandas`, `numpy` -- Data processing
- `prophet`, `statsmodels`, `pmdarima` -- ML forecasting
- `pulp` -- Optimization (MILP)
- `openai` -- AI recommendations
- `streamlit`, `plotly` -- Dashboard
- `matplotlib` -- Visualization
- `pytest`, `pytest-cov` -- Testing

For real data collection, AWS credentials need these IAM permissions:
`ce:GetCostAndUsage`, `ce:GetAnomalies`, `cloudwatch:GetMetricStatistics`,
`ec2:Describe*`, `pricing:GetProducts`, `rds:Describe*`,
`lambda:ListFunctions`, `s3:ListBuckets`, `sts:GetCallerIdentity`,
`elasticloadbalancing:Describe*`.
