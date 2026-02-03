"""
nat_gateway.py — NAT Gateway collector following BaseCollector pattern.

Collects NAT Gateway inventory and CloudWatch metrics across all
enabled AWS regions.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import NAT_METRIC_MAP, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_nat_gateways
from .base import BaseCollector

logger = logging.getLogger(__name__)


class NATGatewayCollector(BaseCollector):
    """Collects NAT Gateway inventory and CloudWatch metrics."""

    SERVICE_NAME: str = "NAT Gateway"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize NAT Gateway Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all NAT Gateways across all regions.

        Returns:
            List of NAT Gateway dictionaries with inventory data.
        """
        all_nat_gateways: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                ec2 = self.config.get_ec2_client(region)
                paginator = ec2.get_paginator("describe_nat_gateways")

                for page in paginator.paginate():
                    for nat in page.get("NatGateways", []):
                        # Extract tags
                        tags = {
                            tag["Key"]: tag["Value"]
                            for tag in nat.get("Tags", [])
                        }

                        # Get first address if available
                        addresses = nat.get("NatGatewayAddresses", [])
                        first_addr = addresses[0] if addresses else {}

                        nat_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "nat_gateway_id": nat["NatGatewayId"],
                            "vpc_id": nat.get("VpcId", ""),
                            "subnet_id": nat.get("SubnetId", ""),
                            "state": nat.get("State", ""),
                            "connectivity_type": nat.get("ConnectivityType", "public"),
                            "allocation_id": first_addr.get("AllocationId", ""),
                            "private_ip": first_addr.get("PrivateIp", ""),
                            "public_ip": first_addr.get("PublicIp", ""),
                            "create_time": (
                                nat.get("CreateTime").isoformat()
                                if nat.get("CreateTime")
                                else None
                            ),
                            "tags": tags,
                        }
                        all_nat_gateways.append(nat_data)
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list NAT Gateways in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [NAT Gateway] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(
            f"  [{self.SERVICE_NAME}] Found {len(all_nat_gateways)} NAT Gateways"
        )
        return all_nat_gateways

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for a single NAT Gateway.

        Args:
            resource_id: The NAT Gateway ID.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with NAT Gateway metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "NatGatewayId", "Value": resource_id}]

        metrics_data = {
            "BytesInFromDestination": self._fetch_metric(
                cloudwatch,
                "AWS/NATGateway",
                "BytesInFromDestination",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "BytesOutToDestination": self._fetch_metric(
                cloudwatch,
                "AWS/NATGateway",
                "BytesOutToDestination",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "PacketsInFromDestination": self._fetch_metric(
                cloudwatch,
                "AWS/NATGateway",
                "PacketsInFromDestination",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "PacketsOutToDestination": self._fetch_metric(
                cloudwatch,
                "AWS/NATGateway",
                "PacketsOutToDestination",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "ActiveConnectionCount": self._fetch_metric(
                cloudwatch,
                "AWS/NATGateway",
                "ActiveConnectionCount",
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
            "nat_gateway_id": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list NAT Gateways, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of NAT Gateways successfully collected.
        """
        nat_gateways = self.list_resources()

        # Insert inventory
        if nat_gateways:
            rows = transform_nat_gateways(nat_gateways)
            storage.insert_nat_gateways(self.conn, self.user_id, rows)

        # Collect metrics
        total = len(nat_gateways)
        count = 0
        failed_gateways = []

        for idx, nat in enumerate(nat_gateways, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    nat["nat_gateway_id"],
                    nat["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(
                    metrics, "nat_gateway_id", NAT_METRIC_MAP
                )
                if rows:
                    storage.insert_nat_gateway_metrics(
                        self.conn, self.user_id, rows
                    )
                count += 1
            except Exception as e:
                logger.warning(
                    f"    [WARN] Failed {nat['nat_gateway_id']}: {e}"
                )
                failed_gateways.append(nat["nat_gateway_id"])

        if failed_gateways:
            logger.warning(f"  [NAT Gateway] Failed {len(failed_gateways)} gateways: {failed_gateways[:5]}{'...' if len(failed_gateways) > 5 else ''}")
        logger.info(
            f"  [{self.SERVICE_NAME}] Collected metrics for {count}/{total} gateways"
        )
        return count
