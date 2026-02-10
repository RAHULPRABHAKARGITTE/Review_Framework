import subprocess                                   #Uses Python’s subprocess module to run an external command (here, invoking ollama on your machine)

_llm_cache = {}                                     #A simple in-memory cache. Keys are derived from the inputs; values are the generated explanations. This avoids repeated LLM calls for identical requests.

MODEL_NAME = "mistral"  # change if needed

#def explain_mismatch(sys_text: str, hlr_text: str, issues: str) -> str:
def explain_mismatch(sys_text, hlr_text, issues, debug, evidence):
    cache_key = (
        sys_text[:300],
        hlr_text[:300],
        issues,
        str(evidence),
        debug
    )

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]                    #return the same cached result(two calls differ only after the 300th character)

    def _shorten(text, limit=1200):             #trims long texts to 1200 chars
        text = text.strip()
        return text[:limit] + ("..." if len(text) > limit else "")

    prompt = f"""
    You are a safety-critical avionics requirements reviewer.
    You are explaining a requirements compliance failure.

    Explain the mismatch briefly and technically.

    SYSTEM REQUIREMENT:
    {_shorten(sys_text)}

    SOFTWARE REQUIREMENT:
    {_shorten(hlr_text)}

    DETECTED ISSUES:
    {issues}

    DEBUG INFO:
    {debug}

    EVIDENCE:
    {evidence}

    Explain:
    1. What exactly differs
    2. Where it differs (conditions, branches, clauses)
    3. Whether behavior is missing, altered, or split across requirements
    4. Do NOT infer new mismatches
    5. Do NOT evaluate expressions numerically

    Rules:
    - Max 5 sentences
    - No speculation
    - Be precise
    """
    
    try:
        result = subprocess.run(
            ["ollama", "run", MODEL_NAME],
            input=prompt,
            capture_output=True,                                 #Sends the prompt to stdin, captures stdout/stderr, sets UTF-8 encoding, and a timeout of 300 seconds.
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=400
        )
    except Exception as e:
        return f"LLM explanation failed: {e}"

    if result.returncode != 0 or not result.stdout.strip():
        return "LLM explanation unavailable (model not responding)."

    explanation = result.stdout.strip()
    _llm_cache[cache_key] = explanation
    print("LLM CALLED")


    return explanation