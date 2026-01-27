import re
from config import G5Config

ENTITY_REGEX = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def extract_entities(text: str) -> set:
    entities = set()
    for e in ENTITY_REGEX.findall(text.upper()):
        if e not in G5Config.STOP_WORDS:
            entities.add(e)
    return entities


def count_shall(text: str) -> int:
    return len(re.findall(r"\bshall\b", text, re.IGNORECASE))


def extract_shall_clause(text: str) -> str:
    m = re.search(r"(.*?\bshall\b.*?)(\.|\n)",
                  text, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else text


def check_single_functionality(requirements):
    findings = []

    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "")

        if not req_id or not text:
            continue

        # Rule 1: multiple shall
        shall_count = count_shall(text)
        if shall_count > G5Config.MAX_SHALL_COUNT:
            findings.append((
                req_id,
                f"G_5.2-SF-01: Multiple 'shall' statements ({shall_count})"
            ))
            continue

        clause = extract_shall_clause(text)
        scope_entities = extract_entities(clause)

        if len(scope_entities) > 1:
            findings.append((
                req_id,
                "G_5.2-SF-02: Multiple functional entities in one requirement"
            ))

    return findings
