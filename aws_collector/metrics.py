"""
metrics.py — CloudWatch metric utilities and mappings.

Combines metric fetching helper with metric name → DB column mappings.
"""
import logging
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CloudWatch Metric Fetching
# =============================================================================

def fetch_cw_metric(
    cloudwatch_client,
    namespace: str,
    metric_name: str,
    dimensions: List[Dict],
    start_time: datetime,
    end_time: datetime,
    period: int = 3600,
    statistics: List[str] | None = None,
) -> List[Dict]:
    """Fetch metric statistics from CloudWatch.

    Args:
        cloudwatch_client: Boto3 CloudWatch client.
        namespace: CloudWatch metric namespace (e.g. ``AWS/EC2``).
        metric_name: Metric name (e.g. ``CPUUtilization``).
        dimensions: List of dimension dicts with ``Name`` and ``Value``.
        start_time: Start datetime for the query.
        end_time: End datetime for the query.
        period: Aggregation period in seconds.
        statistics: List of statistics to fetch (e.g. ``["Average"]``).

    Returns:
        List of datapoint dicts from CloudWatch.
    """
    if statistics is None:
        statistics = ["Average"]
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=statistics,
        )
        return response.get("Datapoints", [])
    except Exception as e:
        logger.warning(
            f"Failed to fetch {namespace}/{metric_name} for {dimensions}: {e}"
        )
        return []


# =============================================================================
# Date Utilities
# =============================================================================

def get_last_n_months(n: int = 5) -> List[Tuple[str, str]]:
    """Get the last N months as (start_date, end_date) tuples.

    Args:
        n: Number of months to get.

    Returns:
        List of tuples in chronological order (oldest first).
    """
    today = datetime.now()
    months = []

    for i in range(n):
        target_month = today.month - i
        target_year = today.year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        start_date, end_date = month_start_end(target_year, target_month)
        months.append((start_date, end_date))

    return list(reversed(months))


def month_start_end(year: int, month: int) -> Tuple[str, str]:
    """Get start and end dates for a specific month.

    Args:
        year: Year (e.g., 2024).
        month: Month (1-12).

    Returns:
        Tuple of (start_date, end_date) as YYYY-MM-DD strings.
    """
    start_date = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def get_month_key(start_date: str) -> str:
    """Extract month key from start date (YYYY-MM-DD -> YYYY-MM)."""
    return start_date[:7]


def get_date_range_for_cost(start_date: str, end_date: str) -> Tuple[str, str]:
    """Format dates for Cost Explorer API (end date is exclusive).

    Args:
        start_date: Start date string.
        end_date: End date string.

    Returns:
        Tuple of (start, end_exclusive) dates.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    end_exclusive = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    return start.strftime("%Y-%m-%d"), end_exclusive


def get_datetime_range(start_date: str, end_date: str) -> Tuple[datetime, datetime]:
    """Convert date strings to datetime objects for CloudWatch.

    Args:
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).

    Returns:
        Tuple of UTC datetime objects.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )
    return start, end


# =============================================================================
# Metric Name Mappings (CloudWatch -> DB columns)
# =============================================================================

EC2_METRIC_MAP: Dict[str, str] = {
    "CPUUtilization_average": "cpu_utilization",
    "CPUUtilization_maximum": "cpu_max",
    "NetworkIn_average": "network_in_kbps",
    "NetworkOut_average": "network_out_kbps",
    "DiskReadOps_average": "disk_read_ops",
    "DiskWriteOps_average": "disk_write_ops",
}

EBS_METRIC_MAP: Dict[str, str] = {
    "VolumeReadOps_average": "read_ops",
    "VolumeWriteOps_average": "write_ops",
    "VolumeReadBytes_average": "read_bytes",
    "VolumeWriteBytes_average": "write_bytes",
    "VolumeIdleTime_average": "idle_time_seconds",
}

LAMBDA_METRIC_MAP: Dict[str, str] = {
    "Invocations_sum": "invocations",
    "Duration_average": "avg_duration_ms",
    "Errors_sum": "errors",
}

RDS_METRIC_MAP: Dict[str, str] = {
    "CPUUtilization_average": "cpu_utilization",
    "FreeStorageSpace_average": "free_storage_gb",
    "DatabaseConnections_average": "connections",
    "ReadIOPS_average": "read_iops",
    "WriteIOPS_average": "write_iops",
}

S3_METRIC_MAP: Dict[str, str] = {
    "BucketSizeBytes_average": "bucket_size_bytes",
    "NumberOfObjects_average": "number_of_objects",
}

NAT_METRIC_MAP: Dict[str, str] = {
    "BytesInFromDestination_sum": "bytes_in",
    "BytesOutToDestination_sum": "bytes_out",
    "PacketsInFromDestination_sum": "packets_in",
    "PacketsOutToDestination_sum": "packets_out",
    "ActiveConnectionCount_average": "active_connections",
}

ALB_METRIC_MAP: Dict[str, str] = {
    "RequestCount_sum": "request_count",
    "HTTPCode_ELB_4XX_Count_sum": "http_4xx",
    "HTTPCode_ELB_5XX_Count_sum": "http_5xx",
}

NLB_METRIC_MAP: Dict[str, str] = {
    "ProcessedBytes_sum": "processed_bytes",
    "NewFlowCount_sum": "new_connections",
}

ELASTICACHE_METRIC_MAP: Dict[str, str] = {
    "CPUUtilization_average": "cpu_utilization",
    "DatabaseMemoryUsagePercentage_average": "memory_utilization",
    "CurrConnections_average": "curr_connections",
    "CacheHits_sum": "cache_hits",
    "CacheMisses_sum": "cache_misses",
    "Evictions_sum": "evictions",
}

ECS_METRIC_MAP: Dict[str, str] = {
    "CPUUtilization_average": "cpu_utilization",
    "MemoryUtilization_average": "memory_utilization",
}

DYNAMODB_METRIC_MAP: Dict[str, str] = {
    "ConsumedReadCapacityUnits_sum": "consumed_read_units",
    "ConsumedWriteCapacityUnits_sum": "consumed_write_units",
    "ProvisionedReadCapacityUnits_average": "provisioned_read_units",
    "ProvisionedWriteCapacityUnits_average": "provisioned_write_units",
    "ThrottledRequests_sum": "throttled_requests",
}
