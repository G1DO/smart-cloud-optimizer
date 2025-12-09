"""
CloudFront Collector
Collects CloudFront distributions inventory and CloudWatch metrics
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range, get_month_key


class CloudFrontCollector:
    """Collects CloudFront distribution data and metrics"""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize CloudFront Collector
        
        Args:
            config: AWSConfig instance
        """
        self.config = config
        self.account_id = config.account_id
        self.cloudfront = config.session.client('cloudfront', region_name='us-east-1')
        self.cloudwatch = config.session.client('cloudwatch', region_name='us-east-1')
    
    def list_distributions(self) -> List[Dict]:
        """
        List all CloudFront distributions
        
        Returns:
            List of distribution dictionaries
        """
        distributions = []
        try:
            paginator = self.cloudfront.get_paginator('list_distributions')
            for page in paginator.paginate():
                for dist in page.get('DistributionList', {}).get('Items', []):
                    distribution_data = {
                        'account_id': self.account_id,
                        'distribution_id': dist['Id'],
                        'domain_name': dist.get('DomainName', ''),
                        'status': dist.get('Status', ''),
                        'enabled': dist.get('Enabled', False),
                        'comment': dist.get('Comment', ''),
                        'price_class': dist.get('PriceClass', ''),
                        'last_modified': dist.get('LastModifiedTime').isoformat() if dist.get('LastModifiedTime') else None,
                    }
                    distributions.append(distribution_data)
        except Exception as e:
            print(f"[WARN] Failed to list CloudFront distributions: {e}")
        
        return distributions
    
    def save_inventory(self) -> Path:
        """
        Save CloudFront inventory to CSV
        
        Returns:
            Path to saved file
        """
        print("\n[CloudFront] Collecting inventory...")
        distributions = self.list_distributions()
        
        if distributions:
            df = pd.DataFrame(distributions)
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "cloudfront.csv"
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(distributions)} distributions to {filepath.name}")
            return filepath
        else:
            # Create empty file with headers
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "cloudfront.csv"
            df = pd.DataFrame(columns=[
                'account_id', 'distribution_id', 'domain_name', 'status',
                'enabled', 'comment', 'price_class', 'last_modified'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty inventory file {filepath.name}")
            return filepath
    
    def _fetch_metric(
        self,
        distribution_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 3600,
        statistics: List[str] = ['Sum']
    ) -> List[Dict]:
        """
        Fetch CloudWatch metric for CloudFront distribution
        
        Args:
            distribution_id: CloudFront distribution ID
            metric_name: Metric name
            start_time: Start datetime
            end_time: End datetime
            period: Period in seconds
            statistics: List of statistics to fetch
        
        Returns:
            List of datapoints
        """
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/CloudFront',
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'DistributionId', 'Value': distribution_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics
            )
            return response.get('Datapoints', [])
        except Exception as e:
            print(f"[WARN] Failed to fetch CloudFront metric {metric_name} for {distribution_id}: {e}")
            return []
    
    def get_metrics(
        self,
        distribution_id: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get CloudFront distribution metrics
        
        Args:
            distribution_id: CloudFront distribution ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with CloudFront metrics
        """
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        metrics_data = {
            'Requests': self._fetch_metric(
                distribution_id, 'Requests', start_time, end_time,
                period=3600, statistics=['Sum']
            ),
            'BytesDownloaded': self._fetch_metric(
                distribution_id, 'BytesDownloaded', start_time, end_time,
                period=3600, statistics=['Sum']
            ),
            'BytesUploaded': self._fetch_metric(
                distribution_id, 'BytesUploaded', start_time, end_time,
                period=3600, statistics=['Sum']
            ),
            'CacheHitRate': self._fetch_metric(
                distribution_id, 'CacheHitRate', start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'TotalErrorRate': self._fetch_metric(
                distribution_id, 'TotalErrorRate', start_time, end_time,
                period=3600, statistics=['Average']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'distribution_id': distribution_id,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics_data
        }
    
    def save_metrics_csv(self, data: Dict, month_key: str):
        """
        Save CloudFront metrics to CSV file
        
        Args:
            data: Metrics data dictionary
            month_key: Month key (YYYY-MM)
        """
        metrics_dir = DATA_DIR / "metrics" / "cloudfront" / month_key
        metrics_dir.mkdir(parents=True, exist_ok=True)
        filepath = metrics_dir / "cloudfront_metrics.csv"
        
        rows = []
        metrics_data = data.get('metrics', {})
        
        # Collect all unique timestamps
        all_timestamps = set()
        for metric_name, datapoints in metrics_data.items():
            for dp in datapoints:
                if 'Timestamp' in dp:
                    all_timestamps.add(dp['Timestamp'])
        
        sorted_timestamps = sorted(list(all_timestamps))
        
        # Create rows for each timestamp
        for ts in sorted_timestamps:
            row = {
                'account_id': data.get('account_id', ''),
                'distribution_id': data.get('distribution_id', ''),
                'timestamp': ts.isoformat() if isinstance(ts, datetime) else ts,
            }
            
            # Add metric values
            for metric_name, datapoints in metrics_data.items():
                for dp in datapoints:
                    if dp.get('Timestamp') == ts:
                        for stat in ['Average', 'Sum', 'Maximum', 'Minimum']:
                            if stat in dp:
                                row[f"{metric_name}_{stat.lower()}"] = float(dp[stat]) if dp[stat] is not None else None
                        break
            
            rows.append(row)
        
        if rows:
            df = pd.DataFrame(rows)
            # Append to existing file if it exists
            if filepath.exists():
                existing_df = pd.read_csv(filepath)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=['account_id', 'distribution_id', 'timestamp'], keep='last')
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(rows)} metric rows to {filepath.name}")
        else:
            # Create empty file with headers
            df = pd.DataFrame(columns=[
                'account_id', 'distribution_id', 'timestamp',
                'Requests_sum', 'BytesDownloaded_sum', 'BytesUploaded_sum',
                'CacheHitRate_average', 'TotalErrorRate_average'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty metrics file {filepath.name}")

