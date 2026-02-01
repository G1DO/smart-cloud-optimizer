"""
cost_collector.py — AWS Cost Explorer data collector.

Fetches daily, per-service, per-usage-type cost data and anomalies
month-by-month from the Cost Explorer API.

Part of the Smart Cloud Optimizer graduation project.
"""
import csv
import logging
from datetime import datetime
from typing import Dict, List, Optional

from .config import AWSConfig, DATA_DIR
from .date_utils import get_date_range_for_cost, get_month_key

logger = logging.getLogger(__name__)


class CostCollector:
    """Collects cost data from AWS Cost Explorer"""

    def __init__(self, config: AWSConfig):
        """
        Initialize Cost Collector

        Args:
            config: AWSConfig instance with Cost Explorer client
        """
        self.config = config
        self.ce = config.ce
        self.account_id = config.account_id

    def _paginated_query(self, params: dict) -> List[dict]:
        """Handle Cost Explorer pagination"""
        results = []
        next_token = None

        while True:
            effective_params = dict(params)
            if next_token:
                effective_params['NextPageToken'] = next_token

            try:
                response = self.ce.get_cost_and_usage(**effective_params)
                results.append(response)

                next_token = response.get('NextPageToken')
                if not next_token:
                    break
            except Exception as e:
                logger.error(f"[ERROR] Cost Explorer query failed: {e}")
                break

        return results

    def fetch_daily_cost(self, start_date: str, end_date: str) -> Dict:
        """
        Fetch daily cost data

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with daily cost data
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            'TimePeriod': {'Start': start, 'End': end},
            'Granularity': 'DAILY',
            'Metrics': ['UnblendedCost'],
        }

        all_results = []
        for response in self._paginated_query(params):
            all_results.extend(response.get('ResultsByTime', []))

        return {
            'account_id': self.account_id,
            'start_date': start_date,
            'end_date': end_date,
            'data': all_results
        }

    def fetch_service_cost(self, start_date: str, end_date: str) -> Dict:
        """
        Fetch cost grouped by service

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with cost by service
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            'TimePeriod': {'Start': start, 'End': end},
            'Granularity': 'DAILY',
            'Metrics': ['UnblendedCost'],
            'GroupBy': [{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
        }

        all_results = []
        for response in self._paginated_query(params):
            all_results.extend(response.get('ResultsByTime', []))

        return {
            'account_id': self.account_id,
            'start_date': start_date,
            'end_date': end_date,
            'data': all_results
        }

    def fetch_usage_type_cost(self, start_date: str, end_date: str) -> Dict:
        """
        Fetch cost grouped by usage type

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with cost by usage type
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        params = {
            'TimePeriod': {'Start': start, 'End': end},
            'Granularity': 'DAILY',
            'Metrics': ['UnblendedCost'],
            'GroupBy': [{'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}],
        }

        all_results = []
        for response in self._paginated_query(params):
            all_results.extend(response.get('ResultsByTime', []))

        return {
            'account_id': self.account_id,
            'start_date': start_date,
            'end_date': end_date,
            'data': all_results
        }

    def fetch_anomalies(self, start_date: str, end_date: str) -> Dict:
        """
        Fetch cost anomalies

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with cost anomalies
        """
        start, end = get_date_range_for_cost(start_date, end_date)

        try:
            response = self.ce.get_anomalies(
                DateInterval={'StartDate': start, 'EndDate': end}
            )

            return {
                'account_id': self.account_id,
                'start_date': start_date,
                'end_date': end_date,
                'data': response.get('Anomalies', [])
            }
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch anomalies: {e}")
            return {
                'account_id': self.account_id,
                'start_date': start_date,
                'end_date': end_date,
                'data': [],
                'error': str(e)
            }

    def save_csv(self, data: Dict, month_key: str, filename: str):
        """
        Save cost data to CSV file

        Args:
            data: Data dictionary to save
            month_key: Month key (YYYY-MM)
            filename: Filename (without extension)
        """
        # Map filename to consolidated file name
        consolidated_map = {
            'daily_cost': 'daily_cost_consolidated.csv',
            'service_cost': 'service_cost_consolidated.csv',
            'usage_type_cost': 'usage_type_cost_consolidated.csv',
            'anomalies': 'anomalies_consolidated.csv'
        }
        consolidated_filename = consolidated_map.get(filename, f"{filename}_consolidated.csv")
        consolidated_file = DATA_DIR / "cost" / consolidated_filename

        # Flatten the data structure for CSV
        rows = []
        for result in data.get('data', []):
            if filename == 'daily_cost':
                # Daily cost - simple structure
                date_str = result.get('TimePeriod', {}).get('Start', '')
                amount = result.get('Total', {}).get('UnblendedCost', {}).get('Amount', '0')
                unit = result.get('Total', {}).get('UnblendedCost', {}).get('Unit', 'USD')
                rows.append({
                    'account_id': data.get('account_id', ''),
                    'date': date_str,
                    'cost_amount': float(amount) if amount else 0.0,
                    'currency': unit
                })
            elif filename == 'service_cost':
                # Service cost - grouped by service
                date_str = result.get('TimePeriod', {}).get('Start', '')
                for group in result.get('Groups', []):
                    service_name = group.get('Keys', [''])[0]
                    amount = group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', '0')
                    unit = group.get('Metrics', {}).get('UnblendedCost', {}).get('Unit', 'USD')
                    rows.append({
                        'account_id': data.get('account_id', ''),
                        'date': date_str,
                        'service_name': service_name,
                        'cost_amount': float(amount) if amount else 0.0,
                        'currency': unit
                    })
            elif filename == 'usage_type_cost':
                # Usage type cost
                date_str = result.get('TimePeriod', {}).get('Start', '')
                for group in result.get('Groups', []):
                    usage_type = group.get('Keys', [''])[0]
                    amount = group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount', '0')
                    unit = group.get('Metrics', {}).get('UnblendedCost', {}).get('Unit', 'USD')
                    rows.append({
                        'account_id': data.get('account_id', ''),
                        'date': date_str,
                        'usage_type': usage_type,
                        'cost_amount': float(amount) if amount else 0.0,
                        'currency': unit
                    })
            elif filename == 'anomalies':
                # Anomalies
                for anomaly in data.get('data', []):
                    rows.append({
                        'account_id': data.get('account_id', ''),
                        'anomaly_id': anomaly.get('AnomalyId', ''),
                        'anomaly_start_date': anomaly.get('AnomalyStartDate', ''),
                        'anomaly_end_date': anomaly.get('AnomalyEndDate', ''),
                        'dimension_value': anomaly.get('DimensionValue', ''),
                        'root_cause': str(anomaly.get('RootCauses', [])),
                        'impact': str(anomaly.get('Impact', {}))
                    })

        # Write CSV (append to consolidated file only - no monthly folders)
        if rows:
            fieldnames = list(rows[0].keys())

            # Ensure cost directory exists
            consolidated_file.parent.mkdir(parents=True, exist_ok=True)

            # Check if consolidated file exists
            file_exists = consolidated_file.exists()

            # Append to consolidated file
            with open(consolidated_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(rows)

            logger.info(f"  ✓ Saved {len(rows)} rows → {consolidated_filename}")
        else:
            # Create empty CSV with headers if file doesn't exist
            if not consolidated_file.exists():
                consolidated_file.parent.mkdir(parents=True, exist_ok=True)
                with open(consolidated_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['account_id', 'date', 'note'])
                    writer.writerow([data.get('account_id', ''), data.get('start_date', ''), 'No data'])
                logger.info(f"  ✓ Created empty file {consolidated_filename}")

    def collect_month(self, start_date: str, end_date: str):
        """
        Collect all cost data for a specific month

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        month_key = get_month_key(start_date)
        logger.info(f"  Fetching cost data for {month_key}...")

        # Fetch all cost data types
        logger.info("    → Daily cost...")
        daily_cost = self.fetch_daily_cost(start_date, end_date)
        logger.info(" ✓")

        logger.info("    → Service cost...")
        service_cost = self.fetch_service_cost(start_date, end_date)
        logger.info(" ✓")

        logger.info("    → Usage type cost...")
        usage_type_cost = self.fetch_usage_type_cost(start_date, end_date)
        logger.info(" ✓")

        logger.info("    → Anomalies...")
        anomalies = self.fetch_anomalies(start_date, end_date)
        logger.info(" ✓")

        # Save to CSV files
        logger.info("    → Saving files...")
        self.save_csv(daily_cost, month_key, "daily_cost")
        self.save_csv(service_cost, month_key, "service_cost")
        self.save_csv(usage_type_cost, month_key, "usage_type_cost")
        self.save_csv(anomalies, month_key, "anomalies")
