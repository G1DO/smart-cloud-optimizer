"""db.py — SQLite storage layer for Smart Cloud Optimizer.

Single data gateway: all modules read/write through insert_*/get_* functions.
No CSV parsing — callers provide list[dict] data directly.

Transaction contract
--------------------
* ``insert_*`` / ``get_*`` functions do **not** call ``conn.commit()``.
* The caller is responsible for committing after one or more inserts.
  This allows batching multiple inserts into a single transaction.
* ``create_schema``, ``ensure_user``, and ``clear_user_data`` commit
  internally because they perform admin operations.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional

import config
from config import INSTANCE_SPECS, SERVICE_NAME_MAP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
_SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id           TEXT PRIMARY KEY,
    email             TEXT    NOT NULL UNIQUE,
    password_hash     TEXT    NOT NULL,
    profile_name      TEXT,
    user_type         TEXT    NOT NULL DEFAULT 'new',
    avg_monthly_spend REAL,
    num_services      INTEGER,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at     TEXT,
    CHECK (user_type IN ('new','connected','active','inactive'))
);

CREATE TABLE IF NOT EXISTS aws_connections (
    user_id           TEXT PRIMARY KEY,
    aws_account_id    TEXT    NOT NULL,
    iam_role_arn      TEXT    NOT NULL,
    external_id       TEXT,
    aws_region        TEXT    NOT NULL DEFAULT 'us-east-1',
    access_verified   INTEGER NOT NULL DEFAULT 0,
    last_sync_at      TEXT,
    sync_status       TEXT    NOT NULL DEFAULT 'never',
    error_message     TEXT,
    connected_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (sync_status IN ('never','success','failed','in_progress'))
);

CREATE TABLE IF NOT EXISTS daily_costs (
    date              TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    total_cost        REAL    NOT NULL,
    PRIMARY KEY (date, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_daily_costs_user ON daily_costs(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_costs_date ON daily_costs(date);

CREATE TABLE IF NOT EXISTS service_costs (
    date              TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,
    daily_cost        REAL    NOT NULL,
    PRIMARY KEY (date, user_id, service),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_service_costs_user ON service_costs(user_id, service);
CREATE INDEX IF NOT EXISTS idx_service_costs_date ON service_costs(date);

CREATE TABLE IF NOT EXISTS service_region_costs (
    date              TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,
    region            TEXT    NOT NULL,
    daily_cost        REAL    NOT NULL,
    PRIMARY KEY (date, user_id, service, region),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_service_region_costs_user ON service_region_costs(user_id);
CREATE INDEX IF NOT EXISTS idx_service_region_costs_date ON service_region_costs(date);

CREATE TABLE IF NOT EXISTS ec2_instances (
    instance_id       TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    instance_type     TEXT    NOT NULL,
    vcpus             INTEGER,
    memory_gb         REAL,
    state             TEXT    NOT NULL DEFAULT 'running',
    launch_date       TEXT    NOT NULL,
    region            TEXT    NOT NULL DEFAULT 'us-east-1',
    availability_zone TEXT    NOT NULL DEFAULT 'us-east-1a',
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',
    monthly_cost      REAL,
    private_ip        TEXT,
    public_ip         TEXT,
    vpc_id            TEXT,
    subnet_id         TEXT,
    ami_id            TEXT,
    tags              TEXT,
    PRIMARY KEY (instance_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (state IN ('running','stopped','terminated')),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr','spot'))
);
CREATE INDEX IF NOT EXISTS idx_ec2_instances_user ON ec2_instances(user_id);

CREATE TABLE IF NOT EXISTS ec2_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    instance_id       TEXT    NOT NULL,
    cpu_utilization   REAL    NOT NULL,
    cpu_max           REAL,
    memory_utilization REAL,
    network_in_kbps   REAL    NOT NULL DEFAULT 0,
    network_out_kbps  REAL    NOT NULL DEFAULT 0,
    disk_read_kbps    REAL    NOT NULL DEFAULT 0,
    disk_write_kbps   REAL    NOT NULL DEFAULT 0,
    disk_read_ops     REAL    DEFAULT 0,
    disk_write_ops    REAL    DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, instance_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_ec2_metrics_user     ON ec2_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_ec2_metrics_ts       ON ec2_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_ec2_metrics_instance ON ec2_metrics(instance_id);

CREATE TABLE IF NOT EXISTS rds_instances (
    db_instance_id    TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    db_instance_class TEXT    NOT NULL,
    engine            TEXT    NOT NULL,
    engine_version    TEXT,
    storage_gb        INTEGER NOT NULL,
    storage_type      TEXT    NOT NULL DEFAULT 'gp3',
    multi_az          INTEGER NOT NULL DEFAULT 0,
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',
    monthly_cost      REAL,
    endpoint          TEXT,
    port              INTEGER,
    backup_retention_period INTEGER,
    deletion_protection INTEGER DEFAULT 0,
    PRIMARY KEY (db_instance_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr'))
);
CREATE INDEX IF NOT EXISTS idx_rds_instances_user ON rds_instances(user_id);

CREATE TABLE IF NOT EXISTS rds_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    db_instance_id    TEXT    NOT NULL,
    cpu_utilization   REAL    NOT NULL,
    memory_utilization REAL,
    read_iops         REAL    NOT NULL DEFAULT 0,
    write_iops        REAL    NOT NULL DEFAULT 0,
    connections       INTEGER NOT NULL DEFAULT 0,
    free_storage_gb   REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, db_instance_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_rds_metrics_user ON rds_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_rds_metrics_ts   ON rds_metrics(timestamp);

CREATE TABLE IF NOT EXISTS elasticache_nodes (
    cache_cluster_id  TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    cache_node_type   TEXT    NOT NULL,
    engine            TEXT    NOT NULL,
    engine_version    TEXT,
    num_cache_nodes   INTEGER NOT NULL DEFAULT 1,
    pricing_model     TEXT    NOT NULL DEFAULT 'on-demand',
    monthly_cost      REAL,
    PRIMARY KEY (cache_cluster_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (engine IN ('redis','memcached')),
    CHECK (pricing_model IN ('on-demand','reserved-1yr','reserved-3yr'))
);
CREATE INDEX IF NOT EXISTS idx_elasticache_nodes_user ON elasticache_nodes(user_id);

CREATE TABLE IF NOT EXISTS elasticache_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    cache_cluster_id  TEXT    NOT NULL,
    cpu_utilization   REAL    NOT NULL,
    memory_utilization REAL   NOT NULL,
    curr_connections  INTEGER NOT NULL DEFAULT 0,
    cache_hits        INTEGER NOT NULL DEFAULT 0,
    cache_misses      INTEGER NOT NULL DEFAULT 0,
    evictions         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, cache_cluster_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_elasticache_metrics_user ON elasticache_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_elasticache_metrics_ts   ON elasticache_metrics(timestamp);

CREATE TABLE IF NOT EXISTS ecs_services (
    service_name      TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    cluster_name      TEXT    NOT NULL,
    launch_type       TEXT    NOT NULL DEFAULT 'FARGATE',
    desired_count     INTEGER NOT NULL DEFAULT 1,
    cpu               INTEGER NOT NULL,
    memory_mb         INTEGER NOT NULL,
    monthly_cost      REAL,
    PRIMARY KEY (service_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (launch_type IN ('FARGATE','EC2'))
);
CREATE INDEX IF NOT EXISTS idx_ecs_services_user ON ecs_services(user_id);

CREATE TABLE IF NOT EXISTS ecs_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    service_name      TEXT    NOT NULL,
    cluster_name      TEXT    NOT NULL,
    cpu_utilization   REAL    NOT NULL,
    memory_utilization REAL   NOT NULL,
    running_task_count INTEGER NOT NULL DEFAULT 1,
    desired_task_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (timestamp, user_id, service_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_ecs_metrics_user ON ecs_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_ecs_metrics_ts   ON ecs_metrics(timestamp);

CREATE TABLE IF NOT EXISTS lambda_functions (
    function_name     TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    runtime           TEXT    NOT NULL,
    memory_mb         INTEGER,
    timeout_sec       INTEGER NOT NULL DEFAULT 30,
    avg_daily_invocations INTEGER NOT NULL DEFAULT 0,
    avg_duration_ms   REAL    NOT NULL DEFAULT 0,
    monthly_cost      REAL,
    code_size         INTEGER,
    handler           TEXT,
    last_modified     TEXT,
    PRIMARY KEY (function_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_lambda_functions_user ON lambda_functions(user_id);

CREATE TABLE IF NOT EXISTS lambda_metrics (
    date              TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    function_name     TEXT    NOT NULL,
    invocations       INTEGER NOT NULL DEFAULT 0,
    avg_duration_ms   REAL    NOT NULL DEFAULT 0,
    max_duration_ms   REAL    NOT NULL DEFAULT 0,
    errors            INTEGER NOT NULL DEFAULT 0,
    throttles         INTEGER NOT NULL DEFAULT 0,
    avg_memory_used_mb REAL   NOT NULL DEFAULT 0,
    memory_allocated_mb INTEGER,
    PRIMARY KEY (date, user_id, function_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_lambda_metrics_user ON lambda_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_lambda_metrics_date ON lambda_metrics(date);

CREATE TABLE IF NOT EXISTS ebs_volumes (
    volume_id         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    volume_type       TEXT    NOT NULL,
    size_gb           INTEGER NOT NULL,
    iops              INTEGER,
    throughput_mbps   INTEGER,
    attached_instance_id TEXT,
    state             TEXT    NOT NULL DEFAULT 'in-use',
    monthly_cost      REAL,
    encrypted         INTEGER DEFAULT 0,
    create_time       TEXT,
    PRIMARY KEY (volume_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (state IN ('in-use','available'))
);
CREATE INDEX IF NOT EXISTS idx_ebs_volumes_user ON ebs_volumes(user_id);

CREATE TABLE IF NOT EXISTS ebs_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    volume_id         TEXT    NOT NULL,
    read_ops          REAL    NOT NULL DEFAULT 0,
    write_ops         REAL    NOT NULL DEFAULT 0,
    read_bytes        REAL    NOT NULL DEFAULT 0,
    write_bytes       REAL    NOT NULL DEFAULT 0,
    idle_time_seconds REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, volume_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_ebs_metrics_user ON ebs_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_ebs_metrics_ts   ON ebs_metrics(timestamp);

CREATE TABLE IF NOT EXISTS s3_buckets (
    bucket_name       TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    storage_class     TEXT    NOT NULL DEFAULT 'STANDARD',
    size_gb           REAL,
    num_objects       INTEGER NOT NULL DEFAULT 0,
    avg_daily_get_requests INTEGER NOT NULL DEFAULT 0,
    avg_daily_put_requests INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL,
    region            TEXT,
    versioning        TEXT,
    encryption        TEXT,
    PRIMARY KEY (bucket_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_s3_buckets_user ON s3_buckets(user_id);

CREATE TABLE IF NOT EXISTS s3_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    bucket_name       TEXT    NOT NULL,
    bucket_size_bytes REAL    DEFAULT 0,
    number_of_objects INTEGER DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, bucket_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_s3_metrics_user ON s3_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_s3_metrics_ts   ON s3_metrics(timestamp);

CREATE TABLE IF NOT EXISTS dynamodb_tables (
    table_name        TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    capacity_mode     TEXT    NOT NULL,
    provisioned_rcu   INTEGER DEFAULT NULL,
    provisioned_wcu   INTEGER DEFAULT NULL,
    storage_gb        REAL    NOT NULL DEFAULT 0,
    item_count        INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL,
    PRIMARY KEY (table_name, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (capacity_mode IN ('PROVISIONED','ON_DEMAND'))
);
CREATE INDEX IF NOT EXISTS idx_dynamodb_tables_user ON dynamodb_tables(user_id);

CREATE TABLE IF NOT EXISTS dynamodb_metrics (
    timestamp              TEXT    NOT NULL,
    user_id                TEXT    NOT NULL,
    table_name             TEXT    NOT NULL,
    consumed_read_units    REAL    NOT NULL DEFAULT 0,
    consumed_write_units   REAL    NOT NULL DEFAULT 0,
    provisioned_read_units REAL    DEFAULT NULL,
    provisioned_write_units REAL   DEFAULT NULL,
    throttled_requests     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, table_name),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_dynamodb_metrics_user ON dynamodb_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_dynamodb_metrics_ts   ON dynamodb_metrics(timestamp);

CREATE TABLE IF NOT EXISTS nat_gateways (
    nat_gateway_id    TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    vpc_id            TEXT    NOT NULL,
    subnet_id         TEXT    NOT NULL,
    state             TEXT    NOT NULL DEFAULT 'available',
    monthly_hours     REAL    NOT NULL DEFAULT 730,
    monthly_data_processed_gb REAL NOT NULL DEFAULT 0,
    monthly_cost      REAL,
    PRIMARY KEY (nat_gateway_id, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_nat_gateways_user ON nat_gateways(user_id);

CREATE TABLE IF NOT EXISTS nat_gateway_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    nat_gateway_id    TEXT    NOT NULL,
    bytes_in          REAL    NOT NULL DEFAULT 0,
    bytes_out         REAL    NOT NULL DEFAULT 0,
    packets_in        INTEGER NOT NULL DEFAULT 0,
    packets_out       INTEGER NOT NULL DEFAULT 0,
    active_connections INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, nat_gateway_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_nat_gateway_metrics_user ON nat_gateway_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_nat_gateway_metrics_ts   ON nat_gateway_metrics(timestamp);

CREATE TABLE IF NOT EXISTS elb_instances (
    elb_arn           TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    elb_name          TEXT    NOT NULL,
    elb_type          TEXT    NOT NULL,
    scheme            TEXT    NOT NULL DEFAULT 'internet-facing',
    target_count      INTEGER NOT NULL DEFAULT 0,
    healthy_target_count INTEGER NOT NULL DEFAULT 0,
    avg_daily_requests INTEGER NOT NULL DEFAULT 0,
    monthly_cost      REAL,
    dns_name          TEXT,
    vpc_id            TEXT,
    state             TEXT    DEFAULT 'active',
    created_time      TEXT,
    PRIMARY KEY (elb_arn, user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (elb_type IN ('ALB','NLB','CLB')),
    CHECK (scheme IN ('internet-facing','internal'))
);
CREATE INDEX IF NOT EXISTS idx_elb_instances_user ON elb_instances(user_id);

CREATE TABLE IF NOT EXISTS elb_metrics (
    timestamp         TEXT    NOT NULL,
    user_id           TEXT    NOT NULL,
    elb_arn           TEXT    NOT NULL,
    request_count     INTEGER NOT NULL DEFAULT 0,
    active_connections INTEGER NOT NULL DEFAULT 0,
    new_connections   INTEGER NOT NULL DEFAULT 0,
    processed_bytes   REAL    NOT NULL DEFAULT 0,
    http_2xx          INTEGER NOT NULL DEFAULT 0,
    http_3xx          INTEGER NOT NULL DEFAULT 0,
    http_4xx          INTEGER NOT NULL DEFAULT 0,
    http_5xx          INTEGER NOT NULL DEFAULT 0,
    target_response_time_avg REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (timestamp, user_id, elb_arn),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_elb_metrics_user ON elb_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_elb_metrics_ts   ON elb_metrics(timestamp);

CREATE TABLE IF NOT EXISTS instance_pricing (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    service               TEXT    NOT NULL,
    instance_type         TEXT    NOT NULL,
    vcpus                 INTEGER,
    memory_gb             REAL,
    category              TEXT,
    on_demand_hourly      REAL    NOT NULL,
    reserved_1yr_hourly   REAL,
    reserved_3yr_hourly   REAL,
    spot_hourly           REAL,
    on_demand_monthly     REAL    NOT NULL,
    reserved_1yr_monthly  REAL,
    reserved_3yr_monthly  REAL,
    spot_monthly          REAL,
    UNIQUE(service, instance_type)
);
CREATE INDEX IF NOT EXISTS idx_pricing_service ON instance_pricing(service);
CREATE INDEX IF NOT EXISTS idx_pricing_type    ON instance_pricing(instance_type);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    app_type          TEXT    NOT NULL,
    expected_users    INTEGER,
    uptime_hours      INTEGER,
    importance        TEXT,
    budget_monthly    REAL,
    extra_requirements TEXT,
    prompt_text       TEXT    NOT NULL,
    recommended_setup TEXT    NOT NULL,
    estimated_cost    REAL    NOT NULL,
    explanation       TEXT,
    llm_model         TEXT    NOT NULL,
    llm_response_raw  TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_ai_rec_user ON ai_recommendations(user_id);

CREATE TABLE IF NOT EXISTS forecasts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT,
    forecast_date     TEXT    NOT NULL,
    predicted_cost    REAL    NOT NULL,
    lower_bound       REAL,
    upper_bound       REAL,
    model_type        TEXT    NOT NULL,
    model_params      TEXT,
    mae               REAL,
    mape              REAL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_forecasts_user    ON forecasts(user_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_date    ON forecasts(forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_service ON forecasts(user_id, service);

CREATE TABLE IF NOT EXISTS recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT    NOT NULL,
    resource_id       TEXT    NOT NULL,
    recommendation_type TEXT  NOT NULL,
    current_config    TEXT    NOT NULL,
    recommended_config TEXT   NOT NULL,
    current_monthly_cost   REAL NOT NULL,
    estimated_monthly_cost REAL NOT NULL,
    monthly_savings   REAL    NOT NULL,
    savings_percent   REAL    NOT NULL,
    confidence        TEXT    NOT NULL DEFAULT 'medium',
    reasoning         TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (recommendation_type IN (
        'rightsize','pricing_plan_switch','storage_class_switch',
        'memory_resize','volume_type_upgrade','delete_unused',
        'capacity_mode_switch','replace_with_endpoint','delete_idle'
    )),
    CHECK (confidence IN ('high','medium','low'))
);
CREATE INDEX IF NOT EXISTS idx_recommendations_user    ON recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_service ON recommendations(service);

CREATE TABLE IF NOT EXISTS anomalies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL,
    service           TEXT,
    anomaly_date      TEXT    NOT NULL,
    expected_cost     REAL    NOT NULL,
    actual_cost       REAL    NOT NULL,
    deviation_percent REAL    NOT NULL,
    severity          TEXT    NOT NULL DEFAULT 'warning',
    description       TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    CHECK (severity IN ('info','warning','critical'))
);
CREATE INDEX IF NOT EXISTS idx_anomalies_user ON anomalies(user_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_date ON anomalies(anomaly_date);
"""


# ===================================================================
# Connection & schema helpers
# ===================================================================

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    Args:
        db_path: Path to the database file. Defaults to ``config.DB_PATH``.

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables/indexes if they do not already exist.

    This is safe to call repeatedly and does **not** drop any existing data.

    Args:
        conn: Open database connection.
    """
    conn.executescript(_SCHEMA_DDL)
    conn.commit()
    logger.info("Schema ensured (CREATE TABLE IF NOT EXISTS)")


def create_schema(conn: sqlite3.Connection) -> None:
    """Drop all tables and recreate the full schema.

    Args:
        conn: Open database connection.
    """
    tables = [
        "anomalies", "recommendations", "forecasts", "ai_recommendations",
        "instance_pricing",
        "elb_metrics", "nat_gateway_metrics", "ebs_metrics",
        "s3_metrics", "ec2_metrics", "rds_metrics", "elasticache_metrics",
        "ecs_metrics", "lambda_metrics", "dynamodb_metrics",
        "ebs_volumes", "s3_buckets", "dynamodb_tables", "nat_gateways",
        "elb_instances", "ecs_services", "lambda_functions",
        "elasticache_nodes", "rds_instances", "ec2_instances",
        "service_region_costs", "service_costs", "daily_costs",
        "aws_connections", "users",
    ]
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_DDL)
    conn.commit()
    logger.info("Schema created (30 tables)")


def ensure_user(conn: sqlite3.Connection, account_id: str) -> str:
    """Create a user record for the given AWS account if it does not exist.

    Args:
        conn: Open database connection.
        account_id: AWS account ID (e.g. ``"131471595343"``).

    Returns:
        The ``user_id`` string (format: ``"aws-{account_id}"``).
    """
    user_id = f"aws-{account_id}"
    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row:
        return row[0]

    conn.execute(
        "INSERT INTO users (user_id, email, password_hash, profile_name, user_type) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, f"{account_id}@aws.local", "not-applicable",
         f"AWS Account {account_id}", "active"),
    )
    conn.commit()
    logger.info(f"Created user {user_id}")
    return user_id


def clear_user_data(conn: sqlite3.Connection, user_id: str) -> None:
    """Delete all data rows for a user across all data tables.

    Does NOT delete the user record itself or aws_connections.

    Args:
        conn: Open database connection.
        user_id: User ID to wipe.
    """
    # Tables that should NOT be cleared (admin/config tables).
    _SKIP_TABLES = {"users", "aws_connections", "instance_pricing"}
    # Dynamically discover all tables with a user_id column.
    all_tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.execute("PRAGMA foreign_keys = OFF")
    for (table_name,) in all_tables:
        if table_name in _SKIP_TABLES or table_name.startswith("sqlite_"):
            continue
        # Only delete from tables that actually have a user_id column.
        col_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        col_names = {row[1] for row in col_info}
        if "user_id" not in col_names:
            continue
        conn.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    logger.info(f"Cleared all data for user {user_id}")


# ===================================================================
# Internal helpers — type conversion & safe insert
# ===================================================================

def _safe_float(value, default: float = 0.0) -> float:
    """Convert *value* to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default: int = 0) -> int:
    """Convert *value* to int, returning *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _build_tuples(rows: List[dict], mapper: Callable[[dict], tuple],
                  table: str) -> List[tuple]:
    """Apply *mapper* to each row, skipping rows that fail extraction.

    Args:
        rows: Raw dicts from the caller.
        mapper: ``callable(row) -> tuple`` that extracts DB-ready values.
        table: Table name (for logging only).

    Returns:
        List of tuples suitable for ``executemany``.
    """
    tuples: List[tuple] = []
    for idx, r in enumerate(rows):
        try:
            tuples.append(mapper(r))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(f"{table}: skipping row {idx} — {exc}")
    return tuples


def _executemany_insert(conn: sqlite3.Connection, sql: str,
                        tuples: List[tuple], table: str) -> int:
    """Execute an INSERT with many rows.

    Args:
        conn: Open database connection.
        sql: SQL statement with ``?`` placeholders.
        tuples: List of parameter tuples.
        table: Table name (for logging).

    Returns:
        Number of rows inserted.

    Raises:
        sqlite3.Error: Re-raised after logging on database errors.
    """
    if not tuples:
        return 0
    try:
        conn.executemany(sql, tuples)
        count = len(tuples)
        logger.info(f"{table}: {count} rows inserted")
        return count
    except sqlite3.Error as exc:
        logger.error(f"{table}: insert failed — {exc}")
        raise


def _rows_to_dicts(cursor: sqlite3.Cursor) -> List[dict]:
    """Convert sqlite3.Row results to list of plain dicts."""
    return [dict(row) for row in cursor.fetchall()]


def _query_metrics(conn: sqlite3.Connection, table: str, user_id: str,
                   resource_col: Optional[str] = None,
                   resource_id: Optional[str] = None,
                   time_col: str = "timestamp",
                   start: Optional[str] = None,
                   end: Optional[str] = None) -> List[dict]:
    """Generic metrics query filtered by user, optional resource, and time.

    Args:
        conn: Open database connection.
        table: Metrics table name.
        user_id: User ID to query.
        resource_col: Column name for the resource filter.
        resource_id: Value to filter on.
        time_col: Name of the timestamp/date column.
        start: Inclusive start value.
        end: Inclusive end value.

    Returns:
        List of metric dicts ordered by *time_col*.
    """
    sql = f"SELECT * FROM {table} WHERE user_id = ?"
    params: list = [user_id]
    if resource_id and resource_col:
        sql += f" AND {resource_col} = ?"
        params.append(resource_id)
    if start:
        sql += f" AND {time_col} >= ?"
        params.append(start)
    if end:
        sql += f" AND {time_col} <= ?"
        params.append(end)
    sql += f" ORDER BY {time_col}"
    try:
        return _rows_to_dicts(conn.execute(sql, params))
    except sqlite3.Error as exc:
        logger.error(f"{table}: query failed — {exc}")
        raise


# ===================================================================
# Write API — insert_* functions
# ===================================================================

# -- Cost tables --

def insert_daily_costs(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert daily cost rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``date``, ``total_cost``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["date"], user_id, _safe_float(r["total_cost"]),
    ), "daily_costs")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO daily_costs (date, user_id, total_cost) "
        "VALUES (?, ?, ?)",
        tuples, "daily_costs",
    )


def insert_service_costs(conn: sqlite3.Connection, user_id: str,
                         rows: List[dict]) -> int:
    """Insert per-service daily cost rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``date``, ``service``, ``daily_cost``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["date"], user_id, r["service"], _safe_float(r["daily_cost"]),
    ), "service_costs")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO service_costs (date, user_id, service, daily_cost) "
        "VALUES (?, ?, ?, ?)",
        tuples, "service_costs",
    )


def insert_service_region_costs(conn: sqlite3.Connection, user_id: str,
                                rows: List[dict]) -> int:
    """Insert per-service-per-region daily cost rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``date``, ``service``, ``region``,
            ``daily_cost``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["date"], user_id, r["service"], r["region"],
        _safe_float(r["daily_cost"]),
    ), "service_region_costs")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO service_region_costs "
        "(date, user_id, service, region, daily_cost) VALUES (?, ?, ?, ?, ?)",
        tuples, "service_region_costs",
    )


# -- EC2 --

def insert_ec2_instances(conn: sqlite3.Connection, user_id: str,
                         rows: List[dict]) -> int:
    """Insert EC2 instance inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict should have: ``instance_id``, ``instance_type``,
            ``state``, ``launch_date``, ``region``, and optional fields.

    Returns:
        Number of rows inserted.
    """
    def _map(r: dict) -> tuple:
        itype = r.get("instance_type", "")
        vcpus = r.get("vcpus") or INSTANCE_SPECS.get(itype, (None, None))[0]
        mem = r.get("memory_gb") or INSTANCE_SPECS.get(itype, (None, None))[1]
        return (
            r["instance_id"], user_id, itype, vcpus, mem,
            r.get("state", "running"),
            r.get("launch_date", ""),
            r.get("region", "us-east-1"),
            r.get("availability_zone", "us-east-1a"),
            r.get("pricing_model", "on-demand"),
            r.get("monthly_cost"),
            r.get("private_ip"), r.get("public_ip"),
            r.get("vpc_id"), r.get("subnet_id"),
            r.get("ami_id"), r.get("tags"),
        )

    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ec2_instances "
        "(instance_id, user_id, instance_type, vcpus, memory_gb, state, "
        "launch_date, region, availability_zone, pricing_model, monthly_cost, "
        "private_ip, public_ip, vpc_id, subnet_id, ami_id, tags) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _build_tuples(rows, _map, "ec2_instances"),
        "ec2_instances",
    )


def insert_ec2_metrics(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert EC2 metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``instance_id``,
            ``cpu_utilization``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["instance_id"],
        _safe_float(r["cpu_utilization"]),
        r.get("cpu_max"),
        r.get("memory_utilization"),
        _safe_float(r.get("network_in_kbps", 0)),
        _safe_float(r.get("network_out_kbps", 0)),
        _safe_float(r.get("disk_read_kbps", 0)),
        _safe_float(r.get("disk_write_kbps", 0)),
        _safe_float(r.get("disk_read_ops", 0)),
        _safe_float(r.get("disk_write_ops", 0)),
    ), "ec2_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ec2_metrics "
        "(timestamp, user_id, instance_id, cpu_utilization, cpu_max, "
        "memory_utilization, network_in_kbps, network_out_kbps, "
        "disk_read_kbps, disk_write_kbps, disk_read_ops, disk_write_ops) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ec2_metrics",
    )


# -- RDS --

def insert_rds_instances(conn: sqlite3.Connection, user_id: str,
                         rows: List[dict]) -> int:
    """Insert RDS instance inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``db_instance_id``,
            ``db_instance_class``, ``engine``, ``storage_gb``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["db_instance_id"], user_id,
        r["db_instance_class"], r["engine"],
        r.get("engine_version"),
        _safe_int(r.get("storage_gb", 0)),
        r.get("storage_type", "gp3"),
        _safe_int(r.get("multi_az", 0)),
        r.get("pricing_model", "on-demand"),
        r.get("monthly_cost"),
        r.get("endpoint"), r.get("port"),
        r.get("backup_retention_period"),
        _safe_int(r.get("deletion_protection", 0)),
    ), "rds_instances")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO rds_instances "
        "(db_instance_id, user_id, db_instance_class, engine, engine_version, "
        "storage_gb, storage_type, multi_az, pricing_model, monthly_cost, "
        "endpoint, port, backup_retention_period, deletion_protection) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "rds_instances",
    )


def insert_rds_metrics(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert RDS metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``db_instance_id``,
            ``cpu_utilization``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["db_instance_id"],
        _safe_float(r["cpu_utilization"]),
        r.get("memory_utilization"),
        _safe_float(r.get("read_iops", 0)),
        _safe_float(r.get("write_iops", 0)),
        _safe_int(r.get("connections", 0)),
        _safe_float(r.get("free_storage_gb", 0)),
    ), "rds_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO rds_metrics "
        "(timestamp, user_id, db_instance_id, cpu_utilization, "
        "memory_utilization, read_iops, write_iops, connections, "
        "free_storage_gb) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "rds_metrics",
    )


# -- ElastiCache --

def insert_elasticache_nodes(conn: sqlite3.Connection, user_id: str,
                             rows: List[dict]) -> int:
    """Insert ElastiCache node inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``cache_cluster_id``,
            ``cache_node_type``, ``engine``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["cache_cluster_id"], user_id,
        r["cache_node_type"], r["engine"],
        r.get("engine_version"),
        _safe_int(r.get("num_cache_nodes", 1)),
        r.get("pricing_model", "on-demand"),
        r.get("monthly_cost"),
    ), "elasticache_nodes")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO elasticache_nodes "
        "(cache_cluster_id, user_id, cache_node_type, engine, "
        "engine_version, num_cache_nodes, pricing_model, monthly_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "elasticache_nodes",
    )


def insert_elasticache_metrics(conn: sqlite3.Connection, user_id: str,
                               rows: List[dict]) -> int:
    """Insert ElastiCache metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``cache_cluster_id``,
            ``cpu_utilization``, ``memory_utilization``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["cache_cluster_id"],
        _safe_float(r["cpu_utilization"]),
        _safe_float(r["memory_utilization"]),
        _safe_int(r.get("curr_connections", 0)),
        _safe_int(r.get("cache_hits", 0)),
        _safe_int(r.get("cache_misses", 0)),
        _safe_int(r.get("evictions", 0)),
    ), "elasticache_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO elasticache_metrics "
        "(timestamp, user_id, cache_cluster_id, cpu_utilization, "
        "memory_utilization, curr_connections, cache_hits, cache_misses, "
        "evictions) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "elasticache_metrics",
    )


# -- ECS --

def insert_ecs_services(conn: sqlite3.Connection, user_id: str,
                        rows: List[dict]) -> int:
    """Insert ECS service inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``service_name``, ``cluster_name``,
            ``cpu``, ``memory_mb``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["service_name"], user_id,
        r["cluster_name"],
        r.get("launch_type", "FARGATE"),
        _safe_int(r.get("desired_count", 1)),
        _safe_int(r["cpu"]), _safe_int(r["memory_mb"]),
        r.get("monthly_cost"),
    ), "ecs_services")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ecs_services "
        "(service_name, user_id, cluster_name, launch_type, "
        "desired_count, cpu, memory_mb, monthly_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ecs_services",
    )


def insert_ecs_metrics(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert ECS metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``service_name``,
            ``cluster_name``, ``cpu_utilization``, ``memory_utilization``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id,
        r["service_name"], r["cluster_name"],
        _safe_float(r["cpu_utilization"]),
        _safe_float(r["memory_utilization"]),
        _safe_int(r.get("running_task_count", 1)),
        _safe_int(r.get("desired_task_count", 1)),
    ), "ecs_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ecs_metrics "
        "(timestamp, user_id, service_name, cluster_name, "
        "cpu_utilization, memory_utilization, running_task_count, "
        "desired_task_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ecs_metrics",
    )


# -- Lambda --

def insert_lambda_functions(conn: sqlite3.Connection, user_id: str,
                            rows: List[dict]) -> int:
    """Insert Lambda function inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``function_name``, ``runtime``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["function_name"], user_id,
        r["runtime"],
        r.get("memory_mb"),
        _safe_int(r.get("timeout_sec", 30)),
        _safe_int(r.get("avg_daily_invocations", 0)),
        _safe_float(r.get("avg_duration_ms", 0)),
        r.get("monthly_cost"),
        r.get("code_size"),
        r.get("handler"),
        r.get("last_modified"),
    ), "lambda_functions")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO lambda_functions "
        "(function_name, user_id, runtime, memory_mb, timeout_sec, "
        "avg_daily_invocations, avg_duration_ms, monthly_cost, "
        "code_size, handler, last_modified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "lambda_functions",
    )


def insert_lambda_metrics(conn: sqlite3.Connection, user_id: str,
                          rows: List[dict]) -> int:
    """Insert Lambda metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``date``, ``function_name``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["date"], user_id, r["function_name"],
        _safe_int(r.get("invocations", 0)),
        _safe_float(r.get("avg_duration_ms", 0)),
        _safe_float(r.get("max_duration_ms", 0)),
        _safe_int(r.get("errors", 0)),
        _safe_int(r.get("throttles", 0)),
        _safe_float(r.get("avg_memory_used_mb", 0)),
        r.get("memory_allocated_mb"),
    ), "lambda_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO lambda_metrics "
        "(date, user_id, function_name, invocations, avg_duration_ms, "
        "max_duration_ms, errors, throttles, avg_memory_used_mb, "
        "memory_allocated_mb) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "lambda_metrics",
    )


# -- EBS --

def insert_ebs_volumes(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert EBS volume inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``volume_id``, ``volume_type``,
            ``size_gb``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["volume_id"], user_id,
        r["volume_type"], _safe_int(r["size_gb"]),
        r.get("iops"), r.get("throughput_mbps"),
        r.get("attached_instance_id"),
        r.get("state", "in-use"),
        r.get("monthly_cost"),
        _safe_int(r.get("encrypted", 0)),
        r.get("create_time"),
    ), "ebs_volumes")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ebs_volumes "
        "(volume_id, user_id, volume_type, size_gb, iops, throughput_mbps, "
        "attached_instance_id, state, monthly_cost, encrypted, create_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ebs_volumes",
    )


def insert_ebs_metrics(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert EBS metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``volume_id``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["volume_id"],
        _safe_float(r.get("read_ops", 0)),
        _safe_float(r.get("write_ops", 0)),
        _safe_float(r.get("read_bytes", 0)),
        _safe_float(r.get("write_bytes", 0)),
        _safe_float(r.get("idle_time_seconds", 0)),
    ), "ebs_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO ebs_metrics "
        "(timestamp, user_id, volume_id, read_ops, write_ops, "
        "read_bytes, write_bytes, idle_time_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ebs_metrics",
    )


# -- S3 --

def insert_s3_buckets(conn: sqlite3.Connection, user_id: str,
                      rows: List[dict]) -> int:
    """Insert S3 bucket inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``bucket_name``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["bucket_name"], user_id,
        r.get("storage_class", "STANDARD"),
        r.get("size_gb"),
        _safe_int(r.get("num_objects", 0)),
        _safe_int(r.get("avg_daily_get_requests", 0)),
        _safe_int(r.get("avg_daily_put_requests", 0)),
        r.get("monthly_cost"),
        r.get("region"), r.get("versioning"), r.get("encryption"),
    ), "s3_buckets")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO s3_buckets "
        "(bucket_name, user_id, storage_class, size_gb, num_objects, "
        "avg_daily_get_requests, avg_daily_put_requests, monthly_cost, "
        "region, versioning, encryption) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "s3_buckets",
    )


def insert_s3_metrics(conn: sqlite3.Connection, user_id: str,
                      rows: List[dict]) -> int:
    """Insert S3 metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``bucket_name``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["bucket_name"],
        _safe_float(r.get("bucket_size_bytes", 0)),
        _safe_int(r.get("number_of_objects", 0)),
    ), "s3_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO s3_metrics "
        "(timestamp, user_id, bucket_name, bucket_size_bytes, "
        "number_of_objects) VALUES (?, ?, ?, ?, ?)",
        tuples, "s3_metrics",
    )


# -- DynamoDB --

def insert_dynamodb_tables(conn: sqlite3.Connection, user_id: str,
                           rows: List[dict]) -> int:
    """Insert DynamoDB table inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``table_name``, ``capacity_mode``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["table_name"], user_id, r["capacity_mode"],
        r.get("provisioned_rcu"), r.get("provisioned_wcu"),
        _safe_float(r.get("storage_gb", 0)),
        _safe_int(r.get("item_count", 0)),
        r.get("monthly_cost"),
    ), "dynamodb_tables")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO dynamodb_tables "
        "(table_name, user_id, capacity_mode, provisioned_rcu, "
        "provisioned_wcu, storage_gb, item_count, monthly_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "dynamodb_tables",
    )


def insert_dynamodb_metrics(conn: sqlite3.Connection, user_id: str,
                            rows: List[dict]) -> int:
    """Insert DynamoDB metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``table_name``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["table_name"],
        _safe_float(r.get("consumed_read_units", 0)),
        _safe_float(r.get("consumed_write_units", 0)),
        r.get("provisioned_read_units"),
        r.get("provisioned_write_units"),
        _safe_int(r.get("throttled_requests", 0)),
    ), "dynamodb_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO dynamodb_metrics "
        "(timestamp, user_id, table_name, consumed_read_units, "
        "consumed_write_units, provisioned_read_units, "
        "provisioned_write_units, throttled_requests) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "dynamodb_metrics",
    )


# -- NAT Gateway --

def insert_nat_gateways(conn: sqlite3.Connection, user_id: str,
                        rows: List[dict]) -> int:
    """Insert NAT gateway inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``nat_gateway_id``, ``vpc_id``,
            ``subnet_id``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["nat_gateway_id"], user_id,
        r["vpc_id"], r["subnet_id"],
        r.get("state", "available"),
        _safe_float(r.get("monthly_hours", 730)),
        _safe_float(r.get("monthly_data_processed_gb", 0)),
        r.get("monthly_cost"),
    ), "nat_gateways")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO nat_gateways "
        "(nat_gateway_id, user_id, vpc_id, subnet_id, state, "
        "monthly_hours, monthly_data_processed_gb, monthly_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "nat_gateways",
    )


def insert_nat_gateway_metrics(conn: sqlite3.Connection, user_id: str,
                               rows: List[dict]) -> int:
    """Insert NAT gateway metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``nat_gateway_id``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["nat_gateway_id"],
        _safe_float(r.get("bytes_in", 0)),
        _safe_float(r.get("bytes_out", 0)),
        _safe_int(r.get("packets_in", 0)),
        _safe_int(r.get("packets_out", 0)),
        _safe_int(r.get("active_connections", 0)),
    ), "nat_gateway_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO nat_gateway_metrics "
        "(timestamp, user_id, nat_gateway_id, bytes_in, bytes_out, "
        "packets_in, packets_out, active_connections) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "nat_gateway_metrics",
    )


# -- ELB --

def insert_elb_instances(conn: sqlite3.Connection, user_id: str,
                         rows: List[dict]) -> int:
    """Insert ELB/ALB inventory rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``elb_arn``, ``elb_name``, ``elb_type``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["elb_arn"], user_id,
        r["elb_name"], r["elb_type"],
        r.get("scheme", "internet-facing"),
        _safe_int(r.get("target_count", 0)),
        _safe_int(r.get("healthy_target_count", 0)),
        _safe_int(r.get("avg_daily_requests", 0)),
        r.get("monthly_cost"),
        r.get("dns_name"), r.get("vpc_id"),
        r.get("state", "active"),
        r.get("created_time"),
    ), "elb_instances")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO elb_instances "
        "(elb_arn, user_id, elb_name, elb_type, scheme, target_count, "
        "healthy_target_count, avg_daily_requests, monthly_cost, "
        "dns_name, vpc_id, state, created_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "elb_instances",
    )


def insert_elb_metrics(conn: sqlite3.Connection, user_id: str,
                       rows: List[dict]) -> int:
    """Insert ELB metrics rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``timestamp``, ``elb_arn``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["timestamp"], user_id, r["elb_arn"],
        _safe_int(r.get("request_count", 0)),
        _safe_int(r.get("active_connections", 0)),
        _safe_int(r.get("new_connections", 0)),
        _safe_float(r.get("processed_bytes", 0)),
        _safe_int(r.get("http_2xx", 0)),
        _safe_int(r.get("http_3xx", 0)),
        _safe_int(r.get("http_4xx", 0)),
        _safe_int(r.get("http_5xx", 0)),
        _safe_float(r.get("target_response_time_avg", 0)),
    ), "elb_metrics")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO elb_metrics "
        "(timestamp, user_id, elb_arn, request_count, active_connections, "
        "new_connections, processed_bytes, http_2xx, http_3xx, http_4xx, "
        "http_5xx, target_response_time_avg) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "elb_metrics",
    )


# -- Pricing (no user_id) --

def insert_instance_pricing(conn: sqlite3.Connection,
                            rows: List[dict]) -> int:
    """Insert instance pricing reference rows.

    Args:
        conn: Open database connection.
        rows: Each dict must have: ``service``, ``instance_type``,
            ``on_demand_hourly``, ``on_demand_monthly``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        r["service"], r["instance_type"],
        r.get("vcpus"), r.get("memory_gb"), r.get("category"),
        _safe_float(r["on_demand_hourly"]),
        r.get("reserved_1yr_hourly"), r.get("reserved_3yr_hourly"),
        r.get("spot_hourly"),
        _safe_float(r["on_demand_monthly"]),
        r.get("reserved_1yr_monthly"), r.get("reserved_3yr_monthly"),
        r.get("spot_monthly"),
    ), "instance_pricing")
    return _executemany_insert(
        conn,
        "INSERT OR REPLACE INTO instance_pricing "
        "(service, instance_type, vcpus, memory_gb, category, "
        "on_demand_hourly, reserved_1yr_hourly, reserved_3yr_hourly, "
        "spot_hourly, on_demand_monthly, reserved_1yr_monthly, "
        "reserved_3yr_monthly, spot_monthly) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "instance_pricing",
    )


# -- Analytics result tables --
# These use plain INSERT (not OR REPLACE) because they have
# AUTOINCREMENT primary keys — each call creates new rows.

def insert_forecasts(conn: sqlite3.Connection, user_id: str,
                     rows: List[dict]) -> int:
    """Insert forecast result rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``forecast_date``, ``predicted_cost``,
            ``model_type``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        user_id, r.get("service"),
        r["forecast_date"], _safe_float(r["predicted_cost"]),
        r.get("lower_bound"), r.get("upper_bound"),
        r["model_type"], r.get("model_params"),
        r.get("mae"), r.get("mape"),
    ), "forecasts")
    return _executemany_insert(
        conn,
        "INSERT INTO forecasts "
        "(user_id, service, forecast_date, predicted_cost, lower_bound, "
        "upper_bound, model_type, model_params, mae, mape) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "forecasts",
    )


def insert_recommendations(conn: sqlite3.Connection, user_id: str,
                           rows: List[dict]) -> int:
    """Insert optimization recommendation rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``service``, ``resource_id``,
            ``recommendation_type``, ``current_config``,
            ``recommended_config``, ``current_monthly_cost``,
            ``estimated_monthly_cost``, ``monthly_savings``,
            ``savings_percent``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        user_id, r["service"], r["resource_id"],
        r["recommendation_type"],
        r["current_config"], r["recommended_config"],
        _safe_float(r["current_monthly_cost"]),
        _safe_float(r["estimated_monthly_cost"]),
        _safe_float(r["monthly_savings"]),
        _safe_float(r["savings_percent"]),
        r.get("confidence", "medium"),
        r.get("reasoning"),
    ), "recommendations")
    return _executemany_insert(
        conn,
        "INSERT INTO recommendations "
        "(user_id, service, resource_id, recommendation_type, "
        "current_config, recommended_config, current_monthly_cost, "
        "estimated_monthly_cost, monthly_savings, savings_percent, "
        "confidence, reasoning) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "recommendations",
    )


def insert_anomalies(conn: sqlite3.Connection, user_id: str,
                     rows: List[dict]) -> int:
    """Insert anomaly detection result rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``anomaly_date``, ``expected_cost``,
            ``actual_cost``, ``deviation_percent``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        user_id, r.get("service"),
        r["anomaly_date"],
        _safe_float(r["expected_cost"]), _safe_float(r["actual_cost"]),
        _safe_float(r["deviation_percent"]),
        r.get("severity", "warning"),
        r.get("description"),
    ), "anomalies")
    return _executemany_insert(
        conn,
        "INSERT INTO anomalies "
        "(user_id, service, anomaly_date, expected_cost, actual_cost, "
        "deviation_percent, severity, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "anomalies",
    )


def insert_ai_recommendations(conn: sqlite3.Connection, user_id: str,
                              rows: List[dict]) -> int:
    """Insert AI (LLM) recommendation result rows.

    Args:
        conn: Open database connection.
        user_id: User ID to associate.
        rows: Each dict must have: ``app_type``, ``prompt_text``,
            ``recommended_setup``, ``estimated_cost``, ``llm_model``.

    Returns:
        Number of rows inserted.
    """
    tuples = _build_tuples(rows, lambda r: (
        user_id, r["app_type"],
        r.get("expected_users"), r.get("uptime_hours"),
        r.get("importance"), r.get("budget_monthly"),
        r.get("extra_requirements"),
        r["prompt_text"], r["recommended_setup"],
        _safe_float(r["estimated_cost"]),
        r.get("explanation"),
        r["llm_model"], r.get("llm_response_raw"),
    ), "ai_recommendations")
    return _executemany_insert(
        conn,
        "INSERT INTO ai_recommendations "
        "(user_id, app_type, expected_users, uptime_hours, importance, "
        "budget_monthly, extra_requirements, prompt_text, "
        "recommended_setup, estimated_cost, explanation, llm_model, "
        "llm_response_raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuples, "ai_recommendations",
    )


# ===================================================================
# Read API — get_* functions
# ===================================================================

# -- Cost queries --

def get_daily_costs(conn: sqlite3.Connection, user_id: str,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> List[dict]:
    """Query daily costs for a user, optionally filtered by date range.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date: Inclusive end date (YYYY-MM-DD).

    Returns:
        List of dicts with keys: ``date``, ``total_cost``.
    """
    sql = "SELECT date, total_cost FROM daily_costs WHERE user_id = ?"
    params: list = [user_id]
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date"
    return _rows_to_dicts(conn.execute(sql, params))


def get_service_costs(conn: sqlite3.Connection, user_id: str,
                      service: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[dict]:
    """Query per-service daily costs for a user.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        service: Optional service name filter.
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date: Inclusive end date (YYYY-MM-DD).

    Returns:
        List of dicts with keys: ``date``, ``service``, ``daily_cost``.
    """
    sql = "SELECT date, service, daily_cost FROM service_costs WHERE user_id = ?"
    params: list = [user_id]
    if service:
        sql += " AND service = ?"
        params.append(service)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date, service"
    return _rows_to_dicts(conn.execute(sql, params))


def get_service_region_costs(conn: sqlite3.Connection, user_id: str,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> List[dict]:
    """Query per-service-per-region daily costs for a user.

    Args:
        conn: Open database connection.
        user_id: User ID to query.
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date: Inclusive end date (YYYY-MM-DD).

    Returns:
        List of dicts with keys: ``date``, ``service``, ``region``,
        ``daily_cost``.
    """
    sql = ("SELECT date, service, region, daily_cost "
           "FROM service_region_costs WHERE user_id = ?")
    params: list = [user_id]
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date, service, region"
    return _rows_to_dicts(conn.execute(sql, params))


# -- Inventory queries --

def get_ec2_instances(conn: sqlite3.Connection,
                      user_id: str) -> List[dict]:
    """Query all EC2 instances for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM ec2_instances WHERE user_id = ?", (user_id,)))


def get_rds_instances(conn: sqlite3.Connection,
                      user_id: str) -> List[dict]:
    """Query all RDS instances for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM rds_instances WHERE user_id = ?", (user_id,)))


def get_elasticache_nodes(conn: sqlite3.Connection,
                          user_id: str) -> List[dict]:
    """Query all ElastiCache nodes for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM elasticache_nodes WHERE user_id = ?", (user_id,)))


def get_ecs_services(conn: sqlite3.Connection,
                     user_id: str) -> List[dict]:
    """Query all ECS services for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM ecs_services WHERE user_id = ?", (user_id,)))


def get_lambda_functions(conn: sqlite3.Connection,
                         user_id: str) -> List[dict]:
    """Query all Lambda functions for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM lambda_functions WHERE user_id = ?", (user_id,)))


def get_ebs_volumes(conn: sqlite3.Connection,
                    user_id: str) -> List[dict]:
    """Query all EBS volumes for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM ebs_volumes WHERE user_id = ?", (user_id,)))


def get_s3_buckets(conn: sqlite3.Connection,
                   user_id: str) -> List[dict]:
    """Query all S3 buckets for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM s3_buckets WHERE user_id = ?", (user_id,)))


def get_dynamodb_tables(conn: sqlite3.Connection,
                        user_id: str) -> List[dict]:
    """Query all DynamoDB tables for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM dynamodb_tables WHERE user_id = ?", (user_id,)))


def get_nat_gateways(conn: sqlite3.Connection,
                     user_id: str) -> List[dict]:
    """Query all NAT gateways for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM nat_gateways WHERE user_id = ?", (user_id,)))


def get_elb_instances(conn: sqlite3.Connection,
                      user_id: str) -> List[dict]:
    """Query all ELB/ALB instances for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM elb_instances WHERE user_id = ?", (user_id,)))


# -- Metrics queries --

def get_ec2_metrics(conn: sqlite3.Connection, user_id: str,
                    instance_id: Optional[str] = None,
                    start: Optional[str] = None,
                    end: Optional[str] = None) -> List[dict]:
    """Query EC2 metrics for a user, optionally by instance and time range."""
    return _query_metrics(conn, "ec2_metrics", user_id,
                          "instance_id", instance_id, start=start, end=end)


def get_rds_metrics(conn: sqlite3.Connection, user_id: str,
                    db_instance_id: Optional[str] = None,
                    start: Optional[str] = None,
                    end: Optional[str] = None) -> List[dict]:
    """Query RDS metrics for a user."""
    return _query_metrics(conn, "rds_metrics", user_id,
                          "db_instance_id", db_instance_id, start=start, end=end)


def get_lambda_metrics(conn: sqlite3.Connection, user_id: str,
                       function_name: Optional[str] = None) -> List[dict]:
    """Query Lambda metrics for a user."""
    return _query_metrics(conn, "lambda_metrics", user_id,
                          "function_name", function_name, time_col="date")


def get_elasticache_metrics(conn: sqlite3.Connection, user_id: str,
                            cache_cluster_id: Optional[str] = None) -> List[dict]:
    """Query ElastiCache metrics for a user."""
    return _query_metrics(conn, "elasticache_metrics", user_id,
                          "cache_cluster_id", cache_cluster_id)


def get_ecs_metrics(conn: sqlite3.Connection, user_id: str,
                    service_name: Optional[str] = None) -> List[dict]:
    """Query ECS metrics for a user."""
    return _query_metrics(conn, "ecs_metrics", user_id,
                          "service_name", service_name)


def get_dynamodb_metrics(conn: sqlite3.Connection, user_id: str,
                         table_name: Optional[str] = None) -> List[dict]:
    """Query DynamoDB metrics for a user."""
    return _query_metrics(conn, "dynamodb_metrics", user_id,
                          "table_name", table_name)


def get_ebs_metrics(conn: sqlite3.Connection, user_id: str,
                    volume_id: Optional[str] = None) -> List[dict]:
    """Query EBS metrics for a user."""
    return _query_metrics(conn, "ebs_metrics", user_id,
                          "volume_id", volume_id)


def get_s3_metrics(conn: sqlite3.Connection, user_id: str,
                   bucket_name: Optional[str] = None) -> List[dict]:
    """Query S3 metrics for a user."""
    return _query_metrics(conn, "s3_metrics", user_id,
                          "bucket_name", bucket_name)


def get_nat_gateway_metrics(conn: sqlite3.Connection, user_id: str,
                            nat_gateway_id: Optional[str] = None) -> List[dict]:
    """Query NAT gateway metrics for a user."""
    return _query_metrics(conn, "nat_gateway_metrics", user_id,
                          "nat_gateway_id", nat_gateway_id)


def get_elb_metrics(conn: sqlite3.Connection, user_id: str,
                    elb_arn: Optional[str] = None) -> List[dict]:
    """Query ELB metrics for a user."""
    return _query_metrics(conn, "elb_metrics", user_id,
                          "elb_arn", elb_arn)


# -- Pricing query --

def get_instance_pricing(conn: sqlite3.Connection,
                         service: Optional[str] = None,
                         instance_type: Optional[str] = None) -> List[dict]:
    """Query instance pricing reference data.

    Args:
        conn: Open database connection.
        service: Optional filter (e.g. ``"EC2"``, ``"RDS"``).
        instance_type: Optional filter by instance type.

    Returns:
        List of pricing dicts.
    """
    sql = "SELECT * FROM instance_pricing WHERE 1=1"
    params: list = []
    if service:
        sql += " AND service = ?"
        params.append(service)
    if instance_type:
        sql += " AND instance_type = ?"
        params.append(instance_type)
    sql += " ORDER BY service, on_demand_monthly"
    return _rows_to_dicts(conn.execute(sql, params))


# -- Analytics result queries --

def get_forecasts(conn: sqlite3.Connection, user_id: str,
                  service: Optional[str] = None) -> List[dict]:
    """Query forecast results for a user."""
    sql = "SELECT * FROM forecasts WHERE user_id = ?"
    params: list = [user_id]
    if service:
        sql += " AND service = ?"
        params.append(service)
    sql += " ORDER BY forecast_date"
    return _rows_to_dicts(conn.execute(sql, params))


def get_recommendations(conn: sqlite3.Connection, user_id: str,
                        service: Optional[str] = None) -> List[dict]:
    """Query optimization recommendations for a user."""
    sql = "SELECT * FROM recommendations WHERE user_id = ?"
    params: list = [user_id]
    if service:
        sql += " AND service = ?"
        params.append(service)
    sql += " ORDER BY monthly_savings DESC"
    return _rows_to_dicts(conn.execute(sql, params))


def get_anomalies(conn: sqlite3.Connection, user_id: str) -> List[dict]:
    """Query detected anomalies for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM anomalies WHERE user_id = ? ORDER BY anomaly_date",
        (user_id,)))


def get_ai_recommendations(conn: sqlite3.Connection,
                           user_id: str) -> List[dict]:
    """Query AI (LLM) recommendations for a user."""
    return _rows_to_dicts(conn.execute(
        "SELECT * FROM ai_recommendations WHERE user_id = ? "
        "ORDER BY created_at DESC", (user_id,)))
