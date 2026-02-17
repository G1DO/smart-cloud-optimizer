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

Streamlit entry point. Multi-page routing with sidebar navigation. Imports page modules from `dashboard/` and dispatches to `render()` functions. Pages: Home, Costs, Forecasts, Recommendations, Settings.

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

## `data_generation/` — Sample Data Generation

### `synthetic.py`

Generates sample AWS data based on open-source datasets (Bitbrains, NAB, Kaggle) supplemented with generated data for full 10-service coverage. Writes directly to SQLite via `storage.insert_*()`. CLI: `python -m data_generation.synthetic --days 365 --seed 42`.

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

## `ml_engine/` — ML Forecasting Engine

### `data_prep.py`

Data loading and feature engineering from SQLite:

- **Loaders**: `load_cost_data(conn, user_id, ...)`, `load_ec2_metrics(conn, ...)`, `load_rds_metrics(conn, ...)`, plus 7 more service loaders — return DataFrames
- **Dispatcher**: `load_service_metrics(conn, user_id, service)` — loads any service by name
- **Feature engineering**: `add_time_features(df, timestamp_col)` — creates hour, day_of_week, month, is_weekend, sine/cos encodings
- **Lag features**: `create_lag_features(df, columns, lags=[1, 7, 30])`
- **Aggregation**: `aggregate_metrics(df, group_by, agg_funcs)`
- **Training prep**: `prepare_for_training(df, target_col, exclude_cols)` — splits X/y, fills NaNs

### `anomaly.py`

Anomaly detection for cost time series. Run before forecasting to exclude outliers from training:

- **`detect_zscore(series, window, threshold)`** — Rolling Z-score detection (default: window=30, threshold=3.0)
- **`detect_iqr(series, multiplier)`** — IQR-based outlier detection (default: multiplier=1.5)
- **`flag_anomalies(df, value_col)`** — Combines both methods (union), adds `is_anomaly` column

### `forecaster.py`

5 forecasting models with a unified `fit(df)` / `predict(horizon)` interface. All return DataFrame with `[date, forecast, lower, upper]`:

- **`NaiveForecaster`** — Repeats last value (baseline)
- **`SeasonalNaiveForecaster`** — Weekly pattern repetition
- **`ETSForecaster`** — Exponential Smoothing (statsmodels). Falls back to non-seasonal with < 2 weeks data
- **`ProphetForecaster`** — Facebook Prophet with weekly + yearly seasonality
- **`SARIMAXForecaster`** — Auto-tuned SARIMAX via pmdarima

### `evaluator.py`

Model evaluation via walk-forward cross-validation:

- **`calc_metrics(y_true, y_pred)`** — Returns MAPE, RMSE, MAE
- **`time_series_cv(model, df, ...)`** — Expanding window CV, returns metrics per fold
- **`compare_models(models, df, ...)`** — Runs CV on multiple models, returns comparison table sorted by MAPE

## `ai_module/` -- AI Recommendation Engine

For **new users with no AWS data**, generates initial architecture recommendations via Google Gemini 2.5 Flash based on business requirements.

### `guided_questions.py`

Returns 9 structured questions: business_type, expected_users, uptime_requirement, optimization_priority, traffic_pattern, availability_zones, monthly_budget, aws_experience, additional_notes.

### `prompt_builder.py`

Converts user answers into a structured LLM prompt. Specifies JSON output format. Instructs: prefer serverless, Graviton, match experience level.

### `recommender.py`

Calls Google Gemini 2.5 Flash API via `google.genai` client. Returns `(parsed_dict, raw_response_text)`. Handles API failures, JSON parsing errors, missing API keys.

### `ui.py`

Streamlit rendering for AI recommendations -- service breakdown cards, estimated monthly cost, architecture explanation, implementation steps.

---

## `optimizer/` -- Cost Optimization Engine

Uses PuLP linear programming + rule-based heuristics to find savings.

### `compute_lp.py`

MILP solver for optimal resource allocation:
- `optimize_ec2(conn, user_id, budget_cap)` -- Minimizes total cost subject to CPU/memory demand + budget constraints
- `optimize_rds(conn, user_id, budget_cap)` -- Finds best RDS instance type for workload

### `rules.py`

8 heuristic checks across AWS services: EC2 (RI/Spot), RDS (RI, Multi-AZ), Lambda (memory right-sizing), EBS (unattached volumes), S3 (Intelligent-Tiering), DynamoDB (On-Demand vs provisioned), NAT Gateway (consolidation), ELB (idle elimination).

### `engine.py`

Orchestrator. Runs LP solver + rules, deduplicates (keeps highest savings per resource), writes all recommendations to database, returns sorted by savings.

### `__main__.py`

CLI entry point: `python -m optimizer --user-id aws-SYNTHETIC-001`

---

## `dashboard/` -- Streamlit Web UI (6 pages)

### `components.py` (563 lines)

Reusable UI components: metric cards (cost, savings, anomaly count), chart templates (line, bar, area via Plotly), data formatters (currency, percentages), loading states, error displays.

### `home.py`

Home page: user selection dropdown, overview metrics (total cost, projected savings), top recommendations, quick stats cards.

### `costs.py`

Cost analysis page: daily cost line chart (Plotly), service breakdown bar chart, top expensive resources table, date range selector, export to CSV.

### `forecasts.py`

Forecasts page: forecast visualization (actuals vs predictions), confidence intervals (shaded regions), model comparison table (RMSE, MAE, MAPE), forecast horizon selector (7, 14, 30, 60 days).

### `recommendations.py`

Recommendations page: savings cards with priority badges, estimated monthly savings, filters by service/type/priority, sort by savings/priority/risk.

### `settings.py`

Settings page: user profile management, AWS account connection (stub), forecast/optimization parameters, demo mode toggle, data refresh controls.

---

## `tests/`

### `test_config.py`

Tests for root `config.py`: paths exist, constants have correct types, `DB_PATH` is set.

### `test_date_utils.py`

Tests for date utilities in `aws_collector/metrics.py`: month range generation, edge cases (year boundaries, February), output format.

### `test_ml_utils.py`

Tests for `ml_engine/`: data loading, feature engineering, anomaly detection, forecasters (Naive, SeasonalNaive, ETS), evaluator metrics and cross-validation.

### `test_storage.py`

Tests for `storage/db.py`: insert/query API, upsert behavior (`INSERT OR REPLACE`), user isolation, schema creation, 25 tests covering all table categories.

### `test_synthetic.py`

Tests for `data_generation/synthetic.py`: DB table population, schema validation, row counts, determinism (same seed = same output), value ranges.

### `test_optimizer.py`

Tests for `optimizer/`: LP solver constraints, rule-based recommendations, orchestrator deduplication, DB write verification. 27 tests (26 passing, 1 failing).

### `test_ai_module.py`

Tests for `ai_module/`: guided questions structure, prompt builder output, recommender API mocking, JSON parsing, error handling. 13 tests.
