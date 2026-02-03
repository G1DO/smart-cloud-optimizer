"""
dynamodb.py — DynamoDB collector following BaseCollector pattern.

Collects DynamoDB table inventory and CloudWatch metrics across all
enabled AWS regions.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import DYNAMODB_METRIC_MAP, fetch_cw_metric, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_dynamodb_tables
from .base import BaseCollector

logger = logging.getLogger(__name__)


class DynamoDBCollector(BaseCollector):
    """Collects DynamoDB table data and metrics."""

    SERVICE_NAME: str = "DynamoDB"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize DynamoDB Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all DynamoDB tables across all regions.

        Returns:
            List of table dictionaries with inventory data.
        """
        all_tables: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                client = self.config.get_dynamodb_client(region)
                paginator = client.get_paginator("list_tables")

                table_names: List[str] = []
                for page in paginator.paginate():
                    table_names.extend(page.get("TableNames", []))

                for table_name in table_names:
                    try:
                        resp = client.describe_table(TableName=table_name)
                        table = resp["Table"]

                        # Determine capacity mode
                        billing = table.get("BillingModeSummary", {})
                        capacity_mode = billing.get(
                            "BillingMode", "PROVISIONED"
                        )
                        # Normalize to match CHECK constraint
                        if capacity_mode == "PAY_PER_REQUEST":
                            capacity_mode = "ON_DEMAND"

                        throughput = table.get(
                            "ProvisionedThroughput", {}
                        )

                        table_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "table_name": table_name,
                            "capacity_mode": capacity_mode,
                            "provisioned_rcu": throughput.get(
                                "ReadCapacityUnits"
                            ),
                            "provisioned_wcu": throughput.get(
                                "WriteCapacityUnits"
                            ),
                            "storage_gb": table.get("TableSizeBytes", 0)
                            / (1024**3),
                            "item_count": table.get("ItemCount", 0),
                        }
                        all_tables.append(table_data)
                    except Exception as e:
                        logger.warning(
                            f"    [WARN] Failed to describe table "
                            f"{table_name} in {region}: {e}"
                        )
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list DynamoDB tables in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [DynamoDB] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(f"  Found {len(all_tables)} DynamoDB tables")
        return all_tables

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get DynamoDB table metrics.

        Args:
            resource_id: DynamoDB table name.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with DynamoDB metrics.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "TableName", "Value": resource_id}]

        metrics_data = {
            "ConsumedReadCapacityUnits": self._fetch_metric(
                cloudwatch,
                "AWS/DynamoDB",
                "ConsumedReadCapacityUnits",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "ConsumedWriteCapacityUnits": self._fetch_metric(
                cloudwatch,
                "AWS/DynamoDB",
                "ConsumedWriteCapacityUnits",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "ProvisionedReadCapacityUnits": self._fetch_metric(
                cloudwatch,
                "AWS/DynamoDB",
                "ProvisionedReadCapacityUnits",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "ProvisionedWriteCapacityUnits": self._fetch_metric(
                cloudwatch,
                "AWS/DynamoDB",
                "ProvisionedWriteCapacityUnits",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "ThrottledRequests": self._fetch_metric(
                cloudwatch,
                "AWS/DynamoDB",
                "ThrottledRequests",
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
            "table_name": resource_id,
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
            Number of tables successfully collected.
        """
        # Step 1: List all tables
        tables = self.list_resources()

        # Step 2: Insert inventory
        if tables:
            rows = transform_dynamodb_tables(tables)
            storage.insert_dynamodb_tables(self.conn, self.user_id, rows)

        # Step 3: Fetch and insert metrics for each table
        total = len(tables)
        count = 0
        failed_tables = []

        for idx, table in enumerate(tables, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    table["table_name"],
                    table["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(
                    metrics, "table_name", DYNAMODB_METRIC_MAP
                )
                if rows:
                    storage.insert_dynamodb_metrics(
                        self.conn, self.user_id, rows
                    )
                count += 1
            except Exception as e:
                logger.warning(
                    f"    [WARN] Failed DynamoDB metrics for "
                    f"{table['table_name']}: {e}"
                )
                failed_tables.append(table["table_name"])

        if failed_tables:
            logger.warning(f"  [DynamoDB] Failed {len(failed_tables)} tables: {failed_tables[:5]}{'...' if len(failed_tables) > 5 else ''}")
        logger.info(
            f"  Collected {self.SERVICE_NAME} metrics for {count}/{total} tables"
        )
        return count
