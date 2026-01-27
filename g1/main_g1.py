import os
import pandas as pd

from config import CommonConfig, G1Config
from io_utils import extract_docx_text, extract_requirements

# ✅ THIS IMPORT IS MISSING / WRONG
from g1.g1_3_logic import compare_g1_3
from g1.g1_logic import check_g1




def run_g1():
    print("▶ Running G1 review")

    # ---------- G1.3 ----------
    msg_cmp, rx_cmp = compare_g1_3()

    out_g13 = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_3_OUTPUT)
    with pd.ExcelWriter(out_g13, engine="openpyxl") as w:
        pd.DataFrame(msg_cmp).to_excel(
            excel_writer=w,
            sheet_name="Message_Definition_Comparison",
            index=False
        )
        pd.DataFrame(rx_cmp).to_excel(
            excel_writer=w,
            sheet_name="Rx_Rate_Comparison",
            index=False
        )

    print("✅ G1.3 completed")
    print(f"📄 Output: {out_g13}")

    # ---------- G1.4 ----------
    hlr_path = os.path.join(CommonConfig.BASE_INPUT, G1Config.HLR_DOCX)
    sys_path = os.path.join(CommonConfig.BASE_INPUT, G1Config.SYS_DOCX)

    # ✅ PASS FILE PATHS — NOT TEXT
    hlr_reqs = extract_requirements(hlr_path)
    sys_reqs = extract_requirements(sys_path)

    rows = []

    for req in hlr_reqs:
        hid = req.get("id")
        htxt = req.get("text")

        if not hid or not htxt:
            continue

        mapped, label, term, sim, status = check_g1(hid, htxt, sys_reqs)
        rows.append([hid, mapped, label, term, sim, status])

    df = pd.DataFrame(rows, columns=[
        "HLR ID",
        "Mapped System Req",
        "Label Match",
        "Terminology",
        "Intent Similarity",
        "Overall Status"
    ])

    out_g14 = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_4_OUTPUT)
    df.to_excel(out_g14, index=False)

    print("✅ G1.4 completed")
    print(f"📄 Output: {out_g14}")
