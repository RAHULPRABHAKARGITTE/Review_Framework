import re
import os

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
