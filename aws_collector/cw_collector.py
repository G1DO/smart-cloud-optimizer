"""
CloudWatch Metrics Collector
Fetches metrics month-by-month for EC2, EBS, Lambda, RDS, and S3
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range, get_month_key


class CloudWatchCollector:
    """Collects CloudWatch metrics for various AWS services"""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize CloudWatch Collector
        
        Args:
            config: AWSConfig instance
        """
        self.config = config
        self.account_id = config.account_id
    
    def _fetch_metric(
        self,
        cloudwatch_client,
        namespace: str,
        metric_name: str,
        dimensions: List[Dict],
        start_time: datetime,
        end_time: datetime,
        period: int = 3600,
        statistics: List[str] = ['Average']
    ) -> List[Dict]:
        """
        Fetch metric statistics from CloudWatch
        
        Args:
            cloudwatch_client: CloudWatch client
            namespace: Metric namespace
            metric_name: Metric name
            dimensions: Metric dimensions
            start_time: Start datetime
            end_time: End datetime
            period: Period in seconds
            statistics: List of statistics to fetch
        
        Returns:
            List of datapoints
        """
        try:
            response = cloudwatch_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics
            )
            return response.get('Datapoints', [])
        except Exception as e:
            print(f"[WARN] Failed to fetch {namespace}/{metric_name}: {e}")
            return []
    
    def get_ec2_metrics(
        self,
        instance_id: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get EC2 instance metrics
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with EC2 metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        dimensions = [{'Name': 'InstanceId', 'Value': instance_id}]
        
        metrics = {
            'CPUUtilization': self._fetch_metric(
                cloudwatch, 'AWS/EC2', 'CPUUtilization',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average', 'Maximum']
            ),
            'NetworkIn': self._fetch_metric(
                cloudwatch, 'AWS/EC2', 'NetworkIn',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'NetworkOut': self._fetch_metric(
                cloudwatch, 'AWS/EC2', 'NetworkOut',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'DiskReadOps': self._fetch_metric(
                cloudwatch, 'AWS/EC2', 'DiskReadOps',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'DiskWriteOps': self._fetch_metric(
                cloudwatch, 'AWS/EC2', 'DiskWriteOps',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'instance_id': instance_id,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics
        }
    
    def get_ebs_metrics(
        self,
        volume_id: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get EBS volume metrics
        
        Args:
            volume_id: EBS volume ID
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with EBS metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        dimensions = [{'Name': 'VolumeId', 'Value': volume_id}]
        
        metrics = {
            'VolumeReadBytes': self._fetch_metric(
                cloudwatch, 'AWS/EBS', 'VolumeReadBytes',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'VolumeWriteBytes': self._fetch_metric(
                cloudwatch, 'AWS/EBS', 'VolumeWriteBytes',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'VolumeIdleTime': self._fetch_metric(
                cloudwatch, 'AWS/EBS', 'VolumeIdleTime',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'VolumeConsumedReadWriteOps': self._fetch_metric(
                cloudwatch, 'AWS/EBS', 'VolumeConsumedReadWriteOps',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'volume_id': volume_id,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics
        }
    
    def get_lambda_metrics(
        self,
        function_name: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get Lambda function metrics
        
        Args:
            function_name: Lambda function name
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with Lambda metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        dimensions = [{'Name': 'FunctionName', 'Value': function_name}]
        
        metrics = {
            'Invocations': self._fetch_metric(
                cloudwatch, 'AWS/Lambda', 'Invocations',
                dimensions, start_time, end_time,
                period=3600, statistics=['Sum']
            ),
            'Duration': self._fetch_metric(
                cloudwatch, 'AWS/Lambda', 'Duration',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'Errors': self._fetch_metric(
                cloudwatch, 'AWS/Lambda', 'Errors',
                dimensions, start_time, end_time,
                period=3600, statistics=['Sum']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'function_name': function_name,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics
        }
    
    def get_rds_metrics(
        self,
        db_id: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get RDS instance metrics
        
        Args:
            db_id: RDS instance identifier
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with RDS metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        dimensions = [{'Name': 'DBInstanceIdentifier', 'Value': db_id}]
        
        metrics = {
            'CPUUtilization': self._fetch_metric(
                cloudwatch, 'AWS/RDS', 'CPUUtilization',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'FreeStorageSpace': self._fetch_metric(
                cloudwatch, 'AWS/RDS', 'FreeStorageSpace',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
            'DatabaseConnections': self._fetch_metric(
                cloudwatch, 'AWS/RDS', 'DatabaseConnections',
                dimensions, start_time, end_time,
                period=3600, statistics=['Average']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'db_instance_id': db_id,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics
        }
    
    def get_s3_metrics(
        self,
        bucket_name: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get S3 bucket metrics
        
        Args:
            bucket_name: S3 bucket name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with S3 metrics
        """
        # S3 metrics are in us-east-1
        cloudwatch = self.config.get_cloudwatch_client('us-east-1')
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        dimensions_base = [{'Name': 'BucketName', 'Value': bucket_name}]
        
        metrics = {}
        
        # Fetch for StandardStorage
        dimensions = dimensions_base + [{'Name': 'StorageType', 'Value': 'StandardStorage'}]
        
        metrics['BucketSizeBytes'] = self._fetch_metric(
            cloudwatch, 'AWS/S3', 'BucketSizeBytes',
            dimensions, start_time, end_time,
            period=86400, statistics=['Average']  # Daily for S3
        )
        
        metrics['NumberOfObjects'] = self._fetch_metric(
            cloudwatch, 'AWS/S3', 'NumberOfObjects',
            dimensions, start_time, end_time,
            period=86400, statistics=['Average']
        )
        
        return {
            'account_id': self.account_id,
            'bucket_name': bucket_name,
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics
        }
    
    def save_csv(self, data: Dict, service: str, resource_id: str):
        """
        Save metrics data to consolidated CSV file
        
        Args:
            data: Data dictionary to save
            service: Service name (ec2, ebs, lambda, rds, s3)
            resource_id: Resource identifier (instance_id, volume_id, etc.)
        """
        # Save directly to consolidated file in service subdirectory
        service_dir = DATA_DIR / "metrics" / service
        service_dir.mkdir(parents=True, exist_ok=True)
        consolidated_file = service_dir / f"{service}_metrics_consolidated.csv"
        
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
                'timestamp': timestamp_str,
            }
            
            # Add resource identifier based on service
            if service == 'ec2':
                row['instance_id'] = data.get('instance_id', resource_id)
            elif service == 'ebs':
                row['volume_id'] = data.get('volume_id', resource_id)
            elif service == 'lambda':
                row['function_name'] = data.get('function_name', resource_id)
            elif service == 'rds':
                row['db_instance_id'] = data.get('db_instance_id', resource_id)
            elif service == 's3':
                row['bucket_name'] = data.get('bucket_name', resource_id)
            
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
        
        # Write CSV (append to consolidated file only - no monthly folders)
        if rows:
            fieldnames = list(rows[0].keys())
            
            # Ensure metrics directory exists
            consolidated_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if consolidated file exists
            file_exists = consolidated_file.exists()
            
            # Append to consolidated file
            with open(consolidated_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(rows)
        else:
            # Create empty CSV with basic structure if file doesn't exist
            if not consolidated_file.exists():
                consolidated_file.parent.mkdir(parents=True, exist_ok=True)
                base_fields = ['account_id', 'region', 'timestamp']
                if service == 'ec2':
                    base_fields.append('instance_id')
                elif service == 'ebs':
                    base_fields.append('volume_id')
                elif service == 'lambda':
                    base_fields.append('function_name')
                elif service == 'rds':
                    base_fields.append('db_instance_id')
                elif service == 's3':
                    base_fields.append('bucket_name')
                
                with open(consolidated_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=base_fields)
                    writer.writeheader()
                    writer.writerow({
                        'account_id': data.get('account_id', ''),
                        'region': data.get('region', ''),
                        'timestamp': data.get('start_date', ''),
                    })

