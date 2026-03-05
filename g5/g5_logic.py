from collections import defaultdict
from g5.g5_1_logic import check_safety
from g5.g5_2_logic import check_single_functionality
from g5.g5_3_logic import check_project_guidelines
from g5.g5_4_logic import check_ambiguous_words
from g5.g5_5_logic import check_format_and_structure

def run_g5_checks(requirements, keywords):
    g5_1_results = check_safety(requirements, keywords)
    g5_2_results = check_single_functionality(requirements, keywords)
    g5_3_results = check_project_guidelines(requirements, keywords)
    g5_4_results = check_ambiguous_words(requirements, keywords)
    g5_5_results = check_format_and_structure(requirements)

    all_findings = g5_1_results + g5_2_results + g5_3_results + g5_4_results + g5_5_results

    findings_by_req = defaultdict(list)
    for req_id, issue in all_findings:
        findings_by_req[req_id].append(issue)

    g5_results = {req_id: {"overall": "FAIL" if issues else "PASS", "issues": issues}
                  for req_id, issues in findings_by_req.items()}

    return g5_results, all_findings