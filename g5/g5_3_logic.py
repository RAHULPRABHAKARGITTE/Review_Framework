import re

def check_project_guidelines(requirements, keywords):
    findings = []
    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()
        if not req_id or not text:
            continue

        text_lower = text.lower()

        if "shall" not in text_lower:
            findings.append((req_id, "G_5.3-PG-01: Requirement does not contain 'shall'"))

        if text_lower.count("shall") > 1:
            findings.append((req_id, "G_5.3-PG-02: Multiple 'shall' statements found"))

        if not text_lower.startswith(keywords["subject_prefix"]):
            findings.append((req_id, "G_5.3-PG-03: Requirement does not start with 'The STC Program shall'"))

        for word in keywords["forbidden_modals"]:
            if re.search(rf"\b{word}\b", text_lower):
                findings.append((req_id, f"G_5.3-PG-04: Forbidden modal verb used ('{word}')"))

        for phrase in keywords["forbidden_vague"]:
            if phrase in text_lower:
                findings.append((req_id, f"G_5.3-PG-05: Forbidden vague term used ('{phrase}')"))

        for pattern in keywords["passive_patterns"]:
            if re.search(pattern, text_lower):
                findings.append((req_id, "G_5.3-PG-06: Possible passive voice usage"))

    return findings