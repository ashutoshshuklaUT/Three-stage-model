#!/usr/bin/env python
# coding: utf-8

# In[1]:
import os
import sys
import yaml
import json
import argparse
from utils import *
from three_stage_model import *
from IPython import embed

# Read model parameters
with open(r'multi.yaml') as file:
    params = yaml.load(file, Loader=yaml.FullLoader)
    
model_scenarios = return_model_scenarios()

# In[ ]:
parser = argparse.ArgumentParser()

parser.add_argument('--message', type=str, required=True, help="Details about the runs")
parser.add_argument('--run_name', type=str, required=True, help="Name of the run")
parser.add_argument('--machine', type=str, required=True, help = "Machine Type")

parser.add_argument('--fixed_cost', type=int, required=False, help="Fixed cost of hardening")
parser.add_argument('--variable_cost', type=int, required=False, help="Variable cost of hardening")
parser.add_argument('--td_cost', type=int, required=False, help="Cost of a tiger dam unit")
parser.add_argument('--operating_cost', type=int, required=False, help="Tiger dam deployment cost per substation")

parser.add_argument('--tau', type=int, required=False, help="Number of hurricanes")
parser.add_argument('--restoration_time', type=int, required=False, help = "Restoration time")
parser.add_argument('--voll', type=int, required=False, help = "Value of load loss")

parser.add_argument('--flexible_generation', type=str, required=False, help="Dispatch Decisions")

parser.add_argument('--max_mit', type=int, required=False, help = "Maximum allowed mitigation")
parser.add_argument('--mit_level', type=int, required=False, help = "Mitigation unit")
parser.add_argument('--max_prep', type=int, required=False, help = "Maximum allowed preparedness")
parser.add_argument('--prep_level', type=int, required=False, help = "Preparedness unit")

parser.add_argument('--mip_gap', type=float, required=False, help = "MIP-Gap")
parser.add_argument('--time_limit', type=int, required=False, help = "Solver time")

parser.add_argument('--mitigation_budget', type=int, required=False, help = "If there is a mitigation budget")
parser.add_argument('--first_stage_binary', type=str, required=False, help = "is first-stage binary: true or false")

################## new arguements #########################
parser.add_argument('--coordination', type=str, required=False, help = "Is it a coordination model to be solved")
parser.add_argument('--initial_sol_path', type=str, required=False, help = "path of the initial solution")
parser.add_argument('--mip_focus', type=str, required=False, help = "mip focus strategy")
parser.add_argument('--cut_level', type=str, required=False, help = "cut aggresiveness")





# In[ ]:
# Parse the argument
args = parser.parse_args()


if args.fixed_cost:
    params["fixed_cost"] = args.fixed_cost
if args.variable_cost:
    params["variable_cost"] = args.variable_cost
if args.td_cost:
    params["td_cost"] = args.td_cost
if args.operating_cost:
    params["operating_cost"] = args.operating_cost

if args.tau:
    params["tau"] = args.tau
if args.restoration_time:
    params["restore_time"] = args.restoration_time
if args.voll:
    params["voll"] = args.voll    

if args.flexible_generation:
    if args.flexible_generation == "true":
        params["flexible_generation"] = True
    else:
        params["flexible_generation"] = False

if args.max_mit:
    params["max_mit"] = args.max_mit
if args.mit_level:
    params["mit_level"] = args.mit_level
if args.max_prep:
    params["max_prep"] = args.max_prep
if args.prep_level:
    params["prep_level"] = args.prep_level

if args.mip_gap:
    params["mip_gap"] = args.mip_gap
if args.time_limit:
    params["time_limit"] = args.time_limit
    
if args.first_stage_binary:
    if args.first_stage_binary == "true":
        params["first_stage_binary"] = True
    else:
        params["first_stage_binary"] = False

if args.machine == "tacc":
    params["path_to_output"] = "/work2/07346/ashukla/ls6/ThreeStageModel/output/" + args.run_name + "/"
else:
    params["path_to_output"] = os.getcwd() + "/output/" + args.run_name + "/"        

# In[ ]:
params["path_to_input"] = os.getcwd() + "/data/192_Scenario/"
if os.path.exists(params["path_to_output"]):
    print("The path exisits. Try a new directory name")
    sys.exit()
else:
    os.mkdir(params["path_to_output"])
    
print("Path to output is:\t", params["path_to_output"])
print("Creating model instance.")
print("The number of mini-brent models is\t", len(model_scenarios.keys()))
print("Number of scenarios per model is\t", len(model_scenarios[0]))

# In[ ]:
base_model = three_stage_model(params, model_scenarios)
if args.mitigation_budget:
    base_model.model.addConstr(base_model.i_mitigation + base_model.i_preparedness <= args.mitigation_budget)

######################################## Coordination ####################################
if args.coordination:
    params["coordination"] = args.coordination
    prep_constraint = base_model.model.addConstr(base_model.i_preparedness <= 0)
    base_model.model.setParam("LogFile", params["path_to_output"] + "coordination_log_" + str(params["voll"]))
    base_model.model.setParam("MIPGap", params["mip_gap"])
    base_model.model.setParam("TimeLimit", 36000)
    base_model.model.setParam("Method", params["solver_method"])
    base_model.model.optimize()
    params["coordination_i_mitigation"] = base_model.i_mitigation.X
    params["coordination_i_preparedness"] = base_model.i_preparedness.X
    params["coordination_i_oc"] = base_model.i_oc.X
    params["coordination_i_voll"] = base_model.i_voll.X
    base_model.model.remove(prep_constraint)
    for i in base_model.substation_info:
        if base_model.x_mit[i].X > 0:
            base_model.model.addConstr(base_model.x_mit[i] == base_model.x_mit[i].X)
            base_model.model.addConstr(base_model.y_mit[i] == 1)
        else:
            base_model.model.addConstr(base_model.x_mit[i] == 0)
            base_model.model.addConstr(base_model.y_mit[i] == 0)

if args.initial_sol_path:
    params["initial_sol_path"] = args.initial_sol_path
    base_model.model.update()
    base_model.model.read(args.initial_sol_path)
    base_model.model.update()

    temp_here = 0
    for sub_id in base_model.substation_info:
        temp = base_model.model.getVarByName('x_mit[' +  str(sub_id) + ']').Start
        if temp > 0:
            print("Substation ", sub_id, " has hardening ", temp)
            temp_here = temp_here + params["fixed_cost"] + params["mit_level"]*temp*params["variable_cost"]
            print("Updated Mitigation Cost: ", temp_here/1e6)
    print("Total Budget\t", temp_here/1e6)
    
if args.mip_focus:
    params["mip_focus"] = int(args.mip_focus)
    base_model.model.setParam("MIPFocus", params["mip_focus"])

if args.cut_level:
    params["cut_level"] = int(args.cut_level)
    base_model.model.setParam("Cuts", params["cut_level"])
    
base_model.model.setParam("LogFile", params["path_to_output"] + "log")
base_model.model.setParam("MIPGap", params["mip_gap"])
base_model.model.setParam("TimeLimit", params["time_limit"])
base_model.model.setParam("Method", params["solver_method"])

base_model.model.setParam("NodeFileStart", 0.5)
base_model.model.setParam("Threads", 10)  

base_model.model.optimize()
base_model.model.write(params["path_to_output"] + "solution.sol")    

params["i_mitigation"] = base_model.i_mitigation.X
params["i_preparedness"] = base_model.i_preparedness.X
params["i_oc"] = base_model.i_oc.X
params["i_voll"] = base_model.i_voll.X
params["message"]: args.message

# In[ ]:
with open(params["path_to_output"] + 'model_params.json', 'w') as fp:
    json.dump(params, fp)
    
with open(params["path_to_output"] + 'model_scenarios.json', 'w') as fp:
    json.dump(model_scenarios, fp)