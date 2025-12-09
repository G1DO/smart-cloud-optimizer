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
│   └── YYYY-MM/              # Monthly cost data (CSV)
│       ├── daily_cost_consolidated.csv
│       ├── service_cost_consolidated.csv
│       ├── usage_type_cost_consolidated.csv
│       └── anomalies_consolidated.csv
├── metrics/
│   ├── ec2/                  # EC2 metrics (consolidated CSV)
│   ├── ebs/                  # EBS metrics (consolidated CSV)
│   ├── lambda/               # Lambda metrics (consolidated CSV)
│   ├── rds/                  # RDS metrics (consolidated CSV)
│   ├── s3/                   # S3 metrics (consolidated CSV)
│   ├── cloudfront/YYYY-MM/   # CloudFront metrics by month (CSV)
│   │   └── cloudfront_metrics.csv
│   ├── nat/YYYY-MM/          # NAT Gateway metrics by month (CSV)
│   │   └── nat_metrics.csv
│   ├── alb/YYYY-MM/          # ALB metrics by month (CSV)
│   │   └── alb_metrics.csv
│   └── nlb/YYYY-MM/          # NLB metrics by month (CSV)
│       └── nlb_metrics.csv
├── pricing/
│   └── pricing_consolidated.csv  # Pricing data (consolidated CSV)
└── inventory/
    ├── ec2_instances.csv      # EC2 instances (collected once)
    ├── ebs_volumes.csv        # EBS volumes (collected once)
    ├── regions_consolidated.csv  # AWS regions (collected once)
    ├── cloudfront.csv         # CloudFront distributions (collected once)
    ├── nat_gateways.csv       # NAT Gateways (collected once)
    └── load_balancers.csv     # Load Balancers (collected once)
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
- **CloudFront**: Requests, BytesDownloaded, BytesUploaded, CacheHitRate, TotalErrorRate
- **NAT Gateways**: BytesProcessed, ActiveConnectionCount
- **ALB (Application Load Balancer)**: RequestCount, HTTPCode_ELB_4XX_Count, HTTPCode_ELB_5XX_Count
- **NLB (Network Load Balancer)**: ProcessedBytes, NewFlowCount

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
- CloudFront distributions
- NAT Gateways (all regions)
- Load Balancers (ALB + NLB, all regions)

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

## New Supported AWS Services

The collector now includes comprehensive support for additional AWS services:

### CloudFront
- **Inventory**: Distribution ID, domain name, status, enabled state, price class
- **Metrics**: Requests, BytesDownloaded, BytesUploaded, CacheHitRate, TotalErrorRate
- **Data Location**: `data/inventory/cloudfront.csv`, `data/metrics/cloudfront/YYYY-MM/cloudfront_metrics.csv`

### NAT Gateways
- **Inventory**: NAT Gateway ID, VPC ID, subnet ID, state, connectivity type, tags
- **Metrics**: BytesProcessed, ActiveConnectionCount
- **Data Location**: `data/inventory/nat_gateways.csv`, `data/metrics/nat/YYYY-MM/nat_metrics.csv`

### Load Balancers (ALB + NLB)
- **Inventory**: Load Balancer ARN, name, type (ALB/NLB), scheme, DNS name, state, VPC ID, security groups, subnets
- **ALB Metrics**: RequestCount, HTTPCode_ELB_4XX_Count, HTTPCode_ELB_5XX_Count
- **NLB Metrics**: ProcessedBytes, NewFlowCount
- **Data Location**: `data/inventory/load_balancers.csv`, `data/metrics/alb/YYYY-MM/alb_metrics.csv`, `data/metrics/nlb/YYYY-MM/nlb_metrics.csv`

These new collectors complete FinOps-level data coverage, enabling advanced cloud cost optimization across compute, storage, networking, and edge services.

## Notes

- Collection may take a while depending on the number of resources
- Some API calls may fail due to permissions or missing resources - these are logged as warnings
- All data is saved as CSV files for easy processing and ML model training
- The collector handles pagination automatically
- Failures in new collectors (CloudFront, NAT Gateways, Load Balancers) do not stop the entire collection process
