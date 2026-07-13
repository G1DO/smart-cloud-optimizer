#!/usr/bin/env python3
"""Build and validate editable DOCX versions of the final manuscripts."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


PAPER_DIR = Path(__file__).resolve().parent
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

CONFIG = {
    "conference": {
        "source": PAPER_DIR / "final" / "conference_final.tex",
        "output": PAPER_DIR / "final" / "conference_final.docx",
        "title": (
            "The Price of Conservatism in Cloud Optimization: Empirical "
            "Evidence from Right-Sizing and Reservation Heuristics"
        ),
        "subject": (
            "Cloud cost optimization, right-sizing, and reservation heuristics"
        ),
        "resource_dirs": (
            PAPER_DIR / "final",
            PAPER_DIR,
            PAPER_DIR / "figures",
        ),
    },
    "journal": {
        "source": PAPER_DIR / "journal" / "final" / "journal_final.tex",
        "output": PAPER_DIR / "journal" / "final" / "journal_final.docx",
        "title": (
            "The Price of Conservatism in Cloud Optimization: An Empirical "
            "Evaluation of Right-Sizing and Reservation Policies"
        ),
        "subject": (
            "Cloud cost optimization, right-sizing, and reservation policies"
        ),
        "resource_dirs": (
            PAPER_DIR / "journal" / "final",
            PAPER_DIR,
            PAPER_DIR / "figures",
        ),
    },
}

CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CUSTOM_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
)
VT_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
)

ET.register_namespace("cp", CP_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("", CUSTOM_NS)
ET.register_namespace("vt", VT_NS)
ET.register_namespace(
    "dcterms", "http://purl.org/dc/terms/"
)
ET.register_namespace(
    "dcmitype", "http://purl.org/dc/dcmitype/"
)
ET.register_namespace(
    "xsi", "http://www.w3.org/2001/XMLSchema-instance"
)


def replace_front_matter(text: str) -> str:
    start = text.find("\\title{")
    if start < 0:
        raise RuntimeError("DOCX conversion: manuscript title anchor not found")
    end_start = text.find("\\maketitle", start)
    if end_start < 0:
        raise RuntimeError("DOCX conversion: maketitle anchor not found")
    end = end_start + len("\\maketitle")

    author_block = rf"""\begin{{center}}
\textbf{{Ibrahim Mohamed, Mariam Emad, Hazem Ibrahim, Ahmed Sameh, Mahmoud Ahmed, John Ehab}}\\[3pt]
\emph{{\small {SUPPORT_LINE}}}\\[3pt]
All authors: Department of Computer Systems\\
Faculty of Computer Science\\
Ain Shams University\\
Cairo, Egypt
\end{{center}}"""
    removed_front_matter = text[start:end]
    if "\\begin{document}" in removed_front_matter:
        author_block = "\\begin{document}\n\n" + author_block
    return text[:start] + author_block + text[end:]


def normalize_for_pandoc(text: str, manuscript: str) -> str:
    text = replace_front_matter(text)
    text = text.replace("\\IEEEoverridecommandlockouts\n", "")

    abstract_start_marker = "\\begin{abstract}"
    abstract_end_marker = "\\end{abstract}"
    abstract_start = text.find(abstract_start_marker)
    abstract_end = text.find(abstract_end_marker, abstract_start)
    if abstract_start < 0 or abstract_end < 0:
        raise RuntimeError("DOCX conversion: abstract block not found")
    abstract_body_start = abstract_start + len(abstract_start_marker)
    abstract_body = text[abstract_body_start:abstract_end].strip()
    text = (
        text[:abstract_start]
        + "\\section*{Abstract}\n"
        + abstract_body
        + "\n"
        + text[abstract_end + len(abstract_end_marker) :]
    )

    if manuscript == "conference":
        start = text.find("\\begin{IEEEkeywords}")
        end_marker = "\\end{IEEEkeywords}"
        end_start = text.find(end_marker, start)
        if start < 0 or end_start < 0:
            raise RuntimeError(
                "DOCX conversion: conference keyword block not found"
            )
        keyword_block = (
            "\\noindent\\textbf{Keywords:} cloud cost optimization; "
            "right-sizing; capacity reservation; resource management; cloud "
            "pricing; workload traces; FinOps; empirical evaluation."
        )
        text = (
            text[:start]
            + keyword_block
            + text[end_start + len(end_marker) :]
        )

    text = re.sub(
        r"\\bibliographystyle\{[^}]+\}\s*\\bibliography\{[^}]+\}",
        "",
        text,
        count=1,
    )
    return text


def set_core_property(root: ET.Element, tag: str, value: str) -> None:
    element = root.find(tag)
    if element is None:
        element = ET.SubElement(root, tag)
    element.text = value


def find_support_run(document_markup: str, path_name: str) -> re.Match[str]:
    support_text = (
        '<w:t xml:space="preserve">'
        f"{re.escape(SUPPORT_LINE)}</w:t>"
    )
    pattern = re.compile(
        r"<w:r(?:\s[^>]*)?>(?:(?!</w:r>).)*?"
        + support_text
        + r"(?:(?!</w:r>).)*?</w:r>",
        flags=re.DOTALL,
    )
    matches = list(pattern.finditer(document_markup))
    if len(matches) != 1:
        raise RuntimeError(
            f"{path_name}: support-line run not found uniquely"
        )
    return matches[0]


def style_support_run(document_xml: bytes, path_name: str) -> bytes:
    document_markup = document_xml.decode("utf-8")
    match = find_support_run(document_markup, path_name)
    run = match.group(0)
    run = re.sub(r"<w:sz(?:Cs)?\b[^>]*/>", "", run)
    size_markup = '<w:sz w:val="18" /><w:szCs w:val="18" />'
    if "<w:rPr>" in run:
        run = run.replace("</w:rPr>", size_markup + "</w:rPr>", 1)
    else:
        run_open_end = run.index(">") + 1
        run = (
            run[:run_open_end]
            + "<w:rPr><w:i /><w:iCs />"
            + size_markup
            + "</w:rPr>"
            + run[run_open_end:]
        )
    document_markup = (
        document_markup[: match.start()]
        + run
        + document_markup[match.end() :]
    )
    return document_markup.encode("utf-8")


def update_docx_metadata(
    path: Path, *, title: str, subject: str
) -> None:
    replacement = path.with_name(f".{path.name}.metadata.tmp")
    with zipfile.ZipFile(path, "r") as source_zip:
        with zipfile.ZipFile(
            replacement, "w", compression=zipfile.ZIP_DEFLATED
        ) as output_zip:
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)
                if info.filename == "docProps/core.xml":
                    root = ET.fromstring(data)
                    set_core_property(root, f"{{{DC_NS}}}title", title)
                    set_core_property(
                        root, f"{{{DC_NS}}}creator", AUTHOR_METADATA
                    )
                    set_core_property(root, f"{{{DC_NS}}}subject", subject)
                    set_core_property(
                        root, f"{{{CP_NS}}}lastModifiedBy", AUTHOR_METADATA
                    )
                    set_core_property(
                        root, f"{{{CP_NS}}}keywords", KEYWORDS
                    )
                    data = ET.tostring(
                        root, encoding="utf-8", xml_declaration=True
                    )
                elif info.filename == "word/document.xml":
                    data = style_support_run(data, path.name)
                elif info.filename == "docProps/custom.xml":
                    root = ET.fromstring(data)
                    for property_element in list(root):
                        value = " ".join(property_element.itertext())
                        if (
                            "/home/" in value
                            or "file:///home/" in value
                            or property_element.get("name") == "bibliography"
                        ):
                            root.remove(property_element)
                    data = ET.tostring(
                        root, encoding="utf-8", xml_declaration=True
                    )
                output_zip.writestr(info, data)
    os.replace(replacement, path)


def extract_document_text(document_xml: bytes) -> str:
    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{{{W_NS}}}p"):
        paragraph_text = "".join(
            node.text or "" for node in paragraph.iter(f"{{{W_NS}}}t")
        )
        if paragraph_text:
            paragraphs.append(paragraph_text)
    return re.sub(r"\s+", " ", "\n".join(paragraphs)).strip()


def validate_docx(path: Path, *, title: str, subject: str) -> None:
    prohibited = (
        "Anonymous Author",
        "Anonymous Authors",
        "Anonymous for Review",
        "TO BE",
        "TBD",
        "TBC",
        "placeholder",
        "continued",
        "confirmed later",
        "completed later",
    )
    tracked_change_tags = (
        "<w:ins",
        "<w:del",
        "<w:moveFrom",
        "<w:moveTo",
        "<w:commentRangeStart",
        "<w:commentRangeEnd",
        "<w:commentReference",
    )

    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        required_parts = {"word/document.xml", "docProps/core.xml"}
        missing_parts = required_parts - names
        if missing_parts:
            raise RuntimeError(
                f"{path.name}: missing DOCX parts: {sorted(missing_parts)}"
            )

        nonempty_comment_parts = []
        for name in names:
            if name.startswith("word/comments") or name == "word/people.xml":
                if len(ET.fromstring(archive.read(name))):
                    nonempty_comment_parts.append(name)
        if nonempty_comment_parts:
            raise RuntimeError(
                f"{path.name}: comments remain: "
                f"{sorted(nonempty_comment_parts)}"
            )

        document_xml = archive.read("word/document.xml")
        document_text = extract_document_text(document_xml)
        required_text = (
            title,
            *(value for author in AUTHORS for value in author),
            "Department of Computer Systems",
            "Faculty of Computer Science",
            "Ain Shams University",
            "Cairo, Egypt",
            SUPPORT_LINE,
            "Abstract",
            "Introduction",
            "References",
        )
        for value in required_text:
            if value not in document_text:
                raise RuntimeError(
                    f"{path.name}: required document text missing: {value}"
                )

        document_markup = document_xml.decode("utf-8", errors="ignore")
        support_run = find_support_run(
            document_markup, path.name
        ).group(0)
        if (
            '<w:sz w:val="18" />' not in support_run
            or '<w:szCs w:val="18" />' not in support_run
        ):
            raise RuntimeError(
                f"{path.name}: support line is not styled at 9 pt"
            )

        searchable_xml = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".xml", ".rels"))
        )
        for value in prohibited:
            if re.search(re.escape(value), searchable_xml, flags=re.IGNORECASE):
                raise RuntimeError(
                    f"{path.name}: prohibited text remains: {value}"
                )
        for value in tracked_change_tags:
            if value in searchable_xml:
                raise RuntimeError(
                    f"{path.name}: tracked-change markup remains: {value}"
                )
        if "/home/ibrahim/" in searchable_xml or "file:///home/" in searchable_xml:
            raise RuntimeError(f"{path.name}: local filesystem path remains")

        core = ET.fromstring(archive.read("docProps/core.xml"))
        expected_core = {
            f"{{{DC_NS}}}title": title,
            f"{{{DC_NS}}}creator": AUTHOR_METADATA,
            f"{{{DC_NS}}}subject": subject,
            f"{{{CP_NS}}}lastModifiedBy": AUTHOR_METADATA,
            f"{{{CP_NS}}}keywords": KEYWORDS,
        }
        for tag, expected in expected_core.items():
            element = core.find(tag)
            actual = element.text if element is not None else None
            if actual != expected:
                raise RuntimeError(
                    f"{path.name}: metadata mismatch for {tag}: {actual!r}"
                )


def build_docx(manuscript: str) -> Path:
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError(
            "Pandoc is required for DOCX generation but was not found on PATH. "
            "Install Pandoc and rerun the final build."
        )

    config = CONFIG[manuscript]
    source = Path(config["source"])
    output = Path(config["output"])
    title = str(config["title"])
    subject = str(config["subject"])

    if not source.is_file():
        raise RuntimeError(
            f"Final LaTeX source not found: {source}. Generate it first."
        )

    normalized = normalize_for_pandoc(
        source.read_text(encoding="utf-8"), manuscript
    )
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tex",
            prefix=f".{manuscript}_docx_",
            dir=source.parent,
            delete=False,
        ) as temp_file:
            temp_file.write(normalized)
            temp_path = Path(temp_file.name)

        resource_path = os.pathsep.join(
            str(Path(path).resolve()) for path in config["resource_dirs"]
        )
        command = [
            pandoc,
            str(temp_path),
            "--from=latex",
            "--to=docx",
            "--standalone",
            "--number-sections",
            "--citeproc",
            f"--bibliography={PAPER_DIR / 'references.bib'}",
            f"--resource-path={resource_path}",
            "-M",
            f"title={title}",
            "-M",
            "reference-section-title=References",
            f"--output={output}",
        ]
        subprocess.run(command, check=True, cwd=source.parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    update_docx_metadata(output, title=title, subject=subject)
    validate_docx(output, title=title, subject=subject)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and validate a final editable DOCX manuscript."
    )
    parser.add_argument("manuscript", choices=tuple(CONFIG))
    args = parser.parse_args()

    output = build_docx(args.manuscript)
    print(f"Built and validated {output.relative_to(PAPER_DIR.parent)}")


if __name__ == "__main__":
    main()
