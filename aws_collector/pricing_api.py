"""
AWS Pricing API Module
Fetches current pricing information for AWS services
"""
from typing import Dict, List, Optional


class PricingAPI:
    """AWS Pricing API client"""
    
    def __init__(self, session, region: str = "us-east-1"):
        """
        Initialize Pricing API client
        
        Args:
            session: boto3 session
            region: AWS region (Pricing API is only available in us-east-1 and ap-south-1)
        """
        self.session = session
        self.region = region
        self.pricing = session.client("pricing", region_name=region)
    
    def get_ec2_instance_pricing(
        self,
        instance_type: str,
        operating_system: str = "Linux",
        tenancy: str = "Shared",
        region: str = "us-east-1"
    ) -> Optional[Dict]:
        """
        Get pricing for a specific EC2 instance type
        
        Args:
            instance_type: EC2 instance type (e.g., "t3.micro")
            operating_system: Operating system (Linux, Windows, etc.)
            tenancy: Tenancy type (Shared, Dedicated, Host)
            region: AWS region
        
        Returns:
            Dictionary with pricing information or None if not found
        """
        try:
            filters = [
                {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonEC2"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": self._get_location_name(region)},
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": tenancy},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ]
            
            response = self.pricing.get_products(
                ServiceCode="AmazonEC2",
                Filters=filters,
                MaxResults=1
            )
            
            products = response.get("PriceList", [])
            if products:
                import json
                product = json.loads(products[0])
                return self._extract_pricing(product)
            
            return None
        except Exception as e:
            print(f"[WARN] Failed to get pricing for {instance_type}: {e}")
            return None
    
    def _get_location_name(self, region: str) -> str:
        """Convert region code to location name for Pricing API"""
        location_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "EU (Ireland)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
        }
        return location_map.get(region, region)
    
    def _extract_pricing(self, product: Dict) -> Dict:
        """Extract pricing information from product JSON"""
        try:
            terms = product.get("terms", {})
            on_demand = terms.get("OnDemand", {})
            
            price_info = {}
            for term_key, term_value in on_demand.items():
                price_dimensions = term_value.get("priceDimensions", {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get("pricePerUnit", {})
                    if "USD" in price_per_unit:
                        price_info["on_demand_hourly"] = float(price_per_unit["USD"])
                        break
            
            return {
                "product": product.get("product", {}).get("attributes", {}),
                "pricing": price_info
            }
        except Exception as e:
            print(f"[WARN] Failed to extract pricing: {e}")
            return {}
    
    def get_current_ec2_prices(self, instance_types: List[str], region: str = "us-east-1") -> Dict[str, Dict]:
        """
        Get current prices for multiple EC2 instance types
        
        Args:
            instance_types: List of instance types to query
            region: AWS region
        
        Returns:
            Dictionary mapping instance_type to pricing information
        """
        prices = {}
        for instance_type in instance_types:
            pricing = self.get_ec2_instance_pricing(instance_type, region=region)
            if pricing:
                prices[instance_type] = pricing
        
        return prices

