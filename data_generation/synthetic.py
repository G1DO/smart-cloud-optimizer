"""
Synthetic Data Generator for Smart Cloud Optimizer

Generates realistic AWS usage data matching the exact CSV schemas
produced by aws_collector/. The synthetic data simulates a mid-size
SaaS startup with monthly bill ~$1,500-$2,500.

Usage:
    python -m data_generation.synthetic --output-dir data/synthetic/ --days 365 --seed 42
"""

import argparse
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "SYNTHETIC-001"
REGION = "us-east-1"

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
    end_date = datetime(2025, 6, 30)
    start_date = end_date - timedelta(days=days - 1)
    dates = pd.date_range(start_date, end_date, freq="D")

    n = len(dates)
    day_idx = np.arange(n, dtype=float)

    # Base daily cost ~$65
    base = 65.0

    # Trend: +1.5% per month ≈ +0.05% per day
    trend = base * (1.0 + 0.0005 * day_idx)

    # Weekly seasonality: weekdays 30% higher than weekends on average
    dow = np.array([d.weekday() for d in dates])
    weekday_factor = np.where(dow < 5, 1.15, 0.70)

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
    cost = np.maximum(cost, 20.0)

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
    end_date = datetime(2025, 6, 30)
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
    rows = []
    base_ip = 10
    for i, inst in enumerate(EC2_FLEET):
        iid = _instance_id(inst["name"])
        vid = _volume_id(inst["name"])
        eid = _eni_id(inst["name"])
        launch = datetime(2025, 1, 10 + i, 8, 30, 0)

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
        })

    return pd.DataFrame(rows)


def generate_s3_buckets() -> pd.DataFrame:
    """
    Generate S3 bucket inventory matching data/inventory/s3_buckets.csv schema.

    Columns: account_id, bucket_name, region, creation_date, versioning,
             default_encryption, public_access_block
    """
    buckets = [
        {"name": "app-user-uploads",  "created": "2024-06-15T10:00:00+00:00", "versioning": "Enabled"},
        {"name": "app-logs",          "created": "2024-06-15T10:05:00+00:00", "versioning": "Suspended"},
        {"name": "app-backups",       "created": "2024-07-01T08:00:00+00:00", "versioning": "Enabled"},
        {"name": "app-static-assets", "created": "2024-06-15T10:10:00+00:00", "versioning": ""},
    ]

    rows = []
    block = "{'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True}"
    for b in buckets:
        rows.append({
            "account_id": ACCOUNT_ID,
            "bucket_name": b["name"],
            "region": REGION,
            "creation_date": b["created"],
            "versioning": b["versioning"],
            "default_encryption": "AES256",
            "public_access_block": block,
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
        {"name": "image-resizer",   "runtime": "python3.12", "memory": 512,  "timeout": 30,  "handler": "index.handler", "size": 5242880,  "desc": "Resize uploaded images"},
        {"name": "email-sender",    "runtime": "python3.12", "memory": 256,  "timeout": 15,  "handler": "index.handler", "size": 2097152,  "desc": "Send transactional emails"},
        {"name": "log-processor",   "runtime": "python3.12", "memory": 1024, "timeout": 300, "handler": "index.handler", "size": 10485760, "desc": "Process and aggregate logs"},
        {"name": "webhook-handler", "runtime": "nodejs20.x", "memory": 128,  "timeout": 10,  "handler": "index.handler", "size": 1048576,  "desc": "Handle incoming webhooks"},
    ]

    rows = []
    for fn in functions:
        arn = f"arn:aws:lambda:{REGION}:000000000000:function:{fn['name']}"
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
            "tags": f"Environment=production",
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
    end_date = datetime(2025, 6, 30)
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
    end_date = datetime(2025, 6, 30)
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


# ---------------------------------------------------------------------------
# Pricing generator
# ---------------------------------------------------------------------------

def generate_instance_pricing(real_pricing_path: Optional[Path] = None) -> Tuple[pd.DataFrame, int, int]:
    """
    Generate instance pricing matching data/real/pricing/pricing_consolidated.csv schema.

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
# Cost preview plot
# ---------------------------------------------------------------------------

def _plot_cost_preview(daily_df: pd.DataFrame, service_df: pd.DataFrame,
                       output_path: Path) -> None:
    """Generate a cost preview PNG showing daily total and per-service breakdown."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    dates = pd.to_datetime(daily_df["date"])
    costs = daily_df["cost_amount"].values

    # Top: total daily cost
    ax = axes[0]
    ax.plot(dates, costs, linewidth=0.8, color="#2563eb", alpha=0.9)
    ax.fill_between(dates, 0, costs, alpha=0.15, color="#2563eb")

    # Mark anomalies (>2x median)
    median_cost = np.median(costs)
    anomaly_mask = costs > 2.0 * median_cost
    if anomaly_mask.any():
        ax.scatter(dates[anomaly_mask], costs[anomaly_mask],
                   color="red", s=40, zorder=5, label="Anomaly")
        ax.legend()

    ax.set_ylabel("Total Daily Cost (USD)")
    ax.set_title("Synthetic Daily Cost — Total")
    ax.grid(True, alpha=0.3)

    # Bottom: stacked per-service
    ax2 = axes[1]
    pivot = service_df.pivot_table(index="date", columns="service_name",
                                    values="cost_amount", aggfunc="sum").fillna(0)
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index()

    colors = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#8b5cf6", "#64748b"]
    pivot.plot.area(ax=ax2, stacked=True, alpha=0.7, linewidth=0.5, color=colors[:len(pivot.columns)])
    ax2.set_ylabel("Cost (USD)")
    ax2.set_title("Synthetic Daily Cost — By Service")
    ax2.legend(loc="upper left", fontsize=7, ncol=2)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate all synthetic datasets and save to output directory."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic AWS data for Smart Cloud Optimizer"
    )
    parser.add_argument("--output-dir", type=str, default="data/synthetic/",
                        help="Output directory (default: data/synthetic/)")
    parser.add_argument("--days", type=int, default=365,
                        help="Days of cost data (default: 365)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--real-pricing", type=str, default=None,
                        help="Path to real pricing CSV to merge (default: auto-detect)")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Auto-detect real pricing path
    real_pricing = None
    if args.real_pricing:
        real_pricing = Path(args.real_pricing)
    else:
        # Try standard location
        candidates = [
            Path("data/real/pricing/pricing_consolidated.csv"),
            Path("data/pricing/pricing_consolidated.csv"),
        ]
        for c in candidates:
            if c.exists():
                real_pricing = c
                break

    logger.info(f"Generating synthetic data (days={args.days}, seed={args.seed})...")
    logger.info(f"Output: {out.resolve()}")
    if real_pricing:
        logger.info(f"Real pricing: {real_pricing}")


    # -- Generate all datasets --
    daily = generate_daily_costs(days=args.days, seed=args.seed)
    daily.to_csv(out / "daily_costs.csv", index=False)

    service = generate_service_costs(days=args.days, seed=args.seed)
    service.to_csv(out / "service_costs.csv", index=False)

    ec2_inv = generate_ec2_instances()
    ec2_inv.to_csv(out / "ec2_instances.csv", index=False)

    rds_inv = generate_rds_instances()
    rds_inv.to_csv(out / "rds_instances.csv", index=False)

    s3 = generate_s3_buckets()
    s3.to_csv(out / "s3_buckets.csv", index=False)

    lam = generate_lambda_functions()
    lam.to_csv(out / "lambda_functions.csv", index=False)

    ebs = generate_ebs_volumes()
    ebs.to_csv(out / "ebs_volumes.csv", index=False)

    ec2_metrics_days = min(args.days, 90)
    ec2_met = generate_ec2_metrics(days=ec2_metrics_days, seed=args.seed)
    ec2_met.to_csv(out / "ec2_metrics.csv", index=False)

    rds_metrics_days = min(args.days, 45)
    rds_met = generate_rds_metrics(days=rds_metrics_days, seed=args.seed)
    rds_met.to_csv(out / "rds_metrics.csv", index=False)

    pricing, real_price_rows, synth_price_rows = generate_instance_pricing(real_pricing)
    pricing.to_csv(out / "instance_pricing.csv", index=False)

    ai_recs = generate_ai_recommendations_sample()
    ai_recs.to_csv(out / "ai_recommendations_sample.csv", index=False)

    # -- Cost preview plot --
    _plot_cost_preview(daily, service, out / "cost_preview.png")

    # -- Summary --
    logger.info("=== Synthetic Data Summary ===")

    dates_dt = pd.to_datetime(daily["date"])
    weekday_mask = dates_dt.dt.weekday < 5
    wd_avg = daily.loc[weekday_mask, "cost_amount"].mean()
    we_avg = daily.loc[~weekday_mask, "cost_amount"].mean()
    anomaly_count = (daily["cost_amount"] > 2.0 * daily["cost_amount"].median()).sum()

    # Trend: compare first 14 days avg vs last 14 days avg
    first_14 = daily["cost_amount"].iloc[:14].mean()
    last_14 = daily["cost_amount"].iloc[-14:].mean()
    trend_pct = ((last_14 - first_14) / first_14) * 100

    lines = [
        f"daily_costs.csv:              {len(daily):>6} rows | {daily['date'].iloc[0]} to {daily['date'].iloc[-1]}",
        f"  Total cost range: ${daily['cost_amount'].min():.2f} - ${daily['cost_amount'].max():.2f} (mean: ${daily['cost_amount'].mean():.2f})",
        f"  Weekday avg: ${wd_avg:.2f} | Weekend avg: ${we_avg:.2f} (ratio: {wd_avg/we_avg:.2f}x)",
        f"  Anomalies detected: {anomaly_count} dates",
        f"  Trend: {trend_pct:+.1f}% over period",
        f"service_costs.csv:            {len(service):>6} rows | {service['service_name'].nunique()} services x {args.days} days",
        f"ec2_instances.csv:            {len(ec2_inv):>6} rows",
        f"ec2_metrics.csv:              {len(ec2_met):>6} rows | {len(EC2_FLEET)} instances x 24h x {ec2_metrics_days}d",
        f"rds_instances.csv:            {len(rds_inv):>6} rows",
        f"rds_metrics.csv:              {len(rds_met):>6} rows | 2 instances x 24h x {rds_metrics_days}d",
        f"s3_buckets.csv:               {len(s3):>6} rows",
        f"lambda_functions.csv:         {len(lam):>6} rows",
        f"ebs_volumes.csv:              {len(ebs):>6} rows",
        f"instance_pricing.csv:         {len(pricing):>6} rows ({real_price_rows} from real data, {synth_price_rows} synthetic)",
        f"ai_recommendations_sample.csv:{len(ai_recs):>6} rows",
        f"cost_preview.png:             saved ✓",
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
