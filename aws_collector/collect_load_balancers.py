"""
Load Balancers Collector
Collects ALB and NLB inventory and CloudWatch metrics
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range, get_month_key


class LoadBalancerCollector:
    """Collects Load Balancer (ALB/NLB) data and metrics"""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize Load Balancer Collector
        
        Args:
            config: AWSConfig instance
        """
        self.config = config
        self.account_id = config.account_id
        self.regions = config.regions
    
    def list_load_balancers(self) -> List[Dict]:
        """
        List all Load Balancers (ALB + NLB) across all regions
        
        Returns:
            List of Load Balancer dictionaries
        """
        all_load_balancers = []
        
        print("\n[Load Balancers] Collecting inventory...")
        for region in self.regions:
            try:
                elbv2 = self.config.session.client('elbv2', region_name=region)
                paginator = elbv2.get_paginator('describe_load_balancers')
                
                for page in paginator.paginate():
                    for lb in page.get('LoadBalancers', []):
                        # Get security groups and subnets
                        security_groups = ','.join(lb.get('SecurityGroups', []))
                        subnets = ','.join(lb.get('AvailabilityZones', []))
                        
                        lb_data = {
                            'account_id': self.account_id,
                            'region': region,
                            'lb_arn': lb['LoadBalancerArn'],
                            'lb_name': lb.get('LoadBalancerName', ''),
                            'type': lb.get('Type', ''),  # application or network
                            'scheme': lb.get('Scheme', ''),  # internet-facing or internal
                            'dns_name': lb.get('DNSName', ''),
                            'state': lb.get('State', {}).get('Code', ''),
                            'vpc_id': lb.get('VpcId', ''),
                            'security_groups': security_groups,
                            'subnets': subnets,
                            'canonical_hosted_zone_id': lb.get('CanonicalHostedZoneId', ''),
                            'created_time': lb.get('CreatedTime').isoformat() if lb.get('CreatedTime') else None,
                        }
                        all_load_balancers.append(lb_data)
            except Exception as e:
                print(f"  [WARN] Failed to list Load Balancers in {region}: {e}")
        
        return all_load_balancers
    
    def save_inventory(self) -> Path:
        """
        Save Load Balancer inventory to CSV
        
        Returns:
            Path to saved file
        """
        load_balancers = self.list_load_balancers()
        
        if load_balancers:
            df = pd.DataFrame(load_balancers)
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "load_balancers.csv"
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(load_balancers)} Load Balancers to {filepath.name}")
            return filepath
        else:
            # Create empty file with headers
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "load_balancers.csv"
            df = pd.DataFrame(columns=[
                'account_id', 'region', 'lb_arn', 'lb_name', 'type', 'scheme',
                'dns_name', 'state', 'vpc_id', 'security_groups', 'subnets',
                'canonical_hosted_zone_id', 'created_time'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty inventory file {filepath.name}")
            return filepath
    
    def _fetch_metric(
        self,
        cloudwatch_client,
        load_balancer_arn: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        namespace: str = 'AWS/ApplicationELB',
        period: int = 3600,
        statistics: List[str] = ['Sum']
    ) -> List[Dict]:
        """
        Fetch CloudWatch metric for Load Balancer
        
        Args:
            cloudwatch_client: CloudWatch client
            load_balancer_arn: Load Balancer ARN
            metric_name: Metric name
            start_time: Start datetime
            end_time: End datetime
            period: Period in seconds
            statistics: List of statistics to fetch
        
        Returns:
            List of datapoints
        """
        try:
            # Determine namespace based on load balancer type
            # ALB uses 'AWS/ApplicationELB', NLB uses 'AWS/NetworkELB'
            namespace = 'AWS/ApplicationELB'  # Default, will be overridden for NLB
            
            response = cloudwatch_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'LoadBalancer', 'Value': load_balancer_arn}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics
            )
            return response.get('Datapoints', [])
        except Exception as e:
            print(f"[WARN] Failed to fetch Load Balancer metric {metric_name} for {load_balancer_arn}: {e}")
            return []
    
    def get_alb_metrics(
        self,
        load_balancer_arn: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get ALB metrics
        
        Args:
            load_balancer_arn: Load Balancer ARN
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with ALB metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        metrics_data = {
            'RequestCount': self._fetch_metric(
                cloudwatch, load_balancer_arn, 'RequestCount', start_time, end_time,
                namespace='AWS/ApplicationELB', period=3600, statistics=['Sum']
            ),
            'HTTPCode_ELB_4XX_Count': self._fetch_metric(
                cloudwatch, load_balancer_arn, 'HTTPCode_ELB_4XX_Count', start_time, end_time,
                namespace='AWS/ApplicationELB', period=3600, statistics=['Sum']
            ),
            'HTTPCode_ELB_5XX_Count': self._fetch_metric(
                cloudwatch, load_balancer_arn, 'HTTPCode_ELB_5XX_Count', start_time, end_time,
                namespace='AWS/ApplicationELB', period=3600, statistics=['Sum']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'lb_arn': load_balancer_arn,
            'lb_type': 'ALB',
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics_data
        }
    
    def get_nlb_metrics(
        self,
        load_balancer_arn: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Get NLB metrics
        
        Args:
            load_balancer_arn: Load Balancer ARN
            region: AWS region
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with NLB metrics
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)
        
        metrics_data = {
            'ProcessedBytes': self._fetch_metric(
                cloudwatch, load_balancer_arn, 'ProcessedBytes', start_time, end_time,
                namespace='AWS/NetworkELB', period=3600, statistics=['Sum']
            ),
            'NewFlowCount': self._fetch_metric(
                cloudwatch, load_balancer_arn, 'NewFlowCount', start_time, end_time,
                namespace='AWS/NetworkELB', period=3600, statistics=['Sum']
            ),
        }
        
        return {
            'account_id': self.account_id,
            'region': region,
            'lb_arn': load_balancer_arn,
            'lb_type': 'NLB',
            'start_date': start_date,
            'end_date': end_date,
            'metrics': metrics_data
        }
    
    def save_alb_metrics_csv(self, data: Dict, month_key: str):
        """
        Save ALB metrics to CSV file
        
        Args:
            data: Metrics data dictionary
            month_key: Month key (YYYY-MM)
        """
        metrics_dir = DATA_DIR / "metrics" / "alb" / month_key
        metrics_dir.mkdir(parents=True, exist_ok=True)
        filepath = metrics_dir / "alb_metrics.csv"
        
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
                'region': data.get('region', ''),
                'lb_arn': data.get('lb_arn', ''),
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
                df = df.drop_duplicates(subset=['account_id', 'region', 'lb_arn', 'timestamp'], keep='last')
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(rows)} ALB metric rows to {filepath.name}")
        else:
            # Create empty file with headers
            df = pd.DataFrame(columns=[
                'account_id', 'region', 'lb_arn', 'timestamp',
                'RequestCount_sum', 'HTTPCode_ELB_4XX_Count_sum', 'HTTPCode_ELB_5XX_Count_sum'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty ALB metrics file {filepath.name}")
    
    def save_nlb_metrics_csv(self, data: Dict, month_key: str):
        """
        Save NLB metrics to CSV file
        
        Args:
            data: Metrics data dictionary
            month_key: Month key (YYYY-MM)
        """
        metrics_dir = DATA_DIR / "metrics" / "nlb" / month_key
        metrics_dir.mkdir(parents=True, exist_ok=True)
        filepath = metrics_dir / "nlb_metrics.csv"
        
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
                'region': data.get('region', ''),
                'lb_arn': data.get('lb_arn', ''),
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
                df = df.drop_duplicates(subset=['account_id', 'region', 'lb_arn', 'timestamp'], keep='last')
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(rows)} NLB metric rows to {filepath.name}")
        else:
            # Create empty file with headers
            df = pd.DataFrame(columns=[
                'account_id', 'region', 'lb_arn', 'timestamp',
                'ProcessedBytes_sum', 'NewFlowCount_sum'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty NLB metrics file {filepath.name}")

