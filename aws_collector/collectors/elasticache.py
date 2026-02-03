"""
elasticache.py — ElastiCache collector following BaseCollector pattern.

Collects ElastiCache cluster inventory and CloudWatch metrics across all
enabled AWS regions.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import sqlite3
from typing import Dict, List

import storage

from ..config import AWSConfig
from ..metrics import ELASTICACHE_METRIC_MAP, fetch_cw_metric, get_datetime_range
from ..transforms import flatten_cw_metrics, transform_elasticache_nodes
from .base import BaseCollector

logger = logging.getLogger(__name__)


class ElastiCacheCollector(BaseCollector):
    """Collects ElastiCache cluster data and metrics."""

    SERVICE_NAME: str = "ElastiCache"

    def __init__(
        self,
        config: AWSConfig,
        conn: sqlite3.Connection,
        user_id: str,
    ) -> None:
        """Initialize ElastiCache Collector.

        Args:
            config: AWSConfig instance for AWS API access.
            conn: SQLite connection for data storage.
            user_id: User ID for data isolation.
        """
        super().__init__(config, conn, user_id)

    def list_resources(self) -> List[Dict]:
        """List all ElastiCache clusters across all regions.

        Returns:
            List of cluster dictionaries with inventory data.
        """
        all_clusters: List[Dict] = []
        failed_regions = []

        logger.info(f"\n[{self.SERVICE_NAME}] Collecting inventory...")
        for region in self.regions:
            try:
                client = self.config.get_elasticache_client(region)
                paginator = client.get_paginator("describe_cache_clusters")

                for page in paginator.paginate(ShowCacheNodeInfo=True):
                    for cluster in page.get("CacheClusters", []):
                        cluster_data = {
                            "account_id": self.account_id,
                            "region": region,
                            "cache_cluster_id": cluster["CacheClusterId"],
                            "cache_node_type": cluster.get("CacheNodeType", ""),
                            "engine": cluster.get("Engine", ""),
                            "engine_version": cluster.get("EngineVersion"),
                            "num_cache_nodes": cluster.get("NumCacheNodes", 1),
                        }
                        all_clusters.append(cluster_data)
            except Exception as e:
                logger.warning(
                    f"  [WARN] Failed to list ElastiCache clusters in {region}: {e}"
                )
                failed_regions.append(region)

        if failed_regions:
            logger.warning(f"  [ElastiCache] Skipped {len(failed_regions)} regions: {failed_regions}")
        logger.info(f"  Found {len(all_clusters)} ElastiCache clusters")
        return all_clusters

    def get_metrics(
        self,
        resource_id: str,
        region: str,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Get ElastiCache cluster metrics.

        Args:
            resource_id: ElastiCache cluster ID (cache_cluster_id).
            region: AWS region.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Dictionary with ElastiCache metrics.
        """
        cloudwatch = self.config.get_cloudwatch_client(region)
        start_time, end_time = get_datetime_range(start_date, end_date)

        dimensions = [{"Name": "CacheClusterId", "Value": resource_id}]

        metrics_data = {
            "CPUUtilization": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "CPUUtilization",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "DatabaseMemoryUsagePercentage": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "DatabaseMemoryUsagePercentage",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "CurrConnections": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "CurrConnections",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Average"],
            ),
            "CacheHits": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "CacheHits",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "CacheMisses": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "CacheMisses",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
            "Evictions": self._fetch_metric(
                cloudwatch,
                "AWS/ElastiCache",
                "Evictions",
                dimensions,
                start_time,
                end_time,
                period=3600,
                statistics=["Sum"],
            ),
        }

        return {
            "account_id": self.account_id,
            "region": region,
            "cache_cluster_id": resource_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics_data,
        }

    def collect(self, start_date: str, end_date: str) -> int:
        """Full collection: list resources, fetch metrics, store to DB.

        Args:
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Number of clusters successfully collected.
        """
        # Step 1: List all clusters
        clusters = self.list_resources()

        # Step 2: Insert inventory
        if clusters:
            rows = transform_elasticache_nodes(clusters)
            storage.insert_elasticache_nodes(self.conn, self.user_id, rows)

        # Step 3: Fetch and insert metrics for each cluster
        total = len(clusters)
        count = 0
        failed_clusters = []

        for idx, cluster in enumerate(clusters, 1):
            try:
                self._log_progress(idx, total)

                metrics = self.get_metrics(
                    cluster["cache_cluster_id"],
                    cluster["region"],
                    start_date,
                    end_date,
                )
                rows = flatten_cw_metrics(
                    metrics, "cache_cluster_id", ELASTICACHE_METRIC_MAP
                )
                if rows:
                    storage.insert_elasticache_metrics(
                        self.conn, self.user_id, rows
                    )
                count += 1
            except Exception as e:
                logger.warning(
                    f"    [WARN] Failed ElastiCache metrics for "
                    f"{cluster['cache_cluster_id']}: {e}"
                )
                failed_clusters.append(cluster["cache_cluster_id"])

        if failed_clusters:
            logger.warning(f"  [ElastiCache] Failed {len(failed_clusters)} clusters: {failed_clusters[:5]}{'...' if len(failed_clusters) > 5 else ''}")
        logger.info(
            f"  Collected {self.SERVICE_NAME} metrics for {count}/{total} clusters"
        )
        return count
