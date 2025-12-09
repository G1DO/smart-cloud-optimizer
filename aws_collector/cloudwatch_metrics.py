"""
CloudWatch Metrics Collection Module
Handles fetching metrics from AWS CloudWatch
"""
from datetime import datetime
from typing import List, Dict, Any


class CloudWatchMetrics:
    """CloudWatch metrics fetcher"""
    
    def __init__(self, session):
        self.session = session
    
    def fetch_metric(
        self,
        cloudwatch_client,
        namespace: str,
        metric_name: str,
        dimensions: List[Dict[str, str]],
        start_time: datetime,
        end_time: datetime,
        period: int,
        statistics: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch metric statistics from CloudWatch
        
        Args:
            cloudwatch_client: boto3 CloudWatch client
            namespace: CloudWatch namespace (e.g., "AWS/EC2")
            metric_name: Name of the metric
            dimensions: List of dimension dictionaries
            start_time: Start time for the metric query
            end_time: End time for the metric query
            period: Period in seconds
            statistics: List of statistics to retrieve (e.g., ["Average", "Maximum"])
        
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
                Statistics=statistics,
            )
            return response.get("Datapoints", [])
        except Exception as e:
            print(f"[WARN] Failed to fetch metric {namespace}/{metric_name}: {e}")
            return []

