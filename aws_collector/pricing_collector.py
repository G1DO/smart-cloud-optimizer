"""
pricing_collector.py — AWS Pricing API collector.

Fetches pricing information for EC2, S3, Lambda, and RDS from the
AWS Pricing API and EC2 Spot Price History API.

Part of the Smart Cloud Optimizer graduation project.
"""
import csv
import json
import logging
from typing import Any, Dict, List, Optional

from .config import AWSConfig, DATA_DIR
from .pricing_constants import (
    DEFAULT_INSTANCE_TYPES,
    DEFAULT_RDS_INSTANCE_CLASSES,
    DEFAULT_S3_STORAGE_CLASSES,
    PRICING_CSV_FIELDS,
    REGION_LOCATION_MAP,
    REGION_PREFIX_MAP,
    RESERVED_INSTANCE_TYPES_LIMIT,
    SPOT_DISCOUNT_FACTOR,
)

logger = logging.getLogger(__name__)


class PricingCollector:
    """Collects pricing data from AWS Pricing API and EC2 Spot API."""

    def __init__(self, config: AWSConfig) -> None:
        """Initialize Pricing Collector.

        Args:
            config: AWSConfig instance with Pricing client.
        """
        self.config = config
        self.pricing = config.pricing
        self.account_id = config.account_id
        self.session = config.session

    # ------------------------------------------------------------------
    # Region helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_location_name(region: str) -> str:
        """Convert AWS region code to Pricing API location name.

        Args:
            region: AWS region code (e.g. ``us-east-1``).

        Returns:
            Human-readable location string used by the Pricing API.
        """
        if region in REGION_LOCATION_MAP:
            return REGION_LOCATION_MAP[region]

        for prefix, area in REGION_PREFIX_MAP.items():
            if region.startswith(prefix):
                return f"{area} ({region})"
        return region

    # ------------------------------------------------------------------
    # EC2 pricing
    # ------------------------------------------------------------------

    def get_ec2_price(
        self,
        instance_type: str,
        region: str = "us-east-1",
        operating_system: str = "Linux",
        pricing_type: str = "OnDemand",
    ) -> Optional[Dict[str, Any]]:
        """Fetch EC2 On-Demand or Spot price from the Pricing API.

        Args:
            instance_type: EC2 instance type (e.g. ``t3.micro``).
            region: AWS region.
            operating_system: OS filter (Linux, Windows, etc.).
            pricing_type: ``OnDemand`` or ``Spot``.

        Returns:
            Pricing dict or ``None`` on failure.
        """
        location = self._get_location_name(region)

        filters = [
            {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonEC2"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
        ]

        if pricing_type == "OnDemand":
            filters.append({"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"})

        try:
            response = self.pricing.get_products(
                ServiceCode="AmazonEC2",
                Filters=filters,
                MaxResults=10,
            )
            if response.get("PriceList"):
                product = json.loads(response["PriceList"][0])
                return self._extract_ec2_pricing(product, instance_type, region, pricing_type)
            return None
        except Exception as e:
            logger.warning(f"Failed to get EC2 {pricing_type} price for {instance_type} in {region}: {e}")
            return None

    def get_spot_price(
        self,
        instance_type: str,
        region: str,
        operating_system: str = "Linux",
    ) -> Optional[Dict[str, Any]]:
        """Fetch EC2 Spot price using the EC2 Spot Price History API.

        This is more accurate than estimating from the Pricing API.

        Args:
            instance_type: EC2 instance type.
            region: AWS region.
            operating_system: OS (Linux or Windows).

        Returns:
            Spot pricing dict or ``None`` if unavailable.
        """
        try:
            ec2 = self.session.client("ec2", region_name=region)
            product_descriptions = {"Linux": "Linux/UNIX", "Windows": "Windows"}
            product_desc = product_descriptions.get(operating_system, "Linux/UNIX")

            response = ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=[product_desc],
                MaxResults=1,
            )

            price_history = response.get("SpotPriceHistory", [])
            if price_history:
                entry = price_history[0]
                return {
                    "instance_type": instance_type,
                    "region": region,
                    "hourly_price_usd": float(entry["SpotPrice"]),
                    "pricing_type": "Spot",
                    "availability_zone": entry.get("AvailabilityZone", ""),
                    "timestamp": entry["Timestamp"].isoformat() if entry.get("Timestamp") else "",
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to get Spot price for {instance_type} in {region}: {e}")
            return None

    def _extract_ec2_pricing(
        self,
        product: Dict[str, Any],
        instance_type: str,
        region: str,
        pricing_type: str = "OnDemand",
    ) -> Dict[str, Any]:
        """Extract hourly price from an EC2 Pricing API product JSON.

        Args:
            product: Parsed product JSON from the Pricing API.
            instance_type: EC2 instance type.
            region: AWS region.
            pricing_type: ``OnDemand`` or ``Spot``.

        Returns:
            Dict with pricing details, or empty dict on parse failure.
        """
        try:
            terms = product.get("terms", {})
            hourly_price = None

            on_demand = terms.get("OnDemand", {})
            for term_value in on_demand.values():
                for dim_value in term_value.get("priceDimensions", {}).values():
                    usd = dim_value.get("pricePerUnit", {}).get("USD")
                    if usd is not None:
                        hourly_price = float(usd)
                        if pricing_type == "Spot":
                            hourly_price *= SPOT_DISCOUNT_FACTOR
                        break
                if hourly_price is not None:
                    break

            return {
                "instance_type": instance_type,
                "region": region,
                "hourly_price_usd": hourly_price,
                "pricing_type": pricing_type,
                "product_attributes": product.get("product", {}).get("attributes", {}),
            }
        except Exception as e:
            logger.warning(f"Failed to extract EC2 pricing: {e}")
            return {}

    def get_reserved_price(
        self,
        instance_type: str,
        region: str = "us-east-1",
        term: str = "1yr",
    ) -> Optional[Dict[str, Any]]:
        """Fetch EC2 Reserved Instance price from the Pricing API.

        Args:
            instance_type: EC2 instance type.
            region: AWS region.
            term: ``1yr`` or ``3yr``.

        Returns:
            Reserved pricing dict or ``None``.
        """
        location = self._get_location_name(region)
        term_years = "1" if term == "1yr" else "3"

        filters = [
            {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonEC2"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "termLength", "Value": f"{term_years}yr"},
        ]

        try:
            response = self.pricing.get_products(
                ServiceCode="AmazonEC2",
                Filters=filters,
                MaxResults=10,
            )

            reserved_prices: List[Dict[str, Any]] = []
            for price_item in response.get("PriceList", []):
                product = json.loads(price_item)
                terms = product.get("terms", {}).get("Reserved", {})
                for term_value in terms.values():
                    for dim_value in term_value.get("priceDimensions", {}).values():
                        usd = dim_value.get("pricePerUnit", {}).get("USD")
                        if usd is not None:
                            reserved_prices.append({
                                "instance_type": instance_type,
                                "region": region,
                                "term": term,
                                "price_usd": float(usd),
                                "unit": dim_value.get("unit", ""),
                                "description": dim_value.get("description", ""),
                            })

            return reserved_prices[0] if reserved_prices else None
        except Exception as e:
            logger.warning(f"Failed to get Reserved price for {instance_type}: {e}")
            return None

    # ------------------------------------------------------------------
    # S3 pricing
    # ------------------------------------------------------------------

    def get_s3_price(self, storage_class: str = "Standard") -> Optional[Dict[str, Any]]:
        """Fetch S3 storage price from the Pricing API.

        Args:
            storage_class: S3 storage class name.

        Returns:
            S3 pricing dict or ``None``.
        """
        filters = [
            {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonS3"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
            {"Type": "TERM_MATCH", "Field": "storageClass", "Value": storage_class},
        ]

        try:
            response = self.pricing.get_products(
                ServiceCode="AmazonS3",
                Filters=filters,
                MaxResults=1,
            )
            if response.get("PriceList"):
                product = json.loads(response["PriceList"][0])
                return self._extract_s3_pricing(product, storage_class)
            return None
        except Exception as e:
            logger.warning(f"Failed to get S3 price: {e}")
            return None

    @staticmethod
    def _extract_s3_pricing(product: Dict[str, Any], storage_class: str) -> Dict[str, Any]:
        """Extract per-GB price from an S3 Pricing API product.

        Args:
            product: Parsed product JSON.
            storage_class: S3 storage class name.

        Returns:
            Dict with ``storage_class`` and ``price_per_gb_usd``.
        """
        try:
            for term_value in product.get("terms", {}).get("OnDemand", {}).values():
                for dim_value in term_value.get("priceDimensions", {}).values():
                    usd = dim_value.get("pricePerUnit", {}).get("USD")
                    if usd is not None:
                        return {"storage_class": storage_class, "price_per_gb_usd": float(usd)}
            return {"storage_class": storage_class, "price_per_gb_usd": None}
        except Exception as e:
            logger.warning(f"Failed to extract S3 pricing: {e}")
            return {}

    # ------------------------------------------------------------------
    # Lambda pricing
    # ------------------------------------------------------------------

    def get_lambda_price(self, region: str = "us-east-1") -> Optional[Dict[str, Any]]:
        """Fetch Lambda pricing (requests + compute) from the Pricing API.

        Args:
            region: AWS region.

        Returns:
            Dict with ``requests_per_million`` and ``compute_per_gb_second``,
            or ``None`` if unavailable.
        """
        location = self._get_location_name(region)

        filters = [
            {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AWSLambda"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
        ]

        try:
            response = self.pricing.get_products(
                ServiceCode="AWSLambda",
                Filters=filters,
                MaxResults=10,
            )

            pricing_info: Dict[str, Any] = {}
            for price_item in response.get("PriceList", []):
                product = json.loads(price_item)
                group = product.get("product", {}).get("attributes", {}).get("group", "")
                if "Request" in group:
                    pricing_info["requests_per_million"] = self._extract_price(price_item)
                elif "Compute" in group:
                    pricing_info["compute_per_gb_second"] = self._extract_price(price_item)

            return pricing_info if pricing_info else None
        except Exception as e:
            logger.warning(f"Failed to get Lambda price: {e}")
            return None

    @staticmethod
    def _extract_price(price_item: str) -> Optional[float]:
        """Extract the USD price from a raw Pricing API JSON string.

        Args:
            price_item: Raw JSON string from PriceList.

        Returns:
            Price as float or ``None``.
        """
        try:
            product = json.loads(price_item)
            for term_value in product.get("terms", {}).get("OnDemand", {}).values():
                for dim_value in term_value.get("priceDimensions", {}).values():
                    usd = dim_value.get("pricePerUnit", {}).get("USD")
                    if usd is not None:
                        return float(usd)
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # RDS pricing
    # ------------------------------------------------------------------

    def get_rds_price(
        self,
        instance_class: str,
        engine: str = "mysql",
        region: str = "us-east-1",
    ) -> Optional[Dict[str, Any]]:
        """Fetch RDS On-Demand pricing from the Pricing API.

        Args:
            instance_class: RDS instance class (e.g. ``db.t3.micro``).
            engine: Database engine.
            region: AWS region.

        Returns:
            RDS pricing dict or ``None``.
        """
        location = self._get_location_name(region)

        filters = [
            {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonRDS"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_class},
            {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": engine},
        ]

        try:
            response = self.pricing.get_products(
                ServiceCode="AmazonRDS",
                Filters=filters,
                MaxResults=1,
            )
            if response.get("PriceList"):
                product = json.loads(response["PriceList"][0])
                return self._extract_rds_pricing(product, instance_class, engine, region)
            return None
        except Exception as e:
            logger.warning(f"Failed to get RDS price: {e}")
            return None

    @staticmethod
    def _extract_rds_pricing(
        product: Dict[str, Any],
        instance_class: str,
        engine: str,
        region: str,
    ) -> Dict[str, Any]:
        """Extract hourly price from an RDS Pricing API product.

        Args:
            product: Parsed product JSON.
            instance_class: RDS instance class.
            engine: Database engine.
            region: AWS region.

        Returns:
            Dict with pricing details.
        """
        try:
            for term_value in product.get("terms", {}).get("OnDemand", {}).values():
                for dim_value in term_value.get("priceDimensions", {}).values():
                    usd = dim_value.get("pricePerUnit", {}).get("USD")
                    if usd is not None:
                        return {
                            "instance_class": instance_class,
                            "engine": engine,
                            "region": region,
                            "hourly_price_usd": float(usd),
                        }
            return {"instance_class": instance_class, "engine": engine, "region": region, "hourly_price_usd": None}
        except Exception as e:
            logger.warning(f"Failed to extract RDS pricing: {e}")
            return {}

    # ------------------------------------------------------------------
    # Monthly snapshot collection
    # ------------------------------------------------------------------

    def collect_month_snapshot(
        self,
        month_key: str,
        instance_types: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> None:
        """Collect and save a full pricing snapshot for one month.

        Fetches EC2 (On-Demand, Reserved, Spot), S3, Lambda, and RDS
        pricing and writes a consolidated CSV.

        Args:
            month_key: Month key in ``YYYY-MM`` format.
            instance_types: EC2 types to query (defaults to ``DEFAULT_INSTANCE_TYPES``).
            regions: AWS regions to query (defaults to all configured regions).
        """
        if instance_types is None:
            instance_types = list(DEFAULT_INSTANCE_TYPES)
        if regions is None:
            from .config import get_config
            regions = get_config().regions

        logger.info(f"  Collecting pricing snapshot for {month_key}...")
        logger.info(f"    Regions: {len(regions)}, Instance types: {len(instance_types)}")

        rows: List[Dict[str, Any]] = []
        rows.extend(self._collect_ec2_on_demand(month_key, instance_types, regions))
        rows.extend(self._collect_ec2_reserved(month_key, instance_types, regions))
        rows.extend(self._collect_ec2_spot(month_key, instance_types, regions))
        rows.extend(self._collect_s3_pricing(month_key))
        rows.extend(self._collect_lambda_pricing(month_key))
        rows.extend(self._collect_rds_pricing(month_key))

        self._write_pricing_csv(month_key, rows)

    def _collect_ec2_on_demand(
        self, month_key: str, instance_types: List[str], regions: List[str],
    ) -> List[Dict[str, Any]]:
        """Collect EC2 On-Demand prices for all type/region combinations."""
        logger.info(f"    -> EC2 on-demand prices ({len(instance_types)} types x {len(regions)} regions)...")
        rows: List[Dict[str, Any]] = []
        for instance_type in instance_types:
            for region in regions:
                price = self.get_ec2_price(instance_type, region=region, pricing_type="OnDemand")
                if price:
                    rows.append({
                        "account_id": self.account_id,
                        "month": month_key,
                        "service": "EC2",
                        "pricing_type": "On-Demand",
                        "instance_type": price.get("instance_type", ""),
                        "region": price.get("region", ""),
                        "hourly_price_usd": float(price["hourly_price_usd"]) if price.get("hourly_price_usd") else 0.0,
                        "product_family": price.get("product_attributes", {}).get("productFamily", ""),
                    })
        logger.info(f"      {len(rows)} prices collected")
        return rows

    def _collect_ec2_reserved(
        self, month_key: str, instance_types: List[str], regions: List[str],
    ) -> List[Dict[str, Any]]:
        """Collect EC2 Reserved Instance prices (1yr and 3yr)."""
        reserved_types = instance_types[:RESERVED_INSTANCE_TYPES_LIMIT]
        rows: List[Dict[str, Any]] = []

        for term in ("1yr", "3yr"):
            logger.info(f"    -> EC2 reserved {term} prices ({len(reserved_types)} types x {len(regions)} regions)...")
            count = 0
            for instance_type in reserved_types:
                for region in regions:
                    reserved = self.get_reserved_price(instance_type, region=region, term=term)
                    if reserved:
                        rows.append({
                            "account_id": self.account_id,
                            "month": month_key,
                            "service": "EC2",
                            "pricing_type": f"Reserved-{term}",
                            "instance_type": reserved.get("instance_type", ""),
                            "region": reserved.get("region", ""),
                            "term": term,
                            "price_usd": float(reserved["price_usd"]) if reserved.get("price_usd") else 0.0,
                            "unit": reserved.get("unit", ""),
                        })
                        count += 1
            logger.info(f"      {count} prices collected")
        return rows

    def _collect_ec2_spot(
        self, month_key: str, instance_types: List[str], regions: List[str],
    ) -> List[Dict[str, Any]]:
        """Collect EC2 Spot prices using the EC2 Spot Price History API."""
        logger.info(f"    -> EC2 spot prices ({len(instance_types)} types x {len(regions)} regions)...")
        rows: List[Dict[str, Any]] = []
        for instance_type in instance_types:
            for region in regions:
                spot_price = self.get_spot_price(instance_type, region=region)
                if spot_price:
                    rows.append({
                        "account_id": self.account_id,
                        "month": month_key,
                        "service": "EC2",
                        "pricing_type": "Spot",
                        "instance_type": spot_price.get("instance_type", ""),
                        "region": spot_price.get("region", ""),
                        "hourly_price_usd": float(spot_price["hourly_price_usd"]) if spot_price.get("hourly_price_usd") else 0.0,
                    })
        logger.info(f"      {len(rows)} prices collected")
        return rows

    def _collect_s3_pricing(self, month_key: str) -> List[Dict[str, Any]]:
        """Collect S3 storage prices for standard classes."""
        logger.info("    -> S3 storage prices...")
        rows: List[Dict[str, Any]] = []
        for storage_class in DEFAULT_S3_STORAGE_CLASSES:
            s3_price = self.get_s3_price(storage_class)
            if s3_price:
                rows.append({
                    "account_id": self.account_id,
                    "month": month_key,
                    "service": "S3",
                    "pricing_type": "Storage",
                    "storage_class": storage_class,
                    "price_per_gb_usd": float(s3_price["price_per_gb_usd"]) if s3_price.get("price_per_gb_usd") else 0.0,
                })
        logger.info(f"      {len(rows)} prices collected")
        return rows

    def _collect_lambda_pricing(self, month_key: str) -> List[Dict[str, Any]]:
        """Collect Lambda request and compute pricing."""
        logger.info("    -> Lambda pricing...")
        rows: List[Dict[str, Any]] = []
        lambda_price = self.get_lambda_price()
        if lambda_price:
            rows.append({
                "account_id": self.account_id,
                "month": month_key,
                "service": "Lambda",
                "pricing_type": "Requests",
                "requests_per_million_usd": float(lambda_price.get("requests_per_million", 0)) if lambda_price.get("requests_per_million") else 0.0,
                "compute_per_gb_second_usd": float(lambda_price.get("compute_per_gb_second", 0)) if lambda_price.get("compute_per_gb_second") else 0.0,
            })
        logger.info(f"      {len(rows)} entries collected")
        return rows

    def _collect_rds_pricing(self, month_key: str) -> List[Dict[str, Any]]:
        """Collect RDS On-Demand pricing for sample instance classes."""
        logger.info("    -> RDS pricing...")
        rows: List[Dict[str, Any]] = []
        for instance_class in DEFAULT_RDS_INSTANCE_CLASSES:
            rds_price = self.get_rds_price(instance_class)
            if rds_price:
                rows.append({
                    "account_id": self.account_id,
                    "month": month_key,
                    "service": "RDS",
                    "pricing_type": "On-Demand",
                    "instance_class": instance_class,
                    "engine": rds_price.get("engine", ""),
                    "region": rds_price.get("region", ""),
                    "hourly_price_usd": float(rds_price["hourly_price_usd"]) if rds_price.get("hourly_price_usd") else 0.0,
                })
        logger.info(f"      {len(rows)} prices collected")
        return rows

    def _write_pricing_csv(self, month_key: str, rows: List[Dict[str, Any]]) -> None:
        """Write collected pricing rows to the consolidated CSV file.

        Args:
            month_key: Month key for logging.
            rows: List of pricing row dicts.
        """
        pricing_dir = DATA_DIR / "pricing"
        pricing_dir.mkdir(parents=True, exist_ok=True)
        consolidated_file = pricing_dir / "pricing_consolidated.csv"

        if rows:
            all_fieldnames: set[str] = set()
            for row in rows:
                all_fieldnames.update(row.keys())

            fieldnames = [f for f in PRICING_CSV_FIELDS if f in all_fieldnames]
            extra_fields = sorted(all_fieldnames - set(fieldnames))
            fieldnames.extend(extra_fields)

            normalized_rows = [{field: row.get(field, "") for field in fieldnames} for row in rows]

            file_exists = consolidated_file.exists()
            with open(consolidated_file, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(normalized_rows)

            logger.info(f"  Saved {len(rows)} pricing records -> pricing_consolidated.csv")
        else:
            if not consolidated_file.exists():
                with open(consolidated_file, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["account_id", "month", "service", "note"])
                    writer.writerow([self.account_id, month_key, "N/A", "No pricing data"])
                logger.info("  Created empty pricing file pricing_consolidated.csv")
