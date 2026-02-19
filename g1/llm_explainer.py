# import subprocess                                   #Uses Python’s subprocess module to run an external command (here, invoking ollama on your machine)

# _llm_cache = {}                                     #A simple in-memory cache. Keys are derived from the inputs; values are the generated explanations. This avoids repeated LLM calls for identical requests.

# MODEL_NAME = "mistral"  # change if needed

# #def explain_mismatch(sys_text: str, hlr_text: str, issues: str) -> str:
# def explain_mismatch(sys_text, hlr_text, issues, debug, evidence):
#     cache_key = (
#         sys_text[:300],
#         hlr_text[:300],
#         issues,
#         str(evidence),
#         debug
#     )

#     if cache_key in _llm_cache:
#         return _llm_cache[cache_key]                    #return the same cached result(two calls differ only after the 300th character)

#     def _shorten(text, limit=1200):             #trims long texts to 1200 chars
#         text = text.strip()
#         return text[:limit] + ("..." if len(text) > limit else "")

# #purpose and intended behaviour
# #{..} inputs can be reusable - prompt template
#     prompt = f"""
#     You are a safety-critical avionics requirements reviewer.
#     You are explaining a requirements compliance failure.

#     Explain the mismatch briefly and technically.

#     SYSTEM REQUIREMENT:
#     {_shorten(sys_text)}

#     SOFTWARE REQUIREMENT:
#     {_shorten(hlr_text)}

#     DETECTED ISSUES:
#     {issues}

#     DEBUG INFO:
#     {debug}

#     EVIDENCE:
#     {evidence}

#     Explain:
#     1. What exactly differs
#     2. Where it differs (conditions, branches, clauses)
#     3. Whether behavior is missing, altered, or split across requirements
#     4. Do NOT infer new mismatches
#     5. Do NOT evaluate expressions numerically

#     Rules:
#     - Max 5 sentences
#     - No speculation
#     - Be precise
#     """
    
#     try:
#         result = subprocess.run(
#             ["ollama", "run", MODEL_NAME],
#             input=prompt,
#             capture_output=True,                                 #Sends the prompt to stdin, captures stdout/stderr, sets UTF-8 encoding, and a timeout of 300 seconds.
#             text=True,
#             encoding="utf-8",
#             errors="replace",
#             timeout=400
#         )
#     except Exception as e:
#         return f"LLM explanation failed: {e}"

#     if result.returncode != 0 or not result.stdout.strip():
#         return "LLM explanation unavailable (model not responding)."

#     explanation = result.stdout.strip()
#     _llm_cache[cache_key] = explanation
#     print("LLM CALLED")


#     return explanation

# import subprocess
# import hashlib

# class RequirementIntentAgent:
#     """
#     Single autonomous LLM agent.
#     Must be independent of G1 findings, debug, or comments.
#     """

#     MODEL_NAME = "mistral"

#     def __init__(self):
#         self._cache = {}

#     def _key(self, sys_text: str, sw_text: str) -> str:
#         return hashlib.sha256(
#             (sys_text.strip() + "||" + sw_text.strip()).encode("utf-8")
#         ).hexdigest()

#     def _shorten(self, text: str, limit: int = 2000) -> str:
#         t = (text or "").strip()
#         return t[:limit] + ("..." if len(t) > limit else "")

#     def analyze(self, sys_text: str, sw_text: str) -> str:
#         """
#         Returns HUMAN-READABLE explanation with explicit intent decision.
#         """

#         key = self._key(sys_text, sw_text)
#         if key in self._cache:
#             return self._cache[key]

#         prompt = f"""
# You are an autonomous safety-critical requirements review agent.

# Your task:
# - Compare SYSTEM and SOFTWARE requirements
# - Identify differences, if any
# - Decide whether they express the SAME TECHNICAL INTENT

# SYSTEM REQUIREMENT:
# {self._shorten(sys_text)}

# SOFTWARE REQUIREMENT:
# {self._shorten(sw_text)}

# Rules:
# Rules:
# - Do NOT speculate or infer unstated intent
# - Compare structural control flow explicitly
# - If one requirement contains IF / ELSE IF / ELSE logic:
#   * Verify that equivalent branches exist in the other requirement
#   * Missing ELSE or ELSE IF MUST be reported as a logic difference
# - Differences in control-flow completeness change intent
# - Be conservative (avoid false PASS)


# Output format (MANDATORY):

# Technical Difference Analysis

# Numeric differences:
# <text or "None identified">

# Logic / condition differences:
# <text or "None identified">

# State / mode differences:
# <text or "None identified">

# Behavioral differences:
# <text or "None identified">

# Scope or applicability differences:
# <text or "None identified">

# Intent assessment:
# <INTENT_EQUIVALENT | INTENT_PARTIALLY_EQUIVALENT | INTENT_DIFFERENT | INTENT_UNCLEAR>

# Summary:
# <single-line technical verdict>
# """

#         try:
#             result = subprocess.run(
#                 ["ollama", "run", self.MODEL_NAME],
#                 input=prompt,
#                 capture_output=True,
#                 text=True,
#                 encoding="utf-8",
#                 timeout=400
#             )
#         except Exception as e:
#             return f"LLM execution failed: {e}"

#         if result.returncode != 0 or not result.stdout.strip():
#             return "LLM unavailable."

#         output = result.stdout.strip()
#         self._cache[key] = output
#         return output

import subprocess
import hashlib
import re


class RequirementReviewerAgent:
    """
    Independent LLM reviewer.
    Produces a human-style PASS / FAIL / REVIEW per row.
    """

    MODEL_NAME = "mistral:7b-instruct"

    def __init__(self):
        self._cache = {}

    # -------------------------
    # Internal helpers
    # -------------------------
    def _key(self, sys_text: str, sw_text: str) -> str:
        return hashlib.sha256(
            (sys_text.strip() + "||" + sw_text.strip()).encode("utf-8")
        ).hexdigest()

    def _shorten(self, text: str, limit: int = 2000) -> str:
        t = (text or "").strip()
        return t[:limit] + ("..." if len(t) > limit else "")

    # -------------------------
    # Main reviewer entrypoint
    # -------------------------
    def review(self, sys_text: str, sw_text: str) -> str:
        """
        Reviewer-style assessment of system vs software requirement.
        ALWAYS returns output (never empty).
        """

        key = self._key(sys_text, sw_text)
        if key in self._cache:
            return self._cache[key]
        
        prompt = f"""
        You are an independent DO-178C avionics certification reviewer.

        Your job is to determine whether the SOFTWARE requirement(s)
        fully and exactly implement the SYSTEM requirement.

        You are NOT allowed to assume equivalence.
        You must prove coverage.

        Default assumption is NON-EQUIVALENCE.
        PASS requires explicit structural proof.

        ---------------------------------------------------------------------

        SYSTEM REQUIREMENT:
        {self._shorten(sys_text, 1200)}

        ---------------------------------------------------------------------

        SOFTWARE REQUIREMENT:
        {self._shorten(sw_text, 1200)}

        ---------------------------------------------------------------------

        STRICT RULES

        - Missing behavior → FAIL
        - Missing IF / ELSE branch → FAIL
        - Numeric difference → FAIL
        - Timing difference → FAIL
        - Identifier difference → FAIL
        - Polarity inversion → FAIL
        - If uncertain → FAIL
        - Implicit implementation is NOT acceptable
        - More detail is allowed; omission is NOT

        ---------------------------------------------------------------------

        MANDATORY ANALYSIS

        1. Break SYSTEM into explicit required behaviors.
        2. For EACH SYSTEM behavior:
        - Quote the exact SOFTWARE sentence that implements it.
        3. If any SYSTEM behavior cannot be mapped to a quoted SOFTWARE sentence:
        → FAIL immediately.

        Do NOT infer intent.
        Do NOT rewrite requirements.
        Compare expressions textually.
        Do NOT evaluate formulas numerically.

        ---------------------------------------------------------------------

        OUTPUT FORMAT (EXACT)

        System Behaviors:
        - ...

        Coverage Mapping:
        - SYSTEM: ...
        SOFTWARE: "..."

        Overall Verdict: PASS | FAIL | REVIEW

        Reason:
        One or two technical sentences only.
        """

        

        try:
            result = subprocess.run(
                ["ollama", "run", self.MODEL_NAME],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=400
            )
        except Exception:
            return (
                "Overall Verdict: FAIL\n"
                "Rationale: LLM execution timeout or failure."
            )


        if result.returncode != 0 or not result.stdout.strip():
            return "LLM reviewer unavailable."

        output = result.stdout.strip()
        self._cache[key] = output
        print("LLM CALLED")
        return output


# -------------------------------------------------
# Utility: extract reviewer verdict for Excel row
# -------------------------------------------------
REVIEW_VERDICT_RE = re.compile(
    r"Overall Verdict:\s*(PASS|FAIL|REVIEW)",
    re.IGNORECASE
)

def extract_llm_reviewer_verdict(text: str) -> str:
    """
    Extracts PASS / FAIL / REVIEW from LLM output.
    Safe default = REVIEW.
    """
    if not text:
        return "REVIEW"

    m = REVIEW_VERDICT_RE.search(text)
    if not m:
        return "REVIEW"

    return m.group(1).upper()
