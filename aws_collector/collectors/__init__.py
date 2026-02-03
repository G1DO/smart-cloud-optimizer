"""
AWS Collectors Package — Service-specific data collectors.

Each collector follows a consistent pattern:
- list_resources(): Discover all resources across regions
- get_metrics(): Fetch CloudWatch metrics for a resource
- collect(): Full collection pipeline (list → metrics → store)
"""

from .base import BaseCollector
from .cost import CostCollector
from .dynamodb import DynamoDBCollector
from .ec2 import EC2Collector
from .ecs import ECSCollector
from .elasticache import ElastiCacheCollector
from .elb import ELBCollector
from .lambda_ import LambdaCollector
from .nat_gateway import NATGatewayCollector
from .pricing import PricingCollector
from .rds import RDSCollector
from .s3 import S3Collector

__all__ = [
    "BaseCollector",
    "CostCollector",
    "DynamoDBCollector",
    "EC2Collector",
    "ECSCollector",
    "ElastiCacheCollector",
    "ELBCollector",
    "LambdaCollector",
    "NATGatewayCollector",
    "PricingCollector",
    "RDSCollector",
    "S3Collector",
]
