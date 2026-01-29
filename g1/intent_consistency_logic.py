from config import G1Config


def extract_intents(text: str) -> set:
    """
    Extracts high-level behavioral intents from requirement text.
    """
    if not text:
        return set()

    text = text.lower()
    found = set()

    for intent, keywords in G1Config.INTENT_GROUPS.items():
        for kw in keywords:
            if kw in text:
                found.add(intent)
                break

    return found

def get_intent_debug(sys_req: dict, hlr_req: dict):
    """
    Returns extracted intent sets for debug / audit visibility.
    """
    sys_text = sys_req.get("TEXT", "")
    hlr_text = hlr_req.get("TEXT", "")

    return {
        "SYS_INTENTS": ", ".join(sorted(extract_intents(sys_text))),
        "HLR_INTENTS": ", ".join(sorted(extract_intents(hlr_text))),
    }


def detect_intent_conflict(sys_intents: set, sw_intents: set) -> str | None:
    """
    Returns a reason string if intent drift is detected.
    """

    if "FAILSAFE" in sys_intents and "RECOVERY" in sw_intents:
        return "System enforces failsafe behavior while software introduces recovery."

    if "RECOVERY" in sys_intents and "FAILSAFE" in sw_intents:
        return "System allows recovery while software enforces failsafe behavior."

    if "MONITORING" in sys_intents and "CONTROL" in sw_intents:
        return "System only specifies monitoring, but software performs control."

    if "CONTROL" in sys_intents and "MONITORING" in sw_intents:
        return "System requires control action, but software only monitors."

    if "MANDATORY" in sys_intents and "PERMISSIVE" in sw_intents:
        return "System mandates behavior, but software makes it optional."

    return None


def check_intent_consistency(sys_req: dict, hlr_req: dict):
    """
    G1 semantic intent consistency check.
    (This is NOT G2.)
    """

    sys_text = sys_req.get("TEXT", "")
    hlr_text = hlr_req.get("TEXT", "")

    if not sys_text or not hlr_text:
        return G1Config.FAIL, "Missing requirement text for intent comparison."

    sys_intents = extract_intents(sys_text)
    hlr_intents = extract_intents(hlr_text)

    conflict = detect_intent_conflict(sys_intents, hlr_intents)

    if conflict:
        return G1Config.FAIL, conflict

    return G1Config.PASS, ""
