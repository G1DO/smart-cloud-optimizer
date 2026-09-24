# Optimizer Module

## Overview

The optimizer analyzes AWS resource inventory and metrics to produce cost-saving recommendations. It uses two complementary approaches: a **Linear Programming (LP) solver** for compute right-sizing and a **rule engine** for everything else.

It reads observed metrics and pricing; ML forecasts are not inputs to the current
optimizer. Recommendation generation writes SQLite and does not apply AWS changes.

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
- A candidate must have at least 2.08 vCPUs, so a 2-vCPU instance is insufficient.

### EC2 vs RDS differences

| | EC2 | RDS |
|---|---|---|
| CPU constraint | P95 from metrics | P95 from metrics |
| Memory constraint | P95 when available | Skipped (the implemented RDS collector does not fetch memory) |
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
| 1 | `check_ec2_pricing` | EC2 | on-demand + currently running + metric timestamps span 60+ days + cheaper RI pricing | Switch to reserved-1yr |
| 2 | `check_rds_pricing` | RDS | on-demand + metric timestamps span 60+ days + cheaper RI pricing | Switch to reserved-1yr |
| 3 | `check_lambda_memory` | Lambda | avg memory < 50% of allocation | Downsize to next lower tier |
| 4 | `check_ebs_volumes` | EBS | gp2 type, OR unattached, OR idle >90% | Upgrade gp2→gp3, delete unused |
| 5 | `check_s3_buckets` | S3 | STANDARD class + <100 daily requests | Switch to INTELLIGENT_TIERING |
| 6 | `check_dynamodb_tables` | DynamoDB | PROVISIONED + both RCU/WCU utilization <50% | Switch to ON_DEMAND |
| 7 | `check_nat_gateways` | VPC | monthly cost ≥$30 | Add VPC gateway endpoints |
| 8 | `check_elb_idle` | ELB | 0 targets AND traffic check does not establish ≥100 average daily requests (see limits below) | Delete load balancer |

### Key thresholds and constants

```
EBS:       gp2 = $0.10/GB/mo    gp3 = $0.08/GB/mo     (20% savings)
S3:        STANDARD = $0.023/GB/mo    IT monitoring = $0.0025/1000 objects
DynamoDB:  RCU = $0.09/mo   WCU = $0.47/mo   (provisioned)
NAT:       $0.045/hr + $0.045/GB processed
Lambda:    tiers = [128, 256, 512, 1024, 2048, 3008] MB
```

### Checks and limits

- **Lambda**: skips downsizing when `avg + 2×std > new_tier`. This is a statistical
  estimate from observed memory usage, not a guarantee against out-of-memory failures.
- **EBS idle**: requires at least 168 metric rows (assumed hourly) before flagging;
  row count alone does not establish continuous coverage.
- **ELB**: requires zero targets, but checks traffic only with at least 168 metric
  rows and a `request_count` column. Missing or shorter history leaves the traffic
  flag false and can still produce a high-confidence deletion recommendation.
  With sufficient history, the rule skips deletion at ≥100 average daily requests.
  Independently check workload use and telemetry before acting on a deletion recommendation.
- **DynamoDB**: requires BOTH read AND write utilization below threshold
- **EC2/RDS pricing**: requires a 60-day span between the earliest and latest metric
  timestamps; it does not verify uninterrupted operation or future commitment needs.

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
| `budget_cap` | `config.DEFAULT_BUDGET_CAP` (5000.0) | Cap applied separately to each EC2/RDS LP, not one combined account budget |
| `services` | all 8 services | Select checks; see `ALL_SERVICES` in [engine.py](../../../optimizer/engine.py) |

Every run deletes **all** previous recommendations for the selected user before
generating replacements, including when `services` selects only some checks.
An infeasible LP contributes no sizing recommendations; independent rules can
still produce results. Rule recommendations are outside the LP budget constraint.

### Deduplication

If the LP and a rule both produce a recommendation for the same `(resource_id, recommendation_type)`, only the one with higher `monthly_savings` is kept. This prevents duplicate entries in the DB.

Different action types for one resource remain separate. Their savings may
overlap, so the CLI's summed savings are not a validated combined execution plan.

## Usage

Run from the repository root with dependencies installed. Stop writers to the
source database before copying it; if it is live, use SQLite's backup API to
include committed WAL contents. Keep the committed fixture unchanged:

```bash
optimizer_tmp=$(mktemp -d)
cp data/cloud_optimizer.db "$optimizer_tmp/cloud_optimizer.db"
python -m optimizer --user-id aws-SYNTHETIC-001 \
  --db-path "$optimizer_tmp/cloud_optimizer.db"
```

The disposable copy receives the recommendations. Inspect it before removing
the temporary directory. Use `python -m optimizer --help` for service and budget
arguments. Library callers can pass a connection from
`storage.get_connection(copy_path)` to `optimizer.optimize()`; close it afterward.

The LP code explicitly uses PuLP's `PULP_CBC_CMD`. Verify that solver in the
active Python environment:

```bash
python -c "from pulp import PULP_CBC_CMD; print(PULP_CBC_CMD().available())"
```

An available executable path is expected. Installing a system `cbc` executable
alone does not change the solver selected by this code.

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

## Design rationale

| Decision | Choice | Why |
|----------|--------|-----|
| LP for compute, rules for rest | Approach C | LP needs a menu of alternatives with specs — only compute has this. Rules handle threshold checks. |
| P95 metric (not avg or max) | P95 | Avg hides spikes. Max is one-off outliers. P95 balances real workload. |
| 1.3x headroom | Default | 30% buffer for unexpected traffic. Configurable per call. |
| Clear + replace recs | DELETE before INSERT | Fresh results each run. No stale recs from previous configs. |
| RDS: CPU only | No memory constraint | Original rationale: `FreeableMemory` is bytes, not utilization %. The current collector does not fetch this metric. |
| Confidence levels | high/medium/low | Rule-specific heuristic labels; see [`compute_lp.py`](../../../optimizer/compute_lp.py) and [`rules.py`](../../../optimizer/rules.py). They are not calibrated probabilities or proof an action is safe. |
