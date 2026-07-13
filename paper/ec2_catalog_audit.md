# EC2 Catalog Audit

## Summary

The committed synthetic database contains 13 EC2 price rows, but only four are solver-valid because the MILP candidate filter requires a positive monthly price and a nonmissing vCPU field. Memory-constrained runs also need memory_gb. The nine EC2 rows excluded from the solver all lack vCPU and memory specifications.

The repository already contains documented, snapshot-dated EC2 data in `paper/aws_catalog.py`, so no new scraped or undocumented pricing data was introduced. This snapshot is a 28-type t3/m5/c5/r5 candidate set used by the existing external-validation scripts; it is not a claim to cover every EC2 SKU in AWS.

No new fetcher was added for this run because the existing repository snapshot is sufficient to test whether the synthetic-account infeasibility is caused by the four-row demo candidate set. A full all-SKU AWS Price List ingestion remains separate future artifact work.

Result: EC2 infeasibility disappears for non-budget baseline and ablation rows with the shared-basis snapshot EC2 catalog; remaining EC2 infeasibility is confined to explicit per-service budget-cap rows.

## Current Synthetic DB Schema

| cid | name | type | notnull | dflt_value | pk |
| --- | --- | --- | --- | --- | --- |
| 0 | id | INTEGER | 0 |  | 1 |
| 1 | service | TEXT | 1 |  | 0 |
| 2 | instance_type | TEXT | 1 |  | 0 |
| 3 | vcpus | INTEGER | 0 |  | 0 |
| 4 | memory_gb | REAL | 0 |  | 0 |
| 5 | category | TEXT | 0 |  | 0 |
| 6 | on_demand_hourly | REAL | 1 |  | 0 |
| 7 | reserved_1yr_hourly | REAL | 0 |  | 0 |
| 8 | reserved_3yr_hourly | REAL | 0 |  | 0 |
| 9 | spot_hourly | REAL | 0 |  | 0 |
| 10 | on_demand_monthly | REAL | 1 |  | 0 |
| 11 | reserved_1yr_monthly | REAL | 0 |  | 0 |
| 12 | reserved_3yr_monthly | REAL | 0 |  | 0 |
| 13 | spot_monthly | REAL | 0 |  | 0 |

## Original EC2 Price Rows

| instance_type | vcpus | memory_gb | on_demand_hourly | on_demand_monthly | reserved_1yr_hourly | reserved_1yr_monthly |
| --- | --- | --- | --- | --- | --- | --- |
| c5.2xlarge | 8 | 16.0 | 0.34 | 248.2 | 0.2142 | 156.37 |
| c5.large |  |  | 0.085 | 62.050000000000004 |  |  |
| c5.xlarge |  |  | 0.17 | 124.10000000000001 |  |  |
| m5.2xlarge |  |  | 3.384 | 2470.3199999999997 |  |  |
| m5.large |  |  | 0.164 | 119.72 |  |  |
| m5.xlarge |  |  | 0.26 | 189.8 |  |  |
| r5.large | 2 | 16.0 | 0.126 | 91.98 | 0.0794 | 57.96 |
| r5.xlarge | 4 | 32.0 | 0.252 | 183.96 | 0.1588 | 115.92 |
| t3.large |  |  | 0.0832 | 60.736 |  |  |
| t3.medium |  |  | 0.1092 | 79.71600000000001 |  |  |
| t3.micro |  |  | 0.078 | 56.94 |  |  |
| t3.small |  |  | 0.0208 | 15.184 |  |  |
| t3.xlarge | 4 | 16.0 | 0.1664 | 121.47 | 0.1048 | 76.5 |

## Original Rows Excluded by the Solver Filter

| instance_type | vcpus | memory_gb | on_demand_monthly | exclusion_reason |
| --- | --- | --- | --- | --- |
| t3.small |  |  | 15.184 | missing vcpus; missing memory_gb for memory-constrained runs |
| t3.micro |  |  | 56.94 | missing vcpus; missing memory_gb for memory-constrained runs |
| t3.large |  |  | 60.736 | missing vcpus; missing memory_gb for memory-constrained runs |
| c5.large |  |  | 62.050000000000004 | missing vcpus; missing memory_gb for memory-constrained runs |
| t3.medium |  |  | 79.71600000000001 | missing vcpus; missing memory_gb for memory-constrained runs |
| m5.large |  |  | 119.72 | missing vcpus; missing memory_gb for memory-constrained runs |
| c5.xlarge |  |  | 124.10000000000001 | missing vcpus; missing memory_gb for memory-constrained runs |
| m5.xlarge |  |  | 189.8 | missing vcpus; missing memory_gb for memory-constrained runs |
| m5.2xlarge |  |  | 2470.3199999999997 | missing vcpus; missing memory_gb for memory-constrained runs |

## Snapshot EC2 Catalog Source

- Source file: `paper/aws_catalog.py`
- AWS source URL: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv
- Snapshot date: 2026-06-30
- Publication timestamp: 2026-06-30T19:24:11Z
- Version: 20260630192411
- Region/location: us-east-1 / US East (N. Virginia)
- Operating system: Linux
- Tenancy: Shared
- Pre-installed software: NA
- Capacity status: Used
- License: No License required
- Hours per month conversion: 730.0
- Candidate scope: 28 committed t3/m5/c5/r5 EC2 types with on-demand, 1-year reserved, vCPU, and memory fields; not all AWS EC2 SKUs

Snapshot entries excluded by the same solver-validity filter:

None. All 28 committed snapshot entries have price, vCPU, and memory fields.

## Catalog-Comparison Result

| catalog | ec2_raw | ec2_valid | p95_status | p95_optimized_monthly | p95_savings_pct | non_budget_ec2_infeasible_rows | budget_ec2_infeasible_rows | boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original demo DB | 13 | 4 | Partial (EC2 Infeasible) |  |  | 9 | 4 | catalog coverage |
| AWS snapshot shared EC2 basis | 28 | 28 | Optimal | 1005.65 | 19.003 | 0 | 4 | service budget cap |

## Interpretation

- The original demo catalog failure is explained by candidate coverage: high-percentile/headroom EC2 requirements exceed the four solver-valid EC2 candidates.
- With the snapshot EC2 catalog, the non-budget P95 x 1.3 and related percentile/headroom rows become feasible. This supports treating the original infeasibility as a catalog-completeness boundary.
- Explicit budget-cap rows can still be infeasible under the snapshot catalog because the conservative EC2 assignment costs more than the EC2 service-level cap. That is a separate policy/budget boundary, not hidden solver failure.
- These results do not compare against AWS Compute Optimizer, Azure Advisor, Savings Plans recommendations, or commercial FinOps tools.

## Reproduction

```bash
venv/bin/python paper/evidence_experiments.py
venv/bin/python paper/catalog_comparison.py
./paper/build_conference.sh
```
