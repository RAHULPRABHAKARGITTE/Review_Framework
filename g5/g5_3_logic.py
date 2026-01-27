import re

SUBJECT_PREFIX = "the stc program shall"

FORBIDDEN_MODALS = ["must", "will", "should", "may"]
FORBIDDEN_VAGUE = [
    "etc", "as appropriate", "as required",
    "as needed", "adequate", "sufficient"
]

PASSIVE_PATTERNS = [
    r"shall be provided",
    r"shall be handled",
    r"shall be performed",
    r"shall be supported"
]


def check_project_guidelines(requirements):
    findings = []

    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()

        if not req_id or not text:
            continue

        t = text.lower()

        if "shall" not in t:
            findings.append((req_id, "G_5.3-PG-01: Missing 'shall'"))

        if t.count("shall") > 1:
            findings.append((req_id, "G_5.3-PG-02: Multiple 'shall' statements"))

        if not t.startswith(SUBJECT_PREFIX):
            findings.append((req_id, "G_5.3-PG-03: Incorrect requirement subject"))

        for m in FORBIDDEN_MODALS:
            if re.search(rf"\b{m}\b", t):
                findings.append((req_id, f"G_5.3-PG-04: Forbidden modal '{m}'"))

        for v in FORBIDDEN_VAGUE:
            if v in t:
                findings.append((req_id, f"G_5.3-PG-05: Vague term '{v}'"))

        for p in PASSIVE_PATTERNS:
            if re.search(p, t):
                findings.append((req_id, "G_5.3-PG-06: Passive voice detected"))

    return findings
