"""
Consolidate existing CSV files using only csv module (no pandas required)
"""
import csv
from pathlib import Path
from collections import defaultdict

from .config import DATA_DIR


def consolidate_cost_files():
    """Consolidate cost CSV files"""
    cost_dir = DATA_DIR / "cost"
    
    # Find all monthly cost files
    for filename in ['daily_cost', 'service_cost', 'usage_type_cost', 'anomalies']:
        monthly_files = sorted(cost_dir.glob(f"*/{filename}.csv"))
        if not monthly_files:
            continue
        
        consolidated_file = cost_dir / f"{filename}_consolidated.csv"
        all_rows = []
        fieldnames = None
        
        for file in monthly_files:
            try:
                with open(file, 'r') as f:
                    reader = csv.DictReader(f)
                    if fieldnames is None:
                        fieldnames = reader.fieldnames
                    for row in reader:
                        all_rows.append(row)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if all_rows and fieldnames:
            with open(consolidated_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            print(f"  ✓ Consolidated {len(all_rows)} rows → {filename}_consolidated.csv")


def consolidate_metrics_files():
    """Consolidate metrics CSV files"""
    metrics_dir = DATA_DIR / "metrics"
    
    for service in ['ec2', 'ebs', 'lambda', 'rds', 's3']:
        service_dir = metrics_dir / service
        if not service_dir.exists():
            continue
        
        csv_files = sorted(service_dir.glob("*/*.csv"))
        if not csv_files:
            continue
        
        consolidated_file = metrics_dir / f"{service}_metrics_consolidated.csv"
        all_rows = []
        fieldnames = None
        
        for file in csv_files:
            try:
                with open(file, 'r') as f:
                    reader = csv.DictReader(f)
                    if fieldnames is None:
                        fieldnames = reader.fieldnames
                    for row in reader:
                        all_rows.append(row)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if all_rows and fieldnames:
            with open(consolidated_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            print(f"  ✓ Consolidated {len(all_rows)} rows → {service}_metrics_consolidated.csv")


def consolidate_pricing_files():
    """Consolidate pricing CSV files"""
    pricing_dir = DATA_DIR / "pricing"
    
    csv_files = sorted(pricing_dir.glob("*.csv"))
    if not csv_files:
        return
    
    consolidated_file = pricing_dir / "pricing_consolidated.csv"
    all_rows = []
    fieldnames = None
    
    for file in csv_files:
        if file.name == "pricing_consolidated.csv":
            continue  # Skip if already consolidated
        
        try:
            with open(file, 'r') as f:
                reader = csv.DictReader(f)
                if fieldnames is None:
                    fieldnames = reader.fieldnames
                for row in reader:
                    all_rows.append(row)
        except Exception as e:
            print(f"  [WARN] Could not read {file}: {e}")
    
    if all_rows and fieldnames:
        with open(consolidated_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"  ✓ Consolidated {len(all_rows)} rows → pricing_consolidated.csv")


def consolidate_all():
    """Consolidate all existing CSV files"""
    print("\n" + "=" * 60)
    print("Consolidating Existing CSV Files")
    print("=" * 60)
    
    print("\n[Cost Data]")
    consolidate_cost_files()
    
    print("\n[Metrics Data]")
    consolidate_metrics_files()
    
    print("\n[Pricing Data]")
    consolidate_pricing_files()
    
    print("\n" + "=" * 60)
    print("✓ Consolidation Complete!")
    print("=" * 60)
    print("\nConsolidated files are ready for ML training:")
    print("  - data/cost/*_consolidated.csv")
    print("  - data/metrics/*_metrics_consolidated.csv")
    print("  - data/pricing/pricing_consolidated.csv")
    print("=" * 60)


if __name__ == "__main__":
    consolidate_all()

