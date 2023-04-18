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

# Read model parameters
with open(r'multi.yaml') as file:
    params = yaml.load(file, Loader=yaml.FullLoader)
    
model_scenarios = return_model_scenarios()


# In[ ]:


parser = argparse.ArgumentParser()

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


parser.add_argument('--first_stage_binary', type=str, required=False, help = "is first-stage binary: true or false")

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
    params["path_to_output"] = "/work2/07346/ashukla/stampede2/ThreeStageModel/output/" + args.run_name + "/"
else:
    params["path_to_output"] = os.getcwd() + "/output/" + args.run_name + "/"        

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
base_model.model.setParam("LogFile", params["path_to_output"] + "log")
base_model.model.setParam("MIPGap", params["mip_gap"])
base_model.model.setParam("TimeLimit", params["time_limit"])
base_model.model.setParam("Method", params["solver_method"])
base_model.model.write(params["path_to_output"] + "solution.sol")    
base_model.model.optimize()


# In[ ]:


with open(params["path_to_output"] + 'model_params.json', 'w') as fp:
    del params["input1"]
    del params["input2"]
    json.dump(params, fp)
    
with open(params["path_to_output"] + 'model_scenarios.json', 'w') as fp:
    json.dump(model_scenarios, fp)

