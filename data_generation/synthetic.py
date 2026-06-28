"""Deterministic synthetic AWS data generators for tests and demos."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd


ACCOUNT_ID = "SYNTHETIC-001"
REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
SERVICES = ["EC2", "RDS", "S3", "Lambda", "EBS", "DynamoDB", "ElastiCache", "ECS"]
EC2_FLEET = [
    ("i-syn-001", "t3.micro", "running", "us-east-1"),
    ("i-syn-002", "t3.small", "running", "us-east-1"),
    ("i-syn-003", "t3.medium", "running", "us-east-1"),
    ("i-syn-004", "m5.large", "running", "us-west-2"),
    ("i-syn-005", "m5.xlarge", "running", "us-west-2"),
    ("i-syn-006", "c5.large", "stopped", "eu-west-1"),
    ("i-syn-007", "r5.large", "running", "eu-west-1"),
    ("i-syn-008", "t3.large", "running", "us-east-1"),
]
RDS_FLEET = [("db-syn-001", "db.t3.medium", "postgres"), ("db-syn-002", "db.m5.large", "mysql")]
S3_BUCKETS = ["optic-data-raw", "optic-logs", "optic-archive", "optic-assets"]
LAMBDA_FUNCTIONS = ["cost-loader", "forecast-refresh", "anomaly-check", "report-export"]
EBS_VOLUMES = [f"vol-syn-{index:03d}" for index in range(1, 9)]


def _rng(seed: int | None = None) -> np.random.Generator:
    return np.random.default_rng(seed)


def _dates(days: int) -> list[date]:
    start = date.today() - timedelta(days=days - 1)
    return [start + timedelta(days=index) for index in range(days)]


def generate_daily_costs(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for index, day in enumerate(_dates(days)):
        value = 80 + index * 0.15 + 8 * np.sin(index / 7 * 2 * np.pi) + rng.normal(0, 2)
        rows.append({"account_id": ACCOUNT_ID, "date": day.isoformat(), "cost_amount": round(max(0, value), 2), "currency": "USD"})
    return pd.DataFrame(rows)


def generate_service_costs(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    daily = generate_daily_costs(days=days, seed=seed)
    weights = np.array([0.34, 0.18, 0.12, 0.08, 0.08, 0.07, 0.06, 0.07])
    rows = []
    for _, item in daily.iterrows():
        for service, percent in zip(SERVICES, rng.dirichlet(weights * 60)):
            rows.append({
                "account_id": ACCOUNT_ID,
                "date": item["date"],
                "service_name": service,
                "cost_amount": round(float(item["cost_amount"]) * float(percent), 2),
                "currency": "USD",
            })
    return pd.DataFrame(rows)


def generate_service_region_costs(service_costs: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for _, item in service_costs.iterrows():
        for region, percent in zip(REGIONS, rng.dirichlet(np.array([5, 3, 2]))):
            rows.append({
                "account_id": item.get("account_id", ACCOUNT_ID),
                "date": item["date"],
                "service_name": item["service_name"],
                "region": region,
                "cost_amount": round(float(item["cost_amount"]) * float(percent), 2),
                "currency": item.get("currency", "USD"),
            })
    return pd.DataFrame(rows)


def generate_ec2_instances() -> pd.DataFrame:
    return pd.DataFrame([
        {"instance_id": iid, "instance_type": itype, "state": state, "region": region}
        for iid, itype, state, region in EC2_FLEET
    ])


def generate_ec2_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for iid, *_ in EC2_FLEET:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "instance_id": iid, "cpu_avg": round(float(rng.uniform(8, 72)), 2)})
    return pd.DataFrame(rows)


def generate_rds_instances() -> pd.DataFrame:
    return pd.DataFrame([
        {"db_instance_id": dbid, "db_instance_class": klass, "engine": engine}
        for dbid, klass, engine in RDS_FLEET
    ])


def generate_rds_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for dbid, *_ in RDS_FLEET:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "db_instance_id": dbid, "cpu_utilization_avg": round(float(rng.uniform(10, 65)), 2)})
    return pd.DataFrame(rows)


def generate_s3_buckets() -> pd.DataFrame:
    return pd.DataFrame([{"bucket_name": name, "region": REGIONS[index % len(REGIONS)]} for index, name in enumerate(S3_BUCKETS)])


def generate_lambda_functions() -> pd.DataFrame:
    runtimes = ["python3.12", "nodejs20.x", "python3.12", "nodejs20.x"]
    return pd.DataFrame([{"function_name": name, "runtime": runtimes[index], "memory_mb": 256 + index * 128} for index, name in enumerate(LAMBDA_FUNCTIONS)])


def generate_ebs_volumes() -> pd.DataFrame:
    return pd.DataFrame([{"volume_id": vid, "volume_type": "gp3", "size_gb": 40 + index * 20} for index, vid in enumerate(EBS_VOLUMES)])


def generate_instance_pricing() -> tuple[pd.DataFrame, int, int]:
    """Return on-demand instance pricing.

    Returns a 3-tuple ``(pricing_df, real_count, synthetic_count)``: the
    DataFrame of ``instance_type``/``hourly_price_usd`` rows, the number of rows
    sourced from real AWS pricing (always ``0`` — every price here is a baked-in
    synthetic constant), and the number of synthetic rows (i.e. ``len(df)``).
    The tuple shape mirrors the real collector so callers can swap them.
    """
    rows = [
        {"instance_type": "t3.micro", "hourly_price_usd": 0.0104},
        {"instance_type": "t3.small", "hourly_price_usd": 0.0208},
        {"instance_type": "t3.medium", "hourly_price_usd": 0.0416},
        {"instance_type": "m5.large", "hourly_price_usd": 0.096},
        {"instance_type": "m5.xlarge", "hourly_price_usd": 0.192},
        {"instance_type": "c5.large", "hourly_price_usd": 0.085},
        {"instance_type": "r5.large", "hourly_price_usd": 0.126},
        {"instance_type": "t3.large", "hourly_price_usd": 0.0832},
    ]
    return pd.DataFrame(rows), 0, len(rows)


def generate_elasticache_nodes() -> pd.DataFrame:
    return pd.DataFrame([
        {"cache_cluster_id": "cache-redis-001", "cache_node_type": "cache.t3.small", "engine": "redis"},
        {"cache_cluster_id": "cache-redis-002", "cache_node_type": "cache.t3.medium", "engine": "redis"},
        {"cache_cluster_id": "cache-mem-001", "cache_node_type": "cache.t3.small", "engine": "memcached"},
    ])


def generate_elasticache_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for cid in generate_elasticache_nodes()["cache_cluster_id"]:
            misses = int(rng.integers(20, 80))
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "cache_cluster_id": cid, "cache_hits": misses * 15, "cache_misses": misses, "cpu_util_avg": round(float(rng.uniform(5, 60)), 2)})
    return pd.DataFrame(rows)


def generate_ecs_services() -> pd.DataFrame:
    return pd.DataFrame([
        {"service_name": "api", "cluster_name": "prod", "cpu": 512, "memory_mb": 1024},
        {"service_name": "worker", "cluster_name": "prod", "cpu": 1024, "memory_mb": 2048},
        {"service_name": "scheduler", "cluster_name": "prod", "cpu": 256, "memory_mb": 512},
        {"service_name": "reports", "cluster_name": "analytics", "cpu": 512, "memory_mb": 1024},
    ])


def generate_ecs_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for service in generate_ecs_services()["service_name"]:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "service_name": service, "cpu_utilization_avg": round(float(rng.uniform(10, 75)), 2)})
    return pd.DataFrame(rows)


def generate_dynamodb_tables() -> pd.DataFrame:
    return pd.DataFrame([
        {"table_name": "sessions", "capacity_mode": "ON_DEMAND"},
        {"table_name": "events", "capacity_mode": "PROVISIONED"},
        {"table_name": "feature_flags", "capacity_mode": "ON_DEMAND"},
    ])


def generate_dynamodb_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for table in generate_dynamodb_tables()["table_name"]:
            rows.append({"date": day.isoformat(), "table_name": table, "consumed_read_units_avg": round(float(rng.uniform(0, 500)), 2), "consumed_write_units_avg": round(float(rng.uniform(0, 250)), 2)})
    return pd.DataFrame(rows)


def generate_nat_gateways() -> pd.DataFrame:
    return pd.DataFrame([
        {"nat_gateway_id": "nat-001", "vpc_id": "vpc-001", "subnet_id": "subnet-001", "state": "available"},
        {"nat_gateway_id": "nat-002", "vpc_id": "vpc-002", "subnet_id": "subnet-002", "state": "available"},
    ])


def generate_nat_gateway_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for nat_id in generate_nat_gateways()["nat_gateway_id"]:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "nat_gateway_id": nat_id, "bytes_in_avg": round(float(rng.uniform(0, 1_000_000)), 2), "bytes_out_avg": round(float(rng.uniform(0, 1_000_000)), 2)})
    return pd.DataFrame(rows)


def generate_elb_instances() -> pd.DataFrame:
    return pd.DataFrame([
        {"load_balancer_arn": "arn:aws:elb:001", "load_balancer_name": "public-api", "type": "application"},
        {"load_balancer_arn": "arn:aws:elb:002", "load_balancer_name": "internal-api", "type": "application"},
        {"load_balancer_arn": "arn:aws:elb:003", "load_balancer_name": "tcp-ingress", "type": "network"},
    ])


def generate_elb_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for lb in generate_elb_instances()["load_balancer_name"]:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "load_balancer_name": lb, "http_2xx": int(rng.integers(1000, 10000)), "http_3xx": int(rng.integers(0, 400)), "http_4xx": int(rng.integers(0, 120)), "http_5xx": int(rng.integers(0, 20))})
    return pd.DataFrame(rows)


def generate_ebs_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for vid in EBS_VOLUMES:
            rows.append({"timestamp": datetime.combine(day, datetime.min.time()).isoformat(), "volume_id": vid, "read_ops_avg": round(float(rng.uniform(0, 500)), 2), "write_ops_avg": round(float(rng.uniform(0, 500)), 2)})
    return pd.DataFrame(rows)


def generate_lambda_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for function in LAMBDA_FUNCTIONS:
            rows.append({"date": day.isoformat(), "function_name": function, "invocations": int(rng.integers(0, 50000)), "errors": int(rng.integers(0, 50))})
    return pd.DataFrame(rows)


def generate_s3_metrics(days: int = 365, seed: int | None = None) -> pd.DataFrame:
    rng = _rng(seed)
    rows = []
    for day in _dates(days):
        for bucket in S3_BUCKETS:
            rows.append({"date": day.isoformat(), "bucket_name": bucket, "bucket_size_bytes": int(rng.integers(1_000_000, 25_000_000_000))})
    return pd.DataFrame(rows)


# ===================================================================
# CLI entrypoint: generate + persist synthetic data into the store.
# Powers the documented `python -m data_generation.synthetic` command.
# ===================================================================

def main(argv: list[str] | None = None) -> int:
    """Generate synthetic AWS data and write it to the SQLite store.

    Writes data for a single ``--user-id`` only and never deletes existing
    rows, so it is safe against the committed demo DB. Every write goes through
    the storage ``insert_*`` helpers, which use ``INSERT OR REPLACE`` keyed on
    primary keys (date/timestamp + user + entity); re-running for the same user
    therefore overwrites those rows in place rather than duplicating them.

    The generator frames keep their own column names (asserted by tests); this
    function maps them to the dict shape each ``insert_*`` expects at the call
    boundary.
    """
    import argparse

    import config
    import storage

    parser = argparse.ArgumentParser(
        prog="python -m data_generation.synthetic",
        description="Generate synthetic AWS cost/usage data into the SQLite store.",
    )
    parser.add_argument("--days", type=int, default=config.DEFAULT_SYNTHETIC_DAYS,
                        help="Days of history to generate (default: %(default)s).")
    parser.add_argument("--user-id", default="aws-SYNTHETIC-001",
                        help="Target user_id to write under (default: %(default)s).")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible output (default: %(default)s).")
    args = parser.parse_args(argv)

    days, seed = args.days, args.seed
    account_id = args.user_id.removeprefix("aws-")

    conn = storage.get_connection()
    try:
        storage.ensure_schema(conn)
        user_id = storage.ensure_user(conn, account_id)

        # Cost frames.
        daily = generate_daily_costs(days=days, seed=seed)
        service = generate_service_costs(days=days, seed=seed)
        region = generate_service_region_costs(service, seed=seed)

        # Inventory frames that other frames need for lookups.
        ecs_services = generate_ecs_services()
        ecs_cluster = dict(zip(ecs_services["service_name"], ecs_services["cluster_name"]))
        elb = generate_elb_instances()
        elb_arn = dict(zip(elb["load_balancer_name"], elb["load_balancer_arn"]))
        pricing_df, _, _ = generate_instance_pricing()

        written: dict[str, int] = {}
        written["daily_costs"] = storage.insert_daily_costs(conn, user_id, [
            {"date": r["date"], "total_cost": r["cost_amount"]}
            for r in daily.to_dict("records")
        ])
        written["service_costs"] = storage.insert_service_costs(conn, user_id, [
            {"date": r["date"], "service": r["service_name"], "daily_cost": r["cost_amount"]}
            for r in service.to_dict("records")
        ])
        written["service_region_costs"] = storage.insert_service_region_costs(conn, user_id, [
            {"date": r["date"], "service": r["service_name"], "region": r["region"],
             "daily_cost": r["cost_amount"]}
            for r in region.to_dict("records")
        ])

        written["ec2_instances"] = storage.insert_ec2_instances(
            conn, user_id, generate_ec2_instances().to_dict("records"))
        written["ec2_metrics"] = storage.insert_ec2_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "instance_id": r["instance_id"],
             "cpu_utilization": r["cpu_avg"]}
            for r in generate_ec2_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["rds_instances"] = storage.insert_rds_instances(
            conn, user_id, generate_rds_instances().to_dict("records"))
        written["rds_metrics"] = storage.insert_rds_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "db_instance_id": r["db_instance_id"],
             "cpu_utilization": r["cpu_utilization_avg"]}
            for r in generate_rds_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["elasticache_nodes"] = storage.insert_elasticache_nodes(
            conn, user_id, generate_elasticache_nodes().to_dict("records"))
        written["elasticache_metrics"] = storage.insert_elasticache_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "cache_cluster_id": r["cache_cluster_id"],
             "cpu_utilization": r["cpu_util_avg"], "memory_utilization": 0.0,
             "cache_hits": r["cache_hits"], "cache_misses": r["cache_misses"]}
            for r in generate_elasticache_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["ecs_services"] = storage.insert_ecs_services(
            conn, user_id, ecs_services.to_dict("records"))
        written["ecs_metrics"] = storage.insert_ecs_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "service_name": r["service_name"],
             "cluster_name": ecs_cluster[r["service_name"]],
             "cpu_utilization": r["cpu_utilization_avg"], "memory_utilization": 0.0}
            for r in generate_ecs_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["lambda_functions"] = storage.insert_lambda_functions(
            conn, user_id, generate_lambda_functions().to_dict("records"))
        written["lambda_metrics"] = storage.insert_lambda_metrics(
            conn, user_id, generate_lambda_metrics(days=days, seed=seed).to_dict("records"))

        written["ebs_volumes"] = storage.insert_ebs_volumes(
            conn, user_id, generate_ebs_volumes().to_dict("records"))
        written["ebs_metrics"] = storage.insert_ebs_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "volume_id": r["volume_id"],
             "read_ops": r["read_ops_avg"], "write_ops": r["write_ops_avg"]}
            for r in generate_ebs_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["s3_buckets"] = storage.insert_s3_buckets(
            conn, user_id, generate_s3_buckets().to_dict("records"))
        written["s3_metrics"] = storage.insert_s3_metrics(conn, user_id, [
            {"timestamp": r["date"], "bucket_name": r["bucket_name"],
             "bucket_size_bytes": r["bucket_size_bytes"]}
            for r in generate_s3_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["dynamodb_tables"] = storage.insert_dynamodb_tables(
            conn, user_id, generate_dynamodb_tables().to_dict("records"))
        written["dynamodb_metrics"] = storage.insert_dynamodb_metrics(conn, user_id, [
            {"timestamp": r["date"], "table_name": r["table_name"],
             "consumed_read_units": r["consumed_read_units_avg"],
             "consumed_write_units": r["consumed_write_units_avg"]}
            for r in generate_dynamodb_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["nat_gateways"] = storage.insert_nat_gateways(
            conn, user_id, generate_nat_gateways().to_dict("records"))
        written["nat_gateway_metrics"] = storage.insert_nat_gateway_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "nat_gateway_id": r["nat_gateway_id"],
             "bytes_in": r["bytes_in_avg"], "bytes_out": r["bytes_out_avg"]}
            for r in generate_nat_gateway_metrics(days=days, seed=seed).to_dict("records")
        ])

        elb_type_map = {"application": "ALB", "network": "NLB", "classic": "CLB"}
        written["elb_instances"] = storage.insert_elb_instances(conn, user_id, [
            {"elb_arn": r["load_balancer_arn"], "elb_name": r["load_balancer_name"],
             "elb_type": elb_type_map.get(r["type"], "ALB")}
            for r in elb.to_dict("records")
        ])
        written["elb_metrics"] = storage.insert_elb_metrics(conn, user_id, [
            {"timestamp": r["timestamp"], "elb_arn": elb_arn[r["load_balancer_name"]],
             "http_2xx": r["http_2xx"], "http_3xx": r["http_3xx"],
             "http_4xx": r["http_4xx"], "http_5xx": r["http_5xx"]}
            for r in generate_elb_metrics(days=days, seed=seed).to_dict("records")
        ])

        written["instance_pricing"] = storage.insert_instance_pricing(conn, [
            {"service": "EC2", "instance_type": r["instance_type"],
             "on_demand_hourly": r["hourly_price_usd"],
             "on_demand_monthly": round(r["hourly_price_usd"] * 730, 4)}
            for r in pricing_df.to_dict("records")
        ])

        conn.commit()
    finally:
        conn.close()

    total = sum(written.values())
    print(f"Synthetic data written for user_id={user_id} ({days} days, seed={seed}):")
    for table in sorted(written):
        print(f"  {table:<22} {written[table]:>8,} rows")
    print(f"  {'TOTAL':<22} {total:>8,} rows")
    print("Existing rows for this user were overwritten by primary key; no data was deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
