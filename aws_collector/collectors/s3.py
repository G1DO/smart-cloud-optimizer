"""
s3.py — S3 bucket collector.

Collects S3 bucket inventory and CloudWatch metrics. S3 metrics are
global and fetched from us-east-1 CloudWatch region.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import S3_METRIC_MAP, fetch_cw_metric, get_datetime_range
from ..transforms import flatten_cw_metrics
from .base import BaseCollector

logger = logging.getLogger(__name__)

# S3 CloudWatch metrics are only available in us-east-1
S3_METRICS_REGION: str = "us-east-1"

# S3 metrics use daily period (one datapoint per day)
S3_METRIC_PERIOD: int = 86400


class S3Collector(BaseCollector):
    """Collects S3 bucket inventory and CloudWatch metrics."""

    SERVICE_NAME: str = "S3"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize S3 Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all S3 buckets.

        S3 buckets are global; no region loop needed.

        Returns:
            List of bucket dictionaries with inventory data.
        """
        all_buckets: List[Dict] = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        try:
            response = self.config.s3.list_buckets()
            buckets = response.get("Buckets", [])

            for bucket in buckets:
                bucket_data = {
                    "account_id": self.account_id,
                    "bucket_name": bucket["Name"],
                    "creation_date": (
                        bucket["CreationDate"].isoformat()
                        if bucket.get("CreationDate")
                        else None
                    ),
                }
                all_buckets.append(bucket_data)

        except Exception as e:
            logger.warning(f"  [WARN] Failed to list S3 buckets: {e}")

        logger.info(f"  Found {len(all_buckets)} S3 buckets")
        return all_buckets

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for an S3 bucket.

        S3 metrics are fetched from us-east-1 regardless of bucket region.

        Args:
            resource_id: S3 bucket name.
            region: AWS region (ignored; uses us-east-1).
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with S3 metrics.
        """
        # S3 metrics are always in us-east-1
        cloudwatch = self.config.get_cloudwatch_client(S3_METRICS_REGION)
        start_time, end_time = get_datetime_range(start_date, end_date)

        # S3 metrics require StorageType dimension
        dimensions_base = [{"Name": "BucketName", "Value": resource_id}]
        dimensions = dimensions_base + [
            {"Name": "StorageType", "Value": "StandardStorage"}
        ]

        metrics_data = {
            "BucketSizeBytes": self._fetch_metric(
                cloudwatch, "AWS/S3", "BucketSizeBytes",
                dimensions, start_time, end_time,
                period=S3_METRIC_PERIOD, statistics=["Average"],
            ),
            "NumberOfObjects": self._fetch_metric(
                cloudwatch, "AWS/S3", "NumberOfObjects",
                dimensions, start_time, end_time,
                period=S3_METRIC_PERIOD, statistics=["Average"],
            ),
        }

        return {
            "account_id": self.account_id,
            "bucket_name": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list buckets, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of buckets successfully collected.
        """
        # Step 1: List all S3 buckets
        buckets = self.list_resources()
        total = len(buckets)

        if not buckets:
            logger.info(f"[{self.SERVICE_NAME}] No buckets found")
            return 0

        # Step 2: Insert bucket inventory
        # S3 inventory is simple - just bucket_name dict
        bucket_rows = [{"bucket_name": b["bucket_name"]} for b in buckets]
        storage.insert_s3_buckets(self.conn, self.user_id, bucket_rows)

        # Step 3: Fetch and insert metrics for each bucket
        logger.info(f"\n[{self.SERVICE_NAME}] Processing {total} buckets...")
        count = 0
        failed_buckets = []

        for idx, bucket in enumerate(buckets, 1):
            try:
                self._log_progress(idx, total)

                # S3 metrics don't need region - always us-east-1
                metrics = self.get_metrics(
                    bucket["bucket_name"],
                    S3_METRICS_REGION,
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(metrics, "bucket_name", S3_METRIC_MAP)

                # S3 metrics use "date" column not "timestamp"
                for row in rows:
                    if "timestamp" in row:
                        row["date"] = row.pop("timestamp").split("T")[0]

                if rows:
                    storage.insert_s3_metrics(self.conn, self.user_id, rows)

                count += 1
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to collect S3 metrics for {bucket['bucket_name']}: {e}"
                )
                failed_buckets.append(bucket["bucket_name"])

        if failed_buckets:
            logger.warning(f"  [S3] Failed {len(failed_buckets)} buckets: {failed_buckets[:5]}{'...' if len(failed_buckets) > 5 else ''}")
        logger.info(
            f"\n[{self.SERVICE_NAME}] Collected metrics for {count}/{total} buckets"
        )
        return count
