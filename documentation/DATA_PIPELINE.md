# Data Pipeline

This document explains both data pipelines: real AWS collection and synthetic generation.

## 1. Real AWS Collection Pipeline

### Entry Point

```bash
python -m aws_collector.main
```

### How It Works

The `CollectorRunner` orchestrates everything. It runs in three steps:

```text
Step 1: Inventory (once)
  EC2Collector.save_inventory()
    ├── list_instances()  ──>  data/real/inventory/instances_consolidated.csv
    ├── list_volumes()    ──>  data/real/inventory/volumes_consolidated.csv
    └── list_regions()    ──>  data/real/inventory/regions_consolidated.csv

Step 2: Monthly loop (12 months, oldest first)
  For each month:
    ├── CostCollector.collect_month()
    │     ├── fetch_daily_cost()        ──>  data/real/cost/daily_cost_consolidated.csv
    │     ├── fetch_service_cost()      ──>  data/real/cost/service_cost_consolidated.csv
    │     ├── fetch_usage_type_cost()   ──>  data/real/cost/usage_type_cost_consolidated.csv
    │     └── fetch_anomalies()         ──>  data/real/cost/anomalies_consolidated.csv
    │
    ├── collect_metrics_for_month()
    │     ├── _collect_ec2_metrics()        ──>  data/real/metrics/ec2/ec2_metrics_consolidated.csv
    │     ├── _collect_ebs_metrics()        ──>  data/real/metrics/ebs/ebs_metrics_consolidated.csv
    │     ├── _collect_lambda_metrics()     ──>  data/real/metrics/lambda/lambda_metrics_consolidated.csv
    │     ├── _collect_rds_metrics()        ──>  data/real/metrics/rds/rds_metrics_consolidated.csv
    │     ├── _collect_s3_metrics()         ──>  data/real/metrics/s3/s3_metrics_consolidated.csv
    │     ├── _collect_cloudfront_metrics() ──>  data/real/metrics/cloudfront/cloudfront_metrics_consolidated.csv
    │     ├── _collect_nat_metrics()        ──>  data/real/metrics/nat/nat_metrics_consolidated.csv
    │     └── _collect_lb_metrics()         ──>  data/real/metrics/alb/ + nlb/
    │
    └── PricingCollector.collect_month_snapshot()
          ├── _collect_ec2_on_demand()   ──┐
          ├── _collect_ec2_reserved()    ──┤
          ├── _collect_ec2_spot()        ──┼──>  data/real/pricing/pricing_consolidated.csv
          ├── _collect_s3_pricing()      ──┤
          ├── _collect_lambda_pricing()  ──┤
          └── _collect_rds_pricing()     ──┘
```

### Month Splitting

AWS APIs have time range limits. The collector splits the last 12 months into individual month ranges using `date_utils.get_last_n_months(12)`:

```text
Example output for 12 months from June 2025:
  ("2024-07-01", "2024-07-31")
  ("2024-08-01", "2024-08-31")
  ...
  ("2025-06-01", "2025-06-30")
```

Each month is processed sequentially: cost → metrics → pricing.

### Deduplication

Every CSV write operation checks for existing rows before appending. The dedup key depends on the service:

| Service | Dedup Key |
| --- | --- |
| EC2 metrics | `(instance_id, timestamp)` |
| EBS metrics | `(volume_id, timestamp)` |
| RDS metrics | `(db_instance_id, timestamp)` |
| CloudFront | `(distribution_id, timestamp)` |
| NAT Gateway | `(nat_gateway_id, region, timestamp)` |
| ALB/NLB | `(lb_arn, timestamp)` |

This means you can safely re-run the collector without creating duplicate rows.

### Instance Merging

The metrics collection step merges three sources of instance data to capture metrics for terminated instances (CloudWatch retains historical data even after termination):

```text
1. Current live instances  ──>  ec2.describe_instances()
2. Previous JSON inventory ──>  data/inventory/instances.json
3. Legacy CSV inventory    ──>  data/inventory/ec2_instances.csv
```

### Error Handling

Every AWS API call and file I/O operation is wrapped in try/except. Failures are logged as warnings and skipped — a failed metric for one instance doesn't stop collection for the remaining instances.

---

## 2. Synthetic Data Pipeline

### Entry Point

```bash
python -m data_generation.synthetic --output-dir data/synthetic/ --days 365 --seed 42
```

### What It Generates

The synthetic generator creates data that matches the exact CSV schemas produced by `aws_collector/`. It simulates a mid-size SaaS startup.

```text
synthetic.py
  ├── generate_daily_costs()           ──>  daily_costs.csv
  ├── generate_service_costs()         ──>  service_costs.csv
  ├── generate_ec2_instances()         ──>  ec2_instances.csv
  ├── generate_rds_instances()         ──>  rds_instances.csv
  ├── generate_s3_buckets()            ──>  s3_buckets.csv
  ├── generate_lambda_functions()      ──>  lambda_functions.csv
  ├── generate_ebs_volumes()           ──>  ebs_volumes.csv
  ├── generate_ec2_metrics()           ──>  ec2_metrics.csv
  ├── generate_rds_metrics()           ──>  rds_metrics.csv
  ├── generate_instance_pricing()      ──>  instance_pricing.csv
  ├── generate_ai_recommendations()    ──>  ai_recommendations_sample.csv
  └── _plot_cost_preview()             ──>  cost_preview.png
```

### The Simulated Environment

| Resource | Count | Details |
| --- | --- | --- |
| EC2 instances | 8 | 2 prod-web, 1 prod-api, 1 prod-cache, 1 staging-web, 1 staging-api, 1 dev, 1 batch |
| RDS instances | 2 | 1 prod-postgres (r5.large), 1 staging-postgres (t4g.medium) |
| S3 buckets | 4 | uploads, logs, backups, static-assets |
| Lambda functions | 4 | image-resizer, email-sender, log-processor, webhook-handler |
| EBS volumes | 8 | One per EC2 instance (gp2/gp3/io2) |
| Monthly bill | ~$1,500-$2,500 | Realistic for a small SaaS company |

### Realism Features

**Cost data** has:

- Weekly seasonality (weekdays 30% higher than weekends)
- Upward trend (+1.5%/month)
- Month-end bumps (+8% last 3 days)
- 5 anomaly spikes (2-3x normal cost)
- Gaussian noise (+-12%)

**EC2 metrics** have per-instance CPU profiles:

| Profile | Behavior |
| --- | --- |
| `prod-web` | Diurnal pattern: 8-35% weekday, 4-15% weekend |
| `prod-api` | Spiky 35-55% during business hours |
| `prod-cache` | Steady 20-30% |
| `staging` | 5-15% weekday work hours, 1-3% otherwise |
| `dev` | 2-8% with random 35-55% spikes (5% probability) |
| `batch` | 1% except 2-5am = 85-95% |

**Pricing data** can merge with real pricing. If `data/real/pricing/pricing_consolidated.csv` exists, the generator uses real on-demand prices and fills missing pricing types (Reserved, Spot) synthetically.

### Determinism

All random values use `numpy.random.default_rng(seed)`. Instance IDs are derived from names via MD5 hashes. The same seed always produces identical output.

---

## 3. How the Two Pipelines Connect

Both pipelines produce CSVs with compatible schemas. The `config.get_data_dir()` function returns the correct directory:

```python
# In any downstream module:
from config import get_data_dir

data_dir = get_data_dir()  # Returns data/synthetic/ or data/real/
costs = pd.read_csv(data_dir / "daily_costs.csv")
```

The ML engine, AI module, and optimizer all use this function to read data — they don't care whether the data is real or synthetic.
