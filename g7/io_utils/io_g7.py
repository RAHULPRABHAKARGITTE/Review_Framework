# io_utils.py
import os
import pandas as pd
from docx import Document
from openpyxl import load_workbook

def read_srs_doc(path: str):
    """
    Read the DOCX SRS and return a list of table rows (each row is a list of cell texts).
    """
    doc = Document(path)
    rows = []
    for t in doc.tables:
        for r in t.rows:
            rows.append([c.text.strip() for c in r.cells])
    return rows


def write_or_replace_sheet(excel_path: str, sheet_name: str, df: pd.DataFrame) -> None:
    """
    Writes df into excel_path in sheet_name.
    - If excel doesn't exist => create it.
    - If sheet exists => delete and recreate it.
    """
    if not os.path.exists(excel_path):
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return

    wb = load_workbook(excel_path)
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        wb.remove(ws)
        wb.save(excel_path)

    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)


def append_results(summary_df, details_df, excel_file: str, summary_sheet: str, details_sheet: str):
    """
    Append summary_df into summary_sheet and details_df into details_sheet in the excel file.
    If exists → append to end of each sheet without headers.
    """
    if not os.path.exists(excel_file):
        with pd.ExcelWriter(excel_file, mode="w", engine="xlsxwriter") as writer:
            summary_df.to_excel(writer, sheet_name=summary_sheet, index=False, header=True)
            details_df.to_excel(writer, sheet_name=details_sheet, index=False, header=True)
        print(f"Created {excel_file} with sheets '{summary_sheet}' and '{details_sheet}'")
        return

    book = load_workbook(excel_file)

    def _append_df(writer, sheet_name, df):
        if sheet_name in book.sheetnames:
            ws = book[sheet_name]
            startrow = ws.max_row  # append below last row
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False, startrow=startrow)
        else:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=True)

    with pd.ExcelWriter(excel_file, mode="a", engine="openpyxl") as writer:
        writer.book = book
        _append_df(writer, summary_sheet, summary_df)
        _append_df(writer, details_sheet, details_df)

    print(f"Results appended to {excel_file} → '{summary_sheet}' and '{details_sheet}'")

# -----------------------------
# Excel helper (required by g7_logic.py)
# -----------------------------
import os
import pandas as pd
from openpyxl import load_workbook

def write_or_replace_sheet(excel_path: str, sheet_name: str, df: pd.DataFrame) -> None:
    """
    Write df into excel_path in sheet_name.

    - If workbook does not exist => create new workbook.
    - If sheet exists => delete sheet and recreate (replace behavior).
    """
    if not os.path.exists(excel_path):
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return

    wb = load_workbook(excel_path)

    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        wb.remove(ws)
        wb.save(excel_path)

    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)