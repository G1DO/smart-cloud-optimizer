# MASTER PROMPT — Professionalize the GP Thesis Without Touching the Design

Paste everything below the horizontal rule into Claude Code as a single prompt.

---

## Mission
You are working in the repository `/home/user/smart-cloud-optimizer`. Your single objective is to transform the existing graduation-project thesis at `gp-docs/AWS_Cost_Intelligence_System.docx` into a maximally professional, defense-ready academic document — improving the **writing, accuracy, consistency, and academic rigor** while keeping the **visual design byte-faithful** (fonts, sizes, heading styles, page layout, Table of Contents, headers, footers, cover page, figures, section breaks). You improve only the *words and their correctness*, never the *look*. Wherever you do not deliberately edit text, the on-page appearance must remain identical.

This thesis documents the real software in this same repository, so every technical claim can and must be grounded in the actual code. Invent nothing.

You MUST do this rigorously by orchestrating the work with the **Workflow tool, fan-out subagents, and an independent adversarial verification pass** — not as a single linear edit. The orchestration plan below is mandatory.

---

## THE #1 CONSTRAINT — PRESERVE THE DESIGN (read first, obey always)

A teammate confirmed the current fonts and formatting are exactly what the college mandated. **Treat the visual design as immutable.** You may rewrite *text content*; you may **not** change how anything looks. Preservation overrides every other goal: if a nicer edit and preserving the formatting ever conflict, **preserve the formatting** — leave the text as-is and log it instead.

**Do NOT change, for any paragraph you edit OR any paragraph you leave alone:**
- **Fonts.** Body text is **Times New Roman** on-page almost everywhere (the analyzed file has 437 `w:ascii="Times New Roman"` run declarations and 1394 total "Times New Roman" mentions in `word/document.xml`; both headers and both footers are 100% Times New Roman). The `.docx` theme nominally lists `Aptos`/`Aptos Display`, but body runs explicitly override to Times New Roman, so the *effective* on-page font is Times New Roman. Those explicit overrides must survive untouched on every run you keep. **Never let an edit fall back to Aptos, Calibri, or any theme default, and never introduce a font that is not already in the document.**
- **Pre-existing non–Times-New-Roman runs are NOT yours to "fix."** The analyzed file also contains a small number of non-TNR runs that already exist: **1 `Cambria Math`** run (legitimate — used for an equation; KEEP it), **5 `Calibri`** runs, **1 `Segoe UI Symbol`** run, and **30 `Segoe UI Emoji`** runs. Only the **Segoe UI Emoji** runs are in scope to change (see emoji method below). The stray Calibri / Segoe UI Symbol runs are a judgment call: **do not silently restyle them** — if you believe they should be Times New Roman, FLAG them in `OPEN_QUESTIONS.md` and leave them unless the human approves. Never touch the Cambria Math equation run.
- **Font sizes.** Half-point `w:sz`/`w:szCs` values must be preserved exactly. The analyzed distribution is dominated by `w:val="28"` (14pt, ~2967×) and `w:val="24"` (12pt, ~1166×); headings use `36`/`32` (18pt/16pt); other present sizes include `22`, `20`; the cover/title uses large sizes (`72`, `56`, `48`). Do not normalize, "tidy", round, or clean up any size.
- **Named styles.** Keep every `w:styleId` and every `w:pStyle`/`w:rStyle` reference exactly as-is, including `Heading1`/`Heading2`/`Heading3`, `Caption`, `ListParagraph`, `NoSpacing`, `NormalWeb`, `TOC1`/`TOC2`/`TOC3`, `TOCHeading`, `TableofFigures`, and the document's body style `font-claude-response-body` (these last names reveal the file's AI origin, but they are load-bearing — **renaming or removing them would alter the layout, so leave them untouched**). Do not add, rename, delete, re-point, or merge styles.
- **Bold/italic/underline, color, character/line spacing, indentation, alignment**, list numbering (`w:numPr`, `numbering.xml`), and all tab stops — including the **right-aligned dot-leader tabs** (`w:leader="dot"`; the analyzed file has 64 of them in the TOC/lists).
- **Front-matter mechanisms.** The Table of Contents, List of Figures, List of Tables, and List of Abbreviations — keep their structure and field codes. You may *update entry text* to match any heading/caption text you change, but never replace the TOC/field mechanism and never hand-edit page numbers.
- **Cover/title page**, **headers** (`header1.xml`, `header2.xml`), **footers** (`footer1.xml`, `footer2.xml`), page-numbering fields, both `w:sectPr` blocks, section breaks, page geometry, and margins.
- **Figures and embedded media.** Exactly six media files must remain present, in place, same bytes, same size, and referenced: `word/media/image1.jpeg`, `image2.png`, `image3.png`, `image4.png`, `image5.png`, `image6.png`. Do not re-encode, resize, reorder, or drop them.
- **Plumbing:** `word/_rels/document.xml.rels`, all other `*.rels`, `[Content_Types].xml`, `customXml/*`, `word/settings.xml`, `word/webSettings.xml`, `word/fontTable.xml`, `word/theme/theme1.xml`, `word/numbering.xml`, `word/footnotes.xml`, `word/endnotes.xml`.

**You change only the *text content* of runs (`<w:t>`), plus exactly one metadata file (`docProps/core.xml`).** You do not restructure the document skeleton, reorder chapters/sections, add/remove headings, or merge/split paragraphs — unless strictly required to fix a single clearly broken sentence, and never deleting a paragraph that carries layout meaning.

### The technical "how" of lossless preservation (mandatory method)
A `.docx` is a ZIP of XML parts. The complete part inventory of the analyzed file (28 parts) is: `[Content_Types].xml`; `_rels/.rels`; `customXml/item1.xml`, `customXml/itemProps1.xml`, `customXml/_rels/item1.xml.rels`; `docProps/app.xml`, `docProps/core.xml`; `word/document.xml`, `word/styles.xml`, `word/theme/theme1.xml`, `word/numbering.xml`, `word/settings.xml`, `word/webSettings.xml`, `word/fontTable.xml`, `word/footnotes.xml`, `word/endnotes.xml`, `word/header1.xml`, `word/header2.xml`, `word/footer1.xml`, `word/footer2.xml`, `word/_rels/document.xml.rels`; and `word/media/image1.jpeg`..`image6.png`.

**Two permitted editing techniques (pick per task; you may mix):**

- **Technique A — run-level `<w:t>` text edits in the XML** (preferred for surgical changes, emoji removal, and metadata). Unzip into a working folder preserving exact paths and filenames. Edit ONLY the text inside `<w:t>…</w:t>` elements (and `docProps/core.xml`). Never touch `<w:rPr>`, `<w:pPr>`, `<w:pStyle>`, `<w:sectPr>`, `<w:numPr>`, `<w:tabs>`, `<w:rFonts>`, `<w:sz>`, or any relationship. Preserve `xml:space="preserve"` wherever present. If you must split or join text across runs, **carry the original run's full `<w:rPr>` onto every resulting run** — never emit a run without the exact rPr the original had.
- **Technique B — `python-docx`** (handy for bulk paragraph-by-paragraph prose work). **It is not installed in this environment**, so `pip install python-docx` first; if installation fails (offline/locked), fall back to Technique A for everything — do not block on it. **Golden rule:** edit text at the existing `run.text` level so `run.font` (name, size, bold) and the paragraph `style` are preserved automatically. Where consecutive runs share *identical* `rPr`, you may consolidate corrected text into the first and blank the others; where formatting differs across runs (e.g. a bold term mid-sentence), edit within each run and keep its boundaries. Never call anything that reassigns a style, clears formatting, or sets a font to a theme/default; never use `add_paragraph`/`add_run` to replace existing structured content.

**Re-zip losslessly:** preserve all part names and paths exactly, do not reformat or pretty-print untouched XML, do not reorder or rename entries, keep `[Content_Types].xml` first if the original did. A correct re-zip opens in Microsoft Word with **zero repair prompts** and fonts visually identical.

> If a writing improvement would *require* a design change, **do not make the design change** — leave the text and flag it in `OPEN_QUESTIONS.md`.

### Emoji / symbol cleanup (30 emoji runs — handle precisely, do NOT over-delete)
The analyzed file has **30 runs whose font is `Segoe UI Emoji`** (this shows up as ~90 attribute occurrences across `w:ascii`/`w:hAnsi`/`w:cs`, so do not report it as "90 emojis"). The distinct emoji/symbol codepoints actually present in text are exactly:
- `✅` U+2705, `❌` U+274C, `⚠` U+26A0, and the variation selector `️` U+FE0F (and you must also catch any U+1F000+ pictographs, ZWJ U+200D, and surrogate-pair emoji if present). **These are true emojis — remove them.**
- `→` U+2192 (rightwards arrow) **is NOT an emoji** — it is a meaning-bearing typographic arrow (e.g., "input → output", "request → response"). **Do NOT blindly delete it.** Where it is decorative, convert it to a word ("to"/"yields"/"then") in the run's existing formatting; where it conveys a real mapping, keep it. Treat every `→` as a deliberate, logged decision — never a blanket strip.

Removal method (never break surrounding runs):
- If a true emoji sits in its own decorative run (e.g. `✅`/`❌` before a heading or bullet), delete that entire run **and** any now-orphaned leading/trailing space in the adjacent run, leaving the heading/text run and its formatting untouched.
- If a true emoji sits inside a text run, strip only the emoji + its variation selector from that run's `<w:t>`, keep the run and its rPr, and collapse any doubled space.
- If a removed emoji carried meaning (e.g. a ✅/❌ status cell in a table), replace it with a neutral textual equivalent ("Pass"/"Fail", "Implemented"/"Not implemented") in the existing run's formatting, and log it.
- Never delete a whole paragraph or its `pPr` just to remove an emoji. After removal, the kept text must retain its original font and size.

### The one metadata exception (`docProps/core.xml`)
The metadata is wrong: `<dc:title>` reads "Chapter one" and `<dc:subject>` reads "Introduction". Correct the title to the real thesis title ("AWS Cost Intelligence System") and set the subject appropriately ("Graduation Project Thesis"). Keep `<dc:creator>`/`<cp:lastModifiedBy>` "Ahmed Sameh" and any teammates already present; **do not invent names**. You may set sensible `<cp:keywords>`. Do not fabricate the supervisor. This is a properties-only change with no on-page effect; log every metadata field you touch.

---

## What "professional and perfect" means — the academic-quality rubric

Apply all of these to the **prose only**:

1. **Mechanics.** Flawless grammar, spelling, punctuation; consistent capitalization and hyphenation; no run-ons or fragments.
2. **Formal academic register.** Objective third-person academic English; no contractions; no first-person hype ("we built an amazing…"); no marketing fluff ("revolutionary", "cutting-edge", "seamless", "game-changing", "powerful"); no rhetorical questions; no second-person address to the reader.
3. **No emojis, no AI-tells.** Remove every true emoji (method above). Remove AI-writing tells: "delve", "in today's fast-paced world", "it is worth/important to note", "boasts/leverages" as filler, empty topic sentences, hollow tricolons, em-dash overuse, stacked "Furthermore/Moreover", sycophancy, and bullet-spam where prose is expected. Vary sentence structure; keep it precise and dense.
4. **Terminology & acronyms.** One canonical name per concept across all chapters (decide between "AWS Cost Intelligence System" and "Smart Cloud Optimizer" and use it consistently — note both only if intentional, and record the decision in `OPEN_QUESTIONS.md`). Define every acronym on first use and reconcile it with the **List of Abbreviations**; add missing entries (text-only) and flag (do not silently delete) seemingly unused ones.
5. **Abstracts (EN + AR).** The **English abstract** is a tight, self-contained 150–250 words stating problem, approach, methods, key quantitative results, and contribution. The **Arabic abstract** is a faithful, fluent, formal-Arabic translation that mirrors the finalized English abstract (not literal/MT-sounding); preserve its RTL direction and existing Arabic run properties (`w:rtl`, `w:bidi`, `w:cs`), and flag it for native-speaker review.
6. **Literature review (Ch.2).** Coherent, critical synthesis with consistent in-text citations (IEEE recommended, since an IEEE paper already lives in `paper/`), and a complete, consistent References/Bibliography where every in-text citation resolves to an entry and vice-versa. **Never fabricate a citation, DOI, author, venue, or year.** If a source is needed but unavailable, insert a visible placeholder `[CITATION NEEDED: <claim>]` rather than inventing one.
7. **Methodology (Ch.3).** Rigorous, reproducible, and accurate to the real architecture and module names.
8. **Results (Ch.4).** Every result presented with a numbered, captioned figure or table and an in-text cross-reference ("as shown in Figure 4.x / Table 4.x"); units stated; claims matching the numbers; numbers internally consistent. **Do not change any reported number** — if one looks inconsistent or unsupported, flag it; never "correct" it by inventing a value.
9. **Honest limitations** and trade-offs (Ch.6) — credible and specific, not defensive.
10. **Logical flow.** Smooth transitions within and across chapters; each chapter opens with a brief orienting sentence and closes with a summary that genuinely summarizes; no orphaned or duplicated content.
11. **Accuracy verified against the codebase** (grounding rules below) — unverifiable items flagged, never invented.

### Per-chapter checklist (mapped to THIS document)
- **Front Matter** — Acknowledgments (formal tone); English Abstract (rubric §5); Arabic Abstract (faithful translation, RTL preserved); verify TOC / List of Figures / List of Tables / List of Abbreviations entries match the final headings and captions (text only — do not regenerate fields); ensure the abbreviations list is complete and consistent.
- **Chapter 1 — Introduction** — clear problem statement, motivation, objectives, scope, contributions, thesis outline; align stated objectives with what the system actually does.
- **Chapter 2 — Literature Review** — 2.1 Introduction, 2.2 Cloud Cost Optimization, 2.3 Time-Series Forecasting for Cloud Workloads, 2.4 Anomaly Detection in Cloud Environments, 2.5 AI-Based Architecture Recommendation Systems, 2.6 Summary and Research Gaps. Real citations only; ensure 2.6 explicitly states the gap this project fills; build/clean the References section.
- **Chapter 3 — System Architecture & Methods** — 3.1 System Overview … 3.8 Summary. Match module names and data flow to the real code; ensure each architecture figure is captioned, numbered, and referenced in text.
- **Chapter 4 — System Implementation & Results** — 4.1 Introduction … 4.11 Summary. Development environment, datasets, and experiment setup must match the repo; forecasting / anomaly / cost-optimization / AI-recommendation / testing results each need captioned, numbered figures/tables plus cross-references; flag unverifiable numbers; keep 4.10 (challenges) honest and specific.
- **Chapter 5 — Run the Application** — 5.1 Introduction; 5.2 System Startup (+5.2.1 Prerequisites); 5.3 Demo Mode Walkthrough; 5.4 Real Mode Setup; 5.5 Key User Workflows; 5.6 Summary. Verify every command, path, env var, flag, and credential step against `README.md`/`app.py`/`config.py`/`documentation/`; fix anything inaccurate; keep screenshots and their captions.
- **Chapter 6 — Conclusion and Future Work** — 6.1 Project Summary, 6.2 Key Findings, 6.3 Impact and Value, 6.4 Limitations and Trade-offs, 6.5 Future Work, 6.6 Conclusion. Findings must reconcile with Ch.4; limitations honest; future work concrete and non-grandiose.

---

## Grounding rules — no fabrication, ever

The thesis documents the software in this repo. Cross-check every technical claim against reality, citing file evidence:
- **Modules:** `aws_collector/` (incl. `collectors/`, `metrics.py`, `pricing_constants.py`, `runner.py`, `transforms.py`, `main.py`), `storage/` (`db.py`), `ml_engine/` (`forecaster.py`, `anomaly.py`, `data_prep.py`, `evaluator.py`), `optimizer/` (`engine.py`, `rules.py`, `compute_lp.py`), `ai_module/` (`recommender.py`, `prompt_builder.py`, `guided_questions.py`, `ui.py`), `dashboard/` (`home.py`, `costs.py`, `forecasts.py`, `recommendations.py`, `auth.py`, `settings.py`, `components.py`), `data/`, `tests/` (`test_optimizer.py`, `test_ml_utils.py`, `test_storage.py`). **Verify the actual contents before relying on these names — treat this list as a starting map, not gospel.**
- **Entry/config:** `app.py`, `config.py`, `requirements.txt`, `pyproject.toml`, `README.md`.
- **Docs:** `documentation/` (`ARCHITECTURE.md`, `QUICKSTART.md`, `STARTUP.md`, `MODULES.md`, `forecasting_models.md`, `optimizer.md`, `recommendation.md`, `schema.sql`).
- **Authoritative internal source for results/citations:** `paper/` — an existing IEEE conference paper on capacity-reservation cost optimization (`main.tex`, `references.bib`, `results.json`, `cv_results.csv`, `numbers.tex`, `figures/`).

Rules:
- Module names, library names/versions, and architecture descriptions must match the code and `requirements.txt`/`pyproject.toml`.
- **Chapter 5 run instructions** must match the real `README.md`/`app.py`/`config.py`/`documentation/QUICKSTART.md`/`STARTUP.md`. Correct any command, filename, env var, or flag that does not match.
- **Numbers and results** (accuracy, MAPE, cost-savings %, latency, test counts): keep only numbers traceable to the code, `tests/`, `data/`, `paper/`, or existing document content. **Any number you cannot verify → flag it as a placeholder for the human team; never invent or "improve" a metric.** Reconcile the thesis against `paper/` and flag contradictions.
- **When you cannot verify a factual claim, flag it — do not guess, do not delete silently, do not fabricate a replacement.**

---

## ORCHESTRATION PLAN — Workflow tool + fan-out subagents + adversarial verification

Drive the entire job through the **Workflow tool**. Use **fan-out subagents** for parallelizable work and **independent adversarial verifier** subagents that try to break your output. Use **barriers** where a phase's full output is needed before the next begins. Give every content-editing subagent the grounding rules and the full preservation contract verbatim. Persist all intermediate artifacts under `gp-docs/work/` so phases are auditable, reproducible, and resumable. Announce each phase, the subagents you fan out, and their returned results as you go.

> **Global rule for every content-editing subagent:** it operates on **extracted text segments**, never the live `.docx`. Subagents return *revised text + a per-change rationale + a run-index map back to the XML*. Only the **Assembly** phase (Phase 6) writes back into XML, run-by-run, preserving `rPr`/`pPr`. This centralizes formatting preservation and keeps it auditable.

### Phase 0 — Setup & Baseline Snapshot (single agent, barrier)
- Copy the original to an immutable baseline `gp-docs/work/ORIGINAL.docx` (never edit it). Create the working copy and unzip it into `gp-docs/work/extracted/` preserving structure.
- Record a **baseline formatting fingerprint** at `gp-docs/work/baseline-fingerprint.json`: the exact list of 28 parts; the `media/image*` inventory with SHA-256 checksums; the full multiset of `w:rFonts` values (ascii/hAnsi/cs/eastAsia) and of `w:sz`/`w:szCs` values; the set of `w:styleId`s and of referenced `w:pStyle`/`w:rStyle` ids; both `w:sectPr` blocks; all `w:numPr` and tab-stop defs (incl. the 64 TOC `w:leader="dot"` tabs); and SHA-256 of `styles.xml`, `theme1.xml`, `numbering.xml`, `settings.xml`, `fontTable.xml`, `header1.xml`, `header2.xml`, `footer1.xml`, `footer2.xml`.
- Correct `docProps/core.xml` metadata here (title/subject per the metadata exception). Metadata only.

### Phase 1 — Inventory & Extraction (single agent, barrier)
- Parse `word/document.xml` into an ordered map of paragraphs → runs, each tagged with chapter/section, style id, `rPr` summary, emoji/non-TNR-font flag, and zone (front matter / body / caption / TOC field / header / footer).
- Build a **segment manifest** at `gp-docs/work/segments/` (one file per chapter + per front-matter block) with editable text plus a stable run-index map for Assembly.
- Build a **figure/table register** (`gp-docs/work/figure-register.json`): every image relationship, current caption text, and every in-text figure/table reference. Build an **acronym table** (`gp-docs/work/acronyms.json`), an **emoji/symbol-hit list** (`gp-docs/work/emoji-hits.json`, with codepoint + whether it is a true emoji or the `→` arrow), and a **non-TNR-run list** (the Calibri / Segoe UI Symbol / Cambria Math runs, classified keep-vs-flag).
- Output `gp-docs/work/INVENTORY.md`: structure confirmation, emoji/symbol locations, non-TNR runs, metadata issues, and the figure/table list with current captions.

### Phase 2 — Codebase Ground-Truth Brief (fan-out, read-only, barrier)
Fan out read-only subagents to build the factual reference the writers will use:
- **Subagent A (architecture):** read `app.py`, `config.py`, and each module → verified architecture/data-flow summary and canonical component names.
- **Subagent B (run instructions):** read `README.md`, `app.py`, `config.py`, `requirements.txt`, `pyproject.toml`, `documentation/QUICKSTART.md`/`STARTUP.md` → exact prerequisites, install steps, run command(s), demo-vs-real mode, and env/config keys for Chapter 5.
- **Subagent C (results/metrics):** read `tests/`, `data/`, `paper/`, `documentation/` → every defensible metric with its source, plus the metrics that appear in the thesis but cannot be sourced.
- **Subagent D (citations/related work):** read `paper/references.bib` and `documentation/` → reusable, real bibliography entries and related-work facts.
- Merge into a single **Ground-Truth Brief** at `gp-docs/work/ground-truth.md` that every Phase-3 writer receives. Record source conflicts as flags; do not silently resolve them.

### Phase 3 — Parallel Per-Chapter Polishing (fan-out, barrier)
Spawn parallel subagents — one each for Front Matter, Chapter 1, Chapter 2, Chapter 3, Chapter 4, Chapter 5, Chapter 6. Each **receives** its segment file, the Ground-Truth Brief, the rubric + per-chapter checklist, the acronym table, and the figure register. Each **returns** run-aligned revised text, a per-change log categorized as `{grammar, register, emoji-removal, ai-tell-removal, terminology, accuracy-fix, citation, caption, transition}`, the facts it relied on, and a list of unverifiable claims/placeholders it flagged. **Constraints (verbatim to each):** no skeleton restructuring; no moved/added/removed sections or headings; preserve meaning and author intent; conservative edits only; flag, don't fabricate.
- The **English Abstract** subagent drafts the canonical abstract the Arabic subagent must mirror.
- The **Arabic Abstract** subagent works strictly within existing Arabic runs, preserves RTL and run properties, and produces a fluent translation of the finalized English abstract — flagged for human review.
- The **Front-matter/TOC** subagent does **not** rebuild fields; it only proposes corrected entry text to match changed headings.
- The **Ch.4** subagent must not change any numeric result; the **Ch.2** subagent must not add or alter a citation without a verifiable source.

### Phase 4 — Cross-Document Consistency Pass (single coordinating agent, barrier)
Merge all chapter edits and enforce what per-chapter agents could not see:
- **Terminology/acronym unifier:** one canonical term per concept; every acronym defined on first use and present in the List of Abbreviations; reconcile the abbreviations list (flag, don't silently add unknown acronyms).
- **Figure/table consistency:** sequential numbering, every figure/table captioned, every in-text cross-reference resolves. Do not move or re-anchor images.
- **Citation/reference reconciler:** every in-text citation has a bibliography entry and vice-versa; uniform style; zero orphans; **zero fabricated entries**.
- **Tense/voice and flow:** methods in past tense, established facts in present; chapter intros/summaries align; no duplicated boilerplate.
- Output `gp-docs/work/consistency-report.md` plus the consolidated revision set.

### Phase 5 — Adversarial Content Verification (independent fan-out, barrier — BEFORE assembly)
Spawn **independent red-team** subagents that did NOT do the writing; their job is to find failures, not to praise:
- **Fact-checker (adversarial):** attempt to falsify each technical claim, module name, command, and number against the code. Any claim not directly supported → FAIL/UNVERIFIED with evidence.
- **AI-tell / register auditor:** scan for any remaining true emoji, contraction, hype phrase, or AI-tell; must return an empty findings list to pass.
- **Citation auditor:** find any citation without a real source or any bibliography entry not cited; fabricated-source detection.
- **Meaning-preservation auditor:** diff revised vs original segment-by-segment to confirm no factual claim or author intent was changed or dropped (only improved); flag any silent semantic drift, including any `→` arrow whose meaning was altered.
- Route findings back to the relevant Phase-3/4 logic. **Loop Phases 3→5 on affected segments until red-team findings are empty or explicitly converted to human-review flags.** Do not proceed to Assembly with open FAILs.

### Phase 6 — Assembly (single agent, barrier — the ONLY phase that writes XML)
- Write each finalized revision back to its **exact original runs** in `word/document.xml` (and the relevant header/footer XML for any header/footer text), **inheriting the original `rPr` for every run.** Where a revision needs more or fewer runs, clone the neighbor run's `rPr` so fonts/sizes/styles stay identical. Remove true-emoji runs per the method above — never the surrounding paragraph or its `pPr`. Apply the `→` decisions logged in Phase 1/3.
- Update TOC / LoF / LoT entry text and the List of Abbreviations to match changed headings/captions (without replacing field mechanisms; do not hand-edit page numbers).
- Re-zip losslessly into `gp-docs/AWS_Cost_Intelligence_System.POLISHED.docx`. The immutable original remains at `gp-docs/work/ORIGINAL.docx`.

### Phase 7 — Adversarial Formatting-Preservation Verification (independent fan-out, HARD gate to done)
Spawn **independent** verifier subagents (not the editors) whose explicit job is to *try to prove the design changed*. Implement and run a guard script at `gp-docs/work/preservation_guard.py` comparing `ORIGINAL.docx` vs the polished file that **exits non-zero on any drift**. It must at minimum:
1. **Part inventory:** identical set of part names. Only `docProps/core.xml` (metadata) and `word/document.xml` + `header*/footer*.xml` (`<w:t>` text) may differ; everything else must match.
2. **Formatting-token multisets** (parse `document.xml`, `header*.xml`, `footer*.xml`): compare as multisets all `w:rFonts` (ascii/hAnsi/cs/eastAsia), all `w:sz`/`w:szCs`, all `w:pStyle`/`w:rStyle` ids, both `w:sectPr` blocks, all `w:numPr`, and all tab-stop defs incl. `w:leader="dot"`. **Text content is excluded; only formatting tokens are compared. Any added/removed/changed token = FAIL** — with this one allowance: the `w:rFonts` multiset is allowed to *lose* `Segoe UI Emoji` entries (emoji removal) but may not *gain* any font and may not lose `Times New Roman`, `Cambria Math`, `Calibri`, or `Segoe UI Symbol` unless that exact change was explicitly approved and logged.
3. **Byte-identity:** `styles.xml`, `theme1.xml`, `numbering.xml`, `settings.xml`, `webSettings.xml`, `fontTable.xml`, `footnotes.xml`, `endnotes.xml`, `customXml/*`, and every `word/media/` file must be **byte-identical** (FAIL otherwise). `header*/footer*.xml` must be byte-identical unless header/footer text was deliberately edited (then formatting-token-identical).
4. **Emoji gate:** zero true-emoji codepoints (✅ U+2705, ❌ U+274C, ⚠ U+26A0, U+FE0F, any U+1F000+, ZWJ-joined sequences) remain, and the `Segoe UI Emoji` font count is **0**. **Do NOT assert that every run is Times New Roman** — the document legitimately contains 1 Cambria Math run and may retain pre-existing Calibri/Segoe-UI-Symbol runs; instead assert **no NEW non-TNR font was introduced** relative to the baseline fingerprint.
5. **Validity:** every XML part is well-formed; the ZIP is valid; the file opens with no Word repair prompt. If `python-docx` is installed, a round-trip must open cleanly. If LibreOffice headless is available (it is, at `/usr/bin/soffice`), export both ORIGINAL and POLISHED to PDF and compare page count, heading appearance, TOC, and figure placement within a tiny tolerance.

If any assertion fails → **stop, report the exact diff, fix the Assembly method, and repeat.** A formatting regression is a hard failure, not a warning. Output `gp-docs/work/preservation-verification.md` (pass/fail per assertion, with before/after numbers).

---

## Deliverables (produce all four)
1. **`gp-docs/AWS_Cost_Intelligence_System.POLISHED.docx`** — the professionalized thesis. The original stays untouched at `gp-docs/work/ORIGINAL.docx`.
2. **`gp-docs/CHANGELOG.md`** — every change grouped by category: grammar/spelling, register/de-hype, emoji removal, AI-tell removal, terminology/acronym unification, citations/references, figure/table captioning & cross-refs, transitions, code-grounded technical corrections, metadata fix, and `→`-arrow decisions. Include counts and representative before/after examples per category.
3. **`gp-docs/PRESERVATION_REPORT.md`** — the Phase-7 guard results plus the baseline-vs-final fingerprint diff for fonts, sizes, style ids, section props, numbering, headers/footers, and media; an explicit PASS/FAIL line for headings, TOC, headers/footers, and cover page; and a statement that the visual design is byte-faithful where untouched and that no new font was introduced (Times New Roman + Cambria Math equation + all sizes/styles intact; emoji font removed).
4. **`gp-docs/OPEN_QUESTIONS.md`** — everything the human team must supply or confirm, each with its document location: real measured numbers flagged as placeholders; missing/needed citations; supervisor/committee/teammate names; the date; the canonical-title decision; the Arabic-abstract native-speaker check; the disposition of the stray Calibri / Segoe UI Symbol runs; any contradicted/unverifiable technical claim; and any place where a writing fix was blocked by the no-design-change rule.

---

## Guardrails (non-negotiable)
- **Never fabricate** data, results, numbers, measurements, citations, DOIs, authors, venues, or dates. Flag gaps; never fill them with guesses.
- **Never change the visual design.** Fonts (keep Times New Roman; keep the Cambria Math equation run), sizes, heading styles, numbering, TOC, headers/footers, cover, page layout, and figures are immutable. The only permitted non-text change is the `docProps/core.xml` metadata correction. A design regression fails the task.
- **Preserve author intent and meaning** — improve expression and correctness; never invent claims, change technical conclusions, or alter reported numbers.
- **Keep the document skeleton** — same chapters and sections in the same order; no silent restructuring; no added/removed/merged sections or headings.
- **Conservative prose edits only** — minimal, surgical, justifiable to a thesis examiner; do not rewrite a correct paragraph just to restyle it.
- **When uncertain about a fact or a formatting risk, stop and flag — do not guess.** If `python-docx` risks dropping formatting on a paragraph, use Technique A instead.
- Keep all intermediate work under `gp-docs/work/` so every change is auditable and the run is resumable.

---

## Definition of Done (final checklist — all must be true)
- [ ] Workflow executed all phases; Phases 2, 3, 5, and 7 fanned out subagents; Phases 5 and 7 used **independent** adversarial verifiers; intermediate artifacts saved under `gp-docs/work/`.
- [ ] `AWS_Cost_Intelligence_System.POLISHED.docx` opens in Microsoft Word with **no repair prompt**, is valid OOXML, and is visually identical to the original (Times New Roman, all sizes, all heading styles, TOC with dot leaders, headers/footers, cover page, all six figures, page layout).
- [ ] **Preservation guard passed:** identical 28-part inventory (only `core.xml` + text differs); no new font introduced (no Aptos/Calibri leakage beyond pre-existing); unchanged `w:sz` distribution on untouched text; identical style-id set (incl. `font-claude-response-body`, `TOCHeading`); unchanged `sectPr`/`numbering.xml`/headers/footers/section breaks; byte-identical `media/image1.jpeg`+`image2..6.png`; valid ZIP. PASS recorded for headings, TOC, headers/footers, cover.
- [ ] Zero true emojis and zero `Segoe UI Emoji` runs remain; the Cambria Math equation run preserved; every `→` arrow handled deliberately and logged.
- [ ] Prose is grammatically flawless, formal, contraction-free, fluff-free, and AI-tell-free (auditor returned empty).
- [ ] Terminology and acronyms unified and reconciled with the List of Abbreviations; every acronym defined on first use.
- [ ] English abstract meets the rubric; Arabic abstract is a faithful, fluent translation with RTL preserved and flagged for native review.
- [ ] Every in-text citation resolves to a real reference and vice-versa; no fabricated sources; References section clean.
- [ ] Every figure/table is numbered, captioned, and cross-referenced; numbers internally consistent and unchanged.
- [ ] All technical claims, module names, metrics, and Chapter 5 run instructions verified against the codebase, or flagged as placeholders; nothing invented.
- [ ] `docProps/core.xml` metadata corrected (no more "Chapter one"/"Introduction"); no other metadata or design changed.
- [ ] All four deliverables produced: `…POLISHED.docx`, `CHANGELOG.md`, `PRESERVATION_REPORT.md`, `OPEN_QUESTIONS.md`.

Begin with Phase 0. Do not skip the adversarial content verification (Phase 5) or the preservation guard (Phase 7) — they are the gates that make this both "perfect" and "safe for the college font."