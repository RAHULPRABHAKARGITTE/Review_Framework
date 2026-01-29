from collections import defaultdict

from g1.g1_1_logic import check_g1_1
from g1.g1_2_logic import check_g1_2
from config import G1Config

from g1.intent_consistency_logic import (
    check_intent_consistency,
    get_intent_debug
)

from g1.llm_explainer import explain_mismatch

from g1.state_diagram_logic import (
    is_state_diagram_requirement,
    extract_state_model,
    compare_state_models
)
import re

COND_RE = re.compile(r"\b(ELSE\s+IF|IF)\s*\((.*?)\)", re.IGNORECASE)
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

def extract_thresholds(text: str):
    thresholds = []
    for _, cond in COND_RE.findall(text or ""):
        nums = NUM_RE.findall(cond)
        thresholds.extend([float(n) for n in nums])
    return thresholds

def compare_thresholds(sys_text: str, sw_text: str, tol=1e-3):
    sys_thr = extract_thresholds(sys_text)
    sw_thr = extract_thresholds(sw_text)

    missing = []
    #mismatched = []

    for t in sys_thr:
        if not any(abs(t - x) <= tol for x in sw_thr):
            missing.append(t)

    # optional: mismatched detection requires pairing, which is harder,
    # but missing threshold detection already catches your 34.7 vs 37 case.

    return missing


# ------------------------------------------------------------
# YOUR VERSION IMPORTS (integrated safely)
# ------------------------------------------------------------
import math
from collections import Counter
from io_utils import norm, normalize_text


# ============================================================
# YOUR VERSION HELPERS (internal only)
# ============================================================

def _g1_extract_labels(text):
    return {
        m for m in re.findall(G1Config.LABEL_RE, text or "")
        if m.isdigit() and 0 < int(m) <= 377
    }

def _g1_label_status(hlr_text: str, sys_text: str):
    """
    Debug-only ARINC label overlap check.
    Returns:
      (status, debug_str)
    """
    hlr_labels = _g1_extract_labels(hlr_text)
    sys_labels = _g1_extract_labels(sys_text)

    if not hlr_labels and not sys_labels:
        return "N/A", ""

    if hlr_labels & sys_labels:
        common = sorted(list(hlr_labels & sys_labels), key=lambda x: int(x))
        return "Match", f"Common labels={common}"

    # mismatch case: no overlap
    missing = sorted(list(sys_labels - hlr_labels), key=lambda x: int(x)) if sys_labels else []
    extra = sorted(list(hlr_labels - sys_labels), key=lambda x: int(x)) if hlr_labels else []

    dbg_parts = []
    if missing:
        dbg_parts.append(f"Missing labels in SW={missing}")
    if extra:
        dbg_parts.append(f"Extra labels in SW={extra}")

    return "Mismatch", "; ".join(dbg_parts)


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
    """
    Use cosine similarity (your version) but keep normalized text.
    """
    return _g1_cosine_similarity(norm(a), norm(b))


def _g1_find_best_sys_req(hlr_text, sys_reqs):
    """
    sys_reqs expected format from io_utils.G1IOUtils:
    [
      {"SYS_ID": "...", "TEXT": "...", "TABLE_TEXT": "..."},
      ...
    ]
    """
    best_sid = None
    best_text = ""
    best_sim = 0.0

    for req in sys_reqs:
        sid = req.get("SYS_ID")
        stext = req.get("TEXT")

        if not sid or not stext:
            continue

        sim = _g1_similarity(hlr_text, stext)

        if sim > best_sim:
            best_sid = sid
            best_text = stext
            best_sim = sim

    return best_sid, best_text, best_sim


def _g1_check_single_hlr_against_sys(hlr_id, hlr_text, sys_reqs):
    """
    YOUR version check adapted to current SYS schema.
    Returns: dict with useful debug signals (does not affect pass/fail)
    """
    sid, stxt, sim = _g1_find_best_sys_req(hlr_text, sys_reqs)

    if not sid:
        overall = G1Config.FAIL
        return {
            "BEST_SYS_ID": "",
            "SIMILARITY": 0.0,
            "TERM_STATUS": "Mismatch",
            "LABEL_STATUS": "N/A",
            "LABEL_DEBUG": "",
            "OVERALL": overall
        }

    term = _g1_terminology_status((hlr_text or "").lower(), (stxt or "").lower())
    intent = "Match" if sim > G1Config.SIM_MATCH else "Mismatch"

    # ✅ label check now used
    label_status, label_debug = _g1_label_status(hlr_text or "", stxt or "")

    overall = G1Config.PASS if (term == "Match" and intent == "Match") else G1Config.FAIL

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
# EXISTING PROJECT LOGIC (unchanged output contract)
# ============================================================

def merge_hlrs(hlr_reqs, hlr_ids):
    """
    Merge multiple HLR requirements into ONE combined pseudo requirement.
    This enables SYS vs UNION(HLRs) compliance check.
    """
    merged_text_parts = []
    merged_table_parts = []
    merged_ids = []

    hlr_map = {r["HLR_ID"]: r for r in hlr_reqs}

    for hid in hlr_ids:
        r = hlr_map.get(hid)
        if not r:
            continue

        merged_ids.append(hid)

        t = (r.get("TEXT") or "").strip()
        if t:
            merged_text_parts.append(f"[{hid}] {t}")

        tt = (r.get("TABLE_TEXT") or "").strip()
        if tt:
            merged_table_parts.append(f"[{hid} TABLE]\n{tt}")

    return {
        "HLR_ID": " + ".join(merged_ids) if merged_ids else "MISSING_HLR_DATA",
        "TEXT": "\n\n".join(merged_text_parts),
        "TABLE_TEXT": "\n\n".join(merged_table_parts),
    }


def check_g1(system_reqs, hlr_reqs, trace_links):
    """
    DO NOT change signature or output schema.
    """
    results = []

    sys_map = {r["SYS_ID"]: r for r in system_reqs}

    # ------------------------------------------------------------
    # GROUP TRACE LINKS BY SYS_ID
    # ------------------------------------------------------------
    sys_to_hlrs = defaultdict(list)
    for link in trace_links:
        sys_id = (link.get("SYS_ID", "") or "").strip()
        hlr_id = (link.get("HLR_ID", "") or "").strip()

        if not sys_id or not hlr_id:
            continue

        if sys_id.upper() == "NOT_TRACED":
            continue

        sys_to_hlrs[sys_id].append(hlr_id)

    # ------------------------------------------------------------
    # EVALUATE EACH SYS_ID AGAINST UNION(HLRs)
    # ------------------------------------------------------------
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
                "G1_RESULT": G1Config.FAIL,
                "REFINEMENT": "NOT_APPLICABLE",
                "COMMENT": "Missing system requirement data.",
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
                "G1_RESULT": G1Config.FAIL,
                "REFINEMENT": "NOT_APPLICABLE",
                "COMMENT": "Trace links exist but HLR requirement text not found.",
                "LLM_EXPLANATION": ""
            })
            continue

        # --------------------------------------------------------
        # 1) G1.1 COMPLIANCE
        # --------------------------------------------------------
        g1_1_result, g1_1_refinement, g1_1_comment = check_g1_1(
            sys_req, merged_hlr_req
        )

        # --------------------------------------------------------
        # 2) G1.2 CLARITY
        # --------------------------------------------------------
        g1_2_result, g1_2_comment = check_g1_2(merged_hlr_req)

        # --------------------------------------------------------
        # 3) STATE DIAGRAM COMPARISON
        # --------------------------------------------------------
        state_result = G1Config.PASS
        state_comment = ""

        if is_state_diagram_requirement(sys_req) and is_state_diagram_requirement(merged_hlr_req):
            sys_model = extract_state_model(sys_req)
            hlr_model = extract_state_model(merged_hlr_req)

            if sys_model and hlr_model:
                state_result, state_comment = compare_state_models(sys_model, hlr_model)

        # --------------------------------------------------------
        # 4) INTENT CONSISTENCY CHECK
        # --------------------------------------------------------
        intent_result, intent_comment = check_intent_consistency(sys_req, merged_hlr_req)
        intent_debug = get_intent_debug(sys_req, merged_hlr_req)

        # --------------------------------------------------------
        # FINAL DECISION (unchanged)
        # --------------------------------------------------------
        final_result = G1Config.FAIL if G1Config.FAIL in (
            g1_1_result,
            g1_2_result,
            state_result,
            intent_result
        ) else G1Config.PASS

        final_comment = " | ".join(
            c for c in [g1_1_comment, g1_2_comment, state_comment, intent_comment] if c
        )

        missing_thr = compare_thresholds(sys_req.get("TEXT",""), merged_hlr_req.get("TEXT",""))
        if missing_thr:
            final_comment = (final_comment + " | " if final_comment else "") + \
                            f"ALGORITHM_BRANCH_MISSING: Missing thresholds in SW: {missing_thr}"



        # --------------------------------------------------------
        # CHECK If I ignore traceability grouping / intent logic and just compare requirement text similarity, what system requirement does this HLR seem to align with?
        # --------------------------------------------------------
        myver_debug = _g1_check_single_hlr_against_sys(
            merged_hlr_req.get("HLR_ID", ""),
            merged_hlr_req.get("TEXT", ""),
            system_reqs
        )

        if myver_debug.get("BEST_SYS_ID"):
            final_comment = (final_comment + " | " if final_comment else "") + \
                            f"BEST_SYS_ID={myver_debug['BEST_SYS_ID']} " \
                            f"SIMILARITY={myver_debug['SIMILARITY']} " \
                            f"TERM_STATUS={myver_debug['TERM_STATUS']} " \
                            f"LABEL_STATUS={myver_debug.get('LABEL_STATUS','N/A')}"
            
        if myver_debug.get("LABEL_DEBUG"):
            final_comment = (final_comment + " | " if final_comment else "") + \
                            f"LABEL_DEBUG={myver_debug['LABEL_DEBUG']}"

        # --------------------------------------------------------
        # LLM EXPLANATION (unchanged)
        # --------------------------------------------------------
        llm_explanation = ""
        if final_result == G1Config.FAIL and final_comment:
            llm_explanation = explain_mismatch(
                sys_req.get("TEXT", ""),
                merged_hlr_req.get("TEXT", ""),
                final_comment
            )

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
            "LLM_EXPLANATION": llm_explanation
        })

    return results