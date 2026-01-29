from openpyxl.styles import Alignment, PatternFill


def format_excel_sheet(writer, sheet_name):
    """
    Applies wrap text, top alignment, and reasonable column widths.
    """
    ws = writer.book[sheet_name]

    # Wrap text and align top
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(
                wrap_text=True,
                vertical="top"
            )

    # Set column widths based on content type
    for col in ws.columns:
        col_letter = col[0].column_letter
        header = str(col[0].value).upper()

        if "TEXT" in header:
            ws.column_dimensions[col_letter].width = 70
        elif "FUNCTIONALITY" in header:
            ws.column_dimensions[col_letter].width = 40
        elif "COMMENT" in header:
            ws.column_dimensions[col_letter].width = 60
        else:
            ws.column_dimensions[col_letter].width = 25

        # Let Excel auto-adjust row height
    for row_dim in ws.row_dimensions.values():
        row_dim.height = None