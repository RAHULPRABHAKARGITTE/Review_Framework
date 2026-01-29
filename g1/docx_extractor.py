"""
docx_extractor.py

FINAL – ARINC-SAFE & TOOL-COMPATIBLE VERSION

Outputs:
1. System_Req.docx
2. Software_Req.docx
3. Traceability_SRS_TO_SYS.docx   (FLAT, FROM_TEXT preserved incl. tables)
4. Traceability_SYS_TO_SRS.docx   (FLAT, FROM_TEXT preserved incl. tables)

Fully aligned with trial_1_traceability.py
"""

import re
from docx import Document

# -------------------------------------------------
# ID PATTERNS (MUST MATCH trial_1_traceability)
# -------------------------------------------------
SYS_ID_RE = re.compile(r"SCU_SYS_\d+", re.IGNORECASE)
SRS_ID_RE = re.compile(r"SCU_STC_SRS_\d+", re.IGNORECASE)


# ============================================================
# REQUIREMENT EXTRACTION
# Output:
# | ID | DESC |
# ============================================================
def extract_requirements(input_docx, output_docx, id_regex, id_col, text_col):
    src = Document(input_docx)
    out = Document()

    table = out.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = id_col
    table.rows[0].cells[1].text = text_col

    for tbl in src.tables:
        for row in tbl.rows:
            row_text = " ".join(cell.text for cell in row.cells)
            match = id_regex.search(row_text)
            if not match:
                continue

            req_id = match.group()
            out_row = table.add_row()
            out_row.cells[0].text = req_id
            req_cell = out_row.cells[1]

            for cell in row.cells:
                if req_id in cell.text:
                    continue

                # Copy paragraphs
                for p in cell.paragraphs:
                    if p.text.strip():
                        req_cell.add_paragraph(p.text.strip())

                # Copy nested tables (ARINC, etc.)
                for nested in cell.tables:
                    nt = req_cell.add_table(
                        rows=len(nested.rows),
                        cols=len(nested.columns)
                    )
                    nt.style = "Table Grid"
                    for r, nrow in enumerate(nested.rows):
                        for c, ncell in enumerate(nrow.cells):
                            nt.rows[r].cells[c].text = ncell.text.strip()

    out.save(output_docx)
    print(f"[OK] Generated {output_docx}")


# ============================================================
# LOAD REQUIREMENT CELL MAP
# ID → ORIGINAL CELL (paragraphs + tables)
# ============================================================
def load_req_cell_map(req_docx):
    doc = Document(req_docx)
    req_map = {}

    for tbl in doc.tables:
        for row in tbl.rows:
            if len(row.cells) < 2:
                continue
            rid = row.cells[0].text.strip()
            if rid and rid not in req_map:
                req_map[rid] = row.cells[1]   # store CELL, not text
    return req_map


# ============================================================
# COPY CELL CONTENT (PARAGRAPHS + TABLES)
# ============================================================
def copy_cell_content(src_cell, dst_cell):
    # Copy paragraphs
    for p in src_cell.paragraphs:
        if p.text.strip():
            dst_cell.add_paragraph(p.text)

    # Copy nested tables (ARINC tables preserved)
    for tbl in src_cell.tables:
        nt = dst_cell.add_table(
            rows=len(tbl.rows),
            cols=len(tbl.columns)
        )
        nt.style = "Table Grid"
        for r, row in enumerate(tbl.rows):
            for c, cell in enumerate(row.cells):
                nt.rows[r].cells[c].text = cell.text


# ============================================================
# TRACEABILITY EXTRACTION (FLAT + ARINC-SAFE FROM_TEXT)
# Output:
# | FROM_ID | FROM_TEXT | TO_ID |
# ============================================================
def extract_traceability_flat(
    input_docx,
    output_docx,
    from_type,
    srs_cell_map,
    sys_cell_map
):
    """
    from_type:
        "SRS" → FROM_ID = SRS, TO_ID = SYS
        "SYS" → FROM_ID = SYS, TO_ID = SRS
    """
    src = Document(input_docx)
    out = Document()

    table = out.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "FROM_ID"
    table.rows[0].cells[1].text = "FROM_TEXT"
    table.rows[0].cells[2].text = "TO_ID"

    seen = set()

    for tbl in src.tables:
        for row in tbl.rows:

            # ---- SKIP HEADER ROWS ----
            first_cell = row.cells[0].text.strip().upper()
            if first_cell in {"FROM_ID", "SRS_ID", "SYS_ID", "REQ_ID"}:
                continue

            # text = " ".join(cell.text for cell in row.cells)


            # sys_ids = SYS_ID_RE.findall(text)
            # srs_ids = SRS_ID_RE.findall(text)

            from_cell = row.cells[0].text.strip()
            to_cell   = row.cells[2].text.strip()

            sys_ids = SYS_ID_RE.findall(from_cell + " " + to_cell)
            srs_ids = SRS_ID_RE.findall(from_cell + " " + to_cell)

            # -------------------------------
            # SRS → SYS
            # -------------------------------
            if from_type == "SRS":
                for srs in srs_ids:
                    for sys in sys_ids:
                        key = (srs, sys)
                        if key in seen:
                            continue
                        seen.add(key)

                        r = table.add_row()
                        r.cells[0].text = srs
                        src_cell = srs_cell_map.get(srs)
                        if src_cell:
                            copy_cell_content(src_cell, r.cells[1])
                        r.cells[2].text = sys

            # -------------------------------
            # SYS → SRS
            # -------------------------------
            elif from_type == "SYS":
                for sys in sys_ids:
                    for srs in srs_ids:
                        key = (sys, srs)
                        if key in seen:
                            continue
                        seen.add(key)

                        r = table.add_row()
                        r.cells[0].text = sys
                        src_cell = sys_cell_map.get(sys)
                        if src_cell:
                            copy_cell_content(src_cell, r.cells[1])
                        r.cells[2].text = srs

    out.save(output_docx)
    print(f"[OK] Generated {output_docx} ({from_type} traceability)")

import os

def run_docx_extractor():
    print("Running DOCX extraction (FINAL ARINC-SAFE MODE)...")

    in_dir = "inputs"
    out_dir = "inputs"   # or "outputs" if you want generated docs there

    ses = os.path.join(in_dir, "SCU_SES_g1.docx")
    srs = os.path.join(in_dir, "SCU_SRS_g1.docx")
    trace = os.path.join(in_dir, "SCU_Traceability.docx")

    sys_out = os.path.join(in_dir, "System_Req.docx")
    sw_out = os.path.join(in_dir, "Software_Req.docx")

    trace_srs_to_sys = os.path.join(in_dir, "Traceability_SRS_TO_SYS.docx")
    trace_sys_to_srs = os.path.join(in_dir, "Traceability_SYS_TO_SRS.docx")

    # 1️⃣ Extract requirements
    extract_requirements(
        ses,
        sys_out,
        SYS_ID_RE,
        "ID",
        "DESC"
    )

    extract_requirements(
        srs,
        sw_out,
        SRS_ID_RE,
        "ID",
        "DESC"
    )

    # 2️⃣ Load cell maps
    srs_cell_map = load_req_cell_map(sw_out)
    sys_cell_map = load_req_cell_map(sys_out)

    # 3️⃣ Extract traceability
    extract_traceability_flat(
        trace,
        trace_srs_to_sys,
        from_type="SRS",
        srs_cell_map=srs_cell_map,
        sys_cell_map=sys_cell_map
    )

    extract_traceability_flat(
        trace,
        trace_sys_to_srs,
        from_type="SYS",
        srs_cell_map=srs_cell_map,
        sys_cell_map=sys_cell_map
    )

    print("✔ All outputs generated successfully.")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    run_docx_extractor()