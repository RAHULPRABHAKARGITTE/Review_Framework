import re
from config import G5Config


def first_two_sentences(text: str) -> str:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(parts[:2])


def check_format_and_structure(requirements):
    findings = []
    seen_ids = set()

    for req in requirements:
        raw_id = req.get("raw_id")
        req_id = req.get("id")
        text = req.get("text", "").strip()

        if not raw_id:
            findings.append((
                G5Config.MISSING_ID_LABEL,
                f"G_5.5-FS-01: Missing requirement ID\nPreview: {first_two_sentences(text)}"
            ))
            continue

        if req_id is None:
            findings.append((
                raw_id,
                "G_5.5-FS-02: Invalid requirement ID format"
            ))
            continue

        if req_id in seen_ids:
            findings.append((
                req_id,
                "G_5.5-FS-03: Duplicate requirement ID"
            ))
            continue

        seen_ids.add(req_id)

        if not text:
            findings.append((
                req_id,
                "G_5.5-FS-04: Requirement text missing"
            ))

    return findings
