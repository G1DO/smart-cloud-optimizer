"""
elb.py — ELB (ALB + NLB) collector following BaseCollector pattern.

Collects Application and Network Load Balancer inventory and
CloudWatch metrics across all enabled AWS regions.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import ALB_METRIC_MAP, NLB_METRIC_MAP, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_lb_inventory
from .base import BaseCollector

logger = logging.getLogger(__name__)


class ELBCollector(BaseCollector):
    """Collects ALB and NLB inventory and CloudWatch metrics."""

    SERVICE_NAME: str = "ELB"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize ELB Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all Load Balancers (ALB + NLB) across all regions.

        Returns:
            List of Load Balancer dictionaries with inventory data.
        """
        all_load_balancers: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                elbv2 = self.config.session.client("elbv2", region_name=region)
                paginator = elbv2.get_paginator("describe_load_balancers")

                for page in paginator.paginate():
                    for lb in page.get("LoadBalancers", []):
                        # Get security groups and subnets
                        security_groups = ",".join(lb.get("SecurityGroups", []))
                        subnets = ",".join(
                            az.get("SubnetId", "")
                            for az in lb.get("AvailabilityZones", [])
                        )

                        lb_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "lb_arn": lb["LoadBalancerArn"],
                            "lb_name": lb.get("LoadBalancerName", ""),
                            "type": lb.get("Type", ""),  # application or network
                            "scheme": lb.get("Scheme", ""),  # internet-facing or internal
                            "dns_name": lb.get("DNSName", ""),
                            "state": lb.get("State", {}).get("Code", ""),
                            "vpc_id": lb.get("VpcId", ""),
                            "security_groups": security_groups,
                            "subnets": subnets,
                            "canonical_hosted_zone_id": lb.get(
                                "CanonicalHostedZoneId", ""
                            ),
                            "created_time": (
                                lb.get("CreatedTime").isoformat()
                                if lb.get("CreatedTime")
                                else None
                            ),
                        }
                        all_load_balancers.append(lb_data)
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list Load Balancers in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [ELB] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(
            f"  [{self.SERVICE_NAME}] Found {len(all_load_balancers)} Load Balancers"
        )
        return all_load_balancers

    def _extract_lb_dimension(self, lb_arn: str) -> str:
        """Extract the LoadBalancer dimension value from an ARN.

        CloudWatch expects the portion after 'loadbalancer/' in the ARN.

        Args:
            lb_arn: Full Load Balancer ARN.

        Returns:
            Dimension value for CloudWatch metrics.
        """
        # ARN format: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
        # Dimension expects: app/name/id or net/name/id
        parts = lb_arn.split("loadbalancer/")
        return parts[1] if len(parts) > 1 else lb_arn

    def get_alb_metrics(
        self,
        lb_arn: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for an Application Load Balancer.

        Args:
            lb_arn: Load Balancer ARN.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with ALB metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        lb_dimension = self._extract_lb_dimension(lb_arn)
        dimensions = [{"Name": "LoadBalancer", "Value": lb_dimension}]

        metrics_data = {
            "RequestCount": self._fetch_metric(
                cloudwatch,
                "AWS/ApplicationELB",
                "RequestCount",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "HTTPCode_ELB_4XX_Count": self._fetch_metric(
                cloudwatch,
                "AWS/ApplicationELB",
                "HTTPCode_ELB_4XX_Count",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "HTTPCode_ELB_5XX_Count": self._fetch_metric(
                cloudwatch,
                "AWS/ApplicationELB",
                "HTTPCode_ELB_5XX_Count",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
        }

        return {
            "account_id": self.account_id,
            "region": region,
            "elb_arn": lb_arn,
            "lb_type": "ALB",
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def get_nlb_metrics(
        self,
        lb_arn: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for a Network Load Balancer.

        Args:
            lb_arn: Load Balancer ARN.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with NLB metrics data.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        lb_dimension = self._extract_lb_dimension(lb_arn)
        dimensions = [{"Name": "LoadBalancer", "Value": lb_dimension}]

        metrics_data = {
            "ProcessedBytes": self._fetch_metric(
                cloudwatch,
                "AWS/NetworkELB",
                "ProcessedBytes",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "NewFlowCount": self._fetch_metric(
                cloudwatch,
                "AWS/NetworkELB",
                "NewFlowCount",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
        }

        return {
            "account_id": self.account_id,
            "region": region,
            "elb_arn": lb_arn,
            "lb_type": "NLB",
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for a Load Balancer.

        This method dispatches to get_alb_metrics or get_nlb_metrics
        based on the ARN type. For explicit type control, use the
        specific methods directly.

        Args:
            resource_id: Load Balancer ARN.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with metrics data.
        """
        # Determine LB type from ARN
        # ARN contains /app/ for ALB, /net/ for NLB
        if "/app/" in resource_id:
            return self.get_alb_metrics(resource_id, region, start_date, end_date)
        elif "/net/" in resource_id:
            return self.get_nlb_metrics(resource_id, region, start_date, end_date)
        else:
            # Default to ALB metrics if type cannot be determined
            logger.warning(
                f"  [WARN] Unknown LB type for {resource_id}, defaulting to ALB"
            )
            return self.get_alb_metrics(resource_id, region, start_date, end_date)

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list Load Balancers, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of Load Balancers successfully collected.
        """
        load_balancers = self.list_resources()

        # Insert inventory
        if load_balancers:
            rows = transform_lb_inventory(load_balancers)
            storage.insert_elb_instances(self.conn, self.user_id, rows)

        # Collect metrics
        total = len(load_balancers)
        alb_count = 0
        nlb_count = 0
        failed_lbs = []

        for idx, lb in enumerate(load_balancers, 1):
            try:
                self._log_progress(idx, total)

                lb_type = lb.get("type", "")

                if lb_type == "application":
                    metrics = self.get_alb_metrics(
                        lb["lb_arn"],
                        lb["region"],
                        start_date,
                        end_date,
                    )
                    rows = flatten_cw_metrics(metrics, "elb_arn", ALB_METRIC_MAP)
                    # Ensure elb_arn is in each row
                    for row in rows:
                        if "elb_arn" not in row:
                            row["elb_arn"] = lb["lb_arn"]
                    if rows:
                        storage.insert_elb_metrics(self.conn, self.user_id, rows)
                    alb_count += 1

                elif lb_type == "network":
                    metrics = self.get_nlb_metrics(
                        lb["lb_arn"],
                        lb["region"],
                        start_date,
                        end_date,
                    )
                    rows = flatten_cw_metrics(metrics, "elb_arn", NLB_METRIC_MAP)
                    for row in rows:
                        if "elb_arn" not in row:
                            row["elb_arn"] = lb["lb_arn"]
                    if rows:
                        storage.insert_elb_metrics(self.conn, self.user_id, rows)
                    nlb_count += 1

            except Exception as e:
                logger.warning(f"    [WARN] Failed {lb['lb_arn']}: {e}")
                failed_lbs.append(lb["lb_name"])

        if failed_lbs:
            logger.warning(f"  [ELB] Failed {len(failed_lbs)} load balancers: {failed_lbs[:5]}{'...' if len(failed_lbs) > 5 else ''}")
        logger.info(
            f"  [{self.SERVICE_NAME}] Collected ALB metrics: {alb_count}, "
            f"NLB metrics: {nlb_count}"
        )
        return alb_count + nlb_count
