# Reviewer Risks

This file tracks the most likely IEEE reviewer objections, their severity,
how to fix them, and whether each must be fixed before submission or can be
handled as a limitation.

## 1. Engineering project rather than research contribution

Severity: High

Likely objection: The implementation combines known components: forecasting,
right-sizing, reservation checks, and service rules.

Fix:
- Keep the main contribution as an empirical theory-practice bridge.
- Emphasize the price of conservatism, real-trace validation, and Azure
  boundary condition.
- Avoid presenting dashboard, API, storage, authentication, or LLM-advisor
  features as research contributions.

Submission status: Must be fixed in framing before submission. The remaining
implementation-product risk can be discussed as a limitation.

## 2. Incremental novelty over Chen et al.

Severity: High

Likely objection: The reservation theory comes from Chen, Lei, and Moinzadeh;
the paper may look like an application of their model.

Fix:
- State that the contribution is operationalization and empirical
  quantification, not new theory.
- Add a comparison table: Chen et al. theory, deployed P95 pipeline,
  paper-side newsvendor/SAA/dual simulations.
- Keep the full dynamic `(s,S)` policy as future work unless implemented.

Submission status: Must be addressed in framing. Full `(s,S)` implementation
can be limitation/future work for a conference version.

## 3. No direct commercial baseline

Severity: Critical

Likely objection: IEEE reviewers may expect AWS Compute Optimizer, AWS Cost
Explorer RI recommendations, Savings Plans recommendations, Azure Advisor, or
a commercial FinOps tool.

Fix:
- Run at least one direct commercial baseline on the same connected account,
  if feasible.
- Otherwise implement a documented paper-side replay baseline and label it as
  an implementation-specific comparison, not as third-party service output.
- Keep all superiority claims out of the paper.

Submission status: Best fixed before submission. If impossible, must be a
prominent limitation and the title/abstract must avoid superiority language.
Current status: Partially mitigated by the canonical
`paper/results_ri_replay.json` and `paper/table_ri_replay.tex`, which implement
a labeled paper-side usage-hour EC2 reservation replay baseline. The
7/30/60-day rows are retained in JSON but collapsed to one LaTeX row because
the synthetic account cannot distinguish the windows. Legacy-named copies are
retained only as deprecated compatibility aliases for the finalized
conference source. Study III also includes 7/30/60-day recency-window replay
policies. These are not direct AWS, Azure, or commercial FinOps baselines and
must not be described as such.

## 4. Synthetic-account savings are not production evidence

Severity: High

Likely objection: The synthetic account ships with the repository and may be
seen as a demo workload tuned to produce savings.

Fix:
- Present Study I as a system sanity check and method illustration.
- Report the EC2/RDS service split and do not state the aggregate 19.0%
  compute-scope decrease without the EC2 increase and RDS/demo-price caveat.
- Put the main empirical weight on public traces and policy simulation.
- Add live-account validation or a modern production trace if possible.

Submission status: Can be discussed as a limitation if real-trace sections are
kept central and the service split is explicit. Live validation would
materially improve acceptance probability.

## 5. Trace age and provider mismatch

Severity: Medium

Likely objection: Bitbrains and Materna are old managed-hosting traces; Azure
is bucketed and not directly comparable; all are mapped to AWS pricing.

Fix:
- Add sensitivity to price-catalog date and candidate catalog scope.
- Add a post-2019 trace with provisioned and used CPU/memory if available.
- Emphasize relative method comparison rather than absolute dollars.

Submission status: Can be discussed as a limitation, but a modern trace would
strengthen the paper. Current status: GWA Bitbrains/Materna traces have now
been restored, checksummed, and rerun from raw inputs with bootstrap intervals
and a percentile baseline grid. The Azure raw `vmtable.csv.gz` input is still
missing, so that boundary case remains generated-only until restored.

## 6. Forecasting results are weak and not causal for savings

Severity: Medium

Likely objection: Forecasting does not significantly outperform simple
baselines and does not drive the optimizer's savings.

Fix:
- State forecasts are for monitoring and context.
- Avoid claiming forecast-driven optimization.
- Add an ablation only if the system uses forecasting to change
  recommendations.

Submission status: Can be handled by clear framing and limitations.

## 7. Deployed system does not implement newsvendor or full `(s,S)`

Severity: High

Likely objection: The strongest policy results are simulations, while the
deployed optimizer uses P95 right-sizing and always-on reservation checks.

Fix:
- Keep "counterfactual reservation-sizing simulation" language.
- Implement gamma-aware reservation sizing before claiming deployment.
- Implement cancellation/renewal dynamics before claiming full `(s,S)`.

Submission status: Must be explicit before submission. Full implementation can
be future work if not oversold.

## 8. SAA baseline is not an adversarial competitor

Severity: Medium

Likely objection: SAA recovers newsvendor because it optimizes the same
empirical objective.

Fix:
- Present SAA as validation/cross-check, not as a competitive baseline.
- Add simple baselines: mean, median, P90, P95 without headroom, max, greedy.
- Add a direct commercial baseline if possible; otherwise keep the paper-side
  replay explicitly implementation-specific.

Submission status: Should be improved before submission with simple baselines.

## 9. Missing ablation study

Severity: High

Likely objection: Reviewers cannot tell whether percentile, headroom, memory,
budget cap, or rule choices matter.

Fix:
- Add ablations listed in `experiments_needed.md`.
- Report savings and risk proxies: upsize count, downsize count, spillover or
  under-sizing proxy.

Submission status: Must be fixed before a strong IEEE submission.
Current status: Partially mitigated for Study I and GWA Study II. Synthetic
baselines/ablations are generated, and `paper/table_external_baselines.tex`
plus `paper/results_external.json` now add restored-GWA lift-and-shift, mean,
median, P90, P95, P99, max, and P95 x 1.3 baselines with bootstrap intervals.
Azure raw-input ablations remain missing.

## 10. Missing runtime and scalability evidence

Severity: Medium

Likely objection: A systems paper should show solver/runtime behavior.

Fix:
- Add wall-clock runtime, peak memory, solver status, and scaling with fleet
  and catalog size.
- Include Azure full vectorized assignment and MILP sample runtime.

Submission status: Should be fixed before submission; otherwise discuss as a
limitation for a short/workshop paper. Current status: synthetic runtime
evidence exists, and the restored-GWA rerun records fetch/extract, external
validation, CI/grid helper, and real-trace policy wall times in
`paper/experiments_needed.md` and `paper/trace_provenance.md`. Azure raw
runtime and broader fleet/catalog scaling remain missing.

## 11. No SLO or performance-risk validation

Severity: Medium

Likely objection: Cost reductions may imply under-provisioning risk.

Fix:
- Add post-right-sizing risk proxies: fraction of observations exceeding new
  capacity, spillover magnitude, or SLO violation proxy.
- If real SLOs are unavailable, clearly label metrics as proxies.

Submission status: Should be fixed if claiming safe right-sizing. Can be a
limitation if the claim is only cost-mapping.

## 12. Reproducibility asserted but not fully independently verified

Severity: Medium

Likely objection: Generated macros exist, but reviewers need clean rebuild
instructions.

Fix:
- Add dependency versions, trace checksums, command logs, and expected hashes.
- Verify `build_conference.sh` after installing LaTeX.
- Ensure raw external data restoration instructions are complete.

Current handling:
- `paper/fetch_traces.sh` restored the three GWA zip archives into a local
  trace directory represented as `$TRACE_DIR` in the publication artifacts.
- `paper/external_validation.py` reran Bitbrains fastStorage, Bitbrains Rnd,
  Materna, the Rnd forecast table, and `trace_rnd_hourly.csv` from raw inputs.
- `paper/study2_reproducibility.py` added GWA zip SHA256 checksums, extracted
  tree manifest hashes, per-VM bootstrap CIs, a percentile baseline grid, and
  `paper/trace_provenance.md`.
- `paper/policy_sim.py` regenerated the real-trace Study III policy artifacts
  from the rerun Rnd aggregate.

Submission status: Improved for GWA but still incomplete for artifact
evaluation. Azure raw `vmtable.csv.gz`, dependency/version inventory, expected
generated-file hashes, and final clean rebuild documentation remain to be
finished.

## 13. EC2 MILP infeasibility may look like a broken optimizer

Severity: High

Likely objection: The original-demo catalog comparison shows
`Partial (EC2 Infeasible)` for the deployed `q0.95 x 1.3` policy, so a
reviewer may conclude that the implementation failed rather than exposed a
meaningful boundary condition.

Fix:
- Keep all infeasible rows visible in the generated tables.
- Explain that the committed synthetic DB has more EC2 price rows than
  solver-valid EC2 hardware rows; only the valid subset can satisfy MILP
  CPU/memory constraints.
- State that infeasibility arises from the interaction of candidate-catalog
  incompleteness and conservative headroom requirements.
- Do not count partial rows as full EC2 right-sizing success.
- Rerun synthetic EC2 ablations with a snapshot-dated EC2 catalog and report
  whether infeasibility disappears, persists, or moves to a different boundary.

Current handling:
- `paper/catalog_comparison.py` reruns the baseline and ablation grid with the
  committed demo catalog and with the documented 28-type AWS Price List
  snapshot in `paper/aws_catalog.py`, repricing EC2 current inventory and EC2
  candidates onto the same snapshot basis.
- `paper/results_catalog_comparison.json` and
  `paper/table_catalog_comparison.tex` show that non-budget EC2 infeasibility
  disappears under the snapshot EC2 catalog.
- `paper/results_baselines.json` and `paper/table_baselines.tex` now use the
  snapshot EC2 current/candidate basis for the main generated synthetic
  baseline rows; the P95 x 1.3 row is `Optimal` there.
- Explicit budget-cap rows remain EC2-infeasible because the conservative
  snapshot-priced assignment exceeds the EC2 service-level cap. The manuscript
  frames this as a separate policy/budget boundary.

Submission status: Partially addressed. The highest "broken optimizer" risk is
reduced because the non-budget infeasibility disappears with the snapshot
catalog. Remaining risk: the snapshot catalog is 28 t3/m5/c5/r5 types, not an
all-SKU AWS catalog or a commercial recommender output, so broader catalog
sensitivity remains useful before submission.

## 14. Demo pricing errors invalidate Study I dollar claims

Severity: Critical

Likely objection: The committed synthetic/demo EC2 `instance_pricing` table
contains prices that differ sharply from the verified AWS snapshot, so Study I
may be numerically invalid.

Fix:
- Audit all EC2 candidate and current-inventory prices against the verified
  snapshot catalog.
- Preserve original demo data for provenance, but do not use original
  candidate-price savings as headline evidence.
- Reprice EC2 current inventory and EC2 candidates onto the same snapshot
  basis for synthetic right-sizing tables.
- Remove stale stored-recommendation dollar claims from the abstract and
  conclusion.

Current handling:
- `paper/pricing_audit.md` identifies the wrong/incomplete EC2 candidate rows.
- `paper/evidence_experiments.py` now uses snapshot EC2 current/candidate
  pricing for the generated baseline and ablation tables, while preserving
  original demo outputs under `original_demo_*` JSON keys.
- `paper/table_service_decomposition.tex` shows that the snapshot-basis P95 x
  1.3 aggregate reduction is driven by demo-priced RDS while EC2 increases.
- Partial/infeasible rows now show `--` for comparable savings in generated
  tables, with fallback costs retained only as JSON diagnostics.
- The manuscript no longer uses the old 19-recommendation/$590 stored-table
  claim as a headline result.

Submission status: Largely fixed for the conference draft. Remaining risk:
RDS remains on the committed demo DB basis because no RDS snapshot catalog is
present, and the EC2 snapshot covers 28 t3/m5/c5/r5 types rather than all AWS
EC2 SKUs.

## 15. Recommendation-count inconsistency

Severity: High

Likely objection: The manuscript reported 19 recommendations and about
$590/mo, while recomputed evidence reported 15 recommendations and different
rule-set savings.

Fix:
- Identify the source of each count.
- Use a single authoritative result in the manuscript.
- Explain any retained difference as stored-table provenance rather than a
fresh recomputation.

Current handling:
- `paper/pricing_audit.md` explains that the old 19-row count came from the
  stored `recommendations` table queried by `paper/make_figures.py`.
- The recomputed current implementation path reports 15 deduplicated rows and
  $507.83/mo because the committed pricing table only has reserved rates for
  two of the six old EC2 pricing-switch rows.
- The manuscript uses neither the old 19-row count nor the stored $590/mo as
  a headline result.

Submission status: Fixed for claims. The stored table can remain as provenance,
but should not drive headline savings.

## 16. Aggregate Study I result may hide EC2 upsizing

Severity: High

Likely objection: The abstract-level 19.0% synthetic compute-scope decrease
could look like a broad optimizer win even though EC2 increases by 15.0% and
the aggregate is dominated by demo-priced RDS reduction.

Fix:
- Split Study I by service in generated JSON, LaTeX tables, abstract, results,
  and conclusion.
- State that EC2 cost increases under conservative P95 x 1.3 on the
  snapshot-basis synthetic account.
- State that RDS remains on the committed demo DB price basis.
- Do not present aggregate 19.0% without the service-level caveat.

Current handling:
- `paper/results_baselines.json` includes `service_breakdown` for generated
  rows.
- `paper/table_service_decomposition.tex` reports EC2 +$126.87/mo (+15.0%),
  RDS -$362.81/mo (-91.2%), and aggregate -$235.93/mo (-19.0%).
- `paper/conference_draft.tex` now frames the aggregate as service-mixed and
  method-illustrative.

Submission status: Fixed for claim safety, but still a reviewer risk because
RDS snapshot pricing has not been generated.

## 17. Final reference resolution

Severity: Medium

Likely objection: A final IEEE submission can lose credibility if references
lack resolvable DOI, arXiv, venue, or stable URL metadata.

Fix:
- Before submission, verify every bibliography entry resolves.
- Add DOI or stable URL metadata where available.
- Do not invent missing citation details; mark unresolved references for manual
  author review.

Submission status: Still needed as a final packaging check.
