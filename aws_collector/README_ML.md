# ML-Ready Data Access

All collected data is stored in SQLite (`data/cloud_optimizer.db`) and accessed through the `storage.db` and `ml_engine.data_prep` modules. Here's how to use them for ML model training.

## Data Access

### Via storage.db (raw queries)

```python
from storage.db import get_connection, get_daily_costs, get_ec2_metrics, get_ec2_instances

conn = get_connection()

# Cost data
costs = get_daily_costs(conn, user_id="aws-DEMO-001")
costs_filtered = get_daily_costs(conn, user_id="aws-DEMO-001",
                                  start_date="2025-01-01", end_date="2025-06-30")

# EC2 metrics
metrics = get_ec2_metrics(conn, user_id="aws-DEMO-001")
metrics_single = get_ec2_metrics(conn, user_id="aws-DEMO-001",
                                  instance_id="i-abcdef1234567890")

# Inventory
instances = get_ec2_instances(conn, user_id="aws-DEMO-001")
```

### Via ml_engine.data_prep (ML-ready DataFrames)

```python
from storage.db import get_connection
from ml_engine.data_prep import load_cost_data

conn = get_connection()

# Load cost data as DataFrame
cost_df = load_cost_data(conn, user_id="aws-DEMO-001")
# Columns: date, total_cost
```

## Available Tables

### Cost Data
- `daily_costs` -- one row per user per day (total cost)
- `service_costs` -- one row per user per service per day
- `service_region_costs` -- one row per user per service per region per day

### Metrics (time-series)
- `ec2_metrics` -- hourly: cpu, memory, network, disk
- `rds_metrics` -- hourly: cpu, memory, iops, connections
- `elasticache_metrics` -- hourly: cpu, memory, hits/misses
- `ecs_metrics` -- hourly: cpu, memory, task counts
- `lambda_metrics` -- daily: invocations, duration, errors
- `dynamodb_metrics` -- hourly: consumed RCU/WCU, throttles
- `ebs_metrics` -- hourly: read/write ops and bytes
- `s3_metrics` -- periodic: bucket size, object count
- `nat_gateway_metrics` -- hourly: bytes, packets, connections
- `elb_metrics` -- hourly: requests, HTTP codes, response time

### Inventory (point-in-time)
- `ec2_instances`, `rds_instances`, `elasticache_nodes`, `ecs_services`
- `lambda_functions`, `ebs_volumes`, `s3_buckets`, `dynamodb_tables`
- `nat_gateways`, `elb_instances`

### Reference
- `instance_pricing` -- EC2/RDS/ElastiCache on-demand, reserved, spot prices

## Example: Cost Forecasting

```python
from storage.db import get_connection
from ml_engine.data_prep import load_cost_data

conn = get_connection()
df = load_cost_data(conn, user_id="aws-DEMO-001")

# df is ready for Prophet, SARIMAX, etc.
from prophet import Prophet
model = Prophet()
model.fit(df.rename(columns={"date": "ds", "total_cost": "y"}))
```

## Data Quality

- All numeric values are floats or ints (NULL-safe via `_safe_float`/`_safe_int`)
- Timestamps are ISO format strings (`YYYY-MM-DD HH:MM:SS` or `YYYY-MM-DD`)
- Missing values are stored as NULL
- All tables have indexes on `user_id` and timestamp columns

## Tips

1. **Time Series**: Use daily_costs or service_costs for forecasting
2. **Anomaly Detection**: Use ec2_metrics with all numeric columns as features
3. **Right-sizing**: Combine ec2_instances (inventory) with ec2_metrics (utilization)
4. **Cost Attribution**: Join service_costs with inventory tables by user_id
