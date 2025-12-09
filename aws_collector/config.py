"""
AWS Client Configuration
Creates boto3 clients for all AWS services needed for data collection
"""
import boto3
from pathlib import Path
from typing import Optional

# Base directory paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "cost").mkdir(exist_ok=True)
(DATA_DIR / "metrics").mkdir(exist_ok=True)
(DATA_DIR / "pricing").mkdir(exist_ok=True)
(DATA_DIR / "inventory").mkdir(exist_ok=True)

for service in ["ec2", "ebs", "lambda", "rds", "s3"]:
    (DATA_DIR / "metrics" / service).mkdir(exist_ok=True)


class AWSConfig:
    """AWS client configuration and initialization"""
    
    def __init__(self, session: Optional[boto3.Session] = None):
        """
        Initialize AWS clients
        
        Args:
            session: boto3 Session object (creates default if None)
        """
        self.session = session or boto3.Session()
        
        # Initialize clients
        self.ce = self.session.client('ce')  # Cost Explorer
        self.ec2 = self.session.client('ec2')  # EC2
        self.cloudwatch = self.session.client('cloudwatch')  # CloudWatch
        self.pricing = self.session.client('pricing', region_name='us-east-1')  # Pricing API (only in us-east-1)
        self.rds = None  # Will be created per region
        self.lambda_client = None  # Will be created per region
        self.s3 = self.session.client('s3')  # S3
        
        # Get account ID
        sts = self.session.client('sts')
        identity = sts.get_caller_identity()
        self.account_id = identity['Account']
        
        # Get available regions
        self.regions = self._get_regions()
    
    def _get_regions(self) -> list:
        """Get list of available AWS regions"""
        try:
            ec2_global = self.session.client('ec2')
            response = ec2_global.describe_regions(AllRegions=False)
            return [r['RegionName'] for r in response['Regions']]
        except Exception as e:
            print(f"[WARN] Failed to get regions: {e}")
            return ['us-east-1']  # Default fallback
    
    def get_rds_client(self, region: str):
        """Get RDS client for specific region"""
        return self.session.client('rds', region_name=region)
    
    def get_lambda_client(self, region: str):
        """Get Lambda client for specific region"""
        return self.session.client('lambda', region_name=region)
    
    def get_cloudwatch_client(self, region: str):
        """Get CloudWatch client for specific region"""
        return self.session.client('cloudwatch', region_name=region)
    
    def get_ec2_client(self, region: str):
        """Get EC2 client for specific region"""
        return self.session.client('ec2', region_name=region)


# Global config instance (can be initialized later)
_config: Optional[AWSConfig] = None


def get_config() -> AWSConfig:
    """Get or create global AWS config instance"""
    global _config
    if _config is None:
        _config = AWSConfig()
    return _config


def init_config(session: Optional[boto3.Session] = None) -> AWSConfig:
    """Initialize global config with optional session"""
    global _config
    _config = AWSConfig(session)
    return _config
