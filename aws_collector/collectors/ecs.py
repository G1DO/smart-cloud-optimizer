"""
ecs.py — ECS/Fargate collector following BaseCollector pattern.

Collects ECS service inventory and CloudWatch metrics across all
enabled AWS regions.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import ECS_METRIC_MAP, fetch_cw_metric, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_ecs_services
from .base import BaseCollector

logger = logging.getLogger(__name__)


class ECSCollector(BaseCollector):
    """Collects ECS service data and metrics."""

    SERVICE_NAME: str = "ECS"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize ECS Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all ECS services across all regions and clusters.

        Returns:
            List of service dictionaries with inventory data.
        """
        all_services: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                client = self.config.get_ecs_client(region)

                # List all clusters
                cluster_arns: List[str] = []
                cluster_paginator = client.get_paginator("list_clusters")
                for page in cluster_paginator.paginate():
                    cluster_arns.extend(page.get("clusterArns", []))

                for cluster_arn in cluster_arns:
                    cluster_name = cluster_arn.rsplit("/", 1)[-1]

                    # List services in this cluster
                    service_arns: List[str] = []
                    svc_paginator = client.get_paginator("list_services")
                    for page in svc_paginator.paginate(cluster=cluster_arn):
                        service_arns.extend(page.get("serviceArns", []))

                    if not service_arns:
                        continue

                    # Describe services in batches of 10 (API limit)
                    for i in range(0, len(service_arns), 10):
                        batch = service_arns[i : i + 10]
                        resp = client.describe_services(
                            cluster=cluster_arn, services=batch
                        )
                        for svc in resp.get("services", []):
                            # Get CPU/memory from task definition
                            cpu = 256
                            memory_mb = 512
                            task_def_arn = svc.get("taskDefinition", "")
                            if task_def_arn:
                                try:
                                    td = client.describe_task_definition(
                                        taskDefinition=task_def_arn
                                    )["taskDefinition"]
                                    cpu = int(td.get("cpu", 256))
                                    memory_mb = int(td.get("memory", 512))
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to fetch task definition '{task_def_arn}' "
                                        f"in {region}: {e}. Using defaults: CPU={cpu}, Memory={memory_mb}MB"
                                    )

                            launch_type = svc.get("launchType", "FARGATE")
                            # Fargate capacity providers also count
                            if not launch_type or launch_type == "":
                                cap_providers = svc.get(
                                    "capacityProviderStrategy", []
                                )
                                if any(
                                    "FARGATE" in cp.get("capacityProvider", "")
                                    for cp in cap_providers
                                ):
                                    launch_type = "FARGATE"
                                else:
                                    launch_type = "EC2"

                            svc_data = {
                                "account_id": self.account_id,
                                "region": region,
                                "service_name": svc["serviceName"],
                                "cluster_name": cluster_name,
                                "launch_type": launch_type,
                                "desired_count": svc.get("desiredCount", 1),
                                "cpu": cpu,
                                "memory_mb": memory_mb,
                            }
                            all_services.append(svc_data)
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list ECS services in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [ECS] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(f"  Found {len(all_services)} ECS services")
        return all_services

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
        cluster_name: str = "",
    ) -> Dict:
        """Get ECS service metrics.

        Args:
            resource_id: ECS service name.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            cluster_name: ECS cluster name (required for ECS metrics).

        Returns:
            Dictionary with ECS metrics.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [
            {"Name": "ClusterName", "Value": cluster_name},
            {"Name": "ServiceName", "Value": resource_id},
        ]

        metrics_data = {
            "CPUUtilization": self._fetch_metric(
                cloudwatch,
                "AWS/ECS",
                "CPUUtilization",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "MemoryUtilization": self._fetch_metric(
                cloudwatch,
                "AWS/ECS",
                "MemoryUtilization",
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
            "service_name": resource_id,
            "cluster_name": cluster_name,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list resources, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of services successfully collected.
        """
        # Step 1: List all services
        services = self.list_resources()

        # Step 2: Insert inventory
        if services:
            rows = transform_ecs_services(services)
            storage.insert_ecs_services(self.conn, self.user_id, rows)

        # Step 3: Fetch and insert metrics for each service
        total = len(services)
        count = 0
        failed_services = []

        for idx, svc in enumerate(services, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    svc["service_name"],
                    svc["region"],
                    start_date,
                    end_date,
                    cluster_name=svc["cluster_name"],
                )
                rows = flatten_cw_metrics(
                    metrics, "service_name", ECS_METRIC_MAP
                )
                # ECS metrics need cluster_name in each row
                for row in rows:
                    row["cluster_name"] = svc["cluster_name"]
                if rows:
                    storage.insert_ecs_metrics(self.conn, self.user_id, rows)
                count += 1
            except Exception as e:
                logger.warning(
                    f"    [WARN] Failed ECS metrics for "
                    f"{svc['service_name']}: {e}"
                )
                failed_services.append(svc["service_name"])

        if failed_services:
            logger.warning(f"  [ECS] Failed {len(failed_services)} services: {failed_services[:5]}{'...' if len(failed_services) > 5 else ''}")
        logger.info(
            f"  Collected {self.SERVICE_NAME} metrics for {count}/{total} services"
        )
        return count
