# Threat model — Smart Cloud Optimizer (`main`)

Scope: single-user localhost demo with synthetic data. This is a tailoring
record for the implemented trust limits, not a production security claim.
See [security boundaries](README.md) and [vulnerability reporting](../../SECURITY.md).

## Assets

- AWS access keys / session tokens submitted via the connection form and
  persisted in SQLite (`aws_connections`).
- Account identifiers: AWS account id, IAM role ARN, `user_id` values
  (`usr-…`, `aws-<account_id>`).
- Personal data in the committed fixture: `data/cloud_optimizer.db` ships a
  real personal email, a real AWS account id, and a real IAM role ARN
  alongside the synthetic `aws-SYNTHETIC-001` workspace.
- Password verifiers: PBKDF2-HMAC-SHA256 `salt:hash` in `users.password_hash`.
- Cost / inventory / metric history, optimizer and forecast output.
- Gemini prompts and generated advice; `.env` values (`GOOGLE_API_KEY`,
  `ONBOARDING_API_TOKEN`).

## Trust boundaries

- Browser `localStorage` holds session identity with no server session;
  any `/dashboard` route is reachable and falls back to the synthetic demo user.
- Every data and settings HTTP endpoint trusts a client-supplied `user_id`
  query parameter with no server-side authorization check
  (`backend_api/routers/auth.py` issues no token; `dashboard.py`, `costs.py`,
  `connections.py`, `forecast.py`, `recommendations.py`, `settings.py`
  filter by the supplied id only).
- SQLite file `data/cloud_optimizer.db` is the trust store; `storage/db.py`
  is the preferred accessor but some routes issue direct SQL.
- Loopback binding (`127.0.0.1`) limits network reachability but does not
  authenticate callers.
- External: AWS via boto3 with stored credentials; Gemini via questionnaire
  prompt. Generated advice is unvalidated.
- Build / runtime: `.env` and `backend_api/runtime_settings.json` are excluded
  from Git and the image context, but the committed demo DB is intentionally
  included in the backend image. Backups inherit DB contents and must stay out
  of Git.

## Threats (in scope for this deployment model)

- Any local client can read or mutate another user's rows by supplying their
  `user_id` (cross-workspace read/write, connection delete, sync trigger).
- Stolen DB file, backup, or image layer exposes plaintext AWS keys (when
  key-based connections exist), account ids, role ARNs, emails, and password
  hashes (offline brute force is the only barrier; PBKDF2 slows but does not
  prevent it).
- Committed PII / account identifiers in `data/cloud_optimizer.db` leak via
  clone, fork, image, or log redaction failure.
- Credential capture via logs, diagnostics, or AI prompts (questionnaire text
  sent to Gemini; backend JSON logs redact secrets/PII but callers can still
  paste them into prompts or public issues).
- Unverified save: `POST /api/connections` with a supplied `aws_account_id`
  stores without re-verifying keys against that account; `GET /test` and save
  are separate operations.
- Login enumeration / brute force is only blunted by an in-process per-IP
  throttle (10 failures / 300 s → 429); no distributed or durable lockout.
- Sync race / stale `in_progress` blocks retry; interrupted daemon thread
  leaves persisted status without automatic resume.

Out of scope (explicit non-goals): multi-tenant isolation, public hosting,
encryption at rest, token/session auth, server-side authorization, durable
rate limiting, and automatic secret rotation. Do not deploy this build
multi-user or off-localhost without fixing those first.

## Controls (implemented)

- Passwords: PBKDF2-HMAC-SHA256, 260k iterations, 16-byte salt, constant-time
  compare; generic auth errors to avoid enumeration.
- Throttle: in-process per-IP 10/300 s on `/api/auth/*`.
- Input validation before AWS calls: `AKIA|ASIA` + 16 chars, 12-digit account
  id; STS-derived account id when none is supplied.
- Secret minimization in API: `ConnectionOut` omits secret, token,
  `external_id`, `iam_role_arn`; only last 4 of the access key id is exposed.
  Sync reads credentials server-side from the stored row.
- AI guard: prompt > 4000 chars → 400; Gemini failure → 502; optional
  `ONBOARDING_API_TOKEN` (`X-API-Token`) gate, off by default for demo.
- Transport scope: Compose and manual runs bind to `127.0.0.1`; CORS allows
  only the two local port-3000 origins.
- Logging: single-line JSON to stdout with `timestamp`/`level`/`service`/
  `msg`/`trace` (W3C `traceparent` where propagated); secrets/PII redaction
  (`[REDACTED]`) covered by `tests/test_service_standards.py`.
- Hygiene: `.gitignore` excludes `.env`, runtime settings, `data/real/`,
  backups, WAL/SHM sidecars; `git diff --check`, `compileall`, frontend lint,
  and `check:secrets` (working tree + full history) run in CI with push
  protection via the pre-push hook.

## Accepted risks (tailoring)

- Auth remains trust-based (`user_id` query param, no token). Accepted only
  for single-user localhost with synthetic data.
- AWS keys persist in plaintext in SQLite when key-based connections are
  used (`storage/db.py` `aws_access_key_id` / `aws_secret_access_key` /
  `aws_session_token`, with inline `SECURITY` comments). Accepted only for
  the localhost demo with no machine-side key store; must be encrypted before
  any shared or public use.
- Committed `data/cloud_optimizer.db` contains real PII / account identifiers
  in plaintext. Accepted as a known fixture limitation; do not add more real
  account data, do not distribute rebuilt images containing real data, and
  keep backups and diagnostics redacted and out of Git.

## Sensitive handling rules

- Never commit `.env`, `runtime_settings.json`, backups, WAL/SHM files, or
  real AWS data under `data/real/`.
- Never paste secrets, account ids, emails, prompts, or exploit details into
  public issues; use the private route in `SECURITY.md` (ack in 2 days,
  status in 7 days, monthly review).
- When sharing diagnostics, redact identifiers, credentials, prompts, and
  personal data; query `aws_connections` by id columns only, never dump
  credential columns.
- Schema changes stay additive: `ensure_schema()` creates missing objects and
  adds supported credential columns; `create_schema()` (drop/recreate) belongs
  only in disposable fixtures. See `docs/architecture/data-model.md` and
  `storage/db.py`.

## Review triggers

Recheck this model whenever identity, connection storage, browser state,
external prompts, network exposure, persistence, or the committed fixture
changes. Secret scan (`check:secrets`), schema compat, and restore proof must
stay green; see `README.md` Verify and `pyproject.toml [tool.poe.tasks]`.
