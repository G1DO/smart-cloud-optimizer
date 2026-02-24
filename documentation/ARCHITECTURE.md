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
│   │  AWS Account(s)  │         │  Pre-loaded Demo Data  │        │
│   │  (real data)     │         │  (synthetic, in DB)    │        │
│   │                  │         │                        │        │
│   │  - Cost Explorer │         │  - 365 days of costs   │        │
│   │  - CloudWatch    │         │  - 10 AWS services     │        │
│   │  - Pricing API   │         │  - Realistic profiles  │        │
│   │  - EC2/RDS/S3..  │         │  - Pricing data        │        │
│   └────────┬─────────┘         └───────────┬──────────┘        │
│            │                                │                   │
│            ▼                                ▼                   │
│   ┌──────────────────────────────────────────────────────┐     │
│   │         storage/db.py  (SQLite gateway)              │     │
│   │                                                       │     │
│   │   insert_*() ──> data/cloud_optimizer.db             │     │
│   │   get_*()    <── (30 tables, user_id keyed)          │     │
│   │                                                       │     │
│   │   Auth: register_user, authenticate_user, hash_pw    │     │
│   │   Connections: add/get/delete_aws_connection          │     │
│   └───────────────────────┬──────────────────────────────┘     │
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
│   │  ┌─ auth gate (login / register / demo) ──┐  │             │
│   │  │                                        │  │             │
│   │  │  ┌─ account switcher ──────────────┐   │  │             │
│   │  │  │  Home | Costs | Forecasts |     │   │  │             │
│   │  │  │  Recommendations | Settings     │   │  │             │
│   │  │  └─────────────────────────────────┘   │  │             │
│   │  └────────────────────────────────────────┘  │             │
│   └──────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## The Two Modes

### Demo Mode (click "Try Demo Mode" on login screen)

No AWS credentials needed. The database ships with pre-loaded synthetic data (originally generated from open-source datasets: Bitbrains VM traces, NAB CloudWatch metrics, Kaggle pricing) covering all 10 AWS services. Mimics a mid-size SaaS startup (~$1,500-$2,500/month AWS bill). Logs in as a pre-seeded demo user (`demo@cis.asu.edu.eg`).

```text
pre-loaded data in SQLite DB  ──>  dashboard (read-only via storage.get_*())
```

### Real Mode (register + connect AWS account)

Users register an account, then add AWS connections in Settings by providing an IAM role ARN. The collector assumes the role via STS, collects 12 months of historical data across all enabled regions, and writes to the database.

```text
aws_collector/runner.py  ──>  storage.insert_*()  ──>  SQLite DB  ──>  dashboard
```

Both modes read from the same SQLite database through `storage.get_*()`. Downstream modules don't care which source produced the data.

## Module Responsibilities

| Module | Purpose | Status |
| --- | --- | --- |
| `config.py` | Project-wide constants, paths, env vars | Done |
| `aws_collector/` | Real AWS data collection pipeline (supports IAM role assumption) | Done |
| `storage/` | SQLite gateway (30 tables, auth + `insert_*`/`get_*` API) | Done |
| `ml_engine/` | Data prep, anomaly detection, time-series forecasting, evaluation | Done |
| `ai_module/` | LLM-based architecture recommendations (Google Gemini 2.5 Flash) | Done |
| `optimizer/` | Cost minimization via LP (PuLP) + 8 rule-based checks | Done |
| `dashboard/` | Streamlit web UI (auth gate + 5 pages: Home, Costs, Forecasts, Recommendations, Settings) | Done |
| `tests/` | Unit tests (pytest), including auth and AWS connection CRUD | Done |

## Why This Architecture

**SQLite as the single data store** -- All modules read and write through `storage.db` `insert_*`/`get_*` functions. No CSV intermediate layer. This gives us ACID transactions, type safety, indexed queries, and multi-user isolation via `user_id` -- all without external database setup.

**Authentication in the storage layer** -- User management (registration, login, password hashing) lives in `storage/db.py` alongside the data functions. The `users` table stores credentials (HMAC-SHA256 hashed passwords with random salts) and the `aws_connections` table maps users to their AWS accounts via IAM role ARNs. The dashboard's `auth.py` module handles the Streamlit UI and session state. This keeps auth logic close to the data layer it protects.

**Two config files** -- `config.py` (root) holds project-level settings like paths and ML constants. `aws_collector/config.py` holds boto3 session management with `AWSConfig.from_role()` for cross-account access. They don't overlap -- one is about the project, the other is about AWS.

**Upsert on primary keys** -- `INSERT OR REPLACE` handles deduplication automatically. Re-running the collector won't create duplicate rows. Downstream modules just call `storage.get_*()`.

**Collector pattern** -- Each AWS service has its own collector class in `aws_collector/collectors/` (EC2Collector, RDSCollector, LambdaCollector, etc.). All inherit from `BaseCollector` and implement `list_resources()`, `get_metrics()`, and `collect()`. The `CollectorRunner` in `runner.py` orchestrates them month-by-month. `CollectorRunner.from_connection()` enables per-user collection by assuming IAM roles from `aws_connections` rows. This makes it easy to add new services without touching existing code.
