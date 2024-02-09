##################################################################### Network Representations for Use-Cases ##################################################################
import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from Toolkit.demand_generation import *

plt.style.use(['science',"no-latex"])
plt.rc('font',**{'family':'sans-serif','sans-serif':['Century Gothic']})
plt.rcParams['figure.figsize'] = [16, 8]

def get_approx_measures(l,mu,c):

    '''
    Generates approximate measures to be used in the SBC approach:

    Args:
        l (np.array) : arrival rates per unit of time.
        mu (np.array) : processing rate of server per unit of time.
        c (np.array) : available servers per unit of time.

    Returns:
        P (float): Probability of the system having a backlog (not serving everyone at this timestep)
        E (float): Utilization of the servers. (probability of the system being empty)
        l_mar (float) : Modified arrival rate for the SBC approach
    '''

    P = (l/mu)**c/(math.factorial(c)*(sum([((l/mu)**x)/(math.factorial(x)) for x in range(0,c+1)])))
    E = (l-P*l)/(c*mu)
    l_mar = c*mu*E
    return P,E,l_mar

def get_mmc_measures(l_mar,mu,c):

    '''
    Generates approximate measures from the M/M/C queue using the formulas from
    Queueing Networks And Markov Chains - Modelling And Performance Evaluation With Computer Science Applications (p.218,Eq.6.27-28):

    Args:
        l_mar (np.array) : modified arrival rates per unit of time.
        mu (np.array) : processing rate of server per unit of time.
        c (np.array) : available servers per unit of time.

    Returns:
        L_q (float): Number of people in the queue
        W (float): Waiting time in the queue in minutes
    '''

    rho = l_mar/(c*mu)
    cons = ((c*rho)**c)/(math.factorial(c)*((1-rho)))
    P_0 = sum([((c*rho)**x)/(math.factorial(x))  for x in range(0,c)]) + cons
    P_0 = (P_0)**(-1)
    Lq = (P_0 *(l_mar/mu)**c*rho)/(math.factorial(c)*((1-rho)**2))
    W = Lq/l_mar
    return Lq,W

def get_mdc_measures(l_mar,mu,c,W_m):

    '''
    Generates approximate measures from the M/D/C queue using the formulas from
    Queueing Networks And Markov Chains - Modelling And Performance Evaluation With Computer Science Applications (p.231,Eq.6.82):

    Args:
        l_mar (np.array) : modified arrival rates per unit of time.
        mu (np.array) : processing rate of server per unit of time.
        c (np.array) : available servers per unit of time.

    Returns:
        L_q (float): Number of people in the queue
        W (float): Waiting time in the queue in minutes

    '''

    rho = l_mar/(c*mu)
    nc = (1 + (1-rho)*(c-1)*((4+5*c)**0.5-2)/(16*rho*c))**(-1)
    W = 0.5*(1/(nc))*W_m
    Lq = W*l_mar
    return Lq,W

def get_arrival_rates(df,queue_chars,point):

    '''
    Isolates arrival rates at specific point in the chain

    Args:
        PT_DF (pd.DataFrame) : Arrivals flows from PT; stored as xlsx file
        PT_CARS (pd.DataFrame) : Arrivals flows from Cars & Taxi; stored as xlsx file
        queue_chars (dict) : Queue characteristics for specific points in the airport
        point (str) : point in the airport (model-CHECK, BAGS, PASSPORT).

    Returns:
        t (list): Timesteps in the examined queue
        l (np.array): Flow rates in the examined queue per timestep
        mu (np.array): Processing rate in the examined queue per timestep
        c (np.array): Available servers in the examined queue per timestep

    '''

    # Concat DFs and sort by activation time               
    # Isolate traffic at examined point
    df_mod = df[point]

    df_mod = df_mod.reindex(list(range(df_mod.index.min(),df_mod.index.max()+1)),fill_value=1e-16)

    #Initialise timesteps and lambda
    t = df_mod.index.tolist()

    #Initialise timesteps and lambda
    t = df_mod.index.tolist()
    l = df_mod.tolist()
    l = [0] * t[0] + l
    l = l + [0] * (1440-t[-1])
    t = range(1441)

    
    # Concentrate arrivals to timesteps related to mean service time
    # t = [x for x in t if x % queue_chars[point]['mean_service_time'] == t[0] % queue_chars[point]['mean_service_time']]
    # l = np.array([sum(l[x:x+queue_chars[point]['mean_service_time']]) for x in range(len(l)) if x % queue_chars[point]['mean_service_time'] == 0])
    l = np.array(l)
    mu = np.ones(l.shape)*queue_chars[point]['mean_service_time']

    # l = df_mod.values.tolist()


    # # Concentrate arrivals to timesteps related to mean service time
    # #t = [x for x in t if x % queue_chars[point]['mean_service_time'] == t[0] % queue_chars[point]['mean_service_time']]
    # l = np.array([sum(l[x:x+queue_chars[point]['mean_service_time']]) for x in range(len(l)) if x % queue_chars[point]['mean_service_time'] == 0])
    # mu = np.ones(l.shape)/queue_chars[point]['mean_service_time']
    # #c = (np.ones(l.shape)*queue_chars[point]['servers']).astype(int)

    return t,l,mu

def plot_queue_stats(t,E,Lq,Wq,point):
    # Initialise the subplot function using number of rows and columns
    figure, axis = plt.subplots(1, 3)
    
    # For Utilization
    axis[0].plot(t, E)
    axis[0].set_title(f"Utilization of servers per minute in {point}")
    axis[0].set(xlabel="", ylabel="Utilization")
    
    # For Queue Lengths
    axis[1].plot(t, Lq)
    axis[1].set_title(f"Length of Queue(s) per minute in {point}")
    axis[1].set(xlabel="", ylabel="Persons")
    
    # For Waiting time is Queue
    axis[2].plot(t, Wq)
    axis[2].set_title(f"Waiting time in Queue(s) per minute in {point}")
    axis[2].set(xlabel="Minutes", ylabel="Seconds")


    # Combine all the operations and display
    plt.show()

def get_queues(df,queue_chars,model):
    next_point = {"C1":{},"C2":{},"C3":{},"C4":{},"C5":{},
                  "C6":{},"C7":{},"C8":{},"C9":{},"C10":{},"C11":{},
                  "X-RAY":{}}
    waiting_time = {}
    queue_people = {}
    enter = False
    servers = []
    c = int(model.args.min_open)
    
    for point in queue_chars.keys():

        if point == "X-RAY" and enter == False:
            c = int(model.args.min_open)
            enter = True

        waiting_time[point] = 0
        queue_people[point] = 0

        # Get Exlusive traffic (starting point is point)
        try:
            dummy = df[point]
        except:
            continue

        t,l,mu = get_arrival_rates(df,queue_chars,point=point)
        
        s2,mean_service = queue_chars[point]['S_SQUARED'], queue_chars[point]['mean_service_time']

        # Initialize probabilities of backlog
        P=np.zeros(l.shape)
        l_t= np.zeros(l.shape)
        E = np.zeros(l.shape)
        l_mar = np.zeros(l.shape)

        
        # Add Incoming traffic from other points
        index = 0
        for step in next_point[point].keys():
            if step in t:
                index = t.index(step)
                l[index]+=next_point[point][step]
            else:
                l[index]+=next_point[point][step]


        # Get state at time-window 0
        l_t[0] = l[0]
        P[0],E[0],l_mar[0]= get_approx_measures(l_t[0],mu[0],c)

        # Store M/m/c measures
        Lq_M,Wq_M = [],[]

        # Store M/d/c measures
        Wq_D,Lq_D = [],[]

        # Store M/g/c (Final) measures
        Lq,Wq,Ex_q = [],[],[]

        for idx in range(l.shape[0]):
            if idx != 0:       
                l_t[idx] = l[idx] + P[idx-1]*l_t[idx-1] # Modify l tilde
                P[idx],E[idx],l_mar[idx]= get_approx_measures(l_t[idx],mu[idx],c)

            # Store M/M/C
            Lq_m,Wq_m = get_mmc_measures(l_mar[idx],mu[idx],c)
            Lq_M.append(Lq_m)
            Wq_M.append(Wq_m)

            # Store M/D/c
            Lq_d,Wq_d = get_mdc_measures(l_mar[idx],mu[idx],c,Wq_m) 
            Wq_D.append(Wq_d)
            Lq_D.append(Lq_d)

            # Cosmetatos Approximation p.231 (6.81)
            W = (s2*Wq_m + (1-s2)*Wq_d)

            if np.isnan(W):
                W = 0
            L = (W)*l_mar[idx]

            Wq.append(W)
            Lq.append(L)

            if (W >=int(model.args.trigger) or L >=200) and (point == "X-RAY") and (idx % 30 == 0):
                c = min(19,c+int(model.args.increase)+2)
            elif W <=2 and point == "X-RAY" and (idx % 30 == 0) :
                c = max(int(model.args.min_open),c-int(model.args.increase))

            if point != "X-RAY":
                walk = queue_chars[point]['walk']
            else:
                walk = 0
                servers.append(c)
                
            for idx2,x in enumerate(queue_chars[point]['trans_point']):
                if round(t[idx]+mean_service+W+walk) not in next_point[x].keys():
                    next_point[x][round(t[idx]+mean_service+W+walk)] = round(queue_chars[point]['trans'][idx2]*l[idx])
                else:
                    next_point[x][round(t[idx]+mean_service+W+walk)] += round(queue_chars[point]['trans'][idx2]*l[idx])
        
        waiting_time[point] = Wq
        queue_people[point] = Lq

    return waiting_time,servers,queue_people 

def get_flows(agents_mod):
    # Initialize an empty list to store duplicated rows
    duplicated_rows = []

    # Iterate through each row in the DataFrame
    for index, row in agents_mod.iterrows():
        # Get the value from the 'n_times' column
        n = int(row['NO_PERSONS'])

        if n >=2:
            # Create a copy of the row and append it to the list 'n' times
            duplicated_rows.extend([row] * (n-1))

    # Create a new DataFrame with the duplicated rows
    duplicated_df = pd.DataFrame(duplicated_rows, columns=agents_mod.columns)

    # Concatenate the original DataFrame with the duplicated DataFrame
    agents_mod = pd.concat([agents_mod, duplicated_df], ignore_index=True)
    agents_mod = agents_mod.drop(columns=['NO_PERSONS'])

    agents_f = agents_mod.copy()
    spawn = []
    for idx,r in agents_mod.iterrows():
        try:
            agents_f.at[idx,"END_TIME"] = 60*r.E_TIME.hour +r.E_TIME.minute
        except:
            agents_f.at[idx,"END_TIME"] = 60*r.END_TIME.hour +r.END_TIME.minute
        if r.MODE == "TRAIN" or r.MODE == "COACH":
            agents_f.at[idx,"APPROACH"] = np.NaN
            agents_f.at[idx,"DROP_OFF"] = np.NaN
            
            if r.MODE == "COACH":
                spawn.append("COACH")
            else:
                spawn.append("TRAIN")
            try:
                if r.LINE_USED == "EMERGENCY COACH":
                    spawn[-1] = "E"
            except:
                pass

        else:
            mode  = r.MODE
            if mode == None or mode == "None":
                mode = "CAR"

            try:
                if r.APPROACH == "SOUTH":
                    spawn.append(f"SOUTH/{mode}")
                else:
                    spawn.append(f"NORTH/{mode}")
            except:
                if weighted_choice(50):
                    spawn.append(f"SOUTH/{mode}")
                else:
                    spawn.append(f"NORTH/{mode}")
                    
        try:
            b = r.STATUS
        except:
            agents_f.at[idx,"STATUS"] = 'NORMAL'
            agents_f.at[idx,"ACTIVATION"] = r.ACTIVATION_TIME

    agents_f["SPAWN"] = spawn
    
    agents_f = agents_f[['FLIGHT','GATE','DEPARTURE','END_TIME','STATUS','SPAWN']]
    agents_f = agents_f.astype(int, errors='ignore')
    agents_f = agents_f.rename(columns={'END_TIME': 'PAX ARRIVAL'})
    agents_f = agents_f.sort_values(by=['PAX ARRIVAL', 'DEPARTURE'])
    return agents_f


def update_flows(model,agent_mode,agent_bags,agent_gate,agent_persons,agent_ARR_TIME,flow_update = {}):
    # Compute "spawning" times based on mode and profile of passengers
    if agent_mode == "CAR" or agent_mode == "TAXI" or agent_mode == None:
        if agent_bags == 1:
            check_time = round(agent_ARR_TIME+model.arr_to_check.loc[agent_gate,"Time Car (min)"])
            if (check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}") not in flow_update.keys(): 
                flow_update[check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"] = agent_persons
            else:
                flow_update[check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"] += agent_persons
        else:
            check_time = round(agent_ARR_TIME+model.arr_to_xray.loc['CAR',"Time (min)"])
            if (check_time, "X-RAY") not in flow_update.keys(): 
                flow_update[check_time, "X-RAY"] = agent_persons
            else:
                flow_update[check_time, "X-RAY"] += agent_persons
    else:
        if agent_bags == 1:
            check_time = round(agent_ARR_TIME+model.arr_to_check.loc[agent_gate,"Time Train (min)"])
            if (check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}") not in flow_update.keys(): 
                flow_update[check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"] = agent_persons
            else:
                flow_update[check_time, f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"] += agent_persons                            
        else:
            check_time = round(agent_ARR_TIME+model.arr_to_xray.loc['CAR',"Time (min)"])
            if (check_time, "X-RAY") not in flow_update.keys(): 
                flow_update[check_time, "X-RAY"] = agent_persons
            else:
                flow_update[check_time, "X-RAY"] += agent_persons
    return flow_update

def update_safety_margins(model,agent_ARR_TIME,agent_safety,agent_bags,agent_MODE,agent_gate,st):

    # Update Safety margins based on current conditions
    MISSED = 0
    proc_time = 0
    if agent_ARR_TIME == st:
        
        proc_time += model.waiting_time["X-RAY"]+0.5
        if agent_bags == 1:
            if agent_MODE == "CAR" or agent_MODE == "TAXI" or agent_MODE == None:
                proc_time += model.arr_to_check.loc[agent_gate,"Time Car (min)"]
            else:
                proc_time += model.arr_to_check.loc[agent_gate,"Time Train (min)"]
            proc_time += model.waiting_time[f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"]+2
            proc_time += model.queue_chars[f"C{model.arr_to_check.loc[agent_gate,'Check-in']}"]['walk']
        else:
            if agent_MODE == "CAR" or agent_MODE == "TAXI" or agent_MODE == None:
                proc_time += model.queue_chars["CAR"]['walk']
            else:
                proc_time += model.queue_chars["TRAIN"]['walk']

        agent_safety -= proc_time 
        
        if agent_safety <=25:
            MISSED=1
        return MISSED,agent_safety,round(proc_time)  
    else:
        return 0,agent_safety,round(proc_time)

