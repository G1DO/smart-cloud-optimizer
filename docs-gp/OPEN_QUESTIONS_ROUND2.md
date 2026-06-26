# OPEN QUESTIONS — Round 2 (items left for the human team)

These are the things the corrections pass **could not or should not decide automatically** — facts needing a
human source, judgment calls on framing, low‑confidence cover details, an image that can't be edited as text,
and the one manual Word step. Everything factual and reproducible was already corrected (see
`CHANGELOG_ROUND2.md`); the items below are what remains.

Priority: **A** = do before submission · **B** = confirm framing · **C** = citations to source · **D** = polish.

---

## A — Must handle before submission

1. **Refresh Word fields (mechanical, required).** Open `AWS Cost Intelligence System.CORRECTED.docx`, press
   **Ctrl+A then F9** to rebuild the Table of Contents, **List of Tables**, and List of Figures, then re‑check
   all page numbers. This propagates the renamed heading **5.4.3 "Running Data Collection"** and the corrected
   **Table 4.6 / Table 4.7** captions. (Done automatically only if you have LibreOffice; otherwise it must be
   done in Word.)

2. **Arabic abstract — native‑speaker review (F1).** Left textually unchanged. It currently **mirrors the
   English errors that were corrected**, so it must be reconciled to the *corrected* English by a native
   Arabic speaker:
   - P0052.S11 contains «مع آلية اختيار **تلقائية** للنموذج» ("an **automatic** model‑selection mechanism") —
     the same false runtime claim that was reframed in English; drop "تلقائية / automatic".
   - P0053 carries the «بين 10% و18%» (10–18% MAPE) range — reconcile to the corrected forecasting result
     (ETS ≈11.2% best; Prophet ~14–22%).
   Also review formal‑MSA register; do not reorder segments.

3. **Abstract forecasting range "approximately 10% to 18% MAPE" (P0047) — author decision.** Deliberately
   **not changed**. It is only loosely supportable: the 10% low matches Seasonal Naive (10.18% @ h7) but the
   18% ceiling understates Prophet's worst case (~22%). Choose one: (a) keep as a high‑level summary that
   never names Prophet's worst case; (b) tighten to the best‑model reality (ETS ≈11–12%); or (c) widen to
   ~22%. The abstract also names only 3 of the 5 models (omits Naive, SARIMAX) — optional to expand.

4. **Figure 3.2 (image, not editable as text).** The §3.4.4 decision‑tree figure still depicts the **old
   Prophet‑favoring** selection logic. The surrounding prose was corrected (Seasonal Naive/ETS best, Prophet
   worst), so the figure now contradicts the text. **Regenerate or relabel the figure** to match the corrected
   narrative (or reframe it explicitly as the *designed* selection strategy).

## B — Confirm the framing (design‑intent vs runtime reality)

5. **"Design intent" reframings (B1/B3/B5).** Several claims were softened to "the system is **designed to**…"
   rather than stating the blunt runtime reality. Confirm this framing is what you want, or switch to the
   runtime statement:
   - **B1** model selection — runtime is a manual dropdown defaulting to Prophet; no data‑age→model code
     exists (the tree lives only in `documentation/forecasting_models.md`). Reframed as design intent /
     offline analysis (abstract, Ch.1 P0442/P0455, Ch.3 §3.4.4, Ch.4 Table 4.9 cell, Ch.6, Ch.2 P0594).
   - **B3** "anomalies excluded from training" — the forecast path fits on raw daily costs; reframed as design
     intent (Ch.6 P1791/P1827).
   - **B5** "adding an account starts collection" — corrected to manual collection (P0451 reframed as design
     intent; P1690 corrected; heading **renamed 5.4.3 "Running Data Collection"** — confirm the new title).

6. **Demo Mode (B4).** The honesty caveat ("the `demo@cis.asu.edu.eg` account must first be seeded into the
   shipped database; otherwise 'Try Demo Mode' fails silently") was added at P1550. **Either seed the demo
   user into `data/cloud_optimizer.db`** (preferred, so the claim becomes true) or keep the caveat.

7. **Cover "Computer System Department" (E4) — low confidence.** Likely should be "Computer System**s**
   Department" (plural), but the canonical department name is unconfirmed. **Not changed** at P0024/P0029/P0034
   — please confirm and fix in the master copy if needed.

8. **Cover metadata (F5).** Confirm the supervisor/committee names and the submission date on the cover are
   final and correct. (Only the typo fixes E1–E3 were applied.)

## C — Citations to source or confirm (no sources were invented)

9. **Gartner reference P1919** ("Cloud Cost Optimization Strategies", 2023) is untraceable and absent from the
   curated `references.bib`. The in‑text Gartner attributions were removed (now cites Flexera only), so this
   list entry is now **orphaned**. **Remove it from the reference list**, or supply a real, citable Gartner
   publication. (Reference‑list deletion is a structural edit left for the master copy.)

10. **RightScale "63% of SMEs lack cost visibility" (P0526/P0433).** No source exists; kept softened to
    "industry surveys report that 63% …". **Supply a verifiable source or drop the figure.**

11. **Liu et al., "A Comprehensive Survey of Public Cloud Datasets", CSUR 2025 (P1917 / in‑text P0560).** Not
    in the curated bib; only a doc‑stated DOI `10.1145/3719003` (unconfirmed). **Verify exact title / authors
    / DOI** before relying on it, or remove.

12. **Cortez et al., "Resource Central", SOSP 2017 (P1915 / in‑text P0524).** Real, well‑known paper but absent
    from the curated `references.bib`; the "2M VMs / CPU < 20%" figures rest on documentation only. **Confirm
    the entry is acceptable as listed.**

13. **Orphan Kaggle datasets (P0565 zoya77; P0575 programmer3).** Inline attributions softened to "from
    Kaggle" because no reference entries exist. **Either add reference entries (and the matching Table 4.2
    attributions) or keep the softened wording.**

14. **Flexera "30–35% wasted" (P0432/P0526).** Now rests on Flexera alone (Gartner half removed). **Confirm the
    2024 Flexera State of the Cloud Report supports that range.**

15. **Reference‑list formatting (C9, structural — not risked here).** P1919 (Gartner) is styled differently
    from its siblings; P1924 (Streamlit) is missing the trailing space segment that sibling hyperlink
    references have. **Normalise in the master copy** (would require adding/altering runs; left untouched to
    avoid a formatting break).

## D — Lower‑priority reconciliations

16. **Table 4.3 resource itemization (A11).** The per‑category counts sum to **41** but the canonical
    `n_resources = 42`. No explicit total is printed. **Not edited** (would require fabricating a count) —
    reconcile the itemized rows against the actual inventory, or add a stated total of 42.

17. **Table 3.4 methodology figures.** "**$570+** savings identified" (compute right‑sizing) is consistent with
    the canonical compute‑savings figure ($571.23); "**13 additional recommendations**" (heuristics) does not
    cleanly map to the canonical split (19 total = 2 MILP + 17 rule/pricing). **Not changed** (out of the
    correction scope, approximate design‑overview wording) — verify or adjust.

18. **Structural row‑add to Table 4.8 (acknowledgement).** Adding the 3 omitted test suites
    (`test_aws_config.py`, `test_components.py`, `test_transforms.py`) required **adding 3 table rows** —
    one operation beyond the brief's explicitly‑enumerated structural list, done losslessly (cloned an
    existing row) to satisfy A5 ("add the omitted files"). Confirm this is acceptable; if not, the rows can be
    removed and the omission flagged instead.

19. **STS retry/timeout (P0714).** `MAX_RETRIES=3` / `API_TIMEOUT=30` exist in `config.py` but are surfaced
    only in the Settings UI; they are **not** wired into the boto3 client retry/timeout config. The prose was
    tightened (STS 1 h is the AWS default; `DurationSeconds` not set). Confirm whether to mention the
    constants at all.

20. **Section heading "4.3.2 Anomaly Detection Dataset — NAB CloudWatch" (P1073).** Left as‑is — NAB is a
    legitimate *reference dataset* the project used; only the false "validated against NAB with 100% recall"
    *claims* were removed. No action needed unless you prefer to rename the heading.

---

### Confirmed decisions (no action needed)
- **Title convention (G):** formal "AWS Cost Intelligence System" + product "OptiCloud" kept consistently;
  the code's "Smart Cloud Optimizer" was **not** introduced.
- **Citation style:** the thesis's informal author–year style was kept (not converted to numbered IEEE).
- **GWA / Grid Workloads Archive:** abbreviation (D4) and reference P1925 now agree.
- **PBKDF2‑HMAC‑SHA256, horizon dropdown, no‑Generate‑button:** already corrected in Round 1; left as‑is.
