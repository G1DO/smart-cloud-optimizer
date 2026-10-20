# Vulnerability reporting

Scope: application on **`main`** (single-user localhost demo with synthetic
data). This build trusts client-supplied identities and stores AWS keys in
plaintext; see [threat model](docs/security/threat-model.md). Do not use it multi-tenant or
public.

## Private contact

- Preferred: GitHub private vulnerability reporting for this repository
  (Security tab → Report a vulnerability). Reports stay private until triaged.
- If private reporting is unavailable in your view, request a private channel
  from the [repository maintainer](https://github.com/G1DO) with only the
  affected revision and a request for a channel — no details yet.
- Do not open a public issue, discussion, or PR with vulnerability details,
  credentials, personal data, account identifiers, prompts, or exploits.
  Public contact may only request the private channel.

Include once a private channel is established: affected revision/commit,
impact, minimal reproduction, and redacted logs (redact identifiers,
credentials, prompts, and personal data; never dump credential columns).

## Response commitments

- Acknowledge receipt within **2 days**.
- Provide an initial assessment / next steps within **7 days**.
- Review security posture (dependencies, fixture PII, scan and schema-proof
  status) at least **monthly**; critical localhost-demo fixes target the next
  monthly review or sooner when feasible.
- Supported window: `main` only while this file names the private route above.
  The default `release/ccpe-v1.0` branch is a separate paper artifact and is
  not in scope for application fixes.

Changes to the private route, acknowledgment time, or review cadence update
this file. Recheck the [threat model](docs/security/threat-model.md) whenever
identity, connection storage, browser state, external prompts, network
exposure, or persistence changes.
