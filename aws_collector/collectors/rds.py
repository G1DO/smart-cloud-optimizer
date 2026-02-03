"""
rds.py — RDS collector following BaseCollector pattern.

Collects RDS instances inventory and CloudWatch metrics.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import (
    RDS_METRIC_MAP,
    fetch_cw_metric,
    get_datetime_range,
)
from ..transforms import flatten_cw_metrics, transform_rds_instances
from .base import BaseCollector, PROGRESS_LOG_INTERVAL

logger = logging.getLogger(__name__)


class RDSCollector(BaseCollector):
    """Collector for RDS instances."""

    SERVICE_NAME: str = "RDS"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize RDS Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all RDS instances across all regions.

        Returns:
            List of RDS instance dictionaries with inventory data.
        """
        all_instances = []
        failed_regions = []
        total_regions = len(self.regions)

        logger.info("\n[RDS] Collecting RDS instances...")
        logger.info(f"  Total regions to scan: {total_regions}")
        start_time = datetime.now()

        for idx, region in enumerate(self.regions, 1):
            try:
                rds_client = self.config.get_rds_client(region)
                region_start = datetime.now()
                logger.info(f"  [{idx}/{total_regions}] Scanning region {region}...")

                region_count = 0
                paginator = rds_client.get_paginator("describe_db_instances")
                for page in paginator.paginate():
                    for db in page.get("DBInstances", []):
                        region_count += 1
                        instance_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "db_instance_id": db["DBInstanceIdentifier"],
                            "db_instance_class": db.get("DBInstanceClass", ""),
                            "engine": db.get("Engine", ""),
                            "engine_version": db.get("EngineVersion"),
                            "allocated_storage": db.get("AllocatedStorage", 0),
                            "storage_type": db.get("StorageType", "gp3"),
                            "multi_az": db.get("MultiAZ", False),
                            "endpoint": db.get("Endpoint", {}).get("Address"),
                            "port": db.get("Endpoint", {}).get("Port"),
                            "backup_retention_period": db.get("BackupRetentionPeriod"),
                            "deletion_protection": db.get("DeletionProtection", False),
                            "status": db.get("DBInstanceStatus", ""),
                            "vpc_id": db.get("DBSubnetGroup", {}).get("VpcId"),
                            "availability_zone": db.get("AvailabilityZone"),
                            "create_time": (
                                db.get("InstanceCreateTime").isoformat()
                                if db.get("InstanceCreateTime")
                                else None
                            ),
                        }
                        all_instances.append(instance_data)

                elapsed = (datetime.now() - region_start).total_seconds()
                logger.info(f"    Found {region_count} instances ({elapsed:.1f}s)")
            except Exception as e:
                logger.error(f"    ERROR: {e}")
                failed_regions.append(region)

        total_time = (datetime.now() - start_time).total_seconds()
        if failed_regions:
            logger.warning(f"  [RDS] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(
            f"\n[RDS] Completed: Found {len(all_instances)} instances in {total_time:.1f}s"
        )
        return all_instances

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for an RDS instance.

        Args:
            resource_id: The RDS DB instance identifier.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "DBInstanceIdentifier", "Value": resource_id}]

        metrics = {
            "CPUUtilization": self._fetch_metric(
                cloudwatch,
                "AWS/RDS",
                "CPUUtilization",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "FreeStorageSpace": self._fetch_metric(
                cloudwatch,
                "AWS/RDS",
                "FreeStorageSpace",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "DatabaseConnections": self._fetch_metric(
                cloudwatch,
                "AWS/RDS",
                "DatabaseConnections",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "ReadIOPS": self._fetch_metric(
                cloudwatch,
                "AWS/RDS",
                "ReadIOPS",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "WriteIOPS": self._fetch_metric(
                cloudwatch,
                "AWS/RDS",
                "WriteIOPS",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
        }

        return {
            "account_id": self.account_id,
            "region": region,
            "db_instance_id": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list resources, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of RDS instances successfully collected.
        """
        # Collect inventory
        instances = self.list_resources()

        # Transform and insert inventory
        if instances:
            # transform_rds_instances expects raw API response format
            # Convert our list to that format for the transform
            raw_dbs = []
            for inst in instances:
                raw_db = {
                    "DBInstanceIdentifier": inst["db_instance_id"],
                    "DBInstanceClass": inst["db_instance_class"],
                    "Engine": inst["engine"],
                    "EngineVersion": inst.get("engine_version"),
                    "AllocatedStorage": inst.get("allocated_storage", 0),
                    "StorageType": inst.get("storage_type", "gp3"),
                    "MultiAZ": inst.get("multi_az", False),
                    "Endpoint": {
                        "Address": inst.get("endpoint"),
                        "Port": inst.get("port"),
                    },
                    "BackupRetentionPeriod": inst.get("backup_retention_period"),
                    "DeletionProtection": inst.get("deletion_protection", False),
                }
                raw_dbs.append(raw_db)

            rds_rows = transform_rds_instances(raw_dbs)
            storage.insert_rds_instances(self.conn, self.user_id, rds_rows)

        # Collect metrics
        total = len(instances)
        logger.info(f"\n  [RDS] Processing {total} instances for metrics...")

        count = 0
        failed_instances = []
        for idx, instance in enumerate(instances, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    instance["db_instance_id"],
                    instance["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(metrics, "db_instance_id", RDS_METRIC_MAP)

                # Convert FreeStorageSpace from bytes to GB
                for row in rows:
                    if "free_storage_gb" in row:
                        row["free_storage_gb"] = row["free_storage_gb"] / (1024**3)

                if rows:
                    storage.insert_rds_metrics(self.conn, self.user_id, rows)
                count += 1
            except Exception as e:
                logger.warning(
                    f"\n    [WARN] Failed {instance['db_instance_id']}: {e}"
                )
                failed_instances.append(instance["db_instance_id"])

        if failed_instances:
            logger.warning(f"  [RDS] Failed {len(failed_instances)} instances: {failed_instances[:5]}{'...' if len(failed_instances) > 5 else ''}")
        logger.info(f"\n  Collected RDS metrics for {count}/{total} instances")
        return count
