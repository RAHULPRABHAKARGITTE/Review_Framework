from config import G5Config


def check_ambiguous_words(requirements):
    findings = []

    for req in requirements:
        req_id = req.get("id")
        text = req.get("text", "").strip()

        if not req_id or not text:
            continue

        t = text.lower()

        for word in G5Config.AMBIGUOUS_WORDS:
            if word in t:
                findings.append((
                    req_id,
                    f"G_5.4-AW-01: Ambiguous word used ('{word}')"
                ))

    return findings
