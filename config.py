import re
import os
import pandas as pd
from docx import Document
from pathlib import Path

# =========================================================
# SHARED REGEX
# =========================================================
REQ_ID_RE = re.compile(r"(SCU[_\- ]STC[_\- ]SRS[_\- ]\d+)")


# =========================================================
# COMMON CONFIG (ONE AND ONLY ONE)
# =========================================================
class CommonConfig:
    BASE_INPUT = "inputs"
    BASE_OUTPUT = "outputs"

    SOFTWARE_REQ_FILE = "software_requirements.docx"
    SYSTEM_REQ_FILE   = "system_requirements.docx"
    HLR_FILE          = "high_level_requirements.docx"
    HARDWARE_DS_FILE  = "hardware_datasheet.docx"


    DEFAULT_CPU_MHZ   = 100
    DEFAULT_RAM_KB    = 128
    DEFAULT_FLASH_KB  = 512

# =========================================================
# G2 CONFIG
# =========================================================
class G2Config:
    # -----------------------------
    # GLOBAL ICD MACROS
    # -----------------------------
    BASE_DIR = Path(__file__).resolve().parent  # Review_Framework
    INPUT_DIR = BASE_DIR / "inputs"
    OUTPUT_DIR = BASE_DIR / "outputs"
    G2_SRS      = str(INPUT_DIR /"SW-SR-0001_Updated_3.docx" )
    ICD         = str(INPUT_DIR /"G2_SCU_ICD.docx")
    G2_OUTPUT   = os.path.join(str(OUTPUT_DIR/"G2_Result.xlsx"))

    # ************ G2.2 : Start ************

    # Ambiguous terms (single-req ambiguity). We only flag if NO numeric constraint exists in the same requirement.
    AMBIGUOUS_TERMS = [
        "high", "low", "slow", "significant","quickly",
        "immediately", "acceptable", "reasonable", "periodically"
    ]

    # Actions for contradiction/inconsistency reasoning
    ACTION_ALERT     = ["alert", "indicate", "raise alert", "raise alarm", "signal alert"]
    ACTION_SHUTDOWN  = ["shutdown", "shut down", "power down"]
    ACTION_DISABLE   = ["disable", "inhibit", "suppress"]
    ACTION_ENABLE    = ["enable", "allow", "permit"]
    ACTION_LOG       = ["log", "record"]
    ACTION_NOT_LOG   = ["not log", "suppress log"]

    # Polarity (for shall vs shall not)
    NEGATION_PHRASES = [
        r"\bshall not\b",
        r"\bmust not\b",
        r"\bshould not\b",
        r"\bshall never\b",
        r"\bno[t]?\b"  # simple 'not' guard
    ]

    AFFIRMATION_PHRASES = [
        r"\bshall\b",
        r"\bmust\b",
        r"\bshould\b"
    ]

    # Parameter keywords to help pairwise checks (extend as needed)
    PARAMETER_KEYWORDS = [
        "temperature", "temp", "cabin", "pressure", "speed", "airspeed", "bit", "watchdog",
        "rigging", "offset", "latency", "delay", "response", "message", "label", "data"
    ]

    # ------------------------------------------------------------------------------
    # REGEX PATTERNS (numbers, units, comparators)
    # ------------------------------------------------------------------------------

    # Numbers with units (general)
    NUMBER_UNIT_PATTERN = re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:°[cC]|deg(?:rees)?|ms|us|µs|μs|ns|s|sec|seconds|hz|kHz|KHz|MHz|mbps|kbps|bps|kts|%|bytes?)\b",
        flags=re.IGNORECASE
    )

    # Comparators / thresholds
    COMPARATOR_PATTERN = re.compile(
        r"(?:>=|<=|>|<|=)\s*\d+(?:\.\d+)?\s*(?:°[cC]|deg(?:rees)?|ms|us|µs|μs|ns|s|sec|seconds|hz|kHz|KHz|MHz|mbps|kbps|bps|kts|%|bytes?)?",
        flags=re.IGNORECASE
    )

    # Treat these verbs as "informational" (non-behavioral). Extend if needed.
    INFO_ONLY_VERBS = [
        "compute", "calculate", "derive", "determine", "read", "sample", "measure",
        "convert", "map", "scale", "update", "store", "load", "retrieve", "copy",
        "set variable", "write to", "assign", "evaluate"
    ]

    def _has_info_only_nature(text: str) -> bool:
        """
        Returns True if the requirement text appears informational-only (no behavior).
        This avoids flagging data-derivation/setup steps as inconsistencies.
        """
        t = text.lower()
        # If it has any of the known info-only verbs and does NOT contain behavioral actions,
        # consider it informational.
        info_hit = any(re.search(rf"\b{re.escape(v)}\b", t) for v in G2Config.INFO_ONLY_VERBS)

        # Reuse your existing extract_actions() if available:
        # actions = extract_actions(text)
        # If you’d rather keep it local without dependency, you can approximate:
        behavioral = any(re.search(p, t) for p in [
            r"\balert\b", r"\bshutdown\b", r"\bshut\s*down\b", r"\benable\b",
            r"\bdisable\b", r"\binhibit\b", r"\blog\b", r"\bnot\s+log\b"
        ])

        return info_hit and not behavioral

    def is_informational_only(text: str) -> bool:
        t = text.lower()
        info = any(re.search(rf"\b{re.escape(v)}\b", t) for v in G2Config.INFO_ONLY_VERBS)
        behavioral = any(re.search(p, t) for p in [
            r"\balert\b", r"\bshutdown\b", r"\bshut\s*down\b",
            r"\benable\b", r"\bdisable\b", r"\binhibit\b",
            r"\blog\b", r"\bnot\s+log\b"
        ])
        return info and not behavioral

    # Extract coarse-grained condition signatures
    COND_HEAD = re.compile(r"\b(if|when|while|during|under|provided that)\b", re.IGNORECASE)
    COND_SPLIT = re.compile(r"\b(then|;|\.|\n)\b", re.IGNORECASE)

    def extract_conditions(text: str) -> set:
        """
        Return a set of normalized 'condition' snippets (IF/WHEN/WHILE/DURING/UNDER/PROVIDED THAT ... [THEN|end]).
        Used only to assert 'same condition' / 'overlap' presence.
        """
        low = text.lower()
        conds = set()
        pos = 0
        while True:
            m = G2Config.COND_HEAD.search(low, pos)
            if not m:
                break
            start = m.start()
            m2 = G2Config.COND_SPLIT.search(low, m.end())
            end = m2.start() if m2 else len(low)
            snippet = low[start:end]
            # normalize: collapse spaces
            snippet = re.sub(r"\s+", " ", snippet).strip()
            conds.add(snippet)
            pos = end
        return conds

    # Word boundary helper (with hyphen/space tolerance)
    def make_term_regex(term: str) -> re.Pattern:
        term = term.strip()
        if "-" in term:
            parts = [re.escape(p) for p in term.split("-") if p]
            pattern = r"\b" + r"[-\s]?".join(parts) + r"\b"
        else:
            pattern = r"\b" + re.escape(term) + r"\b"
        return re.compile(pattern, re.IGNORECASE)

    def has_whole_term(text: str, term: str) -> bool:
        return G2Config.make_term_regex(term).search(text) is not None

    def has_numeric_constraint(text: str) -> bool:
        """ True if the requirement contains any numeric measurability (units/thresholds/cycles). """
        return bool(G2Config.NUMBER_UNIT_PATTERN.search(text) or G2Config.COMPARATOR_PATTERN.search(text) or G2Config.CYCLES_PATTERN.search(text))

    def detect_polarity(text: str) -> str:
        """ Return 'NEG' if negated (shall not), 'AFF' if affirmative (shall), else 'UNK'. """
        for pat in G2Config.NEGATION_PHRASES:
            if re.search(pat, text, flags=re.IGNORECASE):
                return "NEG"
        for pat in G2Config.AFFIRMATION_PHRASES:
            if re.search(pat, text, flags=re.IGNORECASE):
                return "AFF"
        return "UNK"

    def extract_actions(text: str) -> set:
        """ Extract coarse action tokens present in text (alert, shutdown, enable, disable, log). """
        actions = set()
        low = text.lower()

        def any_in(words): return any(G2Config.make_term_regex(w).search(low) for w in words)

        if any_in(G2Config.ACTION_ALERT):    actions.add("alert")
        if any_in(G2Config.ACTION_SHUTDOWN): actions.add("shutdown")
        if any_in(G2Config.ACTION_DISABLE):  actions.add("disable")
        if any_in(G2Config.ACTION_ENABLE):   actions.add("enable")
        if any_in(G2Config.ACTION_LOG):      actions.add("log")
        # crude not-log (negated form)
        if re.search(r"\bnot\s+log\b", low) or any_in(G2Config.ACTION_NOT_LOG):
            actions.add("not_log")
        return actions

    def extract_parameters(text: str) -> set:
        """ Extract coarse parameter tokens present in text. """
        low = text.lower()
        params = set()
        for kw in G2Config.PARAMETER_KEYWORDS:
            if G2Config.has_whole_term(low, kw):
                params.add(kw)
        return params

    def extract_thresholds(text: str) -> list:
        """ Return a list of threshold strings (e.g., '>50 °C', '>= 100 ms', '65536 cycles'). """
        vals = []
        vals.extend(m.group(0).strip() for m in G2Config.COMPARATOR_PATTERN.finditer(text))
        vals.extend(m.group(0).strip() for m in G2Config.CYCLES_PATTERN.finditer(text))
        return vals

    # ************ G2.2 : End *************

    # ************ G2.3 : Start ************
    ICD_TERMS = {}          # Populated from ICD.docx
    ICD_UNITS = set()       # Populated from ICD.docx

    # Pattern: number + token (candidate unit)
    NUMBER_TOKEN_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*([a-zA-Zµ°]+)\b")

    # Acceptable non-unit tokens after numbers
    NON_UNIT_TOKENS = [
        "not", "used", "and", "ARINC", "Device", "XINTF", "in", "receiver", "times",
        "are", "xFF", "bytes", "do", "to", "LRVDT", "ratiometric", "into", "of",
        "condition", "before", "when", "Justification", "x", "ADC", "kHz", "us",
        "steps", "channels", "samples", "Health", "Rigging", "because", "after",
        "if", "or", "Reasonableness", "devices", "bus", "control", "ms", "nd",
        "rd", "st", "th", "bits", "Monitoring", "ie", "Pilot", "Towing", "kts",
        "Monitor", "have", "data", "is", "Rudder", "deg", "Bit", "shows",
        "SOV", "psi", "SDI", "Where", "e", "Note", "with", "means", "received",
        "LVDT", "using", "bit", "shift", "ELSE", "calculated", "angles", "degree",
        "rows", "validity", "for", "THEN", "wLower", "The", "index", "wUpper",
        "END", "Discrete", "transceivers", "Address", "DEI", "specified",
        "messages", "defined", "Parity", "out", "Set", "has", "Aircraft", "SCS",
        "sec", "cleared", "Hydraulic", "message", "ELSEIF", "s", "mA", "count",
        "MHz", "KHz", "EHSV", "Selection", "labels", "transmit", "Label", "Words",
        "Internal", "until", "CL", "ML", "CAN", "CPU", "ratio", "correspond",
        "set", "yt", "as", "degrees", "Table", "copies", "copy","SYSCLKOUT"
    ]

    # canonical representation - Irrespective of the case in NON_UNIT_TOKENS
    NON_UNIT_TOKENS_CANON = {token.casefold() for token in NON_UNIT_TOKENS}

    # Unit synonyms → canonical unit
    UNIT_SYNONYMS = {
        "msec": "ms",
        "millisecond": "ms",
        "milliseconds": "ms",

        "sec": "s",
        "secs": "s",
        "second": "s",
        "seconds": "s",

        "degree": "degrees",
        "deg": "degrees",

        #"millimeter": "mm",
        #"millimeters": "mm",--- wantedly commented to get errors in Unit for G2.3

        "µsec": "µs",
        "microsecond": "µs",
        "microseconds": "µs",

        "bytes": "bytes",
        "byte": "bytes"

    }

    UNIT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*([µμa-zA-Z]+)\b")

    ACRONYM_WHITELIST = {
        "ADC", "HSIS", "GPIO", "EV", "SPI", "OTP", "ARINC",
        "XINTF", "DEI", "HW", "SW", "PLL", "PLLCR", "SYSCLKOUT", "RAM",
        "FALSE", "TRUE", "PASS", "SHDL", "END", "FAIL", "LRVDT", "PWM",
        "HDL", "SRAM", "SOV", "FLASH", "EHSV", "WHILE",
        "UEC", "DAL", "DFT", "VSW", "SCS", "SACT", "SMB", "ASA", "ROM",
        "RH", "LH", "CRC", "XOR", "SSM", "LADC", "RADC", "ISI",
        "ELSEIF", "CL", "ML", "DMCA", "SDI", "ON", "DMCB", "OFF", "TSA",
        "PASSED", "SEU", "FAILED", "SUM", "MSB", "FIR", "VA", "VB",
        "RATIO", "BITE", "INVALID", "VALID", "ODD", "DMC", "EVEN",
        "WOW", "NLG", "OMS", "FIFO", "ELSIF", "PID", "SES",
        "SPITXBUF", "SPIRXBUF", "CAN", "ID", "TI", "CPU",
        "MOTS", "MOTO", "LAM", "XMAC", "BF", "PREAD", "IMACL",
        "XPREAD", "PWRITE", "XMACD", "SBF", "DMAC", "XPWRITE",
        "MAC", "QMACL", "PIEACK","EA"
        #"VDT", "STC" --- wantedly commented to get errors in Terminology for G2.3
    }

    # Regex only to FIND candidates, not validate them
    ACRONYM_REGEX = re.compile(r"\b[A-Z]{2,}\b")

    EXCLUDED_WORDS = {
        "IF", "THEN", "ELSE", "ENDIF", "AND", "OR", "NOT","ELSIF","FOR", "DO", "WHILE", "END"
    }
    # ************ G2.3 : End *************

    # ************ G2.5 : Start ************

    # Timing-related terms (require explicit time)
    TIMING_TERMS = [
        "timeout", "delay", "latency", "response", "execution time",
        "startup time"
    ]

    # Throughput / rate related terms
    THROUGHPUT_TERMS = [
        "transmit", "receive", "send", "update", "sample",
        "throughput", "rate", "frequency", "bandwidth"
    ]

    # Resource usage terms (FULL coverage)
    RESOURCE_TERMS = {
        "MEMORY": ["memory", "ram", "rom", "flash"],
        "CPU": ["cpu", "execution time", "cycles", "processing time"],
        "BUFFER": ["buffer", "queue", "fifo"],
        "STACK": ["stack"]
    }

    # -------------------------
    # VAGUE PERFORMANCE TERMS
    # -------------------------
    VAGUE_TERMS = [
        "quick", "quickly", "immediately", "as soon as possible",
        "periodically", "minimal", "low", "high", "acceptable", "reasonable"
    ]

    # -------------------------
    # REGEX PATTERNS
    # -------------------------
    TIME_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*(ms|us|µs|ns|s|sec)\b", re.I)
    RESOURCE_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*(kb|mb|bytes|words|cycles|%)\b", re.I)

    CONDITIONAL_KEYWORDS = ["if", "when", "during", "while", "on"]

    # -------------------------
    # Rate / Periodicity regex
    # -------------------------
    RATE_PATTERN = re.compile(r"""
        \b
        \d+(?:\.\d+)?\s*
        (?:
            (?:[gm]hz|khz|hz)                |    # Hz family
            (?:[gm]bps|kbps|mbps|bps)        |    # bps family
            (?:msgs?|messages|pkts?|packets)\s*/\s*s(?:ec)? |  # msgs/s, messages/sec, packets/s
            (?:per\s*second)                      # per second
        )
        \b
    """, re.IGNORECASE | re.VERBOSE)

    PERIODICITY_PATTERN = re.compile(
        r"\b(?:every|each)\s+\d+(?:\.\d+)?\s*(ms|us|µs|ns|s|sec|seconds)\b",
        re.IGNORECASE
    )

    # Vague throughput phrase (only triggers if no numeric rate present)
    VAGUE_RATE_PATTERN = re.compile(
        r"\b(?:high|low)\s+(?:data\s+rate|throughput|bandwidth)\b",
        re.IGNORECASE
    )

    # Accept "N [token] cycles" e.g., "65536 SYSCLKOUT cycles"
    CYCLES_PATTERN = re.compile(
        r"\b\d+(?:\.\d+)?\s+(?:[A-Za-z_]+\s+)?cycles?\b",
        re.IGNORECASE
    )

    # ************ G2.5 : End *************

    # ************ G2.6 : Start *************
    G2_6_AMBIGUOUS_TERMS = [
        "immediately",
        "quickly",
        "rapidly",
        "as soon as possible",
        "promptly"
    ]

    G2_6_MANDATORY_KEYWORDS = ["shall", "must"]

    G2_6_SRS_ID_PATTERN = r"\bSCU_[A-Z0-9_]+_\d+\b"

    # ************ G2.6 : End *************

# =========================================================
# G3 CONFIG
# =========================================================
class G3Config:
    SUPPORTED_INTERFACES = ["can", "spi", "uart", "i2c"]
    UNSUPPORTED_INTERFACES = ["ethernet", "usb", "arinc", "pcie", "sata"]

    TIMING_KEYWORDS = [
        "ms", "millisecond", "milliseconds",
        "us", "microsecond",
        "hz", "khz", "mhz",
        "period", "rate", "frequency",
        "latency", "deadline", "jitter",
        "wcet", "bcet", "execution time",
        "response time", "cycle time"
    ]

    COMMENTS = {
        "g31_hw_assumption": "Requirement assumes hardware capability not confirmed",
        "g31_cpu_load": "Computational complexity may exceed CPU margin",
        "g31_not_justified": "Hardware constraints not justified",
        "g32_no_timing": "Execution timing not specified",
        "g32_startup": "Startup timing not defined",
        "g32_monitor": "Monitoring rate not defined",
        "g32_logging": "Logging rate not defined",
        "g32_comm": "Communication timing missing",
        "g32_control": "Control timing missing",
        "g33_unsupported_iface": "{} interface not supported",
        "g33_no_bandwidth": "Interface bandwidth not specified",
        "g34_dynamic_memory": "Dynamic memory usage detected",
        "g34_unbounded": "Unbounded operation specified",
        "g34_resource_size": "Resource size not bounded",
    }


# =========================================================
# G4 CONFIG
# =========================================================
class G4Config:
    REQ_PREFIX = "SCU_STC_SRS_"
    VERIFICATION_METHOD_REGEX = (
        r"verification\s*method\s*:\s*"
        r"(Test|Analysis|Inspection|Demonstration|HSI|SI|Manual)"
    )
    MANDATORY_WORD_REGEX = r"\bshall\b"

    CONDITION_WORDS = ["if", "when", "after", "within"]

    NUMBER_PATTERN = r"\d+"

    UNIT_PATTERN = (
        r"\b(ms|µs|us|sec|seconds|%|hz|khz|mhz|rpm|v|a|°c|bytes|"
        r"0x[0-9a-fA-F]+)\b"
    )

    REGISTER_KEYWORDS = ["register", "address", "bit", "offset"]
    COMMUNICATION_KEYWORDS = ["can", "uart", "spi", "i2c", "ethernet"]
    FAULT_KEYWORDS = ["fault", "error", "failure", "detect"]
    IO_KEYWORDS = ["input", "output", "gpio", "pin"]
    FUNCTIONAL_KEYWORDS = ["calculate", "compute", "control", "monitor"]


# =========================================================
# G1 CONFIG
# =========================================================

# =========================================================
# REGEX
# =========================================================
REQ_ID_RE = re.compile(r"^(SCU_[A-Z_]+_\d+)\b")
LABEL_RE = re.compile(r"\b([0-3]?[0-7]{2})\b")


class G1Config:
    HLR_DOCX = "SCU_SRS.docx"
    SYS_DOCX = "SCU_SES.docx"
    SRS_DOCX = "SCU_SRS.docx"
    ICD_DOCX = "SCU_ICD.docx"
    SOFTWARE_REQ_DOCX = "Software_req.docx"

    G1_3_OUTPUT = "G1_3_ARINC_Comparison.xlsx"
    G1_4_OUTPUT = "G1_4_Requirement_Review.xlsx"
    G1_3_4_SUMMARY_OUTPUT = "G1_3_4_Summary.xlsx"

    REQ_ID_RE = r"(SCU_STC_SRS_\d+)"
    LABEL_RE = r"\b([0-7]{1,3})\b"

    SIM_MATCH = 0.85
    SIM_POTENTIAL = 0.65

    TERM_SYNONYMS = {
        "transmission interval": ["update rate", "refresh rate", "output rate"],
        "interface": ["bus", "port", "connection"],
        "signal": ["data", "parameter"],
        "receiver": ["destination", "sink"],
        "transmitter": ["source", "sender"],
    }

    """
    config.py

    Central configuration for G1 Review Tool.
    This file defines constants, patterns, and review templates only.
    NO logic must be implemented here.
    """

    # ============================================================
    # GLOBAL RESULT STATES
    # ============================================================

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"   # requires human review (LLM-assisted)

    # --- NEW: SSM alias map (canonicalization driven by ICD)
    # Canonical tokens we will use in logic:
    #   NORMAL_OPERATION, FUNCTIONAL_TEST, NO_COMPUTED_DATA, NO_DATA, FAILURE_WARNING
    # Synonyms below are normalized to those.
    SSM_ALIASES = {
        # Label 206 SSM bit meanings from your ICD (Type: BNR):
        # [00]=Failure Warning, [01]=No Computed Data, [10]=Functional Test, [11]=Operation  → NORMAL_OPERATION
        "FAILURE WARNING": "FAILURE_WARNING",
        "NO COMPUTED DATA": "NO_COMPUTED_DATA",
        "NCD": "NO_COMPUTED_DATA",
        "FUNCTIONAL TEST": "FUNCTIONAL_TEST",
        "FUNCTIONAL_TEST": "FUNCTIONAL_TEST",
        "OPERATION": "NORMAL_OPERATION",
        "NORMAL OPERATION": "NORMAL_OPERATION",
        "NORMAL_OPERATION": "NORMAL_OPERATION",
        # Common synonyms seen in HLR/SYS
        "NO DATA": "NO_DATA",
        "NO_DATA": "NO_DATA",
    }

    # ============================================================
    # DOMAIN-SPECIFIC FUNCTIONAL ELEMENT KEYWORDS
    # (Used for G1.1 functional alignment checks)
    # ============================================================

    MONITOR_KEYWORDS = [
        "lvdt",
        "asa",
        "ehsv",
        "target input",
        "over angle",
        "steering angle",
        "watchdog",
        "rom test",
        "ram integrity",
        "rigging",
        "aircraft information"
    ]

    # ============================================================
    # G1.1 – COMPLIANCE CHECK CATEGORIES
    # ============================================================

    G1_1_CHECK_TYPES = [
        "TRACEABILITY_MISSING",
        "TRACEABILITY_EXTRA",
        "NUMERIC_MISMATCH",
        "COMPARATOR_MISMATCH",
        "BOOLEAN_POLARITY_MISMATCH",
        "CONDITION_MISSING",
        "CONDITION_EXTRA",
        "POTENTIAL_LOGIC_DRIFT"
    ]

    # ============================================================
    # NUMERIC & LOGICAL EXTRACTION PATTERNS
    # (Used by deterministic + LLM-assisted layers)
    # ============================================================

    # Comparison operators expected in requirements
    COMPARISON_OPERATORS = [
        "<",
        "<=",
        ">",
        ">=",
        "="
    ]

    # Boolean polarity keywords
    BOOLEAN_POSITIVE_TERMS = [
        "shall",
        "must",
        "enabled",
        "allowed",
        "active"
    ]

    BOOLEAN_NEGATIVE_TERMS = [
        "shall not",
        "must not",
        "disabled",
        "not allowed",
        "inactive"
    ]

    # Conditional keywords
    CONDITION_KEYWORDS = [
        "if",
        "when",
        "only when",
        "unless",
        "while",
        "after",
        "before"
    ]

    # ============================================================
    # STATE / MODE LANGUAGE (STRUCTURAL ONLY)
    # ============================================================

    STATE_KEYWORDS = [
        "state",
        "mode",
        "transition",
        "enter",
        "exit"
    ]

    # ============================================================
    # G1.2 – CLARITY (VAGUENESS)
    # ============================================================


    G1_2_VAGUE_TERMS = [
        "user friendly", "fast", "adequate", "sufficient",
        "as appropriate", "if possible", "etc", "where necessary",
        "as needed", "approximately", "as required", "normally", "generally"
    ]


    # ============================================================
    # STANDARD REVIEW COMMENTS (DO NOT HARD-CODE IN LOGIC)
    # ============================================================

    COMMENTS = {
        "TRACEABILITY_MISSING":
            "System requirement is not fully reflected in software requirements.",

        "TRACEABILITY_EXTRA":
            "Software requirement introduces behavior not requested at system level.",

        "NUMERIC_MISMATCH":
            "Numeric values differ between system and software requirements.",

        "COMPARATOR_MISMATCH":
            "Comparison operators differ between system and software requirements.",

        "BOOLEAN_POLARITY_MISMATCH":
            "The system and the software specify opposite logical outcomes or defaults for the same behavior.",

        "CONDITION_MISSING":
            "Condition stated at system level is missing at software level.",

        "CONDITION_EXTRA":
            "Software introduces additional conditions not stated at system level.",

        "POTENTIAL_LOGIC_DRIFT":
            "Potential semantic or logical deviation detected; review required.",

        "VAGUE_WORDING":
            "Requirement contains vague or non-verifiable wording.",

        "INCOMPLETE_SYSTEM_COVERAGE":
            "System behavior not fully covered in software requirements.",

        "STATE_DIAGRAM_MISMATCH" : "State machine behavior differs between system and software.",

        "LLM_ERROR" : "LLM explanation failed."
    }

    # Time units and normalization factors (ms baseline)
    TIME_UNITS = ("us", "µs", "ms", "s", "min")
    UNIT_TO_MS = {
        "us": "0.001",
        "µs": "0.001",
        "ms": "1",
        "s": "1000",
        "min": "60000",
    }

    # Limits for numeric-drift reporting (to avoid noise on long blocks)
    DRIFT_MAX_CONSTS = 25          # skip drift if more than this on SYS side
    DRIFT_MIN_JACCARD = 0.60       # only report drift if Jaccard(sys, sw) < this

    # Verbs that often signal “new feature” introductions at SW level
    EXTRA_FEATURE_VERBS = [
        "provide","compute","calculate","store","log","record","generate",
        "report","publish","transmit","send","expose","offer","display","archive"
    ]

    # Extra-feature detection stopwords (kept minimal; adjust per domain)
    EXTRA_FEATURE_STOPWORDS = {
        "the","this","that","shall","will","must","system","software","hardware",
        "mode","value","data","signal","table","label","state","monitor","parameter"
    }

    # Optional: Primary key hints for tables (first match used)
    TABLE_PRIMARY_KEYS = ["id", "label", "name", "signal", "parameter"]

    # Optional: ARINC table header hints to improve diagnostics
    ARINC_HEADERS = {"label","sdi","ssm","bit","lsb","msb","name","description","units"}

    # Output grouping titles for findings
    GROUP_TITLES = {
        "BOOLEAN_POLARITY_MISMATCH": "Booleans",
        "POTENTIAL_LOGIC_DRIFT": "Numeric constants",
        "NUMERIC_MISMATCH": "Numerics & Timing",
        "INCOMPLETE_SYSTEM_COVERAGE": "Coverage",
        "TRACEABILITY_MISSING": "Traceability (Missing)",
        "TRACEABILITY_EXTRA": "Traceability (Extra)",
        "STATE_DIAGRAM_MISMATCH": "State/Mode",
        "CONDITION_MISSING": "Conditions (Missing)",
        "CONDITION_EXTRA": "Conditions (Extra)",
    }

    # When the checker has nothing comparable to evaluate, prefer REVIEW
    # You already defined: PASS/FAIL/REVIEW and REFINEMENT_*; we’ll reuse them.

    # ============================================================
    # LLM INTEGRATION CONTROL (REVIEW ASSIST ONLY)
    # ============================================================

    LLM_ENABLED = True          # must be switchable
    LLM_MODE = "ASSIST"        # ASSIST | OFF
    LLM_MAX_TOKENS = 800

    # LLM is NOT allowed to decide PASS/FAIL
    LLM_ALLOWED_RESULTS = [
        "ALIGNED",
        "PARTIAL",
        "MISALIGNED"
    ]

    REAL_FINDING_KEYS = (
    "TRACEABILITY_MISSING",
    "TRACEABILITY_EXTRA",
    "NUMERIC_MISMATCH",
    "COMPARATOR_MISMATCH",
    "BOOLEAN_POLARITY_MISMATCH",
    "CONDITION_MISSING",
    "CONDITION_EXTRA",
    "POTENTIAL_LOGIC_DRIFT",
    "THRESHOLD_MISMATCH",
    "FORMULA_MISMATCH",
    "ELSE_MISSING",
    "ELSEIF_MISSING",
    "ALGORITHM_BRANCH_MISSING",
    )

    # ============================================================
    # REFINEMENT CLASSIFICATION (SECOND TIER)
    # ============================================================

    REFINEMENT_ACCEPTABLE = "ACCEPTABLE_REFINEMENT"
    REFINEMENT_UNACCEPTABLE = "UNACCEPTABLE_DRIFT"
    REFINEMENT_NONE = "NOT_APPLICABLE"

    # ============================================================
    # G1.2 – CLARITY FOR COMPLIANCE (KEYWORDS ONLY)
    # ============================================================

    # G1_2_VAGUE_TERMS = [
    #     "approximately",
    #     "as appropriate",
    #     "as required",
    #     "if possible",
    #     "normally",
    #     "generally",
    #     "where necessary",
    #     "as needed"
    #     "adequate",
    #     "sufficient"
    # ]

    G1_2_AMBIGUOUS_REFERENCES = [
        "this value",
        "that value",
        "the above",
        "the below",
        "as mentioned earlier",
        "as above",
        "as below",
        "former",
        "latter",
        "same as above",
        #"following"
    ]

    # ============================================================
    # G1.2 / G2 – INTENT TAXONOMY
    #❗ FAIL here does NOT mean intent mismatch - It means intent match but behavior conflict exists elsewhere
    # ============================================================

    INTENT_GROUPS = {
        # Safety enforcement
        "FAILSAFE": [
            "failsafe", "safe state", "shutdown", "disable", "inhibit",
            "prevent operation", "block operation"
        ],

        # Recovery / continuation
        "RECOVERY": [
            "recover", "resume", "return to normal", "normal operation",
            "exit failsafe"
        ],

        # Monitoring / detection only
        "MONITORING": [
            "monitor", "detect", "check", "observe"
        ],

        # Control / command
        "CONTROL": [
            "command", "set", "control", "drive", "actuate"
        ],

        # Mandatory behavior
        "MANDATORY": [
            "shall", "must", "will"
        ],

        # Optional / permissive behavior
        "PERMISSIVE": [
            "may", "can", "should"
        ]
    }

    LLM_TRIGGER_KEYS = {
        "POTENTIAL_LOGIC_DRIFT",
        "INTENT_MISMATCH",
        "CONDITION_EXTRA",
        "CONDITION_MISSING"
    }

# =========================================================
# G5 CONFIG
# =========================================================
# =========================================================
# G5 CONFIG
# =========================================================
class G5Config:
    INPUT_SRS_FILE = "SCU_SRS.docx"
    OUTPUT_REPORT_FILE = "G5_SRS_Review.xlsx"

    EXPECTED_ID_PREFIX = "SCU_STC_SRS_"
    VALID_ID_REGEX = r"^SCU_STC_SRS_\d+$"
    MISSING_ID_LABEL = "<MISSING ID>"

    # ---------- Safety ----------
    SAFETY_KEYWORDS = [
        "fault", "failure", "fail", "error", "loss", "hazard",
        "degraded", "safe state", "shutdown", "reset", "timeout",
        "monitor", "detect", "isolate", "protect", "recover",
        "invalid", "unsafe"
    ]

    MITIGATION_KEYWORDS = [
        "detect", "prevent", "mitigate", "isolate",
        "monitor", "recover", "limit", "protect",
        "shutdown", "transition"
    ]

    FORBIDDEN_SAFETY_PHRASES = [
        "best effort", "where possible",
        "if feasible", "normally",
        "typically", "as appropriate"
    ]

    FORBIDDEN_MODALS = ["may", "should", "will"]

    # ---------- Ambiguity ----------
    AMBIGUOUS_WORDS = [
        "should", "may", "might", "could",
        "normally", "typically",
        "as appropriate", "where possible"
    ]

    # ---------- Single Functionality ----------
    MAX_SHALL_COUNT = 1   # ✅ THIS FIXES YOUR CRASH

    STOP_WORDS = {
        "SHALL", "WILL", "MAY", "PROGRAM", "SYSTEM",
        "WHEN", "IF", "THEN", "AND", "OR", "NOT",
        "ANY", "THE", "A", "AN", "LEVEL", "MODE",
        "STATE", "STATUS", "FAILSAFE", "MONITOR",
        "ACCORDING", "FOLLOWING", "CONFIRMATION",
        "LOGIC", "TIME", "WITH", "STC"
    }

    # ---------- Excel ----------
    REPORT_TITLE = "High-Level Requirements Conformance Review (G5)"

    COLUMN_HEADERS = [
        "Requirement ID",
        "5.1: Assess safety-critical aspects",
        "5.2: Ensure single functionality",
        "5.3: Follow project guidelines",
        "5.4: Avoid ambiguous words",
        "5.5: Check formatting & structure",
        "Failure Reason(s)"
    ]
class G7Config:
    INPUT_SRS_FILE = "SCU_SRS.docx"

    # Outputs
    ALGO_OUTPUT_FILE = "G7_Algorithm_Analysis.xlsx"
    REQ_OUTPUT_FILE  = "G7_Requirement_Quality.xlsx"
