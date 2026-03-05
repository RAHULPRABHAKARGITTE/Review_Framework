import os
from pathlib import Path
from docx import Document
from config import G5Config   # import the filename constant

# ============================================================
# Fallback logic functions (used if standards file not present)
# ============================================================
def g5_1_logic(req_text):
    return ["G 5.1: Needs semantic/LLM analysis for safety-critical aspects."]

def g5_2_logic(req_text):
    issues = []
    if " and " in req_text.lower() or " or " in req_text.lower():
        issues.append("G 5.2 violation: Multiple functionalities detected.")
    return issues

def g5_3_logic(req_text):
    return ["G 5.3: Needs semantic/LLM analysis for guideline compliance."]

def g5_4_logic(req_text):
    issues = []
    ambiguous_words = ["should", "may", "as appropriate"]
    for word in ambiguous_words:
        if word in req_text.lower():
            issues.append(f"G 5.4 violation: Ambiguous word '{word}' found.")
    return issues

def g5_5_logic(req_id, req_text):
    issues = []
    if not req_id or not req_id.startswith("REQ-"):
        issues.append("G 5.5 violation: Requirement ID not properly formatted.")
    return issues


# ============================================================
# Loader: decides between docx checkpoints or Python functions
# ============================================================
def load_checkpoints():
    # Explicit path to input folder
    base_dir = Path(r"D:\srs_review_tool 1\srs_review_tool\input")
    docx_path = base_dir / G5Config.STANDARDS_FILE

    checkpoints = {}
    if docx_path.exists():
        print(f"✅ Using checkpoints from: {docx_path}")
        doc = Document(docx_path)
        for para in doc.paragraphs:
            text = para.text.strip()
            if text.startswith("G"):
                parts = text.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    checkpoints[key] = value
    else:
        print(f"⚠ File not found at {docx_path}. Using Python logic functions instead.")
        checkpoints = {
            "G 5.1": g5_1_logic,
            "G 5.2": g5_2_logic,
            "G 5.3": g5_3_logic,
            "G 5.4": g5_4_logic,
            "G 5.5": g5_5_logic
        }
    return checkpoints