"""
transforms.py — Data transformation helpers for AWS API responses.

Converts raw AWS API responses into DB-ready row dicts suitable for
the storage ``insert_*`` functions.

Part of the Smart Cloud Optimizer graduation project.
"""
import json
from typing import Any, Dict, List, Set, Tuple

from datetime import datetime

from storage import SERVICE_NAME_MAP


# Map LB API type values to DB elb_type values.
_ELB_TYPE_MAP: Dict[str, str] = {
    "application": "ALB",
    "network": "NLB",
    "classic": "CLB",
}


# ------------------------------------------------------------------
# CloudWatch metric flattening
# ------------------------------------------------------------------

def flatten_cw_metrics(data: Dict, resource_id_key: str,
                       metric_map: Dict[str, str]) -> List[Dict]:
    """Flatten CloudWatch response into DB-ready rows.

    Args:
        data: Dict returned by ``cw_collector.get_*_metrics()``.
            Must have ``metrics`` key mapping metric names to datapoints.
        resource_id_key: Name of the resource identifier field
            (e.g. ``instance_id``).
        metric_map: Mapping from CloudWatch
            ``{MetricName}_{statistic}`` to DB column name.

    Returns:
        One dict per timestamp with DB column names.
    """
    metrics_data = data.get("metrics", {})
    resource_id = data.get(resource_id_key, "")

    # Collect all timestamps across all metrics.
    all_timestamps: Set = set()
    for datapoints in metrics_data.values():
        for dp in datapoints:
            if "Timestamp" in dp:
                all_timestamps.add(dp["Timestamp"])

    rows: List[Dict] = []
    for ts in sorted(all_timestamps):
        ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        row: Dict[str, Any] = {
            "timestamp": ts_str,
            resource_id_key: resource_id,
        }

        # Fill metric values for this timestamp.
        for metric_name, datapoints in metrics_data.items():
            for dp in datapoints:
                if dp.get("Timestamp") == ts:
                    for stat in ("Average", "Maximum", "Sum", "Minimum"):
                        if stat in dp:
                            cw_key = f"{metric_name}_{stat.lower()}"
                            if cw_key in metric_map:
                                row[metric_map[cw_key]] = (
                                    float(dp[stat]) if dp[stat] is not None else 0.0
                                )
                    break

        rows.append(row)

    return rows


# ------------------------------------------------------------------
# Cost transforms
# ------------------------------------------------------------------

def transform_daily_costs(cost_data: Dict) -> List[Dict]:
    """Transform Cost Explorer daily cost response into DB rows.

    Args:
        cost_data: Return value of ``CostCollector.fetch_daily_cost()``.

    Returns:
        List of dicts with ``date``, ``total_cost``.
    """
    rows: List[Dict] = []
    for result in cost_data.get("data", []):
        date_str = result.get("TimePeriod", {}).get("Start", "")
        amount = result.get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
        rows.append({
            "date": date_str,
            "total_cost": float(amount) if amount else 0.0,
        })
    return rows


def transform_service_costs(cost_data: Dict) -> List[Dict]:
    """Transform Cost Explorer service cost response into DB rows.

    Args:
        cost_data: Return value of ``CostCollector.fetch_service_cost()``.

    Returns:
        List of dicts with ``date``, ``service``, ``daily_cost``.
    """
    rows: List[Dict] = []
    for result in cost_data.get("data", []):
        date_str = result.get("TimePeriod", {}).get("Start", "")
        for group in result.get("Groups", []):
            service_name = group.get("Keys", [""])[0]
            amount = group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
            short_name = SERVICE_NAME_MAP.get(service_name, service_name)
            rows.append({
                "date": date_str,
                "service": short_name,
                "daily_cost": float(amount) if amount else 0.0,
            })
    return rows


# ------------------------------------------------------------------
# Inventory transforms
# ------------------------------------------------------------------

def transform_ec2_instances(instances: List[Dict]) -> List[Dict]:
    """Transform EC2 API instance dicts into DB-ready rows.

    Args:
        instances: Return value of ``EC2Collector.list_instances()``.

    Returns:
        List of dicts matching ``insert_ec2_instances`` schema.
    """
    rows: List[Dict] = []
    for inst in instances:
        tags = inst.get("tags")
        if isinstance(tags, dict):
            tags = json.dumps(tags)
        rows.append({
            "instance_id": inst["instance_id"],
            "instance_type": inst.get("instance_type", ""),
            "state": inst.get("state", "running"),
            "launch_date": inst.get("launch_time", ""),
            "region": inst.get("region", "us-east-1"),
            "availability_zone": inst.get("availability_zone", ""),
            "private_ip": inst.get("private_ip"),
            "public_ip": inst.get("public_ip"),
            "vpc_id": inst.get("vpc_id"),
            "subnet_id": inst.get("subnet_id"),
            "ami_id": inst.get("ami_id"),
            "tags": tags,
        })
    return rows


def transform_ebs_volumes(volumes: List[Dict]) -> List[Dict]:
    """Transform EC2 API volume dicts into DB-ready rows.

    Args:
        volumes: Return value of ``EC2Collector.list_volumes()``.

    Returns:
        List of dicts matching ``insert_ebs_volumes`` schema.
    """
    rows: List[Dict] = []
    for vol in volumes:
        tags = vol.get("tags")
        if isinstance(tags, dict):
            tags = json.dumps(tags)
        rows.append({
            "volume_id": vol["volume_id"],
            "volume_type": vol.get("volume_type", "gp3"),
            "size_gb": vol.get("size_gb", 0),
            "iops": vol.get("iops"),
            "throughput_mbps": vol.get("throughput"),
            "encrypted": vol.get("encrypted"),
            "state": vol.get("state"),
            "availability_zone": vol.get("availability_zone"),
        })
    return rows


def transform_rds_instances(db_instances: List[Dict]) -> List[Dict]:
    """Transform RDS API describe_db_instances into DB-ready rows.

    Args:
        db_instances: Raw RDS ``DBInstances`` list.

    Returns:
        List of dicts matching ``insert_rds_instances`` schema.
    """
    rows: List[Dict] = []
    for db in db_instances:
        rows.append({
            "db_instance_id": db["DBInstanceIdentifier"],
            "db_instance_class": db.get("DBInstanceClass", ""),
            "engine": db.get("Engine", ""),
            "engine_version": db.get("EngineVersion"),
            "storage_gb": db.get("AllocatedStorage", 0),
            "storage_type": db.get("StorageType", "gp3"),
            "multi_az": int(db.get("MultiAZ", False)),
            "endpoint": db.get("Endpoint", {}).get("Address"),
            "port": db.get("Endpoint", {}).get("Port"),
            "backup_retention_period": db.get("BackupRetentionPeriod"),
            "deletion_protection": int(db.get("DeletionProtection", False)),
        })
    return rows


def transform_lambda_functions(functions: List[Dict]) -> List[Dict]:
    """Transform Lambda list_functions API into DB-ready rows.

    Args:
        functions: Raw Lambda ``Functions`` list.

    Returns:
        List of dicts matching ``insert_lambda_functions`` schema.
    """
    rows: List[Dict] = []
    for func in functions:
        rows.append({
            "function_name": func["FunctionName"],
            "runtime": func.get("Runtime", ""),
            "memory_mb": func.get("MemorySize"),
            "timeout_sec": func.get("Timeout", 30),
            "code_size": func.get("CodeSize"),
            "handler": func.get("Handler"),
            "last_modified": func.get("LastModified"),
        })
    return rows


def transform_nat_gateways(nat_gateways: List[Dict]) -> List[Dict]:
    """Transform NAT Gateway inventory dicts into DB-ready rows.

    Args:
        nat_gateways: Return value of ``NATGatewayCollector.list_nat_gateways()``.

    Returns:
        List of dicts matching ``insert_nat_gateways`` schema.
    """
    return nat_gateways  # Already matches DB schema


def transform_lb_inventory(load_balancers: List[Dict]) -> List[Dict]:
    """Transform ELBv2 inventory dicts into DB-ready rows.

    Args:
        load_balancers: Return value of ``LoadBalancerCollector.list_load_balancers()``.

    Returns:
        List of dicts matching ``insert_elb_instances`` schema.
    """
    rows: List[Dict] = []
    for lb in load_balancers:
        rows.append({
            "elb_arn": lb["lb_arn"],
            "elb_name": lb.get("lb_name", ""),
            "elb_type": _ELB_TYPE_MAP.get(lb.get("type", ""), lb.get("type", "")),
            "scheme": lb.get("scheme", "internet-facing"),
            "dns_name": lb.get("dns_name"),
            "vpc_id": lb.get("vpc_id"),
            "state": lb.get("state", "active"),
            "created_time": lb.get("created_time"),
        })
    return rows


def transform_elasticache_nodes(clusters: List[Dict]) -> List[Dict]:
    """Transform ElastiCache API cluster dicts into DB-ready rows.

    Args:
        clusters: Return value of ``ElastiCacheCollector.list_clusters()``.

    Returns:
        List of dicts matching ``insert_elasticache_nodes`` schema.
    """
    rows: List[Dict] = []
    for c in clusters:
        rows.append({
            "cache_cluster_id": c["cache_cluster_id"],
            "cache_node_type": c.get("cache_node_type", ""),
            "engine": c.get("engine", ""),
            "engine_version": c.get("engine_version"),
            "num_cache_nodes": c.get("num_cache_nodes", 1),
        })
    return rows


def transform_ecs_services(services: List[Dict]) -> List[Dict]:
    """Transform ECS API service dicts into DB-ready rows.

    Args:
        services: Return value of ``ECSCollector.list_services()``.

    Returns:
        List of dicts matching ``insert_ecs_services`` schema.
    """
    rows: List[Dict] = []
    for svc in services:
        rows.append({
            "service_name": svc["service_name"],
            "cluster_name": svc.get("cluster_name", ""),
            "launch_type": svc.get("launch_type", "FARGATE"),
            "desired_count": svc.get("desired_count", 1),
            "cpu": svc.get("cpu", 256),
            "memory_mb": svc.get("memory_mb", 512),
        })
    return rows


def transform_dynamodb_tables(tables: List[Dict]) -> List[Dict]:
    """Transform DynamoDB API table dicts into DB-ready rows.

    Args:
        tables: Return value of ``DynamoDBCollector.list_tables()``.

    Returns:
        List of dicts matching ``insert_dynamodb_tables`` schema.
    """
    rows: List[Dict] = []
    for t in tables:
        rows.append({
            "table_name": t["table_name"],
            "capacity_mode": t.get("capacity_mode", "PROVISIONED"),
            "provisioned_rcu": t.get("provisioned_rcu"),
            "provisioned_wcu": t.get("provisioned_wcu"),
            "storage_gb": t.get("storage_gb", 0),
            "item_count": t.get("item_count", 0),
        })
    return rows


def transform_pricing(raw_rows: List[Dict]) -> List[Dict]:
    """Pivot per-(instance_type, pricing_type) pricing rows into
    per-instance_type rows with on_demand_hourly, reserved_*, spot_*.

    Args:
        raw_rows: Return value of ``PricingCollector.collect_month_snapshot()``.

    Returns:
        List of dicts matching ``insert_instance_pricing`` schema.
    """
    # Group by (service, instance_type/instance_class)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in raw_rows:
        service = row.get("service", "")
        itype = row.get("instance_type") or row.get("instance_class", "")
        if not itype:
            continue
        key = (service, itype)
        if key not in grouped:
            grouped[key] = {
                "service": service,
                "instance_type": itype,
                "on_demand_hourly": 0.0,
                "on_demand_monthly": 0.0,
            }
        entry = grouped[key]
        pricing_type = row.get("pricing_type", "")
        hourly = row.get("hourly_price_usd", 0.0) or 0.0

        if pricing_type == "On-Demand":
            entry["on_demand_hourly"] = float(hourly)
            entry["on_demand_monthly"] = float(hourly) * 730
        elif pricing_type == "Reserved-1yr":
            price = row.get("price_usd", 0.0) or 0.0
            entry["reserved_1yr_hourly"] = float(price)
            entry["reserved_1yr_monthly"] = float(price) * 730
        elif pricing_type == "Reserved-3yr":
            price = row.get("price_usd", 0.0) or 0.0
            entry["reserved_3yr_hourly"] = float(price)
            entry["reserved_3yr_monthly"] = float(price) * 730
        elif pricing_type == "Spot":
            entry["spot_hourly"] = float(hourly)
            entry["spot_monthly"] = float(hourly) * 730

    return list(grouped.values())
