# Smart Cloud Optimizer

AI-powered AWS cloud cost optimization platform. Collects real AWS data (or generates synthetic data for demo mode), forecasts usage with ML models, and recommends right-sizing and pricing strategies.

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
# Generate synthetic data (no AWS credentials needed)
python -m data_generation.synthetic --output-dir data/synthetic/ --days 365 --seed 42

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
├── config.py                  # Project-wide settings (paths, constants, env)
├── app.py                     # Streamlit entry point (stub)
├── requirements.txt
│
├── aws_collector/             # AWS data collection pipeline
│   ├── config.py              # boto3 client configuration
│   ├── collector_runner.py    # Main orchestrator
│   ├── cost_collector.py      # Cost Explorer data
│   ├── cw_collector.py        # CloudWatch metrics
│   ├── pricing_collector.py   # AWS Pricing API
│   ├── pricing_constants.py   # Pricing lookup constants
│   ├── ec2_collector.py       # EC2/EBS inventory
│   ├── collect_cloudfront.py  # CloudFront collector
│   ├── collect_nat_gateways.py# NAT Gateway collector
│   ├── collect_load_balancers.py # ALB/NLB collector
│   ├── date_utils.py          # Month-range utilities
│   ├── ml_utils.py            # ML data preparation
│   └── main.py                # CLI entry point
│
├── data_generation/           # Synthetic data generation
│   └── synthetic.py           # Generates realistic AWS data
│
├── ai_module/                 # AI recommendation engine (stub)
├── ml_engine/                 # ML forecasting models (stub)
├── optimizer/                 # Cost optimization logic (stub)
├── storage/                   # Data persistence layer (stub)
├── dashboard/                 # Streamlit dashboard (stub)
│
├── data/
│   ├── synthetic/             # Generated demo data (committed)
│   └── real/                  # Real AWS data (gitignored)
│
└── tests/                     # Unit tests
    ├── test_config.py
    ├── test_date_utils.py
    ├── test_ml_utils.py
    └── test_synthetic.py
```

## Architecture

```
                ┌─────────────────────────────┐
                │     aws_collector/          │
                │  (Cost, Metrics, Pricing,   │
                │   Inventory collectors)      │
                └──────────┬──────────────────┘
                           │ CSV files
                           ▼
┌──────────────┐    ┌─────────────┐    ┌───────────────┐
│ data_generation│   │  data/       │    │  ml_engine/   │
│ (synthetic.py) │──▶│  (CSV store) │──▶│  (forecasting)│
└──────────────┘    └──────┬──────┘    └───────┬───────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐    ┌───────────────┐
                    │ ai_module/  │    │  optimizer/   │
                    │ (LLM recs)  │    │ (right-sizing)│
                    └──────┬──────┘    └───────┬───────┘
                           │                    │
                           └────────┬───────────┘
                                    ▼
                            ┌──────────────┐
                            │  dashboard/  │
                            │  (Streamlit) │
                            └──────────────┘
```

## Collected Data

### Cost Explorer

- Daily cost breakdown
- Cost by service (EC2, RDS, S3, Lambda, EBS, Data Transfer)
- Cost by usage type
- Cost anomaly detection

### CloudWatch Metrics

| Service     | Metrics                                                        |
|-------------|----------------------------------------------------------------|
| EC2         | CPUUtilization, NetworkIn/Out, DiskReadOps/WriteOps            |
| EBS         | VolumeReadBytes/WriteBytes, VolumeIdleTime, ConsumedRWOps      |
| Lambda      | Invocations, Duration, Errors                                  |
| RDS         | CPUUtilization, FreeStorageSpace, DatabaseConnections          |
| S3          | BucketSizeBytes, NumberOfObjects                               |
| CloudFront  | Requests, BytesDownloaded/Uploaded, CacheHitRate, ErrorRate    |
| NAT Gateway | BytesProcessed, ActiveConnectionCount                          |
| ALB         | RequestCount, HTTPCode_ELB_4XX/5XX_Count                       |
| NLB         | ProcessedBytes, NewFlowCount                                   |

### Pricing

- EC2 On-Demand, Reserved (1yr/3yr), Spot
- S3 storage classes (Standard, Standard-IA, Glacier)
- Lambda compute pricing
- RDS instance pricing

All data is saved as **consolidated CSV files** — one file per service, append-only, with deduplication.

## Configuration

| Variable         | Default       | Description                        |
| ---------------- | ------------- | ---------------------------------- |
| `DEMO_MODE`      | `true`        | Use synthetic data instead of AWS  |
| `AWS_REGION`     | `us-east-1`   | Default AWS region                 |
| `OPENAI_API_KEY` | —             | OpenAI key for AI recommendations  |
| `OPENAI_MODEL`   | `gpt-4o-mini` | Model for AI module                |

See [config.py](config.py) for all settings.

## Requirements

- `boto3` — AWS SDK
- `pandas`, `numpy` — Data processing
- `matplotlib` — Visualization
- `pytest` — Testing

For real data collection, AWS credentials need these IAM permissions:
`ce:GetCostAndUsage`, `ce:GetAnomalies`, `cloudwatch:GetMetricStatistics`,
`ec2:Describe*`, `pricing:GetProducts`, `rds:Describe*`,
`lambda:ListFunctions`, `s3:ListBuckets`, `sts:GetCallerIdentity`,
`elasticloadbalancing:Describe*`, `cloudfront:ListDistributions`.
