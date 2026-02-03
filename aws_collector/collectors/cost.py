"""
cost.py — AWS Cost Explorer collector.

Fetches daily, per-service, per-usage-type cost data and anomalies
month-by-month from the Cost Explorer API.

Note: This collector does not follow the standard list_resources/get_metrics
pattern as cost data is fundamentally different from resource metrics.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import get_date_range_for_cost, get_month_key
from ..transforms import transform_daily_costs, transform_service_costs

logger = logging.getLogger(__name__)


class CostCollector:
    """Collects cost data from AWS Cost Explorer.

    Unlike resource collectors, cost data doesn't map to individual
    resources with metrics. Instead, it provides aggregate cost
    breakdowns by day, service, and usage type.
    """

    SERVICE_NAME: str = "Cost Explorer"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize Cost Collector.

        Args:
            config: AWSConfig instance with Cost Explorer client.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        self.config = config
        self.conn = conn
        self.user_id = user_id
        self.ce = config.ce
        self.account_id = config.account_id

    def _paginated_query(self, params: dict) -> List[dict]:
        """Handle Cost Explorer pagination.

        Args:
            params: Query parameters for get_cost_and_usage.

        Returns:
            List of response dictionaries.
        """
        results: List[dict] = []
        next_token = None

        while True:
            effective_params = dict(params)
            if next_token:
                effective_params["NextPageToken"] = next_token

            try:
                response = self.ce.get_cost_and_usage(**effective_params)
                results.append(response)

                next_token = response.get("NextPageToken")
                if not next_token:
                    break
            except Exception as e:
                logger.error(f"[ERROR] Cost Explorer query failed: {e}")
                break

        return results

    def fetch_daily_cost(self, start_date: str, end_date: str) -> Dict:
        """Fetch daily cost data.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with daily cost data.
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
        }

        all_results: List[Dict] = []
        for response in self._paginated_query(params):
            all_results.extend(response.get("ResultsByTime", []))

        return {
            "account_id": self.account_id,
            "start_date": start_date,
            "end_date": end_date,
            "data": all_results,
        }

    def fetch_service_cost(self, start_date: str, end_date: str) -> Dict:
        """Fetch cost grouped by service.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with cost by service.
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        }

        all_results: List[Dict] = []
        for response in self._paginated_query(params):
            all_results.extend(response.get("ResultsByTime", []))

        return {
            "account_id": self.account_id,
            "start_date": start_date,
            "end_date": end_date,
            "data": all_results,
        }

    def fetch_usage_type_cost(self, start_date: str, end_date: str) -> Dict:
        """Fetch cost grouped by usage type.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with cost by usage type.
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        }

        all_results: List[Dict] = []
        for response in self._paginated_query(params):
            all_results.extend(response.get("ResultsByTime", []))

        return {
            "account_id": self.account_id,
            "start_date": start_date,
            "end_date": end_date,
            "data": all_results,
        }

    def fetch_anomalies(self, start_date: str, end_date: str) -> Dict:
        """Fetch cost anomalies.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with cost anomalies.
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        try:
            response = self.ce.get_anomalies(
                DateInterval={"StartDate": start, "EndDate": end}
            )

            return {
                "account_id": self.account_id,
                "start_date": start_date,
                "end_date": end_date,
                "data": response.get("Anomalies", []),
            }
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch anomalies: {e}")
            return {
                "account_id": self.account_id,
                "start_date": start_date,
                "end_date": end_date,
                "data": [],
                "error": str(e),
            }

    def collect_month(self, start_date: str, end_date: str) -> Dict:
        """Collect all cost data for a specific month.

        This is the main entry point for cost collection. It fetches
        daily costs, service costs, usage type costs, and anomalies
        for the specified date range.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dict with keys: daily_cost, service_cost, usage_type_cost, anomalies.
        """
        month_key = get_month_key(start_date)
        logger.info(f"  [{self.SERVICE_NAME}] Fetching cost data for {month_key}...")

        logger.info("    -> Daily cost...")
        daily_cost = self.fetch_daily_cost(start_date, end_date)
        logger.info("    done")

        logger.info("    -> Service cost...")
        service_cost = self.fetch_service_cost(start_date, end_date)
        logger.info("    done")

        logger.info("    -> Usage type cost...")
        usage_type_cost = self.fetch_usage_type_cost(start_date, end_date)
        logger.info("    done")

        logger.info("    -> Anomalies...")
        anomalies = self.fetch_anomalies(start_date, end_date)
        logger.info("    done")

        return {
            "daily_cost": daily_cost,
            "service_cost": service_cost,
            "usage_type_cost": usage_type_cost,
            "anomalies": anomalies,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Collect and store cost data for the specified date range.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of cost records inserted (daily + service).
        """
        cost_data = self.collect_month(start_date, end_date)

        # Transform and insert daily costs
        daily_rows = transform_daily_costs(cost_data["daily_cost"])
        if daily_rows:
            storage.insert_daily_costs(self.conn, self.user_id, daily_rows)

        # Transform and insert service costs
        service_rows = transform_service_costs(cost_data["service_cost"])
        if service_rows:
            storage.insert_service_costs(self.conn, self.user_id, service_rows)

        total_records = len(daily_rows) + len(service_rows)
        logger.info(
            f"  [{self.SERVICE_NAME}] Inserted {len(daily_rows)} daily, "
            f"{len(service_rows)} service cost records"
        )
        return total_records
