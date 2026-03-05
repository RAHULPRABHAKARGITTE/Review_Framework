import re
ENTITY_REGEX = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")

def extract_entities(text: str, stop_words: set) -> set:
    candidates = ENTITY_REGEX.findall(text.upper())
    return {c for c in candidates if ("_" in c or re.search(r"\d$", c)) and c not in stop_words}

def count_shall(text: str) -> int:
    return len(re.findall(r"\bshall\b", text, re.IGNORECASE))

def extract_shall_clause(text: str) -> str:
    match = re.search(r"(.*?\bshall\b.*?)(\.|\n)", text, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else text

def extract_write_targets(text: str, stop_words: set) -> set:
    targets = set()
    for line in text.splitlines():
        if "=" in line:
            lhs = line.split("=", 1)[0]
            targets |= extract_entities(lhs, stop_words)
    return targets

def is_derived_entity(scope: str, target: str) -> bool:
    return scope in target

def check_single_functionality(requirements, keywords):
    findings = []
    stop_words = keywords["stop_words"]

    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "")
        if not req_id or not text:
            continue

        shall_count = count_shall(text)
        if shall_count > keywords["max_shall_count"]:
            findings.append((req_id, f"G_5.2: Single functionality violation. Found {shall_count} 'shall' statements."))
            continue

        shall_clause = extract_shall_clause(text)
        scope_entities = extract_entities(shall_clause, stop_words)
        if not scope_entities:
            continue

        write_targets = extract_write_targets(text, stop_words)
        if not write_targets:
            continue

        if len(scope_entities) > 1 and write_targets.issubset(scope_entities):
            continue

        allowed_targets = {t for t in write_targets for s in scope_entities if is_derived_entity(s, t)}
        illegal_targets = write_targets - scope_entities - allowed_targets

        if illegal_targets:
            findings.append((req_id, f"G_5.2: Single functionality violation. Illegal targets: {', '.join(illegal_targets)}"))

    return findings