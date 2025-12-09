"""
CloudFront Collector
Collects CloudFront distributions inventory and CloudWatch metrics
"""
import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range


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
        
        inventory_dir = DATA_DIR / "inventory"
        inventory_dir.mkdir(parents=True, exist_ok=True)
        filepath = inventory_dir / "cloudfront.csv"
        
        if distributions:
            fieldnames = list(distributions[0].keys())
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(distributions)
            print(f"  ✓ Saved {len(distributions)} distributions to {filepath.name}")
            return filepath
        else:
            # Create empty file with headers
            fieldnames = [
                'account_id', 'distribution_id', 'domain_name', 'status',
                'enabled', 'comment', 'price_class', 'last_modified'
            ]
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
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
    
    def save_metrics_csv(self, data: Dict):
        """
        Save CloudFront metrics to consolidated CSV file
        
        Args:
            data: Metrics data dictionary
        """
        # Save directly to consolidated file in service subdirectory
        service_dir = DATA_DIR / "metrics" / "cloudfront"
        service_dir.mkdir(parents=True, exist_ok=True)
        consolidated_file = service_dir / "cloudfront_metrics_consolidated.csv"
        
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
                'distribution_id': data.get('distribution_id', ''),
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
            
            # Append to consolidated file
            with open(consolidated_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(rows)
            print(f"  ✓ Saved {len(rows)} metric rows to cloudfront_metrics_consolidated.csv")
        else:
            # Create empty CSV with basic structure if file doesn't exist
            if not consolidated_file.exists():
                consolidated_file.parent.mkdir(parents=True, exist_ok=True)
                base_fields = ['account_id', 'distribution_id', 'timestamp']
                
                with open(consolidated_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=base_fields)
                    writer.writeheader()
                    writer.writerow({
                        'account_id': data.get('account_id', ''),
                        'distribution_id': data.get('distribution_id', ''),
                        'timestamp': data.get('start_date', ''),
                    })
                print(f"  ✓ Created empty metrics file cloudfront_metrics_consolidated.csv")

