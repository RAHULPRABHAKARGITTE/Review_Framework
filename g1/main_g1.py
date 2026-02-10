import os
import pandas as pd

from g1.g1_logic import check_g1
from g1.g1_3_logic import compare
from g1.g1_4_logic import run_g1_4
from io_utils import G1IOUtils
from g1.excel_utils import format_excel_sheet
from g1.docx_extractor import run_docx_extractor

# G1.3 imports
from config import CommonConfig, G1Config
#from g1_3_logic import compare


OUTPUT_FILE = os.path.join(CommonConfig.BASE_OUTPUT, "G1_Compliance.xlsx")

def generate_g1_summary():
    print("🚀 Generating G1_3_4 Summary")

    g13_path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_3_OUTPUT)
    g14_path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_4_OUTPUT)
    out_path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_3_4_SUMMARY_OUTPUT)

    # -------------------------------
    # Load G1.3 outputs
    # -------------------------------
    g13_msg = pd.read_excel(g13_path, sheet_name="Message_Definition_Comparison")
    g13_rx  = pd.read_excel(g13_path, sheet_name="Rx_Rate_Comparison")

    # -------------------------------
    # Load G1.4 output
    # -------------------------------
    g14 = pd.read_excel(g14_path)

    summary_rows = []

    # G1.3 – Message Definition
    for _, row in g13_msg.iterrows():
        summary_rows.append({
            "HLR ID": "SCU_STC_SRS_135",
            "Label": row.get("Label", ""),
            "Intent Similarity": "",
            "G1_3_Status": row.get("Status", ""),
            "G1_4_Overall Status": "",
            "Reason": row.get("Reason", "")
        })

    # G1.3 – Rx Rate
    for _, row in g13_rx.iterrows():
        summary_rows.append({
            "HLR ID": "SCU_STC_SRS_137",
            "Label": row.get("Label", ""),
            "Intent Similarity": "",
            "G1_3_Status": row.get("Status", ""),
            "G1_4_Overall Status": "",
            "Reason": row.get("Reason", "")
        })

    # G1.4 – Requirement Review
    for _, row in g14.iterrows():
        summary_rows.append({
            "HLR ID": row.get("HLR ID", ""),
            "Label": "",
            "Intent Similarity": row.get("Intent Similarity", ""),
            "G1_3_Status": "",
            "G1_4_Overall Status": row.get("Overall Status", ""),
            "Reason": ""
        })

    summary_df = pd.DataFrame(summary_rows)

    # ensure output dir exists
    os.makedirs(CommonConfig.BASE_OUTPUT, exist_ok=True)

    # Avoid permission error
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except PermissionError:
            raise RuntimeError(f"❌ Please close '{out_path}' and rerun.")

    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        summary_df.to_excel(w, sheet_name="G1_3_4_Summary", index=False)
        format_excel_sheet(w, "G1_3_4_Summary")

    print("✅ G1_3_4 Summary generated")
    print("📄 Output:", out_path)



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
        format_excel_sheet(writer, "System_Requirements", zebra=True)

        df_hlr.to_excel(writer, sheet_name="Software_Requirements", index=False)
        format_excel_sheet(writer, "Software_Requirements", zebra=True)

        df_trace.to_excel(writer, sheet_name="Traceability", index=False)
        format_excel_sheet(writer, "Traceability", zebra=True)

        df_g1.to_excel(writer, sheet_name="G1_Results", index=False)
        # Colorize by result/refinement for this sheet
        format_excel_sheet(
            writer,
            "G1_Results",
            result_col_candidates=("G1_RESULT", "G1_1_RESULT", "OVERALL", "RESULT"),
            refinement_col_candidates=("REFINEMENT", "REFINEMENT_FLAG"),
            zebra=True,
        )

    print(f"✅ G1.1/G1.2 output generated: {OUTPUT_FILE}")

    # ============================================================
    # PART 2: G1.3 (Niri version)
    # ============================================================
    print("🚀 Starting G1.3 ARINC Review")
    msg_cmp, rx_cmp = compare()
    g13_path = os.path.join(CommonConfig.BASE_OUTPUT, G1Config.G1_3_OUTPUT)

    if os.path.exists(g13_path):
        try:
            os.remove(g13_path)
        except PermissionError:
            raise RuntimeError(f"❌ Please close '{g13_path}' and rerun.")

    with pd.ExcelWriter(g13_path, engine="openpyxl") as w:
        pd.DataFrame(msg_cmp).to_excel(
            w, sheet_name="Message_Definition_Comparison", index=False
        )
        format_excel_sheet(w, "Message_Definition_Comparison")

        pd.DataFrame(rx_cmp).to_excel(
            w, sheet_name="Rx_Rate_Comparison", index=False
        )
        format_excel_sheet(w, "Rx_Rate_Comparison")

    print("✅ G1.3 completed")
    print("📄 Output:", g13_path)

    # ============================================================
    # PART 3: G1.4 (Niri version)
    # ============================================================
    print("🚀 Starting G1.4 Requirement Review")
    run_g1_4()
    print("✅ G1.4 completed")
    print("📄 Output:", G1Config.G1_4_OUTPUT)

    generate_g1_summary()


if __name__ == "__main__":
    run_g1()