"""
AWS Collector Package — Modular system for collecting AWS usage data.

Collects costs, metrics, inventory, and pricing data across 10 AWS services:
EC2, RDS, Lambda, S3, DynamoDB, ElastiCache, ECS, NAT Gateway, ELB, EBS.
"""

__version__ = "3.0.0"

from .config import AWSConfig, get_config, init_config
from .runner import CollectorRunner

__all__ = [
    "CollectorRunner",
    "AWSConfig",
    "init_config",
    "get_config",
]
