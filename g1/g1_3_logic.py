# =========================================================
# G1.3 – ARINC SRS vs ICD COMPARISON LOGIC
# =========================================================

import os
import re
from docx import Document

from config import CommonConfig, G1Config
from io_utils import clean, norm


SRS_ID_RE = re.compile(r"SCU_STC_SRS_\d+")

def extract_label(text):
    """
    Extract ARINC octal label (<= 377)
    Examples:
      - Label 206
      - 206 (ADC)
    """
    if not text:
        return None

    import re
    matches = re.findall(r"\b([0-7]{1,3})\b", text)
    for m in matches:
        if 0 < int(m) <= 377:
            return m
    return None

# =========================================================
# STEP 1: GENERATE Software_req.docx FROM SRS
# =========================================================
def generate_software_req():
    """
    Generates Software_req.docx from SRS
    Output is written into framework output directory
    """

    srs_path = os.path.join(CommonConfig.BASE_INPUT, G1Config.SRS_DOCX)
    out_path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.SOFTWARE_REQ_DOCX)

    src = Document(srs_path)
    out = Document()

    table = out.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "ID"
    table.rows[0].cells[1].text = "DESC"

    for tbl in src.tables:
        for row in tbl.rows:
            row_text = " ".join(c.text for c in row.cells)
            m = SRS_ID_RE.search(row_text)
            if not m:
                continue

            rid = m.group()
            r = table.add_row()
            r.cells[0].text = rid
            dst = r.cells[1]

            for cell in row.cells:
                if rid in cell.text:
                    continue

                for p in cell.paragraphs:
                    if p.text.strip():
                        dst.add_paragraph(p.text.strip())

                for nt in cell.tables:
                    t = dst.add_table(rows=len(nt.rows), cols=len(nt.columns))
                    t.style = "Table Grid"
                    for i, rr in enumerate(nt.rows):
                        for j, cc in enumerate(rr.cells):
                            t.rows[i].cells[j].text = cc.text.strip()

    out.save(out_path)


# =========================================================
# STEP 2: EXTRACT ARINC FROM Software_req.docx (SRS)
# =========================================================
def extract_srs_arinc():
    path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.SOFTWARE_REQ_DOCX)
    doc = Document(path)

    rx, msg = [], []

    for tbl in doc.tables:
        for row in tbl.rows[1:]:
            cell = row.cells[1]
            label = extract_label(cell.text)

            for nt in cell.tables:
                headers = [norm(c.text) for c in nt.rows[0].cells]

                # ---------- RX RATE ----------
                if "receiver" in " ".join(headers):
                    for r in nt.rows[1:]:
                        c = [clean(x.text) for x in r.cells]
                        rx.append({
                            "Label": extract_label(c[1]) or label,
                            "Receiver": c[0],
                            "Interval": c[2]
                        })

                # ---------- MESSAGE DEFINITION ----------
                if "bit" in " ".join(headers):
                    for r in nt.rows[1:]:
                        c = [clean(x.text) for x in r.cells]
                        msg.append({
                            "Label": label,
                            "Bit": c[0],
                            "Field": c[1],
                            "Description": c[2],
                            "Definition": c[3]
                        })

    return rx, msg


# =========================================================
# STEP 3: EXTRACT ARINC FROM ICD DOCX
# =========================================================
def extract_icd_arinc():
    path = os.path.join(CommonConfig.BASE_INPUT, G1Config.ICD_DOCX)
    doc = Document(path)

    rx, msg = [], []
    current_label = None
    tables = list(doc.tables)
    ti = 0

    for p in doc.paragraphs:
        lbl = extract_label(p.text)
        if lbl:
            current_label = lbl

        if ti < len(tables) and tables[ti]._tbl.getprevious() == p._p:
            t = tables[ti]
            ti += 1
            headers = [norm(c.text) for c in t.rows[0].cells]

            # ---------- RX RATE ----------
            if "receiver" in " ".join(headers):
                for r in t.rows[1:]:
                    c = [clean(x.text) for x in r.cells]
                    rx.append({
                        "Label": extract_label(c[1]),
                        "Receiver": c[0],
                        "Interval": c[2]
                    })

            # ---------- MESSAGE DEFINITION ----------
            if "bit" in " ".join(headers):
                for r in t.rows[1:]:
                    c = [clean(x.text) for x in r.cells]
                    msg.append({
                        "Label": current_label,
                        "Bit": c[0],
                        "Field": c[1],
                        "Description": c[2],
                        "Definition": c[3]
                    })

    return rx, msg


# =========================================================
# STEP 4: FULL G1.3 FLOW
# =========================================================
def compare_g1_3():
    """
    Executes full G1.3 flow:
    - Generate Software_req.docx
    - Extract ARINC from SRS
    - Extract ARINC from ICD
    - Compare and return results
    """

    generate_software_req()

    srs_rx, srs_msg = extract_srs_arinc()
    icd_rx, icd_msg = extract_icd_arinc()

    msg_out, rx_out = [], []

    # ---------- MESSAGE DEFINITION COMPARISON ----------
    for s in srs_msg:
        match = next(
            (
                i for i in icd_msg
                if i["Label"] == s["Label"]
                and norm(i["Field"]) == norm(s["Field"])
            ),
            None
        )

        if not match:
            msg_out.append({
                **s,
                "Status": "Fail",
                "Reason": "Field not found in ICD"
            })
            continue

        sb1 = int(re.findall(r"\d+", s["Bit"])[0]) if s["Bit"] else None
        ib1 = int(re.findall(r"\d+", match["Bit"])[0]) if match["Bit"] else None

        fails = []
        if sb1 != (ib1 + 1 if ib1 is not None else None):
            fails.append("Bit offset mismatch (SRS = ICD + 1)")
        if norm(s["Description"]) != norm(match["Description"]):
            fails.append("Description mismatch")
        if norm(s["Definition"]) != norm(match["Definition"]):
            fails.append("Definition mismatch")

        msg_out.append({
            **s,
            "ICD Bit": match["Bit"],
            "Status": "Pass" if not fails else "Fail",
            "Reason": " | ".join(fails)
        })

    # ---------- RX RATE COMPARISON ----------
    for s in srs_rx:
        match = next(
            (
                i for i in icd_rx
                if i["Label"] == s["Label"]
                and norm(i["Receiver"]) == norm(s["Receiver"])
            ),
            None
        )

        if not match:
            rx_out.append({
                **s,
                "Status": "Fail",
                "Reason": "Receiver not found in ICD"
            })
            continue

        ok = norm(s["Interval"]) == norm(match["Interval"])
        rx_out.append({
            **s,
            "ICD Interval": match["Interval"],
            "Status": "Pass" if ok else "Fail",
            "Reason": "" if ok else "Transmission interval mismatch"
        })

    return msg_out, rx_out
