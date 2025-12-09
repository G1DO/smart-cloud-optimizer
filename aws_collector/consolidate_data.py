"""
Consolidate CSV Data
Combines monthly CSV files into consolidated files for easy ML training
"""
import csv
import pandas as pd
from pathlib import Path
from typing import List, Dict
import glob

from .config import DATA_DIR


def consolidate_cost_data():
    """Consolidate all monthly cost CSV files into single files"""
    cost_dir = DATA_DIR / "cost"
    output_dir = DATA_DIR / "cost"
    
    # Consolidate daily_cost
    daily_files = sorted(cost_dir.glob("*/daily_cost.csv"))
    if daily_files:
        dfs = []
        for file in daily_files:
            try:
                df = pd.read_csv(file)
                dfs.append(df)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if dfs:
            consolidated = pd.concat(dfs, ignore_index=True)
            consolidated = consolidated.sort_values('date')
            consolidated.to_csv(output_dir / "daily_cost_consolidated.csv", index=False)
            print(f"  ✓ Consolidated {len(consolidated)} rows from {len(daily_files)} files → daily_cost_consolidated.csv")
    
    # Consolidate service_cost
    service_files = sorted(cost_dir.glob("*/service_cost.csv"))
    if service_files:
        dfs = []
        for file in service_files:
            try:
                df = pd.read_csv(file)
                dfs.append(df)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if dfs:
            consolidated = pd.concat(dfs, ignore_index=True)
            consolidated = consolidated.sort_values('date')
            consolidated.to_csv(output_dir / "service_cost_consolidated.csv", index=False)
            print(f"  ✓ Consolidated {len(consolidated)} rows from {len(service_files)} files → service_cost_consolidated.csv")
    
    # Consolidate usage_type_cost
    usage_files = sorted(cost_dir.glob("*/usage_type_cost.csv"))
    if usage_files:
        dfs = []
        for file in usage_files:
            try:
                df = pd.read_csv(file)
                dfs.append(df)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if dfs:
            consolidated = pd.concat(dfs, ignore_index=True)
            consolidated = consolidated.sort_values('date')
            consolidated.to_csv(output_dir / "usage_type_cost_consolidated.csv", index=False)
            print(f"  ✓ Consolidated {len(consolidated)} rows from {len(usage_files)} files → usage_type_cost_consolidated.csv")
    
    # Consolidate anomalies
    anomaly_files = sorted(cost_dir.glob("*/anomalies.csv"))
    if anomaly_files:
        dfs = []
        for file in anomaly_files:
            try:
                df = pd.read_csv(file)
                dfs.append(df)
            except Exception as e:
                print(f"  [WARN] Could not read {file}: {e}")
        
        if dfs:
            consolidated = pd.concat(dfs, ignore_index=True)
            consolidated.to_csv(output_dir / "anomalies_consolidated.csv", index=False)
            print(f"  ✓ Consolidated {len(consolidated)} rows from {len(anomaly_files)} files → anomalies_consolidated.csv")


def consolidate_metrics(service: str):
    """Consolidate all monthly metrics CSV files for a service"""
    metrics_dir = DATA_DIR / "metrics" / service
    output_dir = DATA_DIR / "metrics"
    
    # Find all CSV files across all months
    csv_files = sorted(metrics_dir.glob("*/*.csv"))
    
    if not csv_files:
        return
    
    dfs = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            # Add month from parent directory
            month = file.parent.name
            df['month'] = month
            dfs.append(df)
        except Exception as e:
            print(f"  [WARN] Could not read {file}: {e}")
    
    if dfs:
        consolidated = pd.concat(dfs, ignore_index=True)
        consolidated = consolidated.sort_values('timestamp')
        output_file = output_dir / f"{service}_metrics_consolidated.csv"
        consolidated.to_csv(output_file, index=False)
        print(f"  ✓ Consolidated {len(consolidated)} rows from {len(csv_files)} files → {service}_metrics_consolidated.csv")


def consolidate_pricing():
    """Consolidate all monthly pricing CSV files"""
    pricing_dir = DATA_DIR / "pricing"
    output_file = pricing_dir / "pricing_consolidated.csv"
    
    csv_files = sorted(pricing_dir.glob("*.csv"))
    
    if not csv_files:
        return
    
    dfs = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            print(f"  [WARN] Could not read {file}: {e}")
    
    if dfs:
        consolidated = pd.concat(dfs, ignore_index=True)
        consolidated = consolidated.sort_values('month')
        consolidated.to_csv(output_file, index=False)
        print(f"  ✓ Consolidated {len(consolidated)} rows from {len(csv_files)} files → pricing_consolidated.csv")


def consolidate_all():
    """Consolidate all data types"""
    print("\n" + "=" * 60)
    print("Consolidating CSV Data")
    print("=" * 60)
    
    print("\n[Cost Data]")
    consolidate_cost_data()
    
    print("\n[Metrics Data]")
    for service in ['ec2', 'ebs', 'lambda', 'rds', 's3']:
        consolidate_metrics(service)
    
    print("\n[Pricing Data]")
    consolidate_pricing()
    
    print("\n" + "=" * 60)
    print("✓ Consolidation Complete!")
    print("=" * 60)


if __name__ == "__main__":
    consolidate_all()

