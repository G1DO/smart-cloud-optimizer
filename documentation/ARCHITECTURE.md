# Architecture

## What This Project Is

Smart Cloud Optimizer is an AI-powered platform that helps reduce AWS cloud costs. It works in three stages:

1. **Collect** — Gather real AWS data (costs, metrics, pricing, inventory) or generate synthetic data for demo mode
2. **Analyze** — Use ML models to forecast future usage and detect anomalies
3. **Optimize** — Recommend right-sizing instances, switching pricing plans, and eliminating waste

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│   ┌──────────────────┐         ┌──────────────────────┐        │
│   │  AWS Account     │         │  Synthetic Generator  │        │
│   │  (real data)     │         │  (demo mode)          │        │
│   │                  │         │                       │        │
│   │  - Cost Explorer │         │  - Fake 8-instance    │        │
│   │  - CloudWatch    │         │    EC2 fleet           │        │
│   │  - Pricing API   │         │  - 365 days of costs  │        │
│   │  - EC2/RDS/S3..  │         │  - Realistic metrics  │        │
│   └────────┬─────────┘         └───────────┬──────────┘        │
│            │                                │                   │
│            ▼                                ▼                   │
│   ┌──────────────────────────────────────────────┐             │
│   │              data/ (CSV files)                │             │
│   │                                               │             │
│   │   data/real/     ← from AWS (gitignored)     │             │
│   │   data/synthetic/ ← generated (committed)    │             │
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
│   │   ARIMA)     │  │  (OpenAI)    │  │  minimization    │    │
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

No AWS credentials needed. The synthetic generator creates realistic data that mimics a mid-size SaaS startup (~$1,500-$2,500/month AWS bill). This mode lets you demo the full platform without a real AWS account.

```text
data_generation/synthetic.py  ──>  data/synthetic/*.csv  ──>  dashboard
```

### Real Mode (`DEMO_MODE=false`)

Connects to a real AWS account via boto3. Collects 12 months of historical data across all enabled regions.

```text
aws_collector/main.py  ──>  data/real/*.csv  ──>  dashboard
```

The `config.get_data_dir()` function returns the correct path based on the mode.

## Module Responsibilities

| Module | Purpose | Status |
| --- | --- | --- |
| `config.py` | Project-wide constants, paths, env vars | Done |
| `aws_collector/` | Real AWS data collection pipeline | Done |
| `data_generation/` | Synthetic data generator | Done |
| `ml_engine/` | Time-series forecasting (Prophet, ARIMA, statsmodels) | Stub |
| `ai_module/` | LLM-based instance recommendations (OpenAI) | Stub |
| `optimizer/` | Cost minimization via linear programming (PuLP) | Stub |
| `storage/` | Data persistence and database layer | Stub |
| `dashboard/` | Streamlit web UI | Stub |
| `tests/` | Unit tests (pytest) | Done |

## Why This Architecture

**CSV as the data interchange format** — Every module reads and writes CSV. This makes debugging trivial (open in any spreadsheet), avoids database setup complexity, and works identically in demo and real modes.

**Two config files** — `config.py` (root) holds project-level settings like paths and ML constants. `aws_collector/config.py` holds boto3 session management. They don't overlap — one is about the project, the other is about AWS.

**Append-only consolidated files** — Instead of one CSV per month, each service has a single consolidated file. New data appends with deduplication. This makes ML training simple — just `pd.read_csv()` the one file.

**Collector pattern** — Each AWS service has its own collector class (CostCollector, EC2Collector, etc.). The CollectorRunner orchestrates them month-by-month. This makes it easy to add new services without touching existing code.
