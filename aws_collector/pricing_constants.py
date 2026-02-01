"""
pricing_constants.py — Constants for AWS Pricing API lookups.

Region-to-location mappings, default instance types, and pricing multipliers
used by PricingCollector.

Part of the Smart Cloud Optimizer graduation project.
"""

# Multiplier applied to On-Demand price to estimate Spot pricing
# when actual Spot price is unavailable from the EC2 API.
SPOT_DISCOUNT_FACTOR: float = 0.7

# Region code to AWS Pricing API location name mapping.
REGION_LOCATION_MAP: dict[str, str] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-west-3": "EU (Paris)",
    "eu-central-1": "EU (Frankfurt)",
    "eu-north-1": "EU (Stockholm)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-southeast-3": "Asia Pacific (Jakarta)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-northeast-3": "Asia Pacific (Osaka)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-south-2": "Asia Pacific (Hyderabad)",
    "ap-east-1": "Asia Pacific (Hong Kong)",
    "ca-central-1": "Canada (Central)",
    "sa-east-1": "South America (Sao Paulo)",
    "af-south-1": "Africa (Cape Town)",
    "me-south-1": "Middle East (Bahrain)",
    "me-central-1": "Middle East (UAE)",
    "il-central-1": "Israel (Tel Aviv)",
}

# Region prefix to human-readable area name for unknown regions.
REGION_PREFIX_MAP: dict[str, str] = {
    "us-": "US",
    "eu-": "EU",
    "ap-": "Asia Pacific",
    "sa-": "South America",
    "ca-": "Canada",
    "af-": "Africa",
    "me-": "Middle East",
}

# Default EC2 instance types to collect pricing for.
DEFAULT_INSTANCE_TYPES: list[str] = [
    "t3.micro",
    "t3.small",
    "t3.medium",
    "t3.large",
    "m5.large",
    "m5.xlarge",
    "m5.2xlarge",
    "c5.large",
    "c5.xlarge",
]

# Instance types for which to collect Reserved pricing.
# Subset of DEFAULT_INSTANCE_TYPES to limit API call volume.
RESERVED_INSTANCE_TYPES_LIMIT: int = 5

# Default S3 storage classes to collect pricing for.
DEFAULT_S3_STORAGE_CLASSES: list[str] = [
    "Standard",
    "Standard-IA",
    "Glacier",
]

# Default RDS instance classes to sample pricing for.
DEFAULT_RDS_INSTANCE_CLASSES: list[str] = [
    "db.t3.micro",
    "db.t3.small",
]

# Standard field ordering for the consolidated pricing CSV.
PRICING_CSV_FIELDS: list[str] = [
    "account_id",
    "month",
    "service",
    "pricing_type",
    "instance_type",
    "instance_class",
    "region",
    "term",
    "hourly_price_usd",
    "price_usd",
    "price_per_gb_usd",
    "unit",
    "storage_class",
    "engine",
    "requests_per_million_usd",
    "compute_per_gb_second_usd",
    "product_family",
    "description",
]
