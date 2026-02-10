"""
state_diagram_logic.py

State diagram requirement detection + extraction + comparison.

Goal:
- Extract state machine model (states, initial, transitions) from SYS and HLR requirements
- Compare models and flag missing / extra transitions, missing states, initial mismatch

IMPORTANT:
- This is heuristic-based extraction, so when model is incomplete, we should not hard FAIL
  unless there are clear contradictions.
"""

import re
from config import G1Config
from g1.nlp_normalize import normalize_event as _normalize_event, normalize_text


# ============================================================
# DETECTION
# ============================================================

STATE_KEYWORDS = (
    "STATE DIAGRAM",
    "STATE MACHINE",
    "STATE TRANSITION",
    "TRANSITION TABLE",
    "CURRENT_STATE",
    "NEXT_STATE",
    "STATE :=",
    "STATE:=",
)

def is_state_diagram_requirement(req: dict) -> bool:
    """
    Detects whether a requirement likely contains state machine content.

    Uses:
    - key phrases in TEXT
    - transition-table patterns in TABLE_TEXT
    """
    text = (req.get("TEXT") or "").upper()
    table = (req.get("TABLE_TEXT") or "").upper()

    # Strong text triggers
    if any(k in text for k in STATE_KEYWORDS):
        return True

    # UML arrow in text (HTML-escaped)
    if "-->" in text or "--&gt;" in text:
        return True

    # Table header signature (more reliable than random table)
    if "FROM" in table and "TO" in table and "|" in table:
        return True

    return False


# ============================================================
# EXTRACTION REGEX
# ============================================================

# IF ... THEN ...
IF_RE = re.compile(r"\bIF\s+(.+?)\s+THEN\b", re.IGNORECASE)

# STATE := X
STATE_ASSIGN_RE = re.compile(r"\bSTATE\s*:?=\s*([A-Z0-9_]+)\b", re.IGNORECASE)

# INITIAL STATE X  / INITIAL_STATE = X / INITIAL: X / INIT STATE: X
INITIAL_RE = re.compile(
    r"\b(?:INITIAL(?:\s+|_)STATE|INITIAL|INIT(?:IAL)?(?:\s+|_)STATE)\s*[:=]?\s*([A-Z0-9_]+)\b",
    re.IGNORECASE
)

# Try to infer FROM state from IF condition, e.g., IF STATE = NORMAL THEN ...
FROM_STATE_IN_IF_RE = re.compile(
    r"\b(?:CURRENT(?:\s+|_)STATE|STATE)\s*(?:=|==|IS|IN)\s*([A-Z0-9_]+)\b",
    re.IGNORECASE
)

# UML patterns (text may be HTML-escaped by docx extractor)
UML_SIMPLE_RE = re.compile(r"\b([A-Z0-9_]+)\s*--(?:>|&gt;)\s*([A-Z0-9_]+)\b", re.IGNORECASE)
UML_EVENT_RE  = re.compile(r"\b([A-Z0-9_]+)\s*--\s*(.+?)\s*--(?:>|&gt;)\s*([A-Z0-9_]+)\b", re.IGNORECASE)


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_state(s: str) -> str:
    """
    - Use your shared normalize_text (handles punctuation/spacing)
    - Uppercase
    - Convert spaces to underscores
    """
    s = normalize_text(s or "").upper()
    return re.sub(r"\s+", "_", s).strip("_")


def _norm_event(ev: str) -> str:
    """
    Wrapper around your nlp_normalize.normalize_event with extra tolerances:

    - underscores → spaces (so 'failure_detected' == 'failure detected')
    - drop articles ('a', 'an', 'the')
    - collapse 'is detected' → 'detected'
    - normalize spacing and uppercase
    """
    ev = (ev or "")
    ev = ev.replace("_", " ")
    ev = _normalize_event(ev)  # keep your existing normalization first
    # Additional harmonization
    ev = re.sub(r"\b(a|an|the)\b", " ", ev, flags=re.IGNORECASE)
    ev = re.sub(r"\bis\s+detected\b", "detected", ev, flags=re.IGNORECASE)
    ev = re.sub(r"\s+", " ", ev).strip().upper()
    return ev


def _is_separator_row(cols: list[str]) -> bool:
    """
    Detect markdown-like separators from docx tables:
    e.g. ---- | ---- | ----
    """
    joined = "".join(cols)
    return bool(joined) and all(ch in "-_|" for ch in joined)


# ============================================================
# MODEL EXTRACTION
# ============================================================

def extract_state_model(req: dict) -> dict | None:
    """
    Extracts model from requirement:
      model = {
        "states": set[str],
        "initial": str|None,
        "transitions": set[tuple(from_state|None, event, to_state)],
        "unknown_from_count": int
      }

    Returns None if nothing state-like is found.
    """
    text = (req.get("TEXT") or "")
    table = (req.get("TABLE_TEXT") or "")

    states: set[str] = set()
    transitions: set[tuple] = set()
    initial: str | None = None
    unknown_from_count = 0

    # ---- Initial state
    m = INITIAL_RE.search(text)
    if m:
        initial = _normalize_state(m.group(1))
        if initial:
            states.add(initial)

    # ---- IF/THEN / STATE := parsing
    current_event = None
    current_from_state = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # IF ... THEN ...
        m = IF_RE.search(line)
        if m:
            cond = m.group(1)
            current_event = _norm_event(cond)
            m2 = FROM_STATE_IN_IF_RE.search(cond)
            current_from_state = _normalize_state(m2.group(1)) if m2 else None
            continue

        # STATE := X
        m = STATE_ASSIGN_RE.search(line)
        if m and current_event:
            to_state = _normalize_state(m.group(1))
            transitions.add((current_from_state, current_event, to_state))
            if current_from_state is None:
                unknown_from_count += 1
            else:
                states.add(current_from_state)
            if to_state:
                states.add(to_state)
            continue

        # reset on END IF / END / ENDIF (tolerate both with/without space)
        if line.upper().startswith(("END IF", "ENDIF", "END")):
            current_event = None
            current_from_state = None

    # ---- UML arrows (A --> B) and (A -- EVENT --> B)
    for frm, to in UML_SIMPLE_RE.findall(text):
        frm_n = _normalize_state(frm)
        to_n = _normalize_state(to)
        transitions.add((frm_n, "UML", to_n))
        states.update([frm_n, to_n])

    for frm, event, to in UML_EVENT_RE.findall(text):
        frm_n = _normalize_state(frm)
        to_n = _normalize_state(to)
        ev_n = _norm_event(event)
        transitions.add((frm_n, ev_n, to_n))
        states.update([frm_n, to_n])

    # ---- Table transitions FROM | EVENT | TO
    for raw_line in table.splitlines():
        if "|" not in raw_line:
            continue

        cols = [c.strip() for c in raw_line.split("|")]
        cols = [c for c in cols if c.strip()]  # drop empties

        if len(cols) < 3:
            continue

        cols_u = [c.upper().strip() for c in cols]

        # ignore separator rows and header rows
        if _is_separator_row(cols_u):
            continue

        if cols_u[0] in ("FROM", "CURRENT_STATE", "STATE") and cols_u[2] in ("TO", "NEXT_STATE"):
            continue

        frm = _normalize_state(cols_u[0])
        event = _norm_event(cols_u[1])
        to = _normalize_state(cols_u[2])

        if not frm or not to:
            continue
        if frm in ("FROM", "STATE", "CURRENT_STATE"):
            continue
        if to in ("TO", "NEXT_STATE"):
            continue

        transitions.add((frm, event, to))
        states.update([frm, to])

    # ---- Decide if model exists
    if not states and not transitions:
        return None

    return {
        "states": states,
        "initial": initial,
        "transitions": transitions,
        "unknown_from_count": unknown_from_count
    }


# ============================================================
# MODEL COMPARISON
# ============================================================

def compare_state_models(sys_model: dict, hlr_model: dict):
    """
    Compares SYS and HLR models.

    Conservative rule:
    - If HLR introduces states or transitions not in SYS → FAIL
    - If HLR misses SYS transitions/states → FAIL
    - If parsing is incomplete (unknown FROM-state transitions), it should NOT hard FAIL by itself.
      Return REVIEW with a note if everything else matches.
    """
    findings = []
    notes = []

    sys_states = sys_model.get("states", set())
    hlr_states = hlr_model.get("states", set())

    sys_trans = sys_model.get("transitions", set())
    hlr_trans = hlr_model.get("transitions", set())

    sys_init = sys_model.get("initial")
    hlr_init = hlr_model.get("initial")

    # ---- Initial state mismatch
    if sys_init and hlr_init and sys_init != hlr_init:
        findings.append(f"Initial state mismatch: SYS={sys_init}, HLR={hlr_init}")

    # ---- State set mismatch
    missing_states = sys_states - hlr_states
    extra_states = hlr_states - sys_states

    if missing_states:
        findings.append(f"Missing states in software: {sorted(missing_states)}")

    if extra_states:
        findings.append(f"Extra states in software: {sorted(extra_states)}")

    # ---- Transition mismatches
    missing_trans = sys_trans - hlr_trans
    extra_trans = hlr_trans - sys_trans

    if missing_trans:
        findings.append(f"Missing transitions in software: {sorted(missing_trans)}")

    if extra_trans:
        findings.append(f"Extra transitions in software: {sorted(extra_trans)}")

    # ---- Unknown FROM states in HLR indicate extraction uncertainty ONLY
    unknown_from = {t for t in hlr_trans if t[0] is None}
    if unknown_from:
        notes.append(
            f"Software has transitions with unknown FROM-state (extraction uncertainty): count={len(unknown_from)}"
        )

    if findings:
        # Real mismatches → FAIL, but include uncertainty notes if any
        msg = " | ".join(findings + notes) if notes else " | ".join(findings)
        return G1Config.FAIL, msg

    # No real mismatches
    if notes:
        # Don’t fail: return REVIEW so it doesn’t turn the overall result into FAIL
        return G1Config.REVIEW, " | ".join(notes)

    return G1Config.PASS, "State models are aligned."