# Modules

Every file in the project, what it does, and how it connects to the rest.

---

## Root Files

### `config.py`

Single source of truth for project-wide settings. Contains:

- **Paths**: `PROJECT_ROOT`, `DATA_DIR`, `REAL_DATA_DIR`, `SYNTHETIC_DATA_DIR`, `DB_PATH`
- **Mode**: `DEMO_MODE` (bool, from env var, default `true`)
- **AWS**: `AWS_REGION`, `AWS_ACCOUNT_ID`
- **ML**: `FORECAST_HORIZON_DAYS`, `MIN_TRAINING_DAYS`, `SEASONALITY_PERIOD`
- **Optimization**: `DEFAULT_BUDGET_CAP`, `SPOT_RELIABILITY`
- **API keys**: `OPENAI_API_KEY`, `OPENAI_MODEL`
- **Functions**: `get_data_dir()` (returns synthetic or real path), `setup_logging()`

This file does NOT touch boto3. AWS client setup lives in `aws_collector/config.py`.

### `app.py`

Streamlit entry point (stub). Will import from `dashboard/` and launch the web UI.

### `requirements.txt`

Python dependencies: `boto3`, `pandas`, `numpy`, `matplotlib`, `pytest`.

---

## `aws_collector/` — AWS Data Collection Pipeline

### `__init__.py`

Exports `CollectorRunner` for external use.

### `config.py`

AWS-specific configuration. Creates and manages boto3 clients.

- **`AWSConfig`** class: Holds `session`, `ce` (Cost Explorer), `ec2`, `cloudwatch`, `pricing`, `s3` clients. Also fetches `account_id` via STS and `regions` via `ec2.describe_regions()`.
- **`get_config()`**: Singleton accessor — returns existing `AWSConfig` or creates one.
- **`init_config(session)`**: Initializes the singleton with a specific boto3 session.
- Creates `data/` subdirectories on import.

### `collector_runner.py`

The orchestrator. `CollectorRunner` runs the full collection pipeline:

1. `save_inventory()` — EC2 instances, volumes, regions
2. Monthly loop: `collect_month()` (costs) → `collect_metrics_for_month()` (CloudWatch) → `collect_month_snapshot()` (pricing)

The metrics collection is split into private methods:
- `_collect_ec2_metrics()`, `_collect_ebs_metrics()`, `_collect_lambda_metrics()`
- `_collect_rds_metrics()`, `_collect_s3_metrics()`, `_collect_cloudfront_metrics()`
- `_collect_nat_metrics()`, `_collect_lb_metrics()`

Also handles instance merging (live + JSON + CSV inventories) to capture terminated instance metrics.

### `cost_collector.py`

`CostCollector` wraps AWS Cost Explorer API. Methods:

- `collect_month(start, end)` — Runs all four cost queries for a date range
- `fetch_daily_cost()` — `GetCostAndUsage` grouped by day
- `fetch_service_cost()` — `GetCostAndUsage` grouped by service
- `fetch_usage_type_cost()` — `GetCostAndUsage` grouped by usage type
- `fetch_anomalies()` — `GetAnomalies` for the period

All results append to consolidated CSVs with deduplication.

### `cw_collector.py`

`CloudWatchCollector` wraps `cloudwatch.get_metric_statistics()`. Provides typed methods for each metric:

- `get_cpu_utilization()`, `get_network_in()`, `get_network_out()`
- `get_disk_read_ops()`, `get_disk_write_ops()`
- And similar for EBS, Lambda, RDS, S3, CloudFront, NAT, ALB, NLB

Each method returns a list of `(timestamp, value)` tuples.

### `ec2_collector.py`

`EC2Collector` handles EC2 and EBS inventory:

- `list_instances()` — Calls `ec2.describe_instances()` across all regions
- `list_volumes()` — Calls `ec2.describe_volumes()` across all regions
- `list_regions()` — Returns the region list from config
- `save_inventory()` — Writes all three to consolidated CSVs

### `pricing_collector.py`

`PricingCollector` queries the AWS Pricing API for instance costs:

- `collect_month_snapshot(month_key)` — Collects all pricing types for a month
- `_collect_ec2_on_demand()` — On-demand EC2 pricing via Pricing API
- `_collect_ec2_reserved()` — Reserved instance pricing (1yr, 3yr)
- `_collect_ec2_spot()` — Spot pricing (estimated from on-demand × discount factor)
- `_collect_s3_pricing()` — S3 storage class pricing
- `_collect_lambda_pricing()` — Lambda compute pricing
- `_collect_rds_pricing()` — RDS instance pricing

### `pricing_constants.py`

Static data used by `PricingCollector`:

- `REGION_LOCATION_MAP` — Maps region codes to AWS pricing API location names
- `DEFAULT_INSTANCE_TYPES` — Instance types to query pricing for
- `DEFAULT_S3_CLASSES` — S3 storage classes
- `DEFAULT_RDS_CLASSES` — RDS instance classes
- `SPOT_DISCOUNT_FACTOR` — 0.7 (Spot is ~70% of on-demand)

### `collect_cloudfront.py`

Collects CloudFront distribution inventory and metrics. Called by `CollectorRunner._collect_cloudfront_metrics()`.

### `collect_nat_gateways.py`

Collects NAT Gateway inventory and metrics across all regions. Called by `CollectorRunner._collect_nat_metrics()`.

### `collect_load_balancers.py`

Collects ALB and NLB inventory and metrics. Handles the ELBv2 API and splits results by load balancer type. Called by `CollectorRunner._collect_lb_metrics()`.

### `date_utils.py`

Date arithmetic for month-based collection:

- `get_last_n_months(n)` — Returns list of `(start_str, end_str)` tuples for the last N months
- `get_datetime_range(start_str, end_str)` — Converts date strings to datetime objects

### `ml_utils.py`

Data preparation for the ML engine:

- `prepare_for_training(csv_path)` — Reads a metrics CSV, converts timestamps, sorts, fills missing values
- `compute_daily_aggregates(df)` — Resamples hourly metrics to daily averages
- `detect_outliers(series, threshold)` — Z-score based outlier detection

### `main.py`

CLI entry point (`python -m aws_collector.main`). Initializes logging, creates `AWSConfig`, runs `CollectorRunner.run()`, reports results.

---

## `data_generation/` — Synthetic Data

### `__init__.py`

Empty. Package marker.

### `synthetic.py`

Generates all synthetic CSV files. CLI: `python -m data_generation.synthetic --output-dir data/synthetic/ --days 365 --seed 42`.

Key functions:

- `generate_daily_costs()` — Realistic cost curve with seasonality, trend, anomalies, noise
- `generate_service_costs()` — Breaks daily cost into per-service amounts
- `generate_ec2_instances()` — 8 instances with realistic metadata
- `generate_ec2_metrics()` — Per-instance CPU profiles (diurnal, spiky, steady, batch)
- `generate_rds_instances()` — 2 RDS instances
- `generate_rds_metrics()` — RDS CPU, storage, connections
- `generate_s3_buckets()` — 4 buckets
- `generate_lambda_functions()` — 4 functions
- `generate_ebs_volumes()` — 8 volumes (one per EC2)
- `generate_instance_pricing()` — Pricing for all instance types, merges with real pricing if available
- `generate_ai_recommendations()` — Sample AI recommendations
- `_plot_cost_preview()` — Saves a PNG chart of the generated cost data

All random values use `numpy.random.default_rng(seed)` for deterministic output.

---

## `ml_engine/` — ML Forecasting (Stub)

Will contain time-series forecasting models (Prophet, ARIMA, statsmodels). Reads metrics and cost CSVs, outputs forecasts.

## `ai_module/` — AI Recommendations (Stub)

Will use OpenAI API to recommend instance types based on workload profiles. Reads inventory and metrics, outputs recommendations.

## `optimizer/` — Cost Optimization (Stub)

Will use PuLP linear programming to find the cheapest instance mix that meets performance constraints. Reads forecasts and pricing, outputs an optimized plan.

## `storage/` — Data Persistence (Stub)

Will provide a database layer (SQLite) for storing processed results. Currently all data lives in CSV files.

## `dashboard/` — Web UI (Stub)

Streamlit dashboard. Will display cost trends, anomaly charts, right-sizing recommendations, and pricing comparisons.

---

## `tests/`

### `test_config.py`

Tests for root `config.py`: paths exist, constants have correct types, `get_data_dir()` returns the right directory based on `DEMO_MODE`.

### `test_date_utils.py`

Tests for `aws_collector/date_utils.py`: month range generation, edge cases (year boundaries, February), output format.

### `test_ml_utils.py`

Tests for `aws_collector/ml_utils.py`: data preparation, daily aggregation, outlier detection.

### `test_synthetic.py`

Tests for `data_generation/synthetic.py`: CSV output existence, schema validation, row counts, determinism (same seed = same output), value ranges.
