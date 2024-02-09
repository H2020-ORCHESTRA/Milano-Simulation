##################################################################### Dynamic Guidance for incoming agents ##################################################################

import pandas as pd
import polyline
from Toolkit.network_represenentations import isolate_route,weighted_choice
from TransitRouting.raptor import raptor
import random
import numpy as np

pd.options.mode.chained_assignment = None 

def return_car_route(client,coords,radius,disruption = []):
    while True:
        try:
            if disruption != []:
                CAR_ROUTE = get_road_route(client,coords[0],coords[1],disruption)
                CAR_ROUTE['routes'] = [{}]
                CAR_ROUTE['routes'][0]['summary'] = CAR_ROUTE['features'][0]['properties']['summary']
                return CAR_ROUTE
            else:
                CAR_ROUTE = client.directions(coords,radiuses=radius)
                return CAR_ROUTE
        except:
            radius +=250
            if radius == 1000:
                
                return None
    

def get_road_route(client,origin,destination,disruption):
    '''
    Returns optimal route based on existing network status

    Args:
        client (openrouteservice.client) : The loaded local instance of the ORS router
        origin (list): Starting position for the route in the (long,lat) format
        destination (list) : Finishing position for the route in the (long,lat) format
        disruption (dict) : Disruption affecting the examined route

    Returns:
        route (dict) : openrouteservice request
    '''

    request_params = {'coordinates': [origin,destination],
                    'format_out': 'geojson',
                    'profile': 'driving-car',
                    'preference': 'recommended',
                    'attributes' : ['avgspeed'],
                    'instructions': True}
    
    base_route = client.directions(**request_params)
    request_params['options'] = {'avoid_polygons': disruption['avoid_polygon']}
    avoid_route = client.directions(**request_params)   

    if  disruption['perc_road'] == 0 :
        return base_route
    
    if disruption['slow_down'] == False:
        request_params['options'] = {'avoid_polygons': disruption['avoid_polygon']}
        avoid_route = client.directions(**request_params)   
        return avoid_route
    
    if disruption['slow_down'] == True:
        slow_route = base_route
        segments = base_route['features'][0]['properties']['segments'][0]['steps']
        for edge in segments:
            if edge['name'] in disruption['edges_speed'].keys():
                edge['duration'] = disruption['edges_speed'][edge['name']]
        
        slow_route['features'][0]['properties']['segments'][0]['steps'] = segments
        slow_route['features'][0]['properties']['summary']['duration'] = sum([x['duration'] for x in segments])

        if slow_route['features'][0]['properties']['summary']['duration'] < avoid_route['features'][0]['properties']['summary']['duration']:
            return slow_route
        else:
            return avoid_route

def get_route_to_list(route):
    '''
    Returns route in a list coordinates format for folium visualization 

    Args:
        route (dict) : openrouteservice request

    Returns:
        loc (list) : list of coordinates
    '''

    loc = route['features'][0]['geometry']['coordinates']
    loc = [(x[1],x[0]) for x in loc]
    return loc

def extract_KPIS(model,agent,mode,CAR_ROUTE,D_TIME,TRANS_ROUTE=None,TRANSFERS=None):

    if mode == "CAR" or mode == "TAXI":
        pl = []
        if model.active_road_disruption != []:
            pl = CAR_ROUTE['features'][0]['geometry']['coordinates']
        
        # Compute Travel Time and Distance by Car 
        agent.TRAVEL_TIME_CAR = CAR_ROUTE['routes'][0]['summary']['duration']/60 + np.random.randint(1,10)
        agent.DISTANCE_CAR = CAR_ROUTE['routes'][0]['summary']['distance']//1000

        # Define Approach of Car route
        if pl == []:
            pl = polyline.decode(CAR_ROUTE['routes'][0]['geometry'])
            pl = [x[0] for x in pl]
        if max(pl) == pl[-1]:
            agent.APPROACH = "SOUTH"
        else:
            agent.APPROACH = "NORTH"

        # Compute Safety Margin, Start of Trip and 
        agent.SAFETY_MARGIN_CAR =  agent.departure - (agent.activation + agent.TRAVEL_TIME_CAR)
        
        # Determine if trip is a drop-off
        if mode == "TAXI":
            agent.DROP_OFF_CAR = True
        else:
            agent.DROP_OFF_CAR = weighted_choice(50)
        agent.BOARD_TIME_STAMP = None
        
    else:

        # Isolate legs of multimodal routes    
        route = isolate_route(agent.unique_id,TRANS_ROUTE,agent.S_TIME_PT,agent.WALK_TIME,model.CH_DELTA)

        # Compute Waiting Time before start of travel 
        agent.WAITING_TIME = (agent.S_TIME_PT-D_TIME-model.CH_DELTA).total_seconds()/60
            
        # Define used last line to access the airport
        agent.LINE_USED = route[-1][-1]
        agent.BOARD_TIME = route[-1][-3].time()
        agent.BOARD_TIME = agent.BOARD_TIME.hour * 60 + agent.BOARD_TIME.minute
        agent.BOARD_TIME_STAMP = route[-1][-3].time()

        # Save the line that was used to the model 
        model.lines.append(agent.LINE_USED)

        # Define Transit Station
        agent.TRANSIT_STATION = route[-1][0]
        agent.TRANSIT_STATION_NAME = model.stops_file['stop_name'].to_numpy()[model.stops_file['stop_id'].to_numpy() == agent.TRANSIT_STATION].item()
        
        # Compute TRAVEL TIME by Public Transport 
        agent.TRAVEL_TIME_PT = (agent.E_TIME_PT-agent.S_TIME_PT).total_seconds()/60

        # Computes mode Transfer that occurred 
        agent.TRANSFERS = TRANSFERS-1

        # Computes ACCESS TIME to reach optimal MXP Station 
        if agent.TRANSFERS > 0:
            agent.ACCESS_TIME = (route[-2][3]-agent.S_TIME_PT).total_seconds()/60
        else:
            agent.ACCESS_TIME = 0 

        # Computes ratio of first mile towards the total trip 
        agent.IR_RATIO = 1-agent.ACCESS_TIME/agent.TRAVEL_TIME_PT

        # Computes total time lost in waiting for the next mode (minimum 2)             
        agent.TRANSFER_TIME = pd.Series([route[x+1][2]-route[x][3] for x in range(len(route)-1)]).sum()
        agent.TRANSFER_TIME = agent.TRANSFER_TIME.total_seconds()/60

        # Computes safety margin between departure and airport arrival for each passenger 
        agent.SAFETY_MARGIN_PT =  agent.departure - (60*agent.E_TIME_PT.hour + agent.E_TIME_PT.minute)

        # Computes percentile increase in TRAVEL TIME by use of PT
        agent.MULTIMODAL_EFFECT = agent.TRAVEL_TIME_PT/(agent.TRAVEL_TIME_CAR)
        agent.WALK_TIME= agent.WALK_TIME.total_seconds()/60

def assign(agent,model):
    '''
    Determine assignment of Passenger and store KPIs when Passenger is activated.

    :param agent: The agent to be assigned.
    :param model: The simulation model.
    '''

    if agent.activation != model.schedule.steps:
        agent.STATUS = "PRIORITY"
        # Current step as timestamp
        D_TIME = pd.Timestamp(year=model.date.year,month=model.date.month,day=model.date.day,
                    hour =agent.st//60,
                    minute=agent.st%60)
    else:
        # Current step as timestamp
        D_TIME = pd.Timestamp(year=model.date.year,month=model.date.month,day=model.date.day,
                    hour =model.schedule.steps//60,
                    minute=model.schedule.steps%60)
        
    # To Spawn users directly at the airport 
    if agent.lonlat == model.mxp_lonlat:
        agent.E_TIME = D_TIME + pd.to_timedelta(int(random.uniform(30, 60)), unit='m')
        agent.APPROACH = random.choice(["SOUTH","NORTH"])
        agent.DROP_OFF_CAR = weighted_choice(50)
        agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute
        agent.SAFETY_MARGIN = agent.departure - agent.ARR_TIME
    else:
        
        ######################## Examine Single modes via Taxi or Car ########################

        agent.MODE = "CAR"

        # Initialize coordinates for route
        coords = (agent.lonlat,model.mxp_lonlat)
        CAR_ROUTE = return_car_route(model.client,coords,250,model.active_road_disruption)
        if CAR_ROUTE == None:
            agent.E_TIME = D_TIME + pd.to_timedelta(int(random.uniform(30, 60)), unit='m')
            agent.APPROACH = random.choice(["SOUTH","NORTH"])
            agent.DROP_OFF_CAR = weighted_choice(50)
            agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute
            agent.SAFETY_MARGIN = agent.departure - agent.ARR_TIME
            return None        

        # Extract KPIS
        extract_KPIS(model,agent,agent.MODE,CAR_ROUTE,D_TIME)
        agent.TRAVEL_TIME = agent.TRAVEL_TIME_CAR
        agent.S_TIME = D_TIME.floor("T")
        agent.E_TIME = D_TIME + pd.Timedelta(minutes=agent.TRAVEL_TIME_CAR).ceil("T")
        agent.SAFETY_MARGIN = agent.SAFETY_MARGIN_CAR
        agent.LINE_USED = "None"
        agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute    

        ####################### Examine use of Multimodality (Bus->Train->Mixed) ########################

        if model.args.skip_access:
            if np.random.random() < float(model.args.modal_split_coach) + float(model.args.modal_split_train):

                # Determine potential Transit Points to access via car or taxi
                CAR_FIRST_MILES = []    
                for tr in model.transit_nodes.keys():
                    coords = (agent.lonlat,model.transit_nodes[tr]['lonlat'])
                    CAR_ROUTE_TRANS = return_car_route(model.client,coords,250,[])
                    CAR_TIME_TRANS = CAR_ROUTE_TRANS['routes'][0]['summary']['duration']/60
                    CAR_FIRST_MILES.append(CAR_TIME_TRANS)

                # Isolate best three
                BEST_TRANSIT = sorted(range(len(CAR_FIRST_MILES)), key=lambda k: CAR_FIRST_MILES[k])
                BEST_TRANSIT = [list(model.transit_nodes.keys())[x] for x in BEST_TRANSIT]
                if np.random.random()<0.5:
                    BEST_TRANSIT = [x for x in BEST_TRANSIT if model.transit_nodes[x]['mode'] == "TRAIN"][0]
                    mode = "TRAIN"
                else:
                    BEST_TRANSIT = [x for x in BEST_TRANSIT if model.transit_nodes[x]['mode'] == "COACH"][0]
                    mode = "COACH"
                S_TIME_PT,E_TIME_PT,TRANSFERS,TRANS_ROUTE = raptor(model.transit_nodes[BEST_TRANSIT]['stop_id'],model.transit_nodes[BEST_TRANSIT]['mxp_node'],D_TIME,1,model.change_time,
                model.routes_by_stop_dict,model.stops_dict,model.stoptimes_dict,model.footpath_dict,
                model.idx_by_route_stop_dict)

                if TRANS_ROUTE != None:
                    agent.S_TIME_PT = S_TIME_PT
                    agent.E_TIME_PT = E_TIME_PT
                    if agent.departure - (60*agent.E_TIME_PT.hour + agent.E_TIME_PT.minute) >= int(model.args.threshold):
                        agent.WALK_TIME = pd.Timedelta(minutes=0) # Representing ACCESS TIME to first station
                        extract_KPIS(model,agent,mode,CAR_ROUTE,D_TIME,TRANS_ROUTE,TRANSFERS)
                        agent.BOARD_TIME_STAMP = pd.Timestamp(str(agent.BOARD_TIME_STAMP)).time()
                        agent.BOARD_TIME_STAMP = pd.Timestamp.combine(model.date, agent.BOARD_TIME_STAMP)
                        agent.MODE = mode
                        agent.TRAVEL_TIME = agent.TRAVEL_TIME_PT
                        agent.S_TIME = agent.S_TIME_PT
                        agent.E_TIME = agent.E_TIME_PT
                        agent.SAFETY_MARGIN = agent.SAFETY_MARGIN_PT
                        agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute

        else:
            # Find Close stations for the maximum walking radius
            close_stations = agent.get_stations()
            
            # Get walking time estimation for all stations within the radius
            walking_time = agent.calculate_time_to_station(close_stations)

            # Sort stations from closer to further
            close_stations = {close_stations[i]: walking_time[i] for i in range(len(close_stations))}
            close_stations = sorted(close_stations.items(), key=lambda x:x[1])

            if close_stations!=[]:
                close_stations = [close_stations[0]]

            for m in model.modes.keys():

                if m != "MIXED": 

                    for station,walking in close_stations:

                        agent.WALK_TIME = pd.Timedelta(minutes=walking)  
                        COMB_TIME = D_TIME + agent.WALK_TIME + model.CH_DELTA

                        # Call raptor to compute shortest multimodal path
                        S_TIME_PT,E_TIME_PT,TRANSFERS,TRANS_ROUTE = raptor(station.unique_id,model.modes[m][1],COMB_TIME,agent.max_transfer,model.change_time,
                        model.routes_by_stop_dict,model.stops_dict,model.stoptimes_dict,model.footpath_dict,
                        model.idx_by_route_stop_dict)
                    
                        agent.S_TIME_PT = S_TIME_PT - (agent.WALK_TIME+model.CH_DELTA)
                        agent.E_TIME_PT = E_TIME_PT
                        if S_TIME_PT!= None:
                            extract_KPIS(model,agent,m,CAR_ROUTE,D_TIME,TRANS_ROUTE,TRANSFERS)
                            agent.BOARD_TIME_STAMP = pd.Timestamp(str(agent.BOARD_TIME_STAMP)).time()
                            agent.BOARD_TIME_STAMP = pd.Timestamp.combine(model.date, agent.BOARD_TIME_STAMP)
                            if agent.departure - (60*agent.E_TIME_PT.time().hour + agent.E_TIME_PT.time().minute) >=45:
                                break
                else:
                    # Initialize optimal first file of transit point 
                    CAR_FIRST_MILES = []
                    BEST_TRANSITS = []

                    # Determine potential Transit Points to access via car or taxi    
                    for tr in model.transit_nodes.keys():
                        coords = (agent.lonlat,model.transit_nodes[tr]['lonlat'])
                        CAR_ROUTE_TRANS = return_car_route(model.client,coords,250,model.active_road_disruption)
                        CAR_TIME_TRANS = CAR_ROUTE_TRANS['routes'][0]['summary']['duration']/60
                        CAR_FIRST_MILES.append(CAR_TIME_TRANS)

                    # Isolate best three
                    BEST_TRANSIT = sorted(range(len(CAR_FIRST_MILES)), key=lambda k: CAR_FIRST_MILES[k])[0:3]
                    BEST_TRANSIT = [list(model.transit_nodes.keys())[x] for x in BEST_TRANSIT]
                    CAR_FIRST_MILES = sorted(CAR_FIRST_MILES)[0:3]
                    
                    # Initalize upper bounds  
                    BEST_MIXED = pd.Timestamp(year=model.date.year,month=model.date.month+1,day=model.date.day)
                    BEST_TM = np.inf

                    # Determine second leg of route via PT
                    for tr,tm in zip(BEST_TRANSIT,CAR_FIRST_MILES):
                        CAR_TIME_TRANS = pd.Timedelta(minutes=tm)
                        COMB_TIME_TRANS = D_TIME + CAR_TIME_TRANS + model.CH_DELTA
                        S_TIME_PT,E_TIME_PT,TRANSFERS,TRANS_ROUTE = raptor(model.transit_nodes[tr]['stop_id'],model.transit_nodes[tr]['mxp_node'],COMB_TIME_TRANS,1,model.change_time,
                        model.routes_by_stop_dict,model.stops_dict,model.stoptimes_dict,model.footpath_dict,
                        model.idx_by_route_stop_dict)

                        if TRANS_ROUTE!= None:
                            if BEST_MIXED >= E_TIME_PT:
                                if BEST_TM >= tm:
                                    BEST_MIXED = E_TIME_PT
                                    BEST_TM = tm
                                    agent.S_TIME_PT = S_TIME_PT - (CAR_TIME_TRANS+model.CH_DELTA)
                                    agent.E_TIME_PT = E_TIME_PT
                                    agent.WALK_TIME = CAR_TIME_TRANS # Representing ACCESS TIME to first station
                                    extract_KPIS(model,agent,m,CAR_ROUTE,D_TIME,TRANS_ROUTE,TRANSFERS)

                # Save final solution
                if agent.MULTIMODAL_EFFECT != None and agent.E_TIME != None :
                    if agent.MULTIMODAL_EFFECT <= model.modes[m][0] and agent.SAFETY_MARGIN_PT > 45:
                        agent.MODE = m
                        agent.TRAVEL_TIME = agent.TRAVEL_TIME_PT
                        agent.S_TIME = agent.S_TIME_PT
                        agent.E_TIME = agent.E_TIME_PT
                        agent.SAFETY_MARGIN = agent.SAFETY_MARGIN_PT
                        try:
                            agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute
                        except:
                            pass
                        break
                if m == "TRAIN": # Save car route
                    agent.TRAVEL_TIME = agent.TRAVEL_TIME_CAR
                    agent.S_TIME = D_TIME.floor("T")
                    agent.E_TIME = D_TIME + pd.Timedelta(minutes=agent.TRAVEL_TIME_CAR).ceil("T")
                    agent.SAFETY_MARGIN = agent.SAFETY_MARGIN_CAR
                    agent.LINE_USED = "None"
                    agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute

def reassign(agent, station, model):
    '''
    Reassign a Passenger when a Passenger is reassigned due to a disruption.

    :param agent: The agent to be reassigned.
    :param station: The transit station where the Passenger is being reassigned.
    :param model: The simulation model.
    '''
    # Set status to PRIORITY
    agent.STATUS = "PRIORITY"

    # Get the current step as a timestamp
    D_TIME = pd.Timestamp(year=model.date.year, month=model.date.month, day=model.date.day,
                        hour=(model.schedule.steps+1) // 60, minute=(model.schedule.steps+1) % 60)

    S_TIME_PT, E_TIME_PT, TRANSFERS, TRANS_ROUTE = raptor(station.unique_id, model.transit_nodes[station.name]['mxp_node'],
                                                        D_TIME, 1, model.change_time, model.routes_by_stop_dict,
                                                        model.stops_dict, model.stoptimes_dict, model.footpath_dict,
                                                        model.idx_by_route_stop_dict)

    # Update the Passenger's information
    agent.E_TIME = E_TIME_PT
    agent.LINE_USED = TRANS_ROUTE[0][-1]
    
    # Calculate the safety margin (time remaining until departure)
    agent.SAFETY_MARGIN = agent.departure - (60 * agent.E_TIME.hour + agent.E_TIME.minute)
    agent.TRANSFER_TIME+= int((agent.E_TIME-agent.S_TIME).seconds/60)-agent.TRAVEL_TIME
    agent.TRAVEL_TIME = int((agent.E_TIME-agent.S_TIME).seconds/60)
    agent.IR_RATIO = 1-agent.ACCESS_TIME/agent.TRAVEL_TIME
    agent.MULTIMODAL_EFFECT = agent.TRAVEL_TIME/(agent.TRAVEL_TIME_CAR)
    agent.TRANSFERS+=1
    agent.ARR_TIME = agent.E_TIME.hour * 60 + agent.E_TIME.minute

def initial_state(model,pass_distr):
    '''
    Initialize agents at the airport prior to simulation start

    :param agent: The agent to be reassigned.
    :param model: The simulation model.
    '''

    random_arrivals = np.random.randint(30, 91, size=len(pass_distr))
    pass_distr['ARR_TIME'] = pass_distr['activation_time'] + random_arrivals
    modes = ['CAR', 'TRAIN', 'COACH', 'TAXI']
    percentages = [model.args.modal_split_car, model.args.modal_split_train, model.args.modal_split_coach,model.args.modal_split_taxi]

    # Add a new column based on sampling from the given percentages
    pass_distr['MODE'] = np.random.choice(modes, len(pass_distr), p=percentages)
    pass_distr['E_TIME'] = pd.Timestamp(model.date) + pd.to_timedelta(pass_distr['ARR_TIME'], unit='m')
    pass_distr['TRAIN_ARR'] = pass_distr['E_TIME'].apply(lambda x: model.train_arrivals.loc[model.train_arrivals['arrival_time'] >= x, 'arrival_time'].min())
    pass_distr['COACH_ARR'] = pass_distr['E_TIME'].apply(lambda x: model.coach_arrivals.loc[model.coach_arrivals['arrival_time'] >= x, 'arrival_time'].min())
    pass_distr['DEP_TIME'] = pd.Timestamp(model.date) + pd.to_timedelta(pass_distr['departure'], unit='m')

    pass_distr['SWITCH'] = (pass_distr['MODE'] == 'TRAIN') & ((pass_distr['DEP_TIME'] - pass_distr['TRAIN_ARR']).dt.total_seconds() / 60 < 60)
    pass_distr.loc[pass_distr['SWITCH'], 'MODE'] = 'CAR'
    pass_distr['SWITCH'] = (pass_distr['MODE'] == 'COACH') & ((pass_distr['DEP_TIME'] - pass_distr['COACH_ARR']).dt.total_seconds() / 60 < 60)
    pass_distr.loc[pass_distr['SWITCH'], 'MODE'] = 'CAR'

    pass_distr.loc[pass_distr['MODE'] == 'TRAIN', 'E_TIME'] = pass_distr.loc[pass_distr['MODE'] == 'TRAIN', 'TRAIN_ARR']
    pass_distr.loc[pass_distr['MODE'] == 'COACH', 'E_TIME'] = pass_distr.loc[pass_distr['MODE'] == 'COACH', 'COACH_ARR']
    pass_distr['activation_time'] =  pass_distr['E_TIME'].dt.hour * 60 + pass_distr['E_TIME'].dt.minute
    pass_distr = pass_distr.drop(columns=['TRAIN_ARR',"COACH_ARR",'DEP_TIME',"SWITCH"])
    pass_distr['lat'] = 45.62712
    pass_distr['lon'] = 8.711128
    pass_distr['X'] = 511334.91
    pass_distr['Y'] = 5047804.80
    
    return pass_distr
