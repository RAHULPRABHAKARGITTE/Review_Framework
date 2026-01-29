# nlp_normalize.py
import re

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)

def normalize_text(s: str) -> str:
    """Normalize general text (spacing, hyphens/underscores, articles)."""
    if not s:
        return ""
    s = s.strip()
    # unify hyphens; treat underscores as spaces for canonicalization
    s = re.sub(r"[\u2010-\u2015-]+", "-", s)
    s = s.replace("_", " ")
    # collapse whitespace, drop articles
    s = re.sub(r"\s+", " ", s)
    s = _ARTICLES.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_event(ev: str) -> str:
    """
    Canonicalize event phrases so variants align:
    - 'X is detected' / 'X = detected' -> 'X_DETECTED'
    - 'critical failure' -> 'CRITICAL_FAILURE'
    - remove articles; unify operators; collapse to underscores
    """
    if not ev:
        return ""
    ev = normalize_text(ev).upper()
    ev = ev.replace("==", "=").replace(" IS ", " = ").replace(" IN ", " = ")
    ev = ev.replace("( ", "(").replace(" )", ")")
    ev = re.sub(r"\b([A-Z0-9]+)\s*=\s*DETECTED\b", r"\1_DETECTED", ev)
    ev = re.sub(r"\bCRITICAL\s+FAILURE\b", "CRITICAL_FAILURE", ev)
    return ev.replace(" ", "_")