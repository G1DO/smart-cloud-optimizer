# Data Folder Structure

All AWS data is organized here in CSV format, ready for ML training.

## 📁 Folder Organization

```
data/
├── cost/                          # Cost Explorer data (CSV only)
│   ├── daily_cost_consolidated.csv          # All daily costs (appends new data)
│   ├── service_cost_consolidated.csv        # Cost by service (appends new data)
│   ├── usage_type_cost_consolidated.csv     # Cost by usage type (appends new data)
│   └── anomalies_consolidated.csv           # Cost anomalies (appends new data)
│
├── metrics/                      # CloudWatch metrics (CSV only)
│   ├── ec2_metrics_consolidated.csv        # All EC2 metrics (appends new data)
│   ├── ebs_metrics_consolidated.csv        # All EBS metrics (appends new data)
│   ├── rds_metrics_consolidated.csv        # All RDS metrics (appends new data)
│   ├── lambda_metrics_consolidated.csv     # All Lambda metrics (appends new data)
│   ├── s3_metrics_consolidated.csv         # All S3 metrics (appends new data)
│   └── elbv2_metrics_consolidated.csv      # All ELB metrics (appends new data)
│
├── pricing/                      # AWS Pricing data (CSV only)
│   └── pricing_consolidated.csv            # All pricing snapshots (appends new data)
│
└── inventory/                    # Resource inventory
    ├── instances.json            # EC2 instances (JSON)
    ├── volumes.json              # EBS volumes (JSON)
    ├── regions.json              # AWS regions (JSON)
    └── *.csv                     # Legacy CSV files
```

## 🔄 How Data Collection Works

1. **New data collection**: When you run the collector, it:
   - Fetches data from AWS APIs
   - **Appends** new data directly to `*_consolidated.csv` files
   - **No date folders** - everything goes straight to consolidated CSVs

2. **Consolidated files**: These are your main files for ML training:
   - All historical data in one place
   - New data automatically appended
   - Easy to load with pandas: `pd.read_csv('data/cost/daily_cost_consolidated.csv')`
   - **CSV files only** - no JSON, no date folders

## 📊 Using Consolidated Files for ML

```python
import pandas as pd

# Load consolidated cost data
cost_df = pd.read_csv('data/cost/daily_cost_consolidated.csv')

# Load consolidated EC2 metrics
ec2_df = pd.read_csv('data/metrics/ec2_metrics_consolidated.csv')

# All data is ready for ML training!
```

## ✅ Current Status

- ✅ All JSON files cleaned up
- ✅ All CSV files organized into proper folders
- ✅ Consolidated files created and ready for appending
- ✅ Collector configured to append to consolidated files
- ✅ Monthly backups preserved

## 🚀 Next Steps

Run the collector to start appending new data:

```bash
python3 -m aws_collector.main
```

New data will automatically be added to the consolidated CSV files!

