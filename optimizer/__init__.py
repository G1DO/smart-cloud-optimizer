"""optimizer -- Cost optimization via LP solver and rule engine.

Part of the Smart Cloud Optimizer graduation project.
"""

from .compute_lp import optimize_ec2, optimize_rds
from .engine import optimize
from .rules import (
    check_dynamodb_tables,
    check_ebs_volumes,
    check_ec2_pricing,
    check_elb_idle,
    check_lambda_memory,
    check_nat_gateways,
    check_rds_pricing,
    check_s3_buckets,
)

__all__ = [
    "optimize",
    "optimize_ec2",
    "optimize_rds",
    "check_ec2_pricing",
    "check_rds_pricing",
    "check_lambda_memory",
    "check_ebs_volumes",
    "check_s3_buckets",
    "check_dynamodb_tables",
    "check_nat_gateways",
    "check_elb_idle",
]
