# Development Guide

Code style, testing conventions, and project patterns.

For setup and running instructions, see [QUICKSTART.md](QUICKSTART.md).

---

## Testing

Tests live in `tests/`. Current coverage:

| File | What it tests |
| --- | --- |
| `test_config.py` | Root config paths, types, `DB_PATH` |
| `test_date_utils.py` | Month range generation, edge cases |
| `test_ml_utils.py` | Data loading, feature engineering, anomaly detection, forecasters, evaluation |
| `test_storage.py` | Insert/query API, upsert behavior, user isolation, schema creation |
| `test_synthetic.py` | DB table population, schema validation, row counts, determinism, value ranges |

All tests run without AWS credentials or external services.

### Writing new tests

- Put test files in `tests/` named `test_*.py`
- Use pytest fixtures for shared setup
- Mock AWS calls with `unittest.mock` — never hit real APIs in tests
- Test determinism: same seed must produce identical output

---

## Code Style

### Module docstrings

Every `.py` file starts with:

```python
"""
module_name.py — One-line description.

Part of the Smart Cloud Optimizer graduation project.
"""
```

### Imports

PEP 8 order, alphabetical within groups:

```python
# stdlib
import logging
import os
from pathlib import Path

# third-party
import pandas as pd
import numpy as np

# local
from storage import get_connection, get_daily_costs
```

No inline imports inside functions.

### Type hints

All function signatures have type annotations:

```python
def fetch_daily_cost(self, start: str, end: str) -> pd.DataFrame:
```

### Docstrings

Google style on all public functions:

```python
def get_last_n_months(n: int) -> list[tuple[str, str]]:
    """Return date ranges for the last N months.

    Args:
        n: Number of months to look back.

    Returns:
        List of (start_date, end_date) string tuples in YYYY-MM-DD format.
    """
```

### Logging

- Use `logging` module everywhere. No `print()`.
- Each module: `logger = logging.getLogger(__name__)`
- Levels: `info` for progress, `warning` for recoverable errors, `error` for failures

### Constants

- Extract magic numbers to named constants at module top
- Use UPPER_SNAKE_CASE

### Strings

- f-strings everywhere. No `%` formatting or `.format()`.

---

## Project Conventions

### Data storage

All data is stored in SQLite via `storage/db.py`. The database lives at `data/cloud_optimizer.db`. All tables use `INSERT OR REPLACE` for upsert on primary keys. Every table is keyed by `user_id` for multi-tenant isolation.

### Error handling

All AWS API calls and file I/O are wrapped in try/except. Failures log a warning and skip — one failed metric doesn't stop the rest.

### Two config files

`config.py` (root) = project settings. `aws_collector/config.py` = boto3 clients. They don't overlap.

### Data artifact

```text
data/
  cloud_optimizer.db   ← single SQLite database (all data)
```

Both the data generator and AWS collector write to the same DB. Downstream modules read via `storage.get_*()` and don't know which source produced the data.
