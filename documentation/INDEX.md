# Smart Cloud Optimizer — Documentation Index

## Quick Links

- **New here?** Start with [QUICKSTART.md](QUICKSTART.md)
- **How does it work?** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Where's the code for X?** See [MODULES.md](MODULES.md)
- **Contributing?** See [CONTRIBUTING.md](../CONTRIBUTING.md) and [DEVELOPMENT.md](DEVELOPMENT.md)

The application on `main` is Next.js + FastAPI. Its setup lives in the
[README](../README.md#quick-start). Repository docs describe implemented behavior;
[Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111)
describes the broader project intent. Canonical engineering and documentation
guidance is linked from [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Reading Order

### Level 1: Get Running (15 min)

1. [QUICKSTART.md](QUICKSTART.md) -- Setup and first run
2. [STARTUP.md](STARTUP.md) -- Optional legacy Streamlit UI and engine entry points
3. [DEVELOPMENT.md](DEVELOPMENT.md) -- Checks and development conventions

### Level 2: Understand the System (30 min)

1. [ARCHITECTURE.md](ARCHITECTURE.md) -- How components fit together
2. [MODULES.md](MODULES.md) -- What each file does
3. [DATA_PIPELINE.md](DATA_PIPELINE.md) -- How data flows

### Level 3: Deep Dives (as needed)

1. [STORAGE_API.md](STORAGE_API.md) -- Database API reference (auth, connections, data)
2. [DATA_SCHEMAS.md](DATA_SCHEMAS.md) -- Data model and generated SQLite schema
3. [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables
4. [DATA_RESOURCES.md](DATA_RESOURCES.md) -- Historical research references
5. [ai_module.md](ai_module.md) -- AI recommendation engine
6. [optimizer.md](optimizer.md) -- Cost optimization logic
7. [forecasting_models.md](forecasting_models.md) -- ML model details

---

## What Each File Covers

| File | Topic | When to Read |
|------|-------|--------------|
| QUICKSTART | Setup, run, test | First day |
| STARTUP | Legacy Streamlit startup | Working on the Python UI |
| DEVELOPMENT | Tests, frontend lint/build, API reference | Before opening a PR |
| ARCHITECTURE | System diagram, module roles | Before coding |
| MODULES | File-by-file breakdown | When lost |
| DATA_PIPELINE | Collection + data pipeline flow | Working on data |
| STORAGE_API | Generated signatures, transactions, safe examples | Using the DB |
| DATA_SCHEMAS | Data model and schema generation | DB queries |
| CONFIGURATION | Env vars, logging | Deployment |
| DATA_RESOURCES | Historical dataset references | Research provenance |
| ai_module | AI recommendation engine | AI features |
| optimizer | Cost optimization logic | Optimization |
| forecasting_models | Runtime behavior, evaluation, historical results | Forecasting |

---

## Project Overview

Smart Cloud Optimizer is an AI-powered AWS cost optimization platform:

1. **Collect** — Gather AWS data (costs, metrics, pricing) or use synthetic demo data
2. **Analyze** — Forecast usage with ML models (Prophet, SARIMAX)
3. **Optimize** — Recommend right-sizing and pricing strategies

Account data and engine results are stored in SQLite (`data/cloud_optimizer.db`);
runtime settings use a separate JSON file. See [Architecture](ARCHITECTURE.md)
for persistence and access boundaries.

---

## Key Directories

```
smart-cloud-optimizer/
├── frontend/           # Primary TypeScript/Next.js UI
├── backend_api/        # FastAPI HTTP routes
├── cloud_optimizer/    # Shared Python configuration
├── data_generation/    # Tracked synthetic generator
├── aws_collector/      # AWS data collection (11 service collectors)
├── storage/            # SQLite gateway (30 tables, auth + data API)
├── ml_engine/          # ML forecasting engine (5 models)
├── ai_module/          # AI recommendations (Gemini 2.5)
├── optimizer/          # Cost optimization (LP solver + rules)
├── dashboard/          # Optional legacy Streamlit UI
└── tests/              # Unit tests (auth, storage, ML, optimizer, AI)
```

## Historical material

[Paper artifacts](../docs-gp/README.md) and the
[imported integration review](../CODE_REVIEW_PR2.md) preserve earlier work.
They are not the current backlog, runtime specification, or current validation
results. Use GitHub for accepted engineering work and the linked Notion project
for project context and decisions.
