"""
Synthetic Data Generator for Smart Cloud Optimizer

Generates realistic AWS usage data and writes directly to SQLite
via the storage API. Simulates a mid-size SaaS startup with
monthly bill ~$1,500-$2,500.

Usage:
    python -m data_generation.synthetic --days 365 --seed 42
"""

import argparse
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

import config
import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "SYNTHETIC-001"
REGION = "us-east-1"
DEFAULT_END_DATE = datetime(2025, 6, 30)

# Cost generation parameters
BASE_DAILY_COST: float = 65.0
DAILY_TREND_FACTOR: float = 0.0005  # +1.5% per month ≈ +0.05% per day
WEEKDAY_COST_MULTIPLIER: float = 1.15
WEEKEND_COST_MULTIPLIER: float = 0.70
HOURS_PER_MONTH: float = 730.0
COST_FLOOR: float = 20.0

# Service pricing constants (us-east-1, for monthly_cost computation)
EBS_PRICE_PER_GB = {"gp2": 0.10, "gp3": 0.08, "io2": 0.125}
EBS_IO2_IOPS_PRICE = 0.065  # per provisioned IOPS/month
S3_PRICE_STANDARD_PER_GB = 0.023
LAMBDA_PRICE_PER_GB_SEC = 0.0000166667
LAMBDA_PRICE_PER_REQUEST = 0.0000002
DYNAMO_PRICE_RCU_MONTH = 0.09   # per provisioned RCU/month
DYNAMO_PRICE_WCU_MONTH = 0.47   # per provisioned WCU/month
DYNAMO_PRICE_READ_REQ_M = 1.25  # per million read request units (on-demand)
DYNAMO_PRICE_WRITE_REQ_M = 6.25  # per million write request units (on-demand)
NAT_PRICE_HOURLY = 0.045
NAT_PRICE_PER_GB = 0.045
ELB_ALB_HOURLY = 0.0225

# On-Demand hourly prices for monthly_cost computation
OD_HOURLY = {
    "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
    "t3.large": 0.0832, "t3.xlarge": 0.1664,
    "m5.large": 0.0960, "m5.xlarge": 0.1920, "m5.2xlarge": 0.3840,
    "c5.large": 0.0850, "c5.xlarge": 0.1700, "c5.2xlarge": 0.3400,
    "r5.large": 0.1260, "r5.xlarge": 0.2520,
}
RI1_DISCOUNT = 0.63  # reserved-1yr = 63% of on-demand

# RDS On-Demand hourly
RDS_OD_HOURLY = {
    "db.t4g.micro": 0.016, "db.t4g.medium": 0.065,
    "db.r5.large": 0.240, "db.r5.xlarge": 0.480,
}

# ElastiCache On-Demand hourly
ELASTICACHE_OD_HOURLY = {
    "cache.t3.micro": 0.017, "cache.t3.medium": 0.068,
    "cache.m5.large": 0.142, "cache.r5.large": 0.226,
}

# Anomaly parameters
MIN_ANOMALY_SPIKES: int = 4
MAX_ANOMALY_SPIKES: int = 6
ANOMALY_MULTIPLIER_LOW: float = 1.5
ANOMALY_MULTIPLIER_HIGH: float = 3.0

# EC2 fleet definition
EC2_FLEET = [
    {"name": "prod-web-1",      "type": "m5.xlarge",  "env": "production",  "az": f"{REGION}a", "cpu_cores": 2, "threads": 2},
    {"name": "prod-web-2",      "type": "m5.xlarge",  "env": "production",  "az": f"{REGION}b", "cpu_cores": 2, "threads": 2},
    {"name": "prod-api-1",      "type": "c5.large",   "env": "production",  "az": f"{REGION}a", "cpu_cores": 1, "threads": 2},
    {"name": "prod-cache-1",    "type": "r5.large",   "env": "production",  "az": f"{REGION}b", "cpu_cores": 1, "threads": 2},
    {"name": "staging-web",     "type": "m5.large",   "env": "staging",     "az": f"{REGION}a", "cpu_cores": 1, "threads": 2},
    {"name": "staging-api",     "type": "t3.medium",  "env": "staging",     "az": f"{REGION}b", "cpu_cores": 1, "threads": 2},
    {"name": "dev-server",      "type": "t3.large",   "env": "development", "az": f"{REGION}a", "cpu_cores": 1, "threads": 2},
    {"name": "batch-processor", "type": "c5.2xlarge", "env": "production",  "az": f"{REGION}a", "cpu_cores": 4, "threads": 2},
]

# Deterministic instance IDs derived from names
def _instance_id(name: str) -> str:
    h = hashlib.md5(name.encode()).hexdigest()[:17]
    return f"i-{h}"

def _volume_id(name: str) -> str:
    h = hashlib.md5(f"vol-{name}".encode()).hexdigest()[:17]
    return f"vol-{h}"

def _vpc_id() -> str:
    return "vpc-0synth00000000001"

def _subnet_id(az: str) -> str:
    h = hashlib.md5(az.encode()).hexdigest()[:17]
    return f"subnet-{h}"

def _ami_id() -> str:
    return "ami-0abcdef1234567890"

def _sg_id() -> str:
    return "sg-0synth00000000001"

def _eni_id(name: str) -> str:
    h = hashlib.md5(f"eni-{name}".encode()).hexdigest()[:17]
    return f"eni-{h}"


# ---------------------------------------------------------------------------
# Cost generators
# ---------------------------------------------------------------------------

def generate_daily_costs(days: int = 180, seed: int = 42) -> pd.DataFrame:
    """
    Generate daily total cost data matching data/cost/daily_cost_consolidated.csv schema.

    Columns: account_id, date, cost_amount, currency

    Simulates $1,500-$2,500/month (~$50-$83/day) with:
    - Weekly seasonality (weekdays higher)
    - Upward trend (~1.5%/month)
    - Gaussian noise
    - 4-6 anomaly spikes
    - Month-end bumps
    """
    rng = np.random.default_rng(seed)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)
    dates = pd.date_range(start_date, end_date, freq="D")

    n = len(dates)
    day_idx = np.arange(n, dtype=float)

    # Base daily cost ~$65
    base = BASE_DAILY_COST

    # Trend: +1.5% per month ≈ +0.05% per day
    trend = base * (1.0 + DAILY_TREND_FACTOR * day_idx)

    # Weekly seasonality: weekdays 30% higher than weekends on average
    dow = np.array([d.weekday() for d in dates])
    weekday_factor = np.where(dow < 5, WEEKDAY_COST_MULTIPLIER, WEEKEND_COST_MULTIPLIER)

    # Month-end bump: last 3 days of month get +8%
    month_end_bump = np.ones(n)
    for i, d in enumerate(dates):
        days_in_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if d.day >= days_in_month.day - 2:
            month_end_bump[i] = 1.08

    # Combine
    cost = trend * weekday_factor * month_end_bump

    # Gaussian noise ±12%
    noise = rng.normal(1.0, 0.12, n)
    cost = cost * noise

    # Inject 5 anomaly spikes at 2-3x
    anomaly_indices = rng.choice(np.arange(10, n - 10), size=5, replace=False)
    anomaly_indices.sort()
    for idx in anomaly_indices:
        cost[idx] *= rng.uniform(2.0, 3.0)

    # Floor at $20
    cost = np.maximum(cost, COST_FLOOR)

    df = pd.DataFrame({
        "account_id": ACCOUNT_ID,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "cost_amount": np.round(cost, 2),
        "currency": "USD",
    })
    return df


def generate_service_costs(days: int = 180, seed: int = 42) -> pd.DataFrame:
    """
    Generate per-service daily cost data matching data/cost/service_cost_consolidated.csv schema.

    Columns: account_id, date, service_name, cost_amount, currency

    Services: EC2, RDS, S3, Lambda, EBS, Data Transfer, Other
    with distinct behavior patterns per service.
    """
    rng = np.random.default_rng(seed)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)
    dates = pd.date_range(start_date, end_date, freq="D")
    n = len(dates)
    day_idx = np.arange(n, dtype=float)
    dow = np.array([d.weekday() for d in dates])

    # Month-end mask
    month_end = np.ones(n)
    for i, d in enumerate(dates):
        days_in_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if d.day >= days_in_month.day - 2:
            month_end[i] = 1.08

    # Anomaly dates (shared across services that spike)
    anomaly_indices = rng.choice(np.arange(10, n - 10), size=5, replace=False)
    anomaly_indices.sort()

    services = {}

    # --- EC2: ~50%, $25-$55/day, strong weekly seasonality, trend ---
    ec2_base = 38.0 * (1.0 + 0.0006 * day_idx)
    ec2_weekly = np.where(dow < 5, 1.25, 0.65)
    ec2 = ec2_base * ec2_weekly * month_end * rng.normal(1.0, 0.10, n)
    for idx in anomaly_indices[:3]:
        ec2[idx] *= rng.uniform(1.8, 2.5)
    ec2 = np.clip(ec2, 18.0, None)
    services["Amazon Elastic Compute Cloud - Compute"] = ec2

    # --- RDS: ~20%, $12-$18/day, nearly flat ---
    rds_base = 15.0 * (1.0 + 0.0003 * day_idx)
    rds_weekly = np.where(dow < 5, 1.03, 0.94)
    rds = rds_base * rds_weekly * rng.normal(1.0, 0.04, n)
    rds = np.clip(rds, 10.0, None)
    services["Amazon Relational Database Service"] = rds

    # --- S3: ~5%, $1.50-$4/day, upward trend, no weekly ---
    s3_base = 2.5 * (1.0 + 0.0015 * day_idx)
    s3 = s3_base * rng.normal(1.0, 0.12, n)
    s3 = np.clip(s3, 1.0, None)
    services["Amazon Simple Storage Service"] = s3

    # --- Lambda: ~2%, $0.30-$3/day, bursty, weekly ---
    lam_base = 1.2 * (1.0 + 0.0004 * day_idx)
    lam_weekly = np.where(dow < 5, 1.4, 0.35)
    lam = lam_base * lam_weekly * rng.normal(1.0, 0.30, n)
    # Random burst days
    burst_days = rng.choice(n, size=8, replace=False)
    for bd in burst_days:
        lam[bd] *= rng.uniform(2.0, 4.0)
    lam = np.clip(lam, 0.10, None)
    services["AWS Lambda"] = lam

    # --- EBS: ~3%, $1.80-$2.50/day, almost flat ---
    ebs_base = 2.1
    # Small step increases (simulating new volumes)
    ebs_steps = np.zeros(n)
    for step_day in [n // 4, n // 2, 3 * n // 4]:
        ebs_steps[step_day:] += 0.1
    ebs = (ebs_base + ebs_steps) * rng.normal(1.0, 0.02, n)
    ebs = np.clip(ebs, 1.5, None)
    services["Amazon Elastic Block Store"] = ebs

    # --- Data Transfer: ~10%, $3-$8/day, follows EC2 pattern ---
    dt_base = 5.0 * (1.0 + 0.0005 * day_idx)
    dt_weekly = np.where(dow < 5, 1.20, 0.60)
    dt = dt_base * dt_weekly * month_end * rng.normal(1.0, 0.15, n)
    for idx in anomaly_indices[2:4]:
        dt[idx] *= rng.uniform(1.5, 2.5)
    dt = np.clip(dt, 1.5, None)
    services["Data Transfer"] = dt

    # --- Other: ~5%, $1.50-$4/day, stable ---
    other_base = 2.8 * (1.0 + 0.0003 * day_idx)
    other = other_base * rng.normal(1.0, 0.10, n)
    other = np.clip(other, 1.0, None)
    services["Other"] = other

    # Build rows
    rows = []
    for i in range(n):
        date_str = dates[i].strftime("%Y-%m-%d")
        for svc_name, costs in services.items():
            rows.append({
                "account_id": ACCOUNT_ID,
                "date": date_str,
                "service_name": svc_name,
                "cost_amount": round(float(costs[i]), 2),
                "currency": "USD",
            })

    return pd.DataFrame(rows)


def generate_service_region_costs(service_costs_df: pd.DataFrame,
                                  seed: int = 42) -> pd.DataFrame:
    """Derive per-service-per-region cost data from service_costs DataFrame.

    Splits each service's daily cost across regions. Most services run
    primarily in us-east-1, with a small fraction in us-west-2.

    Args:
        service_costs_df: Output of generate_service_costs().
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns: account_id, date, service_name, region,
        cost_amount, currency.
    """
    rng = np.random.default_rng(seed + 99)

    # Services that span multiple regions vs single-region
    multi_region_services = {
        "Amazon Elastic Compute Cloud - Compute",
        "Amazon Relational Database Service",
        "Amazon Simple Storage Service",
        "AWS Data Transfer",
    }

    rows = []
    for _, r in service_costs_df.iterrows():
        cost = float(r["cost_amount"])
        svc = r["service_name"]

        if svc in multi_region_services and cost > 1.0:
            # Split: 75-90% us-east-1, rest us-west-2
            east_frac = rng.uniform(0.75, 0.90)
            east_cost = round(cost * east_frac, 2)
            west_cost = round(cost - east_cost, 2)
            for region, amount in [("us-east-1", east_cost), ("us-west-2", west_cost)]:
                if amount > 0:
                    rows.append({
                        "account_id": r["account_id"],
                        "date": r["date"],
                        "service_name": svc,
                        "region": region,
                        "cost_amount": amount,
                        "currency": "USD",
                    })
        else:
            rows.append({
                "account_id": r["account_id"],
                "date": r["date"],
                "service_name": svc,
                "region": "us-east-1",
                "cost_amount": round(cost, 2),
                "currency": "USD",
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Inventory generators
# ---------------------------------------------------------------------------

def generate_ec2_instances() -> pd.DataFrame:
    """
    Generate EC2 instance inventory matching data/inventory/ec2_instances.csv schema.

    Columns: account_id, region, instance_id, instance_type, state,
             availability_zone, launch_time, private_ip, public_ip,
             vpc_id, subnet_id, ami_id, tenancy, hypervisor, architecture,
             monitoring, cpu_cores, threads_per_core, security_groups,
             ebs_volumes, network_interfaces, tags
    """
    # Production web instances on reserved pricing (committed workload)
    reserved_instances = {"prod-web-1", "prod-web-2"}

    rows = []
    base_ip = 10
    for i, inst in enumerate(EC2_FLEET):
        iid = _instance_id(inst["name"])
        vid = _volume_id(inst["name"])
        eid = _eni_id(inst["name"])
        launch = datetime(2025, 1, 10 + i, 8, 30, 0)

        pricing_model = "reserved-1yr" if inst["name"] in reserved_instances else "on-demand"
        od_rate = OD_HOURLY.get(inst["type"], 0.10)
        if pricing_model == "reserved-1yr":
            monthly_cost = round(od_rate * RI1_DISCOUNT * HOURS_PER_MONTH, 2)
        else:
            monthly_cost = round(od_rate * HOURS_PER_MONTH, 2)

        tags = f"Name={inst['name']};Environment={inst['env']}"
        rows.append({
            "account_id": ACCOUNT_ID,
            "region": REGION,
            "instance_id": iid,
            "instance_type": inst["type"],
            "state": "running",
            "availability_zone": inst["az"],
            "launch_time": launch.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "private_ip": f"10.0.{i}.{base_ip + i}",
            "public_ip": f"54.{200 + i}.{i}.{100 + i}",
            "vpc_id": _vpc_id(),
            "subnet_id": _subnet_id(inst["az"]),
            "ami_id": _ami_id(),
            "tenancy": "default",
            "hypervisor": "nitro",
            "architecture": "x86_64",
            "monitoring": "disabled",
            "cpu_cores": inst["cpu_cores"],
            "threads_per_core": inst["threads"],
            "security_groups": _sg_id(),
            "ebs_volumes": vid,
            "network_interfaces": eid,
            "tags": tags,
            "pricing_model": pricing_model,
            "monthly_cost": monthly_cost,
        })

    return pd.DataFrame(rows)


def generate_rds_instances() -> pd.DataFrame:
    """
    Generate RDS instance inventory matching data/inventory/rds_instances.csv schema.

    Columns: account_id, region, db_instance_id, engine, engine_version,
             db_instance_class, multi_az, allocated_storage_gb, storage_type,
             iops, status, endpoint, port, publicly_accessible,
             max_allocated_storage, backup_retention_period,
             auto_minor_version_upgrade, deletion_protection,
             instance_create_time, tags
    """
    instances = [
        {
            "db_instance_id": "prod-postgres-primary",
            "db_instance_class": "db.r5.large",
            "multi_az": True,
            "allocated_storage_gb": 100,
            "storage_type": "gp3",
            "iops": 3000,
            "max_allocated_storage": 500,
            "backup_retention_period": 7,
            "deletion_protection": True,
            "create_time": "2025-01-15 10:00:00.000000+00:00",
        },
        {
            "db_instance_id": "staging-postgres",
            "db_instance_class": "db.t4g.medium",
            "multi_az": False,
            "allocated_storage_gb": 20,
            "storage_type": "gp3",
            "iops": "",
            "max_allocated_storage": 100,
            "backup_retention_period": 1,
            "deletion_protection": False,
            "create_time": "2025-02-01 14:30:00.000000+00:00",
        },
    ]

    rows = []
    for inst in instances:
        od_rate = RDS_OD_HOURLY.get(inst["db_instance_class"], 0.10)
        monthly_cost = round(od_rate * HOURS_PER_MONTH, 2)
        # Multi-AZ doubles the cost
        if inst["multi_az"]:
            monthly_cost = round(monthly_cost * 2, 2)

        rows.append({
            "account_id": ACCOUNT_ID,
            "region": REGION,
            "db_instance_id": inst["db_instance_id"],
            "engine": "postgres",
            "engine_version": "15.4",
            "db_instance_class": inst["db_instance_class"],
            "multi_az": inst["multi_az"],
            "allocated_storage_gb": inst["allocated_storage_gb"],
            "storage_type": inst["storage_type"],
            "iops": inst["iops"],
            "status": "available",
            "endpoint": f"{inst['db_instance_id']}.synth.{REGION}.rds.amazonaws.com",
            "port": 5432,
            "publicly_accessible": False,
            "max_allocated_storage": inst["max_allocated_storage"],
            "backup_retention_period": inst["backup_retention_period"],
            "auto_minor_version_upgrade": True,
            "deletion_protection": inst["deletion_protection"],
            "instance_create_time": inst["create_time"],
            "tags": f"Environment={'production' if 'prod' in inst['db_instance_id'] else 'staging'}",
            "pricing_model": "on-demand",
            "monthly_cost": monthly_cost,
        })

    return pd.DataFrame(rows)


def generate_s3_buckets() -> pd.DataFrame:
    """
    Generate S3 bucket inventory matching data/inventory/s3_buckets.csv schema.

    Columns: account_id, bucket_name, region, creation_date, versioning,
             default_encryption, public_access_block
    """
    buckets = [
        {"name": "app-user-uploads",  "created": "2024-06-15T10:00:00+00:00", "versioning": "Enabled",   "size_gb": 500.0, "gets": 150, "puts": 80},
        {"name": "app-logs",          "created": "2024-06-15T10:05:00+00:00", "versioning": "Suspended", "size_gb": 120.0, "gets": 5,   "puts": 200},
        {"name": "app-backups",       "created": "2024-07-01T08:00:00+00:00", "versioning": "Enabled",   "size_gb": 250.0, "gets": 2,   "puts": 10},
        {"name": "app-static-assets", "created": "2024-06-15T10:10:00+00:00", "versioning": "",          "size_gb": 55.0,  "gets": 5000, "puts": 20},
    ]

    rows = []
    block = "{'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True}"
    for b in buckets:
        monthly_cost = round(b["size_gb"] * S3_PRICE_STANDARD_PER_GB, 2)
        rows.append({
            "account_id": ACCOUNT_ID,
            "bucket_name": b["name"],
            "region": REGION,
            "creation_date": b["created"],
            "versioning": b["versioning"],
            "default_encryption": "AES256",
            "public_access_block": block,
            "size_gb": b["size_gb"],
            "num_objects": 0,  # will be set in main() from metrics
            "avg_daily_get_requests": b["gets"],
            "avg_daily_put_requests": b["puts"],
            "monthly_cost": monthly_cost,
            "storage_class": "STANDARD",
        })

    return pd.DataFrame(rows)


def generate_lambda_functions() -> pd.DataFrame:
    """
    Generate Lambda functions inventory matching data/inventory/lambda_functions.csv schema.

    Columns: account_id, region, function_name, function_arn, runtime,
             memory_size, timeout, handler, last_modified, code_size,
             description, vpc_subnet_ids, vpc_security_group_ids, tags
    """
    functions = [
        {"name": "image-resizer",   "runtime": "python3.12", "memory": 512,  "timeout": 30,  "handler": "index.handler", "size": 5242880,  "desc": "Resize uploaded images",  "inv_mean": 12000, "dur_mean_ms": 200},
        {"name": "email-sender",    "runtime": "python3.12", "memory": 256,  "timeout": 15,  "handler": "index.handler", "size": 2097152,  "desc": "Send transactional emails", "inv_mean": 3000,  "dur_mean_ms": 75},
        {"name": "log-processor",   "runtime": "python3.12", "memory": 1024, "timeout": 300, "handler": "index.handler", "size": 10485760, "desc": "Process and aggregate logs", "inv_mean": 1500,  "dur_mean_ms": 2500},
        {"name": "webhook-handler", "runtime": "nodejs20.x", "memory": 256,  "timeout": 10,  "handler": "index.handler", "size": 1048576,  "desc": "Handle incoming webhooks", "inv_mean": 20000, "dur_mean_ms": 35},
    ]

    rows = []
    for fn in functions:
        arn = f"arn:aws:lambda:{REGION}:000000000000:function:{fn['name']}"
        # Estimate monthly cost: (memory_GB * duration_sec * invocations * 30) * price + request price
        mem_gb = fn["memory"] / 1024
        dur_sec = fn["dur_mean_ms"] / 1000
        monthly_invocations = fn["inv_mean"] * 30
        compute_cost = mem_gb * dur_sec * monthly_invocations * LAMBDA_PRICE_PER_GB_SEC
        request_cost = monthly_invocations * LAMBDA_PRICE_PER_REQUEST
        monthly_cost = round(compute_cost + request_cost, 2)

        rows.append({
            "account_id": ACCOUNT_ID,
            "region": REGION,
            "function_name": fn["name"],
            "function_arn": arn,
            "runtime": fn["runtime"],
            "memory_size": fn["memory"],
            "timeout": fn["timeout"],
            "handler": fn["handler"],
            "last_modified": "2025-06-01T12:00:00.000+0000",
            "code_size": fn["size"],
            "description": fn["desc"],
            "vpc_subnet_ids": "",
            "vpc_security_group_ids": "",
            "tags": "Environment=production",
            "avg_daily_invocations": fn["inv_mean"],
            "avg_duration_ms": fn["dur_mean_ms"],
            "monthly_cost": monthly_cost,
        })

    return pd.DataFrame(rows)


def generate_ebs_volumes() -> pd.DataFrame:
    """
    Generate EBS volume inventory matching data/inventory/ebs_volumes.csv schema.

    Columns: account_id, region, volume_id, size_gb, volume_type, iops,
             throughput, encrypted, state, availability_zone, snapshot_id,
             create_time, attachments, tags
    """
    volume_sizes = {
        "prod-web-1": 100, "prod-web-2": 100,
        "prod-api-1": 50, "prod-cache-1": 50,
        "staging-web": 30, "staging-api": 20,
        "dev-server": 30, "batch-processor": 200,
    }
    volume_types = {
        "prod-web-1": "gp3", "prod-web-2": "gp3",
        "prod-api-1": "gp3", "prod-cache-1": "gp3",
        "staging-web": "gp2", "staging-api": "gp2",
        "dev-server": "gp2", "batch-processor": "io2",
    }

    rows = []
    for i, inst in enumerate(EC2_FLEET):
        vid = _volume_id(inst["name"])
        iid = _instance_id(inst["name"])
        vtype = volume_types[inst["name"]]
        size = volume_sizes[inst["name"]]
        iops = 3000 if vtype in ("gp3", "io2") else 100
        throughput = 125 if vtype == "gp3" else ""
        launch = datetime(2025, 1, 10 + i, 8, 30, 0)

        # Compute monthly cost
        base_cost = EBS_PRICE_PER_GB.get(vtype, 0.10) * size
        iops_cost = EBS_IO2_IOPS_PRICE * iops if vtype == "io2" else 0
        monthly_cost = round(base_cost + iops_cost, 2)

        rows.append({
            "account_id": ACCOUNT_ID,
            "region": REGION,
            "volume_id": vid,
            "size_gb": size,
            "volume_type": vtype,
            "iops": iops,
            "throughput": throughput,
            "encrypted": True,
            "state": "in-use",
            "availability_zone": inst["az"],
            "snapshot_id": "",
            "create_time": launch.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
            "attachments": f"{iid}:/dev/xvda",
            "tags": f"Name={inst['name']}-root;Environment={inst['env']}",
            "attached_instance_id": iid,
            "monthly_cost": monthly_cost,
        })

    # Add 1 unattached volume (orphaned after terminated instance)
    rows.append({
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "volume_id": _volume_id("orphan-data"),
        "size_gb": 50,
        "volume_type": "gp2",
        "iops": 150,
        "throughput": "",
        "encrypted": True,
        "state": "available",
        "availability_zone": f"{REGION}a",
        "snapshot_id": "",
        "create_time": "2025-02-01T10:00:00.000000+00:00",
        "attachments": "",
        "tags": "Name=orphan-data-volume;Environment=production",
        "attached_instance_id": None,
        "monthly_cost": round(EBS_PRICE_PER_GB["gp2"] * 50, 2),
    })

    return pd.DataFrame(rows)


def generate_elasticache_nodes() -> pd.DataFrame:
    """Generate ElastiCache node inventory.

    Columns: account_id, region, cache_cluster_id, cache_node_type, engine,
             engine_version, num_cache_nodes
    """
    nodes = [
        {"id": "prod-redis-sessions",   "type": "cache.r5.large",  "engine": "redis",     "version": "7.0", "count": 2},
        {"id": "prod-memcached-cache",   "type": "cache.m5.large",  "engine": "memcached", "version": "1.6", "count": 1},
        {"id": "staging-redis",          "type": "cache.t3.medium", "engine": "redis",     "version": "7.0", "count": 1},
    ]
    rows = []
    for n in nodes:
        od_rate = ELASTICACHE_OD_HOURLY.get(n["type"], 0.10)
        monthly_cost = round(od_rate * HOURS_PER_MONTH * n["count"], 2)
        rows.append({
            "account_id": ACCOUNT_ID, "region": REGION,
            "cache_cluster_id": n["id"], "cache_node_type": n["type"],
            "engine": n["engine"], "engine_version": n["version"],
            "num_cache_nodes": n["count"],
            "pricing_model": "on-demand",
            "monthly_cost": monthly_cost,
        })
    return pd.DataFrame(rows)


def generate_ecs_services() -> pd.DataFrame:
    """Generate ECS/Fargate service inventory.

    Columns: account_id, region, service_name, cluster_name, launch_type,
             desired_count, cpu, memory_mb
    """
    # Fargate pricing: $0.04048/vCPU/hr + $0.004445/GB/hr
    FARGATE_VCPU_HR = 0.04048
    FARGATE_GB_HR = 0.004445

    services = [
        {"name": "prod-api-service",     "cluster": "prod-cluster",    "count": 3, "cpu": 512,  "mem": 1024},
        {"name": "prod-worker-service",  "cluster": "prod-cluster",    "count": 2, "cpu": 256,  "mem": 512},
        {"name": "staging-api-service",  "cluster": "staging-cluster", "count": 1, "cpu": 256,  "mem": 512},
        {"name": "prod-scheduled-tasks", "cluster": "prod-cluster",    "count": 1, "cpu": 1024, "mem": 2048},
    ]
    rows = []
    for s in services:
        vcpu = s["cpu"] / 1024
        mem_gb = s["mem"] / 1024
        hourly = (vcpu * FARGATE_VCPU_HR + mem_gb * FARGATE_GB_HR) * s["count"]
        monthly_cost = round(hourly * HOURS_PER_MONTH, 2)
        rows.append({
            "account_id": ACCOUNT_ID, "region": REGION,
            "service_name": s["name"], "cluster_name": s["cluster"],
            "launch_type": "FARGATE", "desired_count": s["count"],
            "cpu": s["cpu"], "memory_mb": s["mem"],
            "monthly_cost": monthly_cost,
        })
    return pd.DataFrame(rows)


def generate_dynamodb_tables() -> pd.DataFrame:
    """Generate DynamoDB table inventory.

    Columns: account_id, region, table_name, capacity_mode,
             provisioned_rcu, provisioned_wcu, storage_gb, item_count
    """
    tables = [
        {"name": "prod-sessions",       "mode": "ON_DEMAND",   "rcu": None, "wcu": None, "gb": 15.0, "items": 500000, "avg_rcu": 50, "avg_wcu": 25},
        {"name": "prod-user-profiles",  "mode": "PROVISIONED", "rcu": 100,  "wcu": 50,   "gb": 8.0,  "items": 120000, "avg_rcu": 60, "avg_wcu": 30},
        {"name": "staging-sessions",    "mode": "ON_DEMAND",   "rcu": None, "wcu": None, "gb": 2.0,  "items": 50000,  "avg_rcu": 10, "avg_wcu": 5},
    ]
    rows = []
    for t in tables:
        if t["mode"] == "PROVISIONED":
            # Provisioned: RCU * price + WCU * price
            monthly_cost = round(t["rcu"] * DYNAMO_PRICE_RCU_MONTH + t["wcu"] * DYNAMO_PRICE_WCU_MONTH, 2)
        else:
            # On-demand: estimate from avg consumed units * 30 days * 24 hours
            monthly_reads = t["avg_rcu"] * 30 * 24  # ~hourly avg * hours/month
            monthly_writes = t["avg_wcu"] * 30 * 24
            monthly_cost = round(
                (monthly_reads / 1_000_000) * DYNAMO_PRICE_READ_REQ_M +
                (monthly_writes / 1_000_000) * DYNAMO_PRICE_WRITE_REQ_M +
                t["gb"] * 0.25,  # $0.25/GB/month storage
                2
            )
        rows.append({
            "account_id": ACCOUNT_ID, "region": REGION,
            "table_name": t["name"], "capacity_mode": t["mode"],
            "provisioned_rcu": t["rcu"], "provisioned_wcu": t["wcu"],
            "storage_gb": t["gb"], "item_count": t["items"],
            "monthly_cost": monthly_cost,
        })
    return pd.DataFrame(rows)


def generate_nat_gateways() -> pd.DataFrame:
    """Generate NAT Gateway inventory.

    Columns: account_id, region, nat_gateway_id, vpc_id, subnet_id, state
    """
    gateways = [
        {"id": "nat-0synth00000000001", "az": f"{REGION}a", "data_gb": 250.0},
        {"id": "nat-0synth00000000002", "az": f"{REGION}b", "data_gb": 170.0},
    ]
    rows = []
    for gw in gateways:
        fixed_cost = NAT_PRICE_HOURLY * HOURS_PER_MONTH
        data_cost = NAT_PRICE_PER_GB * gw["data_gb"]
        monthly_cost = round(fixed_cost + data_cost, 2)
        rows.append({
            "account_id": ACCOUNT_ID, "region": REGION,
            "nat_gateway_id": gw["id"], "vpc_id": _vpc_id(),
            "subnet_id": _subnet_id(gw["az"]), "state": "available",
            "monthly_data_processed_gb": gw["data_gb"],
            "monthly_cost": monthly_cost,
        })
    return pd.DataFrame(rows)


def generate_elb_instances() -> pd.DataFrame:
    """Generate ELB/ALB inventory.

    Columns: account_id, region, load_balancer_arn, load_balancer_name,
             type, scheme, dns_name, vpc_id, state, created_time
    """
    elbs = [
        {"name": "prod-web-alb",    "scheme": "internet-facing", "targets": 2, "healthy": 2, "req_mean": 10000},
        {"name": "prod-api-alb",    "scheme": "internet-facing", "targets": 1, "healthy": 1, "req_mean": 5000},
        {"name": "staging-web-alb", "scheme": "internet-facing", "targets": 1, "healthy": 1, "req_mean": 1000},
    ]
    rows = []
    for e in elbs:
        h = hashlib.md5(e["name"].encode()).hexdigest()[:32]
        arn = f"arn:aws:elasticloadbalancing:{REGION}:000000000000:loadbalancer/app/{e['name']}/{h}"
        monthly_cost = round(ELB_ALB_HOURLY * 720, 2)  # base ALB cost
        avg_daily_requests = e["req_mean"] * 24  # hourly mean * 24h
        rows.append({
            "account_id": ACCOUNT_ID, "region": REGION,
            "load_balancer_arn": arn, "load_balancer_name": e["name"],
            "type": "application", "scheme": e["scheme"],
            "dns_name": f"{e['name']}-000000000.{REGION}.elb.amazonaws.com",
            "vpc_id": _vpc_id(), "state": "active",
            "created_time": "2025-01-15T10:00:00+00:00",
            "target_count": e["targets"],
            "healthy_target_count": e["healthy"],
            "avg_daily_requests": avg_daily_requests,
            "monthly_cost": monthly_cost,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Metrics generators
# ---------------------------------------------------------------------------

def _diurnal_cpu(hour: int, is_weekday: bool, profile: str, rng: np.random.Generator) -> Tuple[float, float]:
    """
    Return (cpu_avg, cpu_max) for one hour based on instance profile.

    Profiles:
        prod-web: diurnal 8-35% weekday, 4-15% weekend
        prod-api: spiky 35-55% business hours
        prod-cache: steady 20-30%
        staging: 5-15% weekday work hours, 1-3% otherwise
        dev: 2-8% with random spikes
        batch: 1% except 2-5am = 85-95%
    """
    noise = rng.normal(0, 1)

    if profile == "prod-web":
        # Diurnal template
        template_wd = {0: 8, 1: 7, 2: 6, 3: 6, 4: 7, 5: 8, 6: 10,
                       7: 15, 8: 20, 9: 22, 10: 28, 11: 30, 12: 32,
                       13: 34, 14: 35, 15: 33, 16: 30, 17: 25, 18: 22,
                       19: 18, 20: 15, 21: 12, 22: 10, 23: 9}
        template_we = {h: max(3, v * 0.42) for h, v in template_wd.items()}
        base = template_wd[hour] if is_weekday else template_we[hour]
        avg = max(1.0, base + noise * 3.5)

    elif profile == "prod-api":
        if is_weekday and 8 <= hour <= 18:
            avg = max(5.0, rng.normal(48, 8))
        elif is_weekday:
            avg = max(3.0, rng.normal(15, 5))
        else:
            avg = max(2.0, rng.normal(10, 4))

    elif profile == "prod-cache":
        avg = max(5.0, rng.normal(25, 3))

    elif profile == "staging":
        if is_weekday and 9 <= hour <= 17:
            avg = max(1.0, rng.normal(12, 3))
        else:
            avg = max(0.5, rng.normal(2, 1))

    elif profile == "dev":
        avg = max(0.5, rng.normal(5, 2))
        # Random spike 5% of hours
        if rng.random() < 0.05:
            avg = rng.uniform(35, 55)

    elif profile == "batch":
        if 2 <= hour <= 4:
            avg = max(70.0, rng.normal(90, 4))
        else:
            avg = max(0.5, rng.normal(1.5, 0.5))

    else:
        avg = max(1.0, rng.normal(10, 3))

    avg = min(avg, 100.0)
    cpu_max = min(100.0, avg + abs(rng.normal(0, 5)) + 3.0)
    return round(avg, 2), round(cpu_max, 2)


# Map instance names to CPU profiles
_CPU_PROFILES = {
    "prod-web-1": "prod-web", "prod-web-2": "prod-web",
    "prod-api-1": "prod-api", "prod-cache-1": "prod-cache",
    "staging-web": "staging", "staging-api": "staging",
    "dev-server": "dev", "batch-processor": "batch",
}


def generate_ec2_metrics(days: int = 90, seed: int = 42) -> pd.DataFrame:
    """
    Generate EC2 metrics matching data/metrics/ec2/ec2_metrics_consolidated.csv schema.

    Columns: account_id, region, instance_id, timestamp, cpu_avg, cpu_max,
             network_in_avg, network_out_avg, disk_read_ops_avg,
             disk_write_ops_avg, disk_read_bytes_avg, disk_write_bytes_avg,
             status_check_failed_max, memory_used_percent_avg, period_seconds

    NOTE: The real data has instance_id and timestamp swapped (known bug).
    Synthetic data uses the CORRECT column order per the header.
    """
    rng = np.random.default_rng(seed)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    rows = []
    for inst in EC2_FLEET:
        iid = _instance_id(inst["name"])
        profile = _CPU_PROFILES[inst["name"]]

        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour, minute=0, second=0)
                is_wd = ts.weekday() < 5
                cpu_avg, cpu_max = _diurnal_cpu(hour, is_wd, profile, rng)

                # Network correlates loosely with CPU
                net_scale = cpu_avg / 30.0
                net_in = max(0, rng.normal(5_000_000 * net_scale, 1_000_000))
                net_out = max(0, rng.normal(8_000_000 * net_scale, 2_000_000))

                # Disk I/O
                disk_ro = max(0, rng.normal(50 * net_scale, 10))
                disk_wo = max(0, rng.normal(30 * net_scale, 8))
                disk_rb = max(0, rng.normal(500_000 * net_scale, 100_000))
                disk_wb = max(0, rng.normal(300_000 * net_scale, 80_000))

                # Memory (approximate — no real CloudWatch Agent data)
                if profile == "prod-cache":
                    mem = max(10, rng.normal(72, 5))
                elif profile in ("prod-web", "prod-api"):
                    mem = max(10, rng.normal(45, 8))
                else:
                    mem = max(5, rng.normal(25, 7))

                rows.append({
                    "account_id": ACCOUNT_ID,
                    "region": REGION,
                    "instance_id": iid,
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "cpu_avg": cpu_avg,
                    "cpu_max": cpu_max,
                    "network_in_avg": round(net_in, 2),
                    "network_out_avg": round(net_out, 2),
                    "disk_read_ops_avg": round(disk_ro, 2),
                    "disk_write_ops_avg": round(disk_wo, 2),
                    "disk_read_bytes_avg": round(disk_rb, 2),
                    "disk_write_bytes_avg": round(disk_wb, 2),
                    "status_check_failed_max": 0,
                    "memory_used_percent_avg": round(min(mem, 98), 2),
                    "period_seconds": 3600,
                })
            current += timedelta(days=1)

    return pd.DataFrame(rows)


def generate_rds_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """
    Generate RDS metrics matching data/metrics/rds/rds_metrics_consolidated.csv schema.

    Columns: account_id, region, db_instance_id, timestamp, cpu_util_avg,
             free_storage_avg, free_mem_avg, db_conns_avg, read_iops_avg,
             write_iops_avg, read_latency_avg, write_latency_avg,
             queue_depth_avg, net_rx_avg, net_tx_avg, period_seconds

    NOTE: The real data has db_instance_id and timestamp swapped (known bug).
    Synthetic data uses the CORRECT column order per the header.
    """
    rng = np.random.default_rng(seed + 1)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    rds_instances = [
        {"id": "prod-postgres-primary", "cpu_mean": 20, "cpu_std": 4,
         "free_storage": 80_000_000_000, "free_mem": 12_000_000_000,
         "conns_mean": 45, "conns_std": 12},
        {"id": "staging-postgres", "cpu_mean": 7, "cpu_std": 2,
         "free_storage": 18_000_000_000, "free_mem": 3_000_000_000,
         "conns_mean": 5, "conns_std": 3},
    ]

    rows = []
    for inst in rds_instances:
        current = start_date
        day_count = 0
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour, minute=0, second=0)
                is_wd = ts.weekday() < 5

                # CPU with slight diurnal for prod
                cpu_bump = 1.2 if (is_wd and 9 <= hour <= 18) else 0.9
                cpu = max(1.0, min(100.0, rng.normal(inst["cpu_mean"] * cpu_bump, inst["cpu_std"])))

                # Free storage decreases slowly over time
                storage_decay = inst["free_storage"] * (1.0 - 0.0003 * day_count)
                free_storage = max(1_000_000_000, rng.normal(storage_decay, storage_decay * 0.001))

                free_mem = max(100_000_000, rng.normal(inst["free_mem"], inst["free_mem"] * 0.05))
                conns = max(0, rng.normal(inst["conns_mean"] * cpu_bump, inst["conns_std"]))

                read_iops = max(0, rng.normal(50 * cpu_bump, 15))
                write_iops = max(0, rng.normal(30 * cpu_bump, 10))
                read_lat = max(0.0001, rng.normal(0.002, 0.0008))
                write_lat = max(0.0001, rng.normal(0.003, 0.001))
                queue = max(0, rng.normal(0.5 * cpu_bump, 0.2))
                net_rx = max(0, rng.normal(500_000 * cpu_bump, 100_000))
                net_tx = max(0, rng.normal(800_000 * cpu_bump, 200_000))

                rows.append({
                    "account_id": ACCOUNT_ID,
                    "region": REGION,
                    "db_instance_id": inst["id"],
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "cpu_util_avg": round(cpu, 6),
                    "free_storage_avg": round(free_storage, 2),
                    "free_mem_avg": round(free_mem, 2),
                    "db_conns_avg": round(conns, 2),
                    "read_iops_avg": round(read_iops, 4),
                    "write_iops_avg": round(write_iops, 4),
                    "read_latency_avg": round(read_lat, 6),
                    "write_latency_avg": round(write_lat, 6),
                    "queue_depth_avg": round(queue, 4),
                    "net_rx_avg": round(net_rx, 2),
                    "net_tx_avg": round(net_tx, 2),
                    "period_seconds": 3600,
                })
            current += timedelta(days=1)
            day_count += 1

    return pd.DataFrame(rows)


def generate_elasticache_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate ElastiCache metrics with realistic cache hit/miss patterns.

    Columns: account_id, region, cache_cluster_id, timestamp, cpu_util_avg,
             memory_utilization_avg, curr_connections_avg, cache_hits,
             cache_misses, evictions
    """
    rng = np.random.default_rng(seed + 10)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    nodes = [
        {"id": "prod-redis-sessions",  "cpu_mean": 18, "mem_mean": 68, "conns_mean": 120, "hits_mean": 3000, "miss_pct": 0.03},
        {"id": "prod-memcached-cache",  "cpu_mean": 12, "mem_mean": 45, "conns_mean": 80,  "hits_mean": 2000, "miss_pct": 0.05},
        {"id": "staging-redis",         "cpu_mean": 5,  "mem_mean": 25, "conns_mean": 10,  "hits_mean": 500,  "miss_pct": 0.04},
    ]

    rows = []
    for node in nodes:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                bump = 1.2 if (is_wd and 9 <= hour <= 18) else 0.85

                cpu = np.clip(rng.normal(node["cpu_mean"] * bump, 3), 1, 100)
                mem = np.clip(rng.normal(node["mem_mean"], 4), 5, 99)
                conns = max(0, int(rng.normal(node["conns_mean"] * bump, node["conns_mean"] * 0.15)))
                hits = max(0, int(rng.normal(node["hits_mean"] * bump, node["hits_mean"] * 0.1)))
                misses = max(0, int(hits * rng.normal(node["miss_pct"], 0.01)))
                evictions = max(0, int(rng.exponential(2)))

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "cache_cluster_id": node["id"],
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "cpu_util_avg": round(cpu, 2),
                    "memory_utilization_avg": round(mem, 2),
                    "curr_connections_avg": conns,
                    "cache_hits": hits, "cache_misses": misses,
                    "evictions": evictions,
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_ecs_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate ECS/Fargate metrics with diurnal CPU/memory patterns.

    Columns: account_id, region, service_name, cluster_name, timestamp,
             cpu_utilization_avg, memory_utilization_avg,
             running_task_count, desired_task_count
    """
    rng = np.random.default_rng(seed + 11)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    services = [
        {"name": "prod-api-service",     "cluster": "prod-cluster",    "cpu_mean": 35, "mem_mean": 60, "desired": 3},
        {"name": "prod-worker-service",  "cluster": "prod-cluster",    "cpu_mean": 70, "mem_mean": 75, "desired": 2},
        {"name": "staging-api-service",  "cluster": "staging-cluster", "cpu_mean": 10, "mem_mean": 30, "desired": 1},
        {"name": "prod-scheduled-tasks", "cluster": "prod-cluster",    "cpu_mean": 5,  "mem_mean": 20, "desired": 1},
    ]

    rows = []
    for svc in services:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                bump = 1.3 if (is_wd and 9 <= hour <= 18) else 0.8

                cpu = np.clip(rng.normal(svc["cpu_mean"] * bump, 5), 1, 100)
                mem = np.clip(rng.normal(svc["mem_mean"], 5), 5, 99)
                running = svc["desired"]
                # Occasional scale-up for API during peak
                if svc["name"].endswith("api-service") and bump > 1 and rng.random() < 0.1:
                    running += 1

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "service_name": svc["name"], "cluster_name": svc["cluster"],
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "cpu_utilization_avg": round(cpu, 2),
                    "memory_utilization_avg": round(mem, 2),
                    "running_task_count": running,
                    "desired_task_count": svc["desired"],
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_dynamodb_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate DynamoDB metrics with consumed vs provisioned capacity.

    Columns: account_id, region, table_name, timestamp,
             consumed_read_units_avg, consumed_write_units_avg,
             provisioned_read_units, provisioned_write_units,
             throttled_requests
    """
    rng = np.random.default_rng(seed + 12)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    tables = [
        {"name": "prod-sessions",      "rcu_mean": 50, "wcu_mean": 25, "prov_rcu": None, "prov_wcu": None},
        {"name": "prod-user-profiles", "rcu_mean": 60, "wcu_mean": 30, "prov_rcu": 100,  "prov_wcu": 50},
        {"name": "staging-sessions",   "rcu_mean": 10, "wcu_mean": 5,  "prov_rcu": None, "prov_wcu": None},
    ]

    rows = []
    for tbl in tables:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                bump = 1.3 if (is_wd and 9 <= hour <= 18) else 0.7

                rcu = max(0, rng.normal(tbl["rcu_mean"] * bump, tbl["rcu_mean"] * 0.15))
                wcu = max(0, rng.normal(tbl["wcu_mean"] * bump, tbl["wcu_mean"] * 0.15))
                throttled = 0
                if tbl["prov_rcu"] and rcu > tbl["prov_rcu"] * 0.9:
                    throttled = max(0, int(rng.poisson(2)))

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "table_name": tbl["name"],
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "consumed_read_units_avg": round(rcu, 2),
                    "consumed_write_units_avg": round(wcu, 2),
                    "provisioned_read_units": tbl["prov_rcu"],
                    "provisioned_write_units": tbl["prov_wcu"],
                    "throttled_requests": throttled,
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_nat_gateway_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate NAT Gateway metrics with traffic patterns.

    Columns: account_id, region, nat_gateway_id, timestamp,
             bytes_in_avg, bytes_out_avg, packets_in_avg,
             packets_out_avg, active_connections_avg
    """
    rng = np.random.default_rng(seed + 13)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    gateways = [
        {"id": "nat-0synth00000000001", "traffic_scale": 1.0},
        {"id": "nat-0synth00000000002", "traffic_scale": 0.7},
    ]

    rows = []
    for gw in gateways:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                bump = 1.3 if (is_wd and 9 <= hour <= 18) else 0.6
                scale = gw["traffic_scale"] * bump

                bytes_in = max(0, rng.normal(100_000_000 * scale, 20_000_000))
                bytes_out = max(0, rng.normal(200_000_000 * scale, 40_000_000))
                pkts_in = max(0, int(rng.normal(80000 * scale, 15000)))
                pkts_out = max(0, int(rng.normal(150000 * scale, 25000)))
                conns = max(0, int(rng.normal(1000 * scale, 200)))

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "nat_gateway_id": gw["id"],
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "bytes_in_avg": round(bytes_in, 2),
                    "bytes_out_avg": round(bytes_out, 2),
                    "packets_in_avg": pkts_in,
                    "packets_out_avg": pkts_out,
                    "active_connections_avg": conns,
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_elb_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate ELB/ALB metrics with request count and HTTP status patterns.

    Columns: account_id, region, elb_arn, timestamp, request_count,
             active_connections, new_connections, processed_bytes,
             http_2xx, http_3xx, http_4xx, http_5xx,
             target_response_time_avg
    """
    rng = np.random.default_rng(seed + 14)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    elbs = [
        {"name": "prod-web-alb",    "req_mean": 10000, "resp_ms": 100, "conns_mean": 300},
        {"name": "prod-api-alb",    "req_mean": 5000,  "resp_ms": 50,  "conns_mean": 150},
        {"name": "staging-web-alb", "req_mean": 1000,  "resp_ms": 120, "conns_mean": 30},
    ]

    rows = []
    for elb in elbs:
        h = hashlib.md5(elb["name"].encode()).hexdigest()[:32]
        arn = f"arn:aws:elasticloadbalancing:{REGION}:000000000000:loadbalancer/app/{elb['name']}/{h}"
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                bump = 1.4 if (is_wd and 9 <= hour <= 18) else 0.5

                reqs = max(0, int(rng.normal(elb["req_mean"] * bump, elb["req_mean"] * 0.15)))
                conns = max(0, int(rng.normal(elb["conns_mean"] * bump, elb["conns_mean"] * 0.2)))
                new_conns = max(0, int(conns * rng.uniform(0.3, 0.6)))
                proc_bytes = max(0, rng.normal(reqs * 5000, reqs * 1000))

                http_2xx = max(0, int(reqs * rng.normal(0.90, 0.02)))
                http_3xx = max(0, int(reqs * rng.normal(0.05, 0.01)))
                http_4xx = max(0, int(reqs * rng.normal(0.04, 0.01)))
                http_5xx = max(0, int(reqs * rng.normal(0.01, 0.005)))

                resp_time = max(0.005, rng.normal(elb["resp_ms"] / 1000, 0.02))

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "elb_arn": arn,
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "request_count": reqs,
                    "active_connections": conns,
                    "new_connections": new_conns,
                    "processed_bytes": round(proc_bytes, 2),
                    "http_2xx": http_2xx, "http_3xx": http_3xx,
                    "http_4xx": http_4xx, "http_5xx": http_5xx,
                    "target_response_time_avg": round(resp_time, 4),
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_ebs_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate EBS volume metrics tied to EC2 instance workload patterns.

    Columns: account_id, region, volume_id, timestamp, read_ops_avg,
             write_ops_avg, read_bytes_avg, write_bytes_avg,
             idle_time_seconds
    """
    rng = np.random.default_rng(seed + 15)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    rows = []
    for inst in EC2_FLEET:
        vid = _volume_id(inst["name"])
        profile = _CPU_PROFILES[inst["name"]]
        current = start_date
        while current <= end_date:
            for hour in range(24):
                ts = current.replace(hour=hour)
                is_wd = ts.weekday() < 5
                cpu_avg, _ = _diurnal_cpu(hour, is_wd, profile, rng)
                activity = cpu_avg / 50.0

                r_ops = max(0, rng.normal(60 * activity, 15))
                w_ops = max(0, rng.normal(35 * activity, 10))
                r_bytes = max(0, rng.normal(600_000 * activity, 100_000))
                w_bytes = max(0, rng.normal(350_000 * activity, 80_000))
                idle = max(0, 3600 * (1.0 - min(activity, 1.0)) + rng.normal(0, 60))

                rows.append({
                    "account_id": ACCOUNT_ID, "region": REGION,
                    "volume_id": vid,
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "read_ops_avg": round(r_ops, 2),
                    "write_ops_avg": round(w_ops, 2),
                    "read_bytes_avg": round(r_bytes, 2),
                    "write_bytes_avg": round(w_bytes, 2),
                    "idle_time_seconds": round(idle, 2),
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_lambda_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate Lambda invocation metrics per function per day.

    Columns: account_id, region, function_name, date, invocations,
             avg_duration_ms, max_duration_ms, errors, throttles,
             avg_memory_used_mb, memory_allocated_mb
    """
    rng = np.random.default_rng(seed + 16)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    functions = [
        {"name": "image-resizer",   "inv_mean": 12000, "dur_mean": 200,  "mem_alloc": 512,  "mem_used_pct": 0.70},
        {"name": "email-sender",    "inv_mean": 3000,  "dur_mean": 75,   "mem_alloc": 256,  "mem_used_pct": 0.55},
        {"name": "log-processor",   "inv_mean": 1500,  "dur_mean": 2500, "mem_alloc": 1024, "mem_used_pct": 0.80},
        {"name": "webhook-handler", "inv_mean": 20000, "dur_mean": 35,   "mem_alloc": 256,  "mem_used_pct": 0.25},
    ]

    rows = []
    current = start_date
    while current <= end_date:
        is_wd = current.weekday() < 5
        bump = 1.2 if is_wd else 0.6
        for fn in functions:
            inv = max(0, int(rng.normal(fn["inv_mean"] * bump, fn["inv_mean"] * 0.15)))
            dur = max(1, rng.normal(fn["dur_mean"], fn["dur_mean"] * 0.15))
            max_dur = dur * rng.uniform(1.5, 3.0)
            errors = max(0, int(inv * rng.normal(0.003, 0.001)))
            throttles = max(0, int(rng.exponential(1))) if rng.random() < 0.05 else 0
            mem_used = fn["mem_alloc"] * rng.normal(fn["mem_used_pct"], 0.05)

            rows.append({
                "account_id": ACCOUNT_ID, "region": REGION,
                "function_name": fn["name"],
                "date": current.strftime("%Y-%m-%d"),
                "invocations": inv,
                "avg_duration_ms": round(dur, 2),
                "max_duration_ms": round(max_dur, 2),
                "errors": errors, "throttles": throttles,
                "avg_memory_used_mb": round(mem_used, 2),
                "memory_allocated_mb": fn["mem_alloc"],
            })
        current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_s3_metrics(days: int = 45, seed: int = 42) -> pd.DataFrame:
    """Generate S3 bucket size/object metrics over time.

    Columns: account_id, region, bucket_name, timestamp,
             bucket_size_bytes, number_of_objects
    """
    rng = np.random.default_rng(seed + 17)
    end_date = DEFAULT_END_DATE
    start_date = end_date - timedelta(days=days - 1)

    buckets = [
        {"name": "app-user-uploads",  "size_gb": 500,  "growth": 0.005, "objects": 60000,  "obj_growth": 0.003},
        {"name": "app-logs",          "size_gb": 120,  "growth": 0.001, "objects": 25000,  "obj_growth": 0.001},
        {"name": "app-backups",       "size_gb": 250,  "growth": 0.002, "objects": 6000,   "obj_growth": 0.001},
        {"name": "app-static-assets", "size_gb": 55,   "growth": 0.0005,"objects": 11000,  "obj_growth": 0.0003},
    ]

    rows = []
    for b in buckets:
        current = start_date
        day_idx = 0
        while current <= end_date:
            ts = current.replace(hour=0)
            size_bytes = b["size_gb"] * 1e9 * (1 + b["growth"] * day_idx)
            size_bytes += rng.normal(0, size_bytes * 0.005)
            objects = int(b["objects"] * (1 + b["obj_growth"] * day_idx))

            rows.append({
                "account_id": ACCOUNT_ID, "region": REGION,
                "bucket_name": b["name"],
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "bucket_size_bytes": round(max(0, size_bytes), 2),
                "number_of_objects": max(0, objects),
            })
            current += timedelta(days=1)
            day_idx += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pricing generator
# ---------------------------------------------------------------------------

def generate_instance_pricing(real_pricing_path: Optional[Path] = None) -> Tuple[pd.DataFrame, int, int]:
    """
    Generate instance pricing data.

    If real_pricing_path is provided, extracts relevant rows from the real
    pricing file first and only generates synthetic rows for missing
    pricing types (Reserved, Spot for types that only have On-Demand).

    Columns: account_id, month, service, pricing_type, instance_type,
             region, hourly_price_usd, product_family

    Returns:
        Tuple of (DataFrame, real_row_count, synthetic_row_count)
    """
    month = "2025-06"
    real_rows = 0
    rows = []

    # Target instance types we need
    ec2_types_needed = {
        "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge",
        "m5.large", "m5.xlarge", "m5.2xlarge",
        "c5.large", "c5.xlarge", "c5.2xlarge",
        "r5.large", "r5.xlarge",
    }
    pricing_types_needed = {"On-Demand", "Reserved-1yr", "Reserved-3yr", "Spot"}

    # Fallback On-Demand prices (used if real data unavailable)
    od_fallback = {
        "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
        "t3.large": 0.0832, "t3.xlarge": 0.1664,
        "m5.large": 0.0960, "m5.xlarge": 0.1920, "m5.2xlarge": 0.3840,
        "c5.large": 0.0850, "c5.xlarge": 0.1700, "c5.2xlarge": 0.3400,
        "r5.large": 0.1260, "r5.xlarge": 0.2520,
    }

    # Track what we already have: (instance_type, pricing_type) -> price
    existing = {}

    # Try to load real pricing
    if real_pricing_path and real_pricing_path.exists():
        real_df = pd.read_csv(real_pricing_path, on_bad_lines="skip")
        # Filter to us-east-1, EC2, relevant instance types
        mask = (
            (real_df["region"] == "us-east-1") &
            (real_df["service"] == "EC2") &
            (real_df["instance_type"].isin(ec2_types_needed))
        )
        real_ec2 = real_df[mask].drop_duplicates(subset=["instance_type", "pricing_type"])

        for _, row in real_ec2.iterrows():
            itype = row["instance_type"]
            ptype = row["pricing_type"]
            price = row["hourly_price_usd"]
            if pd.notna(price) and price > 0 and ptype in pricing_types_needed:
                existing[(itype, ptype)] = price
                rows.append({
                    "account_id": ACCOUNT_ID,
                    "month": month,
                    "service": "EC2",
                    "pricing_type": ptype,
                    "instance_type": itype,
                    "region": REGION,
                    "hourly_price_usd": price,
                    "product_family": "Compute Instance",
                })
                real_rows += 1

    # Fill missing EC2 pricing types synthetically
    for itype in sorted(ec2_types_needed):
        od_price = existing.get((itype, "On-Demand"), od_fallback.get(itype, 0.10))

        for ptype, multiplier in [("On-Demand", 1.0), ("Reserved-1yr", 0.63),
                                   ("Reserved-3yr", 0.40), ("Spot", 0.30)]:
            if (itype, ptype) not in existing:
                rows.append({
                    "account_id": ACCOUNT_ID,
                    "month": month,
                    "service": "EC2",
                    "pricing_type": ptype,
                    "instance_type": itype,
                    "region": REGION,
                    "hourly_price_usd": round(od_price * multiplier, 4),
                    "product_family": "Compute Instance",
                })

    # RDS pricing (always synthetic — real data doesn't have instance-level RDS pricing)
    rds_types = [
        ("db.t4g.micro", 0.016), ("db.t4g.medium", 0.065),
        ("db.r5.large", 0.240), ("db.r5.xlarge", 0.480),
    ]
    for itype, od_hr in rds_types:
        ri1_hr = round(od_hr * 0.63, 4)
        for ptype, price in [("On-Demand", od_hr), ("Reserved-1yr", ri1_hr)]:
            rows.append({
                "account_id": ACCOUNT_ID,
                "month": month,
                "service": "RDS",
                "pricing_type": ptype,
                "instance_type": itype,
                "region": REGION,
                "hourly_price_usd": price,
                "product_family": "Database Instance",
            })

    # ElastiCache pricing
    for itype, od_hr in ELASTICACHE_OD_HOURLY.items():
        ri1_hr = round(od_hr * 0.63, 4)
        for ptype, price in [("On-Demand", od_hr), ("Reserved-1yr", ri1_hr)]:
            rows.append({
                "account_id": ACCOUNT_ID,
                "month": month,
                "service": "ElastiCache",
                "pricing_type": ptype,
                "instance_type": itype,
                "region": REGION,
                "hourly_price_usd": price,
                "product_family": "Cache Instance",
            })

    df = pd.DataFrame(rows)
    synth_rows = len(df) - real_rows
    return df, real_rows, synth_rows


# ---------------------------------------------------------------------------
# AI recommendations sample
# ---------------------------------------------------------------------------

def generate_ai_recommendations_sample() -> pd.DataFrame:
    """
    Generate sample AI recommendation results.

    Columns: id, app_type, daily_users, uptime_hours, importance,
             budget_usd, region, recommended_instance, recommended_pricing,
             estimated_cost_usd, explanation, created_at
    """
    samples = [
        (1, "Static website", 500, 24, "low", 10.0,
         "t3.micro", "On-Demand", 7.49,
         "Low traffic site fits Free Tier eligible t3.micro. On-Demand is cheapest for unpredictable low usage."),
        (2, "Web application", 5000, 24, "medium", 50.0,
         "t3.medium", "Reserved-1yr", 18.86,
         "Burstable t3.medium handles variable web traffic. Reserved 1yr saves 37% over On-Demand for steady workload."),
        (3, "REST API", 10000, 24, "high", 100.0,
         "c5.large", "Reserved-1yr", 38.59,
         "Compute-optimized c5 is ideal for API workloads. Reserved pricing for production reliability."),
        (4, "E-commerce platform", 20000, 24, "high", 200.0,
         "m5.xlarge", "Reserved-1yr", 87.12,
         "Balanced compute + memory for session management and product catalog. Reserved for cost predictability."),
        (5, "ML training pipeline", 1000, 8, "low", 300.0,
         "c5.2xlarge", "Spot", 73.44,
         "Batch ML workload is fault-tolerant. Spot saves 70% and training can be checkpointed."),
        (6, "PostgreSQL database", 5000, 24, "high", 150.0,
         "r5.large", "Reserved-1yr", 57.17,
         "Memory-optimized r5 suits database workloads. Reserved pricing for always-on production database."),
        (7, "Event-driven microservices", 15000, 24, "medium", 80.0,
         "Lambda", "Pay-per-request", 25.00,
         "Event-driven architecture maps naturally to serverless. Pay only for invocations, no idle cost."),
        (8, "Batch data processing", 500, 4, "low", 40.0,
         "t3.large", "Spot", 18.00,
         "Short-duration fault-tolerant batch job. Spot instance provides 70% savings."),
        (9, "CI/CD build server", 200, 12, "medium", 60.0,
         "c5.xlarge", "On-Demand", 73.44,
         "Compute-heavy builds need c5. On-Demand for variable usage that doesn't justify Reserved commitment."),
        (10, "Redis cache cluster", 8000, 24, "high", 120.0,
         "r5.large", "Reserved-1yr", 57.17,
         "Memory-optimized for in-memory caching. Reserved pricing for always-on production cache."),
    ]

    rows = []
    for s in samples:
        rows.append({
            "id": s[0], "app_type": s[1], "daily_users": s[2],
            "uptime_hours": s[3], "importance": s[4], "budget_usd": s[5],
            "region": REGION,
            "recommended_instance": s[6], "recommended_pricing": s[7],
            "estimated_cost_usd": s[8], "explanation": s[9],
            "created_at": f"2025-06-{s[0]:02d}T12:00:00Z",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def _to_db_records(df: pd.DataFrame, rename: dict | None = None,
                   service_name_map: dict | None = None) -> list[dict]:
    """Convert generator DataFrame to list[dict] with DB-compatible column names.

    Args:
        df: Source DataFrame from a generate_* function.
        rename: Column rename mapping {old_name: new_name}.
        service_name_map: If provided, maps service_name (full AWS) → short name
            and stores result in 'service' key.
    """
    if rename:
        df = df.rename(columns=rename)
    records = df.to_dict("records")
    if service_name_map:
        for r in records:
            if "service_name" in r:
                r["service"] = service_name_map.get(r.pop("service_name"),
                                                     r.get("service_name", "Other"))
            if "cost_amount" in r:
                r["daily_cost"] = r.pop("cost_amount")
    return records


def main() -> None:
    """Generate all synthetic datasets and write to SQLite via storage API."""
    config.setup_logging()

    parser = argparse.ArgumentParser(
        description="Generate synthetic AWS data for Smart Cloud Optimizer"
    )
    parser.add_argument("--days", type=int, default=365,
                        help="Days of cost data (default: 365)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--real-pricing", type=str, default=None,
                        help="Path to real pricing CSV to merge (default: auto-detect)")
    args = parser.parse_args()

    # Auto-detect real pricing path
    real_pricing = None
    if args.real_pricing:
        real_pricing = Path(args.real_pricing)
    else:
        candidates = [
            Path("data/pricing/pricing_consolidated.csv"),
        ]
        for c in candidates:
            if c.exists():
                real_pricing = c
                break

    logger.info(f"Generating synthetic data (days={args.days}, seed={args.seed})...")
    if real_pricing:
        logger.info(f"Real pricing: {real_pricing}")

    # -- DB setup --
    conn = storage.get_connection()
    storage.ensure_schema(conn)
    user_id = storage.ensure_user(conn, ACCOUNT_ID)
    storage.clear_user_data(conn, user_id)
    logger.info(f"DB user: {user_id}")

    # -- Cost data --
    daily = generate_daily_costs(days=args.days, seed=args.seed)
    daily_records = [{"date": r["date"], "total_cost": r["cost_amount"]}
                     for r in daily.to_dict("records")]
    storage.insert_daily_costs(conn, user_id, daily_records)

    service = generate_service_costs(days=args.days, seed=args.seed)
    storage.insert_service_costs(conn, user_id, _to_db_records(
        service, service_name_map=storage.SERVICE_NAME_MAP))

    service_region = generate_service_region_costs(service, seed=args.seed)
    storage.insert_service_region_costs(conn, user_id, _to_db_records(
        service_region, service_name_map=storage.SERVICE_NAME_MAP))

    # -- Inventory --
    ec2_inv = generate_ec2_instances()
    ec2_inv_records = ec2_inv.rename(columns={"launch_time": "launch_date"}).to_dict("records")
    storage.insert_ec2_instances(conn, user_id, ec2_inv_records)

    rds_inv = generate_rds_instances()
    rds_inv_records = rds_inv.rename(columns={"allocated_storage_gb": "storage_gb"}).to_dict("records")
    storage.insert_rds_instances(conn, user_id, rds_inv_records)

    s3_inv = generate_s3_buckets()
    storage.insert_s3_buckets(conn, user_id, _to_db_records(s3_inv, rename={
        "default_encryption": "encryption",
    }))

    lam = generate_lambda_functions()
    storage.insert_lambda_functions(conn, user_id, _to_db_records(lam, rename={
        "memory_size": "memory_mb", "timeout": "timeout_sec",
    }))

    ebs = generate_ebs_volumes()
    storage.insert_ebs_volumes(conn, user_id, _to_db_records(ebs, rename={
        "throughput": "throughput_mbps",
    }))

    elb_inv = generate_elb_instances()
    _elb_type_map = {"application": "ALB", "network": "NLB", "classic": "CLB"}
    elb_inv_records = elb_inv.rename(columns={
        "load_balancer_arn": "elb_arn",
        "load_balancer_name": "elb_name",
        "type": "elb_type",
        "scheme": "elb_scheme",
    }).to_dict("records")
    for r in elb_inv_records:
        r["elb_type"] = _elb_type_map.get(r.get("elb_type", ""), r.get("elb_type", "ALB"))
    storage.insert_elb_instances(conn, user_id, elb_inv_records)

    elasticache_inv = generate_elasticache_nodes()
    storage.insert_elasticache_nodes(conn, user_id, elasticache_inv.to_dict("records"))

    ecs_inv = generate_ecs_services()
    storage.insert_ecs_services(conn, user_id, ecs_inv.to_dict("records"))

    dynamodb_inv = generate_dynamodb_tables()
    storage.insert_dynamodb_tables(conn, user_id, dynamodb_inv.to_dict("records"))

    nat_inv = generate_nat_gateways()
    storage.insert_nat_gateways(conn, user_id, nat_inv.to_dict("records"))

    # -- Metrics --
    ec2_metrics_days = min(args.days, 90)
    ec2_met = generate_ec2_metrics(days=ec2_metrics_days, seed=args.seed)
    storage.insert_ec2_metrics(conn, user_id, _to_db_records(ec2_met, rename={
        "cpu_avg": "cpu_utilization",
        "memory_used_percent_avg": "memory_utilization",
        "network_in_avg": "network_in_kbps",
        "network_out_avg": "network_out_kbps",
        "disk_read_bytes_avg": "disk_read_kbps",
        "disk_write_bytes_avg": "disk_write_kbps",
        "disk_read_ops_avg": "disk_read_ops",
        "disk_write_ops_avg": "disk_write_ops",
    }))

    rds_metrics_days = min(args.days, 45)
    rds_met = generate_rds_metrics(days=rds_metrics_days, seed=args.seed)
    storage.insert_rds_metrics(conn, user_id, _to_db_records(rds_met, rename={
        "cpu_util_avg": "cpu_utilization",
        "free_mem_avg": "memory_utilization",
        "read_iops_avg": "read_iops",
        "write_iops_avg": "write_iops",
        "db_conns_avg": "connections",
        "free_storage_avg": "free_storage_gb",
    }))

    metrics_days = min(args.days, 45)

    lambda_met = generate_lambda_metrics(days=metrics_days, seed=args.seed)
    storage.insert_lambda_metrics(conn, user_id, lambda_met.to_dict("records"))

    s3_met = generate_s3_metrics(days=metrics_days, seed=args.seed)
    storage.insert_s3_metrics(conn, user_id, s3_met.to_dict("records"))

    elasticache_met = generate_elasticache_metrics(days=metrics_days, seed=args.seed)
    storage.insert_elasticache_metrics(conn, user_id, _to_db_records(elasticache_met, rename={
        "cpu_util_avg": "cpu_utilization",
        "memory_utilization_avg": "memory_utilization",
        "curr_connections_avg": "curr_connections",
    }))

    ecs_met = generate_ecs_metrics(days=metrics_days, seed=args.seed)
    storage.insert_ecs_metrics(conn, user_id, _to_db_records(ecs_met, rename={
        "cpu_utilization_avg": "cpu_utilization",
        "memory_utilization_avg": "memory_utilization",
    }))

    dynamodb_met = generate_dynamodb_metrics(days=metrics_days, seed=args.seed)
    storage.insert_dynamodb_metrics(conn, user_id, _to_db_records(dynamodb_met, rename={
        "consumed_read_units_avg": "consumed_read_units",
        "consumed_write_units_avg": "consumed_write_units",
    }))

    nat_met = generate_nat_gateway_metrics(days=metrics_days, seed=args.seed)
    storage.insert_nat_gateway_metrics(conn, user_id, _to_db_records(nat_met, rename={
        "bytes_in_avg": "bytes_in",
        "bytes_out_avg": "bytes_out",
        "packets_in_avg": "packets_in",
        "packets_out_avg": "packets_out",
        "active_connections_avg": "active_connections",
    }))

    elb_met = generate_elb_metrics(days=metrics_days, seed=args.seed)
    storage.insert_elb_metrics(conn, user_id, elb_met.to_dict("records"))

    ebs_met = generate_ebs_metrics(days=metrics_days, seed=args.seed)
    storage.insert_ebs_metrics(conn, user_id, _to_db_records(ebs_met, rename={
        "read_ops_avg": "read_ops",
        "write_ops_avg": "write_ops",
        "read_bytes_avg": "read_bytes",
        "write_bytes_avg": "write_bytes",
    }))

    # -- Pricing (no user_id — reference data) --
    # Generator produces one row per (instance_type, pricing_type) with hourly_price_usd.
    # DB expects one row per instance_type with on_demand_hourly, reserved_1yr_hourly, etc.
    pricing, real_price_rows, synth_price_rows = generate_instance_pricing(real_pricing)
    pricing_pivoted: dict[str, dict] = {}
    # Specs for RDS and ElastiCache (not in config.INSTANCE_SPECS)
    _extra_specs = {
        "db.t4g.micro": (2, 1.0), "db.t4g.medium": (2, 4.0),
        "db.r5.large": (2, 16.0), "db.r5.xlarge": (4, 32.0),
        "cache.t3.micro": (2, 0.5), "cache.t3.medium": (2, 3.09),
        "cache.m5.large": (2, 6.38), "cache.r5.large": (2, 13.07),
    }

    for r in pricing.to_dict("records"):
        itype = r["instance_type"]
        if itype not in pricing_pivoted:
            ec2_spec = storage.INSTANCE_SPECS.get(itype, (None, None))
            extra_spec = _extra_specs.get(itype, (None, None))
            vcpus = ec2_spec[0] or extra_spec[0]
            memory_gb = ec2_spec[1] or extra_spec[1]
            pricing_pivoted[itype] = {
                "service": r.get("service", "EC2"),
                "instance_type": itype,
                "vcpus": vcpus,
                "memory_gb": memory_gb,
            }
        hourly = float(r["hourly_price_usd"])
        ptype = r.get("pricing_type", "On-Demand")
        entry = pricing_pivoted[itype]
        if ptype == "On-Demand":
            entry["on_demand_hourly"] = hourly
            entry["on_demand_monthly"] = round(hourly * HOURS_PER_MONTH, 2)
        elif ptype == "Reserved-1yr":
            entry["reserved_1yr_hourly"] = hourly
            entry["reserved_1yr_monthly"] = round(hourly * HOURS_PER_MONTH, 2)
        elif ptype == "Reserved-3yr":
            entry["reserved_3yr_hourly"] = hourly
            entry["reserved_3yr_monthly"] = round(hourly * HOURS_PER_MONTH, 2)
        elif ptype == "Spot":
            entry["spot_hourly"] = hourly
            entry["spot_monthly"] = round(hourly * HOURS_PER_MONTH, 2)
    # Ensure on_demand defaults exist
    for entry in pricing_pivoted.values():
        entry.setdefault("on_demand_hourly", 0.0)
        entry.setdefault("on_demand_monthly", 0.0)
    storage.insert_instance_pricing(conn, list(pricing_pivoted.values()))

    # -- AI recommendations sample --
    ai_recs = generate_ai_recommendations_sample()
    ai_recs_mapped = [
        {
            "app_type": r["app_type"],
            "expected_users": r["daily_users"],
            "uptime_hours": r["uptime_hours"],
            "importance": r["importance"],
            "budget_monthly": r["budget_usd"],
            "prompt_text": f"{r['app_type']} with {r['daily_users']} daily users",
            "recommended_setup": f"{r['recommended_instance']} ({r['recommended_pricing']})",
            "estimated_cost": r["estimated_cost_usd"],
            "explanation": r["explanation"],
            "llm_model": "synthetic",
        }
        for r in ai_recs.to_dict("records")
    ]
    storage.insert_ai_recommendations(conn, user_id, ai_recs_mapped)

    conn.commit()
    conn.close()

    # -- Summary --
    logger.info("=== Synthetic Data Summary ===")

    dates_dt = pd.to_datetime(daily["date"])
    weekday_mask = dates_dt.dt.weekday < 5
    wd_avg = daily.loc[weekday_mask, "cost_amount"].mean()
    we_avg = daily.loc[~weekday_mask, "cost_amount"].mean()
    anomaly_count = (daily["cost_amount"] > 2.0 * daily["cost_amount"].median()).sum()

    first_14 = daily["cost_amount"].iloc[:14].mean()
    last_14 = daily["cost_amount"].iloc[-14:].mean()
    trend_pct = ((last_14 - first_14) / first_14) * 100

    lines = [
        f"daily_costs:              {len(daily):>6} rows",
        f"  Range: ${daily['cost_amount'].min():.2f} - ${daily['cost_amount'].max():.2f} (mean: ${daily['cost_amount'].mean():.2f})",
        f"  Weekday avg: ${wd_avg:.2f} | Weekend avg: ${we_avg:.2f} (ratio: {wd_avg/we_avg:.2f}x)",
        f"  Anomalies: {anomaly_count} | Trend: {trend_pct:+.1f}%",
        f"service_costs:            {len(service):>6} rows | {service['service_name'].nunique()} services",
        f"service_region_costs:     {len(service_region):>6} rows",
        f"ec2_instances:            {len(ec2_inv):>6} rows",
        f"rds_instances:            {len(rds_inv):>6} rows",
        f"s3_buckets:               {len(s3_inv):>6} rows",
        f"lambda_functions:         {len(lam):>6} rows",
        f"ebs_volumes:              {len(ebs):>6} rows",
        f"elb_instances:            {len(elb_inv):>6} rows",
        f"elasticache_nodes:        {len(elasticache_inv):>6} rows",
        f"ecs_services:             {len(ecs_inv):>6} rows",
        f"dynamodb_tables:          {len(dynamodb_inv):>6} rows",
        f"nat_gateways:             {len(nat_inv):>6} rows",
        f"ec2_metrics:              {len(ec2_met):>6} rows | {ec2_metrics_days}d",
        f"rds_metrics:              {len(rds_met):>6} rows | {rds_metrics_days}d",
        f"lambda_metrics:           {len(lambda_met):>6} rows | {metrics_days}d",
        f"s3_metrics:               {len(s3_met):>6} rows | {metrics_days}d",
        f"elasticache_metrics:      {len(elasticache_met):>6} rows | {metrics_days}d",
        f"ecs_metrics:              {len(ecs_met):>6} rows | {metrics_days}d",
        f"dynamodb_metrics:         {len(dynamodb_met):>6} rows | {metrics_days}d",
        f"nat_gateway_metrics:      {len(nat_met):>6} rows | {metrics_days}d",
        f"elb_metrics:              {len(elb_met):>6} rows | {metrics_days}d",
        f"ebs_metrics:              {len(ebs_met):>6} rows | {metrics_days}d",
        f"instance_pricing:         {len(pricing):>6} rows ({real_price_rows} real, {synth_price_rows} synth)",
        f"ai_recommendations:       {len(ai_recs):>6} rows",
    ]
    for line in lines:
        logger.info(line)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
