# Data Schemas

The authoritative SQLite schema and additive migrations live in
[storage/db.py](../storage/db.py). Generate exact table, column, key, and index
definitions from the implemented initializer instead of maintaining a separate
SQL copy. From the repository root with Python dependencies installed:

```bash
python - <<'PYTHON'
import sqlite3
from contextlib import closing
from storage import ensure_schema

with closing(sqlite3.connect(":memory:")) as conn:
    ensure_schema(conn)
    for (sql,) in conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name"
    ):
        print(sql + ";\n")
PYTHON
```

This prints the current schema without opening or changing the committed demo
DB. It describes a fresh database; `ensure_schema()` only creates missing
objects and adds the supported AWS credential columns to existing databases.
It does not reconcile arbitrary older table definitions.

## Data model

| Area | Tables | Relationship |
| --- | --- | --- |
| Identity and connections | `users`, `aws_connections` | A user can own multiple connections, unique by `(user_id, aws_account_id)` |
| Costs | `daily_costs`, `service_costs`, `service_region_costs` | Daily user totals and service/region breakdowns |
| Inventory | `ec2_instances`, `rds_instances`, `elasticache_nodes`, `ecs_services`, `lambda_functions`, `ebs_volumes`, `s3_buckets`, `dynamodb_tables`, `nat_gateways`, `elb_instances` | Resource identity and `user_id` form composite primary keys |
| Metrics | `ec2_metrics`, `rds_metrics`, `elasticache_metrics`, `ecs_metrics`, `lambda_metrics`, `ebs_metrics`, `s3_metrics`, `dynamodb_metrics`, `nat_gateway_metrics`, `elb_metrics` | Observations keyed by time, resource, and user; Lambda uses `date`, other metrics use `timestamp` |
| Pricing | `instance_pricing` | Shared reference prices, with no `user_id` |
| Results | `forecasts`, `recommendations`, `anomalies`, `ai_recommendations` | User-scoped engine output |

User IDs represent both registered identities (`usr-…`) and AWS workspaces
(`aws-<account_id>`). Web connections belong to the AWS workspace; legacy
Streamlit connections belong to the registered owner. Collection writes data
into the AWS workspace. See
[Connection identity and verification](ARCHITECTURE.md#connection-identity-and-verification).
Demo data uses `aws-SYNTHETIC-001`. Filtering these IDs is not HTTP authorization.

Passwords use PBKDF2-HMAC-SHA256. Connection access keys and session tokens are
stored in plaintext, and storage reads expose those columns to Python callers.
See the [security limitations](../README.md#known-limitations--security-notes).

For insert/query behavior and commit ownership, see [Storage API](STORAGE_API.md).
For data replacement during sync or seeding, see [Data pipeline](DATA_PIPELINE.md).
Runtime settings are a separate JSON file, described in
[Architecture](ARCHITECTURE.md#runtime-settings).
