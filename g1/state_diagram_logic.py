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

    # UML arrow in text
    if "-->" in text:
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

# INITIAL STATE X  / INITIAL: X / INIT STATE: X
INITIAL_RE = re.compile(
    r"\b(?:INITIAL\s+STATE|INITIAL|INIT(?:IAL)?\s+STATE)\s*[:=]?\s*([A-Z0-9_]+)\b",
    re.IGNORECASE
)

# Try to infer FROM state from IF condition
FROM_STATE_IN_IF_RE = re.compile(
    r"\b(?:CURRENT_STATE|STATE)\s*(?:=|==|IS|IN)\s*([A-Z0-9_]+)\b",
    re.IGNORECASE
)

# UML patterns
UML_SIMPLE_RE = re.compile(r"\b([A-Z0-9_]+)\s*-->\s*([A-Z0-9_]+)\b", re.IGNORECASE)
UML_EVENT_RE  = re.compile(r"\b([A-Z0-9_]+)\s*--\s*(.+?)\s*-->\s*([A-Z0-9_]+)\b", re.IGNORECASE)


# ============================================================
# NORMALIZATION
# ============================================================

# def _normalize_state(s: str) -> str:
#     s = (s or "").strip().upper()
#     s = re.sub(r"\s+", "_", s)
#     return s


# def _normalize_event(ev: str) -> str:
#     """
#     Event normalization:
#     - uppercase
#     - collapse whitespace
#     - normalize operators
#     - remove extra parentheses spacing
#     """
#     if not ev:
#         return ""

#     ev = ev.strip().upper()
#     ev = " ".join(ev.split())

#     # Normalize common operator variants
#     ev = ev.replace("==", "=")
#     ev = ev.replace(" IS ", " = ")
#     ev = ev.replace(" IN ", " = ")

#     # Remove repeated parentheses spaces
#     ev = ev.replace("( ", "(").replace(" )", ")")

#     return ev

from g1.nlp_normalize import normalize_event as _normalize_event, normalize_text

def _normalize_state(s: str) -> str:
    s = normalize_text(s).upper()
    return re.sub(r"\s+", "_", s)
# _normalize_event is now provided by nlp_normalize.normalize_event

# _normalize_event is now provided by nlp_normalize.normalize_event


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

    states = set()
    transitions = set()
    initial = None
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
            current_event = _normalize_event(m.group(1))
            m2 = FROM_STATE_IN_IF_RE.search(m.group(1))
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

        # reset on END IF / END / ENDIF
        if line.upper().startswith(("END IF", "ENDIF", "END")):
            current_event = None
            current_from_state = None

    # ---- UML arrows (A --> B)
    for frm, to in UML_SIMPLE_RE.findall(text):
        frm = _normalize_state(frm)
        to = _normalize_state(to)
        transitions.add((frm, "UML", to))
        states.update([frm, to])

    # ---- UML arrows with event (A -- EVENT --> B)
    for frm, event, to in UML_EVENT_RE.findall(text):
        frm = _normalize_state(frm)
        to = _normalize_state(to)
        event = _normalize_event(event)
        transitions.add((frm, event, to))
        states.update([frm, to])

    # ---- Table transitions FROM | EVENT | TO
    for raw_line in table.splitlines():
        if "|" not in raw_line:
            continue

        cols = [c.strip() for c in raw_line.split("|")]

        # Remove empty columns due to leading/trailing |
        cols = [c for c in cols if c.strip()]

        if len(cols) < 3:
            continue

        cols_u = [c.upper().strip() for c in cols]

        # ignore separator rows and header rows
        if _is_separator_row(cols_u):
            continue

        if cols_u[0] in ("FROM", "CURRENT_STATE", "STATE") and cols_u[2] in ("TO", "NEXT_STATE"):
            continue

        frm = _normalize_state(cols_u[0])
        event = _normalize_event(cols_u[1])
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
    - If parsing is incomplete (too many unknown FROM transitions), add REVIEW-like note but still FAIL only if clear mismatch
    """
    findings = []

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

    # ---- Unknown FROM states are not automatically FAIL
    # They indicate extraction uncertainty.
    unknown_from = {t for t in hlr_trans if t[0] is None}
    if unknown_from:
        findings.append(
            f"Software has transitions with unknown FROM-state (extraction uncertainty): count={len(unknown_from)}"
        )

    if findings:
        return G1Config.FAIL, " | ".join(findings)

    return G1Config.PASS, "State models are aligned."