# main_g7.py
import argparse

import config
from g7.io.io_g7 import write_requirements_excel

from g7.io.io_g7 import write_requirements_excel, append_results
from g7.config_g7.config_g7 import (
    REQUIREMENTS_XLSX,
    RESULTS_XLSX,
    ALL_REQ_SHEET,
    ALGO_REQ_SHEET,
    NON_ALGO_REQ_SHEET,
    RESULTS_SUMMARY_SHEET,
    RESULTS_DETAILS_SHEET
)
import pandas as pd

from g7.g7_logic import (
    parse_requirements,
    if_else_syntax_check,
    for_condition_syntax_check,
    while_syntax_check,
    switch_syntax_check,
    edge_case_check,
    checklist_presence,
    div_by_zero_check,
    infinite_loop_check,
    null_pointer_check,
    out_of_range_check,
    var_input_analysis
)
from g7.config_g7.config_g7 import DEFAULT_SRS_PATH

import os
from g7.config_g7.config_g7 import BASE_OUTPUT

def run_g7():
    print("▶ Running G7 review")

    algo_df = parse_requirements(DEFAULT_SRS_PATH)

    # Objective G 7.1
    if_else_syntax_check(algo_df)
    for_condition_syntax_check(algo_df)
    while_syntax_check(algo_df)
    switch_syntax_check(algo_df)

    # Objective G 7.2
    edge_case_check(algo_df)

    # Objective G 7.3
    checklist_presence(algo_df)

    # Objective G 7.7
    div_by_zero_check(algo_df)
    infinite_loop_check(algo_df)
    null_pointer_check(algo_df)
    out_of_range_check(algo_df)
    var_input_analysis(algo_df)

    print("✅ G7 review completed")
