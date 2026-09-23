# Data Pipeline

## Live AWS collection

The Next.js **Account Settings → Connections** flow validates supplied access
keys through the backend's STS call. Sync starts a background
`CollectorRunner.from_connection()`, using stored keys or legacy role
credentials. The standalone `python -m aws_collector.main` entry point uses
boto3's configured credentials.

The runner clears previous data for the selected account before collecting
12 months of history. It processes month ranges **newest first**, collecting
costs, service inventory/metrics, and pricing, with incremental commits. A
failure can leave partial data; sync is not an atomic replacement.

Per-service collectors live in [aws_collector/collectors/](../aws_collector/collectors/).
Their writes use `storage.insert_*()`. Many data tables use
`INSERT OR REPLACE` on composite primary keys to update matching observations.
Global instance pricing has no `user_id`; account data is keyed by user.
See [Storage API](STORAGE_API.md) for transaction ownership and
[Data schemas](DATA_SCHEMAS.md) for keys.

Collectors log individual API failures where they can continue. Consult sync
status and backend logs if data is incomplete. Runtime AWS credentials and
account data must stay out of commits; see the
[security notes](../README.md#known-limitations--security-notes).

## Synthetic data

[data_generation/synthetic.py](../data_generation/synthetic.py) is tracked and
used by tests and the demo seeder. Its functions generate inventory, metrics,
costs, and pricing; the CLI maps generator columns into storage records and
commits the results. Current fixtures are generated in code without downloading
external research datasets.

```bash
python -m data_generation.synthetic --help
```

The CLI writes to the configured `data/cloud_optimizer.db`; it has no
`--db-path` option. Seeding overwrites matching target-user rows and global
instance-pricing rows. It leaves unmatched rows and other users' data in place,
so running it on an existing database is not a clean reset. Use a disposable
checkout/database for experiments.

Dates are relative to the execution date. The same seed and day count reproduce
random values for that date; a later execution shifts timestamps. The committed
historical demo fixture is not a byte-for-byte output contract for this generator.
[Data resources](DATA_RESOURCES.md) records research sources separately.

## Consumers

The TypeScript UI reads JSON from FastAPI. The API routes call storage helpers
and engines; some routes also use direct SQL as described in
[Architecture](ARCHITECTURE.md). The legacy Streamlit UI calls Python modules
directly.

Forecasting reads historical series. Optimization reads inventory, observed
metrics, and prices and replaces stored recommendations. Its write and budget
semantics are documented in [Optimizer](optimizer.md#usage). These consumers
share the same database schema regardless of how observations were collected.
