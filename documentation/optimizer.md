# Optimizer Module

## Overview

The optimizer analyzes AWS resource inventory and metrics to produce cost-saving recommendations. It uses two complementary approaches: a **Linear Programming (LP) solver** for compute right-sizing and a **rule engine** for everything else.

```
                       ┌─────────────────────┐
                       │  engine.optimize()   │   single entry point
                       └──────────┬──────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                                  ▼
        ┌─────────────────┐               ┌─────────────────┐
        │  compute_lp.py  │               │    rules.py     │
        │   LP solver     │               │  threshold      │
        │                 │               │  checks         │
        │  EC2 rightsize  │               │  EC2 pricing    │
        │  RDS rightsize  │               │  RDS pricing    │
        └─────────────────┘               │  Lambda memory  │
                                          │  EBS volumes    │
                                          │  S3 tiering     │
                                          │  DynamoDB mode  │
                                          │  NAT endpoints  │
                                          │  ELB idle       │
                                          └─────────────────┘
```

**Why two systems?** The problems are structurally different:

- **Right-sizing** = "which of these 20 instance types is cheapest while still handling my load?" — a menu of alternatives with quantifiable specs. Perfect for LP.
- **Everything else** = "is this thing wasting money? yes/no" — threshold decisions with no alternatives to choose between. Rules are simpler and more transparent.

## LP Solver (`compute_lp.py`)

### Formulation

Binary LP that assigns each instance the cheapest candidate type from the pricing catalog.

```
Variables:    x[instance, candidate] ∈ {0, 1}

Objective:    minimize  Σ  cost(candidate) × x[instance, candidate]

Constraints:
  1. Assignment:  Σ x[i, c] = 1          each instance gets exactly one type
  2. CPU:         Σ vcpus(c) × x[i,c] ≥ min_vcpus[i]
  3. Memory:      Σ memory(c) × x[i,c] ≥ min_memory[i]   (when data available)
  4. Budget:      Σ total cost ≤ budget_cap                (optional)
```

### How requirements are computed

```
  P95 CPU utilization (from metrics)
       │
       ▼
  actual_vcpus_needed = (p95_cpu / 100) × current_vcpus
       │
       ▼
  min_vcpus = actual_vcpus_needed × headroom (default 1.3)
```

Example: instance with 4 vCPUs running at P95 CPU = 40%
- Actual need: 0.40 × 4 = 1.6 vCPUs
- With 30% headroom: 1.6 × 1.3 = 2.08 vCPUs
- LP can assign a 2-vCPU instance (cheaper)

### EC2 vs RDS differences

| | EC2 | RDS |
|---|---|---|
| CPU constraint | P95 from metrics | P95 from metrics |
| Memory constraint | P95 when available | Skipped (CloudWatch reports raw FreeableMemory bytes, not %) |
| Multi-AZ | N/A | Doubles candidate cost |
| Pricing source | `instance_pricing` table (service=EC2) | `instance_pricing` table (service=RDS) |

### Edge cases

- **No metrics** → instance skipped (can't compute requirements)
- **Stopped instances** → skipped (not running, no need to optimize)
- **LP infeasible** → logged warning, returns empty (e.g., instance needs more vCPUs than any candidate offers)
- **Optimal = current type** → no recommendation (already optimal)
- **Optimal costs more** → no recommendation (only recommend savings)

## Rule Engine (`rules.py`)

### Rule summary

| # | Function | Service | Trigger condition | Recommendation |
|---|----------|---------|-------------------|----------------|
| 1 | `check_ec2_pricing` | EC2 | on-demand + running 60+ days + RI pricing exists | Switch to reserved-1yr |
| 2 | `check_rds_pricing` | RDS | Same as above for RDS | Switch to reserved-1yr |
| 3 | `check_lambda_memory` | Lambda | avg memory < 50% of allocation | Downsize to next lower tier |
| 4 | `check_ebs_volumes` | EBS | gp2 type, OR unattached, OR idle >90% | Upgrade gp2→gp3, delete unused |
| 5 | `check_s3_buckets` | S3 | STANDARD class + <100 daily requests | Switch to INTELLIGENT_TIERING |
| 6 | `check_dynamodb_tables` | DynamoDB | PROVISIONED + both RCU/WCU utilization <50% | Switch to ON_DEMAND |
| 7 | `check_nat_gateways` | VPC | monthly cost >$30 | Add VPC gateway endpoints |
| 8 | `check_elb_idle` | ELB | 0 targets AND no traffic | Delete load balancer |

### Key thresholds and constants

```
EBS:       gp2 = $0.10/GB/mo    gp3 = $0.08/GB/mo     (20% savings)
S3:        STANDARD = $0.023/GB/mo    IT monitoring = $0.0025/1000 objects
DynamoDB:  RCU = $0.09/mo   WCU = $0.47/mo   (provisioned)
NAT:       $0.045/hr + $0.045/GB processed
Lambda:    tiers = [128, 256, 512, 1024, 2048, 3008] MB
```

### Safety checks

- **Lambda**: won't downsize if `avg + 2×std > new_tier` (prevents OOM on spikes)
- **EBS idle**: requires 7+ days of hourly metrics before flagging
- **ELB**: checks BOTH inventory (target_count=0) AND metrics (no traffic) — won't recommend deletion if there IS traffic but no targets (that's a misconfiguration, not waste)
- **DynamoDB**: requires BOTH read AND write utilization below threshold
- **EC2/RDS pricing**: requires 60+ days of metrics to prove it's a long-running workload

## Orchestrator (`engine.py`)

### Flow

```
optimize(conn, user_id)
    │
    ├── 1. DELETE old recommendations for user_id
    │
    ├── 2. Run LP solver
    │      ├── optimize_ec2()
    │      └── optimize_rds()
    │
    ├── 3. Run rule checks
    │      ├── check_ec2_pricing()
    │      ├── check_rds_pricing()
    │      ├── check_lambda_memory()
    │      ├── check_ebs_volumes()
    │      ├── check_s3_buckets()
    │      ├── check_dynamodb_tables()
    │      ├── check_nat_gateways()
    │      └── check_elb_idle()
    │
    ├── 4. Deduplicate by (resource_id, recommendation_type)
    │      └── keep highest monthly_savings
    │
    └── 5. INSERT into recommendations table + COMMIT
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `budget_cap` | `config.DEFAULT_BUDGET_CAP` (5000.0) | Max total compute spend for LP |
| `services` | all 8 services | Filter to run only specific service checks |

### Deduplication

If the LP and a rule both produce a recommendation for the same `(resource_id, recommendation_type)`, only the one with higher `monthly_savings` is kept. This prevents duplicate entries in the DB.

## Results (Synthetic Data)

Run against the synthetic mid-size SaaS database (`aws-SYNTHETIC-001`):

```
  Service    | Resource                       | Type                      | Savings
  ─────────────────────────────────────────────────────────────────────────────────────
  RDS        | prod-postgres-primary          | rightsize                 | $327.04/mo
  RDS        | staging-postgres               | rightsize                 |  $35.77/mo
  EC2 (×6)   | 6 on-demand instances          | pricing_plan_switch       | $208.42/mo
  EBS (×6)   | gp2 volumes + orphan + idle    | volume_type_upgrade/del   |  $12.60/mo
  Lambda     | webhook-handler                | memory_resize             |   $0.11/mo
  S3         | app-backups                    | storage_class_switch      |   $0.79/mo
  VPC (×2)   | 2 NAT gateways                | replace_with_endpoint     |   $5.67/mo
  ─────────────────────────────────────────────────────────────────────────────────────
  Total: 19 recommendations                                               $590.40/mo
```

**Note**: EC2 LP returned infeasible for `batch-processor` (c5.2xlarge at ~90% CPU — needs ~10.4 vCPUs with headroom but max candidate in catalog is 8 vCPUs). This is correct behavior.

## Usage

```python
from pathlib import Path
import storage
from optimizer import optimize

conn = storage.get_connection(Path('data/cloud_optimizer.db'))

# Run all checks
recs = optimize(conn, 'aws-SYNTHETIC-001')

# Run specific services only
recs = optimize(conn, 'aws-SYNTHETIC-001', services=['ec2', 'ebs'])

# With budget cap
recs = optimize(conn, 'aws-SYNTHETIC-001', budget_cap=3000.0)

# Results are also written to the recommendations table
stored = storage.get_recommendations(conn, 'aws-SYNTHETIC-001')
```

### Each recommendation dict contains

```python
{
    "service": "EC2",
    "resource_id": "i-abc123",
    "recommendation_type": "rightsize",           # or pricing_plan_switch, delete_unused, etc.
    "current_config": "c5.xlarge, on-demand",
    "recommended_config": "c5.large, on-demand",
    "current_monthly_cost": 124.00,
    "estimated_monthly_cost": 62.00,
    "monthly_savings": 62.00,
    "savings_percent": 50.0,
    "confidence": "high",                          # high, medium, or low
    "reasoning": "P95 CPU requires 1.8 vCPUs ..."
}
```

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| LP for compute, rules for rest | Approach C | LP needs a menu of alternatives with specs — only compute has this. Rules handle threshold checks. |
| P95 metric (not avg or max) | P95 | Avg hides spikes. Max is one-off outliers. P95 balances real workload. |
| 1.3x headroom | Default | 30% buffer for unexpected traffic. Configurable per call. |
| Clear + replace recs | DELETE before INSERT | Fresh results each run. No stale recs from previous configs. |
| RDS: CPU only | No memory constraint | CloudWatch `FreeableMemory` is raw bytes, not utilization %. Can't reliably convert. |
| Confidence levels | high/medium/low | high: >20% savings or >180 days data. medium: moderate. low: estimates (NAT). |

---

*Generated from Milestone 6: Optimizer Module. Tested against synthetic mid-size SaaS data (30 days, seed 42).*
