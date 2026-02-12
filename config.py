"""
config.py — Project-wide configuration for Smart Cloud Optimizer.

Single source of truth for paths, constants, and environment settings.
AWS-specific boto3 client configuration lives in aws_collector/config.py.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
import os
from pathlib import Path
from typing import NamedTuple

# === Paths ===
PROJECT_ROOT: Path = Path(__file__).parent
DATA_DIR: Path = PROJECT_ROOT / "data"
DB_PATH: Path = DATA_DIR / "cloud_optimizer.db"

# === Mode ===
DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

# === AWS ===
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCOUNT_ID: str = os.getenv("AWS_ACCOUNT_ID", "SYNTHETIC-001")

# === Collection Defaults ===
DEFAULT_COLLECTION_MONTHS: int = 12
DEFAULT_SYNTHETIC_DAYS: int = 365

# === AWS API Settings ===
API_TIMEOUT: int = 30
MAX_RETRIES: int = 3
CHUNK_SIZE: int = 100

# === API Keys ===
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Google Gemini configuration (for ai_module)
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")

# === ML Defaults ===
FORECAST_HORIZON_DAYS: int = 30
MIN_TRAINING_DAYS: int = 30
SEASONALITY_PERIOD: int = 7

# === Optimization ===
DEFAULT_BUDGET_CAP: float = 5000.0
SPOT_RELIABILITY: bool = False

# === Supported Services ===
SUPPORTED_SERVICES: list[str] = [
    "ec2",
    "rds",
    "lambda",
    "s3",
    "ebs",
    "nat_gateway",
    "alb",
    "nlb",
]


# === Instance type specs ===
class InstanceSpec(NamedTuple):
    """Hardware specification for an EC2 instance type."""
    vcpus: int
    memory_gb: float


INSTANCE_SPECS: dict[str, InstanceSpec] = {
    "t3.micro": InstanceSpec(2, 1.0),
    "t3.small": InstanceSpec(2, 2.0),
    "t3.medium": InstanceSpec(2, 4.0),
    "t3.large": InstanceSpec(2, 8.0),
    "t3.xlarge": InstanceSpec(4, 16.0),
    "t3.2xlarge": InstanceSpec(8, 32.0),
    "m5.large": InstanceSpec(2, 8.0),
    "m5.xlarge": InstanceSpec(4, 16.0),
    "m5.2xlarge": InstanceSpec(8, 32.0),
    "m5.4xlarge": InstanceSpec(16, 64.0),
    "t4g.micro": InstanceSpec(2, 1.0),
    "t4g.small": InstanceSpec(2, 2.0),
    "t4g.medium": InstanceSpec(2, 4.0),
    "r5.large": InstanceSpec(2, 16.0),
    "r5.xlarge": InstanceSpec(4, 32.0),
    "c5.large": InstanceSpec(2, 4.0),
    "c5.xlarge": InstanceSpec(4, 8.0),
    "c5.2xlarge": InstanceSpec(8, 16.0),
}

# === AWS full service name → short DB name ===
SERVICE_NAME_MAP: dict[str, str] = {
    "Amazon Elastic Compute Cloud - Compute": "EC2",
    "EC2 - Other": "EC2-Other",
    "Amazon Relational Database Service": "RDS",
    "Amazon Simple Storage Service": "S3",
    "AWS Lambda": "Lambda",
    "Amazon Elastic Block Store": "EBS",
    "Amazon DynamoDB": "DynamoDB",
    "Amazon ElastiCache": "ElastiCache",
    "Amazon Elastic Container Service": "ECS",
    "Amazon Elastic Load Balancing": "ELB",
    "Amazon Virtual Private Cloud": "VPC",
    "AmazonCloudWatch": "CloudWatch",
    "AWS Data Transfer": "DataTransfer",
    "Amazon API Gateway": "APIGateway",
    "AWS Key Management Service": "KMS",
    "AWS CloudFormation": "CloudFormation",
    "AWS CloudShell": "CloudShell",
    "AWS Cost Explorer": "CostExplorer",
    "Amazon Simple Notification Service": "SNS",
    "Amazon Simple Queue Service": "SQS",
    "AWS Glue": "Glue",
    "AWS Secrets Manager": "SecretsManager",
    "AWS Service Catalog": "ServiceCatalog",
    "Amazon Location Service": "LocationService",
    "Tax": "Tax",
}


def setup_logging(level: str = "INFO") -> None:
    """Configure project-wide logging.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
