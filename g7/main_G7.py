# main_g7.py
import os
import importlib.util
from g7.config.config_g7 import DEFAULT_SRS_PATH, RESULTS_XLSX
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
    var_input_analysis,
)



def main():
    algo_req = parse_requirements(DEFAULT_SRS_PATH)

    # -------------------------
    # Objective G 7.1
    # -------------------------
    if_else_syntax_check(algo_req)
    for_condition_syntax_check(algo_req)
    while_syntax_check(algo_req)
    switch_syntax_check(algo_req)

    # -------------------------
    # Objective G 7.2
    # -------------------------
    edge_case_check(algo_req)

    # -------------------------
    # Objective G 7.3
    # -------------------------
    checklist_presence(algo_req)

    # -------------------------
    # Objective G 7.4
    # -------------------------
    from g7.g7_logic import run_objective_g74
    run_objective_g74(DEFAULT_SRS_PATH, RESULTS_XLSX)
    
    # -------------------------
    # Objective G 7.5
    # -------------------------
    from g7 import g7_logic
    g7_logic.algorithm_design_meets_do178c_objectives(DEFAULT_SRS_PATH, RESULTS_XLSX)

    # -------------------------
    # Objective G 7.6
    # -------------------------
    g7_logic.Error_Handling(DEFAULT_SRS_PATH, RESULTS_XLSX)

    # -------------------------
    # Objective G 7.7
    # -------------------------
    div_by_zero_check(algo_req)
    infinite_loop_check(algo_req)
    null_pointer_check(algo_req)
    out_of_range_check(algo_req)
    var_input_analysis(algo_req)

def run_g7():
 main()

if __name__ == "__main__":
    main()
