# Reference and Citation Hygiene Check

Date: 2026-07-09. Scope: `paper/conference_draft.tex` against `paper/references.bib`.
Method: automated key extraction, DOI resolution via the doi.org handle API
(`https://doi.org/api/handles/<doi>`), and title cross-check against Crossref
(`https://api.crossref.org/works/<doi>`). No DOI values were added or edited.

## 1. Cite-key coverage

23 unique `\cite` keys are used in `conference_draft.tex`. All 23 exist in
`references.bib`. No undefined keys.

## 2. DOI resolution (handle API, responseCode 1 = resolves)

All 23 cited entries carry a DOI, and all 23 DOIs resolve:

| Key | DOI | Status |
| --- | --- | --- |
| agullo2025forecasting | 10.1016/j.future.2025.107833 | resolves |
| alves2025iaas | 10.1109/CloudCom67567.2025.11331429 | resolves |
| arrow1951inventory | 10.2307/1906813 | resolves |
| aydin2020binpacking | 10.1016/j.cor.2020.104959 | resolves |
| ban2019newsvendor | 10.1287/opre.2018.1757 | resolves |
| bulbul2021provisioning | 10.1016/j.ejor.2020.06.027 | resolves |
| cahoon2022doppler | 10.14778/3554821.3554840 | resolves |
| chaisiri2012provisioning | 10.1109/TSC.2011.7 | resolves |
| chen2024capacity | 10.1177/10591478241251614 | resolves |
| cortez2017resource | 10.1145/3132747.3132772 | resolves |
| diebold1995comparing | 10.1080/07350015.1995.10524599 | resolves |
| harvey1997testing | 10.1016/S0169-2070(96)00719-4 | resolves |
| hyndman2006mase | 10.1016/j.ijforecast.2006.03.001 | resolves |
| hyndman2008forecast | 10.18637/jss.v027.i03 | resolves |
| iosup2008gwa | 10.1016/j.future.2008.02.003 | resolves |
| kirchoff2024provisioning | 10.1007/s11227-024-06303-6 | resolves |
| musa2024costeffective | 10.1109/CloudCom62794.2024.00036 | resolves |
| rzadca2020autopilot | 10.1145/3342195.3387524 | resolves |
| shen2015bitbrains | 10.1109/CCGrid.2015.60 | resolves |
| taylor2018prophet | 10.1080/00031305.2017.1380080 | resolves |
| wang2014dynamic | 10.1109/TPDS.2014.2326409 | resolves |
| wang2014optimal | 10.1109/TPDS.2014.2385697 | resolves |
| yadwadkar2017paris | 10.1145/3127479.3131614 | resolves |

## 3. Title cross-check against Crossref

19/23 titles match Crossref directly (similarity > 0.85). The remaining four
are Crossref title/subtitle splits, not errors — the bib entries correctly
concatenate title and subtitle:

- `cahoon2022doppler`: Crossref "Doppler" + subtitle "automated SKU
  recommendation in migrating SQL workloads to the cloud".
- `cortez2017resource`: Crossref "Resource Central" + subtitle "Understanding
  and Predicting Workloads ...".
- `rzadca2020autopilot`: Crossref "Autopilot" + subtitle "workload autoscaling
  at Google".
- `yadwadkar2017paris`: Crossref title contains embedded HTML markup; text
  matches the bib entry.

No fabricated or miswired DOI was found.

## 4. IEEE metadata sufficiency

Every cited entry has author, title, venue (journal or booktitle), year, and
pages where applicable, plus a DOI. No cited entry relies on URL-only
identification.

## 5. Minor notes (no action strictly required)

- `wang2014optimal` and `wang2014dynamic`: the bib **keys** say 2014 but the
  publication year fields correctly say 2015 (IEEE TPDS). Keys are internal
  labels and never rendered in IEEE numeric style; cosmetic only.
- `chen2024capacity` carries a note referencing its SSRN working-paper
  version; harmless provenance.
- `references.bib` contains ~60 additional entries that are not cited by
  `conference_draft.tex`. BibTeX emits only cited entries, so they do not
  appear in the PDF. They are retained as the literature-sweep corpus (some
  are cited by the legacy `main.tex`).
- Publisher HTTP HEAD requests return 403 for SAGE/ACM (bot blocking); the
  handle-API check above is the authoritative existence test and passes for
  all entries.

## 6. Build verification

`./paper/build_conference.sh` completes with exit 0. The BibTeX log
(`conference_draft.blg`) and LaTeX log (`conference_draft.log`) contain no
undefined citations, no undefined references, and no missing-entry warnings
(see command outputs recorded on 2026-07-09).

## Unresolved issues

None. All cited references exist, resolve, and carry IEEE-sufficient metadata.
