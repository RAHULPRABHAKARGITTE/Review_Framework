from config import G1Config
import re
from decimal import Decimal, InvalidOperation

# ============================================================
# BASIC EXTRACTORS
# ============================================================

# def extract_failsafe_level(text: str):
#     m = re.search(r"failsafe level\s*(\d+)", (text or "").lower())
#     return m.group(1) if m else None


FAILSAFE_LEVEL_RE = re.compile(
    r"failsafe(?:\s*[-_]*\s*level|_level)\s*[-_ ]*([0-9]+)",
    re.IGNORECASE
)

def extract_failsafe_level(text: str):
    m = FAILSAFE_LEVEL_RE.search(text or "")
    return m.group(1) if m else None


# ============================================================
# MONITOR EXTRACTION (STRICT BLOCK)
# ============================================================

MONITOR_LIST_TRIGGER_PATTERN = re.compile(
    r"(any\s+one\s+of\s+the\s+following\s+monitors|following\s+monitors|monitors\s*:)",
    re.IGNORECASE
)

STOP_SECTION_PATTERN = re.compile(
    r"^\s*(note\b|object type\b|source\b|verification method\b|ref\b|references\b)",
    re.IGNORECASE
)

BULLET_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")

def extract_monitor_list_block(text: str) -> set:
    """
    Extract monitor items from structured list only.
    Stronger than keyword match.
    """
    text = text or ""
    lines = text.splitlines()
    start_idx = None

    for i, line in enumerate(lines):
        if MONITOR_LIST_TRIGGER_PATTERN.search(line):
            start_idx = i
            break

    if start_idx is None:
        return set()

    buffer = []
    for j in range(start_idx + 1, len(lines)):
        ln = lines[j].strip()

        if not ln:
            if buffer:
                break
            continue

        if STOP_SECTION_PATTERN.match(ln):
            break

        # hard stop if paragraph turns into metadata
        if "object type" in ln.lower() or "verification method" in ln.lower():
            break

        buffer.append(ln)

    if not buffer:
        return set()

    found = set()

    bullet_lines = [ln for ln in buffer if BULLET_PATTERN.match(ln)]
    if bullet_lines:
        for ln in bullet_lines:
            item = BULLET_PATTERN.sub("", ln).strip(" ,;.")
            if len(item) >= 4:
                found.add(item.lower())
        return found

    # Comma list: join only buffer text
    joined = " ".join(buffer)
    parts = re.split(r"[;,]", joined)

    for p in parts:
        item = p.strip(" ,;.")
        if len(item) >= 4:
            found.add(item.lower())

    return found


def extract_monitor_set(text: str) -> set:
    structured = extract_monitor_list_block(text)
    if structured:
        return structured

    # fallback keyword scan
    found = set()
    t = (text or "").lower()
    for k in G1Config.MONITOR_KEYWORDS:
        if k in t:
            found.add(k)
    return found


# ============================================================
# TABLE NORMALIZATION
# ============================================================

def normalize_table(table_text: str) -> set:
    if not table_text:
        return set()

    rows = []
    for line in table_text.splitlines():
        line = line.strip()
        if "|" in line:
            rows.append(" | ".join(part.strip() for part in line.split("|") if part.strip()))
    return set(rows)


# ============================================================
# ARINC LABEL HANDLING (ROBUST)
# ============================================================

ARINC_LABEL_PATTERN = re.compile(r"\b0?[0-7]{3}\b")
ARINC_TABLE_HINT = re.compile(r"\blabel\b", re.IGNORECASE)

def extract_arinc_labels_anywhere(text: str, table_text: str) -> set:
    """
    Extract possible ARINC labels from BOTH free text + table text.
    Do NOT require keyword ARINC.
    """
    labels = set()
    blob = f"{text or ''}\n{table_text or ''}"
    for m in ARINC_LABEL_PATTERN.findall(blob):
        labels.add(m)
    return labels

def looks_like_arinc(table_text: str) -> bool:
    return bool(table_text and ARINC_TABLE_HINT.search(table_text))


# ============================================================
# NUMERIC EXTRACTION
# ============================================================

TIME_PATTERN = re.compile(
    r"(?P<sign>[-+])?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>ms|s)\b",
    re.IGNORECASE
)

def extract_time_values(text: str) -> set:
    values = set()
    text = text or ""

    for m in TIME_PATTERN.finditer(text):
        sign = m.group("sign") or ""
        num_s = m.group("num")
        unit = m.group("unit").lower()

        try:
            num = Decimal(sign + num_s)
        except InvalidOperation:
            continue

        if unit == "s":
            num = num * Decimal("1000")

        num = num.normalize()
        values.add(str(num))

    return values


EXPRESSION_NUMBER_PATTERN = re.compile(
    r"(?:(?:[-+]?\d+\.\d+(?:e[-+]?\d+)?)|(?:[-+]?\d+(?:e[-+]?\d+)?))",
    re.IGNORECASE
)

def extract_expression_numbers(text: str) -> set:
    nums = set()
    text = text or ""

    for raw in EXPRESSION_NUMBER_PATTERN.findall(text):
        raw = raw.strip().lower().replace("+", "")
        try:
            nums.add(str(Decimal(raw).normalize()))
        except Exception:
            nums.add(raw)

    return nums


def format_numeric_drift(sys_nums: set, hlr_nums: set) -> str:
    missing = sorted(sys_nums - hlr_nums)
    extra = sorted(hlr_nums - sys_nums)

    parts = []
    if missing:
        parts.append(f"Missing in software: {', '.join(missing)}")
    if extra:
        parts.append(f"Extra in software: {', '.join(extra)}")
    return "; ".join(parts)


# ============================================================
# BOOLEAN EXTRACTION (SSM + DEFAULT)
# ============================================================

# Wider: handles "!= Normal Operation", "not equal", "NOT set to"
SSM_PATTERN = re.compile(
    r"SSM\s+data\s+(?:is\s+)?(?:(not)\s+)?set\s+to\s+\"?Normal\s+Operation\"?",
    re.IGNORECASE
)

SSM_NEQ_PATTERN = re.compile(
    r"SSM\s+data\s+(?:!=|not\s+equal\s+to|not\s+set\s+to)\s+\"?Normal\s+Operation\"?",
    re.IGNORECASE
)

def extract_ssm_condition(text: str):
    """
    True  = set to Normal Operation
    False = NOT set to Normal Operation
    None  = not found
    """
    text = text or ""
    if SSM_NEQ_PATTERN.search(text):
        return False

    m = SSM_PATTERN.search(text)
    if not m:
        return None
    return False if m.group(1) else True


INITIAL_BOOL_PATTERN = re.compile(
    r"(initial value of|initially|initial value)\s+(TRUE|FALSE)",
    re.IGNORECASE
)

ASSIGNMENT_PATTERN = re.compile(
    r"\b=\s*(TRUE|FALSE)\b",
    re.IGNORECASE
)

def extract_boolean_polarity(text: str):
    text = text or ""
    text_u = text.upper()

    m = INITIAL_BOOL_PATTERN.search(text_u)
    if m:
        return m.group(2)

    assigns = set()
    for m in ASSIGNMENT_PATTERN.finditer(text_u):
        assigns.add(m.group(1))

    if len(assigns) == 1:
        return assigns.pop()

    return None


# ============================================================
# FAILSAFE COVERAGE SIGNALS
# ============================================================

def extract_failsafe_states(text: str) -> set:
    return set(re.findall(r"failsafe level\s*(\d+)", (text or "").lower()))

def extract_state_behaviors(text: str) -> set:
    t = (text or "").lower()
    behaviors = set()

    if "enter and remain" in t or "remain in" in t:
        behaviors.add("STATE_PERSISTENCE")
    if "when a failure is reported" in t or "upon failure" in t:
        behaviors.add("FAILURE_TRIGGER")
    if "failsafe level 1" in t or "failsafe_level_1" in t:
        behaviors.add("FAILSAFE_L1")
    if "failsafe level 2" in t or "failsafe_level_2" in t:
        behaviors.add("FAILSAFE_L2")

    return behaviors


# ============================================================
# COMPARABILITY GATE (STRONG)
# ============================================================

def has_any_signal(sys_text: str, hlr_text: str, sys_table: set, hlr_table: set) -> bool:
    # Strong structured signals only
    if extract_failsafe_states(sys_text) or extract_failsafe_states(hlr_text):
        return True
    if extract_monitor_set(sys_text) or extract_monitor_set(hlr_text):
        return True
    if extract_time_values(sys_text) or extract_time_values(hlr_text):
        return True
    if extract_ssm_condition(sys_text) is not None or extract_ssm_condition(hlr_text) is not None:
        return True
    if extract_boolean_polarity(sys_text) or extract_boolean_polarity(hlr_text):
        return True
    if sys_table or hlr_table:
        return True
    return False


# ============================================================
# G1.1 CORE LOGIC
# ============================================================

def check_g1_1(sys_req: dict, hlr_req: dict):
    sys_text = sys_req.get("TEXT", "") or ""
    hlr_text = hlr_req.get("TEXT", "") or ""
    sys_table = normalize_table(sys_req.get("TABLE_TEXT", "") or "")
    hlr_table = normalize_table(hlr_req.get("TABLE_TEXT", "") or "")

    findings = []

    # STRICT: if no signals, do not PASS
    if not has_any_signal(sys_text, hlr_text, sys_table, hlr_table):
        #return FAIL, "NOT_APPLICABLE", "No comparable structured signals detected; manual review required."
        return G1Config.PASS, "NOT_APPLICABLE", (
            "No comparable structured signals detected; relied on state-model check."
        )


    # --- ARINC LABEL LOGIC (SYS subset in SW union)
    # If either looks like ARINC via table content or contains arinc keyword, compare labels.
    if looks_like_arinc(sys_req.get("TABLE_TEXT", "")) or looks_like_arinc(hlr_req.get("TABLE_TEXT", "")) or ("arinc" in sys_text.lower()) or ("arinc" in hlr_text.lower()):
        sys_labels = extract_arinc_labels_anywhere(sys_text, sys_req.get("TABLE_TEXT", ""))
        hlr_labels = extract_arinc_labels_anywhere(hlr_text, hlr_req.get("TABLE_TEXT", ""))

        # SYS requires these labels exist somewhere in SW (union handles this)
        if sys_labels and not sys_labels.issubset(hlr_labels):
            findings.append((
                "INCOMPLETE_SYSTEM_COVERAGE",
                f"Missing ARINC labels in software: {sorted(sys_labels - hlr_labels)}"
            ))

        # SW should not invent new labels not required by SYS (optional rule; keep strict)
        if hlr_labels - sys_labels:
            findings.append(("TRACEABILITY_EXTRA", f"Extra ARINC labels in software: {sorted(hlr_labels - sys_labels)}"))

    # --- SSM polarity mismatch
    sys_ssm = extract_ssm_condition(sys_text)
    hlr_ssm = extract_ssm_condition(hlr_text)
    if sys_ssm is not None and hlr_ssm is not None and sys_ssm != hlr_ssm:
        findings.append("BOOLEAN_POLARITY_MISMATCH")

    # --- Boolean polarity mismatch (general)
    if sys_ssm is None and hlr_ssm is None:
        sys_bool = extract_boolean_polarity(sys_text)
        hlr_bool = extract_boolean_polarity(hlr_text)
        if sys_bool and hlr_bool and sys_bool != hlr_bool:
            findings.append("BOOLEAN_POLARITY_MISMATCH")

    # --- Numeric mismatch (failsafe level)
    sys_level = extract_failsafe_level(sys_text)
    hlr_level = extract_failsafe_level(hlr_text)
    if sys_level and hlr_level and sys_level != hlr_level:
        findings.append("NUMERIC_MISMATCH")

    # --- Coverage mismatch (failsafe levels)
    sys_states = extract_failsafe_states(sys_text)
    hlr_states = extract_failsafe_states(hlr_text)
    if sys_states and not sys_states.issubset(hlr_states):
        findings.append((
            "INCOMPLETE_SYSTEM_COVERAGE",
            f"Missing failsafe levels in software: {sorted(sys_states - hlr_states)}"
        ))

    # --- Coverage mismatch (behaviors)
    if "failsafe" in sys_text.lower():
        sys_beh = extract_state_behaviors(sys_text)
        hlr_beh = extract_state_behaviors(hlr_text)
        missing = sys_beh - hlr_beh
        if missing:
            findings.append((
                "INCOMPLETE_SYSTEM_COVERAGE",
                f"Missing failsafe behaviors: {sorted(missing)}"
            ))

    # --- Monitors subset mismatch
    sys_monitors = extract_monitor_set(sys_text)
    hlr_monitors = extract_monitor_set(hlr_text)
    if sys_monitors and not sys_monitors.issubset(hlr_monitors):
        findings.append((
            "INCOMPLETE_SYSTEM_COVERAGE",
            f"Missing monitors in software: {sorted(sys_monitors - hlr_monitors)[:30]}"
        ))
    if hlr_monitors - sys_monitors:
        findings.append(("TRACEABILITY_EXTRA", f"Extra monitors in software: {sorted(hlr_monitors - sys_monitors)[:30]}"))

    # --- Time mismatch
    if extract_time_values(sys_text) != extract_time_values(hlr_text):
        # Only raise if SYS has some times
        if extract_time_values(sys_text):
            findings.append("NUMERIC_MISMATCH")

    # --- Expression drift (only if SYS has expression nums)
    sys_nums = extract_expression_numbers(sys_text) - {"0", "1"}
    hlr_nums = extract_expression_numbers(hlr_text) - {"0", "1"}
    if sys_nums and sys_nums != hlr_nums:
        findings.append(("POTENTIAL_LOGIC_DRIFT", format_numeric_drift(sys_nums, hlr_nums)))

    # --- Table missing/extra
    if sys_table and not hlr_table:
        findings.append("TRACEABILITY_MISSING")
    if hlr_table and not sys_table:
        findings.append("TRACEABILITY_EXTRA")

    # --- Table mismatch
    if sys_table and hlr_table and sys_table != hlr_table:
        findings.append("NUMERIC_MISMATCH")

    # --- Refinement flag
    refinement_flag = "NOT_APPLICABLE"
    finding_keys = {f[0] if isinstance(f, tuple) else f for f in findings}
    if "BOOLEAN_POLARITY_MISMATCH" in finding_keys or "POTENTIAL_LOGIC_DRIFT" in finding_keys:
        refinement_flag = "UNACCEPTABLE_DRIFT"

    # --- Render
    if findings:
        rendered = []
        for f in findings:
            if isinstance(f, tuple):
                key, detail = f
                rendered.append(f"{G1Config.COMMENTS.get(key, key)} ({detail})")
            else:
                rendered.append(G1Config.COMMENTS.get(f, str(f)))
        return G1Config.FAIL, refinement_flag, " | ".join(rendered)

    return G1Config.PASS, refinement_flag, "System and software requirements are functionally aligned."