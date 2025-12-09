"""
Main Collector Service
Orchestrates all collection modules
"""
import boto3
from typing import List, Dict
from pathlib import Path

from .config import Config
from .ec2_inventory import EC2Inventory
from .cost_explorer import CostExplorer
from .cloudwatch_metrics import CloudWatchMetrics
from .pricing_api import PricingAPI


class CollectorService:
    """Main service that orchestrates AWS data collection"""
    
    def __init__(self, session=None, account_id: str = None, regions: List[str] = None):
        """
        Initialize the collector service
        
        Args:
            session: boto3 session (creates default if None)
            account_id: AWS account ID (fetches automatically if None)
            regions: List of regions to scan (fetches all if None)
        """
        self.session = session or boto3.Session()
        
        # Get account ID
        if account_id is None:
            sts = self.session.client("sts")
            identity = sts.get_caller_identity()
            self.account_id = identity["Account"]
        else:
            self.account_id = account_id
        
        # Get regions
        if regions is None:
            ec2_global = self.session.client("ec2")
            regions_resp = ec2_global.describe_regions(AllRegions=False)
            self.regions = [r["RegionName"] for r in regions_resp["Regions"]]
        else:
            self.regions = regions
        
        print(f"Using AWS Account: {self.account_id}")
        print(f"Regions: {self.regions}")
        
        # Initialize modules
        self.ec2_inventory = EC2Inventory(self.session, self.account_id, self.regions)
        self.cost_explorer = CostExplorer(self.session, self.account_id)
        self.cloudwatch_metrics = CloudWatchMetrics(self.session)
        self.pricing_api = PricingAPI(self.session)
    
    def collect_all(self) -> Dict[str, Path]:
        """
        Collect all AWS data
        
        Returns:
            Dictionary mapping data type to CSV file path
        """
        results = {}
        
        print("\n=== Starting AWS Data Collection ===\n")
        
        # Collect EC2 inventory
        print("1. Collecting EC2 inventory...")
        results["ec2_instances"] = self.ec2_inventory.export_instances()
        
        # Collect cost data
        print("\n2. Collecting cost data...")
        results["cost_by_service"] = self.cost_explorer.export_daily_cost_by_service()
        results["cost_by_service_region"] = self.cost_explorer.export_daily_cost_by_service_region()
        results["cost_by_tag_environment"] = self.cost_explorer.export_daily_cost_by_tag_environment()
        
        print("\n=== Collection Complete ===\n")
        print("Generated CSV files:")
        for data_type, csv_path in results.items():
            print(f"  - {data_type}: {csv_path}")
        
        return results
    
    def collect_ec2_only(self) -> Path:
        """Collect only EC2 inventory"""
        return self.ec2_inventory.export_instances()
    
    def collect_costs_only(self) -> Dict[str, Path]:
        """Collect only cost data"""
        results = {}
        results["cost_by_service"] = self.cost_explorer.export_daily_cost_by_service()
        results["cost_by_service_region"] = self.cost_explorer.export_daily_cost_by_service_region()
        results["cost_by_tag_environment"] = self.cost_explorer.export_daily_cost_by_tag_environment()
        return results
    
    def get_pricing(self, instance_types: List[str], region: str = "us-east-1") -> Dict:
        """Get pricing for EC2 instance types"""
        return self.pricing_api.get_current_ec2_prices(instance_types, region)

