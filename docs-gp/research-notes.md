# Historical research observations

These notes preserve previously recorded results, not current verification.
Future research conclusions belong in [Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111); reproducible machine evidence belongs with its inputs and execution record.

## Forecasting observations

The following tables are retained from an earlier analysis. The original note
reported walk-forward tests with an initial 120-day window and 30-day steps,
but `main` does not contain an exact input snapshot and executable run tied to
these numbers. They are not current verified accuracy, service guarantees, or
the runtime model-selection policy. The
[paper's open questions](OPEN_QUESTIONS.md) also identify older,
conflicting evaluation results. Current project conclusions belong in
[Notion project context](https://app.notion.com/p/28b0a821b3cc8061adebea034b7da111).

### Recorded horizon comparison (MAPE)

| Horizon | Naive | SeasonalNaive | ETS | Prophet | Winner |
|---------|-------|---------------|-----|---------|--------|
| 7 days | 40.5% | 16.0% | 9.2% | 7.9% | **Prophet** |
| 14 days | 22.9% | 17.9% | 10.5% | 9.8% | **Prophet** |
| 30 days | 25.7% | 14.6% | 10.4% | 9.5% | **Prophet** |
| 60 days | 25.5% | 14.9% | 10.8% | 22.2% | **ETS** |
| 90 days | 25.8% | 13.1% | 12.0% | 12.4% | **ETS** |
| 120 days | 32.0% | 15.7% | 13.0% | 34.5% | **ETS** |
| 180 days | 43.1% | 16.0% | 12.9% | 27.9% | **ETS** |
| 240 days | 30.9% | 22.7% | 20.6% | 26.8% | **ETS** |
| 300 days | 32.2% | 16.8% | 24.0% | 34.1% | **SeasonalNaive** |

### Recorded training-size comparison (30-day forecast MAPE)

| Training Data | Naive | SNaive | ETS | Prophet | Winner |
|---------------|-------|--------|-----|---------|--------|
| 7 days | 29.8% | **14.0%** | 297% | 1015% | **SNaive** |
| 14 days | 24.6% | **10.1%** | 22.8% | 1176% | **SNaive** |
| 1 month | 32.1% | **9.3%** | 12.9% | 46.7% | **SNaive** |
| 2 months | 42.5% | 10.3% | **9.7%** | 1552% | **ETS** |
| 3 months | 42.0% | 17.0% | **12.0%** | 968% | **ETS** |
| 6 months | 25.4% | 14.6% | **11.1%** | 16.8% | **ETS** |
| 1 year | 25.9% | 16.0% | **12.4%** | 14.9% | **ETS** |
| 14 months | 24.4% | 20.6% | **18.5%** | 19.4% | **ETS** |
| 1.5 years | 35.7% | 12.4% | **10.9%** | 12.2% | **ETS** |

## Optimizer observations

Previously recorded against the synthetic mid-size SaaS database
(`aws-SYNTHETIC-001`); these counts are historical observations, not assertions
about the current fixture or generator:

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

Original provenance note: *Generated from Milestone 6: Optimizer Module. Tested against synthetic mid-size SaaS data (30 days, seed 42).*
