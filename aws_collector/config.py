"""
config.py — AWS boto3 client configuration and session management.

Creates and manages boto3 clients for all AWS services used by the
data collection pipeline. Project-level settings live in the root config.py.

Part of the Smart Cloud Optimizer graduation project.
"""
import logging
from pathlib import Path
from typing import List, Optional

import boto3

logger = logging.getLogger(__name__)

# Base directory paths
BASE_DIR: Path = Path(__file__).parent.parent
DATA_DIR: Path = BASE_DIR / "data" / "real"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
for _subdir in ("cost", "metrics", "pricing", "inventory"):
    (DATA_DIR / _subdir).mkdir(exist_ok=True)

for _service in ("ec2", "ebs", "lambda", "rds", "s3", "cloudfront", "nat", "alb", "nlb"):
    (DATA_DIR / "metrics" / _service).mkdir(exist_ok=True)


class AWSConfig:
    """AWS client configuration and initialization."""

    def __init__(self, session: Optional[boto3.Session] = None) -> None:
        """Initialize AWS clients.

        Args:
            session: boto3 Session object. Creates a default session if *None*.
        """
        self.session = session or boto3.Session()

        # Service clients shared across the pipeline
        self.ce = self.session.client("ce")
        self.ec2 = self.session.client("ec2")
        self.cloudwatch = self.session.client("cloudwatch")
        self.pricing = self.session.client("pricing", region_name="us-east-1")
        self.s3 = self.session.client("s3")

        # Account identity
        sts = self.session.client("sts")
        self.account_id: str = sts.get_caller_identity()["Account"]

        # Available regions
        self.regions: List[str] = self._get_regions()

    def _get_regions(self) -> List[str]:
        """Fetch the list of enabled AWS regions.

        Returns:
            List of region name strings; falls back to ``["us-east-1"]``.
        """
        try:
            ec2_global = self.session.client("ec2")
            response = ec2_global.describe_regions(AllRegions=False)
            return [r["RegionName"] for r in response["Regions"]]
        except Exception as e:
            logger.warning(f"[WARN] Failed to get regions: {e}")
            return ["us-east-1"]

    def get_rds_client(self, region: str):
        """Get RDS client for a specific region."""
        return self.session.client("rds", region_name=region)

    def get_lambda_client(self, region: str):
        """Get Lambda client for a specific region."""
        return self.session.client("lambda", region_name=region)

    def get_cloudwatch_client(self, region: str):
        """Get CloudWatch client for a specific region."""
        return self.session.client("cloudwatch", region_name=region)

    def get_ec2_client(self, region: str):
        """Get EC2 client for a specific region."""
        return self.session.client("ec2", region_name=region)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_config: Optional[AWSConfig] = None


def get_config() -> AWSConfig:
    """Get or create the global AWS config instance."""
    global _config
    if _config is None:
        _config = AWSConfig()
    return _config


def init_config(session: Optional[boto3.Session] = None) -> AWSConfig:
    """Initialize the global config with an optional session.

    Args:
        session: boto3 Session to use. Creates a default if *None*.

    Returns:
        The initialized :class:`AWSConfig` instance.
    """
    global _config
    _config = AWSConfig(session)
    return _config
