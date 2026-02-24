"""
runner.py — Thin orchestrator for AWS data collection.

Coordinates all service collectors for month-by-month data collection.
Each collector handles its own inventory, metrics, and storage operations.
"""
import logging
import sqlite3
from datetime import datetime
from typing import Optional

import storage

from .config import AWSConfig, init_config
from .metrics import get_last_n_months, get_month_key
from .collectors import (
    CostCollector,
    DynamoDBCollector,
    EC2Collector,
    ECSCollector,
    ElastiCacheCollector,
    ELBCollector,
    LambdaCollector,
    NATGatewayCollector,
    PricingCollector,
    RDSCollector,
    S3Collector,
)

logger = logging.getLogger(__name__)


class CollectorRunner:
    """Main runner that orchestrates all data collection."""

    def __init__(
        self,
        config: Optional[AWSConfig] = None,
        conn: Optional[sqlite3.Connection] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Initialize Collector Runner.

        Args:
            config: AWSConfig instance. Creates default if None.
            conn: SQLite connection. Opens default DB if None.
            user_id: User ID for data isolation. Auto-created if None.
        """
        self.config = config or init_config()
        self.conn = conn or storage.get_connection()
        storage.ensure_schema(self.conn)
        self.user_id = user_id or storage.ensure_user(
            self.conn, self.config.account_id
        )

        # Initialize all collectors
        self.ec2 = EC2Collector(self.config, self.conn, self.user_id)
        self.rds = RDSCollector(self.config, self.conn, self.user_id)
        self.lambda_ = LambdaCollector(self.config, self.conn, self.user_id)
        self.s3 = S3Collector(self.config, self.conn, self.user_id)
        self.dynamodb = DynamoDBCollector(self.config, self.conn, self.user_id)
        self.elasticache = ElastiCacheCollector(self.config, self.conn, self.user_id)
        self.ecs = ECSCollector(self.config, self.conn, self.user_id)
        self.nat = NATGatewayCollector(self.config, self.conn, self.user_id)
        self.elb = ELBCollector(self.config, self.conn, self.user_id)
        self.cost = CostCollector(self.config, self.conn, self.user_id)
        self.pricing = PricingCollector(self.config, self.conn, self.user_id)

    @classmethod
    def from_connection(cls, connection: dict, user_id: str,
                        conn=None) -> "CollectorRunner":
        """Create a runner from an aws_connections row.

        Args:
            connection: Dict with ``iam_role_arn``, ``external_id``,
                ``aws_region``, ``aws_account_id``.
            user_id: The data-user_id (``"aws-{account_id}"``).
            conn: Optional SQLite connection.

        Returns:
            A configured :class:`CollectorRunner`.
        """
        aws_cfg = AWSConfig.from_role(
            role_arn=connection["iam_role_arn"],
            external_id=connection.get("external_id", ""),
            region=connection.get("aws_region", "us-east-1"),
        )
        return cls(config=aws_cfg, conn=conn, user_id=user_id)

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
        logger.info("=" * 60)

        # Clear previous data for this user
        storage.clear_user_data(self.conn, self.user_id)
        self.conn.commit()

        month_ranges = get_last_n_months(months)
        total_months = len(month_ranges)

        for month_idx, (start_date, end_date) in enumerate(month_ranges, 1):
            month_key = get_month_key(start_date)
            month_start = datetime.now()

            logger.info(f"\n{'=' * 60}")
            logger.info(f"Month {month_idx}/{total_months}: {month_key}")
            logger.info(f"{'=' * 60}")

            # Cost data
            logger.info(f"\n[{month_key}] Collecting costs...")
            self.cost.collect(start_date, end_date)

            # Service metrics (each collector handles its own inventory)
            logger.info(f"\n[{month_key}] Collecting EC2/EBS...")
            self.ec2.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting RDS...")
            self.rds.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting Lambda...")
            self.lambda_.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting S3...")
            self.s3.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting DynamoDB...")
            self.dynamodb.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting ElastiCache...")
            self.elasticache.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting ECS...")
            self.ecs.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting NAT Gateways...")
            self.nat.collect(start_date, end_date)

            logger.info(f"\n[{month_key}] Collecting Load Balancers...")
            self.elb.collect(start_date, end_date)

            # Pricing snapshot
            logger.info(f"\n[{month_key}] Collecting pricing...")
            self.pricing.collect(month_key)

            # Commit after each month
            self.conn.commit()

            month_time = (datetime.now() - month_start).total_seconds()
            logger.info(f"\n[{month_key}] Completed in {month_time:.1f}s")

            # Progress estimate
            remaining = total_months - month_idx
            if remaining > 0:
                elapsed = (datetime.now() - overall_start).total_seconds()
                avg = elapsed / month_idx
                est_remaining = avg * remaining / 60
                logger.info(f"  Progress: {month_idx}/{total_months} months")
                logger.info(f"  Estimated remaining: {est_remaining:.1f} min")

        overall_time = (datetime.now() - overall_start).total_seconds()
        logger.info("\n" + "=" * 60)
        logger.info("Collection Complete!")
        logger.info(f"Total time: {overall_time / 60:.1f} min")
        logger.info("=" * 60)


def main() -> None:
    """Main entry point."""
    runner = CollectorRunner()
    runner.run(months=12)


if __name__ == "__main__":
    main()
