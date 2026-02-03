"""
lambda_.py — Lambda function collector.

Collects Lambda function inventory and CloudWatch metrics across all
enabled AWS regions.

Note: File named lambda_.py to avoid conflict with Python's lambda keyword.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import LAMBDA_METRIC_MAP, fetch_cw_metric, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_lambda_functions
from .base import BaseCollector

logger = logging.getLogger(__name__)


class LambdaCollector(BaseCollector):
    """Collects Lambda function inventory and CloudWatch metrics."""

    SERVICE_NAME: str = "Lambda"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize Lambda Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all Lambda functions across all regions.

        Returns:
            List of function dictionaries with inventory data.
        """
        all_functions: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                client = self.config.get_lambda_client(region)
                paginator = client.get_paginator("list_functions")

                for page in paginator.paginate():
                    for func in page.get("Functions", []):
                        func_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "function_name": func["FunctionName"],
                            "function_arn": func.get("FunctionArn", ""),
                            "runtime": func.get("Runtime", ""),
                            "memory_mb": func.get("MemorySize"),
                            "timeout_sec": func.get("Timeout", 30),
                            "code_size": func.get("CodeSize"),
                            "handler": func.get("Handler"),
                            "last_modified": func.get("LastModified"),
                            # Keep raw func for transform compatibility
                            "_raw": func,
                        }
                        all_functions.append(func_data)
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list Lambda functions in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [Lambda] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(f"  Found {len(all_functions)} Lambda functions")
        return all_functions

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for a Lambda function.

        Args:
            resource_id: Lambda function name.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with Lambda metrics.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "FunctionName", "Value": resource_id}]

        metrics_data = {
            "Invocations": self._fetch_metric(
                cloudwatch, "AWS/Lambda", "Invocations",
                dimensions, start_time, end_time,
                period=3600, statistics=["Sum"],
            ),
            "Duration": self._fetch_metric(
                cloudwatch, "AWS/Lambda", "Duration",
                dimensions, start_time, end_time,
                period=3600, statistics=["Average"],
            ),
            "Errors": self._fetch_metric(
                cloudwatch, "AWS/Lambda", "Errors",
                dimensions, start_time, end_time,
                period=3600, statistics=["Sum"],
            ),
        }

        return {
            "account_id": self.account_id,
            "region": region,
            "function_name": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list functions, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of functions successfully collected.
        """
        # Step 1: List all Lambda functions
        functions = self.list_resources()
        total = len(functions)

        if not functions:
            logger.info(f"[{self.SERVICE_NAME}] No functions found")
            return 0

        # Step 2: Insert function inventory
        # Transform raw function data for storage
        raw_funcs = [f["_raw"] for f in functions if "_raw" in f]
        if raw_funcs:
            func_rows = transform_lambda_functions(raw_funcs)
            storage.insert_lambda_functions(self.conn, self.user_id, func_rows)

        # Step 3: Fetch and insert metrics for each function
        logger.info(f"\n[{self.SERVICE_NAME}] Processing {total} functions...")
        count = 0
        failed_functions = []

        for idx, func in enumerate(functions, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    func["function_name"],
                    func["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(metrics, "function_name", LAMBDA_METRIC_MAP)

                # Lambda metrics use "date" column not "timestamp"
                for row in rows:
                    if "timestamp" in row:
                        row["date"] = row.pop("timestamp").split("T")[0]

                if rows:
                    storage.insert_lambda_metrics(self.conn, self.user_id, rows)

                count += 1
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed {func['function_name']}: {e}"
                )
                failed_functions.append(func["function_name"])

        if failed_functions:
            logger.warning(f"  [Lambda] Failed {len(failed_functions)} functions: {failed_functions[:5]}{'...' if len(failed_functions) > 5 else ''}")
        logger.info(
            f"\n[{self.SERVICE_NAME}] Collected metrics for {count}/{total} functions"
        )
        return count
