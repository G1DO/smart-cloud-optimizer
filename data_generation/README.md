# Sample Data Generator

Generates sample AWS usage data for the Smart Cloud Optimizer ML pipeline, based on open-source datasets supplemented with generated data for full service coverage.

## Data Sources

The sample data is built on publicly available open-source datasets:

| Source | What it provides | Reference |
|--------|------------------|-----------|
| **Bitbrains GWA-T-12** | VM utilization metrics (CPU, memory, disk I/O, network) from 1,750 VMs | Kaggle / TU Delft |
| **NAB (Numenta)** | Real AWS CloudWatch metrics with labeled anomaly windows | Kaggle / GitHub |
| **EC2 Instance Metrics** | Real EC2 system metrics (CPU, memory, disk) | Kaggle (sakthivelank) |
| **AWS Pricing Dataset** | Pre-scraped AWS pricing across all services | Kaggle (justsahil) |
| **Cloud Workload Traces** | Job traces for forecasting benchmarks | Kaggle (zoya77) |

See [DATA_RESOURCES.md](../documentation/DATA_RESOURCES.md) for full details, citations, and download links.

### Generated supplement

Open-source datasets cover EC2 metrics, anomaly patterns, and pricing well. To ensure full coverage across all **10 AWS services** in the pipeline, the generator creates supplementary data for services without public datasets (ECS, ElastiCache, DynamoDB, NAT Gateway, ELB, etc.) using realistic patterns modeled after the open-source data.

## The sample scenario

A mid-size SaaS startup with monthly AWS bill ~$1,500-$2,500:

| Service | % of Bill | Daily Range | Pattern |
|---------|-----------|-------------|---------|
| EC2 | ~50% | $25-$55 | Weekly seasonality, diurnal, upward trend |
| RDS | ~20% | $12-$18 | Nearly flat (databases run 24/7) |
| S3 | ~5% | $1.50-$4 | Gradual upward trend (data accumulates) |
| Lambda | ~2% | $0.30-$3 | Bursty, correlated with user activity |
| EBS | ~3% | $1.80-$2.50 | Flat (provisioned storage) |
| Data Transfer | ~10% | $3-$8 | Follows EC2 pattern |
| Other | ~5% | $1.50-$4 | Stable |

EC2 fleet: 8 instances with deliberate optimization opportunities (over-provisioned web servers, idle staging/dev, batch job running 24/7 for a 3h nightly task).

## Usage

```bash
# Generate all sample data (default: 365 days, seed 42)
# Writes directly to data/cloud_optimizer.db via storage.db API
python -m data_generation.synthetic --days 365 --seed 42

# Quick test run
python -m data_generation.synthetic --days 30 --seed 42
```

## What gets written to the database

The generator populates the following tables in `data/cloud_optimizer.db`:

| Table | Approximate Rows | Description |
| --- | --- | --- |
| `users` | 1 | Demo user (DEMO-001) |
| `daily_costs` | 365 | Daily total cost |
| `service_costs` | ~2,555 | Per-service daily costs (7 services x 365 days) |
| `ec2_instances` | 8 | EC2 instance inventory |
| `ec2_metrics` | ~70,080 | Hourly EC2 utilization (8 instances x 8,760 hours) |
| `rds_instances` | 2 | RDS instance inventory |
| `rds_metrics` | ~17,520 | Hourly RDS metrics |
| `s3_buckets` | 4 | S3 bucket inventory |
| `lambda_functions` | 4 | Lambda function inventory |
| `ebs_volumes` | 8 | EBS volume inventory |
| `instance_pricing` | ~60 | EC2 and RDS pricing reference data |

## Notes

- All instances are in `us-east-1`
- Reproducible via `--seed` flag — same seed always produces identical output
- All random values use `numpy.random.default_rng(seed)` for determinism
