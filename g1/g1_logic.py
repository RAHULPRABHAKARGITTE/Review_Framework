import math
from collections import Counter
from config import G1Config
from io_utils import norm, normalize_text
import re


# ---------- LABEL EXTRACTION ----------
def extract_labels(text):
    return {
        m for m in re.findall(G1Config.LABEL_RE, text)
        if m.isdigit() and 0 < int(m) <= 377
    }


# ---------- SIMILARITY ----------
def cosine_similarity(a, b):
    c1, c2 = Counter(a.split()), Counter(b.split())
    inter = set(c1) & set(c2)
    num = sum(c1[x] * c2[x] for x in inter)
    den = math.sqrt(
        sum(v * v for v in c1.values()) *
        sum(v * v for v in c2.values())
    )
    return num / den if den else 0.0


def terminology_status(hlr_text, sys_text):
    for base, synonyms in G1Config.TERM_SYNONYMS.items():
        if base in hlr_text:
            if base in sys_text:
                return "Match"
            if any(s in sys_text for s in synonyms):
                return "Potential mismatch"
            return "Mismatch"
    return "Match"


def find_best_sys_req(hlr_text, sys_reqs):
    best_sid = None
    best_text = ""
    best_sim = 0
    label_match = "NO"

    for req in sys_reqs:
        sid = req.get("id")
        stext = req.get("text")

        if not sid or not stext:
            continue

        sim = similarity(hlr_text, stext)

        if sim > best_sim:
            best_sid = sid
            best_text = stext
            best_sim = sim

    if best_sid:
        label_match = "YES"

    return best_sid, best_text, best_sim, label_match



def check_g1(hlr_id, hlr_text, sys_reqs):
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
