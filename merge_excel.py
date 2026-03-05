# -*- coding: utf-8 -*-
"""
Fast + Safe Excel merge with post-formatting using excel_utils.format_excel_sheet.

- Copies only values from each source sheet's used range (avoids corrupt XML)
- Enforces unique sheet names within Excel's 31-char limit
- Atomic save to avoid half-written files
- Family logic:
    * Families considered: G1, G2, G3, G4, G5, G7
    * G3: include only the newest G3_*.xlsx
    * G2: include only whitelisted files (G2_Result*, CI_G2_4_7*)
    * Explicit include: SRS_Review_Report.xlsx
- Beautifies each created tab via excel_utils.format_excel_sheet
"""

from openpyxl import load_workbook, Workbook
from openpyxl.utils import range_boundaries
from pathlib import Path
import re
import time
import os

# === import your beautifier ===
import g1.excel_utils as xu  # <-- uses format_excel_sheet(writer_like, sheet_name)

# ---------------- SETTINGS ----------------
SOURCE_DIR = Path(r"C:\Users\traviprakash\Documents\Tool_development\Review_Framework\outputs")
MASTER_XLSX = SOURCE_DIR / "All_In_One.xlsx"
TEMP_XLSX = SOURCE_DIR / "~All_In_One.tmp.xlsx"

FAMILY_ORDER = ["G1", "G2", "G3", "G4", "G5", "G7"]
G3_PREFIX = "G3__"

# Only these two G2 patterns allowed
G2_ALLOWED = [
    re.compile(r"^G2[_\-\s]?RESULT", re.IGNORECASE),
    re.compile(r"^CI[_\-\s]?G2[_\-\s]?4[_\-\s]?7", re.IGNORECASE),
]

# Extra file stems to include even if not G# family
EXPLICIT_INCLUDE_STEMS = {
    "SRS_Review_Report",
}

# Toggle formatting (set False to test raw merge speed)
APPLY_FORMATTING = True
# -------------------------------------------

INVALID_CHARS = re.compile(r'[:\\/\?\*\[\]]')

def sanitize_title(name: str) -> str:
    """Replace Excel-invalid characters and strip trailing spaces."""
    return INVALID_CHARS.sub("_", name).rstrip()

def safe_unique_title(proposed: str, used: set) -> str:
    """
    Return a worksheet title that is:
      - sanitized
      - <= 31 chars
      - unique in 'used' by reserving space for a suffix __N
    This avoids infinite loops when many names share the same 31-char prefix.
    """
    MAXLEN = 31
    title = sanitize_title(proposed)

    # Fast path
    if len(title) <= MAXLEN and title not in used:
        used.add(title)
        return title

    # Start from the truncated base
    base = title[:MAXLEN]
    if base not in used:
        used.add(base)
        return base

    # Reserve room for suffix __N
    i = 2
    while True:
        suffix = f"__{i}"
        keep = MAXLEN - len(suffix)
        candidate = (base[:keep] + suffix) if keep > 0 else suffix[-MAXLEN:]
        candidate = sanitize_title(candidate)
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1

def get_family(stem: str):
    s = stem.upper().replace("-", "_")
    parts = re.split(r"[_\s]+", s)
    for p in parts:
        if p in FAMILY_ORDER:
            return p
    return None

def is_g2_allowed(stem: str) -> bool:
    return any(p.search(stem) for p in G2_ALLOWED)

def is_explicit_include(path: Path) -> bool:
    return path.stem in EXPLICIT_INCLUDE_STEMS

def used_range_bounds(ws):
    """Bounds of the used range (min_col, min_row, max_col, max_row)."""
    dim = ws.calculate_dimension()  # e.g. "B2:F37" or "A1"
    if ":" in dim:
        (min_cell, max_cell) = dim.split(":")
        min_col, min_row, max_col, max_row = range_boundaries(f"{min_cell}:{max_cell}")
    else:
        min_col = max_col = 1
        min_row = max_row = 1
    return min_col, min_row, max_col, max_row

def get_visible_nonempty_sheets(wb):
    """Return visible, non-empty sheets."""
    out = []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        dim = ws.calculate_dimension()
        if ":" not in dim and (ws["A1"].value in (None, "")):
            continue
        out.append(ws)
    return out

def copy_values_only(ws, target):
    """Copy only values from the used range (fast and robust)."""
    min_c, min_r, max_c, max_r = used_range_bounds(ws)
    # Re-anchor to (1,1) on the target
    for row in ws.iter_rows(min_row=min_r, max_row=max_r, min_col=min_c, max_col=max_c):
        for cell in row:
            target.cell(
                row=cell.row - min_r + 1,
                column=cell.column - min_c + 1,
                value=cell.value
            )

# --- tiny shim so excel_utils can work without pandas.ExcelWriter ---
class _WriterLike:
    """Mimics pandas.ExcelWriter just enough for excel_utils: writer.book[...]"""
    def __init__(self, workbook):
        self.book = workbook
# -------------------------------------------------------------------

def merge_excel_files():
    start = time.time()

    # Safety: ensure temp from prior runs is gone
    if TEMP_XLSX.exists():
        try:
            TEMP_XLSX.unlink()
        except Exception:
            pass

    # 1) Collect files
    family_buckets = {f: [] for f in FAMILY_ORDER}
    explicit_files = []

    for p in SOURCE_DIR.iterdir():
        if p.suffix.lower() not in (".xlsx", ".xlsm"):
            continue
        if p.name.startswith("~$"):            # Skip Excel lock files
            continue
        if p.resolve() == MASTER_XLSX.resolve():
            continue
        if p.resolve() == TEMP_XLSX.resolve():
            continue

        if is_explicit_include(p):
            explicit_files.append(p)
            continue

        fam = get_family(p.stem)
        if not fam:
            continue

        if fam == "G2" and not is_g2_allowed(p.stem):
            continue

        family_buckets[fam].append(p)

    # 2) Order: G1→G2→G3(newest only)→G4→G5→G7 → then explicit includes
    ordered = []
    for fam in FAMILY_ORDER:
        items = sorted(family_buckets[fam], key=lambda x: x.name)
        if fam == "G3" and items:
            newest = max(items, key=lambda x: x.stat().st_mtime)
            ordered.append(newest)
        else:
            ordered.extend(items)
    ordered.extend(sorted(explicit_files, key=lambda x: x.name))

    if not ordered:
        print("No matching Excel files to merge. Nothing to do.")
        return

    # 3) Create master in memory
    master = Workbook()
    master.remove(master.active)
    used_titles = set()
    writer_like = _WriterLike(master)  # for excel_utils

    # 4) Copy + Beautify per sheet
    for file in ordered:
        print(f"📄 {file.name}")
        try:
            wb = load_workbook(file, data_only=True, read_only=False)
        except Exception as e:
            print(f"   ❌ Failed to open ({e}). Skipping file.")
            continue

        fam = get_family(file.stem)

        for ws in get_visible_nonempty_sheets(wb):
            # Decide final sheet name
                
            if fam == "G3":
                proposed = f"{G3_PREFIX}{ws.title}"
            else:
                proposed = f"{file.stem}_{ws.title}"

            title = safe_unique_title(proposed, used_titles)
            try:
                target = master.create_sheet(title)
                copy_values_only(ws, target)
                print(f"   ✔ Copied: {ws.title} → {title}")

                # ---- Beautify using your excel_utils.py ----
                if APPLY_FORMATTING:
                    try:
                        xu.format_excel_sheet(
                            writer_like,
                            sheet_name=title,
                            # optional: pass your preferred header names
                            result_col_candiates=("OVERALL", "RESULT", "G1_RESULT", "G1_1_RESULT"),
                            # NOTE: excel_utils param is `result_col_candiates`? -> it's `result_col_candidates`.
                            # We will rely on defaults inside excel_utils to avoid mismatch.
                        )
                        # ^ we'll simply rely on defaults to avoid arg name mismatch
                    except TypeError:
                        # If arg names mismatch, call with defaults
                        xu.format_excel_sheet(writer_like, sheet_name=title)
                    except Exception as fe:
                        print(f"   ⚠️  Formatting skipped for '{title}' ({fe})")

            except Exception as e:
                # Remove half-created sheet and continue
                if title in master.sheetnames:
                    master.remove(master[title])
                print(f"   ⚠️  Skipped sheet '{ws.title}' ({e})")

        wb.close()

    # 5) Atomic save: write to temp, then replace
    try:
        master.save(TEMP_XLSX)
        if MASTER_XLSX.exists():
            try:
                MASTER_XLSX.unlink()  # ensure Excel is closed
            except PermissionError:
                print("   ❌ Permission denied: Close All_In_One.xlsx and try again.")
                return
        os.replace(TEMP_XLSX, MASTER_XLSX)
    except Exception as e:
        print("❌ Failed to save merged workbook:", e)
        try:
            if TEMP_XLSX.exists():
                TEMP_XLSX.unlink()
        except Exception:
            pass
        return

    print(f"\n✅ Done in {round(time.time() - start, 2)}s")
    print(f"   Saved: {MASTER_XLSX}")
