import numpy as np
from utils import *
import gurobipy as gp
from gurobipy import GRB

class three_stage_model:
    def __init__(self, model_params, model_scenarios):
        self.big_m = model_params["big_m"]
        
        self.main_input1, self.main_input2 = prepare_input(model_params["path_to_input"])
        self.filter_col = filter_col_creater(model_scenarios)
        self.model_scenarios = model_scenarios

        self.n_buses = self.main_input1.shape[0]
        self.n_branches = self.main_input2.shape[0]
        self.n_scenario = len(model_scenarios[0])
        self.n_models = len(model_scenarios.keys())
        
        self.substations = self.main_input1["SubNum"].unique() # list of unique substations
        self.buses = self.main_input1["bus_index"].unique()    # list of unique buses
        
        self.max_mit = model_params["max_mit"]
        self.mit_level = model_params["mit_level"]
        self.max_prep = model_params["max_prep"]
        self.prep_level = model_params["prep_level"]
        
        self.flexible_generation = model_params["flexible_generation"]
        self.reference_bus = model_params["reference_bus"]
        
        self.fixed_cost = model_params["fixed_cost"]
        self.variable_cost = model_params["variable_cost"]
        self.td_cost = model_params["td_cost"]
        self.operating_cost = model_params["operating_cost"]
        self.tau = model_params["tau"]
        self.restore_time = model_params["restore_time"]
        self.voll = model_params["voll"]

        self.first_stage_binary = model_params["first_stage_binary"]

        # Creating of node arc incidence matrix
        self.node_arc_incidence_matrix, self.node_edge_dictionary = node_matrix(self.main_input1, self.main_input2)
        
        # Creating bus_info and substation_info
        self.bus_info = {} # substation id of bus
        self.substation_info = {} # max flood level for each substation
        for i in self.substations:
            self.substation_info[i] = self.main_input1[self.main_input1["SubNum"] == i][self.filter_col].max(axis=1).iloc[0]
        for i in range(len(self.buses)):
            self.bus_info[i] = self.main_input1[self.main_input1["bus_index"] == i].iloc[0,2]   
        
        self.create_model()
        self.stage_one_constraints()

        # if self.first_stage_binary:
        #     self.stage_one_binary()
        
        self.linking_constraints()
        self.dc_constraints()
        self.slack_bus_phase_angle()
        self.flow_conservation()
        self.load_loss_aggregation()
        self.mitigation_cost()
        self.td_acquisition_cost()
        self.deployment_cost()
        self.voll_constraint()
        self.objective_function()

    def create_model(self):
        
        self.model = gp.Model("base_model")
        self.i_oc = self.model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=GRB.INFINITY, name="i_oc")
        self.i_voll = self.model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=GRB.INFINITY, name="i_voll")
        self.i_mitigation = self.model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=GRB.INFINITY, name="i_mitigation")
        self.i_preparedness = self.model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=GRB.INFINITY, name="i_preparedness")

        self.td_units = self.model.addVar(vtype=GRB.INTEGER, lb=0, ub=GRB.INFINITY, name="td_units")

        self.y_mit = self.model.addVars(self.substations, vtype=GRB.BINARY, name="y_mit")
        self.x_mit = self.model.addVars(self.substations, vtype=GRB.BINARY, name="x_mit")
        
        self.y_prep = self.model.addVars(self.substations, np.arange(self.n_models), vtype=GRB.BINARY, name="y_prep")
        self.x_prep = self.model.addVars(self.substations, np.arange(self.n_models), lb=0, ub=int(self.max_prep/self.prep_level), vtype=GRB.INTEGER, name="x_prep")
        
        self.max_x = self.model.addVars(self.substations, np.arange(self.n_models), vtype=GRB.INTEGER, name="max_x")

        self.z = self.model.addVars(np.arange(self.n_buses), np.arange(self.n_scenario), np.arange(self.n_models), vtype=GRB.BINARY, name="z")
        self.alpha = self.model.addVars(np.arange(self.n_buses), np.arange(self.n_scenario), np.arange(self.n_models), vtype=GRB.BINARY, name="alpha")

        self.g = self.model.addVars(np.arange(self.n_buses), np.arange(self.n_scenario), np.arange(self.n_models), lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="g")
        self.s = self.model.addVars(np.arange(self.n_buses), np.arange(self.n_scenario), np.arange(self.n_models), lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="s")
        self.theta = self.model.addVars(np.arange(self.n_buses), np.arange(self.n_scenario), np.arange(self.n_models), lb=-3.14, ub=3.14, vtype=GRB.CONTINUOUS, name="theta")
        
        self.rho = self.model.addVars(np.arange(self.n_scenario), np.arange(self.n_models), lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="rho")
        self.edge = self.model.addVars(np.arange(self.n_branches), np.arange(self.n_scenario), np.arange(self.n_models), lb= -GRB.INFINITY, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="edge")

    def stage_one_constraints(self):
        #self.model.addConstrs((self.mit_level*self.x_mit[i] <= self.max_mit*self.y_mit[i] for i in self.substation_info), name = "mitigation_constraint")
        self.model.addConstrs((self.prep_level*self.x_prep[i,m] <= self.max_prep*self.y_prep[i,m] for m in range(self.n_models) for i in self.substation_info), name="preparedness_constraint")
        self.model.addConstrs((self.prep_level*self.x_prep.sum('*', m) <= self.td_units for m in range(self.n_models)), name="tiger_dam_limit")

    def stage_one_binary(self):
        #self.model.addConstrs((self.mit_level*self.x_mit[i] == self.substation_info[i]*self.y_mit[i] for i in self.substation_info), name="binary_first_stage")
        self.model.addConstrs((self.x_mit[i] == self.y_mit[i] for i in self.substation_info), name="binary_first_stage")

    def linking_constraints(self):
        for m in range(self.n_models):
            new_tags = list(self.main_input1.columns[0:9]) + self.model_scenarios[m]
            input1 = self.main_input1[new_tags].copy().values
            for k in range(self.n_scenario):
                for j in range(self.n_buses):
                    # stage 1 to 2 linking constraints
                    threat = input1[j,9+k]
                    mitigation = self.x_mit[self.bus_info[j]]*self.substation_info[self.bus_info[j]]
                    preparedness = self.x_prep[self.bus_info[j],m]*self.prep_level
                    self.model.addConstr(1 - self.z[j,k,m] >= (threat - self.max_x[self.bus_info[j],m])/35, name="linking_1" + str(m) + str(k) + str(j))
                    self.model.addConstr(self.z[j,k,m] >= (self.max_x[self.bus_info[j],m] - threat + 0.5)/35, name="linking_2" + str(m) + str(k) + str(j))
                    self.model.addConstr(self.max_x[self.bus_info[j],m] >= mitigation, name="reformulation_1" + str(m) + str(k) + str(j))
                    self.model.addConstr(self.max_x[self.bus_info[j],m] >= preparedness, name="reformulation_2" + str(m) + str(k) + str(j))
                    self.model.addConstr(self.max_x[self.bus_info[j],m] <= mitigation + 25*self.y_prep[self.bus_info[j],m], name="reformulation_3" + str(m) + str(k) + str(j))
                    self.model.addConstr(self.max_x[self.bus_info[j],m] <= preparedness + 25*(1-self.y_prep[self.bus_info[j],m]), name="reformulation_4" + str(m) + str(k) + str(j))       
                    # Supply and demand constraints
                    self.model.addConstr(self.s[j,k,m] <= self.z[j,k,m]*input1[j,8])
                    if self.flexible_generation:
                        self.model.addConstr(self.alpha[j,k,m]*input1[j,6] <= self.g[j,k,m], name="flex_gen_1" + str(m) + str(k) + str(j))
                        self.model.addConstr(self.alpha[j,k,m]*input1[j,7] >= self.g[j,k,m], name="flex_gen_2" + str(m) + str(k) + str(j))
                        self.model.addConstr(self.alpha[j,k,m] <= self.z[j,k,m], name="dispatch_decisions" + str(m) + str(k) + str(j))
                    else:
                        self.model.addConstr(self.z[j,k,m]*input1[j,6] <= self.g[j,k,m], name="non_flex_1" + str(m) + str(k) + str(j))
                        self.model.addConstr(self.z[j,k,m]*input1[j,7] >= self.g[j,k,m], name="non_flex_2" + str(m) + str(k) + str(j))

    def dc_constraints(self):
        big_M = self.big_m
        for m in range(self.n_models):
            new_tags = list(self.main_input1.columns[0:9]) + self.model_scenarios[m]
            input1 = self.main_input1[new_tags].copy()
            input2 = self.main_input2.copy()
            temp_index = np.array(input1.index)
            input1 = input1.values
            input2 = input2.values
            for k in range(self.n_scenario):
                for r in range(self.n_branches):            
                    head = input1[np.where(temp_index == input2[r,1])[0][0], 0]
                    tail = input1[np.where(temp_index == input2[r,2])[0][0], 0]
                    self.model.addConstr(-self.z[head, k, m]*input2[r, 4] <= self.edge[r,k,m], name="flow_1" + str(m) + str(k) + str(r))
                    self.model.addConstr(self.edge[r,k,m] <=  self.z[head,k,m]*input2[r, 4], name="flow_2" + str(m) + str(k) + str(r))
                    self.model.addConstr(-self.z[tail, k, m]*input2[r, 4] <= self.edge[r,k,m], name="flow_3" + str(m) + str(k) + str(r))
                    self.model.addConstr(self.edge[r,k,m] <= self.z[tail, k, m]*input2[r, 4], name="flow_4" + str(m) + str(k) + str(r))
                    
                    self.model.addConstr(big_M*(self.z[head,k,m] + self.z[tail,k,m]) -2*big_M + self.edge[r,k,m] <= input2[r,3]*(self.theta[head,k,m] - self.theta[tail,k,m]), name="phase_1" + str(m) + str(k) + str(r))
                    self.model.addConstr(-big_M*(self.z[head,k,m] + self.z[tail,k,m]) + 2*big_M + self.edge[r,k,m] >= input2[r,3]*(self.theta[head,k,m] - self.theta[tail,k,m]), name="phase_2" + str(m) + str(k) + str(r))

    def slack_bus_phase_angle(self):
        self.model.addConstrs((self.theta[self.reference_bus,k,m] == 0 for k in range(self.n_scenario) for m in range(self.n_models)), name="slack")

    def flow_conservation(self):
        for m in range(self.n_models):
            for k in range(self.n_scenario):
                for i in range(self.n_buses):
                    temp = 0
                    for j in self.node_edge_dictionary[i]:
                        temp =  temp + self.node_arc_incidence_matrix[i,j]*self.edge[j, k, m]
                    self.model.addConstr(temp == self.g[i,k,m] - self.s[i,k,m], name="flow_conservation" + str(m) + str(k) + str(i))

    def load_loss_aggregation(self):
        input1 = self.main_input1.copy()
        for m in range(self.n_models):
            for k in range(self.n_scenario):
                temp = 0
                for j in range(self.n_buses):
                    temp = temp + (input1.iloc[j,8] - self.s[j,k,m])
                self.model.addConstr(temp*100 == self.rho[k,m], name="load_loss" + str(m) + str(k))

    def mitigation_cost(self):
        mitigation_cost = 0
        for i in self.substation_info:
            mitigation_cost = mitigation_cost + self.fixed_cost*self.y_mit[i] + self.variable_cost*self.x_mit[i]*self.substation_info[i]
        self.model.addConstr(self.i_mitigation == mitigation_cost, name="mitigation_budget_main_constraint")

    def td_acquisition_cost(self):
        preparedness_cost = self.td_cost*self.td_units
        self.model.addConstr(self.i_preparedness == preparedness_cost, name="preparedness_budget_main_constraint")

    def deployment_cost(self):
        operating_cost = 0
        for m in range(self.n_models):
            temp = 0
            for i in self.substation_info:
                temp = temp + self.y_prep[i,m]
            temp = temp*self.operating_cost
            temp = temp/(self.n_models)
            operating_cost = operating_cost + temp
        operating_cost = operating_cost*self.tau
        self.model.addConstr(self.i_oc == operating_cost, name="oc_budget_main_constraint")

    def voll_constraint(self):
        value_of_load_loss = 0
        for m in range(self.n_models):
            temp = 0
            for k in range(self.n_scenario):
                temp = temp + (1/self.n_scenario)*self.restore_time*self.rho[k,m] # in MW
            temp = temp/self.n_models
            value_of_load_loss = value_of_load_loss + temp
        value_of_load_loss = self.tau*self.voll*value_of_load_loss
        self.model.addConstr(self.i_voll == value_of_load_loss, name="voll_budget_main_constraint")

    def objective_function(self):
        self.model.setObjective(self.i_mitigation + self.i_oc + self.i_preparedness + self.i_voll, GRB.MINIMIZE)