from config import G1Config
import re

NOTE_START_PATTERN = re.compile(
    r"\bnote\s*\d*\s*:",
    re.IGNORECASE
)

def strip_notes(text: str) -> str:
    """
    Removes NOTE / NOTE 1: / NOTE2: and everything after it.
    Used ONLY for G1.2 clarity checks.
    """
    match = NOTE_START_PATTERN.search(text)
    if match:
        return text[:match.start()]
    return text



def check_g1_2(hlr_req):
    """
    G1.2 – Clarity & Standalone Check
    This does NOT compare system vs software.
    It checks whether the SOFTWARE requirement is clear and standalone.
    """

    raw_text = hlr_req.get("TEXT", "")
    text = strip_notes(raw_text).lower()


    findings = []

    # ---- Ambiguous references
    for ref in G1Config.G1_2_AMBIGUOUS_REFERENCES:
        if ref in text:
            findings.append(f"Ambiguous reference '{ref}' makes requirement non-standalone.")

    # ---- Vague terms
    for term in G1Config.G1_2_VAGUE_TERMS:
        if term in text:
            findings.append(f"Vague term '{term}' reduces requirement clarity.")

    if findings:
        return G1Config.FAIL, " | ".join(findings)

    return G1Config.PASS, ""