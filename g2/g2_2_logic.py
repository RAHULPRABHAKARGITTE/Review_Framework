import re
import pandas as pd
from docx import Document
import os
from collections import defaultdict, Counter
from io_utils import G2_IOUtils

from config import G2Config

# ------------------------------------------------------------------------------
# SINGLE‑REQUIREMENT: Ambiguity
# ------------------------------------------------------------------------------

def detect_ambiguity(req_id: str, text: str) -> list:
    """
    Ambiguity: ambiguous terms without numeric measurability in the same requirement.
    Returns list of ambiguous terms found.
    """
    issues = []
    for term in G2Config. AMBIGUOUS_TERMS:
        if G2Config.has_whole_term(text, term) and not G2Config.has_numeric_constraint(text):
            issues.append(term)
    return issues

# ------------------------------------------------------------------------------
# PAIRWISE: Contradiction (direct conflict)
#   Heuristics:
#   - Opposite polarity (shall vs shall not) on overlapping parameters/actions
#   - Same action + same parameter, but incompatible numeric thresholds (different cutoffs)
# ------------------------------------------------------------------------------

def detect_contradictions(requirements: dict) -> dict:
    """
    Returns dict:
      { Requirement_ID : [ list of contradiction explanations ] }
    Covers:
      1) Single‑requirement logical contradictions
      2) Single‑requirement numeric contradictions
      3) Cross‑requirement direct contradictions
    """

    from collections import defaultdict
    contradictions = defaultdict(list)

    # -------------------------------
    # PRE‑EXTRACT FEATURES
    # -------------------------------
    features = {}
    for rid, text in requirements.items():
        features[rid] = {
            "text": text,
            "polarity": G2Config.detect_polarity(text),
            "actions": G2Config.extract_actions(text),
            "params": G2Config.extract_parameters(text),
            "thresholds": G2Config.extract_thresholds(text),   # list of strings
            "conditions": G2Config.extract_conditions(text)
        }

    # ==============================================================
    # 1️⃣ SINGLE‑REQUIREMENT LOGICAL CONTRADICTIONS
    # ==============================================================
    for rid, f in features.items():
        txt = f["text"].upper()

        # PASS / FAIL
        if "PASS" in txt and "FAIL" in txt:
            contradictions[rid].append(
                "Single‑requirement contradiction: both PASS and FAIL outcomes are specified"
            )

        # TRUE / FALSE
        if "TRUE" in txt and "FALSE" in txt:
            contradictions[rid].append(
                "Single‑requirement contradiction: both TRUE and FALSE are specified"
            )

        # ENABLED / DISABLED
        if "ENABLED" in txt and "DISABLED" in txt:
            contradictions[rid].append(
                "Single‑requirement contradiction: both ENABLED and DISABLED are specified"
            )

    # ==============================================================
    # 2️⃣ SINGLE‑REQUIREMENT NUMERIC THRESHOLD CONTRADICTIONS
    #    (e.g. MRJ_SCU_STC_SRS_472)
    # ==============================================================
    for rid, f in features.items():
        thresholds = [t.lower() for t in f["thresholds"]]

        gt_vals = []
        lt_vals = []

        for t in thresholds:
            if ">" in t:
                gt_vals.append(t)
            if "<" in t:
                lt_vals.append(t)

        # If both > and < exist without a valid open interval
        if gt_vals and lt_vals:
            contradictions[rid].append(
                "Single‑requirement numeric contradiction: mutually exclusive timing/threshold constraints"
            )

    # ==============================================================
    # 3️⃣ CROSS‑REQUIREMENT CONTRADICTIONS (existing logic refined)
    # ==============================================================
    ids = list(features.keys())

    def action_family(actions: set) -> str:
        if "alert" in actions:
            return "alert"
        if "shutdown" in actions or "disable" in actions:
            return "shutdown"
        if "enable" in actions:
            return "enable"
        return "other"

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            r1, r2 = ids[i], ids[j]
            f1, f2 = features[r1], features[r2]

            # Same parameter context AND same action family
            if not (f1["params"] & f2["params"]):
                continue

            fam1 = action_family(f1["actions"])
            fam2 = action_family(f2["actions"])

            if fam1 == "other" or fam2 == "other" or fam1 != fam2:
                continue

            # Same condition (or no condition)
            cond_overlap = (
                f1["conditions"] & f2["conditions"]
                or (not f1["conditions"] and not f2["conditions"])
            )
            if not cond_overlap:
                continue

            # Opposite polarity
            if (
                f1["polarity"] in {"AFF", "NEG"}
                and f2["polarity"] in {"AFF", "NEG"}
                and f1["polarity"] != f2["polarity"]
            ):
                reason = (
                    "Direct contradiction: opposite polarity on same behavior and condition"
                )
                contradictions[r1].append(reason)
                contradictions[r2].append(reason)
                continue

            # Conflicting thresholds
            t1 = set(map(str.lower, f1["thresholds"]))
            t2 = set(map(str.lower, f2["thresholds"]))
            if t1 and t2 and not (t1 & t2):
                reason = (
                    "Direct contradiction: conflicting thresholds for same behavior and condition"
                )
                contradictions[r1].append(reason)
                contradictions[r2].append(reason)

    return contradictions

# ------------------------------------------------------------------------------
# PAIRWISE: Inconsistency (indirect conflict)
#   Heuristics:
#   - Overlapping parameter context with different actions (e.g., 'alert' vs 'shutdown')
#   - Overlapping conditions where one expects alert, another expects silent shutdown/log-suppression
# ------------------------------------------------------------------------------

def detect_inconsistencies(requirements: dict) -> dict:
    """
    Return dict: req_id -> list of reasons (each reason describes an inconsistency involving that req).
    Only flags when BOTH reqs have behavioral actions (not informational-only),
    AND share the same parameter context, but prescribe different action families.
    """
    from collections import defaultdict
    reasons = defaultdict(list)
    ids = list(requirements.keys())

    # Pre-extract features for all
    feats = {}
    for rid, text in requirements.items():
        feats[rid] = {
            "actions": G2Config.extract_actions(text),
            "params":  G2Config.extract_parameters(text),
            "thresholds": G2Config.extract_thresholds(text),
            "text": text
        }

    # Define "different actions" families
    def action_family(a: set) -> str:
        if "alert" in a: return "alert"
        if "shutdown" in a or "disable" in a: return "shutdown/disable"
        if "enable" in a: return "enable"
        if "log" in a or "not_log" in a: return "log/not_log"
        return "other"

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            r1, r2 = ids[i], ids[j]
            f1, f2 = feats[r1], feats[r2]

            # 🔒 1) Skip pairs if either requirement is informational-only
            if G2Config._has_info_only_nature(f1["text"]) or G2Config._has_info_only_nature(f2["text"]):
                continue

            # 🔒 2) Require overlapping parameter context
            if not (f1["params"] & f2["params"]):
                continue

            # 🔒 3) Require BOTH to have at least one recognized action
            if not f1["actions"] or not f2["actions"]:
                continue

            fam1, fam2 = action_family(f1["actions"]), action_family(f2["actions"])

            # If both are "other", treat as non-behavioral or out-of-scope
            if fam1 == "other" and fam2 == "other":
                continue

            # 🔒 4) Only flag when the families differ (e.g., alert vs shutdown/disable)
            if fam1 != fam2:
                # Optional refinement: If both have thresholds, annotate overlap
                reason = f"Different actions for overlapping context: '{fam1}' vs '{fam2}'"
                reasons[r1].append(reason)
                reasons[r2].append(reason)

            # 🔸 Special case: explicit alert vs not_log (silent behavior)
            if "alert" in f1["actions"] and "not_log" in f2["actions"]:
                reason = "Inconsistent behavior: one requires alert, the other suppresses logging (silent behavior)"
                reasons[r1].append(reason); reasons[r2].append(reason)
            if "alert" in f2["actions"] and "not_log" in f1["actions"]:
                reason = "Inconsistent behavior: one requires alert, the other suppresses logging (silent behavior)"
                reasons[r1].append(reason); reasons[r2].append(reason)

    return reasons

# ------------------------------------------------------------------------------
# DRIVER
# ------------------------------------------------------------------------------

def check_g2_2_and_generate_excel(srs_docx_path: str, output_folder: str):
    """
    Reads SRS DOCX via read_srs_requirements(), runs:
      - Ambiguity (single requirement)
      - Contradictions (pairwise)
      - Inconsistencies (pairwise)
    Produces a consolidated Excel with one row per (Requirement_ID, Category).
    """
    os.makedirs(output_folder, exist_ok=True)

    # Expect: { req_id: requirement_text }
    requirements = G2_IOUtils.read_srs_requirements(srs_docx_path, mode="AUTO")

    # --- Single requirement: Ambiguity ---
    ambiguity_rows = []
    for rid, text in requirements.items():
        amb = detect_ambiguity(rid, text)
        if amb:
            c = Counter(amb)
            violated = ", ".join(f"{t} (x{n})" for t, n in c.items())

            # Add the note only when 'high' or 'low' are in the detected ambiguous terms
            amb_lower = {t.lower() for t in c.keys()}
            needs_manual_note = bool({"high", "low"} & amb_lower)

            explanation = f"Ambiguous terms without numeric bounds: {violated}"
            if needs_manual_note:
                explanation += ". Manual verification is needed!!"

            ambiguity_rows.append({
                "Requirement_ID": rid,
                "Category": "Ambiguity",
                "Explanation": explanation
            })

    # --- Pairwise: Contradictions & Inconsistencies ---
    contradiction_map = detect_contradictions(requirements)
    inconsistency_map = detect_inconsistencies(requirements)

    contradiction_rows = []
    for rid, reasons in contradiction_map.items():
        if reasons:
            # Consolidate reasons per requirement
            uniq = list(dict.fromkeys(reasons))
            contradiction_rows.append({
                "Requirement_ID": rid,
                "Category": "Contradiction",
                "Explanation": " | ".join(uniq)
            })

    inconsistency_rows = []
    for rid, reasons in inconsistency_map.items():
        if reasons:
            uniq = list(dict.fromkeys(reasons))
            inconsistency_rows.append({
                "Requirement_ID": rid,
                "Category": "Inconsistency",
                "Explanation": " | ".join(uniq)
            })

    # --- Consolidate and write ---
    rows = ambiguity_rows + contradiction_rows + inconsistency_rows
    df = pd.DataFrame(rows, columns=["Requirement_ID", "Category", "Explanation"])

    if df.empty:
        # Provide a PASS artifact (auditable)
        df = pd.DataFrame([{
            "Requirement_ID": "N/A",
            "Category": "PASS",
            "Explanation": "No ambiguities, contradictions, or inconsistencies detected by rule-based screening."
        }])

    out_path = os.path.join(output_folder, "G2_2_Consistency.xlsx")
    df.to_excel(out_path, index=False)

    return df, out_path