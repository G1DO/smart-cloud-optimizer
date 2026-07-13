# Response To Internal Review

This note records how the journal draft addresses the risks documented in
`paper/reviewer_risks.md`, `paper/claim_audit.md`, and
`paper/experiments_needed.md`.

## Addressed In The Journal Draft

- The framing is now an empirical comparison among an implemented percentile
  rule, restored traces, and simplified policy baselines, not a product
  demonstration or a new-theory claim.
- The title is preserved from the final conference version.
- The draft uses a neutral `article` class and does not target a specific
  journal.
- Study I no longer treats the stale stored 19-row recommendation table as a
  headline result.
- The 19.0% synthetic aggregate is always paired with the EC2/RDS
  decomposition: EC2 increases from $843.73/mo to $970.61/mo (+15.0%), while
  demo-priced RDS decreases from $397.85/mo to $35.04/mo (-91.2%).
- EC2 right-sizing is described as snapshot on-demand normalization, with
  RI/commitment effects evaluated separately.
- Catalog-completeness and budget-cap infeasibility are explicit.
- GWA Study II is described as restored/rerun with checksums, CIs, and a full
  baseline grid.
- Azure `vmtable.csv.gz` is explicitly described as not restored/rerun.
- The usage-hour RI replay and recency-window rows are labeled as paper-side
  baselines, not AWS/Azure/third-party outputs.
- Study III includes 7/30/60-day look-back replay policies.
- Study III distinguishes the theoretical physical-capacity quantities
  \(D_t,K\) from empirical \(X_t,Q\): USD/day in the synthetic arm and MHz in
  the restored real-trace arm.
- LOOK60 == newsvendor is explained for the real-trace replay because the
  requested 60-day window exceeds the available training split.
- Higher-savings real-trace baselines are not called better policies because
  SLO/performance-risk was not evaluated.

## Still Limited

- No direct commercial recommender baseline is available.
- No Azure raw rerun, checksum, CI, or runtime evidence is available.
- No SLO, latency, error-rate, or performance-risk validation is available.
- The EC2 catalog comparison uses the documented 28-type snapshot, not a full
  all-SKU AWS catalog.
- The policy simulator is a simplified aggregate model and not a full dynamic
  `(s,S)` contract implementation.
- Declarations, author contributions, funding, and final venue compliance are
  placeholders.

## Recommended Next Revision

Before submission, either remove the Azure boundary condition or restore and
rerun `vmtable.csv.gz` with checksums, runtime, CIs, and a baseline grid. If a
commercial-tool comparison cannot be run, keep the current limitation language
prominent in the abstract, discussion, and threats sections.
