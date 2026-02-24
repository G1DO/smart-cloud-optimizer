# Smart Cloud Optimizer — Documentation Index

## Quick Links

- **New here?** Start with [QUICKSTART.md](QUICKSTART.md)
- **How does it work?** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Where's the code for X?** See [MODULES.md](MODULES.md)

---

## Reading Order

### Level 1: Get Running (15 min)

1. [QUICKSTART.md](QUICKSTART.md) -- Setup and first run
2. [STARTUP.md](STARTUP.md) -- Dashboard launch and CLI tools

### Level 2: Understand the System (30 min)

1. [ARCHITECTURE.md](ARCHITECTURE.md) -- How components fit together
2. [MODULES.md](MODULES.md) -- What each file does
3. [DATA_PIPELINE.md](DATA_PIPELINE.md) -- How data flows

### Level 3: Deep Dives (as needed)

1. [STORAGE_API.md](STORAGE_API.md) -- Database API reference (auth, connections, data)
2. [DATA_SCHEMAS.md](DATA_SCHEMAS.md) -- All 30 database tables
3. [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables
4. [DATA_RESOURCES.md](DATA_RESOURCES.md) -- External data sources
5. [ai_module.md](ai_module.md) -- AI recommendation engine
6. [optimizer.md](optimizer.md) -- Cost optimization logic
7. [recommendation.md](recommendation.md) -- Recommendation data model
8. [forecasting_models.md](forecasting_models.md) -- ML model details

---

## What Each File Covers

| File | Topic | When to Read |
|------|-------|--------------|
| QUICKSTART | Setup, run, test | First day |
| STARTUP | Launch dashboard, CLI tools | First run |
| ARCHITECTURE | System diagram, module roles | Before coding |
| MODULES | File-by-file breakdown | When lost |
| DATA_PIPELINE | Collection + data pipeline flow | Working on data |
| STORAGE_API | insert_*/get_* + auth functions | Using the DB |
| DATA_SCHEMAS | 30 table definitions | DB queries |
| CONFIGURATION | Env vars, logging | Deployment |
| DATA_RESOURCES | External datasets | Research |
| ai_module | AI recommendation engine | AI features |
| optimizer | Cost optimization logic | Optimization |
| recommendation | Recommendation data model | Recommendation details |
| forecasting_models | ML model details | Forecasting |

---

## Project Overview

Smart Cloud Optimizer is an AI-powered AWS cost optimization platform:

1. **Collect** — Gather AWS data (costs, metrics, pricing) or use open-source sample data
2. **Analyze** — Forecast usage with ML models (Prophet, SARIMAX)
3. **Optimize** — Recommend right-sizing and pricing strategies

All data is stored in SQLite (`data/cloud_optimizer.db`) via the `storage/` module.

---

## Key Directories

```
cloud-gp/
├── aws_collector/      # AWS data collection (11 service collectors)
├── storage/            # SQLite gateway (30 tables, auth + data API)
├── ml_engine/          # ML forecasting engine (5 models)
├── ai_module/          # AI recommendations (Gemini 2.5)
├── optimizer/          # Cost optimization (LP solver + rules)
├── dashboard/          # Streamlit UI (auth gate + 5 nav pages)
└── tests/              # Unit tests (auth, storage, ML, optimizer, AI)
```
