# Evidence and Artifact Scope

This file lists missing experiments, baselines, ablations, statistical checks,
and reproducibility work. Do not add results to the paper until scripts produce
them.

## Evidence Generated on 2026-07-09

Command:

```bash
venv/bin/python paper/evidence_experiments.py
venv/bin/python paper/catalog_comparison.py
```

Generated files:

- `paper/results_baselines.json`
- `paper/results_ablations.json`
- `paper/results_runtime.json`
- `paper/table_baselines.tex`
- `paper/table_service_decomposition.tex`
- `paper/table_ablations.tex`
- `paper/table_runtime.tex`
- `paper/ec2_catalog_audit.md`
- `paper/pricing_audit.md`
- `paper/results_catalog_comparison.json`
- `paper/table_catalog_comparison.tex`
- `paper/results_ri_replay.json`
- `paper/table_ri_replay.tex`
- Deprecated compatibility aliases for the finalized conference source:
  `paper/results_commercial_like.json` and
  `paper/table_commercial_like.tex`
- `paper/numbers_evidence.tex`

What this generated within the documented evidence scope:

- Synthetic-account baseline comparison for current inventory, mean, median,
  P90, P95, P95 x 1.3, P99, and max-utilization sizing on a shared EC2
  snapshot price basis.
- Study II GWA lift-and-shift, bootstrap intervals, and percentile baselines
  are now included from the raw rerun in `paper/results_external.json`.
- Synthetic-account ablations for percentile `q`, headroom `h`, memory
  constraint on/off, budget cap levels, and implemented rule sets.
- Runtime measurements for the evidence script, baseline sweep, ablation
  sweep, rule-set ablation, and EC2 MILP stress sizes 100, 500, and 1,000.
- Bootstrap confidence intervals across the 10 synthetic compute resources.
- Catalog-comparison rerun with the committed demo DB catalog and the
  documented 28-type AWS EC2 snapshot in `paper/aws_catalog.py`.
- EC2 pricing audit comparing committed demo candidate/current prices against
  the snapshot catalog.
- Paper-side EC2 usage-hour RI replay baseline. The raw JSON retains
  7/30/60-day rows, but the generated LaTeX table collapses them because all
  reported values are identical on the synthetic account.
- Service-level Study I decomposition for the snapshot-basis P95 x 1.3 row:
  EC2 increases by 15.0%, RDS decreases by 91.2%, and aggregate
  compute-scope cost decreases by 19.0%.
- Study III look-back replay policies for 7, 30, and 60 days in
  `paper/policy_sim.py`, `paper/policy_tabular.tex`, and
  `paper/policy_tabular_ext.tex`.

Important generated finding:

- The implemented EC2 candidate set in the committed DB has only four valid
  EC2 candidates with CPU/memory specs. Under P95 x 1.3 and several high-q or
  high-headroom settings, the EC2 MILP is infeasible. The generated tables
  now mark these rows as partial and do not report comparable savings
  percentages. Fallback costs are retained only as JSON diagnostics.
- The catalog-comparison rerun shows that non-budget EC2 infeasibility
  disappears when EC2 current inventory and EC2 candidates are both repriced
  with the documented 28-type AWS snapshot catalog. Explicit per-service
  budget-cap rows remain infeasible, so the remaining boundary is budget
  feasibility rather than catalog coverage.
- Several committed demo EC2 candidate price rows are incorrect or incomplete
  relative to the snapshot catalog; original-demo-price right-sizing results
  should not be used as headline Study I savings.
- The repaired snapshot-basis Study I aggregate 19.0% compute-scope reduction
  is service-mixed and should not be reported without decomposition: EC2 cost
  increases under P95 x 1.3, while the aggregate reduction is dominated by
  demo-priced RDS right-sizing.
- The old 19-recommendation/$590 manuscript claim came from the stored
  `recommendations` table. The recomputed current implementation rule-set path
  reports 15 deduplicated rows and $507.83/mo. The manuscript now avoids the
  stale stored-table count as a headline result.

## Raw-Trace Reproducibility Triage

Updated on 2026-07-09: the GWA portion of Study II was restored and rerun from
raw public trace inputs. Azure remains pending because the raw Azure Public
Dataset V2 `vmtable.csv.gz` file is not present and `paper/fetch_traces.sh`
does not fetch it.

Commands run from the repository root:

```bash
export TRACE_DIR=/path/to/gwa-traces
./paper/fetch_traces.sh "$TRACE_DIR"
venv/bin/python paper/external_validation.py --trace-dir "$TRACE_DIR"
venv/bin/python paper/study2_reproducibility.py --trace-dir "$TRACE_DIR"
venv/bin/python paper/policy_sim.py --csv paper/trace_rnd_hourly.csv --prefix extPol --suffix _ext --gamma-star 0.63
```

GWA inputs restored and checked:

- `$TRACE_DIR/gwa_t_12_fastStorage.zip`
- `$TRACE_DIR/gwa_t_12_rnd.zip`
- `$TRACE_DIR/gwa_t_13_materna.zip`
- `$TRACE_DIR/gwa-t-12-fastStorage/` with 1,250 CSV files
- `$TRACE_DIR/gwa-t-12-rnd/` with 1,500 CSV files, grouped into 500
  VMs by filename stem
- `$TRACE_DIR/gwa-t-13-materna/` with 1,593 CSV files; the rerun uses
  Materna-Trace-3 with 547 usable VMs

Generated or updated GWA outputs:

- `paper/numbers_external.tex`
- `paper/external_mape_tabular.tex`
- `paper/figures/fig_ext_series.pdf`
- `paper/trace_rnd_hourly.csv`
- `paper/results_external.json`
- `paper/table_external_baselines.tex`
- `paper/trace_provenance.md`
- `paper/numbers_policy_ext.tex`
- `paper/policy_tabular_ext.tex`
- `paper/figures/fig_policy_gamma_ext.pdf`
- `paper/results_policy_ext.json`

Checksums and runtime:

- `paper/trace_provenance.md` records SHA256 checksums for the three GWA zip
  files and manifest hashes for the extracted CSV trees.
- GWA fetch/extract wall time: 176.06 seconds.
- `paper/external_validation.py` wall time: 169.12 seconds.
- `paper/study2_reproducibility.py` helper-stage subtotal: 127.34 seconds; its
  internal timing reports 120.58 seconds for raw quantile scanning and 4.63
  seconds for the baseline grid plus bootstrap in the latest recorded rerun.
- Real-trace policy rerun wall time: 4.51 seconds.

New Study II statistical evidence:

- Per-VM bootstrap 95% confidence intervals were added for restored GWA
  right-sizing savings. For the deployed P95 x 1.3 row: fastStorage saves
  33.6% [24.5, 41.8], Rnd saves 33.1% [19.3, 46.3], and Materna saves
  74.2% [71.4, 76.8].
- The aggregate restored-GWA saving is 41.8% [35.9, 47.5], rising to 63.4%
  [59.7, 67.0] with one-year RI pricing.
- `paper/table_external_baselines.tex` and `paper/results_external.json` now
  include a raw-trace baseline grid for lift-and-shift, mean, median, P90, P95,
  P99, max utilization, and the deployed P95 x 1.3 method.

Azure status:

- Expected raw input: Azure Public Dataset V2 headerless `vmtable.csv.gz`.
- Present locally: no.
- Checksum: missing until the raw file is restored.
- Rerun command when available:

```bash
venv/bin/python paper/azure_validation.py --vmtable /path/to/vmtable.csv.gz
```

Expected Azure outputs after restoration:

- `paper/numbers_azure.tex`
- `paper/results_azure.json`

Why Study II is no longer fully blocked by GWA but still has an Azure artifact
gap: Bitbrains and Materna now have raw-input checksums, a raw rerun, bootstrap
CIs, runtime, and a baseline grid. The Azure boundary case remains based on the
existing generated aggregate until `vmtable.csv.gz` is restored, checksummed,
rerun, and extended with CIs/grid.

Experiments still not run in this workspace:

- Azure runtime, CIs, and percentile ablations because raw `vmtable.csv.gz` is
  not present.
- Direct AWS Compute Optimizer, Azure Advisor, Savings Plans, or commercial
  FinOps baselines because no direct comparable tool output exists in the
  repository. A labeled paper-side replay baseline was generated, but it is
  not a commercial-tool baseline.
- SLO/performance validation because the repository contains no live SLO,
  latency, or error-rate outcomes tied to the recommendations.
- A full all-SKU AWS EC2 catalog sensitivity; the generated snapshot comparison
  uses the 28 t3/m5/c5/r5 types already documented in `paper/aws_catalog.py`.

## Priority 0: Submission-Blocking Checks

- Replace author and affiliation placeholders in `conference_draft.tex`.
- Install or document a LaTeX toolchain and verify `paper/build_conference.sh`.
- Re-run paper scripts from raw inputs and record exact commands where not
  already covered by `paper/trace_provenance.md`:
  - `paper/make_figures.py`
  - `paper/external_validation.py`
  - `paper/azure_validation.py`
  - `paper/policy_sim.py` on synthetic demand
  - `paper/policy_sim.py` on real Rnd demand
- Record Python, package, PuLP/CBC, OS, and LaTeX versions.
- Add expected generated-file hashes for the final artifact bundle.
- Run a final reference audit: verify each bibliography entry resolves, add DOI
  or stable URL metadata where available, and do not invent missing citation
  details.
- Restore and rerun the remaining raw Azure trace when the dataset is
  available:
  - Download Azure Public Dataset V2 `vmtable.csv.gz` from the dataset release
    documented in `paper/azure_validation.py`.
  - `venv/bin/python paper/azure_validation.py --vmtable /path/to/vmtable.csv.gz`
- Add SHA256 checksum and elapsed parse/optimization runtime for Azure after
  restoration.

## Baselines Needed

### Direct Commercial Baselines

Use only if the same workload/account can be evaluated directly.

- AWS Compute Optimizer.
- AWS Cost Explorer Reserved Instance recommendations.
- AWS Savings Plans recommendations.
- Azure Advisor or Azure reservation recommendations.
- A commercial FinOps recommender, if accessible.

Required caution: do not claim superiority over any commercial system unless
the exact same workload was compared directly.

### Paper-Side Replay Baselines

Use if direct commercial services cannot be run.

- Historical replay that chooses reservation quantity by minimizing cost over a
  7/30/60-day look-back window.
- Study III now includes this as a paper-side look-back replay policy; direct
  commercial outputs are still missing.
- Savings-maximizing reservation replay under the same single-resource
  abstraction as Study III.
- Greedy reservation sizing by sorted historical usage.

Required label: call these "paper-side recency-window replay baselines" or
"paper-side usage-hour replay baselines," not AWS/Azure implementations or
evidence of prevailing industry behavior.

### Simple Technical Baselines

- Like-for-like lift-and-shift.
- Mean utilization times headroom.
- Median utilization times headroom.
- P75, P90, P95, and P99 without headroom.
- P95 x 1.3, current deployed rule.
- Max utilization.
- Newsvendor `1 - gamma`.
- SAA stochastic program.
- Dual-capacity observable-state and causal variants.

## Ablations Needed

### Right-Sizing Percentile

- Test `q` in `{0.50, 0.75, 0.90, 0.95, 0.99}`.
- Report cost, savings, downsized count, upsized count, and risk proxy.

### Headroom

- Test `h` in `{1.0, 1.1, 1.3, 1.5}`.
- Report cost/savings and risk proxy.

### Memory Constraint

- CPU-only.
- CPU plus observed memory utilization.
- Provisioned-memory floor, as in Azure.
- No-memory-resource exclusion.

### Budget Cap

- No cap.
- Current monthly bill cap.
- 90% of current monthly bill.
- 75% of current monthly bill.
- Infeasible cap, to report failure behavior.

### Rule Set

- MILP only.
- Reserved-pricing rules only.
- Waste-removal rules only.
- Each rule removed one at a time.
- All rules.

### Forecasting and Anomaly Context

- Optimizer with anomaly filtering.
- Optimizer without anomaly filtering.
- Fixed ETS versus fixed seasonal-naive versus selected model.
- Only include this ablation in the paper if forecasts affect decisions;
  otherwise keep forecasting as monitoring context.

## Runtime and Scalability Experiments

- Measure wall-clock runtime, peak memory, and solver status for:
  - Synthetic account.
  - Bitbrains fastStorage.
  - Bitbrains Rnd.
  - Materna.
  - Azure 2,000-VM MILP validation sample.
  - Azure full vectorized assignment.
  - Policy simulation on synthetic demand.
  - Policy simulation on real Rnd demand.
- MILP stress test:
  - Resources in `{100, 500, 1,000, 5,000}`.
  - Candidate catalog sizes in `{28, 50, 100}`.
  - With and without budget cap.
- Report timeout policy, infeasibility behavior, and objective gap if using a
  time-limited solver.

## Confidence Intervals and Statistical Tests

- Bootstrap confidence intervals for Azure right-sizing savings after raw
  `vmtable.csv.gz` restoration; GWA CIs are now recorded in
  `paper/results_external.json`.
- Bootstrap confidence intervals for policy-simulation cost ratios.
- Multiple chronological train/test split sensitivity beyond 50/60/70.
- Confidence intervals for Azure cost-negative result.
- Correct or scope multiple forecast comparisons.
- Keep current DM/Wilcoxon tests for forecast comparisons, but avoid
  superiority claims when differences are not significant.

## SLO and Performance-Risk Validation

No real SLO data is currently present. Add proxy validation before claiming
right-sizing is performance-safe.

- Fraction of historical observations exceeding the recommended capacity.
- Magnitude and duration of exceedance above recommended capacity.
- Upsize/downsize ratio and resources requiring upsizing.
- Tail-risk estimate under P95 x 1.3 versus lower percentiles.
- If live SLOs exist, compare error rate/latency before and after
  recommendation.

## Dataset Expansion

- Live AWS account validation:
  - Run collector.
  - Run optimizer.
  - Compare recommendations to actual account settings.
  - Measure realized savings only after changes are truly applied.
- Modern trace:
  - Prefer post-2019 per-VM data with provisioned CPU, provisioned memory, CPU
    usage, and memory usage.
  - If memory is unavailable, treat the trace as a metric-semantics boundary
    condition, not primary validation.

## Paper Artifacts To Add After Experiments

- Expanded dataset summary table.
- Baseline comparison table.
- Ablation table.
- Runtime/scalability table.
- SLO/performance-risk table or risk-proxy table.
- Qualitative recommendation examples table.
- Reproducibility appendix with exact commands, versions, and checksums.
