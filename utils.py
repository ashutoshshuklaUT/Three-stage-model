import numpy as np
import pandas as pd

def prepare_input(path_str):
    # Read, format and do per unit correction
    input1 = pd.read_csv(path_str + "Final_Input1.csv")
    input2 = pd.read_csv(path_str + "Final_Input2.csv")
    input1 = input1.reset_index()
    input1.rename(columns={'index':'bus_index'}, inplace=True)
    input1 = input1.set_index("BusNum")
    input2 = input2.reset_index()
    input2.rename(columns={'index':'edge_index'}, inplace=True)
    # Per unit system correction
    input1["generation_capacity_max"] = input1["generation_capacity_max"]/100
    input1["generation_capacity_min"] = input1["generation_capacity_min"]/100
    input1["load"] = input1["load"]/100
    input2["RATE_A"] = input2["RATE_A"]/100
    return input1, input2

def return_model_scenarios():
    directions = ["w", "wnw", "nw", "nnw", "n", "nne"]
    categories = ["2", "3", "4", "5"]
    #categories = ["4", "5"]
    forward_speeds = ["05", "10"]
    model_scenarios = {}
    counter = 0
    for i in directions:
        for j in range(len(categories)):
        #for j in range(len(categories)-1):
            #for k in range(len(forward_speeds)-2):
            for k in range(len(forward_speeds)-1):
                lister = []
                lister.append("max_flood_level_" + i +"_" + categories[j] + "_" + forward_speeds[k])
                lister.append("max_flood_level_" + i +"_" + categories[j] + "_" + forward_speeds[k+1])
                #lister.append("max_flood_level_" + i +"_" + categories[j] + "_" + forward_speeds[k+2])
                #lister.append("max_flood_level_" + i +"_" + categories[j+1] + "_" + forward_speeds[k])
                #lister.append("max_flood_level_" + i +"_" + categories[j+1] + "_" + forward_speeds[k+1])
                #lister.append("max_flood_level_" + i +"_" + categories[j+1] + "_" + forward_speeds[k+2])
                model_scenarios[counter] = lister
                counter = counter + 1
    return model_scenarios


def filter_col_creater(model_scenarios):
    lister = []
    for i in model_scenarios:
        for j in model_scenarios[i]:
            lister.append(j)
    lister = list(set(lister))
    return lister

def node_matrix(input1, input2):
    # Creating of node arc incidence matrix
    node_arc_incidence_matrix = np.zeros((len(input1), len(input2)))
    for i in range(len(input2)): 
        head = input1.loc[input2.iloc[i,1], "bus_index"]
        tail = input1.loc[input2.iloc[i,2], "bus_index"] 
        node_arc_incidence_matrix[head,i] = 1           # Indicates outgoing flux
        node_arc_incidence_matrix[tail,i] = -1          # Indicates incoming flux

    node_edge_dictionary = {}
    for i in range(len(input2)):
        head = input1.loc[input2.iloc[i,1], "bus_index"]
        tail = input1.loc[input2.iloc[i,2], "bus_index"] 
        if head in node_edge_dictionary.keys():
            node_edge_dictionary[head].append(i)
        else:
            node_edge_dictionary[head] = []
            node_edge_dictionary[head].append(i)

        if tail in node_edge_dictionary.keys():
            node_edge_dictionary[tail].append(i)
        else:
            node_edge_dictionary[tail] = []
            node_edge_dictionary[tail].append(i)

    return node_arc_incidence_matrix, node_edge_dictionary

