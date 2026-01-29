import subprocess

_llm_cache = {}

MODEL_NAME = "mistral"  # change if needed

def explain_mismatch(sys_text: str, hlr_text: str, issues: str) -> str:
    cache_key = (
        sys_text[:300],
        hlr_text[:300],
        issues
    )

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    def _shorten(text, limit=1200):
        text = text.strip()
        return text[:limit] + ("..." if len(text) > limit else "")

    prompt = f"""
    You are a safety-critical avionics requirements reviewer.

    Explain the mismatch briefly and technically.

    SYSTEM REQUIREMENT:
    {_shorten(sys_text)}

    SOFTWARE REQUIREMENT:
    {_shorten(hlr_text)}

    DETECTED ISSUES:
    {issues}

    Rules:
    - Max 5 sentences
    - No speculation
    - Be precise
    """


    try:
        result = subprocess.run(
            ["ollama", "run", MODEL_NAME],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300
        )
    except Exception as e:
        return f"LLM explanation failed: {e}"

    if result.returncode != 0 or not result.stdout.strip():
        return "LLM explanation unavailable (model not responding)."

    explanation = result.stdout.strip()
    _llm_cache[cache_key] = explanation
    print("LLM CALLED")


    return explanation