"""
AWS Pricing API Collector
Fetches pricing information for EC2, S3, Lambda, and RDS
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional

from .config import AWSConfig, DATA_DIR
from .date_utils import get_month_key


class PricingCollector:
    """Collects pricing data from AWS Pricing API"""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize Pricing Collector
        
        Args:
            config: AWSConfig instance with Pricing client
        """
        self.config = config
        self.pricing = config.pricing
        self.account_id = config.account_id
        self.session = config.session
    
    def _get_location_name(self, region: str) -> str:
        """Convert region code to Pricing API location name"""
        location_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'EU (Ireland)',
            'eu-west-2': 'EU (London)',
            'eu-west-3': 'EU (Paris)',
            'eu-central-1': 'EU (Frankfurt)',
            'eu-north-1': 'EU (Stockholm)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-southeast-3': 'Asia Pacific (Jakarta)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-northeast-3': 'Asia Pacific (Osaka)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'ap-south-2': 'Asia Pacific (Hyderabad)',
            'ap-east-1': 'Asia Pacific (Hong Kong)',
            'ca-central-1': 'Canada (Central)',
            'sa-east-1': 'South America (Sao Paulo)',
            'af-south-1': 'Africa (Cape Town)',
            'me-south-1': 'Middle East (Bahrain)',
            'me-central-1': 'Middle East (UAE)',
            'il-central-1': 'Israel (Tel Aviv)',
        }
        # If region not in map, try to construct from region code
        if region not in location_map:
            # Try common patterns
            if region.startswith('us-'):
                return f'US ({region})'
            elif region.startswith('eu-'):
                return f'EU ({region})'
            elif region.startswith('ap-'):
                return f'Asia Pacific ({region})'
            elif region.startswith('sa-'):
                return f'South America ({region})'
            elif region.startswith('ca-'):
                return f'Canada ({region})'
            elif region.startswith('af-'):
                return f'Africa ({region})'
            elif region.startswith('me-'):
                return f'Middle East ({region})'
            else:
                return region
        return location_map.get(region, region)
    
    def get_ec2_price(self, instance_type: str, region: str = 'us-east-1', operating_system: str = 'Linux', pricing_type: str = 'OnDemand') -> Optional[Dict]:
        """
        Get EC2 price for instance type (On-Demand or Spot)
        
        Args:
            instance_type: EC2 instance type (e.g., 't3.micro')
            region: AWS region
            operating_system: Operating system (Linux, Windows, etc.)
            pricing_type: 'OnDemand' or 'Spot'
        
        Returns:
            Dictionary with pricing info or None
        """
        location = self._get_location_name(region)
        
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonEC2'},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': operating_system},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
        ]
        
        if pricing_type == 'OnDemand':
            filters.append({'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'})
        elif pricing_type == 'Spot':
            # Spot instances don't have capacitystatus filter
            pass
        
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters,
                MaxResults=10  # Increased for Spot pricing which may have multiple options
            )
            
            if response.get('PriceList'):
                import json as json_lib
                # For Spot, we might get multiple products, get the first one
                product = json_lib.loads(response['PriceList'][0])
                return self._extract_ec2_pricing(product, instance_type, region, pricing_type)
            
            return None
        except Exception as e:
            print(f"[WARN] Failed to get EC2 {pricing_type} price for {instance_type} in {region}: {e}")
            return None
    
    def get_spot_price(self, instance_type: str, region: str, operating_system: str = 'Linux') -> Optional[Dict]:
        """
        Get EC2 Spot price using EC2 API (more accurate than Pricing API estimate)
        
        Args:
            instance_type: EC2 instance type
            region: AWS region
            operating_system: Operating system (Linux/Unix, Windows, etc.)
        
        Returns:
            Dictionary with Spot pricing or None
        """
        try:
            ec2 = self.session.client('ec2', region_name=region)
            
            # Map OS to product description
            product_descriptions = {
                'Linux': 'Linux/UNIX',
                'Windows': 'Windows',
            }
            product_desc = product_descriptions.get(operating_system, 'Linux/UNIX')
            
            response = ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=[product_desc],
                MaxResults=1
                # Omit StartTime to get most recent prices
            )
            
            price_history = response.get('SpotPriceHistory', [])
            if price_history:
                spot_price = float(price_history[0]['SpotPrice'])
                return {
                    'instance_type': instance_type,
                    'region': region,
                    'hourly_price_usd': spot_price,
                    'pricing_type': 'Spot',
                    'availability_zone': price_history[0].get('AvailabilityZone', ''),
                    'timestamp': price_history[0].get('Timestamp', '').isoformat() if price_history[0].get('Timestamp') else '',
                }
            
            return None
        except Exception as e:
            print(f"[WARN] Failed to get Spot price for {instance_type} in {region}: {e}")
            return None
    
    def _extract_ec2_pricing(self, product: Dict, instance_type: str, region: str, pricing_type: str = 'OnDemand') -> Dict:
        """Extract pricing from EC2 product JSON"""
        try:
            terms = product.get('terms', {})
            
            hourly_price = None
            if pricing_type == 'OnDemand':
                on_demand = terms.get('OnDemand', {})
                for term_key, term_value in on_demand.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price_per_unit = dim_value.get('pricePerUnit', {})
                        if 'USD' in price_per_unit:
                            hourly_price = float(price_per_unit['USD'])
                            break
                    if hourly_price:
                        break
            elif pricing_type == 'Spot':
                # Spot pricing is in SpotPriceHistory, but Pricing API returns it differently
                # Try to get from OnDemand and apply typical discount (or fetch from EC2 Spot API)
                on_demand = terms.get('OnDemand', {})
                for term_key, term_value in on_demand.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price_per_unit = dim_value.get('pricePerUnit', {})
                        if 'USD' in price_per_unit:
                            # Spot is typically 50-90% of On-Demand, use 70% as estimate
                            # Actual Spot prices vary, but this gives a baseline
                            hourly_price = float(price_per_unit['USD']) * 0.7
                            break
                    if hourly_price:
                        break
            
            return {
                'instance_type': instance_type,
                'region': region,
                'hourly_price_usd': hourly_price,
                'pricing_type': pricing_type,
                'product_attributes': product.get('product', {}).get('attributes', {})
            }
        except Exception as e:
            print(f"[WARN] Failed to extract pricing: {e}")
            return {}
    
    def get_reserved_price(self, instance_type: str, region: str = 'us-east-1', term: str = '1yr') -> Optional[Dict]:
        """
        Get EC2 Reserved Instance price
        
        Args:
            instance_type: EC2 instance type
            region: AWS region
            term: Reservation term ('1yr' or '3yr')
            payment_option: Payment option ('No Upfront', 'Partial Upfront', 'All Upfront')
        
        Returns:
            Dictionary with Reserved pricing or None
        """
        location = self._get_location_name(region)
        term_years = '1' if term == '1yr' else '3'
        
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonEC2'},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            {'Type': 'TERM_MATCH', 'Field': 'termLength', 'Value': f'{term_years}yr'},
        ]
        
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters,
                MaxResults=10
            )
            
            reserved_prices = []
            for price_item in response.get('PriceList', []):
                import json as json_lib
                product = json_lib.loads(price_item)
                terms = product.get('terms', {}).get('Reserved', {})
                
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price_per_unit = dim_value.get('pricePerUnit', {})
                        if 'USD' in price_per_unit:
                            reserved_prices.append({
                                'instance_type': instance_type,
                                'region': region,
                                'term': term,
                                'price_usd': float(price_per_unit['USD']),
                                'unit': dim_value.get('unit', ''),
                                'description': dim_value.get('description', '')
                            })
            
            return reserved_prices[0] if reserved_prices else None
        except Exception as e:
            print(f"[WARN] Failed to get Reserved price for {instance_type}: {e}")
            return None
    
    def get_s3_price(self, storage_class: str = 'Standard') -> Optional[Dict]:
        """
        Get S3 storage price
        
        Args:
            storage_class: Storage class (Standard, Standard-IA, Glacier, etc.)
        
        Returns:
            Dictionary with S3 pricing or None
        """
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonS3'},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
            {'Type': 'TERM_MATCH', 'Field': 'storageClass', 'Value': storage_class},
        ]
        
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonS3',
                Filters=filters,
                MaxResults=1
            )
            
            if response.get('PriceList'):
                import json as json_lib
                product = json_lib.loads(response['PriceList'][0])
                return self._extract_s3_pricing(product, storage_class)
            
            return None
        except Exception as e:
            print(f"[WARN] Failed to get S3 price: {e}")
            return None
    
    def _extract_s3_pricing(self, product: Dict, storage_class: str) -> Dict:
        """Extract pricing from S3 product JSON"""
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            price_per_gb = None
            
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get('pricePerUnit', {})
                    if 'USD' in price_per_unit:
                        price_per_gb = float(price_per_unit['USD'])
                        break
                if price_per_gb:
                    break
            
            return {
                'storage_class': storage_class,
                'price_per_gb_usd': price_per_gb
            }
        except Exception as e:
            print(f"[WARN] Failed to extract S3 pricing: {e}")
            return {}
    
    def get_lambda_price(self, region: str = 'us-east-1') -> Optional[Dict]:
        """
        Get Lambda pricing
        
        Args:
            region: AWS region
        
        Returns:
            Dictionary with Lambda pricing or None
        """
        location = self._get_location_name(region)
        
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AWSLambda'},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
        ]
        
        try:
            response = self.pricing.get_products(
                ServiceCode='AWSLambda',
                Filters=filters,
                MaxResults=10
            )
            
            pricing_info = {}
            for price_item in response.get('PriceList', []):
                import json as json_lib
                product = json_lib.loads(price_item)
                attributes = product.get('product', {}).get('attributes', {})
                
                # Extract request and compute pricing
                group = attributes.get('group', '')
                if 'Request' in group:
                    pricing_info['requests_per_million'] = self._extract_price(price_item)
                elif 'Compute' in group:
                    pricing_info['compute_per_gb_second'] = self._extract_price(price_item)
            
            return pricing_info if pricing_info else None
        except Exception as e:
            print(f"[WARN] Failed to get Lambda price: {e}")
            return None
    
    def _extract_price(self, price_item: str) -> Optional[float]:
        """Extract price value from price item JSON"""
        try:
            import json as json_lib
            product = json_lib.loads(price_item)
            terms = product.get('terms', {}).get('OnDemand', {})
            
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get('pricePerUnit', {})
                    if 'USD' in price_per_unit:
                        return float(price_per_unit['USD'])
            
            return None
        except Exception:
            return None
    
    def get_rds_price(self, instance_class: str, engine: str = 'mysql', region: str = 'us-east-1') -> Optional[Dict]:
        """
        Get RDS pricing
        
        Args:
            instance_class: RDS instance class (e.g., 'db.t3.micro')
            engine: Database engine (mysql, postgresql, etc.)
            region: AWS region
        
        Returns:
            Dictionary with RDS pricing or None
        """
        location = self._get_location_name(region)
        
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'ServiceCode', 'Value': 'AmazonRDS'},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_class},
            {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
        ]
        
        try:
            response = self.pricing.get_products(
                ServiceCode='AmazonRDS',
                Filters=filters,
                MaxResults=1
            )
            
            if response.get('PriceList'):
                import json as json_lib
                product = json_lib.loads(response['PriceList'][0])
                return self._extract_rds_pricing(product, instance_class, engine, region)
            
            return None
        except Exception as e:
            print(f"[WARN] Failed to get RDS price: {e}")
            return None
    
    def _extract_rds_pricing(self, product: Dict, instance_class: str, engine: str, region: str) -> Dict:
        """Extract pricing from RDS product JSON"""
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            hourly_price = None
            
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get('pricePerUnit', {})
                    if 'USD' in price_per_unit:
                        hourly_price = float(price_per_unit['USD'])
                        break
                if hourly_price:
                    break
            
            return {
                'instance_class': instance_class,
                'engine': engine,
                'region': region,
                'hourly_price_usd': hourly_price
            }
        except Exception as e:
            print(f"[WARN] Failed to extract RDS pricing: {e}")
            return {}
    
    def collect_month_snapshot(self, month_key: str, instance_types: List[str] = None, regions: List[str] = None):
        """
        Collect pricing snapshot for a month
        
        Args:
            month_key: Month key (YYYY-MM)
            instance_types: List of instance types to fetch (fetches common ones if None)
            regions: List of regions to fetch (fetches all if None)
        """
        if instance_types is None:
            # Common instance types
            instance_types = [
                't3.micro', 't3.small', 't3.medium', 't3.large',
                'm5.large', 'm5.xlarge', 'm5.2xlarge',
                'c5.large', 'c5.xlarge',
            ]
        
        if regions is None:
            # Get all regions from config
            from .config import get_config
            config = get_config()
            regions = config.regions
        
        print(f"  Collecting pricing snapshot for {month_key}...")
        print(f"    Regions: {len(regions)}, Instance types: {len(instance_types)}")
        
        pricing_data = {
            'account_id': self.account_id,
            'month': month_key,
            'ec2_on_demand': {},
            'ec2_reserved_1yr': {},
            'ec2_reserved_3yr': {},
            'ec2_spot': {},
            's3': {},
            'lambda': {},
            'rds': {},
        }
        
        # Collect EC2 on-demand prices for all regions
        print(f"    → EC2 on-demand prices ({len(instance_types)} types × {len(regions)} regions)...", end="", flush=True)
        on_demand_count = 0
        for instance_type in instance_types:
            for region in regions:
                price = self.get_ec2_price(instance_type, region=region, pricing_type='OnDemand')
                if price:
                    key = f"{instance_type}_{region}"
                    pricing_data['ec2_on_demand'][key] = price
                    on_demand_count += 1
        print(f" ✓ ({on_demand_count} prices)")
        
        # Collect EC2 reserved prices (1yr) for all regions
        reserved_types = instance_types[:5]  # Limit to avoid too many API calls
        print(f"    → EC2 reserved 1yr prices ({len(reserved_types)} types × {len(regions)} regions)...", end="", flush=True)
        reserved_1yr_count = 0
        for instance_type in reserved_types:
            for region in regions:
                reserved_1yr = self.get_reserved_price(instance_type, region=region, term='1yr')
                if reserved_1yr:
                    key = f"{instance_type}_{region}_1yr"
                    pricing_data['ec2_reserved_1yr'][key] = reserved_1yr
                    reserved_1yr_count += 1
        print(f" ✓ ({reserved_1yr_count} prices)")
        
        # Collect EC2 reserved prices (3yr) for all regions
        print(f"    → EC2 reserved 3yr prices ({len(reserved_types)} types × {len(regions)} regions)...", end="", flush=True)
        reserved_3yr_count = 0
        for instance_type in reserved_types:
            for region in regions:
                reserved_3yr = self.get_reserved_price(instance_type, region=region, term='3yr')
                if reserved_3yr:
                    key = f"{instance_type}_{region}_3yr"
                    pricing_data['ec2_reserved_3yr'][key] = reserved_3yr
                    reserved_3yr_count += 1
        print(f" ✓ ({reserved_3yr_count} prices)")
        
        # Collect EC2 Spot prices for all regions (using EC2 API for accuracy)
        print(f"    → EC2 spot prices ({len(instance_types)} types × {len(regions)} regions)...", end="", flush=True)
        spot_count = 0
        for instance_type in instance_types:
            for region in regions:
                spot_price = self.get_spot_price(instance_type, region=region)
                if spot_price:
                    key = f"{instance_type}_{region}"
                    pricing_data['ec2_spot'][key] = spot_price
                    spot_count += 1
        print(f" ✓ ({spot_count} prices)")
        
        # Collect S3 prices
        print(f"    → S3 storage prices...", end="", flush=True)
        for storage_class in ['Standard', 'Standard-IA', 'Glacier']:
            s3_price = self.get_s3_price(storage_class)
            if s3_price:
                pricing_data['s3'][storage_class] = s3_price
        print(f" ✓ ({len(pricing_data['s3'])} prices)")
        
        # Collect Lambda prices
        print(f"    → Lambda pricing...", end="", flush=True)
        lambda_price = self.get_lambda_price()
        if lambda_price:
            pricing_data['lambda'] = lambda_price
        print(" ✓")
        
        # Collect RDS prices (sample)
        print(f"    → RDS pricing...", end="", flush=True)
        for instance_class in ['db.t3.micro', 'db.t3.small']:
            rds_price = self.get_rds_price(instance_class)
            if rds_price:
                pricing_data['rds'][instance_class] = rds_price
        print(f" ✓ ({len(pricing_data['rds'])} prices)")
        
        # Save to CSV - flatten the pricing data
        pricing_dir = DATA_DIR / "pricing"
        pricing_dir.mkdir(parents=True, exist_ok=True)
        
        consolidated_file = pricing_dir / "pricing_consolidated.csv"
        rows = []
        
        # EC2 On-Demand prices
        for key, price_info in pricing_data.get('ec2_on_demand', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'EC2',
                'pricing_type': 'On-Demand',
                'instance_type': price_info.get('instance_type', ''),
                'region': price_info.get('region', ''),
                'hourly_price_usd': float(price_info.get('hourly_price_usd', 0)) if price_info.get('hourly_price_usd') else 0.0,
                'product_family': price_info.get('product_attributes', {}).get('productFamily', ''),
            })
        
        # EC2 Reserved 1yr prices
        for key, price_info in pricing_data.get('ec2_reserved_1yr', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'EC2',
                'pricing_type': 'Reserved-1yr',
                'instance_type': price_info.get('instance_type', ''),
                'region': price_info.get('region', ''),
                'term': '1yr',
                'price_usd': float(price_info.get('price_usd', 0)) if price_info.get('price_usd') else 0.0,
                'unit': price_info.get('unit', ''),
            })
        
        # EC2 Reserved 3yr prices
        for key, price_info in pricing_data.get('ec2_reserved_3yr', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'EC2',
                'pricing_type': 'Reserved-3yr',
                'instance_type': price_info.get('instance_type', ''),
                'region': price_info.get('region', ''),
                'term': '3yr',
                'price_usd': float(price_info.get('price_usd', 0)) if price_info.get('price_usd') else 0.0,
                'unit': price_info.get('unit', ''),
            })
        
        # EC2 Spot prices
        for key, price_info in pricing_data.get('ec2_spot', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'EC2',
                'pricing_type': 'Spot',
                'instance_type': price_info.get('instance_type', ''),
                'region': price_info.get('region', ''),
                'hourly_price_usd': float(price_info.get('hourly_price_usd', 0)) if price_info.get('hourly_price_usd') else 0.0,
            })
        
        # S3 prices
        for storage_class, price_info in pricing_data.get('s3', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'S3',
                'pricing_type': 'Storage',
                'storage_class': storage_class,
                'price_per_gb_usd': float(price_info.get('price_per_gb_usd', 0)) if price_info.get('price_per_gb_usd') else 0.0,
            })
        
        # Lambda prices
        lambda_prices = pricing_data.get('lambda', {})
        if lambda_prices:
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'Lambda',
                'pricing_type': 'Requests',
                'requests_per_million_usd': float(lambda_prices.get('requests_per_million', 0)) if lambda_prices.get('requests_per_million') else 0.0,
                'compute_per_gb_second_usd': float(lambda_prices.get('compute_per_gb_second', 0)) if lambda_prices.get('compute_per_gb_second') else 0.0,
            })
        
        # RDS prices
        for instance_class, price_info in pricing_data.get('rds', {}).items():
            rows.append({
                'account_id': self.account_id,
                'month': month_key,
                'service': 'RDS',
                'pricing_type': 'On-Demand',
                'instance_class': instance_class,
                'engine': price_info.get('engine', ''),
                'region': price_info.get('region', ''),
                'hourly_price_usd': float(price_info.get('hourly_price_usd', 0)) if price_info.get('hourly_price_usd') else 0.0,
            })
        
        # Write CSV (append to consolidated file)
        if rows:
            # Get all possible fieldnames from all rows (union of all keys)
            all_fieldnames = set()
            for row in rows:
                all_fieldnames.update(row.keys())
            
            # Define standard fieldnames order
            standard_fields = [
                'account_id', 'month', 'service', 'pricing_type',
                'instance_type', 'instance_class', 'region', 'term',
                'hourly_price_usd', 'price_usd', 'price_per_gb_usd',
                'unit', 'storage_class', 'engine',
                'requests_per_million_usd', 'compute_per_gb_second_usd',
                'product_family', 'description'
            ]
            
            # Use standard fields that exist in data, plus any extras
            fieldnames = [f for f in standard_fields if f in all_fieldnames]
            extra_fields = sorted(all_fieldnames - set(fieldnames))
            fieldnames.extend(extra_fields)
            
            # Ensure all rows have all fieldnames (fill missing with empty string)
            normalized_rows = []
            for row in rows:
                normalized_row = {field: row.get(field, '') for field in fieldnames}
                normalized_rows.append(normalized_row)
            
            # Check if consolidated file exists
            file_exists = consolidated_file.exists()
            
            # Append to consolidated file
            with open(consolidated_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(normalized_rows)
            
            print(f"  ✓ Saved {len(rows)} pricing records → pricing_consolidated.csv")
        else:
            # Create empty CSV if file doesn't exist
            if not consolidated_file.exists():
                consolidated_file.parent.mkdir(parents=True, exist_ok=True)
                with open(consolidated_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['account_id', 'month', 'service', 'note'])
                    writer.writerow([self.account_id, month_key, 'N/A', 'No pricing data'])
                print(f"  ✓ Created empty pricing file pricing_consolidated.csv")

