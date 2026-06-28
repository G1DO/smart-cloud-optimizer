# Code Review — PR #2 "Final React frontend with FastAPI backend integration"

> Multi-agent review (32 agents, every finding adversarially verified against the
> real code) of the `final-react` branch, merged to `main` as `545c383`.
> This file is both the review record and the follow-up fix checklist
> (branch `fix/pr2-review-followups`).

**Verdict: merge-with-followups** — calibrated for a student graduation project
running locally on synthetic data.

**Headline:** Solid, runnable full-stack addition (281 tests pass, app imports), but
it ships a *client-trust* auth model with systemic IDOR — a documented localhost
limitation today, a hard blocker the moment it leaves single-user/synthetic use.
Test posture: **281 passed, 0 regressions**; `test_synthetic.py` now collects (the
old "missing `data_generation`" gotcha is half-fixed).

---

## Resolution (branch `fix/pr2-review-followups`)

Decision (user): **harden + document** the auth blocker; fix the rest.
After fixes: **281 tests still pass, 0 regressions**; backend imports clean; the
`data_generation` CLI verified end-to-end (419 rows → temp DB, committed DB untouched).

- **Fixed & test-verified (backend / data-gen / repo):** M1, M5, m1, m2, m3, m4, m5, m6, m7, m14, m15, m16, n1, n2, n3, n7
- **Fixed — backend half (frontend wiring deferred):** M2 (always-on 4000-char prompt cap + optional `ONBOARDING_API_TOKEN` gate; AI failure now returns 502 not fake-200)
- **Fixed — safe frontend file ops only:** n4 (rm empty `tailwind.config.ts`), n5 (`global.c.ts`→`global.d.ts`), m10 *scaffold only* (`app/lib/api.ts` created; page migration deferred)
- **Documented (README / `.env.example`):** m17, n6, **B1** (client-trust/IDOR limitation), **M3** (AWS connections cosmetic, no STS)
- **Deferred — need a frontend build env (npm offline here, can't typecheck 1000+-line TSX):** M4, m8, m9, m11, m12, m13
- **Not fixable retroactively:** n8 (squashed single commit — process note only)

Legend below: `[x]` done · `[~]` partial/scaffold · `[ ]` deferred/documented.

---

## Fix checklist

### 🔴 Blocker
- [ ] **B1** Systemic broken access control / IDOR — login issues no token; every data + settings
  endpoint trusts a client-supplied `user_id` query param. *(architectural — see decision note below)*

### 🟠 Major
- [x] **M1** AI onboarding failures return HTTP 200 and render as fake success (default path, since `GOOGLE_API_KEY` is unset) — `backend_api/routers/on_boarding.py:36-45`, `ai_module/recommender.py:44-45`.
- [~] **M2** Unauthenticated AI endpoint lets any client spend the server's Gemini key (financial DoS + prompt injection) — `backend_api/routers/on_boarding.py:36-45`.
- [ ] **M3** AWS connection secrets (IAM role ARN + externalId) live only in browser `localStorage`, never persisted server-side; "Connected" is cosmetic — `frontend/app/lib/session.ts`, `account-settings/page.tsx:343-349`.
- [ ] **M4** Home dashboard only fetches in demo mode → real connected accounts get a permanently blank page — `frontend/app/(main)/dashboard/home/page.tsx:734-742,827`.
- [x] **M5** `python -m data_generation.synthetic --days 365` is a no-op (no `main()`, never writes) yet README + 3 dashboard pages tell empty-DB users to run it — `data_generation/synthetic.py`.

### 🟡 Minor
- [x] **m1** SQLite connection leak in forecast router (`with` commits but never closes) — `backend_api/routers/forecast.py:48-62`.
- [x] **m2** Settings JSON persistence non-atomic + race-prone; corrupt file silently wipes all users to `{}` — `backend_api/routers/settings.py:60-70,124-145`.
- [x] **m3** Malformed Custom `start_date` → unhandled 500 from untrusted param — `backend_api/routers/costs.py:43-49,103`.
- [x] **m4** `GET /api/recommendations` mutates the DB by default (`generate_if_empty=True` runs an LP solve + commit on read) — `backend_api/routers/recommendations.py:143-158`.
- [x] **m5** Two dead duplicate modules: `backend_api/database.py` (zero importers) and `backend_api/config.py` (drifting copy of root `config.py`).
- [x] **m6** Loose demo detection `"SYNTHETIC" in user_id.upper()` fails closed, locking matching users out of settings writes — `backend_api/routers/settings.py:53`.
- [x] **m7** No rate limiting / lockout on `/api/auth/login`; signup leaks email-enumeration via verbatim `ValueError` — `backend_api/routers/auth.py:64-89,122-125`.
- [ ] **m8** Costs page has no loading/error UI — a failed fetch silently blanks the page — `frontend/app/(main)/dashboard/costs/page.tsx:575-643`.
- [ ] **m9** Demo-mode / user-id resolution duplicated in ~5 diverging copies — `session.ts`, `home`, `costs`, `forecasts`, `recommendations`.
- [~] **m10** `API_BASE` redeclared in 8 files with 3 normalizations (trailing-slash bug on 2 pages) — export one constant.
- [ ] **m11** ~24 `as any` casts around Plotly; types already imported — `home/costs/forecasts` pages.
- [ ] **m12** Home load effect fire-once, no `storage`/`optic-user-updated` listeners → stale after cross-tab workspace switch — `home/page.tsx:707-792`.
- [ ] **m13** Bleeding-edge deps + duplicate Plotly bundle (`react-plotly.js@^2.6.0` pulls full `plotly.js@3.4.0` alongside `plotly.js-dist-min`) — `frontend/package.json`.
- [x] **m14** Generated column names don't match `insert_*` contracts (`cost_amount`/`service_name`) — `data_generation/synthetic.py:43,54-76`.
- [x] **m15** `.gitignore` ignores the committed, mandatory `data/cloud_optimizer.db` (also missing trailing newline) — `.gitignore:68`.
- [x] **m16** ~13 MB of unoptimized binaries in `frontend/public`, incl. a byte-identical dup (`engineer.png` == `images/background.png`) and a 1.9 MB `logo.png`.
- [x] **m17** Stale README command `python -m ml_engine --user-id ...` always exits 1.

### ⚪ Nits
- [x] **n1** Forecast horizon cap `le=90` vs `RuntimeSettings.forecast_horizon_days` up to 180.
- [x] **n2** Costs response duplicates `daily_costs` as `daily_records` (frontend reads only the former).
- [x] **n3** CORS `allow_credentials=True` with `['*']` methods/headers (inert footgun; fixed localhost origins).
- [x] **n4** Tailwind installed but unused; 0-byte `tailwind.config.ts`.
- [x] **n5** `global.c.ts` should be `global.d.ts`.
- [x] **n6** `DEMO_MODE` dropped from docs/`.env.example` but still read in `config.py`.
- [x] **n7** `generate_instance_pricing` returns an opaque `(df, 0, count)` tuple.
- [ ] **n8** Entire 33,836-line change is one squashed commit with no PR body (process nit — not fixable retroactively).

---

## Detail — Blocker

### B1. Systemic broken access control / IDOR
- Login issues **no token and no session cookie** — returns plain identity JSON (`backend_api/routers/auth.py:82-89`).
- Frontend persists identity in **non-httpOnly, forgeable `localStorage`** (`frontend/app/lib/session.ts:48-90`, `login/page.tsx:34-57`).
- **Every** data + settings endpoint trusts a client-supplied `user_id` query param, no server-side auth
  (`grep Depends|jwt|Security backend_api/` → 0 hits): reads `dashboard.py:62`, `recommendations.py:140`,
  `forecast.py:206`, `settings.py:99`; **writes** `settings.py:115` (update), `:137` (reset).
- `user_id` is enumerable (`aws-<accountId>`, plus the well-known `aws-SYNTHETIC-001`).

Net: an unauthenticated client can read any user's data and overwrite their settings by guessing `?user_id=`.
**For this synthetic-data localhost demo this is a documented limitation, not an exploitable production breach** —
but the PR title advertises multi-user auth, so it's a genuine contract mismatch.
**Proper fix:** issue a signed, expiring credential on login (httpOnly+Secure+SameSite cookie or JWT), resolve the
caller via `Depends(get_current_user)`, derive `user_id` from the authenticated principal, never accept it as a query param.

## Detail — Strengths (keep these)
- **Password hashing** correct + hardened: PBKDF2-HMAC-SHA256, 260k iters, 16-byte salt, `compare_digest`; `verify_password` returns False on non-hex hashes; shared constants keep hash/verify in sync.
- **`config.py` `load_dotenv`** correctly ordered (before every `os.getenv`, `override=False`) — closes the ".env ignored" gotcha; python-dotenv now genuinely used.
- **`get_connection` `timeout`/`busy_timeout`** — right move for concurrent WAL access (FastAPI + Streamlit + collector).
- **Forecast caches correctly keyed** by `(user_id, model, horizon, content-fingerprint)` — no cross-user leak (only caveat: unbounded growth).
- **Backend/frontend type contracts line up field-for-field**; division-by-zero guarded; `optimize()` signature matches.
- **Security hygiene**: no hardcoded secrets, correct `.gitignore` negations, parameterized SQL, pydantic bounds + server-side validation, no XSS sinks.
- **Login/forecasts fetch hygiene** (AbortController + timeout, safe JSON parse, explicit states, comparison cache) — the bar the other pages should meet.
- **README backend+frontend setup accurate and runnable**; all new deps declared; `package-lock.json` committed.
