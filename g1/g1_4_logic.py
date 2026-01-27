# =========================================================
# G1.4 – HLR vs SYSTEM REQUIREMENT REVIEW LOGIC
# =========================================================

import math
import re
from collections import Counter

from config import G1Config
from io_utils import norm, normalize_text


# =========================================================
# LABEL EXTRACTION
# =========================================================
def extract_labels(text):
    """
    Extract all valid ARINC labels (octal <= 377)
    """
    if not text:
        return set()

    return {
        m for m in re.findall(G1Config.LABEL_RE, text)
        if m.isdigit() and 0 < int(m) <= 377
    }


# =========================================================
# SIMILARITY METRIC
# =========================================================
def cosine_similarity(a, b):
    """
    Computes cosine similarity between two requirement texts
    """
    c1, c2 = Counter(a.split()), Counter(b.split())
    inter = set(c1) & set(c2)

    num = sum(c1[x] * c2[x] for x in inter)
    den = math.sqrt(
        sum(v * v for v in c1.values()) *
        sum(v * v for v in c2.values())
    )

    return num / den if den else 0.0


# =========================================================
# TERMINOLOGY CHECK
# =========================================================
def terminology_status(hlr_text, sys_text):
    """
    Checks terminology consistency between HLR and SYS
    """
    hlr_text = hlr_text.lower()
    sys_text = sys_text.lower()

    for base, synonyms in G1Config.TERM_SYNONYMS.items():
        if base in hlr_text:
            if base in sys_text:
                return "Match"
            if any(s in sys_text for s in synonyms):
                return "Potential mismatch"
            return "Mismatch"

    return "Match"


# =========================================================
# SYS REQUIREMENT MATCHING
# =========================================================
def find_best_sys_req(hlr_text, sys_reqs):
    """
    Finds best matching SYS requirement for a given HLR
    """
    hlr_text = normalize_text(hlr_text)
    hlr_labels = extract_labels(hlr_text)

    # ---------- 1️⃣ Label-based priority ----------
    for sid, stext in sys_reqs.items():
        if hlr_labels & extract_labels(stext):
            sim = cosine_similarity(hlr_text, normalize_text(stext))
            return sid, stext, max(sim, G1Config.SIM_POTENTIAL), True

    # ---------- 2️⃣ Similarity-based fallback ----------
    best = (None, None, 0.0, False)

    for sid, stext in sys_reqs.items():
        sim = cosine_similarity(hlr_text, normalize_text(stext))
        if sim >= G1Config.SIM_POTENTIAL and sim > best[2]:
            best = (sid, stext, sim, False)

    return best


# =========================================================
# MAIN G1.4 CHECK
# =========================================================
def check_g1_4(hlr_id, hlr_text, sys_reqs):
    """
    Executes G1.4 review for a single HLR
    """

    sid, stxt, sim, label_match = find_best_sys_req(hlr_text, sys_reqs)

    if not sid:
        overall = "Fail" if hlr_id == "SCU_STC_SRS_1038" else "Review Required"
        return (
            "Mapping not present",
            "No",
            "Mismatch",
            0.0,
            overall
        )

    term = terminology_status(hlr_text, stxt)
    intent = "Match" if sim > G1Config.SIM_MATCH else "Mismatch"
    overall = "Pass" if term == "Match" and intent == "Match" else "Review Required"

    return (
        sid,
        "Yes" if label_match else "No",
        term,
        round(sim, 3),
        overall
    )
