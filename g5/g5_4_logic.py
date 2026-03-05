def check_ambiguous_words(requirements, keywords):
    findings = []
    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()
        if not req_id or not text:
            continue

        text_lower = text.lower()
        for word in keywords["ambiguous_words"]:
            if word in text_lower:
                findings.append((req_id, f"G_5.4-AW-01: Ambiguous word used ('{word}')"))

    return findings