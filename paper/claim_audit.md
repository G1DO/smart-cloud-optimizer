# Claim Audit

Scope: this audit targets `paper/conference_draft.tex`, the active IEEE-style
conference manuscript. Classifications are conservative and should be revisited
after new experiments are added.

## 1. Core framing claim

Classification: SUPPORTED

Current wording:
"This paper operationalizes a cloud cost-optimization pipeline and empirically
quantifies when conservative P95-based right-sizing and reservation heuristics
diverge from capacity-reservation theory under intermittent demand surges."

Support:
- Implemented optimizer: `optimizer/compute_lp.py`, `optimizer/rules.py`,
  `optimizer/engine.py`.
- Forecasting and evaluation helpers: `ml_engine/forecaster.py`,
  `paper/paperlib.py`.
- Policy simulation: `paper/policy_sim.py`,
  `paper/results_policy.json`, `paper/results_policy_ext.json`.
- Manuscript macros: `paper/numbers_policy.tex`,
  `paper/numbers_policy_ext.tex`.

Risk:
Low, if the manuscript keeps clear that the newsvendor and dual-capacity
results are paper-side simulations, not deployed production behavior.

Safer IEEE-style wording:
"We use an implemented cloud cost-optimization pipeline as a reproducible
vehicle for measuring when conservative P95-based right-sizing diverges from
price-aware reservation sizing."

## 2. Implemented pipeline claim

Classification: SUPPORTED

Current wording:
"The system context includes telemetry collection, forecasting, mixed-integer
right-sizing, reserved-pricing checks, and service-level waste rules."

Support:
- AWS collection modules: `aws_collector/`.
- Forecast models: `ml_engine/forecaster.py`.
- MILP right-sizing: `optimizer/compute_lp.py`.
- Pricing and waste rules: `optimizer/rules.py`.
- Orchestration: `optimizer/engine.py`.
- System docs: `README.md`, `documentation/ARCHITECTURE.md`.

Risk:
Medium if reviewers read this as a research contribution by itself.

Safer IEEE-style wording:
"These implementation features provide system context; the research evaluation
focuses on right-sizing and reservation-policy behavior."

## 3. Synthetic-account savings claim

Classification: REVISED / OLD WORDING TOO STRONG

Old wording:
"On the repository's synthetic AWS account, the implemented optimizer emits
19 recommendations worth $588.40--$590.40 per month, or 27.0% of the
inventory bill before overlap adjustment."

Support:
- The old wording is supported only as a query over the stored
  `recommendations` table via `paper/make_figures.py` and `paper/numbers.tex`.
- `paper/pricing_audit.md` shows that the stored table is stale relative to
  the current committed `instance_pricing` table and recomputed rule outputs.
- `paper/results_ablations.json` reports the recomputed implementation
  rule-set path as 15 deduplicated recommendations and $507.83/mo under the
  committed demo DB path.
- `paper/results_baselines.json` reports the corrected snapshot-repriced
  P95 x 1.3 compute row as feasible under the synthetic compute-scope basis,
  with EC2 increasing by 15.0%, RDS decreasing by 91.2%, and aggregate
  compute-scope cost decreasing by 19.0%.
- `paper/table_service_decomposition.tex` and `paper/numbers_evidence.tex`
  surface the service-level split so the aggregate is not presented as an
  unqualified optimizer win.
- The canonical `paper/results_ri_replay.json` reports the paper-side EC2
  usage-hour RI replay as 6 recommendations and $209.15/mo savings on eligible
  EC2 on-demand spend; `paper/table_ri_replay.tex` collapses identical
  7/30/60-day rows into one table row. The legacy-named JSON is retained only
  as a deprecated compatibility alias for the finalized conference source.

Risk:
Critical if the old 19-row/$590 figure is presented as a fresh optimizer or
publication-headline result. The stored recommendation table includes EC2
reserved-pricing recommendations from an older catalog state.

Safer IEEE-style wording:
"On the repository's synthetic account, after EC2 snapshot repricing, the
P95 x 1.3 compute row is feasible but service-mixed: EC2 cost increases while
RDS cost decreases sharply, producing an aggregate 19.0% compute-scope
decrease. Because RDS remains demo-priced, this is a method-illustrative
boundary-condition result, not a production savings claim."

## 4. Real-trace right-sizing savings claim

Classification: SUPPORTED FOR GWA RERUN

Current wording:
"On restored raw Bitbrains and Materna GWA traces priced against a
snapshot-dated AWS catalog, the right-sizing MILP saves 41.8% in aggregate
(bootstrap 95% CI 35.9--47.5%) relative to a like-for-like lift-and-shift
baseline."

Support:
- `paper/results_external.json`.
- `paper/numbers_external.tex`.
- `paper/external_validation.py`.
- `paper/study2_reproducibility.py`.
- `paper/table_external_baselines.tex`.
- `paper/trace_provenance.md`.
- AWS catalog snapshot: `paper/aws_catalog.py`.

Risk:
Medium. The GWA traces are now raw-rerun and checksummed, but they are old,
not AWS-native, and priced using a 2026 AWS catalog.

Safer IEEE-style wording:
"Under this like-for-like AWS catalog mapping, the MILP reduces restored GWA
mapped monthly cost by..."

## 5. Azure boundary-condition claim

Classification: SUPPORTED BY GENERATED ARTIFACT / RAW INPUT PENDING

Current wording:
"The Azure Public Dataset V2 arm remains a boundary case from the committed
generated artifact pending restoration of the raw `vmtable.csv.gz`: max-based
CPU percentiles and unobserved memory make right-sizing alone cost-negative
(-3.8%)."

Support:
- `paper/results_azure.json`.
- `paper/numbers_azure.tex`.
- `paper/azure_validation.py`.
- `paper/trace_provenance.md` records that the raw Azure input is absent.

Risk:
Medium-high until `vmtable.csv.gz` is restored, checksummed, rerun, and
extended with CIs/grid. The Azure data semantics differ from Bitbrains/Materna;
this should remain a boundary condition, not a direct contradiction of all P95
sizing.

Safer IEEE-style wording:
"The Azure arm exposes a metric-semantics boundary condition for the deployed
rule."

## 6. Forecasting claim

Classification: SUPPORTED

Current wording:
"Forecasting is useful for monitoring but not decisive for the cost results."

Support:
- Synthetic CV table: `paper/mape_tabular.tex`,
  `paper/results.json`.
- External CV table: `paper/external_mape_tabular.tex`,
  `paper/results_external.json`.
- Forecast models: `ml_engine/forecaster.py`.

Risk:
Low. This is appropriately cautious.

Safer IEEE-style wording:
"The current evidence supports using forecasts for monitoring and context,
not for claiming forecast-driven optimization savings."

## 7. Newsvendor price-of-conservatism claim

Classification: SUPPORTED

Current wording:
"At gamma=0.63, using the high-percentile capacity rule as a reservation-sizing
rule realizes 101.8% and 153.5% of on-demand cost, whereas the newsvendor
fractile realizes 73.6% and 86.2%; look-back replay policies are also
reported."

Support:
- `paper/policy_sim.py`.
- `paper/results_policy.json`.
- `paper/results_policy_ext.json`.
- `paper/numbers_policy.tex`.
- `paper/numbers_policy_ext.tex`.
- `paper/policy_tabular.tex` and `paper/policy_tabular_ext.tex` now include
  7-, 30-, and 60-day look-back replay rows.

Risk:
Medium if readers think the deployed system actually sizes reservations this
way or if the look-back rows are mistaken for AWS/Azure/third-party output.
The manuscript must keep "counterfactually read as reservation sizing" and
"paper-side recency-window baseline" language.

Safer IEEE-style wording:
"When the right-sizing rule is counterfactually reused for reservation sizing,
the held-out simulation shows a large cost gap relative to price-aware
newsvendor and look-back replay policies; these replay rows are not commercial
tool outputs."

## 8. Dual-capacity policy insight

Classification: PARTIALLY SUPPORTED

Current wording:
"The dual-capacity policy adds little on the synthetic daily series but
materially improves the real trace, where surge states persist long enough
for causal activation to retain most of the value."

Support:
- `paper/results_policy.json`.
- `paper/results_policy_ext.json`.
- `paper/policy_sim.py`.

Risk:
Medium. It is a simplified aggregate simulation, not a full contract-policy
implementation.

Safer IEEE-style wording:
"In the simplified aggregate simulation, dual-capacity policies are more
valuable on the real trace than on the synthetic daily series."

## 9. "No commercial superiority" claim

Classification: SUPPORTED AS A LIMITATION

Current wording:
"We do not claim superiority over AWS, Azure, or commercial FinOps
recommenders; no direct evidence for that comparison exists in the repository."

Support:
- No direct commercial baseline files or results exist in `paper/` or tests.
- `paper/results_ri_replay.json` and `paper/table_ri_replay.tex` add a labeled
  paper-side usage-hour EC2 reservation replay baseline, but explicitly mark
  it as not AWS/Azure/commercial output. The corresponding legacy-named files
  are deprecated compatibility aliases for the finalized conference source.
- `paper/reviewer_risks.md` and `paper/experiments_needed.md` list direct
  commercial evidence as still missing.

Risk:
Low. This reduces reviewer risk.

Safer IEEE-style wording:
Keep current wording.

## 10. Reproducibility claim

Classification: PARTIALLY SUPPORTED / GWA IMPROVED

Current wording:
"Reported result values are emitted by scripts in the paper folder; restored
GWA Study II inputs include checksums, runtime, bootstrap intervals, and a
baseline grid."

Support:
- Generated macro files and JSON results exist.
- Scripts: `paper/make_figures.py`, `paper/external_validation.py`,
  `paper/study2_reproducibility.py`, `paper/azure_validation.py`,
  `paper/policy_sim.py`.
- Build script exists: `paper/build_conference.sh`.
- `paper/trace_provenance.md` records GWA zip SHA256 checksums, extracted-tree
  manifest hashes, commands, and helper runtime.

Risk:
Medium. The conference draft builds locally and GWA restoration has been
verified. Azure raw `vmtable.csv.gz`, package/version inventory, and final
artifact hashes still need to be added for a full artifact release.

Safer IEEE-style wording:
"The committed manuscript values are script-generated; the restored GWA trace
path is checksummed and rerun, while Azure and final dependency/version hashes
remain artifact work."

## 11. Full `(s,S)` policy claim

Classification: PARTIALLY SUPPORTED

Potential unsafe wording (not used in the current draft):
"The deployed system realizes Chen et al.'s full dynamic `(s,S)` policy."

Support:
None in the implementation. The manuscript currently does not make this claim.

Risk:
Critical if introduced.

Safer IEEE-style wording:
"The dual-capacity simulation is a static step toward the base/supplementary
structure; full dynamic cancellation and renewal remain future work."

## 12. LLM-advisor contribution claim

Classification: TOO STRONG / SHOULD BE WEAKENED

Potential unsafe wording (not used in the current draft):
"The LLM advisor improves optimization or savings."

Support:
The implementation contains `ai_module/`, but the paper does not evaluate its
dollar impact.

Risk:
High if presented as a research contribution.

Safer IEEE-style wording:
"The LLM advisor is part of the surrounding application and is not evaluated
in this paper."

## 13. Runtime/scalability claim

Classification: NEEDS EVIDENCE

Potential unsafe wording (not used in the current draft):
"The system scales to large fleets."

Support:
- `paper/evidence_experiments.py` generates `paper/results_runtime.json` and
  `paper/table_runtime.tex`.
- The generated table reports synthetic-account baseline and ablation sweep
  runtimes, rule-set ablation runtime, and EC2 MILP stress sizes up to 1,000
  cloned resources.
- GWA raw-trace rerun wall times are recorded in `paper/experiments_needed.md`
  and `paper/trace_provenance.md` for fetch/extract, external validation,
  reproducibility helper, and real-trace policy simulation.
- Azure vectorized assignment validates a 2,000-VM MILP sample and full
  vectorized selection in `paper/results_azure.json`, but raw Azure runtime was
  not rerun in this workspace.

Risk:
Medium. The current runtime evidence is useful but still not enough for a
general scalability claim because Azure raw timing and broader catalog/fleet
scale sensitivity are still missing.

Safer IEEE-style wording:
"The generated evidence reports solver/runtime behavior on the synthetic
account and cloned EC2 stress inputs; raw-trace runtime remains future
artifact work."

## 14. SLO/performance-safety claim

Classification: NEEDS EVIDENCE

Potential unsafe wording (not used in the current draft):
"P95 x 1.3 right-sizing is safe for performance."

Support:
The rule is implemented and common in spirit, but the repo has no SLO or
post-right-sizing performance validation.

Risk:
High if stated as a guarantee.

Safer IEEE-style wording:
"P95 x 1.3 is a conservative capacity heuristic; validating SLO risk after
right-sizing remains future work."

## 15. Candidate-catalog feasibility boundary claim

Classification: SUPPORTED

Current wording:
"Under the original committed demo catalog, q0.95 x 1.3 and related
high-percentile or high-headroom settings exceed the reduced EC2 candidate set,
so CBC returns an infeasible EC2 assignment while the RDS subproblem remains
feasible. Under the snapshot EC2 current/candidate basis, non-budget EC2
infeasibility disappears."

Support:
- `paper/results_baselines.json` records the snapshot-basis `P95 x 1.3
  heuristic` as `Optimal` and preserves original-demo results under
  `original_demo_baselines`.
- `paper/results_catalog_comparison.json` records the original demo DB row as
  `Partial (EC2 Infeasible)` and the snapshot EC2 row as `Optimal`.
- `paper/results_ablations.json` preserves original-demo high-percentile,
  high-headroom, memory-mode, and budget infeasibilities under
  `original_demo_ablations`, while the snapshot-basis non-budget rows are
  feasible and budget-cap rows expose a separate cap boundary.
- `paper/results_runtime.json` records implementation-match metadata where
  EC2 returns no assignment under P95 x 1.3 and RDS remains optimal.
- `paper/evidence_experiments.py` records raw and solver-valid candidate
  counts and preserves infeasible rows.
- `paper/ec2_catalog_audit.md` identifies the nine EC2 database price rows
  excluded because they lack vCPU and memory fields.

Risk:
Medium if a reviewer reads the partial rows as successful full-fleet EC2
optimization or as a universal failure of P95 headroom sizing.

Safer IEEE-style wording:
"The synthetic-account EC2 infeasibility is a candidate-catalog and constraint
coverage boundary in the committed demo data; after switching EC2 current and
candidate costs to the documented snapshot basis, non-budget infeasibility
disappears. This does not establish that a complete AWS catalog or commercial
recommender would behave the same way."

## 16. Snapshot catalog comparison claim

Classification: SUPPORTED, WITH SCOPE LIMITATION

Current wording:
"Replacing EC2 current inventory and EC2 candidates with the documented,
snapshot-dated 28-type AWS Price List catalog makes the non-budget P95 and
high-percentile/headroom rows feasible, while explicit per-service budget caps
remain a separate infeasibility boundary."

Support:
- `paper/catalog_comparison.py` reruns the same baseline and ablation grid
  under the original demo DB catalog and the shared-basis snapshot EC2
  catalog.
- `paper/results_catalog_comparison.json` reports the original demo DB row as
  `Partial (EC2 Infeasible)` for P95 x 1.3 and reports the snapshot EC2 row as
  `Optimal`.
- `paper/table_catalog_comparison.tex` reports non-budget EC2 infeasible rows
  changing from 9/18 to 0/18 and budget-cap EC2 infeasible rows remaining 4/4.
- `paper/results_baselines.json` reports the snapshot P95 x 1.3 row as
  optimal on the shared EC2 price basis.
- `paper/aws_catalog.py` documents the AWS Price List source URL,
  publication timestamp, version, region, operating system, tenancy, capacity
  status, license filter, and snapshot date.

Risk:
Medium if this is described as a complete all-SKU AWS EC2 catalog or as a
commercial-tool comparison. The committed snapshot covers 28 t3/m5/c5/r5
candidate types used by the paper scripts; it is not every EC2 SKU.

Safer IEEE-style wording:
"A rerun with the paper's documented 28-type snapshot EC2 current/candidate
price basis removes non-budget EC2 infeasibility, supporting the
interpretation that the original failure is a demo-catalog coverage boundary.
Broader all-SKU and commercial recommender comparisons remain unevaluated."

## 17. Demo pricing audit claim

Classification: SUPPORTED

Current wording:
"Several committed demo EC2 candidate prices are wrong or incomplete relative
to the verified AWS snapshot, so Study I separates original-demo diagnostics
from snapshot-repriced synthetic evidence."

Support:
- `paper/pricing_audit.md` compares all committed EC2 `instance_pricing` rows
  against `paper/aws_catalog.py`.
- The audit identifies missing vCPU/memory and missing RI prices for nine
  candidate rows, plus on-demand hourly mismatches for `m5.2xlarge`,
  `m5.large`, `m5.xlarge`, `t3.medium`, and `t3.micro`.
- The same audit shows EC2 current-inventory monthly costs mostly match the
  snapshot basis, so the defect is primarily in candidate pricing/spec rows.

Risk:
Low if the manuscript does not use original demo candidate-price savings as
headline evidence.

Safer IEEE-style wording:
"The original demo catalog is retained for provenance and failure-boundary
diagnostics; price-comparable Study I right-sizing rows use the snapshot EC2
current/candidate basis."

## 18. Service-level Study I decomposition claim

Classification: SUPPORTED

Current wording:
"The aggregate 19.0% synthetic compute-scope reduction is service-mixed: EC2
increases by 15.0%, while demo-priced RDS decreases by 91.2%."

Support:
- `paper/results_baselines.json` includes `service_breakdown` for the P95 x
  1.3 row.
- `paper/table_service_decomposition.tex` reports EC2 current $843.73/mo,
  optimized $970.61/mo, delta +$126.87/mo (+15.0%), and RDS current
  $397.85/mo, optimized $35.04/mo, delta -$362.81/mo (-91.2%).
- `paper/numbers_evidence.tex` exports the same values as macros.

Risk:
Medium if the aggregate is stated without the service split or if the
demo-priced RDS reduction is treated as production evidence.

Safer IEEE-style wording:
"The snapshot-basis synthetic P95 x 1.3 row is feasible, but its aggregate
decrease is driven by demo-priced RDS right-sizing while EC2 increases; the
service split is the result, not a cross-service superiority claim."
