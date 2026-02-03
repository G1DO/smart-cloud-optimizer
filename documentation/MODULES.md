# Modules

Every file in the project, what it does, and how it connects to the rest.

---

## Root Files

### `config.py`

Single source of truth for project-wide settings. Contains:

- **Paths**: `PROJECT_ROOT`, `DATA_DIR`, `DB_PATH`
- **Mode**: `DEMO_MODE` (bool, from env var, default `true`)
- **AWS**: `AWS_REGION`, `AWS_ACCOUNT_ID`
- **ML**: `FORECAST_HORIZON_DAYS`, `MIN_TRAINING_DAYS`, `SEASONALITY_PERIOD`
- **Optimization**: `DEFAULT_BUDGET_CAP`, `SPOT_RELIABILITY`
- **API keys**: `OPENAI_API_KEY`, `OPENAI_MODEL`
- **Reference data**: `INSTANCE_SPECS` (17 instance types), `SERVICE_NAME_MAP` (AWS name → short DB name)
- **Functions**: `setup_logging()`

This file does NOT touch boto3. AWS client setup lives in `aws_collector/config.py`.

### `app.py`

Streamlit entry point (stub). Will import from `dashboard/` and launch the web UI.

### `pyproject.toml`

Project metadata and dependency specification.

---

## `aws_collector/` — AWS Data Collection Pipeline

### `__init__.py`

Exports `CollectorRunner`, `AWSConfig`, `init_config`, `get_config`.

### `config.py`

AWS-specific configuration. Creates and manages boto3 clients.

- **`AWSConfig`** class: Holds `session`, `ce` (Cost Explorer), `ec2`, `cloudwatch`, `pricing`, `s3` clients. Also fetches `account_id` via STS and `regions` via `ec2.describe_regions()`.
- **`get_config()`**: Singleton accessor — returns existing `AWSConfig` or creates one.
- **`init_config(session)`**: Initializes the singleton with a specific boto3 session.
- Regional clients created on-demand via `get_ec2_client(region)`, `get_rds_client(region)`, `get_lambda_client(region)`, `get_cloudwatch_client(region)`.

### `runner.py`

Thin orchestrator (~165 lines). Initializes all service collectors and runs them month-by-month:

```python
class CollectorRunner:
    def run(self, months: int = 12):
        for start, end in get_last_n_months(months):
            self.cost.collect(start, end)
            self.ec2.collect(start, end)
            # ... each collector handles its own inventory + metrics
```

### `metrics.py`

Merged module containing CloudWatch helpers, metric maps, and date utilities:

- **`fetch_cw_metric()`** — Generic wrapper for `cloudwatch.get_metric_statistics()`
- **Metric maps**: `EC2_METRIC_MAP`, `RDS_METRIC_MAP`, `LAMBDA_METRIC_MAP`, etc.
- **Date utilities**: `get_last_n_months()`, `get_datetime_range()`, `month_start_end()`, `get_month_key()`

### `transforms.py`

Data transformation helpers. Normalizes raw AWS API responses into the dict format expected by `storage.insert_*()`.

### `pricing_constants.py`

Static data used by `PricingCollector`:

- `REGION_LOCATION_MAP` — Maps region codes to AWS pricing API location names
- `DEFAULT_INSTANCE_TYPES` — Instance types to query pricing for
- `DEFAULT_S3_CLASSES` — S3 storage classes
- `DEFAULT_RDS_CLASSES` — RDS instance classes
- `SPOT_DISCOUNT_FACTOR` — 0.7 (Spot is ~70% of on-demand)

### `main.py`

CLI entry point (`python -m aws_collector.main`). Initializes logging, creates `CollectorRunner`, runs `runner.run()`, reports results.

---

### `collectors/` — Service Collectors

All collectors inherit from `BaseCollector` and implement a consistent interface:

```python
class ServiceCollector(BaseCollector):
    SERVICE_NAME: str = "ServiceName"

    def list_resources(self) -> List[Dict]: ...
    def get_metrics(self, resource_id, region, start, end) -> Dict: ...
    def collect(self, start_date, end_date) -> int: ...
```

| File | Service | Inventory | Metrics |
|------|---------|-----------|---------|
| `base.py` | Abstract base | — | `_fetch_metric()` helper |
| `ec2.py` | EC2 + EBS | instances, volumes | CPU, network, disk |
| `rds.py` | RDS | db instances | CPU, connections, storage |
| `lambda_.py` | Lambda | functions | invocations, duration, errors |
| `s3.py` | S3 | buckets | size, object count |
| `dynamodb.py` | DynamoDB | tables | read/write capacity |
| `elasticache.py` | ElastiCache | clusters | CPU, memory, cache hits |
| `ecs.py` | ECS/Fargate | services | CPU, memory |
| `nat_gateway.py` | NAT Gateway | gateways | bytes, packets, connections |
| `elb.py` | ALB/NLB | load balancers | requests, response time |
| `cost.py` | Cost Explorer | — | daily/service costs, anomalies |
| `pricing.py` | Pricing API | — | EC2/RDS/Lambda/S3 pricing |

---

## `storage/` — Data Persistence Layer

### `db.py`

Single data gateway for the entire project. Contains:

- **Schema DDL**: 30 `CREATE TABLE` statements (inline, not a separate SQL file)
- **Connection management**: `get_connection(db_path)` — opens SQLite with WAL mode, foreign keys enabled
- **Schema lifecycle**: `ensure_schema(conn)` (create tables/indexes if missing, non-destructive), `create_schema(conn)` (drop + recreate, destructive; tests/dev only), `ensure_user(conn, account_id)`, `clear_user_data(conn, user_id)`
- **Insert functions** (30): One per table — `insert_daily_costs()`, `insert_ec2_instances()`, `insert_ec2_metrics()`, etc. All accept `(conn, user_id, rows: list[dict])`. Do not commit — caller batches and commits.
- **Get functions** (27): One per table — `get_daily_costs()`, `get_ec2_instances()`, `get_ec2_metrics()`, etc. Support filtering by date range and resource ID. Return `list[dict]`.
- **Internal helpers**: `_safe_float()`, `_safe_int()`, `_build_tuples()`, `_executemany_insert()`, `_rows_to_dicts()`, `_query_metrics()`

### `__init__.py`

Exports all 57+ public functions, plus `INSTANCE_SPECS` and `SERVICE_NAME_MAP` constants.

---

## `data_generation/` — Synthetic Data

### `synthetic.py`

Generates realistic AWS data and writes directly to SQLite via `storage.insert_*()`. CLI: `python -m data_generation.synthetic --days 365 --seed 42`.

Key functions:

- `generate_daily_costs()` — Realistic cost curve with seasonality, trend, anomalies, noise
- `generate_service_costs()` — Breaks daily cost into per-service amounts
- `generate_ec2_instances()` — 8 instances with realistic metadata
- `generate_ec2_metrics()` — Per-instance CPU profiles (diurnal, spiky, steady, batch)
- `generate_rds_instances()` — 2 RDS instances
- `generate_rds_metrics()` — RDS CPU, storage, connections
- Plus generators for ElastiCache, ECS, DynamoDB, S3, Lambda, EBS, NAT Gateway, ELB
- `generate_instance_pricing()` — Pricing for all instance types
- `generate_ai_recommendations()` — Sample AI recommendations

All random values use `numpy.random.default_rng(seed)` for deterministic output.

---

## `ml_engine/` — ML Forecasting (Partial)

### `data_prep.py`

Data loading and feature engineering from SQLite:

- **Loaders**: `load_cost_data(conn, user_id, ...)`, `load_ec2_metrics(conn, ...)`, `load_rds_metrics(conn, ...)` — return DataFrames
- **Feature engineering**: `add_time_features(df, timestamp_col)` — creates hour, day_of_week, month, is_weekend, sine/cos encodings
- **Lag features**: `create_lag_features(df, columns, lags=[1, 7, 30])`
- **Aggregation**: `aggregate_metrics(df, group_by, agg_funcs)`
- **Training prep**: `prepare_for_training(df, target_col, exclude_cols)` — splits X/y, fills NaNs

Forecasting models (Prophet, SARIMAX) not yet implemented.

## `ai_module/` — AI Recommendations (Stub)

Will use OpenAI API to recommend instance types based on workload profiles. Reads inventory and metrics via `storage.get_*()`, outputs recommendations.

## `optimizer/` — Cost Optimization (Stub)

Will use PuLP linear programming to find the cheapest instance mix that meets performance constraints. Reads forecasts and pricing via `storage.get_*()`, outputs an optimized plan.

## `dashboard/` — Web UI (Stub)

Streamlit dashboard. Will display cost trends, anomaly charts, right-sizing recommendations, and pricing comparisons.

---

## `tests/`

### `test_config.py`

Tests for root `config.py`: paths exist, constants have correct types, `DB_PATH` is set.

### `test_date_utils.py`

Tests for date utilities in `aws_collector/metrics.py`: month range generation, edge cases (year boundaries, February), output format.

### `test_ml_utils.py`

Tests for `ml_engine/data_prep.py`: data loading, feature engineering, lag creation.

### `test_storage.py`

Tests for `storage/db.py`: insert/query API, upsert behavior (`INSERT OR REPLACE`), user isolation, schema creation, 25 tests covering all table categories.

### `test_synthetic.py`

Tests for `data_generation/synthetic.py`: DB table population, schema validation, row counts, determinism (same seed = same output), value ranges.
