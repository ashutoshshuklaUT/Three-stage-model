import pandas as pd
import json

main_path = "/work2/07346/ashukla/stampede2/ThreeStageModel/output/modified_td_prep_" 

variable_list = [18,24]
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
df = pd.DataFrame(data_list)
df = df/1e6
df = df.round(2)
df.to_csv("parsed_data.csv", header=None)
