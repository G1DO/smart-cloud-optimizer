# Local operations and recovery

This guide covers the single-user development/demo stack. Start it with the
[README](../../README.md#quick-start). Host ports bind to `127.0.0.1`; container
listeners and the Compose network remain accessible within the stack. This does
not repair the [application's trust boundaries](../security/README.md).

## Diagnose the running stack

```bash
docker compose --profile full ps
docker compose logs --tail=100 backend frontend
# If the optional legacy UI is running:
docker compose logs --tail=100 streamlit
```

Open http://127.0.0.1:3000, http://127.0.0.1:8000/health, and, for the `full`
profile, http://127.0.0.1:8501. `/health` is a static liveness response: it does not
verify database contents, AWS permissions, or Gemini availability. Check the
specific failed page/request and backend logs. Redact account identifiers,
credentials, prompts, and personal data before sharing diagnostics.

| Symptom | Checks and next action |
| --- | --- |
| Browser cannot reach API | Check backend health and the frontend's build-time `NEXT_PUBLIC_API_BASE_URL`; it must be browser-reachable. Rebuild the frontend after changing it. CORS permits the two local port-3000 origins. |
| Empty account dashboard | Confirm the selected workspace, stored dates, and sync state. Registration alone does not populate data; demo data belongs to `aws-SYNTHETIC-001`. |
| Incomplete AWS data | Inspect sync status and collector logs for service-level failures. Successful completion does not prove every AWS read succeeded. Review [collection/write behavior](../architecture/data-pipeline.md) before retrying. |
| Sync returns 409 after a restart | An interrupted daemon thread can leave persisted `in_progress`; use the stopped-worker procedure below. |
| AI returns 502 | Check the API key and upstream error in backend logs. Synthetic data does not remove the Gemini key requirement. Enabling the optional token gate also requires a client that sends the token. |
| Settings saved but behavior unchanged | Settings are stored preferences; engines and collection do not consume them. See [active configuration](../reference/configuration.md). |

## State and lifetime

| State | Location | Lifetime |
| --- | --- | --- |
| Manual-run database | `data/cloud_optimizer.db` | Local tracked fixture, modified by application writes; keep runtime changes out of Git |
| Compose database | `/app/data/cloud_optimizer.db` on `optimizer-data` | Seeded from the image when the volume is empty; survives container recreation |
| Web runtime settings | `backend_api/runtime_settings.json` (`/app/backend_api/` in the container) | Separate from SQLite; lost on container recreation in the supplied Compose setup |
| Browser identity | Browser localStorage | Client state, not an authenticated server session |

A rebuild does not replace an existing database volume with the image's fixture.
`docker compose down` retains the volume. **`docker compose down -v` destroys the
Compose database volume**; use it only for an intentional disposable-demo reset
after preserving anything needed. The next start seeds the volume from the image.
The synthetic generator updates matching rows and is not a clean database reset.

## Preserve and restore state

Before collection or other replacement writes, preserve data you need. For a
manual-run database, use SQLite's backup API so committed WAL contents are
included. This example creates a new private directory outside the repository:

```bash
backup_dir=$(mktemp -d)
python - "$backup_dir/cloud_optimizer.db" <<'PYTHON'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

source = Path("data/cloud_optimizer.db").resolve()
with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
    with closing(sqlite3.connect(sys.argv[1])) as dst:
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print(sys.argv[1])
PYTHON
```

For Compose, execute the same backup operation against `/app/data/cloud_optimizer.db`
inside the backend container, write the snapshot to a temporary container path,
and copy that snapshot out with `docker compose cp` before recreating the container.
Copy runtime settings separately if needed. Store snapshots privately: the database
can contain plaintext credentials and account data. An integrity check proves
SQLite structural consistency, not collection completeness or correct values.

To restore, stop every database writer (backend, optional Streamlit, and standalone
collectors/engines), preserve the current database and any WAL/SHM sidecars as a
separate recovery copy, then restore the verified snapshot to the configured path.
Do not pair a restored snapshot with old WAL/SHM files. In Compose retain writable
ownership for UID 10001 on `/app/data`. Restart and verify the intended workspace,
connection state, and data dates through the application. Do not commit snapshots.

## Interrupted sync recovery

Sync runs in a daemon thread in the backend process. It clears previous account
data and commits incrementally. Restarting the backend can stop that thread while
leaving `sync_status = 'in_progress'`, which blocks a new sync. There is no durable
queue or automatic resume; retry starts a fresh replacement collection.

1. Confirm the old worker is no longer running; stop the backend and all other
   writers. Do not clear the status of an active sync.
2. Preserve state as above. Identify the exact connection and workspace from
   `aws_connections`, selecting only `id`, `user_id`, `aws_account_id`, and
   `sync_status`; do not dump its credential columns.
3. On that database, call the existing storage helper with the confirmed ID:

   ```python
   from contextlib import closing
   from storage import get_connection, update_aws_connection_status

   # Use the verified database path and connection ID from the preceding step.
   with closing(get_connection(database_path)) as conn:
       update_aws_connection_status(
           conn, connection_id, "failed", "Interrupted sync; worker stopped",
       )
   ```

   The helper commits and updates `last_sync_at` to the repair time; that timestamp
   is not evidence of a successful collection.
4. Restart the backend, confirm the failed status, and decide whether to retry
   through Account Settings. Inspect backend logs and data coverage afterward;
   changing the status alone does not recover deleted or partial data.

## Runtime settings recovery

The [settings router](../../backend_api/routers/settings.py) replaces the JSON
file atomically and serializes access within one process. It does not coordinate
multiple backend processes. Malformed JSON is renamed to
`runtime_settings.json.corrupt`; reads then use defaults until valid settings are
saved. A syntactically valid file with invalid setting values can still fail model
validation.

Stop the backend, preserve the current file and any corrupt copy outside Git,
then repair or restore a valid user-to-settings mapping. Validate values against
`RuntimeSettings` in the router, restart, and read the affected user's settings.
Repeated malformed reads can replace the previous `.corrupt` copy, so preserve it
before trying recovery. The database volume does not preserve this file; copy it
out before container recreation and restore it into the replacement container.
