from config import G1Config
import re
from decimal import Decimal, ROUND_HALF_UP


# ============================================================
# FAILSAFE LEVEL EXTRACTION
# ============================================================

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

    # Comma/semicolon list
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

    found = set()
    t = (text or "").lower()
    for k in G1Config.MONITOR_KEYWORDS:
        if k in t:
            found.add(k)
    return found


# ============================================================
# TABLE NORMALIZATION (for comparability gate only)
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
# ARINC LABEL HANDLING
# ============================================================

ARINC_LABEL_PATTERN = re.compile(r"\b0?[0-7]{3}\b")
ARINC_TABLE_HINT = re.compile(r"\blabel\b", re.IGNORECASE)

def extract_arinc_labels_anywhere(text: str, table_text: str) -> set:
    """
    Extract possible ARINC labels from BOTH free text + table text.
    """
    labels = set()
    blob = f"{text or ''}\n{table_text or ''}"
    for m in ARINC_LABEL_PATTERN.findall(blob):
        labels.add(m)
    return labels

def looks_like_arinc(table_text: str) -> bool:
    return bool(table_text and ARINC_TABLE_HINT.search(table_text))


# ============================================================
# NUMERIC & TIMING EXTRACTION (Enhanced, config-driven)
# ============================================================

def _unit_factor_ms(unit: str) -> Decimal:
    u = (unit or "").lower()
    return Decimal(G1Config.UNIT_TO_MS.get(u, "1"))

def _build_units_alt() -> str:
    # e.g., "us|µs|ms|s|min"
    esc = [re.escape(u) for u in G1Config.TIME_UNITS]
    return "|".join(esc)

_TIME_UNITS_ALT = _build_units_alt()

TIME_PATTERN = re.compile(
    rf"""
    (?P<cmp><=|>=|<|>)?\s*
    (?P<num>\d+(?:\.\d+)?)\s*
    (?P<unit>{_TIME_UNITS_ALT})\b
    """,
    re.IGNORECASE | re.VERBOSE
)

RANGE_PATTERN = re.compile(
    rf"(?P<a>\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(?P<b>\d+(?:\.\d+)?)\s*(?P<unit>{_TIME_UNITS_ALT})\b",
    re.IGNORECASE
)

TOLERANCE_PATTERN = re.compile(
    rf"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>{_TIME_UNITS_ALT})\s*(?:\+/-|±)\s*(?P<t>\d+(?:\.\d+)?)\s*(?P<tunit>%|{_TIME_UNITS_ALT})\b",
    re.IGNORECASE
)

EXPRESSION_NUMBER_PATTERN = re.compile(
    r"(?:(?:[-+]?\d+\.\d+(?:e[-+]?\d+)?)|(?:[-+]?\d+(?:e[-+]?\d+)?))",
    re.IGNORECASE
)

# -------- ELSE default polarity extraction --------
ELSE_DEFAULT_VALUE_RE = re.compile(
    r"\bELSE\b.*?(?:initial\s+value\s+of|initial\s+value\s*[:=]?)\s*(TRUE|FALSE)\b",
    re.IGNORECASE | re.DOTALL
)

INITIAL_BOOL_INLINE_RE = re.compile(
    r"\bINITIAL(?:\s+|_)STATE\s*(?:=|:=|:)?\s*(TRUE|FALSE)\b",
    re.IGNORECASE
)

def _extract_else_default(text: str) -> str | None:
    """
    Tries to extract the ELSE default boolean value.
    Priority:
      1) 'ELSE ... initial value (TRUE|FALSE)'
      2) If ELSE says 'remains unchanged' and there is an 'INITIAL_STATE = TRUE|FALSE',
         return that initial value as the effective ELSE default.
    Returns 'TRUE' / 'FALSE' / None
    """
    t = (text or "")
    m = ELSE_DEFAULT_VALUE_RE.search(t)
    if m:
        return m.group(1).upper()

    # Heuristic: if ELSE 'remains unchanged' exists, use INITIAL_STATE as default
    if re.search(r"\bELSE\b.*?\bremains\s+unchanged\b", t, flags=re.IGNORECASE | re.DOTALL):
        m2 = INITIAL_BOOL_INLINE_RE.search(t)
        if m2:
            return m2.group(1).upper()
    return None


# ---------- Pretty formatting for timing (no scientific notation) ----------

def _fmt_ms(ms: Decimal) -> str:
    """
    Pretty-prints a duration given in milliseconds:
      - 1500 ms  -> '1.5 s'
      - 1000 ms  -> '1 s'
      - 200 ms   -> '200 ms'
    No scientific notation.
    """
    if ms is None:
        return ""
    # quantize to 0.001ms to avoid exponent and normalize
    ms_q = ms.quantize(Decimal("0.001")).normalize()
    if ms_q >= Decimal("1000"):
        s = (ms_q / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP).normalize()
        s_str = format(s, "f")
        if "." in s_str:
            s_str = s_str.rstrip("0").rstrip(".")
        return f"{s_str} s"
    ms_str = format(ms_q, "f")
    if "." in ms_str:
        ms_str = ms_str.rstrip("0").rstrip(".")
    return f"{ms_str} ms"

def _fmt_ms_value_token(token: str) -> str:
    """
    token looks like '<= 500' (ms) or '200' etc. Extract number and format to 'ms'/'s'.
    """
    token = (token or "").strip()
    m = re.search(r"(?P<num>-?\d+(?:\.\d+)?)$", token)
    if not m:
        return token
    num = Decimal(m.group("num"))
    pretty = _fmt_ms(num)
    lead = token[:token.rfind(m.group("num"))].strip()
    return f"{lead} {pretty}".strip()


def extract_time_values(text: str) -> set:
    """Single time values with optional comparators, normalized to ms (as Decimal string)."""
    values = set()
    text = text or ""
    for m in TIME_PATTERN.finditer(text):
        cmp_op = (m.group("cmp") or "").strip()
        num = Decimal(m.group("num"))
        unit = m.group("unit").lower()
        ms = (num * _unit_factor_ms(unit)).normalize()
        values.add(f"{cmp_op} {ms}".strip())
    return values

def extract_time_ranges_and_tolerances(text: str) -> dict:
    out = {"ranges": [], "tolerances": []}
    text = text or ""

    for m in RANGE_PATTERN.finditer(text):
        a = Decimal(m.group("a")); b = Decimal(m.group("b"))
        unit = m.group("unit").lower()
        f = _unit_factor_ms(unit)
        out["ranges"].append((str((a*f).normalize()), str((b*f).normalize())))

    for m in TOLERANCE_PATTERN.finditer(text):
        center = Decimal(m.group("num")); unit = m.group("unit").lower()
        t = Decimal(m.group("t")); tunit = m.group("tunit").lower()
        center_ms = (center * _unit_factor_ms(unit)).normalize()
        if tunit == "%":
            out["tolerances"].append({"center_ms": str(center_ms), "tol_ms": None, "percent": str(t.normalize())})
        else:
            tol_ms = (t * _unit_factor_ms(tunit)).normalize()
            out["tolerances"].append({"center_ms": str(center_ms), "tol_ms": str(tol_ms), "percent": None})
    return out

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

def compare_timing(sys_text: str, hlr_text: str, findings: list):
    """
    Produce actionable timing diffs across values, ranges, and tolerances.
    Render values human-readably (e.g., '1.5 s', '200 ms').
    """
    # values
    sys_vals = extract_time_values(sys_text); hlr_vals = extract_time_values(hlr_text)
    if sys_vals and sys_vals != hlr_vals:
        sys_vals_fmt = [ _fmt_ms_value_token(v) for v in sorted(sys_vals) ]
        hlr_vals_fmt = [ _fmt_ms_value_token(v) for v in sorted(hlr_vals) ]
        findings.append(("NUMERIC_MISMATCH",
                         f"Timing values differ: SYS={sys_vals_fmt} vs SW={hlr_vals_fmt}"))

    # ranges
    sys_ext = extract_time_ranges_and_tolerances(sys_text)
    hlr_ext = extract_time_ranges_and_tolerances(hlr_text)

    sys_ranges = set(sys_ext["ranges"]); hlr_ranges = set(hlr_ext["ranges"])
    if sys_ranges and sys_ranges != hlr_ranges:
        sys_r_fmt = [ ( _fmt_ms(Decimal(a)), _fmt_ms(Decimal(b)) ) for (a,b) in sorted(sys_ranges) ]
        hlr_r_fmt = [ ( _fmt_ms(Decimal(a)), _fmt_ms(Decimal(b)) ) for (a,b) in sorted(hlr_ranges) ]
        findings.append(("NUMERIC_MISMATCH",
                         f"Timing ranges differ: SYS={sys_r_fmt} vs SW={hlr_r_fmt}"))

    # tolerances
    def tol_key(t): return (t["center_ms"], t["tol_ms"], t["percent"])
    sys_tols = {tol_key(t) for t in sys_ext["tolerances"]}
    hlr_tols = {tol_key(t) for t in hlr_ext["tolerances"]}
    if sys_tols and sys_tols != hlr_tols:
        def _fmt_tol(t):
            c = _fmt_ms(Decimal(t[0])) if t[0] is not None else None
            if t[2]:   # percent tolerance
                pct = str(Decimal(t[2]).normalize()).rstrip("0").rstrip(".")
                return (c, f"{pct}%")
            if t[1]:   # absolute tolerance in ms
                return (c, _fmt_ms(Decimal(t[1])))
            return (c, None)
        sys_t_fmt = [ _fmt_tol(t) for t in sorted(sys_tols) ]
        hlr_t_fmt = [ _fmt_tol(t) for t in sorted(hlr_tols) ]
        findings.append(("NUMERIC_MISMATCH",
                         f"Timing tolerances differ: SYS={sys_t_fmt} vs SW={hlr_t_fmt}"))


# ============================================================
# BOOLEAN EXTRACTION
# ============================================================

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
ASSIGNMENT_PATTERN = re.compile(r"\b=\s*(TRUE|FALSE)\b", re.IGNORECASE)

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

FAILSAFE_STATE_RE = re.compile(
    r"(?:failsafe(?:\s*[-_]*\s*level|_level)\s*[-_ ]*([0-9]+))",
    re.IGNORECASE
)

def extract_failsafe_states(text: str) -> set:
    """
    Extract FAILSAFE levels appearing as:
      FAILSAFE_LEVEL_1 / FAILSAFE level 1 / failsafe_level_2
    Returns: {"1","2",...}
    """
    if not text:
        return set()
    found = set()
    for m in FAILSAFE_STATE_RE.finditer(text):
        found.add(m.group(1))
    return found

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
# SCOPE CREEP / EXTRA FEATURES (heuristic, config-driven)
# ============================================================

def tokenize_terms(text: str) -> set:
    text = (text or "").lower()
    words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", text))
    return {w for w in words if w not in G1Config.EXTRA_FEATURE_STOPWORDS}

def detect_extra_features(sys_text: str, hlr_text: str) -> list:
    sys_terms = tokenize_terms(sys_text)
    extras = []
    # Allow up to 3 in-between words after verb before object noun
    for v in G1Config.EXTRA_FEATURE_VERBS:
        pattern = re.compile(rf"\b{re.escape(v)}\b\s+(?:[a-z]+\s+){{0,3}}([a-zA-Z0-9_{{}}/\-]+)", re.IGNORECASE)
        for m in pattern.finditer(hlr_text or ""):
            obj = (m.group(1) or "").lower()
            if obj and (obj not in sys_terms) and (obj not in (sys_text or "").lower()):
                extras.append(f"{v} {obj}")
    return extras

def check_extra_features(sys_text: str, hlr_text: str, findings: list):
    extra_feats = detect_extra_features(sys_text, hlr_text)
    if extra_feats:
        findings.append(("TRACEABILITY_EXTRA", f"Potential extra features in SW: {extra_feats[:10]}"))


# ============================================================
# TABLE PARSING & COMPARISON (Enhanced)
# ============================================================

def parse_table(table_text: str):
    if not table_text:
        return [], []
    lines = [ln.strip() for ln in table_text.splitlines() if "|" in ln]
    if not lines:
        return [], []
    rows = []
    for ln in lines:
        parts = [p.strip() for p in ln.split("|")]
        parts = [p for p in parts if p != ""]
        if parts:
            rows.append(parts)
    if not rows:
        return [], []
    headers = [h.strip().lower() for h in rows[0]]
    data = []
    for r in rows[1:]:
        row = {}
        for i, h in enumerate(headers):
            row[h] = r[i].strip() if i < len(r) else ""
        data.append(row)
    return headers, data

def _choose_primary_key(headers: list):
    if not headers:
        return None
    for k in G1Config.TABLE_PRIMARY_KEYS:
        if k in headers:
            return k
    return headers[0]  # fallback

def compare_tables(sys_table_text: str, hlr_table_text: str, findings: list):
    sys_h, sys_rows = parse_table(sys_table_text)
    hlr_h, hlr_rows = parse_table(hlr_table_text)

    if sys_rows and not hlr_rows:
        findings.append(("TRACEABILITY_MISSING", "Table missing in software"))
        return
    if hlr_rows and not sys_rows:
        findings.append(("TRACEABILITY_EXTRA", "Extra table in software"))
        return
    if not sys_rows and not hlr_rows:
        return

    # Header diffs
    sys_hs = set(sys_h); hlr_hs = set(hlr_h)
    if sys_hs != hlr_hs:
        missing_cols = sorted(sys_hs - hlr_hs)
        extra_cols = sorted(hlr_hs - sys_hs)
        if missing_cols:
            findings.append(("NUMERIC_MISMATCH", f"Missing table columns in SW: {missing_cols}"))
        if extra_cols:
            findings.append(("TRACEABILITY_EXTRA", f"Extra table columns in SW: {extra_cols}"))

    # Row diffs by primary key
    key = _choose_primary_key(sys_h)
    if key:
        sys_map = {r.get(key, f"row{idx}"): r for idx, r in enumerate(sys_rows)}
        hlr_map = {r.get(key, f"row{idx}"): r for idx, r in enumerate(hlr_rows)}
        missing_keys = sorted(set(sys_map.keys()) - set(hlr_map.keys()))
        extra_keys = sorted(set(hlr_map.keys()) - set(sys_map.keys()))
        if missing_keys:
            findings.append(("TRACEABILITY_MISSING", f"Missing table rows in SW (by '{key}'): {missing_keys[:20]}"))
        if extra_keys:
            findings.append(("TRACEABILITY_EXTRA", f"Extra table rows in SW (by '{key}'): {extra_keys[:20]}"))

        # Cell-level diffs for common keys
        for k in sorted(set(sys_map.keys()) & set(hlr_map.keys())):
            srow = sys_map[k]; hrow = hlr_map[k]
            cell_diffs = []
            for col in set(sys_h) & set(hlr_h):
                sv = srow.get(col, "").strip(); hv = hrow.get(col, "").strip()
                if sv != hv:
                    cell_diffs.append(f"{col}: SYS='{sv}' vs SW='{hv}'")
            if cell_diffs:
                findings.append(("NUMERIC_MISMATCH", f"Table row '{k}' differs -> " + "; ".join(cell_diffs[:5])))

def arinc_header_hint(table_text: str) -> set:
    headers, _ = parse_table(table_text)
    return set(h.lower() for h in headers if h and h.lower() in G1Config.ARINC_HEADERS)

def arinc_header_compare(sys_table_text: str, hlr_table_text: str, findings: list):
    sys_h = arinc_header_hint(sys_table_text)
    hlr_h = arinc_header_hint(hlr_table_text)
    missing = sorted(sys_h - hlr_h)
    if missing:
        findings.append(("TRACEABILITY_MISSING", f"ARINC column(s) missing in SW table: {missing}"))


# ============================================================
# OUTPUT RENDERING (grouped)
# ============================================================

def render_grouped(findings: list) -> str:
    buckets = {}
    for key, detail in findings:
        title = G1Config.GROUP_TITLES.get(key, key)
        msg = f"- {G1Config.COMMENTS.get(key, key)} ({detail})"
        buckets.setdefault(title, []).append(msg)
    parts = []
    for title in sorted(buckets.keys()):
        parts.append(f"[{title}]\n" + "\n".join(buckets[title]))
    return "\n\n".join(parts)


# ============================================================
# COMPARABILITY GATE
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
    # RAW text first
    sys_text = sys_req.get("TEXT_RAW") or sys_req.get("TEXT", "") or ""
    hlr_text = hlr_req.get("TEXT_RAW") or hlr_req.get("TEXT", "") or ""

    sys_table_text = sys_req.get("TABLE_TEXT", "") or ""
    hlr_table_text = hlr_req.get("TABLE_TEXT", "") or ""

    # For comparability gate we keep normalized presence checks
    sys_table = normalize_table(sys_table_text)
    hlr_table = normalize_table(hlr_table_text)

    findings = []

    # Applicability gate => REVIEW (manual review), not FAIL
    if not has_any_signal(sys_text, hlr_text, sys_table, hlr_table):
        return (
            G1Config.REVIEW,
            G1Config.REFINEMENT_NONE,
            "No comparable structured signals detected; automated comparison not applicable. Manual review required."
        )

    # --- ARINC label logic
    if (
        looks_like_arinc(sys_table_text) or
        looks_like_arinc(hlr_table_text) or
        ("arinc" in sys_text.lower()) or
        ("arinc" in hlr_text.lower())
    ):
        sys_labels = extract_arinc_labels_anywhere(sys_text, sys_table_text)
        hlr_labels = extract_arinc_labels_anywhere(hlr_text, hlr_table_text)

        if sys_labels and not sys_labels.issubset(hlr_labels):
            findings.append((
                "INCOMPLETE_SYSTEM_COVERAGE",
                f"Missing ARINC labels in software: {sorted(sys_labels - hlr_labels)}"
            ))

        if hlr_labels - sys_labels:
            findings.append(("TRACEABILITY_EXTRA", f"Extra ARINC labels in software: {sorted(hlr_labels - sys_labels)}"))

        # ARINC header hints
        arinc_header_compare(sys_table_text, hlr_table_text, findings)

    # --- SSM polarity mismatch
    sys_ssm = extract_ssm_condition(sys_text)
    hlr_ssm = extract_ssm_condition(hlr_text)
    if sys_ssm is not None and hlr_ssm is not None and sys_ssm != hlr_ssm:
        findings.append(("BOOLEAN_POLARITY_MISMATCH", "SSM condition differs"))

    # --- ELSE default polarity mismatch (explicit, reviewer-friendly)
    sys_else_default = _extract_else_default(sys_text)
    hlr_else_default = _extract_else_default(hlr_text)
    if sys_else_default and hlr_else_default and sys_else_default != hlr_else_default:
        findings.append(("BOOLEAN_POLARITY_MISMATCH",
                        f"ELSE default differs: SYS={sys_else_default} vs SW={hlr_else_default}"))

    # --- Numeric mismatch (failsafe level)
    sys_level = extract_failsafe_level(sys_text)
    hlr_level = extract_failsafe_level(hlr_text)
    if sys_level and hlr_level and sys_level != hlr_level:
        findings.append(("NUMERIC_MISMATCH", f"Failsafe level SYS={sys_level} SW={hlr_level}"))

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

    # --- Heuristic extra features (scope creep)
    check_extra_features(sys_text, hlr_text, findings)

    # --- Timing diffs (enhanced, pretty-format)
    compare_timing(sys_text, hlr_text, findings)

    # --- Expression drift (noise-controlled)
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 1.0

    sys_nums = extract_expression_numbers(sys_text) - {"0", "1"}
    hlr_nums = extract_expression_numbers(hlr_text) - {"0", "1"}

    if sys_nums:
        # 1) Skip drift if there are too many constants (likely algorithm body)
        if len(sys_nums) <= getattr(G1Config, "DRIFT_MAX_CONSTS", 25):
            # 2) Only report drift if sets are materially different
            j = _jaccard(sys_nums, hlr_nums)
            if sys_nums != hlr_nums and j < getattr(G1Config, "DRIFT_MIN_JACCARD", 0.60):
                findings.append(("POTENTIAL_LOGIC_DRIFT", format_numeric_drift(sys_nums, hlr_nums)))
        # else: skip to reduce noise

    # --- Table comparison (enhanced)
    compare_tables(sys_table_text, hlr_table_text, findings)

    # --- Refinement classification (predictable)
    refinement_flag = G1Config.REFINEMENT_NONE
    finding_keys = {k for (k, _) in findings}
    if any(k in finding_keys for k in ["BOOLEAN_POLARITY_MISMATCH", "POTENTIAL_LOGIC_DRIFT", "NUMERIC_MISMATCH"]):
        refinement_flag = G1Config.REFINEMENT_UNACCEPTABLE
    elif any(k in finding_keys for k in ["INCOMPLETE_SYSTEM_COVERAGE", "TRACEABILITY_MISSING"]):
        refinement_flag = G1Config.REFINEMENT_ACCEPTABLE

    if findings:
        return G1Config.FAIL, refinement_flag, render_grouped(findings)

    return G1Config.PASS, refinement_flag, "System and software requirements are functionally aligned."