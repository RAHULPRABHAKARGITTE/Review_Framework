# g2_4_7_logic.py

import re
from config import G2Config

REQ_ID_REGEX = re.compile(G2Config.REQ_ID_PATTERN, re.IGNORECASE)

# =============================
# Extract Requirements
# =============================
def extract_requirements(full_text):
    requirements = []
    current_id = None
    buffer = []

    for line in full_text.splitlines():
        line = line.strip()
        if not line:
            continue

        match = REQ_ID_REGEX.search(line)

        if match:
            if current_id:
                requirements.append((current_id, "\n".join(buffer)))
            current_id = match.group(1)
            buffer = [line]
        elif current_id:
            buffer.append(line)

    if current_id:
        requirements.append((current_id, "\n".join(buffer)))

    return requirements

# =============================
# Checkpoint 1 – Derived Review
# =============================
def check_derived_requirement(text):
    text_l = text.lower()

    is_derived = any(k in text_l for k in G2Config.DERIVED_KEYWORDS)

    justification_present = False
    justification_valid = False
    justification_appropriate = "Not Applicable"

    for word in G2Config.JUSTIFICATION_WORDS:
        pattern = rf"\b{word}\s*:"
        match = re.search(pattern, text_l)

        if match:
            justification_present = True
            justification_text = text[match.end():].strip()
            justification_text_l = justification_text.lower()

            # Meaningful length check
            if len(justification_text) > 40:
                justification_valid = True

                # Check reasoning indicators
                if any(r in justification_text_l for r in G2Config.JUSTIFICATION_REASONING_WORDS):
                    justification_appropriate = "Yes"
                else:
                    justification_appropriate = "No"
            else:
                justification_appropriate = "No"
            break

    if is_derived:
        if justification_present and justification_valid:
            return "Derived", "Yes", justification_appropriate
        else:
            return "Derived", "No", "No"
    else:
        return "Not Derived", "Not Applicable", "Not Applicable"

# =============================
# Checkpoint 2 – Sufficient Detail
# =============================
def check_sufficient_detail(text):
    text_l = text.lower()

    has_mandatory = any(w in text_l for w in G2Config.MANDATORY_WORDS)
    has_condition = any(w in text_l for w in G2Config.CONDITION_WORDS)
    has_number = re.search(G2Config.NUMBER_PATTERN, text)
    has_unit = re.search(G2Config.G2_4_7_UNIT_PATTERN, text)

    if has_mandatory and has_condition and has_number and has_unit:
        return "PASS", "Requirement is measurable and verifiable."
    else:
        return "FAIL", "Requirement lacks measurable or verifiable detail."
