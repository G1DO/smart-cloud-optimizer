# Pricing Audit

## Summary

This audit compares the committed synthetic/demo EC2 prices against the snapshot-dated AWS EC2 catalog in `paper/aws_catalog.py`. The application database is not modified.

- Snapshot source: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv
- Snapshot date: 2026-06-30
- Publication: 2026-06-30T19:24:11Z
- Version: 20260630192411
- Filters: us-east-1 / US East (N. Virginia), Linux, shared tenancy, Pre-Installed S/W=NA, CapacityStatus=Used, License=No License required.

Key finding: the EC2 current-inventory monthly costs mostly match the snapshot basis, but several `instance_pricing` candidate rows are wrong or incomplete. The old manuscript-level recommendation count came from the stored `recommendations` table, which is stale relative to the current pricing table and recomputed optimizer/rule outputs.

## EC2 Candidate Price Rows

| instance_type | vcpus | memory_gb | on_demand_hourly | snapshot_od_hourly | od_hourly_delta_pct | reserved_1yr_hourly | snapshot_ri1y_hourly | issues |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c5.2xlarge | 8 | 16 | 0.34 | 0.34 | 0 | 0.2142 | 0.214 | matches snapshot within tolerance |
| c5.large |  |  | 0.085 | 0.085 | 0 |  | 0.054 | missing vcpus; missing memory; missing RI price |
| c5.xlarge |  |  | 0.17 | 0.17 | 0 |  | 0.107 | missing vcpus; missing memory; missing RI price |
| m5.2xlarge |  |  | 3.384 | 0.384 | 781.25 |  | 0.242 | missing vcpus; missing memory; on-demand price mismatch; missing RI price |
| m5.large |  |  | 0.164 | 0.096 | 70.833 |  | 0.06 | missing vcpus; missing memory; on-demand price mismatch; missing RI price |
| m5.xlarge |  |  | 0.26 | 0.192 | 35.417 |  | 0.121 | missing vcpus; missing memory; on-demand price mismatch; missing RI price |
| r5.large | 2 | 16 | 0.126 | 0.126 | 0 | 0.0794 | 0.079 | matches snapshot within tolerance |
| r5.xlarge | 4 | 32 | 0.252 | 0.252 | 0 | 0.1588 | 0.159 | matches snapshot within tolerance |
| t3.large |  |  | 0.0832 | 0.0832 | 0 |  | 0.0522 | missing vcpus; missing memory; missing RI price |
| t3.medium |  |  | 0.1092 | 0.0416 | 162.5 |  | 0.0261 | missing vcpus; missing memory; on-demand price mismatch; missing RI price |
| t3.micro |  |  | 0.078 | 0.0104 | 650 |  | 0.0065 | missing vcpus; missing memory; on-demand price mismatch; missing RI price |
| t3.small |  |  | 0.0208 | 0.0208 | 0 |  | 0.013 | missing vcpus; missing memory; missing RI price |
| t3.xlarge | 4 | 16 | 0.1664 | 0.1664 | 0 | 0.1048 | 0.1043 | matches snapshot within tolerance |

## EC2 Current Inventory Cost Rows

| instance_id | instance_type | pricing_model | monthly_cost | snapshot_price_basis | snapshot_monthly | monthly_delta_pct | issues |
| --- | --- | --- | --- | --- | --- | --- | --- |
| i-322ced9d357a71851 | m5.xlarge | reserved-1yr | 88.3 | ri1y | 88.33 | -0.034 | matches snapshot within tolerance |
| i-62c9b73536b4afb64 | c5.large | on-demand | 62.05 | od | 62.05 | 0 | matches snapshot within tolerance |
| i-6fcb9841d7a4596cc | m5.large | on-demand | 70.08 | od | 70.08 | 0 | matches snapshot within tolerance |
| i-7f2d2987eea6a58df | c5.2xlarge | on-demand | 248.2 | od | 248.2 | 0 | matches snapshot within tolerance |
| i-8a2f2d2dd5bc5cab6 | t3.large | on-demand | 60.74 | od | 60.736 | 0.007 | matches snapshot within tolerance |
| i-9ad0eb8ce137a7aa6 | r5.large | on-demand | 91.98 | od | 91.98 | 0 | matches snapshot within tolerance |
| i-f785f27a24b145b6a | t3.medium | on-demand | 30.37 | od | 30.368 | 0.007 | matches snapshot within tolerance |
| i-fe01442ffcbdd8b17 | m5.xlarge | reserved-1yr | 88.3 | ri1y | 88.33 | -0.034 | matches snapshot within tolerance |

## Recommendation Count Reconciliation

- Stored `recommendations` table: 19 rows, $590.40/mo.
- Recomputed current implementation rule-set path: 15 rows, $507.83/mo.
- Cause: the stored table includes six EC2 reserved-pricing rows from an older candidate catalog state; the current committed `instance_pricing` table only has reserved rates for two of those EC2 types. The paper therefore should not use the stored 19-row count as an authoritative fresh optimizer result.

## Paper-Side Usage-Hour RI Replay

The surrogate below uses observed EC2 metric coverage over trailing look-back windows and snapshot EC2 RI prices. It is not AWS Compute Optimizer, Cost Explorer, Azure Advisor, or a commercial FinOps tool.

The 7-, 30-, and 60-day rows are identical because the same six eligible on-demand EC2 instances have complete metric coverage in all three windows and the snapshot reserved/on-demand prices are static. The manuscript table collapses these identical rows to avoid padding.

| lookback_days | eligible_on_demand_instances | recommendations | current_monthly | estimated_monthly | savings_monthly | savings_pct | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 6 | 6 | 563.42 | 354.27 | 209.15 | 37.122 | surrogate; not AWS/Azure/commercial output |
| 30 | 6 | 6 | 563.42 | 354.27 | 209.15 | 37.122 | surrogate; not AWS/Azure/commercial output |
| 60 | 6 | 6 | 563.42 | 354.27 | 209.15 | 37.122 | surrogate; not AWS/Azure/commercial output |

## Paper Consequence

- Study I dollar claims based on the stored 19 recommendation rows are not publication-safe as headline results.
- Snapshot-repriced EC2 right-sizing rows and the paper-side usage-hour RI replay are the safer synthetic-account evidence generated by `paper/evidence_experiments.py`.
- Partial or failed MILP rows must be reported as non-comparable; their fallback costs are diagnostics only.
