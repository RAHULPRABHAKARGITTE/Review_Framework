from collections import defaultdict

from g5.g5_1_logic import check_safety
from g5.g5_2_logic import check_single_functionality
from g5.g5_3_logic import check_project_guidelines
from g5.g5_4_logic import check_ambiguous_words
from g5.g5_5_logic import check_format_and_structure


def run_g5_checks(requirements):
    """
    G5 Aggregator

    - Calls all G5 sub-guideline logic modules
    - Collects and merges findings
    - Returns:
        1) g5_results: per-requirement PASS/FAIL + issues
        2) all_findings: flat list for reporting
    """

    # -------------------------
    # Run sub-guidelines
    # -------------------------
    g51 = check_safety(requirements)
    g52 = check_single_functionality(requirements)
    g53 = check_project_guidelines(requirements)
    g54 = check_ambiguous_words(requirements)
    g55 = check_format_and_structure(requirements)

    # -------------------------
    # Merge all findings
    # -------------------------
    all_findings = g51 + g52 + g53 + g54 + g55

    # -------------------------
    # Group by Requirement ID
    # -------------------------
    findings_by_req = defaultdict(list)
    for req_id, issue in all_findings:
        findings_by_req[req_id].append(issue)

    # -------------------------
    # Build final G5 decision
    # -------------------------
    g5_results = {}

    for req_id, issues in findings_by_req.items():
        g5_results[req_id] = {
            "overall": "FAIL" if issues else "PASS",
            "issues": issues
        }

    return g5_results, all_findings
