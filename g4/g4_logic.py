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


# ---------- G4.1 / G4.2 ----------

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


# ---------- G4.3 ----------

def extract_verification_method(text):
    match = re.search(G4Config.VERIFICATION_METHOD_REGEX, text, re.IGNORECASE)
    return match.group(1).capitalize() if match else "NA"


# ---------- G4.5 ----------

def check_g45(text):
    return "PASS" if re.search(G4Config.MANDATORY_WORD_REGEX, text, re.IGNORECASE) else "FAIL"
