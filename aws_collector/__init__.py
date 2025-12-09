"""
AWS Collector Package
A modular system for collecting AWS usage data, costs, and metrics.
"""

__version__ = "2.0.0"

from .collector_runner import CollectorRunner
from .config import AWSConfig, init_config, get_config

# ML utilities available but not imported by default (requires pandas/numpy)
# Import with: from aws_collector.ml_utils import load_cost_data, add_time_features

__all__ = [
    "CollectorRunner",
    "AWSConfig",
    "init_config",
    "get_config",
]
