# Storage API Reference

The `storage/` module is the single data gateway for the entire project. All modules read and write through this package.

---

## Quick Reference

```python
from storage import get_connection, ensure_schema, insert_daily_costs, get_daily_costs

conn = get_connection()
ensure_schema(conn)

# Write data
insert_daily_costs(conn, user_id, [{"date": "2024-01-15", "total_cost": 125.50}])
conn.commit()  # Caller must commit!

# Read data
costs = get_daily_costs(conn, user_id, start_date="2024-01-01", end_date="2024-01-31")
```

---

## Transaction Contract

- `insert_*` / `get_*` functions do **NOT** call `conn.commit()`
- The caller is responsible for committing after one or more inserts
- This allows batching multiple inserts into a single transaction
- Admin functions (`create_schema`, `ensure_user`, `clear_user_data`) commit internally

---

## Connection & Schema

| Function | Description |
|----------|-------------|
| `get_connection(db_path=None)` | Open SQLite connection with WAL mode, foreign keys enabled |
| `ensure_schema(conn)` | Create tables/indexes if missing (non-destructive) |
| `create_schema(conn)` | Drop + recreate all tables (destructive, tests/dev only) |
| `ensure_user(conn, account_id)` | Create user if not exists, returns `user_id` |
| `clear_user_data(conn, user_id)` | Delete all data for a user (keeps user record) |

---

## Authentication Functions

Password hashing uses HMAC-SHA256 with a random 32-byte salt.

| Function | Description |
|----------|-------------|
| `hash_password(password)` | Hash a plaintext password, returns `salt:hash` string |
| `verify_password(password, stored_hash)` | Verify a password against a stored hash |
| `register_user(conn, email, password, profile_name)` | Create a new user account, returns `user_id` (`usr-` + 12 hex). Raises `ValueError` on duplicate email. Commits internally. |
| `authenticate_user(conn, email, password)` | Verify credentials. Returns user dict on success, `None` on failure. Updates `last_login_at`. |
| `get_user_by_id(conn, user_id)` | Fetch user record by ID. Returns dict or `None`. |
| `update_user_profile(conn, user_id, profile_name)` | Update display name. Returns `True` on success. Commits internally. |

---

## AWS Connection CRUD

Manages per-user AWS account connections. Each connection stores an IAM role ARN for cross-account access.

| Function | Description |
|----------|-------------|
| `add_aws_connection(conn, user_id, aws_account_id, iam_role_arn, ...)` | Add a new AWS connection. Optional: `connection_name`, `external_id`, `aws_region`. Returns row ID. Commits internally. Unique constraint on `(user_id, aws_account_id)`. |
| `get_aws_connections(conn, user_id)` | Get all connections for a user. Returns list of dicts. |
| `delete_aws_connection(conn, connection_id, user_id)` | Delete a connection. Scoped to user (users cannot delete other users' connections). Returns `True` on success. |
| `update_aws_connection_status(conn, connection_id, status, error_message)` | Update sync status (`never`, `success`, `failed`, `in_progress`). Sets `last_sync_at`. |

---

## Insert Functions (24)

All insert functions have the signature:

```python
def insert_*(conn, user_id: str, rows: list[dict]) -> None
```

### Cost Data

| Function | Table | Key Columns |
|----------|-------|-------------|
| `insert_daily_costs` | daily_costs | date, total_cost |
| `insert_service_costs` | service_costs | date, service, daily_cost |
| `insert_service_region_costs` | service_region_costs | date, service, region, daily_cost |

### Inventory (10 services)

| Function | Table | Primary Key |
|----------|-------|-------------|
| `insert_ec2_instances` | ec2_instances | instance_id |
| `insert_rds_instances` | rds_instances | db_instance_id |
| `insert_elasticache_nodes` | elasticache_nodes | node_id |
| `insert_ecs_services` | ecs_services | service_arn |
| `insert_lambda_functions` | lambda_functions | function_name |
| `insert_ebs_volumes` | ebs_volumes | volume_id |
| `insert_s3_buckets` | s3_buckets | bucket_name |
| `insert_dynamodb_tables` | dynamodb_tables | table_name |
| `insert_nat_gateways` | nat_gateways | nat_gateway_id |
| `insert_elb_instances` | elb_instances | elb_arn |

### Metrics (10 services)

| Function | Table | Primary Key |
|----------|-------|-------------|
| `insert_ec2_metrics` | ec2_metrics | (timestamp, instance_id) |
| `insert_rds_metrics` | rds_metrics | (timestamp, db_instance_id) |
| `insert_elasticache_metrics` | elasticache_metrics | (timestamp, node_id) |
| `insert_ecs_metrics` | ecs_metrics | (timestamp, service_arn) |
| `insert_lambda_metrics` | lambda_metrics | (timestamp, function_name) |
| `insert_ebs_metrics` | ebs_metrics | (timestamp, volume_id) |
| `insert_s3_metrics` | s3_metrics | (timestamp, bucket_name) |
| `insert_dynamodb_metrics` | dynamodb_metrics | (timestamp, table_name) |
| `insert_nat_gateway_metrics` | nat_gateway_metrics | (timestamp, nat_gateway_id) |
| `insert_elb_metrics` | elb_metrics | (timestamp, elb_arn) |

### Pricing & Analytics

| Function | Table |
|----------|-------|
| `insert_instance_pricing` | instance_pricing |
| `insert_forecasts` | forecasts |
| `insert_recommendations` | recommendations |
| `insert_anomalies` | anomalies |
| `insert_ai_recommendations` | ai_recommendations |

---

## Query Functions (24)

All query functions have the signature:

```python
def get_*(conn, user_id: str, **filters) -> list[dict]
```

Common filters:

- `start_date`, `end_date` — Filter by date range (YYYY-MM-DD)
- `instance_id`, `function_name`, etc. — Filter by resource ID
- `region` — Filter by AWS region

### Cost Data

| Function | Filters |
|----------|---------|
| `get_daily_costs` | start_date, end_date |
| `get_service_costs` | start_date, end_date, service |
| `get_service_region_costs` | start_date, end_date, service, region |

### Inventory

| Function | Filters |
|----------|---------|
| `get_ec2_instances` | instance_id, region |
| `get_rds_instances` | db_instance_id, region |
| `get_elasticache_nodes` | node_id, region |
| `get_ecs_services` | service_arn, region |
| `get_lambda_functions` | function_name, region |
| `get_ebs_volumes` | volume_id, region |
| `get_s3_buckets` | bucket_name |
| `get_dynamodb_tables` | table_name, region |
| `get_nat_gateways` | nat_gateway_id, region |
| `get_elb_instances` | elb_arn, region |

### Metrics

| Function | Filters |
|----------|---------|
| `get_ec2_metrics` | start_date, end_date, instance_id |
| `get_rds_metrics` | start_date, end_date, db_instance_id |
| `get_elasticache_metrics` | start_date, end_date, node_id |
| `get_ecs_metrics` | start_date, end_date, service_arn |
| `get_lambda_metrics` | start_date, end_date, function_name |
| `get_ebs_metrics` | start_date, end_date, volume_id |
| `get_s3_metrics` | start_date, end_date, bucket_name |
| `get_dynamodb_metrics` | start_date, end_date, table_name |
| `get_nat_gateway_metrics` | start_date, end_date, nat_gateway_id |
| `get_elb_metrics` | start_date, end_date, elb_arn |

### Pricing & Analytics

| Function | Filters |
|----------|---------|
| `get_instance_pricing` | month, service, instance_type, pricing_model |
| `get_forecasts` | metric_type |
| `get_recommendations` | — |
| `get_anomalies` | start_date, end_date |
| `get_ai_recommendations` | — |

---

## Usage Examples

### Batch Insert with Single Commit

```python
from storage import get_connection, ensure_schema, insert_ec2_instances, insert_ec2_metrics

conn = get_connection()
ensure_schema(conn)
user_id = "user-123"

# Insert inventory
insert_ec2_instances(conn, user_id, [
    {"instance_id": "i-abc123", "instance_type": "t3.micro", "state": "running", ...}
])

# Insert metrics
insert_ec2_metrics(conn, user_id, [
    {"timestamp": "2024-01-15T12:00:00", "instance_id": "i-abc123", "cpu_utilization": 45.2, ...}
])

# Single commit for both
conn.commit()
```

### Query with Filters

```python
from storage import get_connection, get_daily_costs, get_ec2_metrics

conn = get_connection()

# Get January costs
costs = get_daily_costs(conn, user_id, start_date="2024-01-01", end_date="2024-01-31")

# Get metrics for specific instance
metrics = get_ec2_metrics(conn, user_id, instance_id="i-abc123", start_date="2024-01-01")
```

### Multi-User Isolation

Every table has a `user_id` foreign key. Data is automatically isolated:

```python
# User A's data
costs_a = get_daily_costs(conn, user_id="user-A")

# User B's data (completely separate)
costs_b = get_daily_costs(conn, user_id="user-B")
```

---

## Constants

Exported from `storage`:

- `INSTANCE_SPECS` — Dict of EC2 instance types with vCPUs, memory, etc.
- `SERVICE_NAME_MAP` — Maps AWS service names to short DB names

---

## Database Location

Default: `data/cloud_optimizer.db` (set by `config.DB_PATH`)

SQLite features enabled:

- WAL mode (Write-Ahead Logging) for concurrent reads
- Foreign keys enforced
- `INSERT OR REPLACE` for upsert on primary keys
