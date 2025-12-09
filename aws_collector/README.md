# AWS Data Collector

A complete AWS data collection system that gathers cost, metrics, pricing, and inventory data month-by-month for the last 5 months.

## Structure

```
aws_collector/
├── __init__.py              # Package initialization
├── config.py                # AWS client configuration
├── date_utils.py            # Month splitting utilities
├── cost_collector.py        # Cost Explorer data collection
├── cw_collector.py          # CloudWatch metrics collection
├── pricing_collector.py     # AWS Pricing API collection
├── ec2_collector.py         # EC2 inventory collection
├── collector_runner.py      # Main orchestrator
└── main.py                  # Entry point
```

## Data Structure

All collected data is stored in the `data/` folder:

```
data/
├── cost/
│   └── YYYY-MM/              # Monthly cost data
│       ├── daily_cost.json
│       ├── service_cost.json
│       ├── usage_type_cost.json
│       └── anomalies.json
├── metrics/
│   ├── ec2/YYYY-MM/          # EC2 metrics by month
│   ├── ebs/YYYY-MM/          # EBS metrics by month
│   ├── lambda/YYYY-MM/       # Lambda metrics by month
│   ├── rds/YYYY-MM/          # RDS metrics by month
│   └── s3/YYYY-MM/           # S3 metrics by month
├── pricing/
│   └── YYYY-MM.json          # Monthly pricing snapshots
└── inventory/
    ├── instances.json        # EC2 instances (collected once)
    ├── volumes.json          # EBS volumes (collected once)
    └── regions.json          # AWS regions (collected once)
```

## Usage

### Command Line

```bash
# Run from project root
python -m aws_collector.main

# Or
cd aws_collector
python main.py
```

### Python API

```python
from aws_collector import CollectorRunner

# Initialize and run collector
runner = CollectorRunner()
runner.run(months=5)  # Collect last 5 months
```

### Collect Specific Data

```python
from aws_collector import CollectorRunner, AWSConfig
from aws_collector.date_utils import get_last_n_months

config = AWSConfig()
runner = CollectorRunner(config)

# Collect inventory only
runner.ec2_collector.save_inventory()

# Collect cost for specific month
from aws_collector.cost_collector import CostCollector
cost_collector = CostCollector(config)
cost_collector.collect_month("2024-10-01", "2024-10-31")
```

## Features

### Cost Explorer Data
- Daily cost breakdown
- Cost by service
- Cost by usage type
- Cost anomalies detection

### CloudWatch Metrics
- **EC2**: CPUUtilization, NetworkIn/Out, DiskReadOps/WriteOps
- **EBS**: VolumeReadBytes, VolumeWriteBytes, VolumeIdleTime, VolumeConsumedReadWriteOps
- **Lambda**: Invocations, Duration, Errors
- **RDS**: CPUUtilization, FreeStorageSpace, DatabaseConnections
- **S3**: BucketSizeBytes, NumberOfObjects

### Pricing Data
- EC2 on-demand prices
- EC2 Reserved Instance prices (1yr, 3yr)
- S3 storage prices (Standard, Standard-IA, Glacier)
- Lambda pricing
- RDS pricing

### Inventory
- EC2 instances (all regions)
- EBS volumes (all regions)
- AWS regions list

## Month-by-Month Collection

The collector automatically splits the last 5 months into monthly chunks to comply with AWS API limits:

- Cost Explorer: Fetches one month at a time
- CloudWatch: Fetches metrics for each month separately
- Pricing: Takes monthly snapshots
- Inventory: Collected once (doesn't change frequently)

## Configuration

Edit `config.py` to adjust:
- AWS region selection
- Data output directories
- API client settings

## Requirements

- boto3
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Appropriate IAM permissions:
  - Cost Explorer: `ce:GetCostAndUsage`, `ce:GetAnomalies`
  - CloudWatch: `cloudwatch:GetMetricStatistics`
  - EC2: `ec2:Describe*`
  - Pricing: `pricing:GetProducts`
  - RDS: `rds:Describe*`
  - Lambda: `lambda:ListFunctions`
  - S3: `s3:ListBuckets`

## Notes

- Collection may take a while depending on the number of resources
- Some API calls may fail due to permissions or missing resources - these are logged as warnings
- All data is saved as JSON files for easy processing
- The collector handles pagination automatically
