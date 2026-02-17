# Smart Cloud Optimizer

AI-powered AWS cloud cost optimization platform. Collects real AWS data (or uses open-source datasets for demo mode), forecasts usage with ML models, and recommends right-sizing and pricing strategies.

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

### Demo Mode (sample data)

```bash
# Load sample data into database (based on open-source datasets)
python -m data_generation.synthetic --days 365 --seed 42

# Launch the dashboard
streamlit run app.py

# Run tests
python -m pytest tests/ -v
```

### CLI Tools

```bash
# Run optimizer (generates cost-saving recommendations)
python -m optimizer --user-id aws-SYNTHETIC-001

# Run ML forecasting
python -m ml_engine --user-id aws-SYNTHETIC-001
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
├── app.py                     # Streamlit entry point (multi-page routing)
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
├── data_generation/           # Sample data generation
│   └── synthetic.py           # Generates sample AWS data into DB
│
├── storage/                   # Data persistence layer
│   └── db.py                  # SQLite gateway (30 tables, insert_*/get_* API)
│
├── ml_engine/                 # ML forecasting engine
│   ├── data_prep.py           # Data loading & feature engineering from DB
│   ├── anomaly.py             # Anomaly detection (Z-score + IQR)
│   ├── forecaster.py          # 5 forecasting models (Naive, SNaive, ETS, Prophet, SARIMAX)
│   └── evaluator.py           # Cross-validation & model comparison
│
├── ai_module/                 # AI recommendation engine (Google Gemini)
│   ├── guided_questions.py    # 9-question requirements gathering
│   ├── prompt_builder.py      # Structured LLM prompt generation
│   ├── recommender.py         # Gemini 2.5 Flash API integration
│   └── ui.py                  # Streamlit recommendation display
│
├── optimizer/                 # Cost optimization (LP solver + rules)
│   ├── compute_lp.py          # PuLP MILP for EC2/RDS right-sizing
│   ├── rules.py               # 8 heuristic checks across services
│   ├── engine.py              # Orchestrator (dedup + DB write)
│   └── __main__.py            # CLI entry point
│
├── dashboard/                 # Streamlit dashboard (6 pages)
│   ├── components.py          # Reusable charts, cards, formatters
│   ├── home.py                # Overview metrics, top recommendations
│   ├── costs.py               # Cost analysis with charts + date range
│   ├── forecasts.py           # ML predictions + model comparison
│   ├── recommendations.py     # Savings cards, filters, sorting
│   └── settings.py            # User config, parameters, demo toggle
│
├── data/
│   └── cloud_optimizer.db     # SQLite database (all data)
│
├── documentation/             # Detailed docs → start with INDEX.md
│
└── tests/
    ├── test_config.py
    ├── test_date_utils.py
    ├── test_storage.py
    ├── test_synthetic.py
    ├── test_ml_utils.py
    ├── test_optimizer.py
    └── test_ai_module.py
```

## Architecture

```
data_generation/synthetic.py ──┐
  (open-source + generated)    │
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
| `DEMO_MODE`      | `true`        | Use sample data instead of AWS     |
| `AWS_REGION`     | `us-east-1`   | Default AWS region                 |
| `OPENAI_API_KEY` | --            | OpenAI key (legacy, unused)        |
| `OPENAI_MODEL`   | `gpt-4o-mini` | OpenAI model (legacy, unused)      |
| `GOOGLE_API_KEY` | --            | Google API key for AI recommendations |
| `GOOGLE_MODEL`   | `gemini-2.5-flash` | Gemini model for AI module    |

See [config.py](config.py) for all settings.

## Documentation

For detailed documentation, see [documentation/INDEX.md](documentation/INDEX.md).

| Document | Description |
|----------|-------------|
| [QUICKSTART](documentation/QUICKSTART.md) | Setup and first run |
| [STARTUP](documentation/STARTUP.md) | Dashboard launch and CLI tools |
| [ARCHITECTURE](documentation/ARCHITECTURE.md) | System design |
| [MODULES](documentation/MODULES.md) | File-by-file breakdown |
| [PROJECT_STATUS](documentation/PROJECT_STATUS.md) | What's done, gaps, roadmap |
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
