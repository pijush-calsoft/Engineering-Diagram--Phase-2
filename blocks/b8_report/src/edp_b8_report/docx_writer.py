"""Write a ``Report`` as DOCX (plan Phase 6 Insight task 1: "PDF or DOCX"; deck slide 40).

Sections follow the contract's template keys (summary, inputs, model, margins, envelope, flags,
assumptions). The document only lays out text the report already holds; it adds no numbers.
python-docx is MIT (plan §4.2 block 8 lists docxtpl / python-docx). PDF is not built yet.
"""

import io
from typing import Any

from docx import Document

from edp_contracts.artifacts.report import Report

TITLES = {
    "summary": "Summary",
    "inputs": "Inputs",
    "model": "Model",
    "margins": "Margins",
    "envelope": "Failure envelope",
    "flags": "Flags",
    "assumptions": "Assumptions and limits",
}


def to_docx(report: Report, meta: dict[str, Any]) -> bytes:
    doc = Document()
    doc.add_heading(f"Design insight report: {meta['part']} rev {meta['revision']}", level=0)
    status = doc.add_paragraph()
    status.add_run("DRAFT: not signed off. ").bold = True
    status.add_run("An engineer must review and sign this report before it is used.")
    table = doc.add_table(rows=0, cols=2)
    for label, value in (
        ("Run", report.run_id),
        ("Domain pack", meta["domain_pack"]),
        ("Materials file", meta["materials_sha256"][:16]),
        ("Load cases file", meta["load_cases_sha256"][:16]),
        ("Report schema", report.schema_version),
        (
            "Changed from the drawing",
            ", ".join(f"{k} {v:g} mm" for k, v in sorted((meta.get("overrides") or {}).items())) or "nothing",
        ),
    ):
        row = table.add_row().cells
        row[0].text, row[1].text = label, value
    for section in report.sections:
        doc.add_heading(TITLES[section.key], level=1)
        doc.add_paragraph(section.text)
    doc.add_heading("Figures and where they come from", level=1)
    claims = doc.add_table(rows=1, cols=4)
    head = claims.rows[0].cells
    head[0].text, head[1].text, head[2].text, head[3].text = "Claim", "Value", "Unit", "Run Store reference"
    for c in report.claims:
        cells = claims.add_row().cells
        cells[0].text, cells[1].text, cells[2].text, cells[3].text = (
            c.id,
            repr(c.value),
            c.unit or "",
            c.run_store_ref,
        )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
