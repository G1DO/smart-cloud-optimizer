"""
ec2.py — EC2 and EBS collector following BaseCollector pattern.

Collects EC2 instances and EBS volumes inventory, plus CloudWatch
metrics for both resource types.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import (
    EC2_METRIC_MAP,
    EBS_METRIC_MAP,
    fetch_cw_metric,
    get_datetime_range,
)
from ..transforms import (
    flatten_cw_metrics,
    transform_ebs_volumes,
    transform_ec2_instances,
)
from .base import BaseCollector, PROGRESS_LOG_INTERVAL

logger = logging.getLogger(__name__)


class EC2Collector(BaseCollector):
    """Collector for EC2 instances and EBS volumes."""

    SERVICE_NAME: str = "EC2"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize EC2 Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all EC2 instances across all regions.

        Returns:
            List of instance dictionaries with inventory data.
        """
        all_instances = []
        failed_regions = []
        total_regions = len(self.regions)

        logger.info("\n[EC2] Collecting EC2 instances...")
        logger.info(f"  Total regions to scan: {total_regions}")
        start_time = datetime.now()

        for idx, region in enumerate(self.regions, 1):
            try:
                ec2 = self.config.get_ec2_client(region)
                region_start = datetime.now()
                logger.info(f"  [{idx}/{total_regions}] Scanning region {region}...")

                region_count = 0
                paginator = ec2.get_paginator("describe_instances")
                for page in paginator.paginate():
                    for reservation in page.get("Reservations", []):
                        for inst in reservation.get("Instances", []):
                            region_count += 1
                            instance_data = {
                                "account_id": self.account_id,
                                "region": region,
                                "instance_id": inst["InstanceId"],
                                "instance_type": inst.get("InstanceType", ""),
                                "state": inst.get("State", {}).get("Name", ""),
                                "availability_zone": inst.get("Placement", {}).get(
                                    "AvailabilityZone", ""
                                ),
                                "launch_time": (
                                    inst.get("LaunchTime").isoformat()
                                    if inst.get("LaunchTime")
                                    else None
                                ),
                                "private_ip": inst.get("PrivateIpAddress"),
                                "public_ip": inst.get("PublicIpAddress"),
                                "vpc_id": inst.get("VpcId"),
                                "subnet_id": inst.get("SubnetId"),
                                "ami_id": inst.get("ImageId"),
                                "architecture": inst.get("Architecture"),
                                "monitoring": inst.get("Monitoring", {}).get("State"),
                                "cpu_cores": inst.get("CpuOptions", {}).get("CoreCount"),
                                "threads_per_core": inst.get("CpuOptions", {}).get(
                                    "ThreadsPerCore"
                                ),
                                "tags": {
                                    tag["Key"]: tag["Value"]
                                    for tag in inst.get("Tags", [])
                                },
                            }
                            all_instances.append(instance_data)

                elapsed = (datetime.now() - region_start).total_seconds()
                logger.info(f"    Found {region_count} instances ({elapsed:.1f}s)")
            except Exception as e:
                logger.error(f"    ERROR: {e}")
                failed_regions.append(region)

        total_time = (datetime.now() - start_time).total_seconds()
        if failed_regions:
            logger.warning(f"  [EC2] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(
            f"\n[EC2] Completed: Found {len(all_instances)} instances in {total_time:.1f}s"
        )
        return all_instances

    def list_volumes(self) -> List[Dict]:
        """List all EBS volumes across all regions.

        Returns:
            List of volume dictionaries with inventory data.
        """
        all_volumes = []
        failed_regions = []
        total_regions = len(self.regions)

        logger.info("\n[EBS] Collecting EBS volumes...")
        logger.info(f"  Total regions to scan: {total_regions}")
        start_time = datetime.now()

        for idx, region in enumerate(self.regions, 1):
            try:
                ec2 = self.config.get_ec2_client(region)
                region_start = datetime.now()
                logger.info(f"  [{idx}/{total_regions}] Scanning region {region}...")

                region_count = 0
                paginator = ec2.get_paginator("describe_volumes")
                for page in paginator.paginate():
                    for vol in page.get("Volumes", []):
                        region_count += 1
                        volume_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "volume_id": vol["VolumeId"],
                            "size_gb": vol.get("Size"),
                            "volume_type": vol.get("VolumeType"),
                            "iops": vol.get("Iops"),
                            "throughput": vol.get("Throughput"),
                            "encrypted": vol.get("Encrypted"),
                            "state": vol.get("State"),
                            "availability_zone": vol.get("AvailabilityZone"),
                            "create_time": (
                                vol.get("CreateTime").isoformat()
                                if vol.get("CreateTime")
                                else None
                            ),
                            "snapshot_id": vol.get("SnapshotId"),
                            "attachments": [
                                {
                                    "instance_id": att.get("InstanceId"),
                                    "device": att.get("Device"),
                                    "state": att.get("State"),
                                }
                                for att in vol.get("Attachments", [])
                            ],
                            "tags": {
                                tag["Key"]: tag["Value"]
                                for tag in vol.get("Tags", [])
                            },
                        }
                        all_volumes.append(volume_data)

                elapsed = (datetime.now() - region_start).total_seconds()
                logger.info(f"    Found {region_count} volumes ({elapsed:.1f}s)")
            except Exception as e:
                logger.error(f"    ERROR: {e}")
                failed_regions.append(region)

        total_time = (datetime.now() - start_time).total_seconds()
        if failed_regions:
            logger.warning(f"  [EBS] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(
            f"\n[EBS] Completed: Found {len(all_volumes)} volumes in {total_time:.1f}s"
        )
        return all_volumes

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for an EC2 instance.

        Args:
            resource_id: The EC2 instance ID.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "InstanceId", "Value": resource_id}]

        metrics = {
            "CPUUtilization": self._fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "CPUUtilization",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average", "Maximum"],
            ),
            "NetworkIn": self._fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "NetworkIn",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "NetworkOut": self._fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "NetworkOut",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "DiskReadOps": self._fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskReadOps",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "DiskWriteOps": self._fetch_metric(
                cloudwatch,
                "AWS/EC2",
                "DiskWriteOps",
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
            "instance_id": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics,
        }

    def get_ebs_metrics(
        self,
        volume_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for an EBS volume.

        Args:
            volume_id: The EBS volume ID.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "VolumeId", "Value": volume_id}]

        metrics = {
            "VolumeReadOps": self._fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeReadOps",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "VolumeWriteOps": self._fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeWriteOps",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "VolumeReadBytes": self._fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeReadBytes",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "VolumeWriteBytes": self._fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeWriteBytes",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "VolumeIdleTime": self._fetch_metric(
                cloudwatch,
                "AWS/EBS",
                "VolumeIdleTime",
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
            "volume_id": volume_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics,
        }

    def _collect_instance_metrics(
        self,
        instances: List[Dict],
        start_date: str,
        end_date: str,
    ) -> int:
        """Collect CloudWatch metrics for all EC2 instances.

        Args:
            instances: List of instance dicts from list_resources().
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of instances successfully collected.
        """
        total = len(instances)
        running = sum(1 for i in instances if i.get("state") == "running")
        terminated = sum(1 for i in instances if i.get("state") == "terminated")

        logger.info(
            f"\n  [EC2] Processing {total} instances "
            f"(running: {running}, terminated: {terminated})..."
        )
        logger.info(
            "  Note: Historical metrics available for terminated instances via CloudWatch"
        )

        count = 0
        failed_instances = []
        for idx, instance in enumerate(instances, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    instance["instance_id"],
                    instance["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(metrics, "instance_id", EC2_METRIC_MAP)

                # Convert NetworkIn/Out from bytes to kbps
                for row in rows:
                    if "network_in_kbps" in row:
                        row["network_in_kbps"] = row["network_in_kbps"] / 1024
                    if "network_out_kbps" in row:
                        row["network_out_kbps"] = row["network_out_kbps"] / 1024

                if rows:
                    storage.insert_ec2_metrics(self.conn, self.user_id, rows)
                count += 1
            except Exception as e:
                logger.warning(f"\n    [WARN] Failed {instance['instance_id']}: {e}")
                failed_instances.append(instance["instance_id"])

        if failed_instances:
            logger.warning(f"  [EC2] Failed {len(failed_instances)} instances: {failed_instances[:5]}{'...' if len(failed_instances) > 5 else ''}")
        logger.info(f"\n  Collected EC2 metrics for {count}/{total} instances")
        return count

    def _collect_volume_metrics(
        self,
        volumes: List[Dict],
        start_date: str,
        end_date: str,
    ) -> int:
        """Collect CloudWatch metrics for attached EBS volumes.

        Args:
            volumes: List of volume dicts from list_volumes().
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of volumes successfully collected.
        """
        # Only collect metrics for attached volumes
        attached = [v for v in volumes if v.get("state") == "in-use"]
        total = len(attached)
        logger.info(f"\n  [EBS] Processing {total} attached volumes...")

        count = 0
        failed_volumes = []
        for idx, volume in enumerate(attached, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_ebs_metrics(
                    volume["volume_id"],
                    volume["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(metrics, "volume_id", EBS_METRIC_MAP)

                if rows:
                    storage.insert_ebs_metrics(self.conn, self.user_id, rows)
                count += 1
            except Exception as e:
                logger.warning(f"\n    [WARN] Failed {volume['volume_id']}: {e}")
                failed_volumes.append(volume["volume_id"])

        if failed_volumes:
            logger.warning(f"  [EBS] Failed {len(failed_volumes)} volumes: {failed_volumes[:5]}{'...' if len(failed_volumes) > 5 else ''}")
        logger.info(f"\n  Collected EBS metrics for {count}/{total} volumes")
        return count

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list resources, fetch metrics, store to DB.

        Handles both EC2 instances and EBS volumes in one call.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Total number of resources successfully collected (instances + volumes).
        """
        # Collect inventory
        instances = self.list_resources()
        volumes = self.list_volumes()

        # Transform and insert inventory
        ec2_rows = transform_ec2_instances(instances)
        if ec2_rows:
            storage.insert_ec2_instances(self.conn, self.user_id, ec2_rows)

        ebs_rows = transform_ebs_volumes(volumes)
        if ebs_rows:
            storage.insert_ebs_volumes(self.conn, self.user_id, ebs_rows)

        # Collect metrics
        instance_count = self._collect_instance_metrics(instances, start_date, end_date)
        volume_count = self._collect_volume_metrics(volumes, start_date, end_date)

        return instance_count + volume_count
