# MASTER PROMPT — Verify the System Against the Code, Then Generate Accurate Diagrams

Paste everything below the horizontal rule into a **fresh** Claude Code session in this project. It is self-contained.

Purpose: before adding architecture / use-case / sequence / ER diagrams to the thesis, **verify what the system actually does against the real source code**, then produce diagrams that match reality (no invented components, no guessed flows). Every element in every diagram must be traceable to a file in the repo.

---

## Mission
You are working in this graduation-project repository (an AWS cost-intelligence system: a Streamlit dashboard over an AWS cost collector, an ML forecasting/anomaly engine, a cost optimizer, and a Gemini-based AI recommendation module). Your job has two parts:
1. **Verify** the system's architecture, actors, use cases, key runtime sequences, and database schema **against the actual code** — confirming or correcting each claim with file-and-line evidence.
2. **Generate** clean, submission-ready diagrams (architecture, use-case, sequence, ER, and optionally data-flow) that reflect the **verified** reality, as ready-to-render source files plus rendered images where tooling allows.

**Ground rule: invent nothing.** If a component, actor, use case, table, or interaction is not in the code, it does not go in a diagram. Anything you cannot confirm is listed as UNVERIFIED for the human team — never drawn as if it were real.

You MUST do this rigorously by orchestrating with the **Workflow tool + fan-out subagents + an independent adversarial verification pass** — not a single linear scan.

---

## Do NOT touch the thesis or its formatting
This task only **reads** the code and **creates new diagram files** under a new `diagrams/` folder in the docs directory. Do **not** edit the `.docx`, the polished/corrected thesis, or any document. Diagrams are delivered as separate source + image files for the team to place into the thesis themselves (so the college formatting is never at risk).

---

## STEP 0 — Orient (don't trust hardcoded paths)
1. Find the project root and confirm these exist (names may vary slightly): `app.py`; modules `aws_collector/`, `storage/`, `ml_engine/`, `optimizer/`, `ai_module/`, `dashboard/`; `data/` (the SQLite DB); `tests/`; and `documentation/` (especially `ARCHITECTURE.md`, `DATA_PIPELINE.md`, `DATA_SCHEMAS.md`, `MODULES.md`, `schema.sql`).
2. Find the docs folder used for deliverables (e.g. `docs-gp/` or `gp-docs/`); create `<docs>/diagrams/` for outputs.
3. Check tooling for rendering: is `mermaid-cli` (`mmdc`), `plantuml`, Graphviz (`dot`), or `draw.io`/`drawio` CLI available? If none, still produce the **source** files and clear render instructions; render to PNG/SVG only where a tool exists. (`sqlite3` is useful for confirming the live schema in `data/*.db`.)

---

## CLAIMS TO VERIFY (confirm each against code; cite `file:line`)
Treat every item below as a hypothesis to prove or correct. For each, record: **VERIFIED** (with evidence) / **CORRECTED** (what it actually is + evidence) / **UNVERIFIED** (not found).

### 1. Components & architecture (layered view)
- **Presentation:** `app.py` (Streamlit entry, auth gate, 5-page nav) → `dashboard/` pages `home.py`, `costs.py`, `forecasts.py`, `recommendations.py`, `settings.py`, plus `auth.py`, `components.py`. Confirm the page set and the auth gate.
- **Data collection:** `aws_collector/` — `collectors/`, `main.py`, `runner.py`, `metrics.py`, `transforms.py`, `pricing_constants.py`, `config.py`. Confirm which AWS services/SDK (boto3?) it talks to and what it writes.
- **Storage:** `storage/db.py` over **SQLite** at `data/cloud_optimizer.db`. Confirm the engine and the access API.
- **ML engine:** `ml_engine/` — `forecaster.py` (which models? Naive/SeasonalNaive/ETS/Prophet/SARIMAX?), `anomaly.py` (detector method?), `evaluator.py` (CV?), `data_prep.py`.
- **Optimizer:** `optimizer/` — `engine.py`, `rules.py` (how many rules?), `compute_lp.py` (MILP / linear programming — which library?).
- **AI module:** `ai_module/` — `recommender.py`, `prompt_builder.py`, `guided_questions.py`, `ui.py`. Confirm the LLM provider (Gemini?) and how it is called.
- Confirm the **data flow direction**: AWS → collector → SQLite → (ML + optimizer + AI) → dashboard. Correct any arrow that the code contradicts.

### 2. Actors (for the use-case diagram)
Confirm the real actors. Candidates: **User** (authenticated dashboard user — check `auth.py` for roles/demo user), **AWS account** (external system the collector reads from — check the SDK/credentials path), **Gemini / LLM API** (external system the AI module calls). Note whether collection is **user-triggered** or a **separate manual/background process** (this changed in the thesis corrections — verify against `dashboard/settings.py` and `aws_collector/main.py`).

### 3. Use cases (what the user can actually do)
Derive strictly from the dashboard pages and their buttons/actions. Likely: authenticate / demo login; view cost overview (Home); analyze costs (Costs); generate/compare forecasts (Forecasts — confirm manual model dropdown vs auto-selection); view recommendations (Recommendations); answer the guided questionnaire / get AI advice (ai_module); manage AWS accounts & settings (Settings). Confirm each against the page code; drop any that don't exist (e.g. password change, save-as-PDF, "test connection" — verify before drawing).

### 4. Key sequences (pick the 2–3 most defensible flows)
Trace the real call path for each, function by function, citing files:
- **Forecast flow:** Forecasts page → `ml_engine` (data_prep → forecaster → evaluator) → storage read → chart render. Confirm whether anomalies are excluded from training (verify — the thesis was corrected to say they are **not**).
- **Recommendation flow:** Recommendations/AI page → `optimizer` (rules/engine/compute_lp) and/or `ai_module` (prompt_builder → recommender → Gemini) → storage → render. Confirm how optimizer rules and the LLM recommendations combine.
- **Data collection flow:** `aws_collector.main`/`runner` → AWS SDK → `transforms` → `storage/db.py`. Confirm it is a manual/standalone run, not auto-triggered by the dashboard.

### 5. Database schema (for the ER diagram)
Derive the ER model from `documentation/schema.sql` and confirm it against the **live** DB (`sqlite3 data/cloud_optimizer.db ".schema"`). Capture every table, its columns/keys, and the foreign-key relationships. Flag any drift between `schema.sql` and the live DB.

---

## ORCHESTRATION PLAN (Workflow + fan-out + adversarial verify)
1. **Phase 0 — Orient:** do STEP 0; create `diagrams/`; confirm tooling.
2. **Phase 1 — Evidence gathering (fan-out, read-only):** independent subagents, one per claim group (Architecture, Actors+UseCases, Sequences, Schema). Each returns a structured findings list: every element with VERIFIED/CORRECTED/UNVERIFIED + `file:line` evidence. The Schema agent also diffs `schema.sql` vs the live DB.
3. **Phase 2 — Adversarial verification (independent fan-out):** a second set of subagents that did NOT gather the evidence try to **falsify** each VERIFIED claim — open the cited file and confirm the element really exists and behaves as described. Anything unsupported is downgraded to UNVERIFIED. Produce a consolidated `diagrams/VERIFICATION.md` (claim → status → evidence).
4. **Phase 3 — Diagram generation (fan-out, one per diagram):** using ONLY VERIFIED/CORRECTED elements, author each diagram as source:
   - **Architecture** (layered component diagram) — Mermaid `flowchart` + a PlantUML component version.
   - **Use-Case** — PlantUML use-case (actors + use cases + associations).
   - **Sequence** (2–3 diagrams) — Mermaid `sequenceDiagram` and/or PlantUML for the verified flows.
   - **ER** — Mermaid `erDiagram` generated from the confirmed schema.
   - **(Optional) Data-Flow Diagram** — Mermaid flowchart of AWS → collector → storage → ML/optimizer/AI → dashboard.
   Keep one consistent visual style and clear labels. Save each as `diagrams/<name>.mmd` / `.puml`.
5. **Phase 4 — Render & self-check:** render to PNG/SVG where a tool exists (`mmdc`, `plantuml`, `dot`); otherwise write exact render instructions. A final subagent checks each rendered diagram against `VERIFICATION.md` to confirm **no UNVERIFIED element leaked into a diagram** and every label matches the evidence.

---

## Deliverables (all under `<docs>/diagrams/`)
1. **Diagram sources** — `architecture.mmd`+`.puml`, `usecase.puml`, `sequence_forecast.mmd`, `sequence_recommendation.mmd`, `sequence_collection.mmd`, `er.mmd` (and optional `dfd.mmd`).
2. **Rendered images** — PNG/SVG for each where tooling allowed; otherwise `RENDER_INSTRUCTIONS.md` (e.g. paste `.mmd` into mermaid.live, or import `.puml` into draw.io / PlantUML).
3. **`VERIFICATION.md`** — every claim with VERIFIED / CORRECTED / UNVERIFIED and `file:line` evidence; the `schema.sql` vs live-DB diff; and a short list of thesis statements these diagrams **contradict** (so the team can reconcile the text).
4. **`README.md`** — which diagram goes in which thesis chapter (Architecture → 3.1, Use-Case → 3.1/1, Sequences → 3.4/3.6, ER → 3.3), and a reminder to caption + number them ("Figure 3.x") and add them to the List of Figures in the same Times New Roman style as the document.

---

## Guardrails
- **Evidence or it doesn't exist.** Every diagram element must trace to code; UNVERIFIED items are reported, never drawn.
- **Do not edit the thesis or any `.docx`** — only create files under `diagrams/`.
- **No fabricated tables, actors, models, or flows.** If `schema.sql` and the live DB disagree, show both and flag.
- When a flow is ambiguous or a claim can't be confirmed, **flag it** rather than guessing.

## Definition of Done
- [ ] Workflow ran all phases; Phases 1–2 fanned out subagents; Phase 2 used independent verifiers.
- [ ] `VERIFICATION.md` covers architecture, actors, use cases, the 2–3 sequences, and the full schema, each with `file:line` evidence and a status.
- [ ] Every diagram uses only VERIFIED/CORRECTED elements; no UNVERIFIED element appears in any diagram.
- [ ] ER diagram matches the live DB schema (drift flagged if any).
- [ ] All sources produced; images rendered where tooling exists, else clear render instructions given.
- [ ] `README.md` maps each diagram to its thesis chapter and notes the contradictions (if any) for the team.

Begin with STEP 0 / Phase 0. Do not skip the adversarial verification (Phase 2) — it is what keeps the diagrams honest and defense-proof.
