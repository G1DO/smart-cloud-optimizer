# Generic Journal Conversion Checklist

This checklist applies to `paper/journal/journal_draft.tex`. Journal-format
workflow guidance was used for structure and package checks only; it is not
scientific evidence and is not a manuscript reference.

## Journal Package

- [x] paper/journal/journal_draft.tex
- [x] paper/journal/build_journal.sh
- [x] paper/journal/journal_checklist.md
- [x] paper/journal/cover_letter_draft.md
- [x] paper/journal/response_to_internal_review.md
- [x] Journal outputs are isolated from paper/conference_draft.tex and
  paper/conference_draft.pdf.
- [x] Packaging documents and manuscript prose contain no local absolute
  paths; artifact references use repository-relative `paper/...` paths.

## Neutral Format And Front Matter

- [x] Uses the generic LaTeX article class and no publisher-specific class.
- [x] Keeps the finalized conference title.
- [x] Uses the confirmed six-author metadata in named mode and supports
  anonymous review through the \anonymousfalse / \anonymoustrue switch.
- [x] Includes the confirmed shared affiliation for all six authors and
  Ibrahim Mohamed's corresponding-author designation in named mode.
- [x] Includes a standalone abstract and neutral keywords.
- [x] Uses the existing paper/references.bib; no references or DOI values were
  invented.
- [x] Uses neutral plain BibTeX styling pending a target venue.
- [x] Contains no conference-class commands.
- [ ] Confirm the target journal's title-length and keyword rules.
- [ ] Confirm whether the target journal requires named or anonymous review.
- [ ] Confirm line numbering, page numbering, spacing, word/page limits, and
  bibliography style with the target journal.

## Structure And Scientific Readiness

- [x] Introduction states the problem, gap, evidence boundary, and three
  explicit contributions.
- [x] Related Work distinguishes inherited capacity-reservation theory, named
  production/resource-management systems, prior provisioning/right-sizing
  work, and this article's empirical contribution.
- [x] Background separates right-sizing from reservation sizing and describes
  mapped-cost/headroom tradeoffs under the evaluated model.
- [x] System and Methodology is separated from the research contribution.
- [x] Experimental Design defines the research questions, inputs, metrics,
  baseline families, bootstrap unit/repetitions/seed, and split sensitivity.
- [x] Three study sections separate synthetic, restored GWA, and reservation
  policy evidence.
- [x] Discussion, Threats to Validity, Reproducibility, and Conclusion are
  distinct.
- [x] Claims map to generated evidence, citations, or explicit limitations.
- [x] No unsupported "best," "superior," "state-of-the-art," or operational
  safety claim is made.

## Evidence Included

- [x] Study I EC2 snapshot on-demand normalization, with commitment effects
  evaluated separately.
- [x] Catalog comparison and feasibility boundary.
- [x] Full synthetic baseline grid and descriptive confidence intervals.
- [x] Mandatory EC2/RDS service decomposition: EC2 +15.0%, RDS -91.2%, and
  aggregate -19.0%.
- [x] RDS demo-pricing caveat and explicit statement that the aggregate is not
  an unqualified optimizer win.
- [x] Full synthetic ablation and runtime tables.
- [x] Paper-side EC2 usage-hour RI replay, labeled as an
  implementation-specific baseline.
- [x] Synthetic forecasting table and non-superiority interpretation.
- [x] Restored Bitbrains/Materna GWA results with archive-content SHA256
  hashes, filename-and-size manifest hashes, runtimes, confidence intervals,
  and the full baseline grid.
- [x] The manuscript gives checksum prefixes; full archive and
  filename-and-size manifest values remain in paper/trace_provenance.md and
  paper/results_external.json.
- [x] Azure vmtable.csv.gz explicitly remains unrestored and not rerun.
- [x] Real-trace forecasting context and non-significant test interpretation.
- [x] Study III formally defines HEUR, NV, SAA, LOOK7/30/60, DUAL/DUALC, and
  the perfect-information bound.
- [x] Study III includes an evaluated-gamma table, representative policy-grid
  tables, and full price-ratio sweep figures.
- [x] Study III distinguishes theoretical physical-capacity notation
  \(D_t,K\) from empirical proxy notation \(X_t,Q\), with USD/day for the
  synthetic arm and MHz for the restored real-trace arm.
- [x] LOOK60/newsvendor degeneracy is explained for the real-trace replay.
- [x] Higher-savings real-trace baselines are not called better because no
  SLO/latency/performance-risk outcomes were measured.

### Evidence Precedence Note

- [x] The journal-only synthetic baseline wrapper intentionally excludes the
  stale GWA row in paper/table_baselines.tex / paper/results_baselines.json
  that says per-VM CIs were not rerun.
- [x] Restored Study II claims instead use paper/results_external.json,
  paper/numbers_external.tex, paper/table_external_baselines.tex, and
  paper/trace_provenance.md, which supersede that stale row.
- [x] Policy terminology, empirical-unit metadata, and the public JSON
  commitment field (`Q`) were regenerated without changing numerical values;
  other evidence values were preserved.

### Deprecated Packaging Compatibility Names

- [x] `paper/results_commercial_like.json` and
  `paper/table_commercial_like.tex` are deprecated packaging filenames
  retained only for the finalized conference source; the journal uses
  `paper/results_ri_replay.json` and `paper/table_ri_replay.tex`.
- [x] The `\evidCommercial*` macros and the `tab:commercial-like` label emitted
  by `paper/evidence_experiments.py` are deprecated aliases retained for
  finalized conference/main consumers. New journal prose uses the canonical
  RI-replay names.
- [x] The generated `*TrainDays` and `*TestDays` macros are deprecated
  period-count aliases retained because finalized conference/main consumers
  still reference them. In the hourly external arm they count hours, not
  days; the journal uses `*TrainPeriods` and `*TestPeriods`.

## Evidence-Safety Constraints

- [x] No results, citations, baselines, DOI values, funding, affiliations, or
  author contributions were invented.
- [x] No direct AWS, Azure, or commercial-tool superiority claim.
- [x] Usage-hour RI and recency-window replay rows use neutral paper-side
  labels and are not used as evidence about third-party-system behavior.
- [x] No production/live-account savings claim.
- [x] No all-SKU AWS catalog claim; the evaluated snapshot has 28 types.
- [x] No full dynamic (s,S) implementation claim.
- [x] No SLO/performance-risk validation claim.
- [x] Capacity headroom is not presented as evidence of operational safety.
- [x] The unrestored Azure result is not given a causal attribution.
- [x] Policy-cost ratios are not presented as having confidence intervals.

## Figures, Tables, And Source Dependencies

- [x] Every journal figure and table is cited in the text.
- [x] Captions identify their contents and were reviewed for empirical units,
  causal wording, and third-party-behavior implications.
- [x] Figures are vector PDF assets.
- [x] Tables remain editable LaTeX, not screenshots.
- [x] Journal displays of the remaining shared `resizebox` tables use
  journal-only `tabularx`, wrapped-column, or full-width layouts; shared
  conference table values and render paths remain unchanged.
- [x] Most headline values are imported from generated artifacts; compact
  presentation tables that contain transcribed summaries or checksum prefixes
  are disclosed in the manuscript.
- [ ] Recheck all caption interpretation and evidence-boundary wording after
  target-journal adaptation.
- [ ] Recheck legibility after adapting to a target journal's column widths.
- [ ] Decide whether the full baseline grids belong in the main article or
  supplementary material under the target journal's limits.

## Declarations And Author Input

- [x] Factual data- and code-availability notes render without unfinished
  placeholders.
- [x] Unresolved competing-interests, funding, author-contribution, ethics,
  consent, and generative-AI declarations remain source TODO comments and do
  not render in the PDF.
- [x] Includes the approved supervision and project-support line between the
  author line and shared affiliation on page 1.
- [x] Records the six required authors in order, with Ibrahim Mohamed as first
  and corresponding author using the supplied email.
- [ ] Complete every declaration using author-approved facts.
- [ ] Confirm all authors approve the final manuscript and submission.
- [ ] Obtain author-approved contribution and competing-interest declarations
  from all six authors before submission. Dr. Hafez Seliem, Mohamed Essam, and
  Saif AlDeen Sameh remain supervision/project-support contributors, not
  authors.
- [ ] Confirm the manuscript is not under consideration elsewhere.

## Reproducibility And Public-Artifact Audit

- [x] Known data sources, snapshot date/scope, principal scripts, available
  commands, seeds, checksums, generated inputs, and major limitations are
  identified in the current workspace; this is not clean-room verification.
- [x] GWA archive-content SHA256 and filename-and-size manifest SHA256 values
  are recorded; the latter cover relative CSV paths and file sizes only.
- [x] Azure raw-input absence is recorded.
- [ ] Add public repository URL, archived release/DOI, and release tag.
- [ ] Record Python, dependency, PuLP/CBC, OS, hardware, and LaTeX versions.
- [ ] State project license, supported operating systems, and restrictions.
- [ ] Complete dependency pinning and an independent clean-room rerun.
- [ ] Add final hashes for submitted generated files.
- [ ] Audit the public artifact for secrets, PII, cloud account IDs, ARNs,
  tokens, credentials, and private data.
- [ ] Restore/rerun Azure and add checksum, runtime, CIs, and grid, or remove
  the Azure boundary result from the submitted manuscript.
- [ ] Add SLO/latency/error-rate validation before making any operational
  safety claim for more aggressive sizing.
- [ ] Re-run the reference audit after any citation change.

## Target-Journal Verification

- [ ] Select the target journal and article type.
- [ ] Check the journal's current aims and scope.
- [ ] Check current author instructions, template, citation style, review
  model, and submission-system requirements.
- [ ] Check current word/page limits and supplementary-material rules.
- [ ] Check APC/waiver or institutional-funding details if relevant.
- [ ] Check special-collection name and deadline only if applicable.
- [ ] Adapt the cover letter's venue-fit paragraph and metadata.
- [ ] Add only real, verified suggested/opposed reviewers if requested.

## Build And Submission Package

- [x] Run `./paper/journal/build_journal.sh` after the final manuscript edit.
- [x] Confirm zero undefined citations/references, LaTeX/BibTeX errors,
  overfull boxes, and serious layout warnings in the final logs.
- [x] Record the final PDF page count: 21 pages.
- [x] Run `./paper/build_conference.sh` as a compatibility check; the finalized
  conference PDF remains 8 pages.
- [x] Run `git diff --check` over all changed and newly added files.
- [ ] Include editable manuscript source, compiled PDF, bibliography, figures,
  generated inputs, cover letter, and any supplementary files required by the
  target journal.

## Citation Search Placeholders

Do not add fake BibTeX entries. If Related Work is expanded, run targeted
searches and add only verified references:

- cloud cost optimization right sizing production recommender utilization percentile
- cloud reserved instance recommendation recency-window utilization commitment
- FinOps cloud cost optimization empirical study right sizing
- capacity reservation intermittent demand cloud reserved on demand pricing
- SLO risk validation cloud right sizing virtual machines utilization
