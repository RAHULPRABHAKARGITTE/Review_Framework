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

# Stop as soon as we hit a NOTE (Note, Note1, Note2...), or document metadata
STOP_SECTION_PATTERN = re.compile(
    r"^\s*(note\b|note\d+\b|object type\b|reqt source\b|source\b|verification method\b|ref\b|references\b)",
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
        if ("object type" in ln.lower()) or ("verification method" in ln.lower()):
            break

        buffer.append(ln)

    if not buffer:
        return set()

    found = set()

    bullet_lines = [ln for ln in buffer if BULLET_PATTERN.match(ln)]
    if bullet_lines:
        for ln in bullet_lines:
            item = BULLET_PATTERN.sub("", ln).strip(" ,;.")
            itl = item.lower()
            if itl.startswith("note"):
                continue
            if len(item) >= 4:
                found.add(itl)
        return found

    # Comma/semicolon list
    joined = " ".join(buffer)
    parts = re.split(r"[;,]", joined)
    for p in parts:
        item = p.strip(" ,;.")
        itl = item.lower()
        if itl.startswith("note"):
            continue
        if len(item) >= 4:
            found.add(itl)

    return found

def extract_monitor_set(text: str) -> set:
    """
    Normalizes a possible monitor list and otherwise falls back to keyword presence.
    """
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
    """
    Normalizes a table-like text into a set of row strings,
    to be used only as a presence signal for comparability.
    """
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

ARINC_LABEL_PATTERN = re.compile(r"\b0?[0-7]{3}\b")         # Finds all octal label tokens of 3 digits
ARINC_TABLE_HINT = re.compile(r"\blabel\b", re.IGNORECASE)  # If a table contains the word “label”.

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

# Accept exponent numbers anywhere in body text for *drift* extraction
EXPR_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)(?![A-Za-z0-9_])"
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

    if re.search(r"\bELSE\b.*?\bremains\s+unchanged\b", t, flags=re.IGNORECASE | re.DOTALL):
        m2 = INITIAL_BOOL_INLINE_RE.search(t)
        if m2:
            return m2.group(1).upper()
    return None


# ---------- Helpers to avoid scientific notation ----------

def _to_plain_str(d: Decimal, q: str = "0.001") -> str:
    """
    Render Decimal as plain string (no exponent), trimmed zeros.
    """
    dq = d.quantize(Decimal(q))
    s = format(dq, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"

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
    ms_q = ms.quantize(Decimal("0.001"))
    if ms_q >= Decimal("1000"):
        s = (ms_q / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        return f"{_to_plain_str(s)} s"
    return f"{_to_plain_str(ms_q)} ms"

_NUM_AT_END_RE = re.compile(r"(?P<num>-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)$")

def _fmt_ms_value_token(token: str) -> str:
    """
    token looks like '<= 500' (ms) or '200' or '<= 1.5E+3'. Extract number and format.
    """
    token = (token or "").strip()
    m = _NUM_AT_END_RE.search(token)
    if not m:
        return token
    num = Decimal(m.group("num").replace(" ", ""))
    pretty = _fmt_ms(num)
    lead = token[:token.rfind(m.group("num"))].strip()
    return f"{lead} {pretty}".strip()

def _sanitize_exponents(text: str) -> str:
    """
    Last-mile sanitizer: convert any exponent number left in the final grouped
    message into a plain decimal (keeps surrounding text/units).
    """
    if not text:
        return text
    def _repl(m):
        try:
            d = Decimal(m.group(1).replace(" ", ""))
            return _to_plain_str(d)
        except Exception:
            return m.group(1)
    return re.sub(r"(-?\d+(?:\.\d+)?(?:[eE]\s*[+\-]?\s*\d+))", _repl, text)


# ---------- Time extraction: store plain, non-exponent numbers ----------

def extract_time_values(text: str) -> set:
    """Single time values with optional comparators, normalized to ms (stored as plain strings)."""
    values = set()
    text = text or ""
    for m in TIME_PATTERN.finditer(text):
        cmp_op = (m.group("cmp") or "").strip()
        num = Decimal(m.group("num"))
        unit = m.group("unit").lower()
        ms = num * _unit_factor_ms(unit)
        ms_s = _to_plain_str(ms)  # plain string, no exponent
        values.add(f"{cmp_op} {ms_s}".strip())
    return values

def extract_time_ranges_and_tolerances(text: str) -> dict:
    out = {"ranges": [], "tolerances": []}
    text = text or ""

    for m in RANGE_PATTERN.finditer(text):
        a = Decimal(m.group("a")); b = Decimal(m.group("b"))
        unit = m.group("unit").lower()
        f = _unit_factor_ms(unit)
        out["ranges"].append((_to_plain_str(a*f), _to_plain_str(b*f)))

    for m in TOLERANCE_PATTERN.finditer(text):
        center = Decimal(m.group("num")); unit = m.group("unit").lower()
        t = Decimal(m.group("t")); tunit = m.group("tunit").lower()
        center_ms = _to_plain_str(center * _unit_factor_ms(unit))
        if tunit == "%":
            out["tolerances"].append({"center_ms": center_ms, "tol_ms": None, "percent": _to_plain_str(t)})
        else:
            tol_ms = _to_plain_str(t * _unit_factor_ms(tunit))
            out["tolerances"].append({"center_ms": center_ms, "tol_ms": tol_ms, "percent": None})
    return out

def extract_expression_numbers(text: str) -> set:
    """
    Extract numeric literals (including exponent) and render as plain strings (no exponent).
    """
    nums = set()
    text = text or ""
    for raw in EXPR_NUM_RE.findall(text):
        try:
            d = Decimal(raw.replace(" ", ""))
            nums.add(_to_plain_str(d))
        except Exception:
            nums.add(raw)
    return nums

def format_numeric_drift(sys_nums: set, hlr_nums: set) -> str:
    """
    Render drift with plain decimals (no E+).
    """
    def _plain_sorted(ss: set) -> list[str]:
        out = []
        for s in ss:
            try:
                out.append(_to_plain_str(Decimal(str(s))))
            except Exception:
                out.append(str(s))
        try:
            return [x for _, x in sorted((Decimal(x), x) for x in out)]
        except Exception:
            return sorted(out)

    missing = _plain_sorted(sys_nums - hlr_nums)
    extra   = _plain_sorted(hlr_nums - sys_nums)
    parts = []
    if missing:
        parts.append(f"Missing in software: {', '.join(missing)}")
    if extra:
        parts.append(f"Extra in software: {', '.join(extra)}")
    return "; ".join(parts)

def compare_timing(sys_text: str, hlr_text: str, findings: list):
    """
    Produce actionable timing diffs across values, ranges, and tolerances.
    Render values human-readably (e.g., '1.5 s', '200 ms'), never in exponent.
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
        sys_r_fmt = [ (_fmt_ms(Decimal(a)), _fmt_ms(Decimal(b)) ) for (a,b) in sorted(sys_ranges) ]
        hlr_r_fmt = [ (_fmt_ms(Decimal(a)), _fmt_ms(Decimal(b)) ) for (a,b) in sorted(hlr_ranges) ]
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
                pct = _to_plain_str(Decimal(t[2]))
                return (c, f"{pct}%")
            if t[1]:   # absolute tolerance in ms
                return (c, _fmt_ms(Decimal(t[1])))
            return (c, None)
        sys_t_fmt = [ _fmt_tol(t) for t in sorted(sys_tols) ]
        hlr_t_fmt = [ _fmt_tol(t) for t in sorted(hlr_tols) ]
        findings.append(("NUMERIC_MISMATCH",
                         f"Timing tolerances differ: SYS={sys_t_fmt} vs SW={hlr_t_fmt}"))


# ============================================================
# SSM (GENERALIZED, MULTI-STATE)
# ============================================================

# Equality: "SSM data is set to <state>", "SSM data equals <state>", "SSM data = <state>", "SSM data indicates <state>"
SSM_EQ_STATES_RE = re.compile(
    r"""
    \bSSM\s+data\b
    (?:\s+is\s+)?                          # optional 'is'
    (?:
        (?:set\s+to|equals?|=)\s*["']?(?P<state_eq>[A-Za-z_ \-/]+?)["']?   # equality forms
      |
        \s+indicates\s+["']?(?P<state_ind>[A-Za-z_ \-/]+?)["']?            # indicates form
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE
)

# Inequality: "SSM data != <state>", "SSM data not equal to <state>", "SSM data not set to <state>"
SSM_NEQ_STATES_RE = re.compile(
    r"""
    \bSSM\s+data\b
    (?:\s+is\s+)?                                     # optional 'is'
    (?:
        (?:!=|not\s+equal\s+to|not\s+set\s+to)\s*["']?(?P<state_neq>[A-Za-z_ \-/]+?)["']?
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE
)

def _normalize_ssm_state(raw: str) -> str | None:
    """
    Normalize raw SSM state text using G1Config.SSM_ALIASES first.
    Falls back to UPPER_SNAKE_CASE so we don't drop previously unseen labels.
    """
    if not raw:
        return None
    t = re.sub(r"\s+", " ", raw.strip()).upper()
    # try configured aliases (from ICD)
    aliases = getattr(G1Config, "SSM_ALIASES", {}) or {}
    for k, v in aliases.items():
        if t == k or t.replace("_", " ") == k:
            return v
    # fallback: generic tokenization
    token = re.sub(r"[^A-Z0-9]+", "_", t).strip("_")
    return token or None

def extract_ssm_states(text: str):
    """
    Returns {"eq": set(), "neq": set()} where sets contain normalized SSM tokens.
    Empty sets if nothing found.
    """
    text = text or ""
    out = {"eq": set(), "neq": set()}

    for m in SSM_EQ_STATES_RE.finditer(text):
        state = m.group("state_eq") or m.group("state_ind")
        norm = _normalize_ssm_state(state)
        if norm:
            out["eq"].add(norm)

    for m in SSM_NEQ_STATES_RE.finditer(text):
        state = m.group("state_neq")
        norm = _normalize_ssm_state(state)
        if norm:
            out["neq"].add(norm)

    return out

def extract_ssm_condition_bool_compat(text: str):
    """
    Backward-compatible boolean for 'Normal Operation':
      True  -> explicitly equals NORMAL_OPERATION
      False -> explicitly not equals NORMAL_OPERATION
      None  -> not determinable from text
    """
    states = extract_ssm_states(text)
    if "NORMAL_OPERATION" in states["eq"]:
        return True
    if "NORMAL_OPERATION" in states["neq"]:
        return False
    return None

def _compare_ssm_states(sys_text: str, hlr_text: str, findings: list):
    """
    Multi-state comparison using eq/neq sets.
    Flags:
      - equality set mismatch
      - contradictions (SYS eq vs HLR neq and vice versa)
      - missing coverage (SYS eq state not covered at SW)
      - extra eq constraints at SW not asked by SYS
    """
    sys_s = extract_ssm_states(sys_text)
    hlr_s = extract_ssm_states(hlr_text)

    # Exit if neither mentions SSM
    if not (sys_s["eq"] or sys_s["neq"] or hlr_s["eq"] or hlr_s["neq"]):
        return

    # Equality sets differ (both sides claim explicit equals but not the same set)
    if sys_s["eq"] and hlr_s["eq"] and sys_s["eq"] != hlr_s["eq"]:
        findings.append((
            "BOOLEAN_POLARITY_MISMATCH",
            f"SSM equality constraints differ: SYS={sorted(sys_s['eq'])} vs SW={sorted(hlr_s['eq'])}"
        ))

    # Contradictions: one requires a state, the other forbids it
    contradictions = (sys_s["eq"] & hlr_s["neq"]) | (hlr_s["eq"] & sys_s["neq"])
    if contradictions:
        findings.append((
            "BOOLEAN_POLARITY_MISMATCH",
            f"SSM contradictions on states: {sorted(contradictions)}"
        ))

    # SYS requires a state but SW is silent/doesn't cover it
    missing_eq = sys_s["eq"] - hlr_s["eq"] - hlr_s["neq"]
    if missing_eq:
        findings.append((
            "INCOMPLETE_SYSTEM_COVERAGE",
            f"SSM states required by SYS but not covered in SW: {sorted(missing_eq)}"
        ))

    # Extra SW equality constraints not asked by SYS (unless SYS explicitly forbids them)
    extra_eq = hlr_s["eq"] - sys_s["eq"] - sys_s["neq"]
    if extra_eq:
        findings.append((
            "TRACEABILITY_EXTRA",
            f"Extra SSM states constrained in SW: {sorted(extra_eq)}"
        ))


# ============================================================
# ICD-AWARE ARINC COMPARISON (labels + polling rates)
# ============================================================

def _all_icd_intervals_for_label(label: str):
    """
    Return all periodic intervals (ms) for a given label across all receivers in ARINC_REF.
    """
    out = []
    for rx, labmap in (getattr(G1Config, "ARINC_REF", {}) or {}).items():
        for key, props in labmap.items():
            # match plain label key (e.g., "206") or special entries like "206_L_ADC"
            if key == label or key.startswith(f"{label}_"):
                if props.get("periodic") and "interval_ms" in props:
                    try:
                        out.append(Decimal(str(props["interval_ms"])))
                    except Exception:
                        pass
    return out

def _icd_recommended_poll_for_label(label: str):
    """
    Return recommended 'polling_ms' hints for aperiodic label across receivers.
    """
    out = []
    for rx, labmap in (getattr(G1Config, "ARINC_REF", {}) or {}).items():
        for key, props in labmap.items():
            if key == label or key.startswith(f"{label}_"):
                if not props.get("periodic") and "polling_ms" in props:
                    try:
                        out.append(Decimal(str(props["polling_ms"])))
                    except Exception:
                        pass
    return out

_SENT_SPLIT = re.compile(r"(?<=[\.\?!])\s+|\n+")

def _find_label_sentences(text: str, label: str):
    """
    Very simple heuristic: return sentences that contain the label token (octal, 3 digits).
    """
    out = []
    if not (text and label):
        return out
    for sent in _SENT_SPLIT.split(text):
        if re.search(rf"\b0?{label}\b", sent):
            out.append(sent)
    return out

def _parse_times_from_sentences(sents: list[str]):
    """
    Use existing extract_time_values to pull candidate ms values from the sentences.
    Returns decimals in ms.
    """
    vals = []
    for s in sents:
        for tok in extract_time_values(s):
            # tokens look like "<= 500" or "200"; we want the trailing number (already in ms)
            m = re.search(r"(-?\d+(?:\.\d+)?)$", tok)
            if m:
                try:
                    vals.append(Decimal(m.group(1)))
                except Exception:
                    pass
    return vals

def _icd_compare_labels_and_rates(sys_text: str, hlr_text: str, findings: list):
    """
    1) Keep your existing label coverage checks (already in check_g1_1).
    2) Additionally enforce ICD polling vs interval:
         - If HLR (or SYS) states a poll period near a label, require:
             period_ms <= min(ICD intervals for that label), when periodic
             period_ms ≈ recommended polling_ms, when aperiodic (within tolerance)
    """
    if not getattr(G1Config, "ARINC_REF", None):
        return  # nothing to do

    # Candidate labels from both sides
    labels = sorted(extract_arinc_labels_anywhere(sys_text, "") | extract_arinc_labels_anywhere(hlr_text, ""))

    for lab in labels:
        # Gather candidate poll periods (ms) from sentences that mention this label in SYS/HLR
        sys_sents = _find_label_sentences(sys_text, lab)
        hlr_sents = _find_label_sentences(hlr_text, lab)
        cand_ms = _parse_times_from_sentences(sys_sents + hlr_sents)

        if not cand_ms:
            continue  # nothing to check for this label

        # Periodic case: ensure period <= interval (use smallest ICD interval for strictest constraint)
        icd_intervals = _all_icd_intervals_for_label(lab)
        if icd_intervals:
            icd_min = min(icd_intervals)
            for p in cand_ms:
                if p > icd_min:
                    findings.append((
                        "NUMERIC_MISMATCH",
                        f"Polling for label {lab} is slower than ICD interval: period={_fmt_ms(p)} vs ICD_min={_fmt_ms(icd_min)}"
                    ))

        # Aperiodic case: if ICD provides a 'polling_ms' recommendation, check proximity (±10%)
        icd_reco = _icd_recommended_poll_for_label(lab)
        for r in icd_reco:
            for p in cand_ms:
                # accept ±10% tolerance by default
                lo = r * Decimal("0.90")
                hi = r * Decimal("1.10")
                if not (lo <= p <= hi):
                    findings.append((
                        "NUMERIC_MISMATCH",
                        f"Aperiodic polling for label {lab} deviates from ICD: period={_fmt_ms(p)} vs recommended≈{_fmt_ms(r)} (±10%)"
                    ))


# ============================================================
# COMPARABILITY GATE (multi-state SSM aware)
# ============================================================

def has_any_signal(sys_text: str, hlr_text: str, sys_table: set, hlr_table: set) -> bool:
    # Strong structured signals only
    if extract_failsafe_states(sys_text) or extract_failsafe_states(hlr_text):
        return True
    if extract_monitor_set(sys_text) or extract_monitor_set(hlr_text):
        return True
    if extract_time_values(sys_text) or extract_time_values(hlr_text):
        return True

    # Legacy binary SSM for 'Normal Operation'
    if extract_ssm_condition(sys_text) is not None or extract_ssm_condition(hlr_text) is not None:
        return True

    # NEW: multi-state SSM presence
    ms_sys = extract_ssm_states(sys_text); ms_hlr = extract_ssm_states(hlr_text)
    if ms_sys["eq"] or ms_sys["neq"] or ms_hlr["eq"] or ms_hlr["neq"]:
        return True

    if extract_boolean_polarity(sys_text) or extract_boolean_polarity(hlr_text):
        return True
    if sys_table or hlr_table:
        return True
    return False


# ============================================================
# BOOLEAN EXTRACTION (legacy helpers)
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
    # LAST-MILE SANITIZER: remove any exponent number that might have slipped in
    grouped = "\n\n".join(parts)
    return _sanitize_exponents(grouped)


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

        # --- NEW: ICD-aware label polling checks ---
        _icd_compare_labels_and_rates(sys_text, hlr_text, findings)  # uses G1Config.ARINC_REF

    # --- NEW: Multi-state SSM comparison ---
    _compare_ssm_states(sys_text, hlr_text, findings)

    # --- OLD boolean fallback for Normal Operation only (kept for compatibility) ---
    sys_ssm = extract_ssm_condition_bool_compat(sys_text)
    hlr_ssm = extract_ssm_condition_bool_compat(hlr_text)
    if sys_ssm is not None and hlr_ssm is not None and sys_ssm != hlr_ssm:
        findings.append(("BOOLEAN_POLARITY_MISMATCH", "SSM condition differs (Normal Operation)"))

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

    # --- Expression drift (noise-controlled) -> plain numbers, no E+
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 1.0

    sys_nums = extract_expression_numbers(sys_text) - {"0", "1"}
    hlr_nums = extract_expression_numbers(hlr_text) - {"0", "1"}

    if sys_nums:
        if len(sys_nums) <= getattr(G1Config, "DRIFT_MAX_CONSTS", 25):
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