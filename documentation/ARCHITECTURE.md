# Architecture

## What This Project Is

Smart Cloud Optimizer is an AI-powered platform that helps reduce AWS cloud costs. It works in three stages:

1. **Collect** — Gather real AWS data (costs, metrics, pricing, inventory) or use open-source sample data for demo mode
2. **Analyze** — Use ML models to forecast future usage and detect anomalies
3. **Optimize** — Recommend right-sizing instances, switching pricing plans, and eliminating waste

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│   ┌──────────────────┐         ┌──────────────────────┐        │
│   │  AWS Account     │         │  Data Generator        │        │
│   │  (real data)     │         │  (open-source based)   │        │
│   │                  │         │                        │        │
│   │  - Cost Explorer │         │  - Bitbrains VM traces │        │
│   │  - CloudWatch    │         │  - NAB CloudWatch      │        │
│   │  - Pricing API   │         │  - Kaggle pricing      │        │
│   │  - EC2/RDS/S3..  │         │  - Generated for 10 svc│        │
│   └────────┬─────────┘         └───────────┬──────────┘        │
│            │                                │                   │
│            ▼                                ▼                   │
│   ┌──────────────────────────────────────────────┐             │
│   │         storage/db.py  (SQLite gateway)      │             │
│   │                                               │             │
│   │   insert_*() ──> data/cloud_optimizer.db     │             │
│   │   get_*()    <── (30 tables, user_id keyed)  │             │
│   └───────────────────────┬──────────────────────┘             │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                            │
│                                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│   │  ml_engine/   │  │  ai_module/   │  │  optimizer/       │    │
│   │              │  │              │  │                  │    │
│   │  Time-series │  │  LLM-based   │  │  Linear          │    │
│   │  forecasting │  │  instance    │  │  programming     │    │
│   │  (Prophet,   │  │  recommender │  │  cost            │    │
│   │   ARIMA)     │  │  (Gemini)    │  │  minimization    │    │
│   └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │
│          │                 │                    │               │
│          └─────────────────┼────────────────────┘               │
│                            │                                    │
└────────────────────────────┼────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                          │
│                                                                 │
│   ┌──────────────────────────────────────────────┐             │
│   │  dashboard/ (Streamlit)                       │             │
│   │                                               │             │
│   │  - Cost trends and anomaly charts            │             │
│   │  - Instance right-sizing recommendations     │             │
│   │  - Pricing plan comparison                   │             │
│   │  - AI recommendation form                    │             │
│   └──────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## The Two Modes

### Demo Mode (`DEMO_MODE=true`, default)

No AWS credentials needed. The data generator creates sample data based on open-source datasets (Bitbrains VM traces, NAB CloudWatch metrics, Kaggle pricing) supplemented with generated data to cover all 10 AWS services. It mimics a mid-size SaaS startup (~$1,500-$2,500/month AWS bill). This mode lets you demo the full platform without a real AWS account.

```text
data_generation/synthetic.py  ──>  storage.insert_*()  ──>  SQLite DB  ──>  dashboard
```

### Real Mode (`DEMO_MODE=false`)

Connects to a real AWS account via boto3. Collects 12 months of historical data across all enabled regions and writes to the database.

```text
aws_collector/main.py  ──>  storage.insert_*()  ──>  SQLite DB  ──>  dashboard
```

Both modes write to the same SQLite database through `storage.insert_*()`. Downstream modules read via `storage.get_*()` and don't care which source produced the data.

## Module Responsibilities

| Module | Purpose | Status |
| --- | --- | --- |
| `config.py` | Project-wide constants, paths, env vars | Done |
| `aws_collector/` | Real AWS data collection pipeline | Done |
| `data_generation/` | Sample data generator (open-source based) | Done |
| `storage/` | SQLite gateway (30 tables, `insert_*`/`get_*` API) | Done |
| `ml_engine/` | Data prep, anomaly detection, time-series forecasting, evaluation | Done |
| `ai_module/` | LLM-based architecture recommendations (Google Gemini 2.5 Flash) | Done |
| `optimizer/` | Cost minimization via LP (PuLP) + 8 rule-based checks | Done |
| `dashboard/` | Streamlit web UI (6 pages: Home, Costs, Forecasts, Recommendations, Settings) | Done |
| `tests/` | Unit tests (pytest) | Done |

## Why This Architecture

**SQLite as the single data store** — All modules read and write through `storage.db` `insert_*`/`get_*` functions. No CSV intermediate layer. This gives us ACID transactions, type safety, indexed queries, and multi-user isolation via `user_id` — all without external database setup.

**Two config files** — `config.py` (root) holds project-level settings like paths and ML constants. `aws_collector/config.py` holds boto3 session management. They don't overlap — one is about the project, the other is about AWS.

**Upsert on primary keys** — `INSERT OR REPLACE` handles deduplication automatically. Re-running the collector or data generator won't create duplicate rows. Downstream modules just call `storage.get_*()`.

**Collector pattern** — Each AWS service has its own collector class in `aws_collector/collectors/` (EC2Collector, RDSCollector, LambdaCollector, etc.). All inherit from `BaseCollector` and implement `list_resources()`, `get_metrics()`, and `collect()`. The `CollectorRunner` in `runner.py` orchestrates them month-by-month. This makes it easy to add new services without touching existing code.
