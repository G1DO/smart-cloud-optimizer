"""
collector_runner.py — Main orchestrator for month-by-month AWS data collection.

Coordinates inventory, cost, metrics, and pricing collection across all
AWS services for the last N months.

Part of the Smart Cloud Optimizer graduation project.
"""
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .collect_cloudfront import CloudFrontCollector
from .collect_load_balancers import LoadBalancerCollector
from .collect_nat_gateways import NATGatewayCollector
from .config import DATA_DIR, AWSConfig, init_config
from .cost_collector import CostCollector
from .cw_collector import CloudWatchCollector
from .date_utils import get_last_n_months, get_month_key
from .ec2_collector import EC2Collector
from .pricing_collector import PricingCollector

logger = logging.getLogger(__name__)

# Log progress every N resources during metric collection.
PROGRESS_LOG_INTERVAL: int = 10


def _count_metric_timestamps(metrics_data: Dict) -> int:
    """Count unique timestamps across all metric datapoints.

    Args:
        metrics_data: Mapping of metric name to list of datapoints.

    Returns:
        Number of unique timestamps.
    """
    timestamps: Set = set()
    for datapoints in metrics_data.values():
        for dp in datapoints:
            if "Timestamp" in dp:
                timestamps.add(dp["Timestamp"])
    return len(timestamps)


class CollectorRunner:
    """Main runner that orchestrates all data collection."""

    def __init__(self, config: Optional[AWSConfig] = None) -> None:
        """Initialize Collector Runner.

        Args:
            config: AWSConfig instance. Creates a default one if *None*.
        """
        self.config = config or init_config()

        self.cost_collector = CostCollector(self.config)
        self.cw_collector = CloudWatchCollector(self.config)
        self.pricing_collector = PricingCollector(self.config)
        self.ec2_collector = EC2Collector(self.config)
        self.cloudfront_collector = CloudFrontCollector(self.config)
        self.nat_collector = NATGatewayCollector(self.config)
        self.lb_collector = LoadBalancerCollector(self.config)

    # ------------------------------------------------------------------
    # Inventory helpers
    # ------------------------------------------------------------------

    def _load_previous_inventory(self) -> Optional[List[Dict]]:
        """Load instance inventory from a previous JSON collection.

        Returns:
            List of instance dicts, or *None* if unavailable.
        """
        inventory_file = DATA_DIR / "inventory" / "instances.json"
        if not inventory_file.exists():
            return None
        try:
            with open(inventory_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.info(f"  [INFO] Could not load previous inventory: {e}")
            return None

    def _load_csv_inventory(self, current_ids: Set[str]) -> List[Dict]:
        """Load additional instances from the legacy CSV inventory.

        Args:
            current_ids: Set of instance IDs already known.

        Returns:
            List of instance dicts found in CSV but not in *current_ids*.
        """
        csv_file = DATA_DIR / "inventory" / "ec2_instances.csv"
        if not csv_file.exists():
            return []

        added: List[Dict] = []
        try:
            with open(csv_file, "r") as f:
                for row in csv.DictReader(f):
                    iid = row.get("instance_id", "")
                    if iid and iid not in current_ids:
                        added.append({
                            "account_id": row.get("account_id", ""),
                            "region": row.get("region", ""),
                            "instance_id": iid,
                            "instance_type": row.get("instance_type", ""),
                            "state": row.get("state", "terminated"),
                        })
                        current_ids.add(iid)
        except Exception as e:
            logger.warning(f"  [WARN] Could not load old CSV inventory: {e}")

        return added

    def _build_full_instance_list(self) -> Tuple[List[Dict], List[Dict]]:
        """Merge current, previous-JSON, and legacy-CSV instance lists.

        Returns:
            Tuple of (all_instances, volumes).
        """
        instances = self.ec2_collector.list_instances()
        volumes = self.ec2_collector.list_volumes()

        current_ids = {inst["instance_id"] for inst in instances}

        # Merge previous JSON inventory
        previous = self._load_previous_inventory()
        if previous:
            added = 0
            for prev in previous:
                if prev["instance_id"] not in current_ids:
                    instances.append(prev)
                    current_ids.add(prev["instance_id"])
                    added += 1
            if added:
                logger.info(f"  [INFO] Added {added} instances from previous inventory for historical metrics")

        # Merge legacy CSV inventory
        csv_added = self._load_csv_inventory(current_ids)
        if csv_added:
            instances.extend(csv_added)
            logger.info(f"  [INFO] Added {len(csv_added)} instances from old CSV inventory for historical metrics")

        return instances, volumes

    # ------------------------------------------------------------------
    # Per-service metric collection
    # ------------------------------------------------------------------

    def _collect_ec2_metrics(
        self, instances: List[Dict], start_date: str, end_date: str
    ) -> int:
        """Collect CloudWatch metrics for all EC2 instances.

        Args:
            instances: Full instance list (running + terminated).
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of instances successfully collected.
        """
        total = len(instances)
        running = sum(1 for i in instances if i.get("state") == "running")
        terminated = sum(1 for i in instances if i.get("state") == "terminated")

        logger.info(f"\n  [EC2] Processing {total} instances (running: {running}, terminated: {terminated})...")
        logger.info("  Note: Historical metrics available for terminated instances via CloudWatch")

        count = 0
        for idx, instance in enumerate(instances, 1):
            try:
                if idx % PROGRESS_LOG_INTERVAL == 0 or idx == total:
                    pct = idx * 100 // total if total else 0
                    logger.info(f"    Progress: {idx}/{total} ({pct}%)")
                    sys.stdout.flush()

                metrics = self.cw_collector.get_ec2_metrics(
                    instance["instance_id"], instance["region"], start_date, end_date
                )
                self.cw_collector.save_csv(metrics, "ec2", instance["instance_id"])
                count += 1
            except Exception as e:
                logger.warning(f"\n    [WARN] Failed {instance['instance_id']}: {e}")

        logger.info(f"\n  ✓ Collected EC2 metrics for {count}/{total} instances")
        if terminated:
            logger.info(f"  ℹ️  {terminated} terminated instances - historical metrics collected from CloudWatch")
        return count

    def _collect_ebs_metrics(
        self, volumes: List[Dict], start_date: str, end_date: str
    ) -> int:
        """Collect CloudWatch metrics for attached EBS volumes.

        Args:
            volumes: Full volume list (will be filtered to in-use).
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of volumes successfully collected.
        """
        attached = [v for v in volumes if v.get("state") == "in-use"]
        total = len(attached)
        logger.info(f"\n  [EBS] Processing {total} attached volumes...")

        count = 0
        for idx, volume in enumerate(attached, 1):
            try:
                if idx % PROGRESS_LOG_INTERVAL == 0 or idx == total:
                    pct = idx * 100 // total if total else 0
                    logger.info(f"    Progress: {idx}/{total} ({pct}%)")
                    sys.stdout.flush()

                metrics = self.cw_collector.get_ebs_metrics(
                    volume["volume_id"], volume["region"], start_date, end_date
                )
                self.cw_collector.save_csv(metrics, "ebs", volume["volume_id"])
                count += 1
            except Exception as e:
                logger.warning(f"\n    [WARN] Failed {volume['volume_id']}: {e}")

        logger.info(f"\n  ✓ Collected EBS metrics for {count}/{total} volumes")
        return count

    def _collect_lambda_metrics(self, start_date: str, end_date: str) -> int:
        """Collect CloudWatch metrics for Lambda functions across all regions.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of functions successfully collected.
        """
        regions = self.config.regions
        logger.info(f"\n  [Lambda] Scanning {len(regions)} regions...")
        count = 0
        total = 0

        for region_idx, region in enumerate(regions, 1):
            try:
                logger.info(f"    [{region_idx}/{len(regions)}] Region {region}...")
                client = self.config.get_lambda_client(region)
                paginator = client.get_paginator("list_functions")

                funcs: List[Dict] = []
                for page in paginator.paginate():
                    funcs.extend(page.get("Functions", []))

                total += len(funcs)
                logger.info(f" Found {len(funcs)} functions")

                for func in funcs:
                    try:
                        metrics = self.cw_collector.get_lambda_metrics(
                            func["FunctionName"], region, start_date, end_date
                        )
                        self.cw_collector.save_csv(metrics, "lambda", func["FunctionName"])
                        count += 1
                    except Exception as e:
                        logger.warning(f"      [WARN] Failed {func['FunctionName']}: {e}")
            except Exception as e:
                logger.error(f" ✗ ERROR: {e}")

        logger.info(f"  ✓ Collected Lambda metrics for {count}/{total} functions")
        return count

    def _collect_rds_metrics(self, start_date: str, end_date: str) -> int:
        """Collect CloudWatch metrics for RDS instances across all regions.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of RDS instances successfully collected.
        """
        regions = self.config.regions
        logger.info(f"\n  [RDS] Scanning {len(regions)} regions...")
        count = 0
        total = 0

        for region_idx, region in enumerate(regions, 1):
            try:
                logger.info(f"    [{region_idx}/{len(regions)}] Region {region}...")
                rds_client = self.config.get_rds_client(region)
                paginator = rds_client.get_paginator("describe_db_instances")

                dbs: List[Dict] = []
                for page in paginator.paginate():
                    dbs.extend(page.get("DBInstances", []))

                total += len(dbs)
                logger.info(f" Found {len(dbs)} instances")

                for db in dbs:
                    try:
                        metrics = self.cw_collector.get_rds_metrics(
                            db["DBInstanceIdentifier"], region, start_date, end_date
                        )
                        self.cw_collector.save_csv(metrics, "rds", db["DBInstanceIdentifier"])
                        count += 1
                    except Exception as e:
                        logger.warning(f"      [WARN] Failed {db['DBInstanceIdentifier']}: {e}")
            except Exception as e:
                logger.error(f" ✗ ERROR: {e}")

        logger.info(f"  ✓ Collected RDS metrics for {count}/{total} instances")
        return count

    def _collect_s3_metrics(self, start_date: str, end_date: str) -> int:
        """Collect CloudWatch metrics for S3 buckets.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of buckets successfully collected.
        """
        logger.info("  Collecting S3 metrics...")
        count = 0
        try:
            buckets = self.config.s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                try:
                    metrics = self.cw_collector.get_s3_metrics(
                        bucket["Name"], start_date, end_date
                    )
                    self.cw_collector.save_csv(metrics, "s3", bucket["Name"])
                    count += 1
                except Exception as e:
                    logger.warning(f"    [WARN] Failed to collect S3 metrics for {bucket['Name']}: {e}")
        except Exception as e:
            logger.warning(f"    [WARN] Failed to list S3 buckets: {e}")

        logger.info(f"  ✓ Collected S3 metrics for {count} buckets")
        return count

    def _collect_cloudfront_metrics(
        self, start_date: str, end_date: str, month_key: str
    ) -> int:
        """Collect CloudWatch metrics for CloudFront distributions.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            month_key: Month key (YYYY-MM) for logging.

        Returns:
            Number of distributions successfully collected.
        """
        logger.info(f"\n  [CloudFront] Collecting metrics for {month_key}...")
        count = 0
        total_rows = 0
        try:
            distributions = self.cloudfront_collector.list_distributions()
            for dist in distributions:
                try:
                    metrics = self.cloudfront_collector.get_metrics(
                        dist["distribution_id"], start_date, end_date
                    )
                    total_rows += _count_metric_timestamps(metrics.get("metrics", {}))
                    self.cloudfront_collector.save_metrics_csv(metrics)
                    count += 1
                except Exception as e:
                    logger.warning(f"    [WARN] Failed to collect CloudFront metrics for {dist['distribution_id']}: {e}")
            logger.info(f"  ✓ Collected CloudFront metrics for {count} distributions ({total_rows} rows added)")
        except Exception as e:
            logger.warning(f"  [WARN] Failed to collect CloudFront metrics: {e}")
        return count

    def _collect_nat_metrics(
        self, start_date: str, end_date: str, month_key: str
    ) -> int:
        """Collect CloudWatch metrics for NAT Gateways.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            month_key: Month key (YYYY-MM) for logging.

        Returns:
            Number of NAT Gateways successfully collected.
        """
        logger.info(f"\n  [NAT Gateways] Collecting metrics for {month_key}...")
        count = 0
        total_rows = 0
        try:
            nat_gateways = self.nat_collector.list_nat_gateways()
            for nat in nat_gateways:
                try:
                    metrics = self.nat_collector.get_metrics(
                        nat["nat_gateway_id"], nat["region"], start_date, end_date
                    )
                    total_rows += _count_metric_timestamps(metrics.get("metrics", {}))
                    self.nat_collector.save_metrics_csv(metrics)
                    count += 1
                except Exception as e:
                    logger.warning(f"    [WARN] Failed to collect NAT Gateway metrics for {nat['nat_gateway_id']}: {e}")
            logger.info(f"  ✓ Collected NAT Gateway metrics for {count} gateways ({total_rows} rows added)")
        except Exception as e:
            logger.warning(f"  [WARN] Failed to collect NAT Gateway metrics: {e}")
        return count

    def _collect_lb_metrics(
        self, start_date: str, end_date: str, month_key: str
    ) -> None:
        """Collect CloudWatch metrics for ALB and NLB load balancers.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            month_key: Month key (YYYY-MM) for logging.
        """
        logger.info(f"\n  [Load Balancers] Collecting metrics for {month_key}...")
        alb_count = 0
        nlb_count = 0
        alb_rows = 0
        nlb_rows = 0

        try:
            load_balancers = self.lb_collector.list_load_balancers()
            for lb in load_balancers:
                try:
                    if lb["type"] == "application":
                        metrics = self.lb_collector.get_alb_metrics(
                            lb["lb_arn"], lb["region"], start_date, end_date
                        )
                        alb_rows += _count_metric_timestamps(metrics.get("metrics", {}))
                        self.lb_collector.save_alb_metrics_csv(metrics)
                        alb_count += 1
                    elif lb["type"] == "network":
                        metrics = self.lb_collector.get_nlb_metrics(
                            lb["lb_arn"], lb["region"], start_date, end_date
                        )
                        nlb_rows += _count_metric_timestamps(metrics.get("metrics", {}))
                        self.lb_collector.save_nlb_metrics_csv(metrics)
                        nlb_count += 1
                except Exception as e:
                    logger.warning(f"    [WARN] Failed to collect Load Balancer metrics for {lb['lb_arn']}: {e}")
            logger.info(f"  ✓ Collected ALB metrics for {alb_count} load balancers ({alb_rows} rows added)")
            logger.info(f"  ✓ Collected NLB metrics for {nlb_count} load balancers ({nlb_rows} rows added)")
        except Exception as e:
            logger.warning(f"  [WARN] Failed to collect Load Balancer metrics: {e}")

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def collect_metrics_for_month(
        self, start_date: str, end_date: str, month_key: str
    ) -> None:
        """Collect CloudWatch metrics for all services for a single month.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            month_key: Month key (YYYY-MM).
        """
        logger.info(f"\n[Metrics] Collecting metrics for {month_key}...")
        metrics_start = datetime.now()

        instances, volumes = self._build_full_instance_list()

        self._collect_ec2_metrics(instances, start_date, end_date)
        self._collect_ebs_metrics(volumes, start_date, end_date)
        self._collect_lambda_metrics(start_date, end_date)
        self._collect_rds_metrics(start_date, end_date)
        self._collect_s3_metrics(start_date, end_date)
        self._collect_cloudfront_metrics(start_date, end_date, month_key)
        self._collect_nat_metrics(start_date, end_date, month_key)
        self._collect_lb_metrics(start_date, end_date, month_key)

        elapsed = (datetime.now() - metrics_start).total_seconds()
        logger.info(f"\n[Metrics] ✓ Completed {month_key} in {elapsed:.1f}s")

    def run(self, months: int = 12) -> None:
        """Run complete data collection for the last N months.

        Args:
            months: Number of months to collect (default: 12).
        """
        overall_start = datetime.now()

        logger.info("=" * 60)
        logger.info("AWS Data Collector - Starting Collection")
        logger.info("=" * 60)
        logger.info(f"Account ID: {self.config.account_id}")
        logger.info(f"Regions: {len(self.config.regions)}")
        logger.info(f"Months to collect: {months}")
        logger.info(f"Start time: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        month_ranges = get_last_n_months(months)

        # Step 1: Collect inventory (once)
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: Collecting Inventory")
        logger.info("=" * 60)
        inventory_start = datetime.now()
        self.ec2_collector.save_inventory()
        inventory_time = (datetime.now() - inventory_start).total_seconds()
        logger.info(f"\n✓ Inventory collection completed in {inventory_time:.1f}s")

        # Step 2: Collect data for each month
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Collecting Monthly Data")
        logger.info("=" * 60)

        total_months = len(month_ranges)
        for month_idx, (start_date, end_date) in enumerate(month_ranges, 1):
            month_key = get_month_key(start_date)
            month_start = datetime.now()

            logger.info(f"\n{'=' * 60}")
            logger.info(f"Month {month_idx}/{total_months}: {month_key} ({start_date} to {end_date})")
            logger.info(f"{'=' * 60}")

            # Cost data
            logger.info(f"\n[{month_key}] Step 1/3: Collecting cost data...")
            cost_start = datetime.now()
            self.cost_collector.collect_month(start_date, end_date)
            cost_time = (datetime.now() - cost_start).total_seconds()
            logger.info(f"[{month_key}] ✓ Cost data collected in {cost_time:.1f}s")

            # Metrics
            logger.info(f"\n[{month_key}] Step 2/3: Collecting metrics...")
            self.collect_metrics_for_month(start_date, end_date, month_key)

            # Pricing
            logger.info(f"\n[{month_key}] Step 3/3: Collecting pricing snapshot...")
            pricing_start = datetime.now()
            self.pricing_collector.collect_month_snapshot(month_key, regions=self.config.regions)
            pricing_time = (datetime.now() - pricing_start).total_seconds()
            logger.info(f"[{month_key}] ✓ Pricing snapshot collected in {pricing_time:.1f}s")

            month_time = (datetime.now() - month_start).total_seconds()
            logger.info(f"\n[{month_key}] ✓ Month completed in {month_time:.1f}s")

            remaining = total_months - month_idx
            if remaining > 0:
                elapsed = (datetime.now() - overall_start).total_seconds()
                avg = elapsed / month_idx
                est_remaining = avg * remaining
                logger.info(f"  Progress: {month_idx}/{total_months} months ({month_idx * 100 // total_months}%)")
                logger.info(f"  Estimated time remaining: {est_remaining / 60:.1f} minutes")

        overall_time = (datetime.now() - overall_start).total_seconds()

        logger.info("\n" + "=" * 60)
        logger.info("✓ Collection Complete!")
        logger.info("=" * 60)
        logger.info(f"Total time: {overall_time / 60:.1f} minutes ({overall_time:.1f}s)")
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("\nData saved to:")
        logger.info("  - Cost data: data/cost/*_consolidated.csv")
        logger.info("  - Metrics: data/metrics/{service}/{service}_metrics_consolidated.csv")
        logger.info("  - Pricing: data/pricing/pricing_consolidated.csv")
        logger.info("  - Inventory: data/inventory/*.csv")
        logger.info("=" * 60)


def main() -> None:
    """Main entry point."""
    runner = CollectorRunner()
    runner.run(months=12)


if __name__ == "__main__":
    main()
