# Synthetic Data Generator

Generates realistic AWS usage data for the Smart Cloud Optimizer ML pipeline.

## Why synthetic data?

The real AWS data comes from a free-tier account: near-zero costs, single instance, no variation. The ML pipeline (Prophet, SARIMAX, PuLP) needs realistic cost patterns, multiple instances, and utilization variation to produce meaningful results.

## The simulated scenario

A mid-size SaaS startup with monthly AWS bill ~$1,500–$2,500:

| Service | % of Bill | Daily Range | Pattern |
|---------|-----------|-------------|---------|
| EC2 | ~50% | $25–$55 | Weekly seasonality, diurnal, upward trend |
| RDS | ~20% | $12–$18 | Nearly flat (databases run 24/7) |
| S3 | ~5% | $1.50–$4 | Gradual upward trend (data accumulates) |
| Lambda | ~2% | $0.30–$3 | Bursty, correlated with user activity |
| EBS | ~3% | $1.80–$2.50 | Flat (provisioned storage) |
| Data Transfer | ~10% | $3–$8 | Follows EC2 pattern |
| Other | ~5% | $1.50–$4 | Stable |

EC2 fleet: 8 instances with deliberate optimization opportunities (over-provisioned web servers, idle staging/dev, batch job running 24/7 for a 3h nightly task).

## Usage

```bash
# Generate all synthetic data (default: 180 days, seed 42)
python -m data_generation.synthetic --output-dir data/synthetic/ --days 180 --seed 42

# Quick test run
python -m data_generation.synthetic --output-dir data/synthetic/ --days 30 --seed 42

# Use specific real pricing file
python -m data_generation.synthetic --real-pricing data/real/pricing/pricing_consolidated.csv
```

Real pricing from `data/real/pricing/pricing_consolidated.csv` is auto-detected and merged when available.

## Output files

All CSVs match the exact column schemas from `data/` (produced by `aws_collector/`):

| File | Rows | Schema source |
|------|------|---------------|
| `daily_costs.csv` | 180 | `data/real/cost/daily_cost_consolidated.csv` |
| `service_costs.csv` | 1,260 | `data/real/cost/service_cost_consolidated.csv` |
| `ec2_instances.csv` | 8 | `data/real/inventory/ec2_instances.csv` |
| `ec2_metrics.csv` | ~17,280 | `data/real/metrics/ec2/ec2_metrics_consolidated.csv` |
| `rds_instances.csv` | 2 | `data/real/inventory/rds_instances.csv` |
| `rds_metrics.csv` | ~2,160 | `data/real/metrics/rds/rds_metrics_consolidated.csv` |
| `s3_buckets.csv` | 4 | `data/real/inventory/s3_buckets.csv` |
| `lambda_functions.csv` | 4 | `data/real/inventory/lambda_functions.csv` |
| `ebs_volumes.csv` | 8 | `data/real/inventory/ebs_volumes.csv` |
| `instance_pricing.csv` | ~60 | `data/real/pricing/pricing_consolidated.csv` + synthetic |
| `ai_recommendations_sample.csv` | 10 | New (demo mode) |
| `cost_preview.png` | — | Matplotlib plot of daily costs |

## Known differences from real data

- `account_id` is `SYNTHETIC-001` instead of a real AWS account number
- EC2/RDS metrics use **correct** column order (the real data has `instance_id` ↔ `timestamp` swapped)
- All instances are in `us-east-1` (real data uses `eu-north-1`)
- Reproducible via `--seed` flag
