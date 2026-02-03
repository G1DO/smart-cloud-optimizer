# Data Pipeline

This document explains both data pipelines: real AWS collection and synthetic generation.

## 1. Real AWS Collection Pipeline

### Entry Point

```bash
python -m aws_collector.main
```

### How It Works

The `CollectorRunner` in `runner.py` orchestrates everything. Each service has its own collector in `collectors/` that handles inventory + metrics:

```text
Monthly loop (12 months, oldest first)
  For each month:
    ├── CostCollector.collect()
    │     └── daily costs, service costs, anomalies ──> storage.insert_*()
    │
    ├── EC2Collector.collect()
    │     └── instances, volumes, metrics ──> storage.insert_*()
    │
    ├── RDSCollector.collect()
    │     └── db instances, metrics ──> storage.insert_*()
    │
    ├── LambdaCollector.collect()
    │     └── functions, metrics ──> storage.insert_*()
    │
    ├── S3Collector.collect()
    │     └── buckets, metrics ──> storage.insert_*()
    │
    ├── DynamoDBCollector.collect()
    │     └── tables, metrics ──> storage.insert_*()
    │
    ├── ElastiCacheCollector.collect()
    │     └── clusters, metrics ──> storage.insert_*()
    │
    ├── ECSCollector.collect()
    │     └── services, metrics ──> storage.insert_*()
    │
    ├── NATGatewayCollector.collect()
    │     └── gateways, metrics ──> storage.insert_*()
    │
    ├── ELBCollector.collect()
    │     └── load balancers, metrics ──> storage.insert_*()
    │
    └── PricingCollector.collect()
          └── EC2/RDS/Lambda/S3 pricing ──> storage.insert_*()
```

### Month Splitting

AWS APIs have time range limits. The collector splits the last 12 months into individual month ranges using `metrics.get_last_n_months(12)`:

```text
Example output for 12 months from June 2025:
  ("2024-07-01", "2024-07-31")
  ("2024-08-01", "2024-08-31")
  ...
  ("2025-06-01", "2025-06-30")
```

Each month is processed sequentially: cost → metrics → pricing.

### Deduplication

All tables use `INSERT OR REPLACE` on their primary keys. The dedup key depends on the service:

| Service | Primary Key |
| --- | --- |
| EC2 metrics | `(timestamp, user_id, instance_id)` |
| EBS metrics | `(timestamp, user_id, volume_id)` |
| RDS metrics | `(timestamp, user_id, db_instance_id)` |
| NAT Gateway metrics | `(timestamp, user_id, nat_gateway_id)` |
| ELB metrics | `(timestamp, user_id, elb_arn)` |

This means you can safely re-run the collector without creating duplicate rows.

### Error Handling

Every AWS API call and file I/O operation is wrapped in try/except. Failures are logged as warnings and skipped — a failed metric for one instance doesn't stop collection for the remaining instances.

---

## 2. Synthetic Data Pipeline

### Entry Point

```bash
python -m data_generation.synthetic --days 365 --seed 42
```

### What It Generates

The synthetic generator creates data that matches the exact DB schemas and writes directly to SQLite via `storage.insert_*()`. It simulates a mid-size SaaS startup.

```text
synthetic.py
  ├── generate_daily_costs()           ──>  storage.insert_daily_costs()
  ├── generate_service_costs()         ──>  storage.insert_service_costs()
  ├── generate_ec2_instances()         ──>  storage.insert_ec2_instances()
  ├── generate_rds_instances()         ──>  storage.insert_rds_instances()
  ├── generate_elasticache_nodes()     ──>  storage.insert_elasticache_nodes()
  ├── generate_ecs_services()          ──>  storage.insert_ecs_services()
  ├── generate_dynamodb_tables()       ──>  storage.insert_dynamodb_tables()
  ├── generate_s3_buckets()            ──>  storage.insert_s3_buckets()
  ├── generate_lambda_functions()      ──>  storage.insert_lambda_functions()
  ├── generate_ebs_volumes()           ──>  storage.insert_ebs_volumes()
  ├── generate_nat_gateways()          ──>  storage.insert_nat_gateways()
  ├── generate_elb_instances()         ──>  storage.insert_elb_instances()
  ├── generate_ec2_metrics()           ──>  storage.insert_ec2_metrics()
  ├── generate_*_metrics()             ──>  storage.insert_*_metrics()
  ├── generate_instance_pricing()      ──>  storage.insert_instance_pricing()
  └── generate_ai_recommendations()    ──>  storage.insert_ai_recommendations()
```

### The Simulated Environment

| Resource | Count | Details |
| --- | --- | --- |
| EC2 instances | 8 | 2 prod-web, 1 prod-api, 1 prod-cache, 1 staging-web, 1 staging-api, 1 dev, 1 batch |
| RDS instances | 2 | 1 prod-postgres (r5.large), 1 staging-postgres (t4g.medium) |
| ElastiCache nodes | 3 | 1 prod Redis, 1 prod Memcached, 1 staging Redis |
| ECS services | 4 | Fargate services across prod + staging clusters |
| DynamoDB tables | 3 | On-Demand + Provisioned modes |
| S3 buckets | 4 | uploads, logs, backups, static-assets |
| Lambda functions | 4 | image-resizer, email-sender, log-processor, webhook-handler |
| EBS volumes | 8 | One per EC2 instance (gp2/gp3/io2) |
| NAT Gateways | 2 | One per VPC |
| ELB instances | 3 | ALBs for prod/staging |
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

**Pricing data** is generated synthetically with realistic price ranges based on AWS pricing models.

### Determinism

All random values use `numpy.random.default_rng(seed)`. Instance IDs are derived from names via MD5 hashes. The same seed always produces identical output.

---

## 3. How the Two Pipelines Connect

Both pipelines write to the same SQLite database (`data/cloud_optimizer.db`) through `storage.insert_*()`. Downstream modules read via `storage.get_*()`:

```python
# In any downstream module:
from storage import get_connection, get_daily_costs

conn = get_connection()
costs = get_daily_costs(conn, user_id, start_date="2024-01-01")
```

The ML engine, AI module, and optimizer all use `storage.get_*()` functions — they don't care whether the data is real or synthetic. Both pipelines produce data with identical schemas, isolated by `user_id`.
