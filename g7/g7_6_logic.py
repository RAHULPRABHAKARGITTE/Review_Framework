import re
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table
import pandas as pd

# -------------------------------
# CONFIGURATION
# -------------------------------
INPUT_DOC = r"C:/Ali/SCU_SRS.docx"
OUTPUT_EXCEL = r"C:/Ali/SRS_Error_Handling_Review.xlsx"

MANDATORY_MUST_INCLUDE_CLASSIFICATION = False
SKIP_ROWS_WITH_EMPTY_ID = True

# -------------------------------
# KEYWORDS
# -------------------------------
ERROR_RELATED_TERMS = [
    "error", "fault", "failure", "fail", "exception", "invalid",
    "timeout", "crc", "overflow", "underflow", "out of range"
]

KW_DETECTION = [
    "detect", "detection", "monitor", "check", "validate",
    "verify", "range check", "diagnostic", "health check"
]

KW_CLASSIFICATION = [
    "severity", "minor", "major", "critical", "catastrophic",
    "recoverable", "non-recoverable", "error code"
]

KW_REPORTING = [
    "log", "report", "flag", "alert", "indicate",
    "status", "notify", "event", "telemetry"
]

KW_RECOVERY = [
    "recover", "retry", "reset", "reinitialize",
    "safe state", "shutdown", "fallback", "degraded mode"
]

REQ_ID_PATTERNS = [
    r"\bREQ[-_ ]?\d+(\.\d+)*\b",
    r"\bSRS[-_ ]?\d+(\.\d+)*\b",
    r"\bSCU[-_ ]?SRS[-_ ]?\d+(\.\d+)*\b"
]

HEADER_HINTS = ["id", "requirement", "description", "text"]

# -------------------------------
# HELPERS
# -------------------------------
def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip())

def find_matched_keywords(text, keywords):
    return [kw for kw in keywords if kw in text]

def find_any(text, patterns):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

def iter_block_items(doc):
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)

def is_header_row(row):
    texts = [normalize(c.text).lower() for c in row.cells]
    return sum(h in " ".join(texts) for h in HEADER_HINTS) >= 2

def extract_req_id(cell_text, row_text):
    cid = normalize(cell_text)
    if cid and not re.fullmatch(r"\d+(\.\d+)*", cid):
        return cid
    for p in REQ_ID_PATTERNS:
        m = re.search(p, row_text, re.IGNORECASE)
        if m:
            return m.group(0)
    return cid

# -------------------------------
# REQUIREMENT EXTRACTION
# -------------------------------
def extract_requirements_from_tables(doc):
    results = []
    last_heading = ""

    for blk in iter_block_items(doc):
        if isinstance(blk, Paragraph):
            if blk.style and "Heading" in blk.style.name:
                last_heading = normalize(blk.text)

        elif isinstance(blk, Table):
            start = 1 if is_header_row(blk.rows[0]) else 0
            for row in blk.rows[start:]:
                if len(row.cells) < 2:
                    continue

                row_text = " ".join(normalize(c.text) for c in row.cells)
                req_id = extract_req_id(row.cells[0].text, row_text)

                if SKIP_ROWS_WITH_EMPTY_ID and not req_id:
                    continue

                req_text = normalize(" ".join(c.text for c in row.cells[1:]))

                if not req_text:
                    continue

                results.append({
                    "Req_ID": req_id,
                    "Source_Section": last_heading,
                    "Requirement_Text": req_text
                })

    return results

# -------------------------------
# EVALUATION LOGIC
# -------------------------------
def evaluate_requirement(req_text):
    t = req_text.lower()
    related = any(k in t for k in ERROR_RELATED_TERMS)

    det_matches  = find_matched_keywords(t, KW_DETECTION)
    rep_matches  = find_matched_keywords(t, KW_REPORTING)
    rec_matches  = find_matched_keywords(t, KW_RECOVERY)
    cls_matches  = find_matched_keywords(t, KW_CLASSIFICATION)


    timing_match = re.search(r"\bwithin\s*\d+\s*(ms|s|sec|second)\b", t)
    if timing_match:
        detm_matches.append(timing_match.group(0))

    traceable = find_any(req_text, REQ_ID_PATTERNS)

    fail_reasons = []

    if related:
        if not det_matches:
            fail_reasons.append(
                f"No detection keyword found (expected one of: {', '.join(KW_DETECTION)})"
            )
        if not rep_matches:
            fail_reasons.append(
                f"No reporting keyword found (expected one of: {', '.join(KW_REPORTING)})"
            )
        if not rec_matches:
            fail_reasons.append(
                f"No recovery keyword found (expected one of: {', '.join(KW_RECOVERY)})"
            )
        if MANDATORY_MUST_INCLUDE_CLASSIFICATION and not cls_matches:
            fail_reasons.append(
                f"No classification keyword found (expected one of: {', '.join(KW_CLASSIFICATION)})"
            )

    overall = "PASS"
    if related and fail_reasons:
        overall = "FAIL"

    return {
        "Related_to_ErrorHandling": "Yes" if related else "No",
        "Check_Error_Detection": "Yes" if det_matches else "No",
        "Check_Error_Classification": "Yes" if cls_matches else "No",
        "Check_Error_Reporting": "Yes" if rep_matches else "No",
        "Check_Recovery": "Yes" if rec_matches else "No",
        "Check_Traceability": "Yes" if traceable else "No",
        "Overall_DO178_ErrorHandling": overall,
        "Fail_Reason_Details": (
            " | ".join(fail_reasons)
            if fail_reasons else
            ("N/A (Not error-handling requirement)" if not related else "Meets all mandatory checks")
        )
    }

# -------------------------------
# MAIN
# -------------------------------
def main():
    doc = Document(INPUT_DOC)
    reqs = extract_requirements_from_tables(doc)

    rows = []
    for i, r in enumerate(reqs, 1):
        ev = evaluate_requirement(r["Requirement_Text"])
        rows.append({
            "Seq": i,
            "Req_ID": r["Req_ID"],
            "Source_Section": r["Source_Section"],
            **ev
        })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Consolidated_Review", index=False)

    print("✅ Error Handling Review generated:", OUTPUT_EXCEL)

if __name__ == "__main__":
    main()