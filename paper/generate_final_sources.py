#!/usr/bin/env python3
"""Generate named, venue-neutral final manuscript sources from working drafts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PAPER_DIR = Path(__file__).resolve().parent

CONFERENCE_TITLE = (
    "The Price of Conservatism in Cloud Optimization: Empirical Evidence from "
    "Right-Sizing and Reservation Heuristics"
)
JOURNAL_TITLE = (
    "The Price of Conservatism in Cloud Optimization: An Empirical Evaluation "
    "of Right-Sizing and Reservation Policies"
)
RUNNING_TITLE = "Conservatism in Cloud Right-Sizing"
AUTHORS = (
    ("Ibrahim Mohamed", "ibrahimmohamedabdelsadek@gmail.com"),
    ("Mariam Emad", "mariamemadcs@gmail.com"),
    ("Hazem Ibrahim", "Ihazem28@gmail.com"),
    ("Ahmed Sameh", "ahmed.sameh.12543@gmail.com"),
    ("Mahmoud Ahmed", "mahmoudkamel9102003@gmail.com"),
    ("John Ehab", "ehabjohn22@gmail.com"),
)
AUTHOR = AUTHORS[0][0]
EMAIL = AUTHORS[0][1]
AUTHOR_METADATA = "; ".join(name for name, _ in AUTHORS)
SUPPORT_LINE = (
    "Academic supervision and project support: Dr. Hafez Seliem, "
    "Mohamed Essam, and Saif AlDeen Sameh."
)

KEYWORDS = (
    "cloud cost optimization, right-sizing, capacity reservation, resource "
    "management, cloud pricing, workload traces, FinOps, empirical evaluation"
)

DATASET_PARAGRAPH = r"""
The study uses the GWA fastStorage, GWA Rnd, and GWA Materna traces; the
retained Azure aggregate artifact; synthetic account data; the documented AWS
price/catalog snapshot; and the derived evidence files recorded in the
repository. For the synthetic-account arm, publicly available workload traces
and catalog artifacts were processed and organized into a unified synthetic
account-level environment with generated resource identifiers. The workloads
were assigned across a deliberately complex EC2/RDS-style infrastructure to
support controlled evaluation of the implemented optimization workflow. The
environment simulates selected structural characteristics of an AWS account
but is not a live production account and contains no customer or personal
data. The resulting account-level data are synthetic; they are not output from
AWS, Azure, or another commercial recommender.
""".strip()

PROHIBITED_FINAL_TEXT = (
    "Anonymous Author",
    "Anonymous Authors",
    "Anonymous for Review",
    "TO BE COMPLETED",
    "TO BE CONFIRMED",
    "TO BE CONTINUED",
    "TBD",
    "TBC",
    "placeholder",
    "insert affiliation",
    "insert repository",
    "corresponding author required",
    "target journal",
    "target conference",
    "draft version",
    "continued",
    "completed later",
    "confirmed later",
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    return text.replace(old, new, 1)


def replace_span(
    text: str, start_marker: str, end_marker: str, replacement: str, label: str
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{label}: start anchor not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{label}: end anchor not found")
    return text[:start] + replacement + text[end:]


def validate_final_source(
    text: str, *, title: str, old_title: str, manuscript: str
) -> None:
    normalized_text = re.sub(r"\s+", " ", text)
    required = (
        title,
        *(value for author in AUTHORS for value in author),
        "Department of Computer Systems",
        "Faculty of Computer Science",
        "Ain Shams University",
        "Cairo, Egypt",
        "Dr. Hafez Seliem",
        "Mohamed Essam",
        "Saif AlDeen Sameh",
        "generated resource identifiers",
        "not a live production account",
        "no customer or personal data",
    )
    for value in required:
        if value not in normalized_text:
            raise RuntimeError(f"{manuscript}: required text missing: {value}")

    if old_title in text:
        raise RuntimeError(f"{manuscript}: old title remains in generated source")

    for value in PROHIBITED_FINAL_TEXT:
        if re.search(re.escape(value), text, flags=re.IGNORECASE):
            raise RuntimeError(
                f"{manuscript}: prohibited final text remains: {value}"
            )


def generate_conference() -> Path:
    source = PAPER_DIR / "conference_draft.tex"
    destination = PAPER_DIR / "final" / "conference_final.tex"
    text = source.read_text(encoding="utf-8")

    text = (
        "% General-purpose named IEEE-style conference manuscript.\n"
        "% Generated from the maintained conference working source.\n"
        + text.lstrip()
    )

    front_matter = rf"""    \hypersetup{{
      pdftitle={{{CONFERENCE_TITLE}}},
      pdfauthor={{{AUTHOR_METADATA}}},
      pdfsubject={{Cloud cost optimization, right-sizing, and reservation heuristics}},
      pdfkeywords={{{KEYWORDS}}}
    }}

    \begin{{document}}

    \title{{{CONFERENCE_TITLE}}}

    \author{{
    \IEEEauthorblockN{{\small Ibrahim Mohamed, Mariam Emad, Hazem Ibrahim, Ahmed Sameh, Mahmoud Ahmed, John Ehab}}
    \IEEEauthorblockA{{
    \emph{{\footnotesize {SUPPORT_LINE}}}\\[2pt]
    \small All authors: Department of Computer Systems\\
    Faculty of Computer Science\\
    Ain Shams University\\
    Cairo, Egypt
    }}
    }}

"""
    text = replace_span(
        text,
        "    % Authorship switch.",
        "    \\maketitle",
        front_matter,
        "conference front matter",
    )

    old_keywords = r"""    \begin{IEEEkeywords}
    cloud cost optimization, capacity reservation, right-sizing, reserved
    instances, newsvendor, FinOps, time-series forecasting.
    \end{IEEEkeywords}"""
    new_keywords = r"""    \begin{IEEEkeywords}
    cloud cost optimization, right-sizing, capacity reservation, resource
    management, cloud pricing, workload traces, FinOps, empirical evaluation.
    \end{IEEEkeywords}"""
    text = replace_once(
        text, old_keywords, new_keywords, "conference keywords"
    )

    dataset_anchor = r"""Study I uses the committed synthetic AWS account. Study II uses public
Bitbrains and Materna traces~\cite{shen2015bitbrains,iosup2008gwa}, priced
against a verified AWS catalog snapshot. The Azure arm uses the Azure Public
Dataset V2 lineage associated with Resource Central~\cite{cortez2017resource}.
"""
    text = replace_once(
        text,
        dataset_anchor,
        dataset_anchor + "\n" + DATASET_PARAGRAPH + "\n",
        "conference dataset description",
    )
    # The Azure "not restored" wording is maintained directly in
    # conference_draft.tex, so no wording patches are needed here.
    text = re.sub(r"\\input\{([^}]+)\}", r"\\input{../\1}", text)
    text = replace_once(
        text,
        r"\graphicspath{{figures/}}",
        r"\graphicspath{{../figures/}}",
        "conference graphics path",
    )
    text = replace_once(
        text,
        r"\bibliography{references}",
        r"\bibliography{../references}",
        "conference bibliography path",
    )

    validate_final_source(
        text,
        title=CONFERENCE_TITLE,
        old_title=(
            "The Price of Conservatism: Empirical Evidence from Cloud "
            "Right-Sizing and Reservation Heuristics"
        ),
        manuscript="conference",
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination


def generate_journal() -> Path:
    source = PAPER_DIR / "journal" / "journal_draft.tex"
    destination = PAPER_DIR / "journal" / "final" / "journal_final.tex"
    text = source.read_text(encoding="utf-8")

    text = replace_span(
        text,
        "% Generic journal-format manuscript.",
        "\\documentclass[11pt]{article}",
        (
            "% General-purpose named original research article.\n"
            "% Generated from the maintained journal working source.\n"
        ),
        "journal source header",
    )
    text = replace_once(
        text, "\\usepackage{authblk}\n", "", "journal authblk removal"
    )

    front_matter = rf"""\title{{{JOURNAL_TITLE}}}
\hypersetup{{
  pdftitle={{{JOURNAL_TITLE}}},
  pdfauthor={{{AUTHOR_METADATA}}},
  pdfsubject={{Cloud cost optimization, right-sizing, and reservation policies}},
  pdfkeywords={{{KEYWORDS}}}
}}

\author{{
\small Ibrahim Mohamed, Mariam Emad, Hazem Ibrahim, Ahmed Sameh, Mahmoud Ahmed, John Ehab\\[3pt]
\footnotesize\emph{{{SUPPORT_LINE}}}\\[3pt]
\small All authors: Department of Computer Systems\\
\small Faculty of Computer Science\\
\small Ain Shams University\\
\small Cairo, Egypt
}}

"""
    text = replace_span(
        text,
        "% Authorship switch:",
        "\\date{}",
        front_matter,
        "journal front matter",
    )
    text = replace_once(
        text,
        "\\date{}\n",
        (
            "\\date{}\n"
            "\\pagestyle{myheadings}\n"
            f"\\markright{{{RUNNING_TITLE}}}\n"
        ),
        "journal running title",
    )

    text = replace_span(
        text,
        "\\noindent\\textbf{Keywords:}",
        "\\section{Introduction}",
        (
            "\\noindent\\textbf{Keywords:} cloud cost optimization; right-sizing; "
            "capacity\nreservation; resource management; cloud pricing; workload "
            "traces; FinOps;\nempirical evaluation.\n\n"
        ),
        "journal keywords",
    )

    dataset_anchor = r"""Table~\ref{tab:datasets} summarizes the evaluated inputs. Study I uses the
committed synthetic AWS account. Study II uses restored Bitbrains and Materna
GWA traces~\cite{shen2015bitbrains,iosup2008gwa}, priced against a
snapshot-dated AWS catalog. The Azure Public Dataset V2 arm is retained only
as a generated boundary condition because the raw \texttt{vmtable.csv.gz}
input was not restored in this workspace.
"""
    text = replace_once(
        text,
        dataset_anchor,
        dataset_anchor + "\n" + DATASET_PARAGRAPH + "\n",
        "journal dataset description",
    )
    text = replace_once(
        text,
        r"Azure Public Dataset V2 & \azVms{} filtered VMs from \azTotalRows{} rows, 2019 trace & recorded boundary case & \path{paper/results_azure.json}; raw checksum pending \\",
        r"Azure Public Dataset V2 & \azVms{} filtered VMs from \azTotalRows{} rows, 2019 trace & recorded boundary case & \path{paper/results_azure.json}; raw input not restored \\",
        "journal Azure table status",
    )
    text = replace_once(
        text,
        (
            "are recorded in \\texttt{paper/trace\\_provenance.md}; the Azure "
            "raw-input\nchecksum is unavailable until "
            "\\texttt{vmtable.csv.gz} is restored."
        ),
        (
            "are recorded in \\texttt{paper/trace\\_provenance.md}; the Azure "
            "raw-input\nchecksum is unavailable because "
            "\\texttt{vmtable.csv.gz} was not restored."
        ),
        "journal Azure checksum wording",
    )
    text = replace_once(
        text,
        (
            "raw-quantile-scan, and baseline-grid helper stages, and 4.51 "
            "seconds for the\nreal-trace policy simulation. These timings "
            "document the artifact run; they\nare not a hardware-normalized "
            "scalability benchmark, and a full\nprocess-memory and "
            "dependency-version inventory remains pending."
        ),
        (
            "raw-quantile-scan, and baseline-grid helper stages, and 4.51 "
            "seconds for the\nreal-trace policy simulation. These timings "
            "document the artifact run; they\nare not a hardware-normalized "
            "scalability benchmark; a full\nprocess-memory and "
            "dependency-version inventory was not recorded."
        ),
        "journal runtime inventory wording",
    )
    text = replace_once(
        text,
        (
            "\\texttt{paper/trace\\_provenance.md}; Azure raw parsing runtime "
            "is pending\nrestoration of \\texttt{vmtable.csv.gz}."
        ),
        (
            "\\texttt{paper/trace\\_provenance.md}; Azure raw parsing runtime "
            "was not\nrecorded because \\texttt{vmtable.csv.gz} was not restored."
        ),
        "journal Azure runtime wording",
    )
    text = replace_once(
        text,
        "\\begin{figure}[H]",
        "\\begin{figure}[t]",
        "journal policy-figure placement",
    )

    reproducibility_close = r"""The principal rerun path is documented, but dependency pinning and independent
clean-room verification are not part of the current artifact. Azure is not
reproducible in this workspace because the raw \texttt{vmtable.csv.gz} input
was not restored. The implementation, generated evidence, build scripts, and
reproducibility materials are maintained in the project repository and are
available from the corresponding author. No public archive DOI has been
assigned. The current artifact does not provide a dependency lock, a complete
environment and execution-hardware inventory, or final generated-file hashes.

"""
    text = replace_span(
        text,
        "The principal rerun path is documented, but dependency pinning",
        "\\section{Conclusion}",
        reproducibility_close,
        "journal reproducibility close",
    )

    declarations = r"""\section*{Declarations}

\textbf{Funding.} This research received no external funding.

\textbf{Ethics approval.} Not applicable. The study did not involve human
participants, personal data, interviews, surveys, medical information, or
identifiable customer data.

\textbf{Consent to participate.} Not applicable.

\textbf{Consent for publication.} Not applicable.

\textbf{Data availability.} The study uses publicly available workload traces,
pricing and catalog artifacts, and derived synthetic data. The public sources,
checksums, preprocessing procedures, and generated evidence are documented in
the accompanying artifact materials. The workloads were reorganized into a
unified synthetic EC2/RDS-style account environment with generated resource
identifiers. The raw Azure input associated with the retained prior aggregate
result was not restored and is identified as an artifact limitation.

\textbf{Code availability.} The implementation, generated evidence, build
scripts, and reproducibility materials are maintained in the project
repository and are available from the corresponding author.

\textbf{AI-assistance disclosure.} The corresponding author used generative
AI tools for organizing the synthetic infrastructure representation, assigning
processed workloads across EC2-style and RDS-style resources, software
organization, code review, and manuscript presentation. Reported numerical
results were produced by the documented repository workflows. The
corresponding author reviewed and verified the final code, experimental
outputs, numerical values, claims, citations, and manuscript text.

\textbf{Prior dissemination.} An earlier version of this work was prepared as
a university project report. The manuscript has not previously been submitted
to or published by a conference or journal.

\section*{Author Contact Information}
\noindent\textbf{Corresponding author:} Ibrahim Mohamed:
\href{mailto:ibrahimmohamedabdelsadek@gmail.com}{\nolinkurl{ibrahimmohamedabdelsadek@gmail.com}}.

\noindent\textbf{Author emails:} Mariam Emad:
\href{mailto:mariamemadcs@gmail.com}{\nolinkurl{mariamemadcs@gmail.com}}; Hazem Ibrahim:
\href{mailto:Ihazem28@gmail.com}{\nolinkurl{Ihazem28@gmail.com}}; Ahmed Sameh:
\href{mailto:ahmed.sameh.12543@gmail.com}{\nolinkurl{ahmed.sameh.12543@gmail.com}}; Mahmoud Ahmed:
\href{mailto:mahmoudkamel9102003@gmail.com}{\nolinkurl{mahmoudkamel9102003@gmail.com}}; John Ehab:
\href{mailto:ehabjohn22@gmail.com}{\nolinkurl{ehabjohn22@gmail.com}}.

"""
    text = replace_span(
        text,
        "\\section*{Declarations}",
        "\\bibliographystyle{plain}",
        declarations,
        "journal declarations",
    )

    text = re.sub(r"\\input\{\.\./([^}]+)\}", r"\\input{../../\1}", text)
    text = replace_once(
        text,
        r"\graphicspath{{../figures/}}",
        r"\graphicspath{{../../figures/}}",
        "journal graphics path",
    )
    text = replace_once(
        text,
        r"\bibliography{../references}",
        r"\bibliography{../../references}",
        "journal bibliography path",
    )

    validate_final_source(
        text,
        title=JOURNAL_TITLE,
        old_title=(
            "The Price of Conservatism: Empirical Evidence from Cloud "
            "Right-Sizing and Reservation Heuristics"
        ),
        manuscript="journal",
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the named final manuscript LaTeX sources."
    )
    parser.add_argument(
        "manuscript",
        nargs="?",
        choices=("all", "conference", "journal"),
        default="all",
    )
    args = parser.parse_args()

    generated: list[Path] = []
    if args.manuscript in ("all", "conference"):
        generated.append(generate_conference())
    if args.manuscript in ("all", "journal"):
        generated.append(generate_journal())

    for path in generated:
        print(f"Generated {path.relative_to(PAPER_DIR.parent)}")


if __name__ == "__main__":
    main()
