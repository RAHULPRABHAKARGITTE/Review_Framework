import re

def is_safety_related(text_lower, keywords):
    return any(keyword in text_lower for keyword in keywords["safety_keywords"])

def check_safety(requirements, keywords):
    findings = []
    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()
        if not req_id or not text:
            continue

        text_lower = text.lower()
        if not is_safety_related(text_lower, keywords):
            continue

        if not any(word in text_lower for word in keywords["mitigation_keywords"]):
            findings.append((req_id, "G_5.1-SR-01: No mitigation action found."))

        if not re.search(r"\bshall\s+\w+", text_lower):
            findings.append((req_id, "G_5.1-SR-02: Missing system behavior."))

        for phrase in keywords["forbidden_vague"]:
            if phrase in text_lower:
                findings.append((req_id, f"G_5.1-SR-03: Vague safety wording detected ('{phrase}')"))

        for modal in keywords["forbidden_modals"]:
            if re.search(rf"\b{modal}\b", text_lower):
                findings.append((req_id, f"G_5.1-SR-04: Weak modal verb used ('{modal}')"))

    return findings