# Security boundaries

These are implemented limitations, not production security guarantees. The app is intended for **single-user local use with synthetic data**. Loopback port binding limits network reachability but does not authenticate clients or isolate users.

- **Auth is trust-based — no tokens or sessions.** Login/sign-up verify a PBKDF2-hashed password but issue **no token or session cookie**. Every data and settings endpoint trusts a `user_id` query parameter with **no server-side authorization check**, so any client could read another user's data by supplying their `user_id`. The login route has only an in-process, per-IP throttle (10 failures / 300s → HTTP 429). This is **not safe for multi-tenant or public deployment** — a real deployment must add token/session auth and derive `user_id` server-side, and configure CORS for the chosen credential transport.
- **AWS credentials are stored in plaintext.** The connection form sends AWS access keys to the backend, which persists them **in the SQLite DB in plaintext**. Connection responses omit secret fields and expose only the last 4 chars of the access key id; sync reads credentials server-side. Saving does not always verify AWS access; see [connection identity and verification](../architecture/README.md#connection-identity-and-verification). Do not point this at a shared or public host with real credentials.
- **The committed demo DB contains real data.** `data/cloud_optimizer.db` ships with the synthetic demo user **plus** a real personal email (PII) and a real AWS account id / IAM role ARN in plaintext. Do not add more real account data to the committed DB.
- **AI onboarding guards.** `POST /api/ai-onboarding/generate` rejects prompts longer than 4000 characters (HTTP 400) and returns HTTP 502 when the upstream Gemini call fails (e.g. `GOOGLE_API_KEY` unset). When `ONBOARDING_API_TOKEN` is set, callers must send a matching `X-API-Token` header; it is off by default so the demo works with no token.
- **Settings are file-backed, not in the DB.** Per-user runtime settings persist to `backend_api/runtime_settings.json`. Reads are always allowed; writes/resets are read-only for demo users and for users without a connected AWS account. Settings are not wired into the engines or collector, and Compose does not persist this file across container recreation; see [runtime settings](../architecture/README.md#runtime-settings).
- **Frontend auth is client-only.** Session identity lives entirely in browser `localStorage` — there is no Next.js middleware or server-side route protection, so any `/dashboard` route is reachable and falls back to the synthetic demo user.

## External services and data handling

AWS sync sends stored credentials to AWS through boto3 and writes account data
locally. The AI advisor sends the questionnaire-derived prompt to Gemini; avoid
including secrets or sensitive account details. Generated advice is not validated
for correctness or safety; review any proposed AWS change independently.

[Data pipeline](../architecture/data-pipeline.md) describes replacement and partial
sync behavior. [Local operations](../operations/local-runtime.md) covers state
preservation; backups inherit the database's sensitive contents and must stay out
of Git. The build context excludes `.env` and runtime settings but intentionally
includes the committed demo database, so do not distribute locally rebuilt images
that contain real account data.

## Reporting and review triggers

Use [SECURITY.md](../../SECURITY.md) for vulnerability reporting. Recheck this
page whenever identity, connection storage, browser state, external prompts,
network exposure, or persistence changes.
