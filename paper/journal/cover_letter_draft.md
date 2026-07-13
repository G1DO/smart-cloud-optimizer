# Cover Letter Draft

[TO BE COMPLETED BEFORE SUBMISSION: date]

Dear [EDITOR-IN-CHIEF OR HANDLING EDITOR NAME],

Please consider our manuscript, "The Price of Conservatism: Empirical Evidence
from Cloud Right-Sizing and Reservation Heuristics," for publication as a
[ARTICLE TYPE] in [JOURNAL NAME].

[TO BE COMPLETED FOR THE SELECTED JOURNAL: Explain in two or three sentences
how the manuscript fits the journal's current aims and scope. Identify the
specific audience, such as readers working on cloud systems, resource
management, capacity planning, or FinOps.]

The manuscript presents an empirical and systems comparison between one
implemented percentile-based cloud right-sizing pipeline, restored public
traces, and simplified reservation-policy baselines. It does not propose new
reservation theory; it evaluates mapped cost when P95 x 1.3 is
counterfactually reused as a commitment-sizing rule.

The evidence has three parts. First, a pricing-audited synthetic-account study
shows why aggregate savings must be decomposed: EC2 changes from $843.73/month
to $970.61/month (+15.0%), while demo-priced RDS changes from $397.85/month to
$35.04/month (-91.2%), producing an aggregate -19.0% cost change that is not
an unqualified optimizer win. Second, a restored Bitbrains/Materna GWA study
with archive-content SHA256 hashes and filename-and-size manifest SHA256
hashes reports 41.8% mapped savings (95% CI 35.9--47.5%) against a
lift-and-shift baseline and includes a full baseline grid. Third, a held-out
policy simulation compares the counterfactual P95 x 1.3 rule with newsvendor,
SAA, dual-level, perfect-information, and 7/30/60-day recency-window
baselines. The synthetic arm uses a daily account-cost proxy in USD/day, and
the restored real-trace arm uses hourly aggregate CPU demand in MHz.

The policy results are paper-side proxy simulations rather than third-party
recommender outputs or provider-billing models; operational and SLO effects
are not evaluated. The Azure raw vmtable.csv.gz input remains unrestored, so
its recorded result is retained only as a boundary case without causal
attribution.

The data, code, generated evidence, and remaining access restrictions will be
described in the final Data Availability and Code Availability statements.
[TO BE COMPLETED BEFORE SUBMISSION: repository URL, archived release/DOI,
license, and any dataset access restrictions.]

[TO BE CONFIRMED BY ALL AUTHORS BEFORE SUBMISSION: The manuscript is original,
has not been published previously, and is not under consideration elsewhere.
All authors have approved the manuscript and this submission.]

Competing interests: [TO BE COMPLETED BEFORE SUBMISSION.]

Funding: [TO BE COMPLETED BEFORE SUBMISSION.]

Optional suggested reviewers: [ADD ONLY IF REQUESTED, USING REAL NAMES,
INSTITUTIONS, INSTITUTIONAL EMAILS, AND A SHORT JUSTIFICATION.]

Optional opposed reviewers: [ADD ONLY IF REQUESTED, USING REAL IDENTITIES AND
A PROFESSIONAL CONFLICT-BASED JUSTIFICATION.]

Thank you for considering our manuscript.

Sincerely,

[CORRESPONDING AUTHOR NAME]
On behalf of all authors
[AFFILIATION]
[INSTITUTIONAL EMAIL]
