import os
import re
import pandas as pd
from docx import Document
from io_utils import G2_IOUtils

from config import G2Config

def check_g2_6_and_generate_excel(docx_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    # ---- Read SRS via your existing utility ----
    requirements = G2_IOUtils.read_srs_requirements(docx_path)

    # ---- Normalize to a map {ID: Text} so the loop is safe ----
    req_map = {}

    # Case 1: dict {ID: Text}
    if isinstance(requirements, dict):
        # Already the right shape
        req_map = {str(k).strip(): ("" if v is None else str(v)) for k, v in requirements.items()}

    else:
        # Try DataFrame
        try:
            if isinstance(requirements, pd.DataFrame):
                cols = {c.lower(): c for c in requirements.columns}
                id_col = cols.get("id")
                txt_col = cols.get("desc") or cols.get("text")
                if id_col and txt_col:
                    for _, row in requirements.iterrows():
                        rid = str(row[id_col]).strip()
                        txt = "" if pd.isna(row[txt_col]) else str(row[txt_col])
                        if rid:
                            req_map[rid] = txt
                else:
                    # Not the expected columns; fall through to list handling
                    pass
            else:
                # Try list of dicts or list of tuples
                if isinstance(requirements, (list, tuple)):
                    for item in requirements:
                        if isinstance(item, dict):
                            rid = str(item.get("Requirement_ID", item.get("ID", ""))).strip()
                            txt = item.get("Requirement_Text", item.get("Text", item.get("DESC", "")))
                            txt = "" if txt is None else str(txt)
                            if rid:
                                req_map[rid] = txt
                        elif isinstance(item, (list, tuple)) and len(item) >= 2:
                            rid = str(item[0]).strip()
                            txt = "" if item[1] is None else str(item[1])
                            if rid:
                                req_map[rid] = txt
                # else: leave empty and error below if still empty
        except Exception:
            # If normalization attempt fails, leave to the check below
            pass

    if not req_map:
        raise TypeError(
            "G2.6: Unsupported SRS shape. Expected dict {ID: Text}, DataFrame(ID+DESC/TEXT), "
            "or list of {'Requirement_ID','Requirement_Text'} / (ID, Text)."
        )

    findings = []

    # ---- Run G2.6 check on normalized requirements ----
    for req_id, text in req_map.items():
        if not text:
            continue
        text_lower = text.lower()

        # Mandatory requirement?
        if not any(k in text_lower for k in G2Config.G2_6_MANDATORY_KEYWORDS):
            continue

        for term in G2Config.G2_6_AMBIGUOUS_TERMS:
            if term in text_lower:
                findings.append({
                    "Requirement_ID": req_id,
                    "Issue": (
                        f"Mandatory requirement uses ambiguous timing term "
                        f"'{term}', which is not objectively verifiable."
                    ),
                    "G_Objective": "DO-178C G2.6"
                })

    df = pd.DataFrame(findings)

    output_path = os.path.join(output_folder, "G2_6_Findings.xlsx")
    df.to_excel(output_path, index=False)

    return output_path, df
