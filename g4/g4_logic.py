import re
from config import G4Config

def contains_keyword(text, keywords):
    text = text.lower()
    return any(k in text for k in keywords)


# ---------- TYPE CLASSIFICATION ----------

def is_register_requirement(text):
    return contains_keyword(text, G4Config.REGISTER_KEYWORDS)


def is_communication_requirement(text):
    return contains_keyword(text, G4Config.COMMUNICATION_KEYWORDS)


def is_fault_requirement(text):
    return contains_keyword(text, G4Config.FAULT_KEYWORDS)


def is_io_requirement(text):
    return contains_keyword(text, G4Config.IO_KEYWORDS)


def is_functional_requirement(text):
    return contains_keyword(text, G4Config.FUNCTIONAL_KEYWORDS)


# ================= G 4.1 =================

def check_g41_testability(text):
    if is_register_requirement(text):
        return "Analysis"

    if (
        is_communication_requirement(text)
        or is_fault_requirement(text)
        or is_io_requirement(text)
        or is_functional_requirement(text)
    ):
        return "Test"

    return "Manual"

# ================= G 4.2 =================
# Acceptance Criteria Check

def check_g42_acceptance_criteria(text):
    text_l = text.lower()

    has_mandatory = re.search(r"\bshall\b|\bmust\b", text_l)
    has_condition = re.search(r"\bif\b|\bwhen\b|\bafter\b|\bwithin\b", text_l)
    has_number = re.search(r"\d+", text)
    has_unit = re.search(
        r"\b(ms|µs|us|sec|seconds|%|hz|rpm|v|a|°c|bytes|0x[0-9a-fA-F]+)\b",
        text,
        re.IGNORECASE,
    )

    missing = []

    if not has_mandatory:
        missing.append("Missing mandatory word (shall/must)")
    if not has_condition:
        missing.append("Missing condition (if/when/after/within)")
    if not has_number:
        missing.append("Missing numeric value")
    if not has_unit:
        missing.append("Missing measurable unit")

    if not missing:
        return "PASS", "NA"
    else:
        return "FAIL", " | ".join(missing)

# ================= G4.3 =================

def extract_verification_method(text):
    match = re.search(G4Config.VERIFICATION_METHOD_REGEX, text, re.IGNORECASE)
    return match.group(1).capitalize() if match else "Blank"


# ================= G4.5 =================

def check_g45(text):
    return "PASS" if re.search(G4Config.MANDATORY_WORD_REGEX, text, re.IGNORECASE) else "FAIL"
