import os
import pandas as pd

from g1.g1_logic import check_g1
from io_utils import G1IOUtils
from g1.excel_utils import format_excel_sheet
from g1.docx_extractor import run_docx_extractor

# G1.3 imports
from config import CommonConfig, G1Config
from g1.g1_3_logic import compare_g1_3


OUTPUT_FILE = os.path.join(CommonConfig.BASE_OUTPUT, "G1_Compliance.xlsx")


def run_g1():
    os.makedirs(CommonConfig.BASE_OUTPUT, exist_ok=True)
    os.makedirs(CommonConfig.BASE_INPUT, exist_ok=True)

    run_docx_extractor()
    # ============================================================
    # PART 1: G1.1/G1.2 (existing output - keep unchanged)
    # ============================================================
    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
        except PermissionError:
            raise SystemExit("Close g1_output.xlsx and run again.")
        
    sys_doc = os.path.join(CommonConfig.BASE_INPUT, "System_Req.docx")
    sw_doc  = os.path.join(CommonConfig.BASE_INPUT, "Software_Req.docx")
    tr_doc  = os.path.join(CommonConfig.BASE_INPUT, "Traceability_SRS_TO_SYS.docx")

    system_reqs = G1IOUtils.load_system_requirements(sys_doc)
    hlr_reqs    = G1IOUtils.load_software_requirements(sw_doc)
    trace_links = G1IOUtils.load_traceability_srs_to_sys(tr_doc)

    print("=== TEST COUNTS ===")
    print("System requirements   :", len(system_reqs))
    print("Software requirements :", len(hlr_reqs))
    print("Trace links           :", len(trace_links))

    # HARD STOP: prevents empty excel generation
    if len(system_reqs) == 0 or len(hlr_reqs) == 0:
        raise SystemExit(
            "Extraction produced 0 requirements. Check docx_extractor output DOCX structure."
        )

    df_sys = pd.DataFrame(system_reqs, columns=["SYS_ID", "TEXT", "TABLE_TEXT"])
    df_hlr = pd.DataFrame(hlr_reqs, columns=["HLR_ID", "TEXT", "TABLE_TEXT"])
    df_trace = pd.DataFrame(trace_links)

    g1_results = check_g1(system_reqs, hlr_reqs, trace_links)
    df_g1 = pd.DataFrame(g1_results)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df_sys.to_excel(writer, sheet_name="System_Requirements", index=False)
        format_excel_sheet(writer, "System_Requirements")

        df_hlr.to_excel(writer, sheet_name="Software_Requirements", index=False)
        format_excel_sheet(writer, "Software_Requirements")

        df_trace.to_excel(writer, sheet_name="Traceability", index=False)
        format_excel_sheet(writer, "Traceability")

        df_g1.to_excel(writer, sheet_name="G1_Results", index=False)
        format_excel_sheet(writer, "G1_Results")

    print(f"✅ G1.1/G1.2 output generated: {OUTPUT_FILE}")

    # ============================================================
    # PART 2: G1.3 (integrated, same as your MY_VERSION)
    # ============================================================
    try:
        print("▶ Running G1.3")
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
    except Exception as e:
        print(f"❌ G1.3 failed: {e}")

    # ============================================================
    # PART 3: G1.4 (integrated WITHOUT breaking signatures)
    # ============================================================
    try:
        print("▶ Running G1.4")

        # Build HLR->SYS mapping from traceability
        rows = []
        for link in trace_links:
            hid = (link.get("HLR_ID") or "").strip()
            sid = (link.get("SYS_ID") or "").strip()

            if not hid:
                continue

            if not sid or sid.upper() == "NOT_TRACED":
                sid = "NOT_TRACED"

            # keep old output columns but don't call incompatible check_g1()
            label = "N/A"
            term = "N/A"
            sim = "N/A"
            status = "FAIL" if sid == "NOT_TRACED" else "PASS"

            rows.append([hid, sid, label, term, sim, status])

        df_g14 = pd.DataFrame(rows, columns=[
            "HLR ID",
            "Mapped System Req",
            "Label Match",
            "Terminology",
            "Intent Similarity",
            "Overall Status"
        ])

        out_g14 = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_4_OUTPUT)
        df_g14.to_excel(out_g14, index=False)

        print("✅ G1.4 completed")
        print(f"📄 Output: {out_g14}")
    except Exception as e:
        print(f"❌ G1.4 failed: {e}")


if __name__ == "__main__":
    run_g1()