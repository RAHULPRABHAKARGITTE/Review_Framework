import os
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from config import CommonConfig, G5Config
from io_utils import extract_requirements
from g5.g5_logic import run_g5_checks


def run_g5():
    print("▶ Running G5 review")

    # ---------------- Paths ----------------
    input_path = os.path.join(
        CommonConfig.BASE_INPUT,
        G5Config.INPUT_SRS_FILE
    )

    output_path = os.path.join(
        CommonConfig.BASE_OUTPUT,
        G5Config.OUTPUT_REPORT_FILE
    )

    # ---------------- Load requirements ----------------
    requirements = extract_requirements(input_path)

    # ---------------- Run G5 checks ----------------
    g5_results, all_findings = run_g5_checks(requirements)

    # ---------------- Excel setup ----------------
    wb = Workbook()
    ws = wb.active
    ws.title = "G5 Review"

    # Title
    ws.merge_cells(
        start_row=1, start_column=1,
        end_row=1, end_column=len(G5Config.COLUMN_HEADERS)
    )
    ws["A1"] = G5Config.REPORT_TITLE
    ws["A1"].font = Font(bold=True)
    ws["A1"].alignment = Alignment(horizontal="center")

    # Headers
    ws.append(G5Config.COLUMN_HEADERS)
    for col in range(1, len(G5Config.COLUMN_HEADERS) + 1):
        ws.cell(row=2, column=col).font = Font(bold=True)
        ws.cell(row=2, column=col).alignment = Alignment(wrap_text=True)

    # ---------------- Group findings ----------------
    findings_by_req = defaultdict(list)
    for req_id, issue in all_findings:
        findings_by_req[req_id].append(issue)

    # ---------------- Populate rows ----------------
    row = 3
    for req_id in sorted(g5_results.keys()):
        issues = findings_by_req.get(req_id, [])

        status = {
            "5.1": "PASS",
            "5.2": "PASS",
            "5.3": "PASS",
            "5.4": "PASS",
            "5.5": "PASS",
        }

        for issue in issues:
            if "G_5.1" in issue:
                status["5.1"] = "FAIL"
            if "G_5.2" in issue:
                status["5.2"] = "FAIL"
            if "G_5.3" in issue:
                status["5.3"] = "FAIL"
            if "G_5.4" in issue:
                status["5.4"] = "FAIL"
            if "G_5.5" in issue:
                status["5.5"] = "FAIL"

        ws.append([
            req_id,
            status["5.1"],
            status["5.2"],
            status["5.3"],
            status["5.4"],
            status["5.5"],
            "\n".join(issues) if issues else "N/A"
        ])

        ws.cell(row=row, column=7).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
        row += 1

    # ---------------- Save ----------------
    os.makedirs(CommonConfig.BASE_OUTPUT, exist_ok=True)
    wb.save(output_path)

    print(f"✅ G5 review completed")
    print(f"📄 Output: {output_path}")
