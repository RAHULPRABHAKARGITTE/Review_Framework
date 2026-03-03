from docx import Document
import pandas as pd
import re
import os
from collections import Counter

from io_utils import G2_IOUtils
from config import G2Config

def read_icd(icd_path):
    G2Config.ICD_TERMS, G2Config.ICD_UNITS

    doc = Document(icd_path)
    section = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if "Terminology" in text:
            section = "TERMS"
            continue
        if "Units" in text:
            section = "UNITS"
            continue

        if section == "TERMS" and ":" in text:
            term, meaning = text.split(":", 1)
            G2Config.ICD_TERMS[term.strip()] = meaning.strip()

        if section == "UNITS":
            units = re.findall(r"\b[a-zA-Zµ°]+\b", text)
            for u in units:
                G2Config.ICD_UNITS.add(u.strip().lower())

def normalize_unit_text(unit: str) -> str:
    b = "μs"
    if not unit:
        return ""
    return (
        unit
        .replace(b, "µs")   # Greek mu → micro sign
        .strip()
    )

def analyze_requirement_g2_3(req_id, text):
    issues = []

    # ---- Terminology check ----
    found_acronyms = set(G2Config.ACRONYM_REGEX.findall(text))
    for acronym in found_acronyms:
        if acronym in G2Config.EXCLUDED_WORDS:
            continue
        if acronym in G2Config.ICD_TERMS or acronym in G2Config.ACRONYM_WHITELIST:
            continue
        # Otherwise: Terminology violation
        issues.append({
            "Requirement_ID": req_id,
            "Category": "Terminology",
            "Violated_Content": acronym,
            "Explanation": (
                f"Acronym '{acronym}' is neither defined in ICD "
                f"nor present in the approved acronym list"
            )
        })

        # -----------------------------
        # UNIT CHECK (WITH SYNONYMS)
        # -----------------------------
        # --- normalize ICD units ONCE ---
        normalized_icd_units = {normalize_unit_text(u) for u in G2Config.ICD_UNITS}
        non_unit_tokens_norm = {t.lower() for t in G2Config.NON_UNIT_TOKENS} #new

        violating_units = [] #new

        # -------- UNIT_PATTERN --------
        for m in G2Config.UNIT_PATTERN.finditer(text):
            raw_unit = m.group(1)
            if not raw_unit:
                continue

            # Ignore NON_UNIT_TOKENS (case-insensitive)
            if raw_unit.lower() in non_unit_tokens_norm:#new
                continue

            raw_unit_norm = normalize_unit_text(raw_unit).strip().lower() #new :.strip().lower() for Hz

            if raw_unit_norm not in normalized_icd_units:
                violating_units.append(raw_unit_norm)

        # -------- NUMBER_TOKEN_PATTERN --------
        for m in G2Config.NUMBER_TOKEN_PATTERN.finditer(text):
            raw_unit = m.group(2)
            if not raw_unit:
                continue

            # normalize extracted word
            unit_norm = raw_unit.casefold()

            # ignore logical / non-unit words REGARDLESS OF CASE
            if unit_norm in G2Config.NON_UNIT_TOKENS_CANON:
                continue

            # normalize synonyms
            if unit_norm in G2Config.UNIT_SYNONYMS:
                unit_norm = G2Config.UNIT_SYNONYMS[unit_norm]

            # validate against ICD
            if unit_norm in normalized_icd_units:
                continue
            violating_units.append(unit_norm)

        # 🔹 Consolidate into ONE row per requirement
        if violating_units:
            counts = Counter(violating_units)
            violated_str = ", ".join(f"{u} (x{c})" for u, c in counts.items())

            issues.append({
                "Requirement_ID": req_id,
                "Category": "Unit",
                "Violated_Content": violated_str,
                "Explanation": "Unit(s) used are not defined in ICD"
            })

        return issues


def check_g2_3_and_generate_excel(requirements, output_folder):

    results = []

    for req_id, text in requirements.items():
        findings = analyze_requirement_g2_3(req_id, text)

        if findings is None:
            findings = []

        results.extend(findings)

    if not results:
        results.append({
            "Requirement_ID": "N/A",
            "Category": "PASS",
            "Violated_Content": "N/A",
            "Explanation": "No G2.3 violations found"
        })

    df = pd.DataFrame(results)

    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, "G2_3_Terminology_and_Units.xlsx")
    df.to_excel(output_path, index=False)

    return df, output_path




