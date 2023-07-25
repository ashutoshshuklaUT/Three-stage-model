# Reads from the solution file and prints/accesses required information.

import os
import pandas as pd
import json
from utils import *
from three_stage_model import *

prep_tech = [0,6,12,18,24]
value_lister = []

for prep_value in prep_tech:
    main_path = "/work2/07346/ashukla/stampede2/ThreeStageModel/output/prep_" + str(prep_value) + "/"
    with open(main_path + "model_params.json", 'r') as f:
        params = json.load(f)        
    with open(main_path + "model_scenarios.json", 'r') as f:
        model_scenarios_string = json.load(f)

    model_scenarios = {}
    for k in model_scenarios_string:
        model_scenarios[int(k)] = model_scenarios_string[k]

    params["path_to_input"] = os.getcwd() + "/data/192_Scenario/"
    base_model = three_stage_model(params, model_scenarios)
    base_model.model.update()
    sol_path = main_path + "solution.sol"
    base_model.model.read(sol_path)
    base_model.model.update()

    value_lister.append((base_model.model.getVarByName('i_oc').Start/1e6,
                         base_model.model.getVarByName('i_mitigation').Start/1e6,
                         base_model.model.getVarByName('i_voll').Start/1e6,
                         base_model.model.getVarByName('i_preparedness').Start/1e6))
    
print(pd.DataFrame(value_lister))
pd.DataFrame(value_lister).to_csv("temp_file_prep_tech.csv")
