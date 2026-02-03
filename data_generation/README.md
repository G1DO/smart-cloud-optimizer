# Synthetic Data Generator

Generates realistic AWS usage data for the Smart Cloud Optimizer ML pipeline.

## Why synthetic data?

The real AWS data comes from a free-tier account: near-zero costs, single instance, no variation. The ML pipeline (Prophet, SARIMAX, PuLP) needs realistic cost patterns, multiple instances, and utilization variation to produce meaningful results.

## The simulated scenario

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
# Generate all synthetic data (default: 365 days, seed 42)
# Writes directly to data/cloud_optimizer.db via storage.db API
python -m data_generation.synthetic --days 365 --seed 42

# Quick test run
python -m data_generation.synthetic --days 30 --seed 42
```

## What gets written to the database

The generator populates the following tables in `data/cloud_optimizer.db`:

| Table | Approximate Rows | Description |
| --- | --- | --- |
| `users` | 1 | Synthetic user (SYNTHETIC-001) |
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

## Known differences from real data

- `account_id` is `SYNTHETIC-001` instead of a real AWS account number
- All instances are in `us-east-1` (real data uses `eu-north-1`)
- Reproducible via `--seed` flag
