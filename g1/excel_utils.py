from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
from openpyxl.utils import get_column_letter

# -------------------- Color constants --------------------
FILL_HEADER = PatternFill("solid", fgColor="1F4E78")   # dark blue header
FONT_HEADER = Font(color="FFFFFF", bold=True)

FILL_PASS   = PatternFill("solid", fgColor="C6E0B4")   # light green
FILL_FAIL   = PatternFill("solid", fgColor="F8CBAD")   # light red
FILL_REVIEW = PatternFill("solid", fgColor="FFE699")   # light yellow

FILL_ODD    = PatternFill("solid", fgColor="F7F7F7")   # zebra (odd rows)
FILL_NONE   = PatternFill()                            # no fill


_GRID_COLOR = "808080"  


_THIN_GRID = Border(
    left=Side(style="thin", color=_GRID_COLOR),
    right=Side(style="thin", color=_GRID_COLOR),
    top=Side(style="thin", color=_GRID_COLOR),
    bottom=Side(style="thin", color=_GRID_COLOR),
)


BORDER_RED  = Border(left=Side(style="thin", color="C00000"),
                     right=Side(style="thin", color="C00000"),
                     top=Side(style="thin", color="C00000"),
                     bottom=Side(style="thin", color="C00000"))
BORDER_AMBER = Border(left=Side(style="thin", color="9C6500"),
                      right=Side(style="thin", color="9C6500"),
                      top=Side(style="thin", color="9C6500"),
                      bottom=Side(style="thin", color="9C6500"))

# Maps for quick lookups
RESULT_TO_FILL = {
    "PASS":   FILL_PASS,
    "FAIL":   FILL_FAIL,
    "REVIEW": FILL_REVIEW,
}
REFINE_RED = {"UNACCEPTABLE_DRIFT"}
REFINE_AMB = {"ACCEPTABLE_REFINEMENT", "ACCEPTABLE", "ACCEPTABLE_REF"}  # allow variants

_HEADER_BASELINE = Border(bottom=Side(style="thin", color=_GRID_COLOR))

def _style_header(ws):
    if ws.max_row < 1:
        return
    for cell in ws[1]:  # header row
        cell.border = _HEADER_BASELINE

def _apply_thin_grid_borders(ws, start_row=1, start_col=1):
    """
    Draw thin grey borders on every used cell so lines are visible.
    Does NOT overwrite cells that already have a custom border.
    """
    max_r = ws.max_row or 1
    max_c = ws.max_column or 1

    for r in range(start_row, max_r + 1):
        for c in range(start_col, max_c + 1):
            cell = ws.cell(row=r, column=c)
            b = cell.border

            # safely check if ANY side has style (avoid None.style)
            has_existing = (
                (b.left and b.left.style) or
                (b.right and b.right.style) or
                (b.top and b.top.style) or
                (b.bottom and b.bottom.style)
            )

            if not has_existing:
                cell.border = _THIN_GRID     # your defined thin border


def _header_and_widths(ws):
    """
    Headers: colored + bold; widths based on header text.
    Keeps your existing logic and adds header color/font.
    """
    if ws.max_row < 1:
        return

    # Style header row
    header_row = next(ws.iter_rows(min_row=1, max_row=1))
    for c in header_row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.fill = FILL_HEADER
        c.font = FONT_HEADER

    # Column widths (preserving your rules)
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        first_cell = next(iter(col_cells), None)
        header = (str(first_cell.value).upper() if first_cell and first_cell.value is not None else "")
        col_letter = get_column_letter(col_idx)
        if "TEXT" in header:
            ws.column_dimensions[col_letter].width = 70
        elif "FUNCTIONALITY" in header:
            ws.column_dimensions[col_letter].width = 40
        elif "COMMENT" in header:
            ws.column_dimensions[col_letter].width = 60
        else:
            ws.column_dimensions[col_letter].width = 25

    # Let Excel auto-adjust row height (as in your file)
    for row_dim in ws.row_dimensions.values():
        row_dim.height = None


def _find_col_index(ws, header_name_candidates):
    """
    Return 1-based index for the first header that matches any candidate
    (case-insensitive). Returns None if not found.
    """
    if ws.max_row < 1:
        return None
    headers = [ (cell.value or "").strip() for cell in ws[1] ]
    lower = [str(h).lower() for h in headers]
    for cand in header_name_candidates:
        cand_low = cand.lower()
        if cand_low in lower:
            return lower.index(cand_low) + 1
    return None


def _apply_zebra(ws, start_row=2):
    """
    Light zebra striping to aid readability (does not override FAIL/PASS/REVIEW fills).
    """
    for r in range(start_row, ws.max_row + 1):
        if (r % 2) == 1:  # odd-numbered data rows
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                if cell.fill is None or cell.fill.fill_type is None:
                    cell.fill = FILL_ODD


def _apply_result_colors(ws, result_col_idx):
    """
    Color only the RESULT cell so native gridlines remain visible elsewhere.
    """
    if result_col_idx is None:
        return
    for r in range(2, ws.max_row + 1):
        cell = ws.cell(row=r, column=result_col_idx)
        val = str(cell.value or "").strip().upper()
        cell.fill = RESULT_TO_FILL.get(val, FILL_NONE)


def _apply_refinement_borders(ws, refinement_col_idx):
    """
    Draw a red or amber border around the refinement cell depending on severity.
    """
    if refinement_col_idx is None:
        return
    for r in range(2, ws.max_row + 1):
        cell = ws.cell(row=r, column=refinement_col_idx)
        val = str(cell.value or "").strip().upper()
        if val in REFINE_RED:
            cell.border = BORDER_RED
        elif val in REFINE_AMB:
            cell.border = BORDER_AMBER


def format_excel_sheet(
    writer,
    sheet_name,
    result_col_candidates=("G1_RESULT", "G1_1_RESULT", "OVERALL", "RESULT"),
    refinement_col_candidates=("REFINEMENT", "REFINEMENT_FLAG"),
    zebra=True
):
    """
    Applies:
      - Wrap text + top alignment
      - Header style + column widths
      - Optional zebra striping
      - Row color by PASS/FAIL/REVIEW (via result column)
      - Refinement cell border color (via refinement column)

    Parameters
    ----------
    writer : pandas.ExcelWriter (openpyxl engine)
    sheet_name : str
    result_col_candidates : tuple[str]   # header names to look for (first hit is used)
    refinement_col_candidates : tuple[str]
    zebra : bool
    """
    ws = writer.book[sheet_name]  # keep using the existing workbook/sheet (your current approach)

    # 1) Header + widths (preserves your behavior)
    _header_and_widths(ws)
    ws.sheet_view.showGridLines = True  # ensure gridlines are visible (in case fills override them)

    # 2) Base alignment (preserve your wrap + top)
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # 3) Row coloring by PASS/FAIL/REVIEW
    res_idx = _find_col_index(ws, result_col_candidates)
    _apply_result_colors(ws, res_idx)

    # 4) Refinement border highlight
    ref_idx = _find_col_index(ws, refinement_col_candidates)
    _apply_refinement_borders(ws, ref_idx)

    # 5) Zebra striping (applied last to untouched cells only)
    if zebra:
        _apply_zebra(ws, start_row=2)

    
    # (optional header baseline)
    _style_header(ws)

    # ✅ Always draw the thin grid last so 'lines' are visible
    _apply_thin_grid_borders(ws, start_row=1, start_col=1)

    # Also ensure worksheet gridlines are enabled (doesn't hurt)
    ws.sheet_view.showGridLines = True
