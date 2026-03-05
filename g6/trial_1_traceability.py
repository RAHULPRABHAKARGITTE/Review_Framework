import argparse
from docx import Document
import pandas as pd
from rapidfuzz import fuzz
from openpyxl.styles import PatternFill, Alignment
import config
from openpyxl.utils import get_column_letter

# ID	Description
# MRJ_SCU_STC_SRS_001	The software shall…
# [
#   ["ID", "Description"],
#   ["MRJ_SCU_STC_SRS_001", "The software shall…"]
# ]
def read_tables(path):
    doc = Document(path)
    rows = []
    for t in doc.tables:
        for r in t.rows:
            rows.append([c.text.strip() for c in r.cells])
    return rows

# Logic:
# Must contain "_"
# Must contain at least 1 number
# Must contain some letters
def looks_like_id(token):
    token = token.strip().strip(",.;:()[]")
    # If it has space(s), it's not an ID (it's likely a sentence)
    if " " in token or "\t" in token:
        return False
    return "_" in token and any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token)

#Extract ID + Description from requirement document.
def parse_requirements(path):
    rows = read_tables(path)
    data = []   # ← store each row separately (allow duplicates)

    current_id = None
    buffer = []

    for r in rows:
        if not r:
            continue

        first = r[0].strip()
        last = r[-1].strip()

        # Case 1: A NEW ID starts in this row
        if looks_like_id(first):
            # Save previous requirement (if any)
            if current_id:
                data.append([current_id, " ".join(buffer).strip()])

            current_id = first
            desc = " ".join(r[1:]).strip()
            buffer = [desc] if desc else []
            # start new description
            continue

        # Case 2: ID is at the end (rare but support it)
        elif looks_like_id(last):
            if current_id:
                data.append([current_id, " ".join(buffer).strip()])

            current_id = last
            desc = " ".join(r[:-1]).strip()
            buffer = [desc] if desc else []
            continue

        # Case 3: No ID → this row is continuation text
        if current_id:
            extra_text = " ".join(r).strip()
            buffer.append(extra_text)  # append even if repetitive


    # Save last requirement
    if current_id:
        data.append([current_id, " ".join(buffer).strip()])

    # Convert to DataFrame
    # Do NOT drop duplicates here
    df = pd.DataFrame(data, columns=["ID", "DESC"])
    return df

#Parse trace docs. Extract from_id, text, to_id + internal referenced IDs.
#TypeError: unhashable type: 'list'
# ...
# df = pd.DataFrame(parsed, columns=["FROM_ID", "FROM_TEXT", "TO_ID", "INTERNAL_IDS"]).drop_duplicates()
# This means:
# In your DataFrame, column INTERNAL_IDS contains lists (like ["MRJ_SCU_STC_SRS_146"]).
# drop_duplicates() tries to compare whole rows, including that list column.
# Pandas needs to hash values to compare them, but lists are not hashable
def parse_traceability(path):
    rows = read_tables(path)
    parsed = []

    for r in rows:

        # Ensure row has at least 3 columns (FROM, TEXT, TO)
        if len(r) < 3:
            r = r + [""] * (3 - len(r))

        from_id = r[0].strip() if looks_like_id(r[0]) else None
        desc    = r[1].strip()

        # The last column is ALWAYS the mapped destination IDs
        raw_to  = r[-1].strip()

        # Split multiple IDs (newline / space / comma)
        tokens = raw_to.replace("\n", " ").replace(",", " ").split()
        mapped_ids = [t for t in tokens if looks_like_id(t)]

        # Detect justification (any extra column beyond text & ID)
        # Detect justification in LAST COLUMN
        justification = False
        last_col = r[-1].strip()

        if last_col and not looks_like_id(last_col):

            last_col_lower = last_col.lower()

            # Check if any justification keyword exists
            if any(k.lower() in last_col_lower for k in config.JUSTIFICATION_KEYWORDS):

                # Remove keywords and check remaining meaningful content
                cleaned = last_col_lower
                for k in config.JUSTIFICATION_KEYWORDS:
                    cleaned = cleaned.replace(k.lower(), "")

                if len(cleaned.strip()) > 15:   # avoids garbage text
                    justification = True


        # If no mapped IDs → keep as single row with TO_ID=None
        if not mapped_ids:
            parsed.append((from_id, desc, None, justification))
        else:
            # Expand: one row per mapped ID
            for to_id in mapped_ids:
                parsed.append((from_id, desc, to_id, justification))

    # Convert to DataFrame
    df = pd.DataFrame(parsed, columns=["FROM_ID", "FROM_TEXT", "TO_ID", "HAS_JUSTIFICATION"])
    return df


# It compares requirement text in the traceability document with the original requirement document (SRS or SYS) and tells you:
# Is the text exactly same? ✅
# If not, how similar it is (fuzzy %)?
# Or is the ID missing in original document?
# orig_map = {
#   "SRS_001": "The system shall turn ON the LED.",
#   "SRS_002": "The system shall turn OFF the LED."
# }
def text_verification(trace_df, orig_df, id_col="FROM_ID", text_col="FROM_TEXT"):
    results = []

    # Use FIRST occurrence of each ID as the "official" one
    base_df = orig_df.drop_duplicates(subset=["ID"], keep="first")
    orig_map = dict(zip(base_df["ID"], base_df["DESC"]))

    for _, row in trace_df.iterrows():
        rid, trace_txt = row[id_col], row[text_col]

        final_score = 0   # ✅ SAFE DEFAULT
        status = ""

        # -----------------------------
        # CASE 1: ID missing in traceability document
        # -----------------------------
        if not rid or str(rid).strip() == "":
            # Fuzzy match text to find best ID
            best_id = None
            best_score = -1
            best_orig_text = ""

            for oid, otext in orig_map.items():
                score = fuzz.token_set_ratio(trace_txt, otext)
                if score > best_score:
                    best_score = score
                    best_id = oid
                    best_orig_text = otext

            results.append([
                best_id,          # inferred ID
                trace_txt,
                best_orig_text,   # real original text
                "ERROR – ID missing in traceability document",
                best_score
            ])
            continue

        orig_txt = orig_map.get(rid, "")
        if not orig_txt:
            status = "ID Not Found OR Derived Requirement"
            final_score = 0
        elif orig_txt.strip() == trace_txt.strip():
            status = "Exact Match"
            final_score = 100
        else:
            # ---------- SIMPLE FUZZY LOGIC ADDED ----------
            base_score = fuzz.token_set_ratio(orig_txt, trace_txt)
            strict_score = fuzz.ratio(orig_txt, trace_txt)

            # Penalize when trace text is much longer than original
            length_penalty = len(orig_txt) / max(len(trace_txt), 1)
            final_score = int(strict_score * length_penalty)

            if final_score >= 90:
                status = "Exact Match"
            else:
                status = "MisMatch"
        results.append([rid, trace_txt, orig_txt, status, final_score])
    return pd.DataFrame(results, columns=["REQ_ID", "Trace_Text", "Original_Text", "Status", "Fuzzy_Score"])

#Check whether every SRS requirement has at least one trace entry.
def check_srs_trace_coverage(srs_df, trace_s2sys_df):
    original_srs_ids = set(srs_df["ID"].astype(str))
    traced_srs_ids = set(
        trace_s2sys_df["FROM_ID"]
        .dropna()
        .astype(str)
    )

    missing_in_trace = original_srs_ids - traced_srs_ids

    coverage_issues = pd.DataFrame(
    [
        [srs_id, "SRS", "NOT TRACEABLE", "No mapping found in SRS→SYS traceability document"]
        for srs_id in missing_in_trace
    ],
    columns=["ID", "Document", "Issue_Type", "Details"]
    )

    return coverage_issues

#Check whether every SYS requirement has at least one trace entry.
def check_sys_trace_coverage(sys_df, trace_sys2s_df):
    original_sys_ids = set(sys_df["ID"].astype(str))
    traced_sys_ids = set(
        trace_sys2s_df["FROM_ID"]
        .dropna()
        .astype(str)
    )

    missing_in_trace = original_sys_ids - traced_sys_ids

    return pd.DataFrame(
        [
            [sys_id, "SYS", "NOT TRACEABLE",
             "No mapping found in SYS→SRS traceability document"]
            for sys_id in missing_in_trace
        ],
        columns=["ID", "Document", "Issue_Type", "Details"]
    )


# Check for invalid SRS IDs used in traceability document
def check_invalid_srs_ids(trace_s2sys_df, srs_df):
    valid_srs_ids = set(srs_df["ID"].astype(str))
    traced_srs_ids = set(
        trace_s2sys_df["FROM_ID"]
        .dropna()
        .astype(str)
    )

    invalid_ids = traced_srs_ids - valid_srs_ids

    return pd.DataFrame(
        [
            [srs_id, "SRS", "INVALID_ID", "SRS ID used in traceability but not found in original SRS document"]
            for srs_id in invalid_ids
        ],
        columns=["ID", "Document", "Issue_Type", "Details"]
    )

# CROSS MATCH VALIDATION (SRS→SYS vs SYS→SRS)
def is_object_type_derived(text):
    if not text:
        return False
    text_lower = text.lower()
    # Check if any object type key exists
    has_object_type = any(
        key in text_lower for key in config.OBJECT_TYPE_KEYS
    )

    # Check if derived keyword exists
    has_derived = any(
        word in text_lower for word in config.DERIVED_KEYWORDS
    )

    return has_object_type and has_derived
    

# CROSS MATCH VALIDATION (SRS→SYS vs SYS→SRS)
def cross_match(s2sys_df, sys2s_df, srs_df, sys_df):

    # Build sets of valid original IDs
    valid_srs_ids = set(srs_df["ID"].astype(str))
    valid_sys_ids = set(sys_df["ID"].astype(str))

    def normalize(a, b):
        if a is None or b is None:
            return None
        if "_SRS_" in a and "_SYS_" in b: return (a, b)
        if "_SYS_" in a and "_SRS_" in b: return (b, a)
        return None

    # Build SRS→SYS mapping pairs
    srs2sys_pairs = set()
    for a, b in zip(s2sys_df["FROM_ID"], s2sys_df["TO_ID"]):
        pair = normalize(a, b)
        if pair:
            srs2sys_pairs.add(pair)

    # Build SYS→SRS mapping pairs
    sys2s_pairs = set()
    for a, b in zip(sys2s_df["FROM_ID"], sys2s_df["TO_ID"]):
        pair = normalize(a, b)
        if pair:
            sys2s_pairs.add(pair)

    rows = []
    seen = set()
    seen_rev = set()
    # ------------------------------------------
    # 1) Evaluate SRS→SYS mappings
    # The BIG Pandas trap: == None
    # ❌ This comparison is not reliable in Pandas:
    # Because Pandas internally treats missing values as:
    # None
    # OR NaN
    # OR NaT
    # And NaN == None is always False
    # ------------------------------------------
    for a, b, justify_flag, trace_text in zip(s2sys_df["FROM_ID"], s2sys_df["TO_ID"], s2sys_df["HAS_JUSTIFICATION"], s2sys_df["FROM_TEXT"]):

        # Missing SRS ID
        if a is None or str(a).strip() == "":
            rows.append([None, b if b else None, "ERROR – SRS ID Missing in SRS→SYS Traceability Document"])
            continue

        # Missing SYS ID Could be derived requirement → handle justification
        if b is None or str(b).strip() == "":

            # 1️⃣ Check Object Type from trace text (highest priority)
            if is_object_type_derived(trace_text):
                rows.append([a, None, "Derived Requirement (Object Type: Derived)"])
                continue

            if justify_flag:
                rows.append([a, None, "Derived Requirement (Justification Provided)"])
                continue
            

            rows.append([a, None, "ERROR – Possible Derived Req OR SYS ID Missing in SRS→SYS Traceability Document"])
            continue

        # ERROR: SRS ID not found in original document
        if a not in valid_srs_ids:
            rows.append([a, b if b else None, "ERROR – SRS ID not found in original SRS document"])
            continue

        # ERROR: SYS ID not found in original SYS document
        if b not in valid_sys_ids:
            rows.append([a, b, "ERROR – SYS ID not found in original SYS document"])
            continue

        # Normal case
        norm = normalize(a, b)
        if not norm:
            continue

        srs, sys = norm

        if norm in seen:
            status = "DUPLICATE – This SRS→SYS mapping already appeared earlier in the traceability document."
        else:
            if norm in sys2s_pairs:
                status = "MATCH – Mapping exists in both SRS→SYS and SYS→SRS traceability documents."
            else:
                status = "MISMATCH – Mapping exists in SRS→SYS but NOT found in SYS→SRS traceability document."
            seen.add(norm)

        rows.append([srs, sys, status])

    # ------------------------------------------
    # 2) Check SYS→SRS mappings missing in SRS→SYS
    # ------------------------------------------
    for a, b in zip(sys2s_df["FROM_ID"], sys2s_df["TO_ID"]):

        # Check missing SYS ID
        if a is None or str(a).strip() == "":
            rows.append([b if b else "None", None, "ERROR – SYS ID Missing in SYS→SRS Traceability Document"])
            continue

        # ERROR: SYS ID not in original SYS doc
        if a not in valid_sys_ids:
            rows.append([None, a, "ERROR – SYS ID not found in original SYS document"])
            continue

        # Check missing SRS ID
        if b is None or str(b).strip() == "":
            rows.append([None, a, "ERROR – SRS ID Missing in SYS→SRS Traceability Document"])
            continue

        # ERROR: SRS ID not in original SRS doc
        if b not in valid_srs_ids:
            rows.append([b, a, "ERROR – SRS ID not found in original SRS document"])
            continue

        # Duplicate detection for SYS→SRS
        norm = normalize(a, b)
        if norm:
            if norm in seen_rev:
                rows.append([norm[1], norm[0],
                            "DUPLICATE – This SYS→SRS mapping already appeared earlier in the traceability document."])
                continue
            else:
                seen_rev.add(norm)

        # Reverse mismatch
        if norm and norm not in srs2sys_pairs:
            rows.append([norm[0], norm[1],
                        "MISMATCH – Mapping exists in SYS→SRS but NOT found in SRS→SYS traceability document."])
            continue

    return pd.DataFrame(rows, columns=["SRS_ID", "SYS_ID", "Status"]).drop_duplicates()

def build_master_summary(srs_df, text_mismatch_df, cross_df, coverage_df):
    rows = []

    srs_ids = sorted(set(srs_df["ID"].astype(str)) | set(cross_df["SRS_ID"].dropna().astype(str)))

    for srs_id in srs_ids:

        # -----------------------------
        # 6.1 – At least one mapping
        # Introduce a boolean flag right after 6.1
        # -----------------------------

        invalid_srs_ids = set(
            cross_df[
                cross_df["Status"].str.contains(
                    "SRS ID not found in original SRS document",
                    na=False
                )
            ]["SRS_ID"]
        )

        if srs_id in invalid_srs_ids:
            g61 = "FAIL\nSRS ID not found in original SRS document"
            has_trace = False

        elif srs_id in coverage_df["ID"].values:
            g61 = "FAIL\nNo mapping found in SRS→SYS traceability document"
            has_trace = False

        else:
            g61 = "PASS"
            has_trace = True


        # --------------------------------------------
        # If no trace exists, dependent checks FAIL/N/A
        # --------------------------------------------
        if not has_trace:
            g62 = "N/A"
            g63 = "N/A"
            g64 = "FAIL"
            g65 = "FAIL"
            g66 = "FAIL"

            rows.append([srs_id, g61, g62, g63, g64, g65, g66])
            continue

        # -----------------------------
        # 6.2 – Multiple mappings
        # -----------------------------
        g62 = ("PASS")

        # -----------------------------
        # 6.3 – Derived requirement
        # -----------------------------
        derived_rows = cross_df[
            (cross_df["SRS_ID"] == srs_id) &
            (
                cross_df["Status"].str.contains(
                    "Derived Requirement \\(",
                    na=False
                )
            )
        ]
        
        if not derived_rows.empty:
            g63 = f"PASS\n{derived_rows.iloc[0]['Status']}"
        else:
            g63 = "N/A\nNot a derived requirement"

        # -----------------------------
        # 6.4 – Bidirectional traceability
        # -----------------------------
        cross_rows = cross_df[cross_df["SRS_ID"] == srs_id]

        if any(cross_rows["Status"].str.contains("MISMATCH|ERROR", na=False)):
            g64 = "FAIL\nBidirectional mapping missing or mismatched"
        else:
            g64 = "PASS\nBidirectional traceability maintained"

        # -----------------------------
        # 6.5 – Completeness & accuracy
        # -----------------------------
        if any(cross_rows["Status"].str.contains("ERROR", na=False)):
            g65 = g65 = "FAIL\nInvalid or incomplete traceability entries detected"
        else:
            g65 = "PASS\nTraceability matrix complete and accurate"

        # -----------------------------
        # 6.6 – Text consistency
        # -----------------------------
        text_rows = text_mismatch_df[
            text_mismatch_df["REQ_ID"] == srs_id
        ]

        if text_rows.empty:
            g66 = "FAIL\nNo traceability text available for comparison"
        else:
            status = text_rows.iloc[0]["Status"]
            if status in ["Exact Match", "High Similarity"]:
                g66 = f"PASS"
            else:
                g66 = f"FAIL"

        rows.append([
            srs_id, g61, g62, g63, g64, g65, g66
        ])

    return pd.DataFrame(
        rows,
        columns=["Requirement_ID", "6.1", "6.2", "6.3", "6.4", "6.5", "6.6"])


# MAIN EXCEL GENERATION
def generate_excel_report(srs_path, sys_path, trace_s2sys_path, trace_sys2s_path, outfile):
    srs_df = parse_requirements(srs_path)
    sys_df = parse_requirements(sys_path)
    trace_s2sys_df = parse_traceability(trace_s2sys_path)
    trace_sys2s_df = parse_traceability(trace_sys2s_path)

    dup_srs = srs_df[srs_df.duplicated("ID", keep=False)]

    dup_srs_rows = pd.DataFrame(
    [
        [row["ID"], "SRS", "DUPLICATE_ID", "Duplicate ID found in original SRS document"]
        for _, row in dup_srs.iterrows()
    ],
    columns=["ID", "Document", "Issue_Type", "Details"]
    )

    srs_coverage = check_srs_trace_coverage(srs_df, trace_s2sys_df)
    sys_coverage = check_sys_trace_coverage(sys_df, trace_sys2s_df)

    invalid_srs_rows = check_invalid_srs_ids(trace_s2sys_df, srs_df)

    original_doc_issues = pd.concat(
    [dup_srs_rows, srs_coverage, sys_coverage, invalid_srs_rows],
    ignore_index=True
    )

    text_mismatch = pd.concat([
        text_verification(trace_s2sys_df, srs_df),
        text_verification(trace_sys2s_df, sys_df, id_col="FROM_ID", text_col="FROM_TEXT")
    ])

    cross = cross_match(trace_s2sys_df, trace_sys2s_df, srs_df, sys_df)

    master = build_master_summary(srs_df, text_mismatch, cross, srs_coverage)

    with pd.ExcelWriter(outfile, engine="openpyxl") as writer:

        text_mismatch.to_excel(excel_writer=writer, sheet_name="Text_Mismatch", index=False)
        cross.to_excel(excel_writer=writer, sheet_name="Cross_Mismatch", index=False)
        original_doc_issues.to_excel(excel_writer=writer, sheet_name="Original_Document_Issues", index=False)
        master.to_excel(excel_writer=writer, sheet_name="Master_Traceability_Summary", index=False, header=False,startrow=2)

        
        ws = writer.book["Master_Traceability_Summary"]

        # ------------------------------------------------
        # 1️⃣ Merge A1:A2 → REQ_ID
        # ------------------------------------------------
        ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
        ws.cell(row=1, column=1, value="Requirement_ID")
        ws.cell(row=1, column=1).alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

        # ------------------------------------------------
        # 2️⃣ Merge B1:G1 → Checklist title
        # ------------------------------------------------
        ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=7)
        ws.cell(
            row=1,
            column=2,
            value="6. High-Level requirements are traceable to system requirements"
        )
        ws.cell(row=1, column=2).alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

        # ------------------------------------------------
        # 3️⃣ Row 2 → Individual checklist IDs (NO merge)
        # ------------------------------------------------
        checklist_headers = [
            "6.1: Verify one-to-one mapping: Ensure each HLR maps to a system requirement.",
            "6.2: Multiple HLRs map to one system requirement",
            "6.3: Identify derived requirements: Ensure clearly marked and justified.",
            "6.4: Maintain bidirectional traceability",
            "6.5: Validate traceability matrix: Ensure completeness and accuracy",
            "6.6: Verify requirement text consistency"
        ]

        for idx, text in enumerate(checklist_headers, start=2):
            ws.cell(row=2, column=idx, value=text)
            ws.cell(row=2, column=idx).alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )


        # ------------------------------------------------
        # Apply formatting AFTER writing all sheets
        # ------------------------------------------------
        workbook = writer.book
        wrap_alignment = Alignment(wrap_text=True)

        def enable_wrap(sheet_name):
            ws = workbook[sheet_name]
            for row in range(2, ws.max_row + 1):
                for col in range(1, ws.max_column + 1):
                    ws.cell(row=row, column=col).alignment = wrap_alignment

        def set_column_width(sheet_name, width=35):
            ws = workbook[sheet_name]

            for col_idx in range(1, ws.max_column + 1):
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = width



        # Defining red fill definition
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        # ---------- Helper function to highlight rows ----------
        #This function targets a single sheet.
        def highlight_errors(sheet_name):
            ws = workbook[sheet_name]
            status_col = None

            # Find "Status" column index
            #✔ Loop through header row (row 1)
            # ✔ Find which column contains "Status"
            # ✔ Save that column index so we know where to check for errors.
            for col in range(1, ws.max_column + 1):
                if ws.cell(row=1, column=col).value == "Status":
                    status_col = col
                    break

            if not status_col:
                return  # No status column in this sheet

            # Apply red fill to rows with errors
            for row in range(2, ws.max_row + 1):
                status = str(ws.cell(row=row, column=status_col).value)
                if (
                    "ERROR" in status
                    or "MISMATCH" in status
                    or "DUPLICATE" in status
                ):
                    for col in range(1, ws.max_column + 1):
                        ws.cell(row=row, column=col).fill = red_fill

        def highlight_master_fails(sheet_name):
            ws = workbook[sheet_name]

            # Skip header row (row 1)
            for row in range(2, ws.max_row + 1):
                for col in range(2, ws.max_column + 1):  # skip Requirement_ID column
                    cell_value = str(ws.cell(row=row, column=col).value)

                    if "FAIL" in cell_value:
                        ws.cell(row=row, column=col).fill = red_fill

        # Apply wrap function to your master sheet
        enable_wrap("Master_Traceability_Summary")

        # Set column width for master sheet
        set_column_width("Master_Traceability_Summary", width=35)

        # Apply red highlight to master sheet FAILs
        highlight_master_fails("Master_Traceability_Summary")

        # Apply highlight to your two sheets
        highlight_errors("Text_Mismatch")
        highlight_errors("Cross_Mismatch")
        
    print("\n✔ REPORT GENERATED:", outfile)
    

#  COMMAND LINE USE
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--srs")
    ap.add_argument("--sys")
    ap.add_argument("--trace_s2sys")
    ap.add_argument("--trace_sys2srs")
    ap.add_argument("--out", default="Traceability_Result.xlsx")
    args = ap.parse_args()
    generate_excel_report(args.srs, args.sys, args.trace_s2sys, args.trace_sys2srs, args.out)

if __name__ == "__main__":
    main()


#python trial_1_traceability.py --srs Software_Req.docx --sys System_Req.docx --trace_s2sys Traceability_SRS_TO_SYS.docx --trace_sys2srs Traceability_SYS_TO_SRS.docx --out Traceability_Result.xlsx 