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
