# Smart Cloud Optimizer — Documentation Index

## Quick Links

- **New here?** Start with [QUICKSTART.md](QUICKSTART.md)
- **How does it work?** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Where's the code for X?** See [MODULES.md](MODULES.md)

---

## Reading Order

### Level 1: Get Running (15 min)

1. [QUICKSTART.md](QUICKSTART.md) — Setup and first run

### Level 2: Understand the System (30 min)

2. [ARCHITECTURE.md](ARCHITECTURE.md) — How components fit together
3. [MODULES.md](MODULES.md) — What each file does
4. [DATA_PIPELINE.md](DATA_PIPELINE.md) — How data flows

### Level 3: Deep Dives (as needed)

5. [STORAGE_API.md](STORAGE_API.md) — Database API reference
6. [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — All 30 database tables
7. [CONFIGURATION.md](CONFIGURATION.md) — Environment variables
8. [DATA_RESOURCES.md](DATA_RESOURCES.md) — External data sources

---

## What Each File Covers

| File | Topic | When to Read |
|------|-------|--------------|
| QUICKSTART | Setup, run, test | First day |
| ARCHITECTURE | System diagram, module roles | Before coding |
| MODULES | File-by-file breakdown | When lost |
| DATA_PIPELINE | Collection + synthetic flow | Working on data |
| STORAGE_API | insert_*/get_* functions | Using the DB |
| DATA_SCHEMAS | 30 table definitions | DB queries |
| CONFIGURATION | Env vars, logging | Deployment |
| DATA_RESOURCES | External datasets | Research |

---

## Project Overview

Smart Cloud Optimizer is an AI-powered AWS cost optimization platform:

1. **Collect** — Gather AWS data (costs, metrics, pricing) or generate synthetic demo data
2. **Analyze** — Forecast usage with ML models (Prophet, SARIMAX)
3. **Optimize** — Recommend right-sizing and pricing strategies

All data is stored in SQLite (`data/cloud_optimizer.db`) via the `storage/` module.

---

## Key Directories

```
cloud-gp/
├── aws_collector/      # AWS data collection (10 service collectors)
├── data_generation/    # Synthetic data generator
├── storage/            # SQLite gateway (30 tables)
├── ml_engine/          # ML forecasting (partial)
├── ai_module/          # AI recommendations (stub)
├── optimizer/          # Cost optimization (stub)
├── dashboard/          # Streamlit UI (stub)
└── tests/              # 117 tests
```
