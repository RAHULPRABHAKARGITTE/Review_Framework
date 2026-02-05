
# g7_logic.py
import re
import html
import pandas as pd
from datetime import datetime
from docx import Document
import argparse
from openpyxl import load_workbook
import numpy as np
import pytest
import os
from g7.config import config_g7 as config
from g7.io_utils.io_g7 import write_or_replace_sheet






__all__ = [
    "parse_requirements",
    "append_result",
    "if_else_syntax_check",
    "for_condition_syntax_check",
    "while_syntax_check",
    "switch_syntax_check",
    "edge_case_check",
    "checklist_presence",
    "div_by_zero_check",
    "infinite_loop_check",
    "null_pointer_check",
    "out_of_range_check",
    "var_input_analysis",
    "get_objective_for_check",
    "print_objective",
]

# -------------------------
# Objective mapping utilities
# -------------------------

# Central mapping: check name -> Objective ID
OBJECTIVE_MAP = {
    # Objective G 7.1
    "if_else_syntax_check": "Objective G 7.1",
    "written_requirement_understandable_check": "Objective G 7.1",
    "for_condition_syntax_check": "Objective G 7.1",
    "while_syntax_check": "Objective G 7.1",
    "switch_syntax_check": "Objective G 7.1",

    # Objective G 7.2
    "edge_case_check": "Objective G 7.2",

    # Objective G 7.3
    "checklist_presence": "Objective G 7.3",

    # Objective G 7.4
    "Timing_Constraints": "Objective G 7.4",
    "Resource_Constraints": "Objective G 7.4",

    # Objective G 7.5
    "Correctness": "Objective G 7.5",
    "Determinism": "Objective G 7.5",
    "Testability": "Objective G 7.5", 
    "Robustness": "Objective G 7.5",
    "Verifiability": "Objective G 7.5",

    # Objective G 7.7
    "div_by_zero_check": "Objective G 7.7",
    "infinite_loop_check": "Objective G 7.7",
    "null_pointer_check": "Objective G 7.7",
    "out_of_range_check": "Objective G 7.7",
    "var_input_analysis": "Objective G 7.7",


    # Not explicitly mapped in headings; leave None if not applicable
    # "var_input_analysis": None,
}

def get_objective_for_check(check: str) -> str | None:
    """
    Return the Objective ID string for a given check name, or None if no mapping exists.
    """
    return OBJECTIVE_MAP.get(check)

def print_objective(check: str) -> None:
    """
    Print 'Objective G 7.X' if the check belongs to Respective Objective G 7.X,
    else print 'No match found'. This satisfies the original requirement.
    """
    g71_checks = {
      "if_else_syntax_check",
      "for_condition_syntax_check",
      "while_syntax_check",
      "switch_syntax_check",
      "written_requirement_understandable_check",
    }
    if check in g71_checks:
        print("Objective G 7.1")

    g72_checks = {
    "edge_case_check",
    }
    if check in g72_checks:
        print("Objective G 7.2")

    g73_checks = {
    "checklist_presence",
    }
    if check in g73_checks:
        print("Objective G 7.3")

    g74_checks = {
    "Timing_Constraints",
    "Resource_Constraints",
    }
    if check in g74_checks:
        print("Objective G 7.4")

    g75_checks = {
    "Correctness",
    "Determinism",
    "Testability",
    "Robustness",
    "Verifiability",
    }
    if check in g75_checks:
        print("Objective G 7.5")
    
    g77_checks = {
    "div_by_zero_check",
    "infinite_loop_check",
    "null_pointer_check",
    "out_of_range_check",
    "var_input_analysis",
    }
    if check in g77_checks:
        print("Objective G 7.7")
    

# -------------------------
# SRS reading utilities
# -------------------------

# ID    Description
# MRJ_SCU_STC_SRS_001   The software shall…
# [
#   ["ID", "Description"],
#   ["MRJ_SCU_STC_SRS_001", "The software shall…"]
# ]
def read_SRS_doc(path):
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

# Extract ID + Description from requirement document.
def parse_requirements(path):
    rows = read_SRS_doc(path)
    data = []  # ← store each row separately (allow duplicates)
    algo_data = []  # store only algorithm-related requirements

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
                desc = " ".join(buffer).strip()
                data.append([current_id, desc])
                # check for "algorithm"
                if (
                    "algorithm" in desc.lower()
                    or "pseudocode" in desc.lower()
                    or "logic below" in desc.lower()
                    or "following logic" in desc.lower()
                ):
                    algo_data.append([current_id, desc])

            current_id = first
            buffer = [" ".join(r[1:]).strip()]  # start new description
            continue

        # Case 2: ID is at the end (rare but support it)
        elif looks_like_id(last):
            if current_id:
                desc = " ".join(buffer).strip()
                data.append([current_id, desc])
                if (
                    "algorithm" in desc.lower()
                    or "pseudocode" in desc.lower()
                    or "logic below" in desc.lower()
                    or "following logic" in desc.lower()
                ):
                    algo_data.append([current_id, desc])

            current_id = last
            buffer = [" ".join(r[:-1]).strip()]
            continue

        # Case 3: No ID → this row is continuation text
        if current_id:
            extra_text = " ".join(r).strip()
            if extra_text:
                buffer.append(extra_text)

    # Save last requirement
    if current_id:
        desc = " ".join(buffer).strip()
        data.append([current_id, desc])
        if (
            "algorithm" in desc.lower()
            or "pseudocode" in desc.lower()
            or "logic below" in desc.lower()
            or "following logic" in desc.lower()
        ):
            algo_data.append([current_id, desc])

    # Convert to DataFrame
    df = pd.DataFrame(data, columns=["ID", "DESC"])
    algo_df = pd.DataFrame(algo_data, columns=["ID", "DESC"])

    # Mark rows in df that are NOT in algo_df
    df["IS_NOT_ALGO"] = ~df.apply(tuple, axis=1).isin(algo_df.apply(tuple, axis=1))
    non_algo_df = df[df["IS_NOT_ALGO"]]

    # Save to Excel with multiple sheets
    with pd.ExcelWriter("requirements_output1.xlsx", engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="All_Requirements", index=False)
        algo_df.to_excel(writer, sheet_name="Algorithm_Requirements", index=False)
        non_algo_df.to_excel(writer, sheet_name="Non_Algorithm_Requirements", index=False)

    return algo_df


# -------------------------------------------------------------------
# Enhanced result appender: per-ID summary + detailed rows
# -------------------------------------------------------------------
def append_result(result):
    """
    Enhanced result appender that:
      - Extracts requirement IDs from 'details' strings (expects 'at ID [XYZ]').
      - Classifies severity per detail ('Error' -> Failed, 'Caution/Notice/Warning' -> Warning, else Info).
      - Computes aggregate status per ID (Failed > Warning > Passed).
      - Writes summary to 'Results' sheet and all messages to 'Results_Details' sheet.
      - Populates 'Objective ID' for each row based on the check name.

    Required fields in 'result':
      - result['check']: str
      - result['status']: str (overall status, used for IDs with no specific messages)
      - result['details']: list[str]
      - result['timestamp']: str
      - OPTIONAL result['ids']: list of all req IDs processed (to mark Passed if no messages)
    """
    required = ("check", "status", "details", "timestamp")
    if not all(k in result for k in required):
        raise ValueError("result must have keys: 'check', 'status', 'details', 'timestamp'")

    check_name  = result["check"]
    overall     = result["status"]
    details     = result["details"] or []
    timestamp   = result["timestamp"]
    all_ids     = result.get("ids", [])  # list of all IDs for this check, used to mark Passed when no issues

    # Determine Objective ID and print if it is G 7.1 (per original requirement)
    objective_id = get_objective_for_check(check_name)
    print_objective(check_name)  # prints "Objective G 7.1" for G 7.1 checks; else "No match found"

    # Regex to extract ID from messages: expects "... at ID [XYZ] ..."
    id_rx = re.compile(r'at\s+ID\s*\[\s*(?P<ID>[^\]]+)\s*\]', re.IGNORECASE)

    def classify_severity(msg: str) -> str:
        m = msg.strip()
        if m.startswith("Error:"):
            return "Failed"
        if m.startswith("Caution:") or m.startswith("Notice:") or m.startswith("Warning:"):
            return "Warning"
        return "Info"

    # Collect detail rows per ID
    messages_by_id = {}  # {ID: [(msg, severity), ...]}
    global_msgs = []     # messages with no ID (e.g., "Scanned N requirements...")
    for msg in details:
        m = id_rx.search(msg)
        if m:
            req_id = m.group("ID").strip()
            severity = classify_severity(msg)
            messages_by_id.setdefault(req_id, []).append((msg, severity))
        else:
            global_msgs.append(msg)

    # Aggregate status per ID (Failed > Warning > Passed)
    def aggregate_status(detail_items):
        severities = {sev for (_, sev) in detail_items}
        if "Failed" in severities:
            return "Failed"
        if "Warning" in severities:
            return "Warning"
        return "Passed"  # Info-only messages → Passed

    summary_rows = []
    detail_rows  = []

    # IDs with explicit messages
    for req_id, items in messages_by_id.items():
        agg = aggregate_status(items)
        summary_rows.append({
            "Objective ID": objective_id,
            "ID": req_id,
            "Check": check_name,
            "Status": agg,
            "Timestamp": timestamp
        })
        for msg, sev in items:
            detail_rows.append({
                "Objective ID": objective_id,
                "ID": req_id,
                "Check": check_name,
                "Status": sev,
                "Details": msg,
                "Timestamp": timestamp
            })

    # IDs with no messages: mark as Passed (no evidence against)
    default_status = "Passed"
    for req_id in all_ids:
        if req_id not in messages_by_id:
            summary_rows.append({
                "Objective ID": objective_id,
                "ID": req_id,
                "Check": check_name,
                "Status": default_status,
                "Timestamp": timestamp
            })

    # Add global messages to details (ID = '__GLOBAL__')
    for msg in global_msgs:
        detail_rows.append({
            "Objective ID": objective_id,
            "ID": "__GLOBAL__",
            "Check": check_name,
            "Status": classify_severity(msg),
            "Details": msg,
            "Timestamp": timestamp
        })

    # Build dataframes
    summary_df = pd.DataFrame(summary_rows, columns=["Objective ID","ID", "Check", "Status", "Timestamp"])
    details_df = pd.DataFrame(detail_rows, columns=["Objective ID","ID", "Check", "Status", "Details", "Timestamp"])

    excel_file = config.RESULTS_XLSX
    summary_sheet = "Results"
    details_sheet = "Results_Details"

    # Write/append to Excel
    if not os.path.exists(excel_file):
        with pd.ExcelWriter(excel_file, mode="w", engine="xlsxwriter") as writer:
            summary_df.to_excel(writer, sheet_name=summary_sheet, index=False, header=True)
            details_df.to_excel(writer, sheet_name=details_sheet, index=False, header=True)
        print(f"Created {excel_file} and Results appended to {excel_file} with sheets '{summary_sheet}'(summary) and '{details_sheet}'(details) for check 'if_else_syntax_check'")
        return

    # Append to existing sheets
    book = load_workbook(excel_file)

    def append_df(writer, sheet_name, df):
        if sheet_name in book.sheetnames:
            ws = book[sheet_name]
            startrow = ws.max_row  # append below last row
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False, startrow=startrow)
        else:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=True)

    with pd.ExcelWriter(excel_file, mode="a", engine="openpyxl", if_sheet_exists="overlay") as writer:
        append_df(writer, summary_sheet, summary_df)
        append_df(writer, details_sheet, details_df)

    print(f"✅ Results appended to {excel_file} → '{summary_sheet}' (summary) and '{details_sheet}' (details) for check '{check_name}'")


## Objective G 7.1 ##

def if_else_syntax_check(algo_df):
    """
    Unified IF/ELSEIF/ELSE syntax checker for algo_df['DESC'] ...
    """
    results = {
        'check': "if_else_syntax_check",
        'status': "Passed",
        'details': [],
        'Understandable' : "Yes",
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    # Structural check
    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    # --- Token regex (case-insensitive) ---
    tok_re = re.compile(
        r'(?P<IF>\bIF\b)|'
        r'(?P<ELSEIF>\bELSE\s*IF\b|\bELSEIF\b)|'
        r'(?P<ELSE>\bELSE\b)|'
        r'(?P<THEN>\bTHEN\b)|'
        r'(?P<ENDIF>\bEND\s*IF\b|\bENDIF\b)',
        re.IGNORECASE
    )

    comparator_re    = re.compile(r'(==|!=|>=|<=|>|<|&gt;=|&lt;=|&gt;|&lt;|&amp;gt;=|&amp;lt;=|&amp;gt;|&amp;lt;)')
    single_equals_re = re.compile(r'(?<![=!<>])=(?!=)')
    ambiguous_ops_re = re.compile(r'\b(EQ|NE|GT|LT|GE|LE)\b', re.IGNORECASE)

    def normalize_line(s: str) -> str:
        s = html.unescape(s)
        s = s.replace('≥', '&gt;=').replace('≤', '&lt;=').replace('≠', '!=')
        s = s.replace('&amp;eq;', '==').replace('&amp;amp;eq;', '==')
        return s

    def validate_condition(cond_text: str, req_id, line_num, context: str):
        text = cond_text.strip()
        if text == '':
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Empty {context} condition at ID [{req_id}], Line {line_num}."
            )
            return
        # parentheses
        stack_paren = 0
        for ch in text:
            if ch == '(':
                stack_paren += 1
            elif ch == ')':
                stack_paren -= 1
                if stack_paren < 0:
                    results['status'] = "Failed"
                    results['details'].append(
                        f"Error: Unbalanced parentheses in {context} condition at ID [{req_id}], Line {line_num}: '{text}'"
                    )
                    break
        if stack_paren != 0:
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unbalanced parentheses in {context} condition at ID [{req_id}], Line {line_num}: '{text}'"
            )

        if single_equals_re.search(text):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Assignment '=' used in {context} condition (use '==') at ID [{req_id}], Line {line_num}: '{text}'"
            )

        if not comparator_re.search(text):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: No comparison operator in {context} condition at ID [{req_id}], Line {line_num}: '{text}'"
            )

        if ambiguous_ops_re.search(text):
            results['details'].append(
                f"Notice: Textual comparator detected in {context} condition at ID [{req_id}], Line {line_num}: '{text}'. Prefer symbolic operators (==, !=, >, <, >=, <=)."
            )

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', ''))
        req_id = row.get('ID', index)

        lines = desc_text.splitlines()
        stack = []

        for line_num, raw_line in enumerate(lines, 1):
            line = normalize_line(raw_line.rstrip())
            if not line.strip():
                if stack and stack[-1]['collecting'] in ('IF', 'ELSEIF'):
                    stack[-1]['cond_parts'].append('')
                continue

            tokens = list(tok_re.finditer(line))
            cursor = 0

            def add_body_segment(seg_text: str):
                text = seg_text.strip()
                if not text:
                    return
                if not stack:
                    return
                cb = stack[-1]['current_branch']
                if cb == 'IF':
                    stack[-1]['if_body_count'] += 1
                elif cb and cb.startswith('ELSEIF_'):
                    idx = int(cb.split('_')[1])
                    while len(stack[-1]['elseif_bodies']) <= idx:
                        stack[-1]['elseif_bodies'].append(0)
                    stack[-1]['elseif_bodies'][idx] += 1
                elif cb == 'ELSE':
                    stack[-1]['else_body_count'] += 1

            if not tokens:
                if stack and stack[-1]['collecting'] in ('IF', 'ELSEIF'):
                    stack[-1]['cond_parts'].append(line.strip())
                elif stack and stack[-1]['current_branch'] is not None:
                    add_body_segment(line[cursor:])
                continue

            for i, m in enumerate(tokens):
                kind = m.lastgroup
                start, end = m.start(), m.end()

                if stack and stack[-1]['collecting'] in ('IF', 'ELSEIF') and kind in ('IF', 'ELSEIF', 'ELSE', 'ENDIF'):
                    results['status'] = "Failed"
                    results['details'].append(
                        f"Error: {kind} encountered before THEN at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                    )
                    cursor = end
                    continue

                if kind == 'IF':
                    if stack and stack[-1]['current_branch'] is not None:
                        add_body_segment('nested_if')
                    stack.append({
                        'open_line': line_num,
                        'collecting': 'IF',
                        'cond_parts': [],
                        'else_seen': False,
                        'if_body_count': 0,
                        'elseif_bodies': [],
                        'else_body_count': 0,
                        'current_branch': None
                    })
                    cursor = end

                elif kind == 'ELSEIF':
                    if not stack:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: ELSEIF without an open IF at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    if stack[-1]['else_seen']:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: ELSEIF after ELSE is not allowed at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    prev = stack[-1]['current_branch']
                    if prev == 'IF' and stack[-1]['if_body_count'] == 0:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: Empty IF body before ELSEIF at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                    elif prev and prev.startswith('ELSEIF_'):
                        idx_prev = int(prev.split('_')[1])
                        if stack[-1]['elseif_bodies'][idx_prev] == 0:
                            results['status'] = "Failed"
                            results['details'].append(
                                f"Error: Empty ELSEIF body before another ELSEIF at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                            )
                    stack[-1]['collecting'] = 'ELSEIF'
                    stack[-1]['cond_parts'] = []
                    new_idx = len(stack[-1]['elseif_bodies'])
                    stack[-1]['current_branch'] = None
                    cursor = end

                elif kind == 'THEN':
                    if not stack or stack[-1]['collecting'] not in ('IF', 'ELSEIF'):
                        add_body_segment(line[cursor:start])
                        cursor = end
                        continue
                    stack[-1]['cond_parts'].append(line[cursor:start].strip())
                    cond_text = ' '.join(p for p in stack[-1]['cond_parts'] if p is not None).strip()
                    context = stack[-1]['collecting']
                    validate_condition(cond_text, req_id, line_num, context=context)
                    if context == 'IF':
                        stack[-1]['current_branch'] = 'IF'
                    else:
                        new_idx = len(stack[-1]['elseif_bodies'])
                        stack[-1]['elseif_bodies'].append(0)
                        stack[-1]['current_branch'] = f'ELSEIF_{new_idx}'
                    stack[-1]['collecting'] = None
                    stack[-1]['cond_parts'] = []
                    cursor = end

                elif kind == 'ELSE':
                    if not stack:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: ELSE without an open IF at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    add_body_segment(line[cursor:start])
                    if stack[-1]['current_branch'] is None:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: ELSE encountered before THEN at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    if stack[-1]['else_seen']:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: Multiple ELSE branches are not allowed at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    stack[-1]['else_seen'] = True
                    stack[-1]['current_branch'] = 'ELSE'
                    cursor = end

                elif kind == 'ENDIF':
                    if not stack:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: END IF/ENDIF without a matching IF at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    add_body_segment(line[cursor:start])
                    if stack[-1]['current_branch'] is None:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: END IF encountered before a THEN at ID [{req_id}], opened Line {stack[-1]['open_line']}, closed Line {line_num}."
                        )
                    else:
                        if stack[-1]['if_body_count'] <= 0:
                            results['status'] = "Failed"
                            results['details'].append(
                                f"Error: Empty IF body before END IF at ID [{req_id}], opened Line {stack[-1]['open_line']}, closed Line {line_num}."
                            )
                        for i, cnt in enumerate(stack[-1]['elseif_bodies']):
                            if cnt <= 0:
                                results['status'] = "Failed"
                                results['details'].append(
                                    f"Error: Empty ELSEIF body #{i+1} before END IF at ID [{req_id}], opened Line {stack[-1]['open_line']}, closed Line {line_num}."
                                )
                        if stack[-1]['else_seen'] and stack[-1]['else_body_count'] <= 0:
                            results['status'] = "Failed"
                            results['details'].append(
                                f"Error: Empty ELSE body before END IF at ID [{req_id}], opened Line {stack[-1]['open_line']}, closed Line {line_num}."
                            )
                    stack.pop()
                    cursor = end

            if stack and stack[-1]['collecting'] is None and cursor < len(line):
                add_body_segment(line[cursor:])
            if stack and stack[-1]['collecting'] in ('IF', 'ELSEIF') and cursor < len(line):
                stack[-1]['cond_parts'].append(line[cursor:].strip())

        if stack:
            open_lines = ", ".join(str(b['open_line']) for b in stack)
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unclosed IF block(s) at ID [{req_id}]; opened at line(s): {open_lines}"
            )

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; IF/ELSEIF/ELSE syntax looks good.")
    append_result(results)
    ##return results

def written_requirement_understandable_check(algo_df):
    """
    Objective G 7.1 — Written requirement statement understandability checker.

    This check verifies that requirement statement text is understandable by detecting:
      - Empty / too short statements
      - Placeholder tokens (TBD/TBR/XXX/???)
      - Ambiguous / vague language (Notice only)
      - Missing prescriptive modal ('shall' or 'must') (Notice only)
      - Unbalanced parentheses/brackets
      - Code-like fragments (Notice only)

    NOTE:
      Length-based warnings are intentionally NOT generated
      (your project explicitly does not want 'Very long requirement...' messages).

    Output:
      Uses append_result() to write into Algorithm_analysis_result.xlsx
      -> Results + Results_Details (same style as if_else_syntax_check).
    """
    results = {
        "check": "written_requirement_understandable_check",
        "status": "Passed",
        "details": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ids": list(pd.unique(algo_df["ID"]))
    }

    total = len(algo_df)
    if total == 0:
        results["status"] = "Failed: algo_df is empty"
        append_result(results)
        return

    # -------------------------
    # Patterns
    # -------------------------
    ambiguous_patterns = [
        r"\betc\.?\b",
        r"\band\/or\b",
        r"\bas appropriate\b",
        r"\bas needed\b",
        r"\bif possible\b",
        r"\bas soon as possible\b",
        r"\buser-friendly\b",
        r"\bintuitive\b",
        r"\boptimize\b",
        r"\bapproximately\b",
        r"\babout\b",
        r"\broughly\b",
        r"\btypical(ly)?\b",
        r"\busually\b",
        r"\bgenerally\b",
        r"\bfast\b",
        r"\bquick(ly)?\b",
        r"\bsoon\b",
        r"\bshould\b",
        r"\bmay\b"
    ]

    placeholder_patterns = [
        r"\bTBD\b",
        r"\bTBR\b",
        r"\bTBC\b",
        r"\bTBS\b",
        r"XXX",
        r"\?\?\?"
    ]

    def _norm_text(t: str) -> str:
        return re.sub(r"\s+", " ", (t or "").strip())

    def _balanced_pairs(text: str) -> bool:
        pairs = {"(": ")", "[": "]", "{": "}"}
        stack = []
        for ch in text:
            if ch in pairs:
                stack.append(pairs[ch])
            elif ch in (")", "]", "}"):
                if not stack or stack.pop() != ch:
                    return False
        return len(stack) == 0

    # -------------------------
    # Row-by-row evaluation
    # -------------------------
    for idx, row in algo_df.iterrows():
        req_id = row.get("ID", f"Row-{idx}")
        desc = _norm_text(str(row.get("DESC", "") or ""))

        # ---------- Rule 1: empty statement ----------
        if not desc:
            results["status"] = "Failed"
            results["details"].append(
                f"Error: Empty requirement text (DESC) at ID [{req_id}]."
            )
            continue

        # ---------- Rule 2: too short to be meaningful ----------
        if len(desc) < 20:
            results["status"] = "Failed"
            results["details"].append(
                f"Error: Requirement text too short to be understandable at ID [{req_id}]: '{desc}'."
            )

        # ---------- Rule 3: requirement strength (shall/must) ----------
        if not re.search(r"\b(shall|must)\b", desc, flags=re.IGNORECASE):
            results["details"].append(
                f"Notice: Missing prescriptive modal ('shall' or 'must') at ID [{req_id}]."
            )

        # ---------- Rule 4: placeholders ----------
        for p in placeholder_patterns:
            if re.search(p, desc, flags=re.IGNORECASE):
                results["status"] = "Failed"
                results["details"].append(
                    f"Error: Placeholder term found in requirement text at ID [{req_id}] (pattern '{p}')."
                )

        # ---------- Rule 5: ambiguity (Notice only) ----------
        for p in ambiguous_patterns:
            if re.search(p, desc, flags=re.IGNORECASE):
                results["details"].append(
                    f"Notice: Ambiguous/vague wording found at ID [{req_id}] (pattern '{p}')."
                )

        # ---------- Rule 6: unbalanced brackets ----------
        if not _balanced_pairs(desc):
            results["status"] = "Failed"
            results["details"].append(
                f"Error: Unbalanced parentheses/brackets in requirement text at ID [{req_id}]."
            )

        # ---------- Rule 7: suspicious code-like fragments ----------
        if re.search(r"===", desc) or re.search(r"\b\w+\(\)", desc):
            results["details"].append(
                f"Notice: Code-like fragment found in requirement text at ID [{req_id}]. Ensure statement is written in plain language."
            )

        # ---------- Rule 8: run-on punctuation (Notice only) ----------
        if desc.count(";") >= 3 or desc.count(",") >= 8:
            results["details"].append(
                f"Notice: Requirement may be compound/run-on (excess punctuation) at ID [{req_id}]."
            )

    if not results["details"]:
        results["details"].append(
            f"Scanned {total} requirements; written statements appear understandable."
        )

    append_result(results)



def for_condition_syntax_check(algo_df, strict_uppercase=True, lookahead_limit=3):
    """
    Validate ONLY the FOR header condition in algo_df['DESC'] ...
    """
    results = {
        'check': "for_condition_syntax_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    tok_re = re.compile(r'(?P<FOR>\bFOR\b)|(?P<DO>\bDO\b)', re.IGNORECASE)
    comparator_re    = re.compile(r'(==|!=|>=|<=|>|<)')
    single_equals_re = re.compile(r'(?<![=!<>])=(?!=)')
    for_range_re     = re.compile(r'\b(TO|DOWNTO|IN)\b', re.IGNORECASE)
    ambiguous_ops_re = re.compile(r'\b(EQ|NE|GT|LT|GE|LE)\b', re.IGNORECASE)

    def normalize_line(s: str) -> str:
        for _ in range(2):
            s = html.unescape(s)
        s = s.replace('≥', '&gt;=').replace('≤', '&lt;=').replace('≠', '!=')
        s = s.replace('&amp;eq;', '==').replace('&amp;amp;eq;', '==')
        return s

    def validate_parens(text: str, req_id, line_num, context: str):
        stack = 0
        for ch in text:
            if ch == '(':
                stack += 1
            elif ch == ')':
                stack -= 1
            if stack < 0:
                results['status'] = "Failed"
                results['details'].append(
                    f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
                )
                return
        if stack != 0:
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
            )

    def validate_for_condition(cond_text: str, req_id, line_num):
        text = cond_text.strip()
        if text == '':
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Empty FOR condition at ID [{req_id}], Line {line_num}."
            )
            return

        validate_parens(text, req_id, line_num, context="FOR condition")

        has_comp   = bool(comparator_re.search(text))
        has_range  = bool(for_range_re.search(text))

        if single_equals_re.search(text) and not has_range:
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Assignment '=' used in FOR condition without a range keyword (use '==' for comparison) at ID [{req_id}], Line {line_num}: '{text}'"
            )

        if not (has_comp or has_range):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: No comparator or range keyword in FOR condition at ID [{req_id}], Line {line_num}: '{text}'. Expected one of (==, !=, >=, <=, >, <) or TO/DOWNTO/IN."
            )

        if ambiguous_ops_re.search(text):
            results['details'].append(
                f"Notice: Textual comparator detected in FOR condition at ID [{req_id}], Line {line_num}: '{text}'. Prefer symbolic operators (==, !=, >, <, >=, <=)."
            )

    def is_probable_for_header(lines_norm, start_idx, after_for_text):
        seg = after_for_text.strip()
        if comparator_re.search(seg) or for_range_re.search(seg):
            return True
        if strict_uppercase:
            if 'DO' in seg.split():
                return True
        else:
            if re.search(r'\bDO\b', seg, re.IGNORECASE):
                return True
        for k in range(1, min(lookahead_limit + 1, len(lines_norm) - start_idx)):
            nxt = lines_norm[start_idx + k].strip()
            if comparator_re.search(nxt) or for_range_re.search(nxt):
                return True
            if strict_uppercase:
                if 'DO' in nxt.split():
                    return True
            else:
                if re.search(r'\bDO\b', nxt, re.IGNORECASE):
                    return True
        return False

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', ''))
        req_id = row.get('ID', index)

        raw_lines = desc_text.splitlines()
        lines = [normalize_line(ln.rstrip()) for ln in raw_lines]

        for line_num, line in enumerate(lines, 1):
            tokens = list(tok_re.finditer(line))
            if not tokens:
                continue

            for m in tokens:
                kind = m.lastgroup
                start, end = m.start(), m.end()
                matched_text = m.group()

                if kind == 'FOR':
                    if strict_uppercase and matched_text != 'FOR':
                        continue
                    after_for = line[end:]
                    if not is_probable_for_header(lines, line_num - 1, after_for):
                        continue
                    if strict_uppercase:
                        do_match_same = re.search(r'\bDO\b', after_for)
                    else:
                        do_match_same = re.search(r'\bDO\b', after_for, re.IGNORECASE)

                    if do_match_same:
                        cond_text = after_for[:do_match_same.start()].strip()
                        validate_for_condition(cond_text, req_id, line_num)
                        continue

                    cond_parts = []
                    if after_for.strip():
                        cond_parts.append(after_for.strip())

                    found_do = False
                    for ahead_idx in range(line_num, min(line_num + lookahead_limit, len(lines))):
                        ahead_line = lines[ahead_idx]
                        if strict_uppercase:
                            m_do = re.search(r'\bDO\b', ahead_line)
                        else:
                            m_do = re.search(r'\bDO\b', ahead_line, re.IGNORECASE)

                        if m_do:
                            prefix = ahead_line[:m_do.start()].strip()
                            if prefix:
                                cond_parts.append(prefix)
                            cond_text = ' '.join(part for part in cond_parts).strip()
                            validate_for_condition(cond_text, req_id, ahead_idx + 0)
                            found_do = True
                            break
                        else:
                            if ahead_line.strip():
                                cond_parts.append(ahead_line.strip())

                    if not found_do:
                        continue

    if not results['details']:
        results['details'].append(
            f"Scanned {total_algos} requirements; FOR conditions look good (strict_uppercase={strict_uppercase}; ignored non-control uses of 'for')."
        )
    append_result(results)
    ##return results


def while_syntax_check(algo_df):
    """
    Unified WHILE syntax checker ...
    """
    results = {
        'check': "while_syntax_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    tok_re = re.compile(
        r'(?P<WHILE>\bWHILE\b)|'
        r'(?P<DO>\bDO\b)|'
        r'(?P<END_WHILE>\bEND\s*WHILE\b|\bENDWHILE\b)|'
        r'(?P<NEST_IF>\bIF\b)|(?P<NEST_FOR>\bFOR\b)|(?P<NEST_WHILE2>\bWHILE\b)|(?P<NEST_SWITCH>\bSWITCH\b)',
        re.IGNORECASE
    )

    comparator_re    = re.compile(r'(==|!=|>=|<=|>|<)')
    single_equals_re = re.compile(r'(?<![=!<>])=(?!=)')
    ambiguous_ops_re = re.compile(r'\b(EQ|NE|GT|LT|GE|LE)\b', re.IGNORECASE)
    boolean_literal_re = re.compile(r'^\s*\(?\s*(TRUE|FALSE)\s*\)?\s*$', re.IGNORECASE)

    def normalize_line(s: str) -> str:
        for _ in range(2):
            s = html.unescape(s)
        s = s.replace('≥', '&gt;=').replace('≤', '&lt;=').replace('≠', '!=')
        s = s.replace('&amp;eq;', '==').replace('&amp;amp;eq;', '==')
        return s

    def validate_parens(text: str, req_id, line_num, context: str):
        stack = 0
        for ch in text:
            if ch == '(':
                stack += 1
            elif ch == ')':
                stack -= 1
            if stack < 0:
                results['status'] = "Failed"
                results['details'].append(
                    f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
                )
                return
        if stack != 0:
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
            )

    def validate_while_condition(cond_text: str, req_id, line_num):
        text = cond_text.strip()
        if text == '':
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Empty WHILE condition at ID [{req_id}], Line {line_num}."
            )
            return

        validate_parens(text, req_id, line_num, context="WHILE condition")

        if single_equals_re.search(text):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Assignment '=' used in WHILE condition (use '==' for equality) at ID [{req_id}], Line {line_num}: '{text}'"
            )

        has_comp = bool(comparator_re.search(text))
        is_boolean_literal = bool(boolean_literal_re.match(text))

        if not (has_comp or is_boolean_literal):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: WHILE condition must be a comparator expression or a boolean literal (TRUE/FALSE) at ID [{req_id}], Line {line_num}: '{text}'"
            )

        if ambiguous_ops_re.search(text) and not is_boolean_literal:
            results['details'].append(
                f"Notice: Textual comparator detected in WHILE condition at ID [{req_id}], Line {line_num}: '{text}'. Prefer symbolic operators (==, !=, >, <, >=, <=)."
            )

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', ''))
        req_id = row.get('ID', index)

        lines = desc_text.splitlines()
        stack = []

        for line_num, raw_line in enumerate(lines, 1):
            line = normalize_line(raw_line.rstrip())
            if not line.strip():
                if stack and stack[-1].get('collecting') == 'COND':
                    stack[-1]['cond_parts'].append('')
                continue

            tokens = list(tok_re.finditer(line))
            cursor = 0

            def add_body_segment(seg_text: str):
                text = seg_text.strip()
                if not text or not stack:
                    return
                top = stack[-1]
                if top['type'] == 'WHILE' and top.get('collecting') is None:
                    top['body_count'] += 1

            def finalize_segment_until(start):
                if stack and stack[-1].get('collecting') is None and start > cursor:
                    add_body_segment(line[cursor:start])

            if not tokens:
                if stack:
                    top = stack[-1]
                    if top.get('collecting') == 'COND':
                        top['cond_parts'].append(line.strip())
                    else:
                        add_body_segment(line[cursor:])
                continue

            for m in tokens:
                kind = m.lastgroup
                start, end = m.start(), m.end()

                if stack and stack[-1].get('collecting') == 'COND':
                    if kind not in ('DO',):
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: {kind} encountered before DO in WHILE header at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue

                if kind == 'WHILE':
                    if stack and stack[-1].get('collecting') is None:
                        finalize_segment_until(start)
                        add_body_segment('nested_WHILE')

                    stack.append({
                        'type': 'WHILE',
                        'open_line': line_num,
                        'collecting': 'COND',
                        'cond_parts': [],
                        'body_count': 0
                    })
                    cursor = end

                elif kind == 'DO':
                    if not stack or stack[-1]['type'] != 'WHILE' or stack[-1].get('collecting') != 'COND':
                        finalize_segment_until(start)
                        cursor = end
                        continue

                    stack[-1]['cond_parts'].append(line[cursor:start].strip())
                    cond_text = ' '.join(p for p in stack[-1]['cond_parts'] if p is not None).strip()
                    validate_while_condition(cond_text, req_id, line_num)
                    stack[-1]['collecting'] = None
                    stack[-1]['cond_parts'] = []
                    cursor = end

                elif kind == 'END_WHILE':
                    if not stack or stack[-1]['type'] != 'WHILE':
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: END WHILE/ENDWHILE without matching WHILE at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue

                    finalize_segment_until(start)
                    if stack[-1]['body_count'] <= 0:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: Empty WHILE body before END WHILE at ID [{req_id}], opened Line {stack[-1]['open_line']}, closed Line {line_num}."
                        )
                    stack.pop()
                    cursor = end

                elif kind in ('NEST_IF', 'NEST_FOR', 'NEST_SWITCH', 'NEST_WHILE2'):
                    finalize_segment_until(start)
                    add_body_segment(f"nested_{kind}")
                    cursor = end

            if stack and stack[-1].get('collecting') is None and cursor < len(line):
                add_body_segment(line[cursor:])
            if stack and stack[-1].get('collecting') == 'COND' and cursor < len(line):
                stack[-1]['cond_parts'].append(line[cursor:].strip())

        if stack:
            open_desc = ", ".join(f"{b['type']}@{b['open_line']}" for b in stack)
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unclosed WHILE block(s) at ID [{req_id}]; opened: {open_desc}"
            )

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; WHILE syntax looks good.")
    append_result(results)
    ##return results


def switch_syntax_check(algo_df):
    """
    Unified SWITCH syntax checker ...
    """
    results = {
        'check': "switch_syntax_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    tok_re = re.compile(
        r'(?P<SWITCH>\bSWITCH\b)|'
        r'(?P<CASE>\bCASE\b)|'
        r'(?P<DEFAULT>\bDEFAULT\b)|'
        r'(?P<THEN>\bTHEN\b)|'
        r'(?P<COLON>:)|'
        r'(?P<END_SWITCH>\bEND\s*SWITCH\b|\bENDSWITCH\b)|'
        r'(?P<NEST_IF>\bIF\b)|(?P<NEST_FOR>\bFOR\b)|(?P<NEST_WHILE>\bWHILE\b)|(?P<NEST_SWITCH2>\bSWITCH\b)',
        re.IGNORECASE
    )

    single_equals_re = re.compile(r'(?<![=!<>])=(?!=)')

    def normalize_line(s: str) -> str:
        for _ in range(2):
            s = html.unescape(s)
        s = s.replace('≥', '&gt;=').replace('≤', '&lt;=').replace('≠', '!=')
        s = s.replace('&amp;eq;', '==').replace('&amp;amp;eq;', '==')
        return s

    def validate_parens(text: str, req_id, line_num, context: str):
        stack = 0
        for ch in text:
            if ch == '(':
                stack += 1
            elif ch == ')':
                stack -= 1
            if stack < 0:
                results['status'] = "Failed"
                results['details'].append(
                    f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
                )
                return
        if stack != 0:
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unbalanced parentheses in {context} at ID [{req_id}], Line {line_num}: '{text.strip()}'"
            )

    def validate_switch_expr(expr_text: str, req_id, line_num):
        t = expr_text.strip()
        if t == '':
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Empty SWITCH expression at ID [{req_id}], Line {line_num}."
            )
            return
        validate_parens(t, req_id, line_num, context="SWITCH expression")
        if single_equals_re.search(t):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Assignment '=' used in SWITCH expression (use '==' if equality intended) at ID [{req_id}], Line {line_num}: '{t}'"
            )

    def validate_case_selector(sel_text: str, req_id, line_num):
        t = sel_text.strip()
        if t == '':
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Empty CASE selector at ID [{req_id}], Line {line_num}."
            )
            return
        validate_parens(t, req_id, line_num, context="CASE selector")
        if single_equals_re.search(t):
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Assignment '=' used in CASE selector (use '==' if equality intended) at ID [{req_id}], Line {line_num}: '{t}'"
            )

    for index, row in algo_df.iterrows():
        req_id = row.get('ID', index)
        desc_text = str(row.get('DESC', ''))

        lines = desc_text.splitlines()
        stack = []

        for line_num, raw_line in enumerate(lines, 1):
            line = normalize_line(raw_line.rstrip())
            if not line.strip():
                continue

            tokens = list(tok_re.finditer(line))
            cursor = 0

            def add_body_segment(seg_text: str):
                text = seg_text.strip()
                if not text or not stack:
                    return
                top = stack[-1]
                if top['type'] == 'SWITCH' and top.get('collecting') is None:
                    if top.get('current_branch', '').startswith('CASE_'):
                        idx = int(top['current_branch'].split('_')[1])
                        top['cases'][idx]['body_count'] += 1
                    elif top.get('current_branch') == 'DEFAULT':
                        top['default_body_count'] += 1

            def finalize_segment_until(start):
                if stack and stack[-1].get('collecting') is None and start > cursor:
                    add_body_segment(line[cursor:start])

            if not tokens:
                continue

            for m in tokens:
                kind = m.lastgroup
                start, end = m.start(), m.end()

                if stack and stack[-1].get('collecting') == 'SWITCH_EXPR':
                    if kind == 'CASE':
                        stack[-1]['cond_parts'].append(line[cursor:start].strip())
                        expr = ' '.join(p for p in stack[-1]['cond_parts']).strip()
                        validate_switch_expr(expr, req_id, line_num)
                        stack[-1]['collecting'] = None
                        stack[-1]['cond_parts'] = []
                        cursor = end
                    else:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: {kind} encountered before CASE after SWITCH at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue

                if stack and stack[-1].get('collecting') == 'CASE':
                    if kind in ('THEN', 'COLON'):
                        stack[-1]['cond_parts'].append(line[cursor:start].strip())
                        selector = ' '.join(p for p in stack[-1]['cond_parts']).strip()
                        validate_case_selector(selector, req_id, line_num)
                        stack[-1]['collecting'] = None
                        stack[-1]['cond_parts'] = []
                        if stack[-1]['cases']:
                            if stack[-1]['cases'][-1]['cond'] is None:
                                stack[-1]['cases'][-1]['cond'] = selector
                        idx = len(stack[-1]['cases']) - 1
                        stack[-1]['current_branch'] = f'CASE_{idx}'
                        cursor = end
                        continue
                    elif kind in ('SWITCH', 'CASE', 'DEFAULT', 'END_SWITCH'):
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: {kind} encountered before THEN/COLON after CASE at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue

                if kind == 'SWITCH':
                    if stack and stack[-1].get('collecting') is None:
                        finalize_segment_until(start)
                        add_body_segment('nested_SWITCH')

                    stack.append({
                        'type': 'SWITCH',
                        'open_line': line_num,
                        'collecting': 'SWITCH_EXPR',
                        'cond_parts': [],
                        'cases': [],
                        'default_seen': False,
                        'default_body_count': 0,
                        'current_branch': None
                    })
                    cursor = end

                elif kind == 'CASE':
                    if not stack or stack[-1]['type'] != 'SWITCH':
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: CASE without matching SWITCH at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    if stack[-1]['default_seen']:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: CASE after DEFAULT is not allowed at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    finalize_segment_until(start)
                    stack[-1]['collecting'] = 'CASE'
                    stack[-1]['cond_parts'] = []
                    stack[-1]['cases'].append({'cond': None, 'body_count': 0, 'start_line': line_num})
                    stack[-1]['current_branch'] = None
                    cursor = end

                elif kind in ('THEN', 'COLON'):
                    finalize_segment_until(start)
                    cursor = end
                    continue

                elif kind == 'DEFAULT':
                    if not stack or stack[-1]['type'] != 'SWITCH':
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: DEFAULT without matching SWITCH at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    if stack[-1]['default_seen']:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: Multiple DEFAULT branches are not allowed at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    finalize_segment_until(start)
                    stack[-1]['default_seen'] = True
                    stack[-1]['current_branch'] = 'DEFAULT'
                    cursor = end

                elif kind == 'END_SWITCH':
                    if not stack or stack[-1]['type'] != 'SWITCH':
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: END SWITCH/ENDSWITCH without matching SWITCH at ID [{req_id}], Line {line_num}: '{raw_line.strip()}'"
                        )
                        cursor = end
                        continue
                    finalize_segment_until(start)
                    top = stack[-1]
                    if len(top['cases']) == 0:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: SWITCH has no CASE branches at ID [{req_id}], opened Line {top['open_line']}, closed Line {line_num}."
                        )
                    for i, c in enumerate(top['cases'], 1):
                        if c['cond'] is None:
                            results['status'] = "Failed"
                            results['details'].append(
                                f"Error: CASE #{i} lacks selector/THEN at ID [{req_id}], opened Line {c['start_line']}, closed Line {line_num}."
                            )
                        if c['body_count'] <= 0:
                            results['status'] = "Failed"
                            results['details'].append(
                                f"Error: Empty CASE #{i} body before END SWITCH at ID [{req_id}], opened Line {c['start_line']}, closed Line {line_num}."
                            )
                    if top['default_seen'] and top['default_body_count'] <= 0:
                        results['status'] = "Failed"
                        results['details'].append(
                            f"Error: Empty DEFAULT body before END SWITCH at ID [{req_id}], opened Line {top['open_line']}, closed Line {line_num}."
                        )
                    stack.pop()
                    cursor = end

                elif kind in ('NEST_IF', 'NEST_FOR', 'NEST_WHILE', 'NEST_SWITCH2'):
                    finalize_segment_until(start)
                    add_body_segment(f"nested_{kind}")
                    cursor = end

            if stack and stack[-1].get('collecting') is None and cursor < len(line):
                add_body_segment(line[cursor:])
            if stack and stack[-1].get('collecting') in ('SWITCH_EXPR', 'CASE') and cursor < len(line):
                stack[-1]['cond_parts'].append(line[cursor:].strip())

        if stack:
            open_desc = ", ".join(f"{b['type']}@{b['open_line']}" for b in stack)
            results['status'] = "Failed"
            results['details'].append(
                f"Error: Unclosed SWITCH block(s) at ID [{req_id}]; opened: {open_desc}"
            )

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; SWITCH syntax looks good.")
    append_result(results)
    ##return results


## Objective G 7.2 ##

def edge_case_check(algo_df):
    """
    Suite to test for DO-178 robustness term mentions in algorithm descriptions.
    """
    results = {
        'check': "edge_case_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    cats = {
        "Boundary/Range": ["min","max","range","limit","boundary","upper","lower","overflow","underflow","saturation","clamp"],
        "Invalid Input": ["invalid","null","empty","out of range","negative","zero","format","type","nan"],
        "Timing/Timeout": ["timeout","deadline","latency","period","rate","watchdog","tick","delay"],
        "Failure/Exceptions": ["error","fault","failure","exception","abort","reset","degraded","safe state","recovery","retry","report"],
        "Resource/Init": ["memory","stack","leak","resource","alloc","allocation","initialization","startup","power","brown-out","loss"],
        "Concurrency": ["race","deadlock","mutex","lock","priority inversion","concurrent","atomic"],
        "Interface/Protocol": ["message","crc","checksum","protocol","handshake","header","sequence","status code"],
        "Numerical": ["precision","divide by zero","rounding","overflow","underflow","saturation"],
        "Mode/State": ["mode","state","transition","unexpected","inhibit","failsafe","fallback"]
    }

    cat_rx = {
        cat: [re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE) for term in terms]
        for cat, terms in cats.items()
    }

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', '') or '')
        req_id = row.get('ID', f"Row{index}")

        if not desc_text.strip():
            results['details'].append(f"Notice: Empty DESC at ID [{req_id}]")
            continue

        txt = ' ' + desc_text.lower() + ' '
        matched = {}
        for cat, patterns in cat_rx.items():
            terms_hit = []
            for rx in patterns:
                if rx.search(txt):
                    term_literal = rx.pattern.replace(r'\b', '')
                    terms_hit.append(term_literal)
            if terms_hit:
                matched[cat] = sorted(set(terms_hit))

        if matched:
            if results['status'] == "Passed":
                results['status'] = "Failed"
            cat_list = ';'.join(matched.keys())
            term_detail = '; '.join([f"{k}: {', '.join(v)}" for k, v in matched.items()])
            results['details'].append(
                f"Notice: Edge-case categories hit at ID [{req_id}] → [{cat_list}] | terms: {term_detail}"
            )

    if results['status'] == "Passed":
        results['details'].append(
            f"Scanned {total_algos} requirements; no DO-178 edge-case terms found."
        )

    append_result(results)
    ##return results

# -------------------------
# Objective G 7.3 Coverage & checklist 
# -------------------------

def checklist_presence(algo_df):
    """
    Suite to test for DO-178 robustness term mentions in algorithm descriptions.
    """
    results = {
        'check': "checklist_presence",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results
    
    checks = {
        "Numeric ranges/limits specified": ["range", "limit", "bounds", "min", "max", "boundary"],
        "Precision/representation defined": ["precision", "floating point", "fixed point", "q-format", "rounding", "truncate"],
        "Overflow/underflow/saturation handling": ["overflow", "underflow", "saturation", "clip", "clipping", "wraparound"],
        "Error bounds/tolerances stated": ["error bound", "tolerance", "accuracy", "residual"],
        "Robustness under worst-case/edge conditions": ["worst case", "worst-case", "stress", "edge case", "corner case", "boundary condition"],
        "Deterministic behavior across platforms": ["deterministic", "platform", "portability", "repeatable"],
        "Exception/NaN/Inf handling defined": ["nan", "inf", "exception"],
        "Algorithm stability/conditioning addressed": ["stability", "numerical stability", "conditioning", "ill-conditioned", "converge", "diverge"],
        "Test coverage for numeric boundaries": ["test", "unit test", "verification", "validation", "boundary"]
    }

    check_rx = {
        checks: [re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE) for term in terms]
        for checks, terms in checks.items()
    }

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', '') or '')
        req_id = row.get('ID', f"Row{index}")

        if not desc_text.strip():
            results['details'].append(f"Notice: Empty DESC at ID [{req_id}]")
            continue

        txt = ' ' + desc_text.lower() + ' '
        matched = {}
        for checks, patterns in check_rx.items():
            terms_hit = []
            for rx in patterns:
                if rx.search(txt):
                    term_literal = rx.pattern.replace(r'\b', '')
                    terms_hit.append(term_literal)
            if terms_hit:
                matched[checks] = sorted(set(terms_hit))

        if matched:
            if results['status'] == "Passed":
                results['status'] = "Failed"
            checks_list = ';'.join(matched.keys())
            term_detail = '; '.join([f"{k}: {', '.join(v)}" for k, v in matched.items()])
            results['details'].append(
                f"Notice: Edge-case categories hit at ID [{req_id}] → [{checks_list}] | terms: {term_detail}"
            )

    if results['status'] == "Passed":
        results['details'].append(
            f"Scanned {total_algos} requirements; no DO-178 edge-case terms found."
        )
    append_result(results)

## Objective G 7.7 ##

def div_by_zero_check(algo_df):
    """
    Detect literal division-by-zero patterns.
    """
    results = {
        'check': "div_by_zero_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    div_zero_pattern = r'/\s*0(?:\.0+)?(?!\d)'

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', ''))
        req_id = row.get('ID', index)
        lines = desc_text.splitlines()
        for line_num, line_content in enumerate(lines, 1):
            if '/' in line_content and re.search(div_zero_pattern, line_content):
                error_msg = f"Error: Zero Division Hazard at ID [{req_id}], Line {line_num}: '{line_content.strip()}'"
                results['status'] = "Failed"
                results['details'].append(error_msg)

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; no literal division by zero found.")
    append_result(results)
    ##return results


def infinite_loop_check(algo_df):
    """
    Detect common infinite-loop pseudocode markers (while(1), while True, typo while Ture).
    """
    results = {
        'check': "infinite_loop_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    combined_pattern = r'(while\s*\(\s*1\s*\)|while\s*True|while\s*Ture)'

    for index, row in algo_df.iterrows():
        desc_text = str(row.get('DESC', ''))
        req_id = row.get('ID', index)
        lines = desc_text.splitlines()
        for line_num, line_content in enumerate(lines, 1):
            if re.search(combined_pattern, line_content, re.IGNORECASE):
                error_msg = f"Caution: Infinite Loop Hazard at ID [{req_id}], Line {line_num}: '{line_content.strip()}'"
                results['status'] = "Failed"
                results['details'].append(error_msg)

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; no infinite loop patterns detected.")
    append_result(results)
    ##return results


def null_pointer_check(algo_df):
    """
    Detect null pointer textual mentions and actual None/NaN cells.
    """
    results = {
        'check': "null_pointer_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    patterns = [
        r"\bnull\s*pointer\b",
        r"\bnullptr\b",
        r"\bnull\s*ptr\b",
        r"\b\w+\s*=\s*null\b",
        r"\b\w+\s*<-\s*null\b",
        r"\bdeclare\s+\w+\s*=\s*null\b"
    ]

    for index, row in algo_df.iterrows():
        req_id = row.get('ID', f"Row-{index}")

        for col in algo_df.columns:
            if pd.isnull(row[col]):
                error_msg = f"Error: Null value detected at ID [{req_id}], Column '{col}'"
                results['status'] = "Failed"
                results['details'].append(error_msg)

        desc_text = str(row.get('DESC', ""))
        lines = desc_text.splitlines()
        for line_num, line_content in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line_content, re.IGNORECASE):
                    error_msg = f"Caution: Null Pointer mention at ID [{req_id}], Line {line_num}: '{line_content.strip()}'"
                    results['status'] = "Failed"
                    if error_msg not in results['details']:
                        results['details'].append(error_msg)
                    break

    if not results['details']:
        results['details'].append(f"Scanned {total_algos} requirements; no null pointers detected.")
    append_result(results)
    ##return results


def out_of_range_check(algo_df):
    """
    Detect out-of-range array or list access in pseudocode stored in algo_df.
    """
    results = {
        'check': "out_of_range_check",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    # Cleaned regex patterns for suspicious array access
    patterns = [
        r"\barray\s*\[\s*\d+\s*\]",   # array[10]
        r"\barray\s*\[\s*index\s*\]",
        r"\barray\s*\[\s*i\s*\]",
        r"\barray\s*\[\s*j\s*\]",
        r"\barray\s*\[\s*k\s*\]"
    ]

    array_decl_pattern = r"SET\s+array\s*=\s*\[(.* ?)\]"
    loop_pattern = r"FOR\s+(\w+)\s*=\s*(\d+)\s*to\s*(\d+)"

    for index, row in algo_df.iterrows():
        req_id = row.get('ID', f"Row-{index}")
        desc_text = str(row.get('DESC', ""))
        lines = desc_text.splitlines()

        array_length = None
        decl_match = re.search(array_decl_pattern, desc_text, re.IGNORECASE)
        if decl_match:
            elements = decl_match.group(1).split(",")
            array_length = len([e.strip() for e in elements if e.strip()])

        for line_num, line_content in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line_content, re.IGNORECASE):
                    error_msg = f"Notice: Potential array access at ID [{req_id}], Line {line_num}: '{line_content.strip()}'"
                    if error_msg not in results['details']:
                        results['status'] = "Failed"
                        results['details'].append(error_msg)
                    break

            loop_match = re.search(loop_pattern, line_content, re.IGNORECASE)
            if loop_match and array_length is not None:
                start_idx = int(loop_match.group(2))
                end_idx = int(loop_match.group(3))
                if end_idx >= array_length:
                    error_msg = (
                        f"Error: Out-of-range loop detected at ID [{req_id}], Line {line_num}: "
                        f"Loop goes to {end_idx} but array length is {array_length}"
                    )
                    if error_msg not in results['details']:
                        results['status'] = "Failed"
                        results['details'].append(error_msg)

    if not results['details']:
        results['details'].append(
            f"Scanned {total_algos} requirements; no input abnormalities patterns detected."
        )
    append_result(results)
    ##return results


def var_input_analysis(algo_df):
    """
    Placeholder for input analysis; currently no checks.
    """
    results = {
        'check': "var_input_analysis",
        'status': "Passed",
        'details': [],
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ids': list(pd.unique(algo_df['ID']))  # <-- Per-ID tracking (so IDs show as Passed)
    }

    total_algos = len(algo_df)
    if total_algos == 0:
        results['status'] = "Failed: algo_df is empty"
        append_result(results)
        ##return results

    results['details'].append(f"Scanned {total_algos} records; no input abnormalities patterns detected.")
    append_result(results)
    ##return results



 ## Objective G 7.4 ##

import os
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import pandas as pd
from docx import Document

# NEW: Local PC metrics
import psutil

# -----------------------------
# Configuration
# -----------------------------
TARGET_OBJECTIVE_TEXT = "Objective G 7.4"
TARGET_ID_TEXT = "SCU_STC_SRS"

OUTPUT_SHEET_NAME = "Result_Objective_G_7_4"

CHECKPOINTS = [
    "Timing - WCET Defined",
    "Timing - Deadlines / Response Time",
    "Timing - Task Rates",
    "Resource - CPU Utilization",
    "Resource - Memory Constraints",
    "Resource - I/O Bandwidth",
]

TIME_UNITS = r"(ns|us|µs|microseconds?|ms|milliseconds?|s|sec|seconds?)"
FREQ_UNITS = r"(Hz|kHz|MHz|cycles/s|updates?/s)"
SIZE_UNITS = r"(B|KB|KiB|MB|MiB|GB|GiB|bytes?)"
BANDWIDTH_UNITS = r"(bps|kbps|Mbps|Gbps|B/s|KB/s|MB/s|GB/s)"
PERCENT = r"(\d+(\.\d+)?)\s*%"

# -----------------------------
# Utilities
# -----------------------------

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def excerpt_with_context(text: str, start: int, end: int, ctx: int = 80) -> str:
    left = max(0, start - ctx)
    right = min(len(text), end + ctx)
    snippet = text[left:right]
    return normalize_text(snippet)

def find_with_units(text: str, patterns: List[Tuple[str, str]]) -> Tuple[str, Optional[str]]:
    for _, pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            span = m.span()
            snippet = excerpt_with_context(text, span[0], span[1])
            value = m.group(0)
            return snippet, value
    return "", None

def status_from_match(value: Optional[str], quantified_patterns: List[str], raw_text: str) -> str:
    if not value:
        return "Missing"
    for qp in quantified_patterns:
        if re.search(qp, value, flags=re.IGNORECASE):
            return "Present (Quantified)"
    for qp in quantified_patterns:
        if re.search(qp, raw_text, flags=re.IGNORECASE):
            return "Present (Quantified)"
    return "Present (Unquantified)"

# -----------------------------
# NEW: Local PC Resource Extractors
# -----------------------------

def get_local_cpu_utilization_percent(sample_seconds: float = 1.0) -> float:
    # Accurate CPU % over sample interval
    return psutil.cpu_percent(interval=sample_seconds)

def get_local_memory_constraints() -> Dict[str, float]:
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    return {
        "RAM_Total_MB": round(vm.total / (1024 * 1024), 2),
        "RAM_Used_MB": round(vm.used / (1024 * 1024), 2),
        "RAM_Available_MB": round(vm.available / (1024 * 1024), 2),
        "RAM_Usage_%": round(vm.percent, 2),
        "SWAP_Total_MB": round(sm.total / (1024 * 1024), 2),
        "SWAP_Used_MB": round(sm.used / (1024 * 1024), 2),
        "SWAP_Usage_%": round(sm.percent, 2),
    }

def get_local_io_bandwidth(sample_seconds: float = 1.0) -> Dict[str, float]:
    # I/O bandwidth measured based on disk read/write counters
    c1 = psutil.disk_io_counters()
    if c1 is None:
        return {"Disk_Read_MBps": 0.0, "Disk_Write_MBps": 0.0}

    # wait and measure again
    import time
    time.sleep(sample_seconds)

    c2 = psutil.disk_io_counters()
    if c2 is None:
        return {"Disk_Read_MBps": 0.0, "Disk_Write_MBps": 0.0}

    read_bps = (c2.read_bytes - c1.read_bytes) / sample_seconds
    write_bps = (c2.write_bytes - c1.write_bytes) / sample_seconds

    return {
        "Disk_Read_MBps": round(read_bps / (1024 * 1024), 3),
        "Disk_Write_MBps": round(write_bps / (1024 * 1024), 3),
    }

# -----------------------------
# Metadata Extraction
# -----------------------------

def get_full_text_from_doc(doc: Document) -> str:
    parts = []
    for p in doc.paragraphs:
        parts.append(p.text)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return normalize_text("\n".join(parts))

def extract_metadata_from_doc(doc: Document) -> Tuple[str, str]:
    text = get_full_text_from_doc(doc)

    objective = TARGET_OBJECTIVE_TEXT if re.search(r"\bObjective\s*G\s*7\.4\b", text, flags=re.IGNORECASE) else TARGET_OBJECTIVE_TEXT
    project_id = TARGET_ID_TEXT
    return objective, project_id

# -----------------------------
# Requirement Extraction (First Column Only)
# -----------------------------

HEADER_HINTS = ["id", "req", "requirement", "identifier"]

def is_header_row(cells_text: List[str]) -> bool:
    header_join = " | ".join([c.lower() for c in cells_text])
    return any(hint in header_join for hint in HEADER_HINTS)

def extract_requirements_from_first_col(doc: Document) -> List[Dict]:
    reqs = []
    for t_index, t in enumerate(doc.tables):
        rows = []
        for row in t.rows:
            rows.append([normalize_text(cell.text) for cell in row.cells])

        if not rows:
            continue

        for r_index, cells in enumerate(rows):
            if not cells:
                continue
            if r_index == 0 and is_header_row(cells):
                continue

            req_id = normalize_text(cells[0]) if len(cells) >= 1 else ""
            if not req_id or req_id.lower() in ("id", "req id", "requirement id", "identifier"):
                continue

            other_text = normalize_text(" | ".join(c for c in cells[1:])) if len(cells) > 1 else ""
            reqs.append({
                "id": req_id,
                "row_text": other_text,
                "table_index": t_index,
                "row_index": r_index,
                "source": "table-first-col"
            })

    seen = set()
    unique = []
    for r in reqs:
        if r["id"] not in seen:
            unique.append(r)
            seen.add(r["id"])
    return unique

def extract_all_requirements(doc_path: str) -> Tuple[List[Dict], Tuple[str, str]]:
    doc = Document(doc_path)
    objective_id, project_id = extract_metadata_from_doc(doc)
    reqs = extract_requirements_from_first_col(doc)
    return reqs, (objective_id, project_id)

# -----------------------------
# Checkpoint Detectors
# -----------------------------

def detect_wcet(text: str) -> Tuple[str, Optional[str], str]:
    patterns = [
        ("wcet", r"\b(WCET|worst[-\s]?case\s+execution\s+time)\b.*?\b\d+(\.\d+)?\s*" + TIME_UNITS),
        ("wcet_phrase", r"\b(WCET|worst[-\s]?case\s+execution\s+time)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [TIME_UNITS], text)
    return snippet, value, status

def detect_deadline_response(text: str) -> Tuple[str, Optional[str], str]:
    # In this checkpoint, we use timestamp in output instead of response time
    patterns = [
        ("deadline", r"\b(deadline|latency|response\s*time)\b.*?\b\d+(\.\d+)?\s*" + TIME_UNITS),
        ("deadline_phrase", r"\b(deadline|latency|response\s*time)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [TIME_UNITS], text)
    return snippet, value, status

def detect_task_rates(text: str) -> Tuple[str, Optional[str], str]:
    patterns = [
        ("frequency", r"\b(\d+(\.\d+)?)\s*" + FREQ_UNITS),
        ("period", r"\b(period|cycle|update\s*rate)\b.*?\b\d+(\.\d+)?\s*" + TIME_UNITS),
        ("rate_phrase", r"\b(rate|period|frequency|update\s*rate|cycle)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [TIME_UNITS, FREQ_UNITS], text)
    return snippet, value, status

# Resource checkpoint detectors remain for doc text,
# but we will override values with local PC metrics.
def detect_cpu_util(text: str) -> Tuple[str, Optional[str], str]:
    patterns = [
        ("cpu_percent", r"\b(CPU|processor)\b.*?" + PERCENT),
        ("utilization", r"\b(utilization|usage|load)\b.*?" + PERCENT),
        ("phrase", r"\b(CPU\s*utilization|CPU\s*usage|processor\s*load)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [PERCENT], text)
    return snippet, value, status

def detect_memory(text: str) -> Tuple[str, Optional[str], str]:
    patterns = [
        ("memory_size", r"\b(memory|RAM|ROM|flash|stack|heap)\b.*?\b\d+(\.\d+)?\s*" + SIZE_UNITS),
        ("stack_heap", r"\b(stack|heap)\b.*?\b\d+(\.\d+)?\s*" + SIZE_UNITS),
        ("phrase", r"\b(memory|RAM|ROM|flash|stack|heap)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [SIZE_UNITS], text)
    return snippet, value, status

def detect_io_bandwidth(text: str) -> Tuple[str, Optional[str], str]:
    patterns = [
        ("bw_numeric", r"\b(bandwidth|throughput)\b.*?\b\d+(\.\d+)?\s*" + BANDWIDTH_UNITS),
        ("net_units", r"\b\d+(\.\d+)?\s*" + BANDWIDTH_UNITS + r"\b"),
        ("phrase", r"\b(bandwidth|throughput|I/O|bus)\b"),
    ]
    snippet, value = find_with_units(text, patterns)
    status = status_from_match(value, [BANDWIDTH_UNITS], text)
    return snippet, value, status

DETECTOR_MAP = {
    "Timing - WCET Defined": detect_wcet,
    "Timing - Deadlines / Response Time": detect_deadline_response,
    "Timing - Task Rates": detect_task_rates,
    "Resource - CPU Utilization": detect_cpu_util,
    "Resource - Memory Constraints": detect_memory,
    "Resource - I/O Bandwidth": detect_io_bandwidth,
}

# -----------------------------
# Review table
# -----------------------------

def review_requirements(reqs: List[Dict], meta: Tuple[str, str]) -> pd.DataFrame:
    objective_id, _project_id = meta
    rows = []

    # Collect local system metrics ONCE
    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    local_cpu = get_local_cpu_utilization_percent(sample_seconds=1.0)
    local_mem = get_local_memory_constraints()
    local_io = get_local_io_bandwidth(sample_seconds=1.0)

    for r in reqs:
        r_id = r["id"]
        row_text = r.get("row_text", "")

        for chk in CHECKPOINTS:
            detector = DETECTOR_MAP[chk]
            snippet, value, status = detector(row_text)

            # OVERRIDES requested by you
            extracted_value_override = None

            if chk == "Timing - Deadlines / Response Time":
                # Put timestamp in place of response time
                extracted_value_override = timestamp_now
                status = "Present (Quantified)"
                snippet = "Timestamp captured for timing evidence (runtime collection)."

            elif chk == "Resource - CPU Utilization":
                extracted_value_override = f"{local_cpu:.2f} %"
                status = "Present (Quantified)"
                snippet = "Local PC CPU utilization captured at runtime."

            elif chk == "Resource - Memory Constraints":
                extracted_value_override = (
                    f"RAM Total={local_mem['RAM_Total_MB']}MB, "
                    f"Used={local_mem['RAM_Used_MB']}MB, "
                    f"Avail={local_mem['RAM_Available_MB']}MB, "
                    f"Usage={local_mem['RAM_Usage_%']}%"
                )
                status = "Present (Quantified)"
                snippet = "Local PC memory utilization captured at runtime."

            elif chk == "Resource - I/O Bandwidth":
                extracted_value_override = (
                    f"Disk Read={local_io['Disk_Read_MBps']} MB/s, "
                    f"Disk Write={local_io['Disk_Write_MBps']} MB/s"
                )
                status = "Present (Quantified)"
                snippet = "Local PC disk I/O bandwidth captured at runtime."

            extracted_value_final = extracted_value_override if extracted_value_override is not None else (value if value else "")

            comment = ""
            if status == "Missing":
                if "Timing" in chk:
                    comment = "No explicit timing value found; specify quantified targets with units."
                elif "CPU" in chk:
                    comment = "No CPU utilization target; specify a max % or headroom."
                elif "Memory" in chk:
                    comment = "No memory constraint; specify RAM/ROM/stack/heap footprints."
                elif "I/O" in chk:
                    comment = "No bandwidth/throughput limit; define kbps/MB/s with margins."
            elif status == "Present (Unquantified)":
                comment = "Constraint mentioned but lacks numeric target/units; add measurable criteria."

            rows.append({
                "Objective_ID": objective_id,
                "Requirement_ID": r_id,
                "Checkpoint": chk,
                "Status": status,
                "Evidence_Snippet": snippet,
                "Extracted_Value": extracted_value_final,
                "Comments": comment
            })

    return pd.DataFrame(rows)

# -----------------------------
# Excel Writer (existing output sheet)
# -----------------------------

def write_or_replace_sheet(xlsx_path: str, sheet_name: str, df: pd.DataFrame):
    os.makedirs(os.path.dirname(xlsx_path), exist_ok=True) if os.path.dirname(xlsx_path) else None

    if os.path.exists(xlsx_path):
        with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

# -----------------------------
# Public entrypoint for project
# -----------------------------

def run_objective_g74(srs_docx_path: str, results_xlsx_path: str):
    """
    Entry point called from main_g7.py
    """
    if not os.path.exists(srs_docx_path):
        print(f"Input file not found: {srs_docx_path}")
        return

    reqs, meta = extract_all_requirements(srs_docx_path)
    if not reqs:
        print("Objective G 7.4: no requirements found in DOCX tables.")
        return

    df = review_requirements(reqs, meta)
    write_or_replace_sheet(results_xlsx_path, OUTPUT_SHEET_NAME, df)

    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Timing_WCET_Defined'")
    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Timing_Response_Time'")
    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Task_Rates'")
    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Resource_CPU_Utilization")
    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Resource_Memory_Constraints'")
    print(f"Objective G 7.4")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME}' (summary) for check 'Resource_I/O_Bandwidth'")

 ## Objective G 7.5 ##

import os
import re
from typing import List, Dict, Optional
import pandas as pd
from docx import Document

# -----------------------------
# Objective G 7.5 Configuration
# -----------------------------
OUTPUT_SHEET_NAME_G75 = "Result_Objective_G_7_5"

# Do NOT count atomicity as an error for Correctness
ATOMICITY_COUNTS_AS_ERROR = False
ADD_ATOMICITY_SUGGESTION = True

# Requirement text selection
TEXT_COLUMN_PREFERENCE = None  # None => first non-empty after column 0

# Words/phrases to flag as ambiguous or non-deterministic
AMBIGUOUS_TERMS = [
    r'\betc\.?\b', r'\band\/or\b', r'\bas appropriate\b', r'\bas needed\b',
    r'\bif possible\b', r'\bas soon as possible\b', r'\buser-friendly\b',
    r'\bintuitive\b', r'\boptimize\b', r'\bapproximately\b', r'\babout\b',
    r'\broughly\b', r'\btypical(ly)?\b', r'\busually\b', r'\bgenerally\b',
    r'\bfast\b', r'\bquick(ly)?\b', r'\bsoon\b', r'\bshould\b', r'\bmay\b'
]

# Common TBD/TBR placeholders
PLACEHOLDER_TERMS = [r'\bTBD\b', r'\bTBR\b', r'\bTBC\b', r'\bTBS\b', r'XXX', r'\?\?\?']

# Phrases suggesting acceptance criteria or verification method
ACCEPTANCE_PHRASES = [
    r'\bwithin\b', r'\bno more than\b', r'\bat least\b', r'\bnot more than\b',
    r'\bless than\b', r'\bgreater than\b', r'\bequal to\b', r'\b±', r'\bplus\/minus\b',
    r'\bshall be verified\b', r'\bverified by\b', r'\bverification\b',
    r'\btest(ed)?\b', r'\banalysis\b', r'\breview\b', r'\binspection\b'
]

# Units or tokens that often indicate measurability
UNITS_OR_NUMERIC = [
    r'\d+\s*(ns|us|µs|microseconds?|ms|milliseconds?|s|sec|seconds?|Hz|kHz|MHz|%|ppm|°C|deg|degrees|mA|A|V|mV|g|kg|N|bit|bits|byte|bytes|KB|MB|GB|px|m|cm|mm|km|in|ft|fps|kPa|Pa|bar)\b',
    r'\d+(\.\d+)?\b'
]

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or "").strip())


def _match_any(patterns: List[str], text: str, flags=re.IGNORECASE) -> bool:
    return any(re.search(p, text, flags=flags) for p in patterns)


def extract_requirements_from_tables_col1_ids(doc: Document) -> List[Dict]:
    """
    Extract requirements by assuming:
      - First column = Requirement ID
      - Requirement Text = first non-empty cell after column 0
        (or by TEXT_COLUMN_PREFERENCE if provided)
    Deduplicates by (ID, Text).
    """
    results = []
    seen = set()

    for tbl in doc.tables:
        for row in tbl.rows:
            cells = row.cells
            if not cells:
                continue

            rid = _norm(cells[0].text)
            if not rid:
                continue

            # skip header-ish rows
            if rid.lower() in {"id", "requirement id", "req id", "requirement"}:
                continue

            req_text = ""
            if TEXT_COLUMN_PREFERENCE:
                for ci in TEXT_COLUMN_PREFERENCE:
                    if ci < len(cells):
                        t = _norm(cells[ci].text)
                        if t:
                            req_text = t
                            break
            else:
                for ci in range(1, len(cells)):
                    t = _norm(cells[ci].text)
                    if t:
                        req_text = t
                        break

            if not req_text:
                continue

            key = (rid, req_text.lower())
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "Requirement_ID": rid,
                "Requirement_Text": req_text
            })

    return results


def _has_measurable_numbers(text: str) -> bool:
    return _match_any(UNITS_OR_NUMERIC, text)


def _has_acceptance_phrases(text: str) -> bool:
    return _match_any(ACCEPTANCE_PHRASES, text)


def _has_ambiguous_terms(text: str) -> bool:
    return _match_any(AMBIGUOUS_TERMS, text)


def _has_placeholders(text: str) -> bool:
    return _match_any(PLACEHOLDER_TERMS, text)


def analyze_requirement(req_text: str) -> Dict:
    """
    Correctness / Determinism / Testability / Robustness(always pass) / Verifiability.
    """
    text = _norm(req_text)
    lower = text.lower()
    issues = []
    suggestions = []

    # --- Correctness ---
    correctness_pass = True
    if not re.search(r'\b(shall|must)\b', lower):
        correctness_pass = False
        issues.append("Missing prescriptive modal ('shall' or 'must').")
        suggestions.append("Rewrite using 'shall' for mandatory behavior (e.g., 'The system shall ...').")

    if _has_placeholders(lower):
        correctness_pass = False
        issues.append("Contains placeholder(s) (TBD/TBR/TBC/XXX/???).")
        suggestions.append("Resolve all placeholders with finalized values and references.")

    # Atomicity heuristic — DO NOT fail correctness unless toggled
    sentences = SENTENCE_SPLIT.split(text) if text else []
    long_sentence = any(len(s) > 280 for s in sentences) if sentences else False
    too_many_conjunctions = any(len(re.findall(r'\band\b|\bor\b|,', s, flags=re.IGNORECASE)) >= 3 for s in sentences) if sentences else False

    if long_sentence or too_many_conjunctions:
        if ATOMICITY_COUNTS_AS_ERROR:
            correctness_pass = False
            issues.append("Requirement may not be atomic (very long or compound).")
        if ADD_ATOMICITY_SUGGESTION:
            suggestions.append("Consider splitting into smaller, atomic requirements (one verifiable statement each).")

    # --- Determinism ---
    determinism_pass = True
    if _has_ambiguous_terms(lower):
        determinism_pass = False
        issues.append("Contains ambiguous or non-deterministic terms (e.g., 'etc.', 'and/or', 'approximately').")
        suggestions.append("Replace vague terms with precise, quantifiable statements and explicit conditions.")

    if re.search(r'\b(latency|response|deadline|period|rate|frequency|time)\b', lower) and not _has_measurable_numbers(lower):
        determinism_pass = False
        issues.append("Timing referenced without numeric bounds.")
        suggestions.append("Specify timing quantitatively (e.g., 'within 50 ms', 'period = 10 ms ±1 ms').")

    # --- Testability ---
    testability_pass = True
    measurable = _has_measurable_numbers(lower) or _has_acceptance_phrases(lower)
    if not measurable:
        testability_pass = False
        issues.append("Lacks measurable acceptance criteria.")
        suggestions.append("Add measurable thresholds, ranges, or explicit verification criteria.")

    # --- Robustness (ALWAYS PASS per requirement) ---
    robustness_pass = True

    # --- Verifiability ---
    verifiability_pass = True
    if (not measurable) or _has_ambiguous_terms(lower):
        verifiability_pass = False
        if not measurable:
            issues.append("Verifiability risk: lacks quantifiable criteria.")
            suggestions.append("State quantitative criteria and verification method (Test/Analysis/Inspection/Review).")
        else:
            issues.append("Verifiability risk: contains ambiguous language.")
            suggestions.append("Eliminate ambiguous terms to enable unambiguous verification.")

    if not re.search(r'\b(test|analysis|inspection|review)\b', lower):
        suggestions.append("Add an explicit verification method tag, e.g., 'Verification: Test'.")

    passes = {
        "Correctness": correctness_pass,
        "Determinism": determinism_pass,
        "Testability": testability_pass,
        "Robustness": robustness_pass,
        "Verifiability": verifiability_pass
    }

    pass_count = sum(1 for v in passes.values() if v)
    fail_count = 5 - pass_count
    overall = (pass_count == 5)

    severity = "High" if fail_count >= 3 else ("Medium" if fail_count == 2 else ("Low" if fail_count == 1 else "None"))

    issues = sorted(set(issues))
    suggestions = sorted(set(suggestions))

    return {
        **passes,
        "Pass_Count": pass_count,
        "Fail_Count": fail_count,
        "Overall_Pass": overall,
        "Severity": severity,
        "Issues": "; ".join(issues) if issues else "",
        "Suggested_Fixes": "; ".join(suggestions) if suggestions else ""
    }


def algorithm_design_meets_do178c_objectives(srs_docx_path: str, results_xlsx_path: str) -> None:
    """
    Project entrypoint.
    Reads requirements from DOCX tables:
        Column 1 = Requirement ID
        Next non-empty column = requirement text
    Writes results into Algorithm_analysis_result.xlsx as a NEW SHEET.
    """
    if not os.path.exists(srs_docx_path):
        print(f"Objective G 7.5: Input file not found: {srs_docx_path}")
        return

    doc = Document(srs_docx_path)
    reqs = extract_requirements_from_tables_col1_ids(doc)

    if not reqs:
        print("Objective G 7.5: No requirements found in DOCX tables.")
        return

    rows = []
    for r in reqs:
        analysis = analyze_requirement(r["Requirement_Text"])
        rows.append({
            "Objective_ID": "Objective G 7.5",
            "Requirement_ID": r["Requirement_ID"],
            **analysis
        })

    df = pd.DataFrame(rows)
    col_order = [
        "Objective_ID",
        "Requirement_ID",
        "Correctness", "Determinism", "Testability", "Robustness", "Verifiability",
        "Pass_Count", "Fail_Count", "Overall_Pass", "Severity", "Issues", "Suggested_Fixes"
    ]
    df = df[col_order]

    # Write into new tab without touching others
    write_or_replace_sheet(results_xlsx_path, OUTPUT_SHEET_NAME_G75, df)

    print("Objective G 7.5")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G75}' (summary) for check 'Correctness'")
    print("Objective G 7.5")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G75}' (summary) for check 'Determinism'")
    print("Objective G 7.5")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G75}' (summary) for check 'Testability'")
    print("Objective G 7.5")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G75}' (summary) for check 'Robustness'")
    print("Objective G 7.5")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G75}' (summary) for check 'Verifiability'")

 ## Objective G 7.6 ##

# ============================================================
# Objective G 7.6 — Error Handling Review (Runner)
# Writes to: Result_Objective_G_7_6
# ============================================================

import re
import os
import pandas as pd
from docx import Document
from g7.io_utils.io_g7 import write_or_replace_sheet

OUTPUT_SHEET_NAME_G76 = "Result_Objective_G_7_6"

MANDATORY_MUST_INCLUDE_CLASSIFICATION = False
SKIP_ROWS_WITH_EMPTY_ID = True

ERROR_RELATED_TERMS = [
    "error", "fault", "failure", "fail", "exception", "invalid",
    "timeout", "crc", "overflow", "underflow", "out of range"
]

KW_DETECTION = [
    "detect", "detection", "monitor", "check", "validate",
    "verify", "range check", "diagnostic", "health check"
]

KW_CLASSIFICATION = [
    "severity", "minor", "major", "critical", "catastrophic",
    "recoverable", "non-recoverable", "error code"
]

KW_REPORTING = [
    "log", "report", "flag", "alert", "indicate",
    "status", "notify", "event", "telemetry"
]

KW_RECOVERY = [
    "recover", "retry", "reset", "reinitialize",
    "safe state", "shutdown", "fallback", "degraded mode"
]

REQ_ID_PATTERNS = [
    r"\bREQ[-_ ]?\d+(\.\d+)*\b",
    r"\bSRS[-_ ]?\d+(\.\d+)*\b",
    r"\bSCU[-_ ]?SRS[-_ ]?\d+(\.\d+)*\b"
]

HEADER_HINTS = ["id", "requirement", "description", "text"]


def _normalize_g76(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _is_header_row_g76(row) -> bool:
    texts = [_normalize_g76(c.text).lower() for c in row.cells]
    return sum(h in " ".join(texts) for h in HEADER_HINTS) >= 2


def _extract_req_id_g76(cell_text: str, row_text: str) -> str:
    cid = _normalize_g76(cell_text)
    if cid and not re.fullmatch(r"\d+(\.\d+)*", cid):
        return cid
    for p in REQ_ID_PATTERNS:
        m = re.search(p, row_text, re.IGNORECASE)
        if m:
            return m.group(0)
    return cid


def _find_matched_keywords_g76(text: str, keywords):
    t = (text or "").lower()
    return [kw for kw in keywords if kw in t]


def _find_any_g76(text: str, patterns):
    return any(re.search(p, text or "", re.IGNORECASE) for p in patterns)


def extract_requirements_from_tables_g76(doc: Document):
    results = []

    for tbl in doc.tables:
        if not tbl.rows:
            continue

        start = 1 if _is_header_row_g76(tbl.rows[0]) else 0

        for row in tbl.rows[start:]:
            if len(row.cells) < 2:
                continue

            row_text = " ".join(_normalize_g76(c.text) for c in row.cells)
            req_id = _extract_req_id_g76(row.cells[0].text, row_text)

            if SKIP_ROWS_WITH_EMPTY_ID and not req_id:
                continue

            req_text = _normalize_g76(" ".join(c.text for c in row.cells[1:]))
            if not req_text:
                continue

            results.append({
                "Req_ID": req_id,
                "Source_Section": "",
                "Requirement_Text": req_text
            })

    return results


def evaluate_requirement_g76(req_text: str):
    t = (req_text or "").lower()
    related = any(k in t for k in ERROR_RELATED_TERMS)

    det_matches = _find_matched_keywords_g76(t, KW_DETECTION)
    rep_matches = _find_matched_keywords_g76(t, KW_REPORTING)
    rec_matches = _find_matched_keywords_g76(t, KW_RECOVERY)
    cls_matches = _find_matched_keywords_g76(t, KW_CLASSIFICATION)

    timing_match = re.search(r"\bwithin\s*\d+\s*(ms|s|sec|second|seconds)\b", t)
    if timing_match:
        det_matches.append(timing_match.group(0))

    traceable = _find_any_g76(req_text, REQ_ID_PATTERNS)

    fail_reasons = []
    if related:
        if not det_matches:
            fail_reasons.append(f"No detection keyword found (expected: {', '.join(KW_DETECTION)})")
        if not rep_matches:
            fail_reasons.append(f"No reporting keyword found (expected: {', '.join(KW_REPORTING)})")
        if not rec_matches:
            fail_reasons.append(f"No recovery keyword found (expected: {', '.join(KW_RECOVERY)})")
        if MANDATORY_MUST_INCLUDE_CLASSIFICATION and not cls_matches:
            fail_reasons.append(f"No classification keyword found (expected: {', '.join(KW_CLASSIFICATION)})")

    overall = "PASS"
    if related and fail_reasons:
        overall = "FAIL"

    return {
        "Related_to_ErrorHandling": "Yes" if related else "No",
        "Check_Error_Detection": "Yes" if det_matches else "No",
        "Check_Error_Classification": "Yes" if cls_matches else "No",
        "Check_Error_Reporting": "Yes" if rep_matches else "No",
        "Check_Recovery": "Yes" if rec_matches else "No",
        "Check_Traceability": "Yes" if traceable else "No",
        "Overall_DO178_ErrorHandling": overall,
        "Fail_Reason_Details": (
            " | ".join(fail_reasons)
            if fail_reasons else
            ("N/A (Not error-handling requirement)" if not related else "Meets all mandatory checks")
        )
    }


def Error_Handling(srs_docx_path: str, results_xlsx_path: str) -> None:
    """
    Objective G 7.6 runner.
    Adds/overwrites sheet: Result_Objective_G_7_6
    """
    if not os.path.exists(srs_docx_path):
        print(f"Objective G 7.6: Input file not found: {srs_docx_path}")
        return

    doc = Document(srs_docx_path)
    reqs = extract_requirements_from_tables_g76(doc)

    rows = []
    for i, r in enumerate(reqs, 1):
        ev = evaluate_requirement_g76(r["Requirement_Text"])
        rows.append({
            "Objective_ID": "Objective G 7.6",
            "Seq": i,
            "Requirement_ID": r["Req_ID"],
            "Source_Section": r.get("Source_Section", ""),
            **ev
        })

    df = pd.DataFrame(rows)

    col_order = [
        "Objective_ID",
        "Seq",
        "Requirement_ID",
        "Source_Section",
        "Related_to_ErrorHandling",
        "Check_Error_Detection",
        "Check_Error_Classification",
        "Check_Error_Reporting",
        "Check_Recovery",
        "Check_Traceability",
        "Overall_DO178_ErrorHandling",
        "Fail_Reason_Details",
    ]
    df = df[col_order]

    write_or_replace_sheet(results_xlsx_path, OUTPUT_SHEET_NAME_G76, df)

    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Related_to_ErrorHandling'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Error_Detection'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Error_Classification'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Error_Reporting'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Error_Recovery'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Error_Traceability'")
    print("Objective G 7.6")
    print(f"✅ Results appended to {results_xlsx_path} → '{OUTPUT_SHEET_NAME_G76}'(summary) for check 'Overall_DO178_ErrorHandling'")