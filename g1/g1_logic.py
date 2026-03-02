from collections import defaultdict, Counter
import math
import re

from config import G1Config
from io_utils import norm, normalize_text

from g1.g1_1_logic import check_g1_1
from g1.g1_2_logic import check_g1_2

from g1.intent_consistency_logic import (
    check_intent_consistency,
    get_intent_debug
)

#from g1.llm_explainer import explain_mismatch
#from g1.llm_explainer import RequirementReviewerAgent, extract_llm_reviewer_verdict

from g1.state_diagram_logic import (
    is_state_diagram_requirement,
    extract_state_model,
    compare_state_models
)

# ============================================================
# Algorithm / structured logic extractors
# Goal:
# - Detect missing ELSE/branches
# - Detect IF threshold mismatch
# - Detect RHS expression mismatch WITHOUT evaluating
# ============================================================

COND_RE = re.compile(r"\b(ELSE\s+IF|IF)\s*\((.*?)\)", re.IGNORECASE)
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$")


def _canon_text(text: str) -> str:
    """
    Canonicalize text for comparisons while preserving semantics:
    - convert underscores to spaces (critical for intent/state parsing)
    - keep fractions like 1/10.3 intact (we don't evaluate)
    """
    t = text or ""
    t = t.replace("\u00a0", " ")   # non-breaking spaces
    t = t.replace("_", " ")       # IMPORTANT FIX
    return t


def _canon_for_state(text: str) -> str:
    """
    Canonicalize text for state parser:
    - replace underscores with spaces
    - collapse multiple spaces
    - normalize END IF -> ENDIF and ' :=' -> '='
    - normalize typical condition wording (optional but helps)
    """
    t = (text or "")
    t = t.replace("\u00a0", " ")
    t = t.replace("_", " ")
    t = re.sub(r"\s+", " ", t)
    # normalize END IF to ENDIF because some parsers look for ENDIF only
    t = re.sub(r"\bEND\s+IF\b", "ENDIF", t, flags=re.IGNORECASE)
    # normalize assignment operator
    t = t.replace(" := ", " = ").replace(":=", " = ")
    # optional: normalize condition phrasing
    t = re.sub(r"\ba\s+failure\s+is\s+detected\b", "failure detected", t, flags=re.IGNORECASE)
    t = re.sub(r"\ba\s+critical\s+failure\s+is\s+detected\b", "critical failure detected", t, flags=re.IGNORECASE)
    return t.strip()


def normalize_expr(expr: str) -> str:
    """
    Normalize expression as text.
    Keep operators and fractions intact (NO evaluation).
    """
    expr = (expr or "").strip()
    expr = _canon_text(expr)
    expr = re.sub(r"\s+", " ", expr)

    # Normalize common operator spacing
    expr = expr.replace(" (", "(").replace("( ", "(")
    expr = expr.replace(" )", ")").replace(") ", ")")

    expr = expr.replace(" / ", "/")
    expr = expr.replace(" * ", "*")
    expr = expr.replace(" + ", "+")
    expr = expr.replace(" - ", "-")
    expr = expr.replace(" <= ", "<=")
    expr = expr.replace(" >= ", ">=")
    expr = expr.replace(" = ", "=")

    return expr


def extract_thresholds(text: str):
    """
    Extract numeric thresholds inside IF / ELSE IF conditions only.
    """
    thresholds = []
    t = _canon_text(text)
    for _, cond in COND_RE.findall(t or ""):
        nums = NUM_RE.findall(cond)
        thresholds.extend([float(n) for n in nums])
    return thresholds


def compare_thresholds(sys_text: str, sw_text: str, tol=1e-3, missing_gap=5.0):
    """
    Compare thresholds:
      - missing: SYS threshold absent in SW (delta >= missing_gap)
      - mismatched: SYS threshold close but different (tol < delta < missing_gap)
    """
    sys_thr = extract_thresholds(sys_text)
    sw_thr = extract_thresholds(sw_text)

    missing = []
    mismatched = []

    if not sys_thr:
        return missing, mismatched

    if not sw_thr:
        return sorted(sys_thr), mismatched

    for t in sys_thr:
        closest = min(sw_thr, key=lambda x: abs(x - t))
        delta = abs(closest - t)

        if delta <= tol:
            continue

        if delta >= missing_gap:
            missing.append(t)
        else:
            mismatched.append((t, closest))

    # de-dup and sort stable
    missing = sorted(set(missing))
    mismatched = sorted(set(mismatched), key=lambda x: (x[0], x[1]))

    return missing, mismatched


# place these compiled regexes near the top with others if you prefer
ELSEIF_ONLY_RE = re.compile(r"\bELSE\s+IF\b", re.IGNORECASE)
ELSE_ONLY_RE   = re.compile(r"\bELSE\b(?!\s*IF\b)", re.IGNORECASE)  # ELSE not followed by IF
ENDIF_RE       = re.compile(r"\bEND\s*IF\b|\bENDIF\b", re.IGNORECASE)


def count_branches(text: str):
    """
    Count IF/ELSE IF/ELSE/END IF or ENDIF (tolerant).
    """
    
    t = _canon_text(text)
    # normalize END IF -> ENDIF for stability (but we also regex both)
    t = re.sub(r"\bEND\s+IF\b", "ENDIF", t, flags=re.IGNORECASE)
    t_u = t.upper()

    return {
        "IF":     len(re.findall(r"\bIF\b", t_u)),
        "ELSEIF": len(ELSEIF_ONLY_RE.findall(t_u)),
        "ELSE":   len(ELSE_ONLY_RE.findall(t_u)),
        "ENDIF":  len(re.findall(r"\bENDIF\b", t_u)),  # already normalized
    }


def extract_assignments(text: str) -> dict:
    """
    Extract assignments LHS = RHS from pseudo-code-like blocks.
    Keeps RHS expression as string (NO eval).
    """
    assigns = {}
    t = _canon_text(text)
    for line in (t or "").splitlines():
        m = ASSIGN_RE.match(line.strip())
        if not m:
            continue
        lhs = m.group(1).strip()
        rhs = normalize_expr(m.group(2))
        assigns.setdefault(lhs, set()).add(rhs)
    return assigns


def compare_assignments(sys_text: str, sw_text: str):
    """
    Compare assignment expressions as strings.
    Detects 1/10.3 vs 1/10.4 WITHOUT dividing.
    """
    sys_a = extract_assignments(sys_text)
    sw_a = extract_assignments(sw_text)

    mismatches = []

    for var, sys_exprs in sys_a.items():
        sw_exprs = sw_a.get(var, set())

        if not sw_exprs:
            mismatches.append(f"{var}: missing in SW")
            continue

        # if no overlap -> mismatch
        if sys_exprs.isdisjoint(sw_exprs):
            # keep output short
            sys_show = sorted(sys_exprs)[:1]
            sw_show = sorted(sw_exprs)[:1]
            mismatches.append(f"{var}: SYS={sys_show[0]} SW={sw_show[0]}")

    return mismatches


# ============================================================
# Debug-only similarity match (must not affect pass/fail)
# ============================================================

def _g1_extract_labels(text):
    return {
        m for m in re.findall(G1Config.LABEL_RE, text or "")
        if m.isdigit() and 0 < int(m) <= 377
    }


def _g1_cosine_similarity(a, b):
    c1, c2 = Counter((a or "").split()), Counter((b or "").split())
    inter = set(c1) & set(c2)
    num = sum(c1[x] * c2[x] for x in inter)
    den = math.sqrt(
        sum(v * v for v in c1.values()) *
        sum(v * v for v in c2.values())
    )
    return num / den if den else 0.0


def _g1_terminology_status(hlr_text, sys_text):
    hlr_text = hlr_text or ""
    sys_text = sys_text or ""
    for base, synonyms in G1Config.TERM_SYNONYMS.items():
        if base in hlr_text:
            if base in sys_text:
                return "Match"
            if any(s in sys_text for s in synonyms):
                return "Potential mismatch"
            return "Mismatch"
    return "Match"


def _g1_similarity(a, b):
    return _g1_cosine_similarity(norm(a), norm(b))


def _g1_find_best_sys_req(hlr_text_norm, sys_reqs):
    best_sid = None
    best_text = ""
    best_sim = 0.0

    for req in sys_reqs:
        sid = req.get("SYS_ID")
        stext_norm = req.get("TEXT_NORM") or normalize_text(req.get("TEXT_RAW") or req.get("TEXT", ""))
        if not sid or not stext_norm:
            continue

        sim = _g1_similarity(hlr_text_norm, stext_norm)
        if sim > best_sim:
            best_sid = sid
            best_text = stext_norm
            best_sim = sim

    return best_sid, best_text, best_sim


def _g1_check_single_hlr_against_sys(hlr_id, hlr_text, sys_reqs):
    hlr_text_norm = normalize_text(_canon_text(hlr_text))
    sid, stxt_norm, sim = _g1_find_best_sys_req(hlr_text_norm, sys_reqs)

    if not sid:
        return {
            "HLR_ID": hlr_id,
            "BEST_SYS_ID": "",
            "SIMILARITY": 0.0,
            "TERM_STATUS": "Mismatch",
            "LABEL_STATUS": "N/A",
            "LABEL_DEBUG": "",
            "OVERALL": G1Config.FAIL
        }

    term = _g1_terminology_status((hlr_text or "").lower(), (stxt_norm or "").lower())
    intent = "Match" if sim > G1Config.SIM_MATCH else "Mismatch"
    overall = G1Config.PASS if term == "Match" and intent == "Match" else G1Config.FAIL

    hlr_labels = _g1_extract_labels((hlr_text or "").lower())
    sys_labels = _g1_extract_labels((stxt_norm or "").lower())

    if not hlr_labels and not sys_labels:
        label_status = "N/A"
        label_debug = ""
    elif hlr_labels & sys_labels:
        label_status = "Match"
        common = sorted(list(hlr_labels & sys_labels), key=lambda x: int(x))
        label_debug = f"Common labels={common}"
    else:
        label_status = "Mismatch"
        missing = sorted(list(sys_labels - hlr_labels), key=lambda x: int(x)) if sys_labels else []
        extra = sorted(list(hlr_labels - sys_labels), key=lambda x: int(x)) if hlr_labels else []
        dbg_parts = []
        if missing:
            dbg_parts.append(f"Missing labels in SW={missing}")
        if extra:
            dbg_parts.append(f"Extra labels in SW={extra}")
        label_debug = "; ".join(dbg_parts)

    return {
        "HLR_ID": hlr_id,
        "BEST_SYS_ID": sid,
        "SIMILARITY": round(sim, 3),
        "TERM_STATUS": term,
        "LABEL_STATUS": label_status,
        "LABEL_DEBUG": label_debug,
        "OVERALL": overall
    }


# ============================================================
# MERGE HLRs (RAW + NORM)
# ============================================================

def merge_hlrs(hlr_reqs, hlr_ids):
    merged_ids = []
    raw_parts = []
    norm_parts = []
    table_parts = []

    hlr_map = {r["HLR_ID"]: r for r in hlr_reqs}

    for hid in hlr_ids:
        r = hlr_map.get(hid)
        if not r:
            continue
        merged_ids.append(hid)

        raw = (r.get("TEXT_RAW") or r.get("TEXT") or "").strip()
        if raw:
            raw_parts.append(f"[{hid}] {raw}")

        normed = (r.get("TEXT_NORM") or normalize_text(raw)).strip()
        if normed:
            norm_parts.append(f"[{hid}] {normed}")

        tt = (r.get("TABLE_TEXT") or "").strip()
        if tt:
            table_parts.append(f"[{hid} TABLE]\n{tt}")

    merged_raw = "\n\n".join(raw_parts)
    merged_norm = "\n\n".join(norm_parts)

    return {
        "HLR_ID": " + ".join(merged_ids) if merged_ids else "MISSING_HLR_DATA",
        "TEXT_RAW": merged_raw,
        "TEXT": merged_raw,
        "TEXT_NORM": merged_norm,
        "TABLE_TEXT": "\n\n".join(table_parts),
    }


# ============================================================
# MAIN CHECK
# ============================================================

def check_g1(system_reqs, hlr_reqs, trace_links):
    results = []
    sys_map = {r["SYS_ID"]: r for r in system_reqs}

    # GROUP TRACE LINKS BY SYS_ID
    sys_to_hlrs = defaultdict(list)
    for link in trace_links:
        sys_id = (link.get("SYS_ID", "") or "").strip()
        hlr_id = (link.get("HLR_ID", "") or "").strip()

        if not sys_id or not hlr_id:
            continue
        if sys_id.upper() == "NOT_TRACED":
            continue

        sys_to_hlrs[sys_id].append(hlr_id)

    # EVALUATE EACH SYS_ID AGAINST UNION(HLRs)
    for sys_id, hlr_ids in sys_to_hlrs.items():
        sys_req = sys_map.get(sys_id)

        if not sys_req:
            results.append({
                "SYS_ID": sys_id,
                "HLR_ID": " + ".join(hlr_ids),
                "G1_1_RESULT": G1Config.FAIL,
                "G1_2_RESULT": G1Config.FAIL,
                "STATE_RESULT": G1Config.FAIL,
                "INTENT_RESULT": G1Config.FAIL,
                "SYS_INTENTS": [],
                "HLR_INTENTS": [],
                "G1_RESULT": G1Config.FAIL,
                "REFINEMENT": "NOT_APPLICABLE",
                "COMMENT": "Missing system requirement data.",
                "DEBUG": "",
                "LLM_EXPLANATION": ""
            })
            continue

        merged_hlr_req = merge_hlrs(hlr_reqs, hlr_ids)

        if merged_hlr_req["HLR_ID"] == "MISSING_HLR_DATA":
            results.append({
                "SYS_ID": sys_id,
                "HLR_ID": " + ".join(hlr_ids),
                "G1_1_RESULT": G1Config.FAIL,
                "G1_2_RESULT": G1Config.FAIL,
                "STATE_RESULT": G1Config.FAIL,
                "INTENT_RESULT": G1Config.FAIL,
                "SYS_INTENTS": [],
                "HLR_INTENTS": [],
                "G1_RESULT": G1Config.FAIL,
                "REFINEMENT": "NOT_APPLICABLE",
                "COMMENT": "Trace links exist but HLR requirement text not found.",
                "DEBUG": "",
                "LLM_EXPLANATION": ""
            })
            continue

        # RAW texts (for accurate mismatch reporting)
        sys_text = _canon_text(sys_req.get("TEXT_RAW") or sys_req.get("TEXT", ""))
        sw_text = _canon_text(merged_hlr_req.get("TEXT_RAW") or merged_hlr_req.get("TEXT", ""))

        # 1) G1.1
        g1_1_result, g1_1_refinement, g1_1_comment = check_g1_1(sys_req, merged_hlr_req)

        # 2) G1.2
        g1_2_result, g1_2_comment = check_g1_2(merged_hlr_req)

        # 3) state diagram
        state_result = G1Config.PASS
        state_comment = ""

        # Make state-friendly copies
        sys_req_state = dict(sys_req)
        hlr_req_state = dict(merged_hlr_req)

        sys_text_state = _canon_for_state(sys_req.get("TEXT_RAW") or sys_req.get("TEXT", ""))
        hlr_text_state = _canon_for_state(merged_hlr_req.get("TEXT_RAW") or merged_hlr_req.get("TEXT", ""))

        sys_req_state["TEXT_RAW"] = sys_text_state
        sys_req_state["TEXT"]     = sys_text_state
        hlr_req_state["TEXT_RAW"] = hlr_text_state
        hlr_req_state["TEXT"]     = hlr_text_state

        if is_state_diagram_requirement(sys_req_state) and is_state_diagram_requirement(hlr_req_state):
            sys_model = extract_state_model(sys_req_state)
            hlr_model = extract_state_model(hlr_req_state)
            if sys_model and hlr_model:
                state_result, state_comment = compare_state_models(sys_model, hlr_model)

        # 4) intent
        intent_result, intent_comment = check_intent_consistency(sys_req, merged_hlr_req)
        intent_debug = get_intent_debug(sys_req, merged_hlr_req)

        evidence = {
            "threshold_mismatch": [],
            "threshold_missing": [],
            "else_missing": False,
            "elseif_missing": False,
            "formula_mismatch": [],
            "partial_coverage": None,
        }

        # FINAL decision
        final_result = G1Config.FAIL if G1Config.FAIL in (
            g1_1_result, g1_2_result, state_result, intent_result
        ) else G1Config.PASS

        # COMMENT (human-facing) = only the 4 checker comments
        final_comment = " | ".join(
            p for p in [
                g1_1_comment,
                g1_2_comment,
                state_comment,
                intent_comment
            ] if p
        )

        
        # --- OVERRIDE: fail the row if algorithm thresholds flagged issues in DEBUG ---
        has_thr_mismatch = bool(evidence.get("threshold_mismatch"))
        has_thr_missing  = bool(evidence.get("threshold_missing"))

        if final_result != G1Config.FAIL and (has_thr_mismatch or has_thr_missing):
            final_result = G1Config.FAIL
            extra_note = "Algorithm threshold mismatch/missing detected; see DEBUG."
            final_comment = (final_comment + " | " + extra_note) if final_comment else extra_note

        # --------------------------------------------------------
        # EXTRA: Algorithm branch + threshold mismatch + formula mismatch
        # Move these details to DEBUG (not COMMENT)
        # --------------------------------------------------------

        # Normalize branch counting
        sys_text_for_branch = _canon_text(sys_text)
        sw_text_for_branch  = _canon_text(sw_text)

        b_sys = count_branches(sys_text_for_branch)
        b_sw  = count_branches(sw_text_for_branch)

        algo_debug = []

        algo_debug.append(f"BRANCH_COUNTS SYS={b_sys} SW={b_sw}")

        # ELSE/ELSEIF deltas
        if b_sys["ELSE"] > b_sw["ELSE"]:
            algo_debug.append("ELSE_MISSING: SYS has ELSE; SW missing")
            evidence["else_missing"] = True
        if b_sys["ELSEIF"] > b_sw["ELSEIF"]:
            algo_debug.append(f"ELSEIF_MISSING: SYS={b_sys['ELSEIF']} SW={b_sw['ELSEIF']}")
            evidence["elseif_missing"] = True

        # threshold mismatch
        missing_thr, mismatched_thr = compare_thresholds(sys_text, sw_text)
        if mismatched_thr:
            pairs = ", ".join([f"{a}→{b}" for a, b in mismatched_thr])
            algo_debug.append(f"THRESHOLD_MISMATCH: SYS→SW ({pairs})")
            evidence["threshold_mismatch"] = mismatched_thr
        if missing_thr:
            algo_debug.append(f"ALGORITHM_BRANCH_MISSING: {missing_thr}")
            evidence["threshold_missing"] = missing_thr

        # formula mismatch (keeps 1/10.3 intact)
        fm = compare_assignments(sys_text, sw_text)
        if fm:
            algo_debug.append("FORMULA_MISMATCH: " + "; ".join(fm[:3]))
            evidence["formula_mismatch"] = fm[:3]

        # DEBUG column (never affects comment or llm)
        debug_str = ""
        myver_debug = _g1_check_single_hlr_against_sys(
            merged_hlr_req.get("HLR_ID", ""),
            merged_hlr_req.get("TEXT_NORM") or normalize_text(sw_text),
            system_reqs
        )
        if myver_debug.get("BEST_SYS_ID"):
            debug_str = (
                f"BEST_SYS_ID={myver_debug['BEST_SYS_ID']} "
                f"SIMILARITY={myver_debug['SIMILARITY']} "
                f"TERM_STATUS={myver_debug['TERM_STATUS']} "
                f"LABEL_STATUS={myver_debug.get('LABEL_STATUS', 'N/A')}"
            )
            if myver_debug.get("LABEL_DEBUG"):
                debug_str += f" | LABEL_DEBUG={myver_debug['LABEL_DEBUG']}"

        # Append algorithm extras to DEBUG (not to COMMENT)
        if algo_debug:
            debug_str = (" | ".join([debug_str] + algo_debug)).strip() if debug_str else " | ".join(algo_debug)

        # ------------------ OVERRIDE (Option B): Algorithm thresholds ------------------
        # Now that 'evidence' and 'debug_str' are fully populated, decide if we must flip to FAIL
        has_thr_mismatch = bool(evidence.get("threshold_mismatch"))
        has_thr_missing  = bool(evidence.get("threshold_missing"))

        # Safety fallback: if evidence wasn't set, scan the debug string
        dbg_upper = (debug_str or "").upper()
        if not has_thr_mismatch and "THRESHOLD_MISMATCH" in dbg_upper:
            has_thr_mismatch = True
        if not has_thr_missing and ("ALGORITHM_BRANCH_MISSING" in dbg_upper or "BRANCH_MISSING" in dbg_upper):
            has_thr_missing = True

        if final_result != G1Config.FAIL and (has_thr_mismatch or has_thr_missing):
            final_result = G1Config.FAIL
            extra_note = "Algorithm threshold mismatch/missing detected; see DEBUG."
            final_comment = (final_comment + " | " + extra_note) if final_comment else extra_note

        # --------------------------------------------------------
        # LLM EXPLANATION (ALWAYS FOR FAIL)
        # --------------------------------------------------------
        # llm_explanation = ""
        # if G1Config.LLM_ENABLED and final_result == G1Config.FAIL:
        #     llm_explanation = explain_mismatch(
        #         sys_text=sys_text,
        #         hlr_text=sw_text,
        #         issues=final_comment or "FAIL_WITHOUT_EXPLICIT_REASON",
        #         evidence=evidence,
        #         debug=debug_str,     # <-- include debug so your template can show it
        #     )

        # llm_reviewer = RequirementReviewerAgent()


        # llm_review = ""

        # llm_review = llm_reviewer.review(
        #     sys_text=sys_text,
        #     sw_text=sw_text
        # )


        results.append({
            "SYS_ID": sys_id,
            "HLR_ID": merged_hlr_req["HLR_ID"],
            "G1_1_RESULT": g1_1_result,
            "G1_2_RESULT": g1_2_result,
            "STATE_RESULT": state_result,
            "INTENT_RESULT": intent_result,
            "SYS_INTENTS": intent_debug.get("SYS_INTENTS", []),
            "HLR_INTENTS": intent_debug.get("HLR_INTENTS", []),
            "G1_RESULT": final_result,
            "REFINEMENT": g1_1_refinement,
            "COMMENT": final_comment,
            "DEBUG": debug_str,
            #"LLM_EXPLANATION": llm_review,
            #"LLM_REVIEW_RESULT": extract_llm_reviewer_verdict(llm_review)
        })

    return results