# g1_4_logic.py

import os
import pandas as pd

from config import CommonConfig, G1Config
from io_utils import G1IOUtils
from g1.g1_logic import check_g1


OUTPUT_EXCEL = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_4_OUTPUT)


def run_g1_4():
    print("🧪 Running G1.4 Requirement Review (IOUtils-based)")

    # --------------------------------------------------
    # Load requirements using the same structured pipeline as G1.1/G1.2
    # --------------------------------------------------
    sys_doc = os.path.join(CommonConfig.BASE_INPUT, "System_Req.docx")
    sw_doc  = os.path.join(CommonConfig.BASE_INPUT, "Software_Req.docx")

    system_reqs = G1IOUtils.load_system_requirements(sys_doc)
    hlr_reqs    = G1IOUtils.load_software_requirements(sw_doc)

    if not system_reqs or not hlr_reqs:
        raise RuntimeError(
            f"❌ Empty extraction for G1.4. "
            f"System reqs={len(system_reqs)} HLR reqs={len(hlr_reqs)}"
        )

    # --------------------------------------------------
    # Run check_g1 for each HLR against system reqs
    # check_g1 signature: check_g1(system_reqs, hlr_reqs, trace_links)
    # BUT your G1.4 needs single-HLR mapping. We'll emulate with a temporary trace link.
    # --------------------------------------------------
    rows = []

    # build a synthetic trace link per HLR using best match function inside g1_logic
    # We will reuse internal helper _g1_check_single_hlr_against_sys via check_g1 wrapper:
    # easiest: create "trace_links" mapping each SYS to each HLR? not possible.
    # Instead, implement mapping by calling the internal debug function indirectly is not exposed.
    # So: do simple similarity mapping using existing fields expected by g1_logic helpers.
    # We'll call _g1_check_single_hlr_against_sys by importing it if present.
    try:
        from g1.g1_logic import _g1_check_single_hlr_against_sys as _single
    except Exception:
        _single = None

    for r in hlr_reqs:
        hid = r.get("HLR_ID")
        htxt = r.get("TEXT_RAW") or r.get("TEXT") or ""

        if _single:
            out = _single(hid, htxt, system_reqs)
            mapped = out.get("BEST_SYS_ID", "")
            sim = out.get("SIMILARITY", "")
            term = out.get("TERM_STATUS", "")
            label = out.get("LABEL_STATUS", "")
            status = out.get("OVERALL", "")
        else:
            # fallback: no mapping
            mapped, label, term, sim, status = "", "N/A", "N/A", "", G1Config.REVIEW

        rows.append([hid, mapped, label, term, sim, status])

    df = pd.DataFrame(rows, columns=[
        "HLR ID",
        "Mapped System Req",
        "Label Match",
        "Terminology",
        "Intent Similarity",
        "Overall Status"
    ])

    os.makedirs(CommonConfig.BASE_OUTPUT, exist_ok=True)

    if os.path.exists(OUTPUT_EXCEL):
        try:
            os.remove(OUTPUT_EXCEL)
        except PermissionError:
            raise RuntimeError(f"❌ Please close '{OUTPUT_EXCEL}' in Excel and rerun.")

    from g1.excel_utils import format_excel_sheet  # add at top

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="G1_4_Requirement_Review", index=False)
        format_excel_sheet(w, "G1_4_Requirement_Review")

    print("✅ G1.4 Review completed")
    print("📄 Output:", OUTPUT_EXCEL)
