"""Rule-based optimization checks for non-compute AWS services.

Each function checks one service pattern against inventory and metrics,
returning recommendation dicts ready for storage.insert_recommendations().

Part of the Smart Cloud Optimizer graduation project.
"""

import logging
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing constants (us-east-1)
# ---------------------------------------------------------------------------

EBS_PRICE_GP2 = 0.10       # $/GB/month
EBS_PRICE_GP3 = 0.08       # $/GB/month
EBS_PRICE_IO2_GB = 0.125   # $/GB/month
EBS_PRICE_IO2_IOPS = 0.065  # per provisioned IOPS/month

S3_PRICE_STANDARD = 0.023      # $/GB/month
S3_PRICE_IT_MONITORING = 0.0025  # per 1000 objects/month

DYNAMO_PRICE_RCU_MONTH = 0.09   # per provisioned RCU/month
DYNAMO_PRICE_WCU_MONTH = 0.47   # per provisioned WCU/month
DYNAMO_PRICE_READ_REQ_M = 1.25  # per million read request units (on-demand)
DYNAMO_PRICE_WRITE_REQ_M = 6.25  # per million write request units (on-demand)

NAT_PRICE_HOURLY = 0.045
NAT_PRICE_PER_GB = 0.045
NAT_HOURS_PER_MONTH = 730.0

ELB_ALB_HOURLY = 0.0225
ELB_HOURS_PER_MONTH = 720.0

HOURS_PER_MONTH = 730.0


# ---------------------------------------------------------------------------
# EC2 / RDS pricing plan switch
# ---------------------------------------------------------------------------

def check_ec2_pricing(
    conn: sqlite3.Connection,
    user_id: str,
    min_running_days: int = 60,
) -> list[dict]:
    """Recommend reserved instances for long-running on-demand EC2 instances.

    If an instance has been running on-demand with metrics spanning
    > min_running_days, and reserved pricing exists in the catalog,
    recommend reserved-1yr.

    Args:
        conn: Open database connection.
        user_id: User to check.
        min_running_days: Minimum days of metrics before recommending commitment.

    Returns:
        List of recommendation dicts.
    """
    instances = storage.get_ec2_instances(conn, user_id)
    if not instances:
        return []

    pricing = {
        p["instance_type"]: p
        for p in storage.get_instance_pricing(conn, service="EC2")
    }

    recs = []
    for inst in instances:
        if inst.get("pricing_model") != "on-demand":
            continue
        if inst.get("state") != "running":
            continue

        iid = inst["instance_id"]
        itype = inst["instance_type"]

        metrics = storage.get_ec2_metrics(conn, user_id, instance_id=iid)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            span_days = (df["timestamp"].max() - df["timestamp"].min()).days
        else:
            continue

        if span_days < min_running_days:
            continue

        p = pricing.get(itype, {})
        ri1_monthly = p.get("reserved_1yr_monthly")
        od_monthly = inst.get("monthly_cost") or p.get("on_demand_monthly") or 0

        if not ri1_monthly or ri1_monthly >= od_monthly:
            continue

        savings = round(od_monthly - ri1_monthly, 2)
        pct = round((savings / od_monthly) * 100, 1) if od_monthly > 0 else 0
        confidence = "high" if span_days > 180 else "medium"

        recs.append({
            "service": "EC2",
            "resource_id": iid,
            "recommendation_type": "pricing_plan_switch",
            "current_config": f"{itype}, on-demand",
            "recommended_config": f"{itype}, reserved-1yr",
            "current_monthly_cost": od_monthly,
            "estimated_monthly_cost": ri1_monthly,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": confidence,
            "reasoning": (
                f"Instance running on-demand for {span_days} days. "
                f"Reserved 1-year saves {pct}% (${savings:.2f}/mo)."
            ),
        })

    return recs


def check_rds_pricing(
    conn: sqlite3.Connection,
    user_id: str,
    min_running_days: int = 60,
) -> list[dict]:
    """Recommend reserved instances for long-running on-demand RDS instances.

    Same logic as check_ec2_pricing but for RDS.

    Args:
        conn: Open database connection.
        user_id: User to check.
        min_running_days: Minimum days of metrics before recommending commitment.

    Returns:
        List of recommendation dicts.
    """
    instances = storage.get_rds_instances(conn, user_id)
    if not instances:
        return []

    pricing = {
        p["instance_type"]: p
        for p in storage.get_instance_pricing(conn, service="RDS")
    }

    recs = []
    for inst in instances:
        if inst.get("pricing_model") != "on-demand":
            continue

        dbid = inst["db_instance_id"]
        db_class = inst.get("db_instance_class", "")

        metrics = storage.get_rds_metrics(conn, user_id, db_instance_id=dbid)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            span_days = (df["timestamp"].max() - df["timestamp"].min()).days
        else:
            continue

        if span_days < min_running_days:
            continue

        p = pricing.get(db_class, {})
        ri1_hourly = p.get("reserved_1yr_hourly")
        if ri1_hourly is None:
            continue

        ri1_monthly = round(ri1_hourly * HOURS_PER_MONTH, 2)
        if inst.get("multi_az"):
            ri1_monthly = round(ri1_monthly * 2, 2)

        od_monthly = inst.get("monthly_cost") or 0
        if ri1_monthly >= od_monthly:
            continue

        savings = round(od_monthly - ri1_monthly, 2)
        pct = round((savings / od_monthly) * 100, 1) if od_monthly > 0 else 0
        confidence = "high" if span_days > 180 else "medium"

        recs.append({
            "service": "RDS",
            "resource_id": dbid,
            "recommendation_type": "pricing_plan_switch",
            "current_config": f"{db_class}, on-demand",
            "recommended_config": f"{db_class}, reserved-1yr",
            "current_monthly_cost": od_monthly,
            "estimated_monthly_cost": ri1_monthly,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": confidence,
            "reasoning": (
                f"RDS instance running on-demand for {span_days} days. "
                f"Reserved 1-year saves {pct}% (${savings:.2f}/mo)."
            ),
        })

    return recs


# ---------------------------------------------------------------------------
# Lambda memory resize
# ---------------------------------------------------------------------------

def check_lambda_memory(
    conn: sqlite3.Connection,
    user_id: str,
    utilization_threshold: float = 50.0,
    min_data_days: int = 14,
) -> list[dict]:
    """Recommend reducing Lambda memory if avg usage is well below allocation.

    If avg(avg_memory_used_mb) / memory_allocated_mb < threshold over the
    observation period, recommend the next lower power-of-2 tier. A safety
    check ensures avg + 2*std stays below the reduced allocation.

    Args:
        conn: Open database connection.
        user_id: User to check.
        utilization_threshold: Percent threshold below which to recommend.
        min_data_days: Minimum days of metrics required.

    Returns:
        List of recommendation dicts.
    """
    LAMBDA_TIERS = [128, 256, 512, 1024, 2048, 3008]

    functions = storage.get_lambda_functions(conn, user_id)
    if not functions:
        return []

    recs = []
    for fn in functions:
        fname = fn["function_name"]
        allocated_mb = fn.get("memory_mb") or 128

        metrics = storage.get_lambda_metrics(conn, user_id, function_name=fname)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if len(df) < min_data_days:
            continue

        if "avg_memory_used_mb" not in df.columns:
            continue
        mem_used = df["avg_memory_used_mb"].dropna()
        if mem_used.empty:
            continue

        avg_used = float(mem_used.mean())
        std_used = float(mem_used.std()) if len(mem_used) > 1 else 0
        utilization = (avg_used / allocated_mb) * 100

        if utilization >= utilization_threshold:
            continue

        # Find next lower tier
        current_idx = None
        for i, tier in enumerate(LAMBDA_TIERS):
            if tier >= allocated_mb:
                current_idx = i
                break
        if current_idx is None or current_idx == 0:
            continue

        new_mb = LAMBDA_TIERS[current_idx - 1]

        # Safety: avg + 2*std must fit in new tier
        if avg_used + 2 * std_used > new_mb:
            continue

        # Estimate cost change (proportional to memory)
        current_cost = fn.get("monthly_cost") or 0
        if current_cost <= 0:
            continue
        ratio = new_mb / allocated_mb
        new_cost = round(current_cost * ratio, 2)
        savings = round(current_cost - new_cost, 2)
        pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0

        confidence = "high" if utilization < 40 else "medium"

        recs.append({
            "service": "Lambda",
            "resource_id": fname,
            "recommendation_type": "memory_resize",
            "current_config": f"{allocated_mb} MB",
            "recommended_config": f"{new_mb} MB",
            "current_monthly_cost": current_cost,
            "estimated_monthly_cost": new_cost,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": confidence,
            "reasoning": (
                f"Avg memory usage {avg_used:.0f} MB ({utilization:.0f}% of "
                f"{allocated_mb} MB). Safe to reduce to {new_mb} MB "
                f"(peak estimate {avg_used + 2 * std_used:.0f} MB)."
            ),
        })

    return recs


# ---------------------------------------------------------------------------
# EBS volume checks
# ---------------------------------------------------------------------------

def check_ebs_volumes(
    conn: sqlite3.Connection,
    user_id: str,
    idle_threshold_pct: float = 90.0,
    min_data_days: int = 7,
) -> list[dict]:
    """Check EBS volumes for type upgrades and delete candidates.

    Sub-rules:
        1. volume_type_upgrade: gp2 -> gp3 (gp3 is 20% cheaper per GB).
        2. delete_unused: Volumes in 'available' state (unattached).
        3. delete_unused: Volumes 'in-use' but idle > threshold of time.

    Args:
        conn: Open database connection.
        user_id: User to check.
        idle_threshold_pct: Percent of time idle to flag for deletion.
        min_data_days: Minimum days of metrics for idle check.

    Returns:
        List of recommendation dicts.
    """
    volumes = storage.get_ebs_volumes(conn, user_id)
    if not volumes:
        return []

    recs = []
    for vol in volumes:
        vid = vol["volume_id"]
        vtype = vol.get("volume_type", "")
        size = vol.get("size_gb") or 0
        current_cost = vol.get("monthly_cost") or 0

        # Rule 1: gp2 -> gp3
        if vtype == "gp2":
            new_cost = round(EBS_PRICE_GP3 * size, 2)
            savings = round(current_cost - new_cost, 2)
            if savings > 0:
                pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0
                recs.append({
                    "service": "EBS",
                    "resource_id": vid,
                    "recommendation_type": "volume_type_upgrade",
                    "current_config": f"gp2, {size} GB",
                    "recommended_config": f"gp3, {size} GB",
                    "current_monthly_cost": current_cost,
                    "estimated_monthly_cost": new_cost,
                    "monthly_savings": savings,
                    "savings_percent": pct,
                    "confidence": "high",
                    "reasoning": (
                        f"gp3 is 20% cheaper per GB than gp2 with same "
                        f"baseline performance (3000 IOPS, 125 MB/s)."
                    ),
                })

        # Rule 2: unattached volumes
        if vol.get("state") == "available":
            recs.append({
                "service": "EBS",
                "resource_id": vid,
                "recommendation_type": "delete_unused",
                "current_config": f"{vtype}, {size} GB, unattached",
                "recommended_config": "delete volume",
                "current_monthly_cost": current_cost,
                "estimated_monthly_cost": 0,
                "monthly_savings": current_cost,
                "savings_percent": 100.0,
                "confidence": "high",
                "reasoning": "Volume is unattached (state=available). No instance is using it.",
            })
            continue  # No need to check idle metrics for unattached

        # Rule 3: idle attached volumes
        metrics = storage.get_ebs_metrics(conn, user_id, volume_id=vid)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if len(df) < min_data_days * 24:  # hourly metrics
            continue

        if "idle_time_seconds" not in df.columns:
            continue

        avg_idle_pct = float(df["idle_time_seconds"].mean()) / 3600 * 100
        if avg_idle_pct > idle_threshold_pct:
            recs.append({
                "service": "EBS",
                "resource_id": vid,
                "recommendation_type": "delete_unused",
                "current_config": f"{vtype}, {size} GB, idle {avg_idle_pct:.0f}%",
                "recommended_config": "delete or snapshot volume",
                "current_monthly_cost": current_cost,
                "estimated_monthly_cost": 0,
                "monthly_savings": current_cost,
                "savings_percent": 100.0,
                "confidence": "medium",
                "reasoning": (
                    f"Volume idle {avg_idle_pct:.0f}% of the time "
                    f"(threshold: {idle_threshold_pct}%). Consider deleting "
                    f"or snapshotting for archival."
                ),
            })

    return recs


# ---------------------------------------------------------------------------
# S3 storage class switch
# ---------------------------------------------------------------------------

def check_s3_buckets(
    conn: sqlite3.Connection,
    user_id: str,
    access_threshold_daily: int = 100,
) -> list[dict]:
    """Recommend INTELLIGENT_TIERING for low-access STANDARD S3 buckets.

    If a STANDARD bucket has avg daily GET + PUT requests below the
    threshold, suggest switching to INTELLIGENT_TIERING which auto-tiers
    objects between frequent and infrequent access.

    Args:
        conn: Open database connection.
        user_id: User to check.
        access_threshold_daily: Max daily requests to qualify as "low access".

    Returns:
        List of recommendation dicts.
    """
    buckets = storage.get_s3_buckets(conn, user_id)
    if not buckets:
        return []

    recs = []
    for bucket in buckets:
        bname = bucket["bucket_name"]
        storage_class = bucket.get("storage_class", "STANDARD")
        size_gb = bucket.get("size_gb") or 0

        if storage_class != "STANDARD":
            continue
        if size_gb <= 0:
            continue

        gets = bucket.get("avg_daily_get_requests") or 0
        puts = bucket.get("avg_daily_put_requests") or 0
        total_daily = gets + puts

        if total_daily >= access_threshold_daily:
            continue

        current_cost = bucket.get("monthly_cost") or round(size_gb * S3_PRICE_STANDARD, 2)
        # IT frequent tier same price as STANDARD, but auto-tiers cold data
        # Monitoring fee: $0.0025 per 1000 objects
        num_objects = bucket.get("num_objects") or 0
        monitoring_cost = (num_objects / 1000) * S3_PRICE_IT_MONITORING
        # Estimate 30% of data moves to infrequent ($0.0125/GB)
        it_cost = round(
            size_gb * 0.7 * S3_PRICE_STANDARD +
            size_gb * 0.3 * 0.0125 +
            monitoring_cost,
            2
        )
        savings = round(current_cost - it_cost, 2)
        if savings <= 0:
            continue

        pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0

        recs.append({
            "service": "S3",
            "resource_id": bname,
            "recommendation_type": "storage_class_switch",
            "current_config": f"STANDARD, {size_gb:.0f} GB",
            "recommended_config": f"INTELLIGENT_TIERING, {size_gb:.0f} GB",
            "current_monthly_cost": current_cost,
            "estimated_monthly_cost": it_cost,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": "medium",
            "reasoning": (
                f"Bucket has {total_daily} avg daily requests (low access). "
                f"INTELLIGENT_TIERING auto-moves cold objects to cheaper tier."
            ),
        })

    return recs


# ---------------------------------------------------------------------------
# DynamoDB capacity mode switch
# ---------------------------------------------------------------------------

def check_dynamodb_tables(
    conn: sqlite3.Connection,
    user_id: str,
    low_utilization_threshold: float = 0.5,
    min_data_days: int = 14,
) -> list[dict]:
    """Recommend ON_DEMAND for PROVISIONED DynamoDB tables with low utilization.

    If avg consumed / provisioned < threshold for BOTH read and write,
    suggest switching to ON_DEMAND.

    Args:
        conn: Open database connection.
        user_id: User to check.
        low_utilization_threshold: Fraction below which to recommend switch.
        min_data_days: Minimum days of metrics required.

    Returns:
        List of recommendation dicts.
    """
    tables = storage.get_dynamodb_tables(conn, user_id)
    if not tables:
        return []

    recs = []
    for tbl in tables:
        tname = tbl["table_name"]
        mode = tbl.get("capacity_mode", "")
        prov_rcu = tbl.get("provisioned_rcu")
        prov_wcu = tbl.get("provisioned_wcu")

        if mode != "PROVISIONED" or not prov_rcu or not prov_wcu:
            continue

        metrics = storage.get_dynamodb_metrics(conn, user_id, table_name=tname)
        if not metrics:
            continue

        df = pd.DataFrame(metrics)
        if len(df) < min_data_days * 24:
            continue

        avg_rcu = float(df["consumed_read_units"].mean()) if "consumed_read_units" in df.columns else 0
        avg_wcu = float(df["consumed_write_units"].mean()) if "consumed_write_units" in df.columns else 0

        rcu_util = avg_rcu / prov_rcu if prov_rcu > 0 else 1
        wcu_util = avg_wcu / prov_wcu if prov_wcu > 0 else 1

        if rcu_util >= low_utilization_threshold or wcu_util >= low_utilization_threshold:
            continue

        current_cost = tbl.get("monthly_cost") or round(
            prov_rcu * DYNAMO_PRICE_RCU_MONTH + prov_wcu * DYNAMO_PRICE_WCU_MONTH, 2
        )
        # On-demand cost estimate from actual consumption
        monthly_hours = 30 * 24
        od_read_cost = (avg_rcu * monthly_hours / 1_000_000) * DYNAMO_PRICE_READ_REQ_M
        od_write_cost = (avg_wcu * monthly_hours / 1_000_000) * DYNAMO_PRICE_WRITE_REQ_M
        storage_cost = (tbl.get("storage_gb") or 0) * 0.25
        new_cost = round(od_read_cost + od_write_cost + storage_cost, 2)

        savings = round(current_cost - new_cost, 2)
        if savings <= 0:
            continue

        pct = round((savings / current_cost) * 100, 1) if current_cost > 0 else 0

        recs.append({
            "service": "DynamoDB",
            "resource_id": tname,
            "recommendation_type": "capacity_mode_switch",
            "current_config": f"PROVISIONED ({prov_rcu} RCU, {prov_wcu} WCU)",
            "recommended_config": "ON_DEMAND",
            "current_monthly_cost": current_cost,
            "estimated_monthly_cost": new_cost,
            "monthly_savings": savings,
            "savings_percent": pct,
            "confidence": "medium",
            "reasoning": (
                f"Avg utilization: RCU {rcu_util:.0%}, WCU {wcu_util:.0%}. "
                f"ON_DEMAND bills per-request, better for low/variable usage."
            ),
        })

    return recs


# ---------------------------------------------------------------------------
# NAT Gateway -> VPC endpoint
# ---------------------------------------------------------------------------

def check_nat_gateways(
    conn: sqlite3.Connection,
    user_id: str,
    monthly_cost_threshold: float = 30.0,
) -> list[dict]:
    """Recommend VPC endpoints for expensive NAT gateways.

    NAT gateways cost $0.045/hr + $0.045/GB processed. If monthly cost
    exceeds the threshold, suggest evaluating VPC gateway endpoints for
    S3/DynamoDB traffic (which are free).

    Args:
        conn: Open database connection.
        user_id: User to check.
        monthly_cost_threshold: Minimum monthly cost to trigger recommendation.

    Returns:
        List of recommendation dicts.
    """
    gateways = storage.get_nat_gateways(conn, user_id)
    if not gateways:
        return []

    recs = []
    for gw in gateways:
        gwid = gw["nat_gateway_id"]
        monthly_cost = gw.get("monthly_cost") or 0

        if monthly_cost < monthly_cost_threshold:
            continue

        data_gb = gw.get("monthly_data_processed_gb") or 0
        # Estimate potential savings: VPC gateway endpoints (S3/DynamoDB) are free
        # Assume ~30% of NAT traffic goes to AWS services
        potential_savings = round(data_gb * 0.3 * NAT_PRICE_PER_GB, 2)
        if potential_savings <= 0:
            potential_savings = round(monthly_cost * 0.1, 2)  # conservative 10%

        new_cost = round(monthly_cost - potential_savings, 2)
        pct = round((potential_savings / monthly_cost) * 100, 1) if monthly_cost > 0 else 0

        recs.append({
            "service": "VPC",
            "resource_id": gwid,
            "recommendation_type": "replace_with_endpoint",
            "current_config": f"NAT Gateway, {data_gb:.0f} GB/mo processed",
            "recommended_config": "Add VPC gateway endpoints for S3/DynamoDB",
            "current_monthly_cost": monthly_cost,
            "estimated_monthly_cost": new_cost,
            "monthly_savings": potential_savings,
            "savings_percent": pct,
            "confidence": "low",
            "reasoning": (
                f"NAT Gateway costs ${monthly_cost:.2f}/mo. VPC gateway "
                f"endpoints for S3/DynamoDB are free and could eliminate "
                f"~30% of NAT data charges."
            ),
        })

    return recs


# ---------------------------------------------------------------------------
# ELB idle check
# ---------------------------------------------------------------------------

def check_elb_idle(
    conn: sqlite3.Connection,
    user_id: str,
    min_daily_requests: int = 100,
    min_data_days: int = 7,
) -> list[dict]:
    """Recommend deleting idle load balancers.

    An ELB is idle if it has no targets AND low/no traffic in metrics.
    We check BOTH inventory (target_count) and metrics (request_count)
    to avoid false positives from stale inventory data.

    Args:
        conn: Open database connection.
        user_id: User to check.
        min_daily_requests: Daily request threshold below which ELB is idle.
        min_data_days: Minimum days of metrics for traffic check.

    Returns:
        List of recommendation dicts.
    """
    elbs = storage.get_elb_instances(conn, user_id)
    if not elbs:
        return []

    recs = []
    for elb in elbs:
        arn = elb["elb_arn"]
        target_count = elb.get("target_count") or 0
        monthly_cost = elb.get("monthly_cost") or round(ELB_ALB_HOURLY * ELB_HOURS_PER_MONTH, 2)

        # Check metrics for actual traffic
        metrics = storage.get_elb_metrics(conn, user_id, elb_arn=arn)
        has_traffic = False
        if metrics:
            df = pd.DataFrame(metrics)
            if len(df) >= min_data_days * 24:  # hourly metrics
                if "request_count" in df.columns:
                    # Sum hourly requests into daily average
                    total_requests = df["request_count"].sum()
                    total_hours = len(df)
                    avg_daily = (total_requests / total_hours) * 24
                    has_traffic = avg_daily >= min_daily_requests

        # Only recommend deletion if NO targets AND NO meaningful traffic
        if target_count == 0 and not has_traffic:
            confidence = "high"
            reasoning = "Load balancer has 0 registered targets and no significant traffic."
        elif target_count == 0:
            # Has traffic but no targets — weird but not idle
            continue
        else:
            continue

        recs.append({
            "service": "ELB",
            "resource_id": arn,
            "recommendation_type": "delete_idle",
            "current_config": f"{elb.get('elb_type', 'ALB')}, {target_count} targets",
            "recommended_config": "delete load balancer",
            "current_monthly_cost": monthly_cost,
            "estimated_monthly_cost": 0,
            "monthly_savings": monthly_cost,
            "savings_percent": 100.0,
            "confidence": confidence,
            "reasoning": reasoning,
        })

    return recs
