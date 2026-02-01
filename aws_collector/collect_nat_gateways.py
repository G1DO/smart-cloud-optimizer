"""
collect_nat_gateways.py — NAT Gateway collector.

Collects NAT Gateway inventory and CloudWatch metrics across all
enabled AWS regions, saving results to consolidated CSV files.

Part of the Smart Cloud Optimizer graduation project.
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range

logger = logging.getLogger(__name__)


class NATGatewayCollector:
    """Collects NAT Gateway data and metrics"""

    def __init__(self, config: AWSConfig):
        """
        Initialize NAT Gateway Collector

        Args:
            config: AWSConfig instance
        """
        self.config = config
        self.account_id = config.account_id
        self.regions = config.regions

    def list_nat_gateways(self) -> List[Dict]:
        """
        List all NAT Gateways across all regions

        Returns:
            List of NAT Gateway dictionaries
        """
        all_nat_gateways = []

        logger.info("\n[NAT Gateways] Collecting inventory...")
        for region in self.regions:
            try:
                ec2 = self.config.get_ec2_client(region)
                paginator = ec2.get_paginator('describe_nat_gateways')

                for page in paginator.paginate():
                    for nat in page.get('NatGateways', []):
                        # Extract tags
                        tags = {tag['Key']: tag['Value'] for tag in nat.get('Tags', [])}

                        nat_data = {
                            'account_id': self.account_id,
                            'region': region,
                            'nat_gateway_id': nat['NatGatewayId'],
                            'vpc_id': nat.get('VpcId', ''),
                            'subnet_id': nat.get('SubnetId', ''),
                            'state': nat.get('State', ''),
                            'connectivity_type': nat.get('ConnectivityType', 'public'),
                            'allocation_id': nat.get('NatGatewayAddresses', [{}])[0].get('AllocationId', '') if nat.get('NatGatewayAddresses') else '',
                            'private_ip': nat.get('NatGatewayAddresses', [{}])[0].get('PrivateIp', '') if nat.get('NatGatewayAddresses') else '',
                            'public_ip': nat.get('NatGatewayAddresses', [{}])[0].get('PublicIp', '') if nat.get('NatGatewayAddresses') else '',
                            'create_time': nat.get('CreateTime').isoformat() if nat.get('CreateTime') else None,
                            'tags': tags,
                        }
                        all_nat_gateways.append(nat_data)
            except Exception as e:
                logger.warning(f"  [WARN] Failed to list NAT Gateways in {region}: {e}")

        return all_nat_gateways

    def save_inventory(self) -> Path:
        """
        Save NAT Gateway inventory to CSV

        Returns:
            Path to saved file
        """
        nat_gateways = self.list_nat_gateways()

        inventory_dir = DATA_DIR / "inventory"
        inventory_dir.mkdir(parents=True, exist_ok=True)
        filepath = inventory_dir / "nat_gateways.csv"

        if nat_gateways:
            fieldnames = list(nat_gateways[0].keys())
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(nat_gateways)
            logger.info(f"  ✓ Saved {len(nat_gateways)} NAT Gateways to {filepath.name}")
            return filepath
        else:
            # Create empty file with headers
            fieldnames = [
                'account_id', 'region', 'nat_gateway_id', 'vpc_id', 'subnet_id',
                'state', 'connectivity_type', 'allocation_id', 'private_ip',
                'public_ip', 'create_time', 'tags'
            ]
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            logger.info(f"  ✓ Created empty inventory file {filepath.name}")
            return filepath

    def _fetch_metric(
        self,
        cloudwatch_client,
        nat_gateway_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 3600,
        statistics: List[str] = ['Sum']
    ) -> List[Dict]:
        """
        Fetch CloudWatch metric for NAT Gateway

        Args:
            cloudwatch_client: CloudWatch client
            nat_gateway_id: NAT Gateway ID
            metric_name: Metric name
            start_time: Start datetime
            end_time: End datetime
            period: Period in seconds
            statistics: List of statistics to fetch

        Returns:
            List of datapoints
        """
        try:
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/NATGateway',
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'NatGatewayId', 'Value': nat_gateway_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics
            )
            return response.get('Datapoints', [])
        except Exception as e:
            logger.warning(f"[WARN] Failed to fetch NAT Gateway metric {metric_name} for {nat_gateway_id}: {e}")
            return []

    def get_metrics(
        self,
        nat_gateway_id: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get NAT Gateway metrics

        Args:
            nat_gateway_id: NAT Gateway ID
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with NAT Gateway metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        metrics_data = {
            'BytesProcessed': self._fetch_metric(
                cloudwatch, nat_gateway_id, 'BytesProcessed', start_time, end_time,
                period=3600, statistics=['Sum']
            ),
            'ActiveConnectionCount': self._fetch_metric(
                cloudwatch, nat_gateway_id, 'ActiveConnectionCount', start_time, end_time,
                period=3600, statistics=['Average', 'Maximum']
            ),
        }

        return {
            'account_id': self.account_id,
            'region': region,
            'nat_gateway_id': nat_gateway_id,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics_data
        }

    def save_metrics_csv(self, data: Dict):
        """
        Save NAT Gateway metrics to consolidated CSV file

        Args:
            data: Metrics data dictionary
        """
        # Save directly to consolidated file in service subdirectory
        service_dir = DATA_DIR / "metrics" / "nat"
        service_dir.mkdir(parents=True, exist_ok=True)
        consolidated_file = service_dir / "nat_metrics_consolidated.csv"

        # Flatten metrics data for CSV
        rows = []
        metrics_data = data.get('metrics', {})

        # Get all unique timestamps from all metrics
        all_timestamps = set()
        for metric_name, datapoints in metrics_data.items():
            for dp in datapoints:
                if 'Timestamp' in dp:
                    all_timestamps.add(dp['Timestamp'])

        # Sort timestamps
        sorted_timestamps = sorted(all_timestamps)

        # Build rows - one per timestamp
        for ts in sorted_timestamps:
            # Format timestamp consistently for ML (ISO format)
            if isinstance(ts, datetime):
                timestamp_str = ts.isoformat()
            else:
                timestamp_str = str(ts)

            row = {
                'account_id': data.get('account_id', ''),
                'region': data.get('region', ''),
                'nat_gateway_id': data.get('nat_gateway_id', ''),
                'timestamp': timestamp_str,
            }

            # Add metric values for this timestamp
            for metric_name, datapoints in metrics_data.items():
                for dp in datapoints:
                    if dp.get('Timestamp') == ts:
                        # Extract statistics - ensure numeric values
                        for stat in ['Average', 'Maximum', 'Sum', 'Minimum']:
                            if stat in dp:
                                value = dp[stat]
                                # Convert to float, handle None
                                try:
                                    row[f"{metric_name}_{stat.lower()}"] = float(value) if value is not None else ''
                                except (ValueError, TypeError):
                                    row[f"{metric_name}_{stat.lower()}"] = ''
                        break

            rows.append(row)

        # Write CSV (append to consolidated file)
        if rows:
            fieldnames = list(rows[0].keys())

            # Check if consolidated file exists
            file_exists = consolidated_file.exists()

            # Read existing data to check for duplicates
            existing_rows = []
            if file_exists:
                try:
                    with open(consolidated_file, 'r', newline='') as f:
                        reader = csv.DictReader(f)
                        existing_rows = list(reader)
                except Exception as e:
                    logger.warning(f"  [WARN] Could not read existing file for deduplication: {e}")

            # Create set of existing unique keys (nat_gateway_id + region + timestamp)
            existing_keys = set()
            if existing_rows:
                for row in existing_rows:
                    key = (row.get('nat_gateway_id', ''), row.get('region', ''), row.get('timestamp', ''))
                    existing_keys.add(key)

            # Filter out duplicates
            new_rows = []
            for row in rows:
                key = (row.get('nat_gateway_id', ''), row.get('region', ''), row.get('timestamp', ''))
                if key not in existing_keys:
                    new_rows.append(row)
                    existing_keys.add(key)  # Prevent duplicates within this batch

            # Append only new rows
            if new_rows:
                with open(consolidated_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if not file_exists:
                        writer.writeheader()
                    writer.writerows(new_rows)
                logger.info(f"  ✓ Added {len(new_rows)} new rows to nat_metrics_consolidated.csv (skipped {len(rows) - len(new_rows)} duplicates)")
            else:
                logger.info(f"  ✓ All {len(rows)} rows already exist (skipped duplicates)")
        else:
            # Create empty CSV with basic structure if file doesn't exist
            if not consolidated_file.exists():
                consolidated_file.parent.mkdir(parents=True, exist_ok=True)
                base_fields = ['account_id', 'region', 'nat_gateway_id', 'timestamp']

                with open(consolidated_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=base_fields)
                    writer.writeheader()
                    writer.writerow({
                        'account_id': data.get('account_id', ''),
                        'region': data.get('region', ''),
                        'nat_gateway_id': data.get('nat_gateway_id', ''),
                        'timestamp': data.get('start_date', ''),
                    })
                logger.info(f"  ✓ Created empty metrics file nat_metrics_consolidated.csv")
