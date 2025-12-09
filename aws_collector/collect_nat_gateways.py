"""
NAT Gateways Collector
Collects NAT Gateway inventory and CloudWatch metrics
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .config import AWSConfig, DATA_DIR
from .date_utils import get_datetime_range, get_month_key


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
        
        print("\n[NAT Gateways] Collecting inventory...")
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
                print(f"  [WARN] Failed to list NAT Gateways in {region}: {e}")
        
        return all_nat_gateways
    
    def save_inventory(self) -> Path:
        """
        Save NAT Gateway inventory to CSV
        
        Returns:
            Path to saved file
        """
        nat_gateways = self.list_nat_gateways()
        
        if nat_gateways:
            df = pd.DataFrame(nat_gateways)
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "nat_gateways.csv"
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(nat_gateways)} NAT Gateways to {filepath.name}")
            return filepath
        else:
            # Create empty file with headers
            inventory_dir = DATA_DIR / "inventory"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            filepath = inventory_dir / "nat_gateways.csv"
            df = pd.DataFrame(columns=[
                'account_id', 'region', 'nat_gateway_id', 'vpc_id', 'subnet_id',
                'state', 'connectivity_type', 'allocation_id', 'private_ip',
                'public_ip', 'create_time', 'tags'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty inventory file {filepath.name}")
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
            print(f"[WARN] Failed to fetch NAT Gateway metric {metric_name} for {nat_gateway_id}: {e}")
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
    
    def save_metrics_csv(self, data: Dict, month_key: str):
        """
        Save NAT Gateway metrics to CSV file
        
        Args:
            data: Metrics data dictionary
            month_key: Month key (YYYY-MM)
        """
        metrics_dir = DATA_DIR / "metrics" / "nat" / month_key
        metrics_dir.mkdir(parents=True, exist_ok=True)
        filepath = metrics_dir / "nat_metrics.csv"
        
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
                'nat_gateway_id': data.get('nat_gateway_id', ''),
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
                df = df.drop_duplicates(subset=['account_id', 'region', 'nat_gateway_id', 'timestamp'], keep='last')
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(rows)} metric rows to {filepath.name}")
        else:
            # Create empty file with headers
            df = pd.DataFrame(columns=[
                'account_id', 'region', 'nat_gateway_id', 'timestamp',
                'BytesProcessed_sum', 'ActiveConnectionCount_average', 'ActiveConnectionCount_maximum'
            ])
            df.to_csv(filepath, index=False)
            print(f"  ✓ Created empty metrics file {filepath.name}")

