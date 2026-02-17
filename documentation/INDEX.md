# Smart Cloud Optimizer — Documentation Index

## Quick Links

- **New here?** Start with [QUICKSTART.md](QUICKSTART.md)
- **Project status?** See [PROJECT_STATUS.md](PROJECT_STATUS.md) ⭐ **NEW**
- **How does it work?** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Where's the code for X?** See [MODULES.md](MODULES.md)

---

## Reading Order

### Level 1: Get Running (15 min)

1. [QUICKSTART.md](QUICKSTART.md) — Setup and first run
2. [PROJECT_STATUS.md](PROJECT_STATUS.md) — What's done, what's missing, what's next ⭐

### Level 2: Understand the System (30 min)

1. [ARCHITECTURE.md](ARCHITECTURE.md) — How components fit together
2. [MODULES.md](MODULES.md) — What each file does
3. [DATA_PIPELINE.md](DATA_PIPELINE.md) — How data flows

### Level 3: Deep Dives (as needed)

1. [STORAGE_API.md](STORAGE_API.md) — Database API reference
2. [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — All 30 database tables
3. [CONFIGURATION.md](CONFIGURATION.md) — Environment variables
4. [DATA_RESOURCES.md](DATA_RESOURCES.md) — External data sources
5. [ai_module.md](ai_module.md) — AI recommendation engine
6. [optimizer.md](optimizer.md) — Cost optimization logic
7. [forecasting_models.md](forecasting_models.md) — ML model details
8. [STARTUP.md](STARTUP.md) — Startup and CLI guide

---

## What Each File Covers

| File | Topic | When to Read |
|------|-------|--------------|
| QUICKSTART | Setup, run, test | First day |
| PROJECT_STATUS | What's done, gaps, roadmap | Planning next work ⭐ |
| ARCHITECTURE | System diagram, module roles | Before coding |
| MODULES | File-by-file breakdown | When lost |
| DATA_PIPELINE | Collection + data pipeline flow | Working on data |
| STORAGE_API | insert_*/get_* functions | Using the DB |
| DATA_SCHEMAS | 30 table definitions | DB queries |
| CONFIGURATION | Env vars, logging | Deployment |
| DATA_RESOURCES | External datasets | Research |
| STARTUP | Launch dashboard, CLI tools | First run |
| ai_module | AI recommendation engine | AI features |
| optimizer | Cost optimization logic | Optimization |
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
├── aws_collector/      # AWS data collection (11 service collectors) ✅
├── data_generation/    # Sample data generator ✅
├── storage/            # SQLite gateway (30 tables) ✅
├── ml_engine/          # ML forecasting engine (5 models) ✅
├── ai_module/          # AI recommendations (Gemini 2.5) ✅
├── optimizer/          # Cost optimization (LP solver + rules) ✅
├── dashboard/          # Streamlit UI (6 pages) ✅
└── tests/              # 183 tests
```
