from config import CommonConfig

# -------- Input --------
DEFAULT_SRS_PATH = f"{CommonConfig.BASE_INPUT}/SCU_SRS.docx"

# -------- Output (SAME as other groups) --------
BASE_OUTPUT = CommonConfig.BASE_OUTPUT  # outputs/

# -------- G7 outputs --------
REQUIREMENTS_XLSX = f"{BASE_OUTPUT}/G7_Requirements.xlsx"
RESULTS_XLSX = f"{BASE_OUTPUT}/G7_Algorithm_Analysis.xlsx"

# -------- Sheet names --------
ALL_REQ_SHEET = "All_Requirements"
ALGO_REQ_SHEET = "Algorithm_Requirements"
NON_ALGO_REQ_SHEET = "Non_Algorithm_Requirements"

RESULTS_SUMMARY_SHEET = "Results"
RESULTS_DETAILS_SHEET = "Results_Details"

# -------- Tunables --------
FOR_STRICT_UPPERCASE = True
FOR_LOOKAHEAD_LIMIT = 3
