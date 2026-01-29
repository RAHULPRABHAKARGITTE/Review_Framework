import re

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
class G1Config:
    HLR_DOCX = "SCU_SRS.docx"
    SYS_DOCX = "SCU_SES.docx"
    SRS_DOCX = "SCU_SRS.docx"
    ICD_DOCX = "SCU_ICD.docx"
    SOFTWARE_REQ_DOCX = "Software_req.docx"

    G1_3_OUTPUT = "G1_3_ARINC_Comparison.xlsx"
    G1_4_OUTPUT = "G1_4_Requirement_Review.xlsx"

    REQ_ID_RE = r"(SCU_STC_SRS_\d+)"
    LABEL_RE = r"\b([0-7]{1,3})\b"

    SIM_MATCH = 0.75
    SIM_POTENTIAL = 0.50

    TERM_SYNONYMS = {
        "transmit": ["send", "tx"],
        "receive": ["rx", "read"],
        "interval": ["rate", "frequency"]
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
#hi rahul