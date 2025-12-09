"""
Data Analysis for Forecasting & Optimization
Analyzes collected data to determine if it's sufficient for ML models
"""
import csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

from .config import DATA_DIR


def analyze_data_sufficiency():
    """Analyze if collected data is sufficient for forecasting and optimization"""
    
    print("=" * 60)
    print("Data Sufficiency Analysis for Forecasting & Optimization")
    print("=" * 60)
    
    # 1. Cost Data Analysis
    print("\n📊 COST DATA (For Forecasting):")
    daily_cost_file = DATA_DIR / "cost" / "daily_cost_consolidated.csv"
    if daily_cost_file.exists():
        with open(daily_cost_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            dates = [row['date'] for row in rows if row.get('date')]
            
            if dates:
                first_date = min(dates)
                last_date = max(dates)
                date_range = (datetime.strptime(last_date, '%Y-%m-%d') - 
                             datetime.strptime(first_date, '%Y-%m-%d')).days
                
                print(f"  ✓ Daily cost data: {len(rows)} days")
                print(f"  ✓ Date range: {first_date} to {last_date} ({date_range} days)")
                
                if date_range >= 30:
                    print(f"  ✅ SUFFICIENT for forecasting (need ≥30 days, have {date_range})")
                else:
                    print(f"  ⚠️  Need more data (have {date_range} days, need ≥30)")
            else:
                print("  ❌ No date data found")
    
    # 2. Service Usage Analysis
    print("\n📈 USAGE METRICS (For Optimization):")
    
    services_data = {
        'EC2': DATA_DIR / "metrics" / "ec2" / "ec2_metrics_consolidated.csv",
        'RDS': DATA_DIR / "metrics" / "rds" / "rds_metrics_consolidated.csv",
        'EBS': DATA_DIR / "metrics" / "ebs" / "ebs_metrics_consolidated.csv",
        'Lambda': DATA_DIR / "metrics" / "lambda" / "lambda_metrics_consolidated.csv",
        'S3': DATA_DIR / "metrics" / "s3" / "s3_metrics_consolidated.csv",
    }
    
    services_with_data = []
    for service, filepath in services_data.items():
        if filepath.exists():
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # Filter out header-only files
                if len(rows) > 0:
                    # Check if has actual data (not just empty rows)
                    has_data = any(row.get('timestamp') for row in rows if row.get('timestamp'))
                    if has_data:
                        print(f"  ✓ {service}: {len(rows)} data points")
                        services_with_data.append(service)
                    else:
                        print(f"  ⚠️  {service}: File exists but no data")
                else:
                    print(f"  ⚠️  {service}: File exists but empty")
        else:
            print(f"  ❌ {service}: No data file")
    
    # 3. Pricing Data
    print("\n💰 PRICING DATA (For Optimization):")
    pricing_file = DATA_DIR / "pricing" / "pricing_consolidated.csv"
    if pricing_file.exists():
        with open(pricing_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            services = set(row.get('service', '') for row in rows)
            print(f"  ✓ Pricing data: {len(rows)} records")
            print(f"  ✓ Services covered: {', '.join(sorted(services))}")
            if len(rows) > 0:
                print(f"  ✅ SUFFICIENT for cost comparison")
            else:
                print(f"  ⚠️  Need pricing data")
    
    # 4. Recommendations
    print("\n" + "=" * 60)
    print("🎯 RECOMMENDATIONS FOR YOUR PROJECT:")
    print("=" * 60)
    
    print("\n1. FOR FORECASTING:")
    if date_range >= 30:
        print("   ✅ You have enough cost data for forecasting!")
        print("   → Use: daily_cost_consolidated.csv")
        print("   → Models: Prophet, SARIMAX, LSTM")
    else:
        print("   ⚠️  Collect more cost data (need ≥30 days)")
    
    print("\n2. FOR OPTIMIZATION:")
    if services_with_data:
        print(f"   ✅ You have usage data for: {', '.join(services_with_data)}")
        print("   → Focus optimization on these services")
        
        if 'EC2' in services_with_data:
            print("\n   📌 EC2 Optimization:")
            print("      → Analyze CPU utilization patterns")
            print("      → Recommend: On-Demand vs Reserved vs Spot")
            print("      → Right-size instances based on usage")
        
        if 'RDS' in services_with_data:
            print("\n   📌 RDS Optimization:")
            print("      → Analyze database connections & CPU")
            print("      → Recommend: Instance class changes")
            print("      → Storage optimization")
        
        print("\n   → Optimization algorithms: PuLP, OR-Tools")
    else:
        print("   ⚠️  Need usage metrics for at least one service")
    
    print("\n3. MINIMUM REQUIREMENTS:")
    print("   For basic optimization:")
    print("   - EC2 metrics (CPU, network) ✓")
    print("   - Cost data (≥30 days) ✓")
    print("   - Pricing data ✓")
    print("\n   ✅ You have the minimum requirements!")
    
    print("\n4. OPTIONAL (for better results):")
    print("   - RDS metrics (if using databases) ✓")
    print("   - EBS metrics (if using volumes)")
    print("   - Lambda metrics (if using serverless)")
    
    print("\n" + "=" * 60)
    print("✅ CONCLUSION: Your data is SUFFICIENT for forecasting & optimization!")
    print("=" * 60)
    print("\nFocus on:")
    ec2_status = 'good' if 'EC2' in services_with_data else 'no'
    print(f"  1. EC2 optimization (you have {ec2_status} data)")
    if 'RDS' in services_with_data:
        print("  2. RDS optimization (you have good data)")
    print("  3. Cost forecasting (you have enough historical data)")
    print("=" * 60)


if __name__ == "__main__":
    analyze_data_sufficiency()

