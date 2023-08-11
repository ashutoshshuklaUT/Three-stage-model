from utils import *
import pandas as pd
from three_stage_model import *
import json
import os

def get_df_for_heuristic():
    df = pd.read_csv("/home1/07346/ashukla/ThreeStageModel/data/192_Scenario/Final_Input1.csv")
    directions = ["w", "wnw", "nw", "nnw", "n", "nne"]
    categories = ["2", "3", "4", "5"]
    forward_speeds = ["05", "10", "15", "25"]
    lister = []
    for i in directions:
        for j in range(len(categories)):
            for k in range(len(forward_speeds)):
                lister.append("max_flood_level_" + i +"_" + categories[j] + "_" + forward_speeds[k])
    df = df[list(df.columns[0:9]) + lister]
    df_sub = df[["SubNum", "load"]].groupby("SubNum").sum()
    df_flood = df[["SubNum"] + lister]
    df_flood = df_flood.drop_duplicates().set_index("SubNum") # drop duplicates
    df_flood = df_flood.loc[(df_flood.sum(axis=1) != 0), :] # drop substations that are not flooded
    """df_sub has load demand for all the substations"""
    """df_flood has only flooded substations"""
    return df, df_sub, df_flood

def flood_info_generator(model_scenarios, df_flood):
    """Dictionary flood_info contains information on how frequently was each substation flooded 
    in each mini-Brent case. They key is substation id. The value is another dictionary whose each 
    entry is mini-Brent model id. And the value of this dictionary is how many scenarios 
    within this mini-brent model was that substation flooded."""
    flood_info = {}
    for i in df_flood.index:
        flood_info[i] = {}
        for j in model_scenarios:
            counter = 0
            for k in model_scenarios[j]:
                if df_flood.loc[i, k] > 0:
                    counter = counter + 1
            flood_info[i][j] = counter
    return flood_info

def compute_load_shed_no_measure(flood_info, df_sub, model_scenarios, params, df_flood):
    expected_load_shed = {}
    for i in flood_info:
        load_value = df_sub.loc[i,"load"]
        temp = 0
        for j in flood_info[i]:
            """We see in how many leaves out of 216 it is flooded"""
            temp = temp + load_value*flood_info[i][j]
        expected_load_shed[i] = temp/(len(model_scenarios.keys())*len(model_scenarios[0]))
        expected_load_shed[i] = [round(expected_load_shed[i]*params["voll"]*params["restore_time"]*params["tau"]/1e6,3), df_flood.loc[i,:].max()]
    main_df = pd.DataFrame(expected_load_shed).T
    main_df.columns = ["voll_million", "max_flood"]
    main_df["prepare_million"] = 1e12
    main_df["mitigate_million"] = 1e12
    """Note that: Every substation in main_df is flooded atleast once"""
    for i in main_df.index:
        hardening_cost = params["fixed_cost"] + params["variable_cost"]*main_df.loc[i, "max_flood"]
        main_df.loc[i, "mitigate_million"] = round(hardening_cost/1e6, 3)
    return main_df

def prep_cost_computer(prep_enough, flood_info, params, model_scenarios):
    for i in prep_enough.index:
        temp = 0 # temp is counter of number of mini-brent cases when tiger dams need to be deployed
        for j in flood_info[i]:
            if flood_info[i][j] > 0:
                temp = temp + 1
        temp = temp/len(model_scenarios.keys())
        temp = temp*params["operating_cost"]*params["tau"]
        prep_enough.loc[i, "prepare_million"] = round((prep_enough.loc[i, "max_flood"]*params["td_cost"] + temp)/1e6, 3)
    return prep_enough

def mit_prep_fixable_substation(mit_enough, df_flood, params):
    temp_df = df_flood.loc[mit_enough.index,:].copy() # only mit indices will be present
    temp_df = temp_df[(temp_df > 0) & (temp_df <= params["prep_level"])]
    temp_df = temp_df.dropna(thresh=1)
    can_be_fixed = list(temp_df.index)
    return can_be_fixed

def mit_cost_computer(mit_enough, params, flood_info, model_scenarios, df_flood, df_sub):
    """For each substation deploy_count counts the number of times, deployment happened in mini-brent models. 
    load_loss counts the number of times flooding happened"""
    deploy_count = {} 
    load_loss = {}
    for i in mit_enough.index:
        deploy_count[i] = 0
        load_loss[i] = 0
        max_preventable_flooding = 0
        for j in flood_info[i]:
            flag = 0
            for k in model_scenarios[j]:
                flood_level = df_flood.loc[i,k]
                if (flood_level > 0) & (flood_level <= params["prep_level"]):
                    flag = 1
                    if flood_level > max_preventable_flooding:
                        max_preventable_flooding = flood_level
                if flood_level > params["prep_level"]:
                    load_loss[i] = load_loss[i] + 1
            deploy_count[i] = deploy_count[i] + flag
        deploy_count[i] = [deploy_count[i], max_preventable_flooding]
    for i in deploy_count:
        deploy_count[i].append(load_loss[i])
    mitigate = pd.DataFrame(deploy_count).T
    mitigate.columns = ["deploy_counts", "max_td_units", "load_loss_flood_counts"]
    
    for i in mitigate.index:
        O_C = (mitigate.loc[i,"deploy_counts"]/len(model_scenarios.keys()))*params["operating_cost"]*params["tau"]
        V_C = mitigate.loc[i,"load_loss_flood_counts"]/(len(model_scenarios.keys())*len(model_scenarios[0]))
        V_C = V_C*df_sub.loc[i,"load"]*params["voll"]*params["restore_time"]*params["tau"]
        A_C = params["td_cost"]*mitigate.loc[i,"max_td_units"]
        T_C = O_C + V_C + A_C
        T_C = round(T_C/1e6,3)
        mit_enough.loc[i, "prepare_million"] = T_C    
    return mitigate, mit_enough

def heuristic(df_type, flood_info, df_flood, model_scenarios, params):
    heuristic_dictionary = {}
    for i in df_type.index:
        heuristic_dictionary[i] = {}
        min_value = min(df_type.loc[i,"voll_million"], 
                        min(df_type.loc[i,"prepare_million"], df_type.loc[i,"mitigate_million"]))
        if min_value == df_type.loc[i,"prepare_million"]:
            heuristic_dictionary[i]["x_mit"] = 0
            heuristic_dictionary[i]["y_mit"] = 0
            for j in flood_info[i]:
                if flood_info[i][j] > 0:
                    # here we check that for flooded substation, can it be protected with tiger dams
                    flag = 0
                    max_preventable_flooding = 0
                    for k in model_scenarios[j]:
                        flood_level = df_flood.loc[i,k]
                        if (flood_level > 0) & (flood_level <= params["prep_level"]):
                            flag = 1
                            if flood_level > max_preventable_flooding:
                                max_preventable_flooding = flood_level
                    # So if in any one scenario, flooding can be prevented with tiger dams, we will protect
                    if flag == 1:
                        heuristic_dictionary[i]["p_" + str(j)] = max_preventable_flooding
                        heuristic_dictionary[i]["q_" + str(j)] = 1
                    else:
                        # in this case, there is flooding but it cannot be prevented
                        heuristic_dictionary[i]["p_" + str(j)] = 0
                        heuristic_dictionary[i]["q_" + str(j)] = 0   
                else:
                    heuristic_dictionary[i]["p_" + str(j)] = 0
                    heuristic_dictionary[i]["q_" + str(j)] = 0  
        elif min_value == df_type.loc[i,"mitigate_million"]:
            heuristic_dictionary[i]["x_mit"] = df_type.loc[i, "max_flood"]
            heuristic_dictionary[i]["y_mit"] = 1
            for j in flood_info[i]:  
                heuristic_dictionary[i]["p_" + str(j)] = 0
                heuristic_dictionary[i]["q_" + str(j)] = 0
        else:
            heuristic_dictionary[i]["x_mit"] = 0
            heuristic_dictionary[i]["y_mit"] = 0
            for j in flood_info[i]:
                heuristic_dictionary[i]["p_" + str(j)] = 0
                heuristic_dictionary[i]["q_" + str(j)] = 0
    return heuristic_dictionary

def tighten_model(df_sub, df_flood, flood_info, model_scenarios):
    heuristic_dictionary = {}
    flood_list = list(df_flood.index)
    for i in df_sub.index:
        if i not in flood_list:
            heuristic_dictionary[i] = {}
            heuristic_dictionary[i]["x_mit"] = 0
            heuristic_dictionary[i]["y_mit"] = 0
            for j in model_scenarios:
                heuristic_dictionary[i]["p_" + str(j)] = 0
                heuristic_dictionary[i]["q_" + str(j)] = 0
        else:
            continue
    return heuristic_dictionary

def final_heuristic(flood_info, df_sub, model_scenarios, params, df_flood):
    main_df = compute_load_shed_no_measure(flood_info, df_sub, model_scenarios, params, df_flood)
    prep_enough = main_df[(main_df["max_flood"] <= params["prep_level"])].copy()
    mit_enough = main_df[(main_df["max_flood"] > params["prep_level"])].copy()
    prep_enough = prep_enough[['voll_million', 'prepare_million', 'mitigate_million', 'max_flood']]
    mit_enough = mit_enough[['voll_million', 'prepare_million', 'mitigate_million', 'max_flood']]
    prep_enough = prep_cost_computer(prep_enough, flood_info, params, model_scenarios)
    mitigate, mit_enough = mit_cost_computer(mit_enough, params, flood_info, model_scenarios, df_flood, df_sub)
    prep_dict = heuristic(prep_enough, flood_info, df_flood, model_scenarios, params)
    mit_dict = heuristic(mit_enough, flood_info, df_flood, model_scenarios, params)
    rest_dict = tighten_model(df_sub, df_flood, flood_info, model_scenarios)
    return prep_dict, mit_dict, rest_dict

def opt_solution_reader(model_scenarios, voll_value, path_str, df_flood):
    main_path = path_str + str(voll_value) + "/"
    with open(main_path + "model_params.json", 'r') as f:
        params = json.load(f)   
    params["path_to_input"] = os.getcwd() + "/data/192_Scenario/"
    base_model = three_stage_model(params, model_scenarios)
    base_model.model.update()
    sol_path = main_path + "solution.sol"
    base_model.model.read(sol_path)
    base_model.model.update()
    
    hardening_decisions = {}
    tiger_dam_decisions = {}
    
    for sub_id in df_flood.index:
        hardening_decisions[sub_id] = int(base_model.x_mit[sub_id].Start*params["mit_level"])
    for sub_id in df_flood.index:
        for j in model_scenarios:
            tiger_dam_decisions[str(sub_id) + "_" + str(j)] = int(base_model.x_prep[sub_id,j].Start*params["prep_level"])
    
    return hardening_decisions, tiger_dam_decisions

def post_process_heuristic_output(voll_list, flood_info, df_sub, model_scenarios, params, df_flood):
    heuristic_solution_dictionary = {}
    for voll_value in voll_list:
        params["voll"] = voll_value
        prep_dict, mit_dict, rest_dict = final_heuristic(flood_info, df_sub, model_scenarios, params, df_flood)    
        h = {}
        for i in df_flood.index:
            if i in prep_dict:
                h[i] = int(prep_dict[i]['x_mit'])
            else:
                h[i] = int(mit_dict[i]['x_mit'])
        t = {}
        for i in df_flood.index:
            for j in model_scenarios:
                if i in prep_dict:
                    t[str(i) + "_" + str(j)] = prep_dict[i]["p_" + str(j)]
                else:
                    t[str(i) + "_" + str(j)] = mit_dict[i]["p_" + str(j)]
        heuristic_solution_dictionary[voll_value] = [h,t]
    return heuristic_solution_dictionary, rest_dict

def heuristic_hardening_score(voll_list, df_flood, heuristic_solution_dictionary, optimization_solution_list):
    df_list = []
    for voll in voll_list:
        zeros = 0
        match = 0
        unmatch = 0
        for i in df_flood.index:
            t1 = heuristic_solution_dictionary[voll][0][i]
            t2 = optimization_solution_list[voll][0][i]    
            if (t1 == t2):
                if t1 == 0:
                    zeros = zeros + 1
                else:
                    match = match + 1
            else:
                unmatch = unmatch + 1
        df_list.append([voll, zeros, match, unmatch])
    df_list = pd.DataFrame(df_list)
    df_list.columns = ["voll", "zeros", "match", "unmatch"]
    df_list = df_list.set_index("voll")
    return df_list

def heuristic_td_score(voll_list, df_flood, model_scenarios, heuristic_solution, optimization_list):
    df_list = []
    mismatch = {}
    for voll in voll_list:
        mismatch[voll] = {}
        zeros = 0
        match = 0
        unmatch = 0
        for i in df_flood.index:
            for j in model_scenarios:
                t1 = heuristic_solution[voll][1][str(i) + "_" + str(j)]
                t2 = optimization_list[voll][1][str(i) + "_" + str(j)]    
                if (t1 == t2):
                    if t1 == 0:
                        zeros = zeros + 1
                    else:
                        match = match + 1
                else:
                    if ((t1 > 0) & (t1 <= 6) & (t2 == 6)):
                        match = match + 1
                    else:
                        if i not in mismatch[voll]:
                            mismatch[voll][i] = {}
                            mismatch[voll][i][j] = [t1,t2]
                        else:
                            mismatch[voll][i][j] = [t1,t2]
                        unmatch = unmatch + 1
        df_list.append([voll, zeros, match, unmatch])
    df_list = pd.DataFrame(df_list)
    df_list.columns = ["voll", "zeros", "match", "unmatch"]
    df_list = df_list.set_index("voll")
    return df_list, mismatch