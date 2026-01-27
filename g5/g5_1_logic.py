import re
from config import G5Config


def is_safety_related(text_lower: str) -> bool:
    return any(k in text_lower for k in G5Config.SAFETY_KEYWORDS)


def check_safety(requirements):
    findings = []

    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()

        if not req_id or not text:
            continue

        text_lower = text.lower()

        if not is_safety_related(text_lower):
            continue

        # SR-01: mitigation missing
        if not any(k in text_lower for k in G5Config.MITIGATION_KEYWORDS):
            findings.append((
                req_id,
                "G_5.1-SR-01: Safety requirement lacks mitigation action"
            ))

        # SR-02: missing system behavior
        if not re.search(r"\bshall\s+\w+", text_lower):
            findings.append((
                req_id,
                "G_5.1-SR-02: Missing 'shall <action>' system behavior"
            ))

        # SR-03: vague phrases
        for phrase in G5Config.FORBIDDEN_SAFETY_PHRASES:
            if phrase in text_lower:
                findings.append((
                    req_id,
                    f"G_5.1-SR-03: Vague safety wording ('{phrase}')"
                ))

        # SR-04: forbidden modals
        for modal in G5Config.FORBIDDEN_MODALS:
            if re.search(rf"\b{modal}\b", text_lower):
                findings.append((
                    req_id,
                    f"G_5.1-SR-04: Forbidden modal verb used ('{modal}')"
                ))

    return findings
