# config.py
from pathlib import Path
from docx import Document
import argparse
from docx import Document
from openpyxl import load_workbook
from datetime import datetime
import pandas as pd
import numpy as np
import pytest
import re
import os
import html


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # Review_Framework

INPUT_DIR = BASE_DIR / "inputs"
OUTPUT_DIR = BASE_DIR / "outputs"

DEFAULT_SRS_PATH = str(INPUT_DIR / "SCU_SRS_G7.docx")
RESULTS_XLSX = str(OUTPUT_DIR / "G7_Algorithm_Analysis.xlsx")


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]   # Review_Framework/
INPUT_DIR = BASE_DIR / "inputs"
OUTPUT_DIR = BASE_DIR / "outputs"

DEFAULT_SRS_PATH = str(INPUT_DIR / "SCU_SRS_G7.docx")
RESULTS_XLSX = str(OUTPUT_DIR / "G7_Algorithm_Analysis.xlsx")


# Parsed requirements output workbook (written by io_utils)
REQUIREMENTS_XLSX = "requirements_output1.xlsx"

# -------- Sheet names --------
ALL_REQ_SHEET = "All_Requirements"
ALGO_REQ_SHEET = "Algorithm_Requirements"
NON_ALGO_REQ_SHEET = "Non_Algorithm_Requirements"

RESULTS_SUMMARY_SHEET = "Results"
RESULTS_DETAILS_SHEET = "Results_Details"

# -------- Tunables --------
FOR_STRICT_UPPERCASE = True        # Require 'FOR'/'DO' uppercase in headers
FOR_LOOKAHEAD_LIMIT = 3            # Lines to look ahead to find 'DO' after 'FOR'
