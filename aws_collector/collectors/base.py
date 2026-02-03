"""
base.py — Base collector class with shared functionality.

All service collectors inherit from BaseCollector to ensure
a consistent interface and shared utilities.
"""
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import storage

from ..config import AWSConfig
from ..metrics import fetch_cw_metric, get_datetime_range

logger = logging.getLogger(__name__)

# Log progress every N resources during metric collection.
PROGRESS_LOG_INTERVAL: int = 10


class BaseCollector(ABC):
    """Abstract base class for all service collectors."""

    # Subclasses should set this to their service name for logging.
    SERVICE_NAME: str = "Base"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize base collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        self.config = config
        self.conn = conn
        self.user_id = user_id
        self.account_id = config.account_id
        self.regions = config.regions

    @abstractmethod
    def list_resources(self) -> List[Dict]:
        """List all resources across all regions.

        Returns:
            List of resource dictionaries with inventory data.
        """
        pass

    @abstractmethod
    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get CloudWatch metrics for a single resource.

        Args:
            resource_id: The resource identifier.
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with metrics data.
        """
        pass

    @abstractmethod
    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list resources, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of resources successfully collected.
        """
        pass

    def _fetch_metric(
        self,
        cloudwatch_client,
        namespace: str,
        metric_name: str,
        dimensions: List[Dict],
        start_time: datetime,
        end_time: datetime,
        period: int = 3600,
        statistics: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Fetch CloudWatch metric using shared utility.

        Args:
            cloudwatch_client: Boto3 CloudWatch client.
            namespace: CloudWatch namespace (e.g., AWS/EC2).
            metric_name: Metric name.
            dimensions: Metric dimensions.
            start_time: Start datetime.
            end_time: End datetime.
            period: Period in seconds.
            statistics: Statistics to fetch.

        Returns:
            List of datapoints.
        """
        return fetch_cw_metric(
            cloudwatch_client,
            namespace,
            metric_name,
            dimensions,
            start_time,
            end_time,
            period,
            statistics,
        )

    def _log_progress(self, current: int, total: int) -> None:
        """Log collection progress at intervals.

        Args:
            current: Current item number (1-indexed).
            total: Total number of items.
        """
        if current % PROGRESS_LOG_INTERVAL == 0 or current == total:
            pct = current * 100 // total if total else 0
            logger.info(f"    [{self.SERVICE_NAME}] Progress: {current}/{total} ({pct}%)")
