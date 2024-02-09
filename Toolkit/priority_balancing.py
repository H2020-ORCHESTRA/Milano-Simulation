##################################################################### Priority based capacity balancing ##################################################################
import datetime
from Toolkit.dynamic_guidance import *
from Toolkit.network_represenentations import *
from Toolkit.queue_decision_support import * 
import math
import copy

def break_train(pass_shuffle, model,station,flow_update):
    """
    Breaks the train at a specific station.

    :param pass_shuffle: List of passengers generated so far.
    :param model: The simulation model.
    :param station: The station that has the disruption model.
    """
    model.dis_agents = []
    delay = 0
    b= 0 
    for agent in pass_shuffle:
        if agent.LINE_USED == model.break_line:
            if agent.BOARD_TIME <= model.schedule.steps:
                delay -= agent.ARR_TIME
                agent.pos = station.pos
                model.PARTIAL_MARGIN.append(agent.departure-model.schedule.steps)
                model.dis_agents.append(agent)
                reassign(agent,station,model)
                model.priority.append(agent)
                delay += agent.ARR_TIME
                b+=1
            elif agent.BOARD_TIME >= model.schedule.steps:
                agent.st = int(agent.BOARD_TIME-agent.ACCESS_TIME+1)
                assign(agent,model)
                model.priority.append(agent)

            flow_update = update_flows(model,agent.MODE,agent.bags,agent.gate,agent.persons,agent.ARR_TIME,flow_update)
            
            proc_time = 1
            
            if agent.bags == 1:
                if agent.MODE == "CAR" or agent.MODE == "TAXI" or agent.MODE == None:
                    proc_time += model.arr_to_check.loc[agent.gate,"Time Car (min)"]
                else:
                    proc_time += model.arr_to_check.loc[agent.gate,"Time Train (min)"]
                proc_time + model.waiting_time[f"C{model.arr_to_check.loc[agent.gate,'Check-in']}"]+2
                proc_time += model.queue_chars[f"C{model.arr_to_check.loc[agent.gate,'Check-in']}"]['walk']
            else:
                if agent.MODE == "CAR" or agent.MODE == "TAXI" or agent.MODE == None:
                    proc_time += model.queue_chars["CAR"]['walk']
                else:
                    proc_time += model.queue_chars["TRAIN"]['walk']

            if agent.SAFETY_MARGIN-proc_time <=20:
                model.MISSED+=1

    if b!= 0:
        model.delay = round(delay/b)
    return flow_update  

def check_dispatch(model, station, flow_update, board_time=5, bus_cap=45):
    """
    Check and dispatch passengers at a transit station.

    :param station: The transit station to check for passenger dispatch.
    :param board_time: The time it takes for passengers to board a vehicle (default: 5 minutes).
    :param bus_cap: The capacity of the bus (default: 15 passengers).
    """
    coords = (station.lonlat, model.mxp_lonlat)
    t1 = 10 + board_time
    t2 = return_car_route(model.client, coords, radius=250)['routes'][0]['summary']['duration'] / 60
    t = t1 + t2

    margins = [x for x in model.PARTIAL_MARGIN]
    sorted_indices = sorted(range(len(margins)), key=lambda i: margins[i])
    sorted_margins = [margins[i] for i in sorted_indices]
    model.dis_agents = [model.dis_agents[i] for i in sorted_indices]

    done = False
    def_bus_cap = copy.deepcopy(bus_cap)

    caps = sum([x.persons for x in model.dis_agents])
    if caps >=35:
        for idx, x in enumerate(model.dis_agents):

            bus_cap -= x.persons
            delta = datetime.timedelta(days=0, hours=0, minutes=sorted_margins[idx] - t - x.SAFETY_MARGIN).total_seconds()/60
            if delta  <=10:
                done = True
                break
            
            if bus_cap <= 0:
                bus_cap = 0
                break

            if x.SAFETY_MARGIN >= sorted_margins[idx] - t:
                done = True
                break

            x.SAFETY_MARGIN = sorted_margins[idx] - t
            
            x.LINE_USED = "EMERGENCY COACH"
            if delta < 0:
                x.E_TIME += datetime.timedelta(days=0, hours=0, minutes=abs(delta))
            else:
                x.E_TIME -= datetime.timedelta(days=0, hours=0, minutes=abs(delta))
            x.TRANSFER_TIME+= int((x.E_TIME-x.S_TIME).seconds/60)-x.TRAVEL_TIME
            x.TRAVEL_TIME = int((x.E_TIME-x.S_TIME).seconds/60)
            x.IR_RATIO = 1-x.ACCESS_TIME/x.TRAVEL_TIME
            x.MULTIMODAL_EFFECT = x.TRAVEL_TIME/(x.TRAVEL_TIME_CAR)
            flow_update = update_flows(model,x.MODE,x.bags,x.gate,x.persons,x.E_TIME.hour * 60 + x.E_TIME.minute,flow_update)
    else:
        done = True

    if not(done) and len(model.dis_agents) != 0:
        hours, minutes = divmod(round(model.schedule.steps +t), 60)
        model.visualization["bus_finish"] = f"Estimated Arrival at : {hours:02}:{minutes:02}"
        model.store_viz_bf = model.visualization["bus_finish"] 
        model.bus_end = round(model.schedule.steps +t)
        model.visualization["dispatch"] = "COACH DISPATCH IS NEEDED"
        model.stop_show = False
        model.bus_start = model.schedule.steps + 10
        hours, minutes = divmod(model.bus_start, 60)
        model.visualization["bus_start"] =  f"Coach started at : {hours:02}:{minutes:02}"
        model.visualization["passengers"] = f"Passengers on Coach : {def_bus_cap-bus_cap}"
        model.store_viz_bs = model.visualization["bus_start"] 
        model.store_viz_p = model.visualization["passengers"] 
    else:
        model.visualization["dispatch"] = "COACH DISPATCH IS NOT NEEDED"
        model.visualization["active_dis"] = ""
        model.stop_show = True
    
    return flow_update
def check_lines_stations(model,agent,station_update,line_update):

    # Store Transit station for any agent that will be there
    if (agent.TRANSIT_STATION, math.floor(model.schedule.steps + agent.ACCESS_TIME)) not in station_update.keys():
        station_update[(agent.TRANSIT_STATION, math.floor(model.schedule.steps + agent.ACCESS_TIME))] = agent.persons
    else:
        station_update[(agent.TRANSIT_STATION, math.floor(model.schedule.steps + agent.ACCESS_TIME))] += agent.persons
    
    model.delay_lines['None'] = 0
    model.delay_lines[None] = 0
    if agent.LINE_USED != None and agent.LINE_USED != 'None':
        if agent.LINE_USED not in line_update.keys():
            line_update[agent.LINE_USED] = agent.persons

            model.delay_lines[agent.LINE_USED] = 0
            if np.random.random() < model.args.delay_line:
                model.delay_lines[agent.LINE_USED] = np.random.randint(10,20)
            
        else:
            if line_update[agent.LINE_USED] >= 200 and agent.MODE =="TRAIN":
                print(f"Full Capacity - Line {agent.LINE_USED}")
                agent.activation = agent.BOARD_TIME + 1
                agent.LINE_USED = 'None'
            elif line_update[agent.LINE_USED] >= 50 and agent.MODE =="COACH":
                print(f"Full Capacity - Line {agent.LINE_USED}")
                agent.activation = agent.BOARD_TIME + 1
                agent.LINE_USED = 'None'
            else:
                line_update[agent.LINE_USED] += agent.persons

    return station_update,line_update,model

