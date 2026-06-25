# gp-docs — Graduation Project Documentation

This folder holds the graduation-project (GP) thesis and the prompt that
turns it into a polished, defense-ready document **without changing the
college-mandated formatting**.

## Files

| File | What it is |
|------|------------|
| `AWS_Cost_Intelligence_System.docx` | The original thesis (Times New Roman, ~80 pages, 6 chapters). **Do not edit by hand — it is the immutable source.** |
| `PROMPT.md` | The master prompt. Paste everything below its horizontal rule into Claude Code to professionalize the thesis. |
| `README.md` | This file. |

## How to use the prompt

1. Make sure the original `.docx` is in this folder (it is).
2. Open Claude Code in the repository root (`/home/user/smart-cloud-optimizer`).
3. Open `gp-docs/PROMPT.md`, copy everything **below the `---` horizontal rule**, and paste it as a single message to Claude Code.
4. Let it run. It orchestrates the whole job with the **Workflow tool + fan-out subagents + an adversarial verification pass** (8 phases), so it will take a while and spawn many agents — that is intentional and gives the thorough, double-checked result.

## What it produces (in this folder)

- `AWS_Cost_Intelligence_System.POLISHED.docx` — the professionalized thesis. The original stays untouched.
- `CHANGELOG.md` — every change grouped by category (grammar, register, emoji removal, terminology, citations, captions, code-grounded fixes…).
- `PRESERVATION_REPORT.md` — proof the visual design did not drift (fonts, sizes, styles, TOC, headers/footers, figures).
- `OPEN_QUESTIONS.md` — gaps only a human can fill (real measured numbers, supervisor name, the Arabic-abstract native-speaker check, etc.).
- `work/` — all intermediate artifacts, so every change is auditable.

## The non-negotiable rule: the design is preserved

Your teammate is right that the college requires a specific look, so the
prompt treats the **visual design as immutable** and only improves the
*words and their correctness*:

- **Body font stays Times New Roman**; all font sizes (14pt body, 12pt, 18pt/16pt headings, large cover sizes) stay exactly as-is.
- Heading styles, the Table of Contents (with dot leaders), List of Figures / Tables / Abbreviations, headers, footers, page numbering, cover page, section breaks, and all six embedded figures are kept untouched.
- A `Cambria Math` equation run is preserved. The only formatting change is removing the ~30 **emoji** runs (e.g. ✅ ❌ ⚠), which are unprofessional in a thesis — and even arrows like `→` are handled deliberately, never blindly deleted.
- A **preservation guard** (`work/preservation_guard.py`) compares the original vs. the polished file and **fails the task** if any font or style drifts. That is the safety net for "the college font."

## Things to expect (honest caveats)

- It will **never invent numbers or citations.** Any metric or source it can't verify against the real code/`paper/` is flagged in `OPEN_QUESTIONS.md` for the team to fill — so the file is not "submission-complete" until you provide those.
- The **Arabic abstract** is improved but flagged for a native-speaker review before submission.
- A few pre-existing stray `Calibri` / `Segoe UI Symbol` runs are left alone (flagged, not auto-restyled) unless you approve normalizing them.
- After it runs, **open the polished `.docx` in real Microsoft Word** to confirm the look — LibreOffice/automation checks are a strong sanity check, not a substitute for the team's eyes.
