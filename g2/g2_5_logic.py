# from config import (
# TIMING_TERMS,
# THROUGHPUT_TERMS,
# RESOURCE_TERMS,
# VAGUE_TERMS,
# TIME_PATTERN,
# RATE_PATTERN,
# PERIODICITY_PATTERN,
# VAGUE_RATE_PATTERN,
# CYCLES_PATTERN,
# RESOURCE_PATTERN,
# EXCLUDED_WORDS
# )
from config import G2Config
from collections import defaultdict
from collections import Counter

import re

# ********* Helper Functions for G2.5 ***********

# --- helper: whole-word matching with optional hyphen/space between parts ---
def _make_term_regex(term: str) -> re.Pattern:
    """
    Build a case-insensitive regex for a term with word boundaries.
    If the term contains a hyphen, allow hyphen OR single space between parts.
    Example: 'cold-start' matches 'cold-start' or 'cold start'.
    """
    term = term.strip()
    if "-" in term:
        parts = [re.escape(p) for p in term.split("-") if p]
        pattern = r'\b' + r'[-\s]?'.join(parts) + r'\b'
    else:
        pattern = r'\b' + re.escape(term) + r'\b'
    return re.compile(pattern, flags=re.IGNORECASE)

def _has_whole_term(text: str, term: str) -> bool:
    """True if `term` (word-bounded, hyphen/space tolerant) appears in text."""
    return _make_term_regex(term).search(text) is not None

# ********* Main G2.5 Function ***********
def analyze_requirement_g2_5(req_id, text, datasheet_refs):
    """
    Returns a list of G2.5 violations for ONE requirement.
    Only the terms that violate are reported (with repetition counts).
    Ensures one row per (Requirement_ID, Category).
    """
    issues = []

    # Collectors per category (lists so we can count duplicates)
    timing_terms     = []
    throughput_terms = []
    resource_terms   = []
    vague_terms      = []

    # -------------------------
    # 1) TIMING CONSTRAINT CHECK
    #    Accept either time units OR cycles-based definition.
    # -------------------------
    timing_terms = []
    for term in G2Config.TIMING_TERMS:
        if _has_whole_term(text, term):
            has_time_units = bool(G2Config.TIME_PATTERN.search(text))
            has_cycles_unit = bool(G2Config.CYCLES_PATTERN.search(text)) or bool(G2Config.RESOURCE_PATTERN.search(text))
            if not (has_time_units or has_cycles_unit):
                timing_terms.append(term)

    if timing_terms:
        c = Counter(timing_terms)
        violated = ", ".join(f"{t} (x{n})" for t, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Timing",
            "Violated_Content": violated,
            "Explanation": "Timing-related terms present without explicit numeric timing (time units or cycles)."
        })

    # -------------------------
    # 2) THROUGHPUT / RATE CHECK
    #    Pass if a numeric rate or periodicity is present.
    #    Violate only for explicit vague phrases without numeric rate/periodicity.
    # -------------------------
    throughput_terms = []

    has_numeric_rate = bool(G2Config.RATE_PATTERN.search(text) or G2Config.PERIODICITY_PATTERN.search(text))

    # "periodically / periodic" with no numeric rate/periodicity -> violation
    if re.search(r"\bperiodic(?:ally)?\b", text, flags=re.IGNORECASE) and not has_numeric_rate:
        throughput_terms.append("periodically")

    # "high/low data rate|throughput|bandwidth" with no numeric rate -> violation
    vr = G2Config.VAGUE_RATE_PATTERN.search(text)
    if vr and not has_numeric_rate:
        throughput_terms.append(vr.group(0).lower())

    # (Optional) If the requirement speaks about throughput nouns but gives no numeric rate
    # keep it minimal & robust: check only nouns (not generic verbs)
    if (re.search(r"\b(?:bandwidth|throughput|sampling\s+rate|message\s+rate|frequency)\b",
                  text, flags=re.IGNORECASE)
            and not has_numeric_rate):
        throughput_terms.append("missing numeric rate")

    if throughput_terms:
        c = Counter(throughput_terms)
        violated = ", ".join(f"{t} (x{n})" for t, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Throughput",
            "Violated_Content": violated,
            "Explanation": "Throughput-related terms present without explicit rate/frequency or periodicity."
        })

    # -------------------------
    # 3) RESOURCE USAGE CHECK
    #    (Full coverage: MEMORY/RAM/ROM/FLASH, CPU/exec time/cycles, BUFFER, STACK)
    #    Aggregate ALL resource terms into ONE row per requirement.
    # -------------------------
    for _resource_type, terms in G2Config.RESOURCE_TERMS.items():
        for term in terms:
            if _has_whole_term(text, term):
                if not G2Config.RESOURCE_PATTERN.search(text):
                    resource_terms.append(term)

    # -------------------------
    # 4) VAGUE PERFORMANCE TERMS
    #    Only flag when NO numeric constraint is present.
    # -------------------------
    vague_terms = []

    has_any_numeric_constraint = bool(
        G2Config.TIME_PATTERN.search(text)
        or G2Config.RATE_PATTERN.search(text)
        or G2Config.RESOURCE_PATTERN.search(text)
        or G2Config.PERIODICITY_PATTERN.search(text)
        or G2Config.CYCLES_PATTERN.search(text)
    )

    for term in G2Config.VAGUE_TERMS:
        if _has_whole_term(text, term):
            # "periodically" is handled in Throughput block; skip here to avoid duplicates
            if re.fullmatch(r"periodic(?:ally)?", term, flags=re.IGNORECASE):
                continue
            # Only record if no numeric constraints are present anywhere in the requirement
            if not has_any_numeric_constraint:
                vague_terms.append(term)

    # --- Consolidate to ONE row per category with counts ---
    if timing_terms:
        c = Counter(timing_terms)
        violated = ", ".join(f"{t} (x{n})" for t, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Timing",
            "Violated_Content": violated,
            "Explanation": "Timing-related terms present without explicit numeric timing (time units or cycles)."
        })

    if throughput_terms:
        c = Counter(throughput_terms)
        violated = ", ".join(f"{t} (x{n})" for t, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Throughput",
            "Violated_Content": violated,
            "Explanation": "Throughput-related terms present without explicit rate/frequency."
        })

    if resource_terms:
        c = Counter(resource_terms)
        violated = ", ".join(f"{t} (x{n})" for t, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Resource",
            "Violated_Content": violated,
            "Explanation": "Resource usage mentioned without bounded numeric limit."
        })

    if vague_terms:
        c = Counter(vague_terms)
        violated = ", ".join(f"{v} (x{n})" for v, n in c.items())
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Vagueness",
            "Violated_Content": violated,
            "Explanation": "Vague performance terms used without measurable constraints."
        })

    # Return consolidated issues (one row per category max)
    return issues




