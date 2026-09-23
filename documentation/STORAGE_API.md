# Storage API Reference

The `storage` package exports the shared SQLite interface from
[storage/__init__.py](../storage/__init__.py). Implementations, accepted row fields,
and SQL live in [storage/db.py](../storage/db.py). Some HTTP routes also issue
SQL directly; see [Architecture](ARCHITECTURE.md).

## Current signatures

Generate the public function reference from the checked-out code:

```bash
python - <<'PYTHON'
import inspect
import storage

for name in storage.__all__:
    value = getattr(storage, name)
    if inspect.isfunction(value):
        print(f"{name}{inspect.signature(value)}")
PYTHON
```

For a function's field requirements and behavior, use, for example,
`python -m pydoc storage.insert_ec2_instances`. Get exact table keys and types
from the [generated schema](DATA_SCHEMAS.md).

Filters are function-specific: inventory reads accept only `conn` and `user_id`;
cost queries use `start_date`/`end_date`; EC2/RDS metrics use `start`/`end`.
Other metric getters accept a resource filter but no time range.
ElastiCache uses `cache_cluster_id`, ECS uses `service_name`, and Lambda metrics
use `date`. Pricing reads accept `service` and `instance_type`, without a user ID.
Do not assume every getter accepts arbitrary keyword filters.

## Transaction contract

- Data `insert_*` functions return an inserted-row count and do not commit.
  Data `get_*` functions return lists of dictionaries and do not commit.
- Commit after batching data inserts; roll back on failure and close the
  connection when finished. SQLite's connection context manager does not close it.
- Schema, user, authentication/profile, and AWS connection mutation helpers
  manage their own commits. These calls are not part of a caller-controlled
  batch of data inserts.
- `ensure_schema()` creates missing objects and applies supported additive
  credential migrations. `create_schema()` drops and recreates all tables;
  use it only for disposable fixtures.
- `clear_user_data()` commits deletion of a user's data/results while retaining
  `users`, `aws_connections`, and global `instance_pricing`.

`get_connection(db_path=None)` defaults to the configured demo DB, enables WAL
and foreign keys, and sets a 10-second busy timeout. Many inventory/metric/cost
inserts use `INSERT OR REPLACE`; result inserts have their own semantics in the
source. Sync and optimization can delete previous results; see
[Data pipeline](DATA_PIPELINE.md) and [Optimizer](optimizer.md#usage).

## Disposable example

This example creates a temporary database, inserts cost data, reads it back,
and closes the connection without touching the tracked database:

```python
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from storage import (
    get_connection, ensure_schema, ensure_user,
    insert_daily_costs, get_daily_costs,
)

with TemporaryDirectory() as directory:
    with closing(get_connection(Path(directory) / "example.db")) as conn:
        ensure_schema(conn)
        user_id = ensure_user(conn, "EXAMPLE-001")
        insert_daily_costs(conn, user_id, [
            {"date": "2024-01-15", "total_cost": 125.50},
        ])
        conn.commit()
        print(get_daily_costs(
            conn, user_id, start_date="2024-01-01", end_date="2024-01-31",
        ))
```

## Identity and credentials

`register_user()` creates a `usr-` identity; `ensure_user()` creates an
`aws-<account_id>` workspace. Connection rows link an owner to an AWS account.
`get_aws_connections()` returns stored credentials to Python callers; HTTP
routes must remove secrets before returning responses. User-scoped queries
filter the supplied ID but do not authenticate it. See the
[security notes](../README.md#known-limitations--security-notes).

`INSTANCE_SPECS` and `SERVICE_NAME_MAP` are also exported by `storage`; their
canonical definitions are in [cloud_optimizer/config.py](../cloud_optimizer/config.py).
