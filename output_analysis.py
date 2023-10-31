# Reads from the solution file and prints/accesses required information.

import json
import pandas as pd
main_path = "/work2/07346/ashukla/ls6/ThreeStageModel/output/vc_"

# variable_list = [250,500,1000,2000,3000,4000,5000,6000]
# variable_list = [25,50,75]

data_list = []

for variable in variable_list:
   path = main_path + str(variable) + "/" + "model_params.json"
   with open(path) as user_file:
      parsed_json = json.load(user_file)
   temp_lister = []
   temp_lister.append(int(parsed_json["i_mitigation"]))
   temp_lister.append(int(parsed_json["i_preparedness"]))
   temp_lister.append(int(parsed_json["i_oc"]))
   temp_lister.append(int(parsed_json["i_voll"]))
   data_list.append(temp_lister)
df = (pd.DataFrame(data_list)/1e6).round(2)
df.columns = ["Hardening", "Tiger Dam", "Deployment", "Load Loss"]
df["Total"] = df.sum(axis=1)
df = df.round(2)
df.index = variable_list
df.index.name = "VOLL"
df.to_csv("vc_k.csv")
