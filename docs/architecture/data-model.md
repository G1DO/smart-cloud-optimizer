# Data Schemas

The authoritative SQLite schema and additive migrations live in
[storage/db.py](../../storage/db.py). Generate exact table, column, key, and index
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
into the AWS workspace. Demo data uses `aws-SYNTHETIC-001`. Filtering these IDs is not HTTP authorization.

Passwords use PBKDF2-HMAC-SHA256. Connection access keys and session tokens are
stored in plaintext, and storage reads expose those columns to Python callers.
See `docs/security/threat-model.md`.

## Schema compatibility check

`ensure_schema()` is additive only: it creates missing tables/indexes and adds
the supported AWS credential columns
(`aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`,
`auth_type`) to older databases. It never drops data or reconciles arbitrary
older table definitions. `create_schema()` drops and recreates all tables and
belongs only in disposable fixtures.

Recorded proof (2026-10-20, `main`):
fresh `:memory:` init holds 30 tables; migration adds the 4 supported
credential columns and preserves both users; temp-copy backup/restore
round-trip `integrity_check` ok. Re-run `poe check:schema` / CI `verify`
after any schema change.

Re-run the script after any schema or migration change.

For insert/query behavior see `storage/db.py` and `storage/__init__.py`.
Runtime settings are a separate JSON file `backend_api/runtime_settings.json`, lost on container recreation.
