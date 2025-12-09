"""
Cost Explorer API Module
Collects cost data from AWS Cost Explorer API
"""
import csv
from pathlib import Path
from typing import List

from .config import Config


class CostExplorer:
    """Cost Explorer API client"""
    
    def __init__(self, session, account_id: str):
        self.session = session
        self.account_id = account_id
        self.ce = session.client("ce")
    
    def _paginated_query(self, params: dict):
        """Helper to handle Cost Explorer pagination"""
        next_token = None
        while True:
            effective = dict(params)
            if next_token:
                effective["NextPageToken"] = next_token
            resp = self.ce.get_cost_and_usage(**effective)
            yield resp
            next_token = resp.get("NextPageToken")
            if not next_token:
                break
    
    def export_daily_cost_by_service(self):
        """Export daily cost grouped by service"""
        start_date, end_date = Config.get_date_range_for_cost()
        print(f"[Cost] Fetching DAILY cost by SERVICE from {start_date} to {end_date} ...")
        
        rows = []
        
        base_params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        }
        
        for resp in self._paginated_query(base_params):
            for result in resp.get("ResultsByTime", []):
                date_str = result["TimePeriod"]["Start"]
                for group in result.get("Groups", []):
                    service_name = group["Keys"][0]
                    amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    unit = group["Metrics"]["UnblendedCost"]["Unit"]
                    
                    rows.append({
                        "account_id": self.account_id,
                        "date": date_str,
                        "service_name": service_name,
                        "cost_amount": amount,
                        "currency": unit,
                    })
        
        fieldnames = [
            "account_id",
            "date",
            "service_name",
            "cost_amount",
            "currency",
        ]
        
        csv_path = Config.get_csv_path(Config.DAILY_COST_CSV)
        print(f"[Cost] Writing {len(rows)} rows to {csv_path} ...")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return csv_path
    
    def export_daily_cost_by_service_region(self):
        """Export daily cost grouped by service and region"""
        start_date, end_date = Config.get_date_range_for_cost()
        print(f"[Cost] Fetching DAILY cost by SERVICE & REGION from {start_date} to {end_date} ...")
        
        rows = []
        
        base_params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        }
        
        for resp in self._paginated_query(base_params):
            for result in resp.get("ResultsByTime", []):
                date_str = result["TimePeriod"]["Start"]
                for group in result.get("Groups", []):
                    service_name, region = group["Keys"]
                    amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    unit = group["Metrics"]["UnblendedCost"]["Unit"]
                    
                    rows.append({
                        "account_id": self.account_id,
                        "date": date_str,
                        "service_name": service_name,
                        "region": region,
                        "cost_amount": amount,
                        "currency": unit,
                    })
        
        fieldnames = [
            "account_id",
            "date",
            "service_name",
            "region",
            "cost_amount",
            "currency",
        ]
        
        csv_path = Config.get_csv_path(Config.DAILY_COST_REGION_CSV)
        print(f"[Cost] Writing {len(rows)} rows to {csv_path} ...")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return csv_path
    
    def export_daily_cost_by_tag_environment(self):
        """
        Export daily cost grouped by Environment tag
        Make sure you actually use tag 'Environment' (Prod/Dev/Test).
        """
        start_date, end_date = Config.get_date_range_for_cost()
        print(f"[Cost] Fetching DAILY cost by TAG:Environment from {start_date} to {end_date} ...")
        
        rows = []
        
        base_params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [
                {"Type": "TAG", "Key": "Environment"},
            ],
        }
        
        for resp in self._paginated_query(base_params):
            for result in resp.get("ResultsByTime", []):
                date_str = result["TimePeriod"]["Start"]
                for group in result.get("Groups", []):
                    tag_val = group["Keys"][0]  # e.g., "Environment$Prod"
                    amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    unit = group["Metrics"]["UnblendedCost"]["Unit"]
                    
                    rows.append({
                        "account_id": self.account_id,
                        "date": date_str,
                        "tag_environment": tag_val,
                        "cost_amount": amount,
                        "currency": unit,
                    })
        
        fieldnames = [
            "account_id",
            "date",
            "tag_environment",
            "cost_amount",
            "currency",
        ]
        
        csv_path = Config.get_csv_path(Config.DAILY_COST_TAG_ENV_CSV)
        print(f"[Cost] Writing {len(rows)} rows to {csv_path} ...")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return csv_path

