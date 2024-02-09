# Standard python libraries
import mesa
import pandas as pd
import utm
import calendar
import time
import openrouteservice
import os
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['USE_PYGEOS'] = '0'
from visualization import map_initialization, map_running, end_disruption_visual,update_visualization
import geopandas as gpd
import pygame

# Transit Routing Functions
from TransitRouting.misc_gtfs_functions import *
from TransitRouting import GTFS_wrapper,build_transfer_file

# Orchestra Toolkit
from Toolkit.demand_generation import * 
from Toolkit.network_represenentations import * 
from Toolkit.dynamic_guidance import *
from Toolkit.priority_balancing import * 
from Toolkit.queue_decision_support import * 

# Configuration
from config import get_config

class Station(mesa.Agent):
    """
    Station class represents a station in the simulation.
    """

    def __init__(self, unique_id, model, pos, name, traffic=0):
        """
        Initialize a Station object.

        :param unique_id: Unique identifier for the station.
        :param model: The mesa.Model environment.
        :param pos: Coordinates in the UTM format (X, Y) representing the station on the mesa.map.
        :param name: Name of the station.
        :param traffic: Initial occupancy in the station (optional).
        """
        super().__init__(unique_id, model)
        self.pos = pos
        self.lonlat = utm.to_latlon(pos[0], pos[1], 32, 'T')
        self.lonlat = (self.lonlat[1],self.lonlat[0])
        self.name = name
        self.traffic = traffic

        # Defines all planned stops around that station
        self.stop_schedule = model.stop_times_file[model.stop_times_file['stop_id'] == unique_id]
        self.stops = self.stop_schedule.copy()[['arrival_time', 'trip_id']]
        self.stops.sort_values(by='arrival_time', inplace=True)
        self.next_stop_time = None

        # TO FIX - Handmade solution that works for start => 270 and < 330
        if self.name == "MILANO PORTA GARIBALDI":
            self.next_stop_time = pd.Timestamp(year=model.date.year, month=model.date.month, day=model.date.day,
                                               hour=5,
                                               minute=34)

    def determine_first_stop(self, step):
        """
        Determine the first stop based on the current step.

        :param step: Current simulation step.
        """
        stops_mod = self.stops.copy(deep=True)
        stops_mod['arrival_time'] -= pd.Timedelta(minutes=step)
        stops_mod['arrival_time'] = stops_mod['arrival_time'].dt.time
        stops_mod.sort_values(by='arrival_time', inplace=True)
        self.next_stop_time = self.stops.at[stops_mod.index[0], 'arrival_time']

    def update(self, pax):
        """
        Updates the occupancy of the station at the current time step.

        :param pax: Number of passengers arriving at the station at the current time step.
        """
        self.traffic += pax

    def empty(self):
        """
        Empties the station according to the current schedule.

        This is only for Transit Stations towards MXP.
        """
        self.traffic = 0
        self.stops = self.stops[1:]

        # Ensure that Milano-bound lines are not emptying the stations
        for i in self.stops:
            if i[1] in set(model.lines) and i[0] != self.next_stop_time:
                if i[0].hour * 60 + i[0].minute > model.schedule.steps:
                    self.next_stop_time = i[0]
                    line = i[1]
                    break

class Passenger(mesa.Agent):
    '''
    Passenger class represents a passenger in the simulation.
    '''

    def __init__(self, unique_id, model, lonlat, pos, persons, activation, flight, departure, NIL, gate, passport, bags, self_check, max_transfer=3, walking_radius=500):
        """
        Initialize a Passenger object.

        :param unique_id: Unique identifier for the passenger.
        :param model: The mesa.Model environment.
        :param lonlat: Longitude and latitude of the passenger's original position.
        :param pos: Coordinates in the UTM format (X, Y) representing the passenger on the mesa.map.
        :param persons: Number of persons in that trip.
        :param activation: Time (minutes from midnight) that the trip starts.
        :param departure: Time (minutes from midnight) that the associated flight ends.
        :param NIL: Region that the trip originates from.
        :param max_transfer: Number of max transfers allowed by the agent.
        :param walking_radius: Maximum Euclidean distance that a station may be located away from origin.
        """

        # Defined initials passed by input
        super().__init__(unique_id, model)
        self.lonlat = lonlat
        self.pos = pos
        self.persons = persons
        self.activation = activation
        self.flight = flight
        self.departure = departure
        self.NIL = NIL
        self.gate = gate
        self.passport = passport
        self.bags = bags
        self.self_check = self_check
        self.max_transfer = max_transfer
        self.walking_radius = walking_radius

        # Initialize various attributes
        self.proc_time = 0
        self.MODE = None
        self.TRAVEL_TIME = None
        self.S_TIME = None
        self.E_TIME = None
        self.SAFETY_MARGIN = None
        self.LINE_USED = None
        self.TRANSIT_STATION = None
        self.TRANSIT_STATION_NAME = None
        self.TRANSFERS = None
        self.ACCESS_TIME = 0
        self.IR_RATIO = None
        self.TRANSFER_TIME = None
        self.WALK_TIME = None
        self.WAITING_TIME = None
        self.MULTIMODAL_EFFECT = None
        self.BOARD_TIME = None
        self.STATUS = "NORMAL"
        self.APPROACH = None
        self.DISTANCE_CAR = None
        self.DROP_OFF_CAR = None

    def get_stations(self):
        '''
        Returns stations that are within the passenger's walking radius.
        '''
        return [x for x in model.map.get_neighbors(self.pos, self.walking_radius) if isinstance(x, Station)]

    def calculate_time_to_station(self, stations):
        '''
        Calculates travel time to the first connection point; this is a rough approximation.
        '''
        return [int(((model.map.get_distance(self.pos, x.pos)) / (60 * 0.8))) for x in stations]


class Milano(mesa.Model):
    
    def __init__(self, args, client,break_station="RESCALDINA",break_time = 659,break_line = '1007_5'):
        """
        Initialize the Milano model.
        
        :param date (pd.Timestamp): examined date of the simulation
        :param window_len (int): length of time window
        :param change_time (int): transfer time between modes (minimum)
        """
        super().__init__()

        # Define case study imposed parameters - Variable
        self.args = args
        self.client = client

        # Simulation Parameters
        self.window_len = 30
        self.change_time = int(args.change_time)
        self.CH_DELTA = pd.Timedelta(seconds=self.change_time)

        # Disruption related parameter
        self.break_station = self.args.break_station
        self.break_time = ""
        self.break_line = ""

        # Date related parameters
        self.date = pd.Timestamp(args.date).date()
        self.date_str = self.date.strftime('X%d/X%m/%Y').replace('X0','X').replace('X','').replace('/','-')
        self.month = self.date.month
        self.month_name = calendar.month_name[self.month]
        self.start_stamp = pd.Timestamp(args.date) + pd.Timedelta(minutes=self.args.start_stamp)

        # Area related Parameters
        self.area = "milano"
        self.x_min, self.y_min, self.x_max, self.y_max = 470343.91, 5012125.44, 577043.51, 5075971.36


        # Load transit nodes data
        self.transit_nodes = pd.read_csv('data/mxp/transit_stops.csv', index_col=0).to_dict(orient='index')
       

        for x in self.transit_nodes.keys():
            self.transit_nodes[x]['lonlat'] = (self.transit_nodes[x]['stop_lon'], self.transit_nodes[x]['stop_lat'])

        # Initialize transit stations
        self.transit_stations = {k: None for k in self.transit_nodes.keys()}
        self.mxp_node_name = 'MALPENSA AEROPORTO T.1'
        self.mxp_lonlat = (8.711128, 45.62712)
        self.mxp_nodes = [4150, 4155]

        self.lines = []

        # Modes of transportation
        self.modes = {'TRAIN': (1.25, 4150),'COACH': (1.5, 4155)}  # Adjusted modes as per your comments

        # Priority and partial margin
        self.priority = []
        self.PARTIAL_MARGIN = []
        self.MISSED = 0
        self.exits = [0 for _ in range(1440)]
        self.schengen = 0
        self.non_schengen = 0
        self.bags_pax = 0
        
        # Parameters to be loaded locally
        data_folder = f"data/mxp/{self.month_name}/{self.date_str}/"
        self.departures_matrix = pd.read_csv(data_folder + "departures_matrix.csv", index_col=0)
        self.departures_plan = pd.read_csv(data_folder + "departures_plan.csv")
        self.arrivals_matrix = pd.read_csv(data_folder + "arrivals_matrix.csv", index_col=0)
        self.arrivals_plan = pd.read_csv(data_folder + "arrivals_plan.csv")
        self.pop_data = pd.read_excel("data/milano/milano_population_data.xlsx")
        self.polygons = gpd.read_file('data/milano/nils_milano.geojson')
        self.varese_pop = pd.read_excel("data/milano/varese_population_data.xlsx")
        self.arr_to_check = pd.read_excel("data/mxp/arr_to_checkin.xlsx",index_col=0)
        self.arr_to_xray= pd.read_excel("data/mxp/arr_to_xray.xlsx",index_col=0)

        # Set Processing rates
        self.waiting_time = {}
        self.waiting_time["X-RAY"]= 0
        self.queue_chars = {f'C{i}': {'mean_service_time':int(args.check_in_proc)/60, "S_SQUARED": (0-2) ** 2 / 12, 'trans': [1],
                                "trans_point": ["X-RAY"]} for i in range(1, 12)}
        self.queue_chars['CAR'] = {}
        self.queue_chars['TRAIN'] = {}

        for i in range(1,12):
            self.queue_chars[f'C{i}']['walk'] = self.arr_to_xray.loc[i]['Time (min)']
            self.waiting_time[f'C{i}']= 0

        self.queue_chars['CAR']['walk'] = self.arr_to_xray.loc['CAR']['Time (min)']
        self.queue_chars['TRAIN']['walk'] = self.arr_to_xray.loc['TRAIN']['Time (min)']
        self.queue_chars["X-RAY"] = {'mean_service_time': int(args.x_ray_proc)/60, "S_SQUARED": (1 - 4) ** 2 / 12, 'trans': [],
                            "trans_point": []}
        self.delay = 0
        self.delay_lines = {}  
        self.store_generated = pd.DataFrame()
        # Load data related to stops and routes
        self.stops_file, self.trips_file, self.stop_times_file, self.transfers_file, \
        self.stops_dict, self.stoptimes_dict, self.footpath_dict, self.routes_by_stop_dict, \
        self.idx_by_route_stop_dict, self.routesindx_by_stop_dict = read_testcase(f'./{self.area}')
    
        self.train_arrivals = self.stop_times_file[self.stop_times_file['stop_id']==4150]
        self.train_arrivals = self.train_arrivals[self.train_arrivals['stop_sequence']!=0]
        self.coach_arrivals = self.stop_times_file[self.stop_times_file['stop_id']==4155]
        self.coach_arrivals = self.coach_arrivals[self.coach_arrivals['stop_sequence']!=0]

        # Mesa Parameters
        self.pax_id = 0  # Agents Counter
        self.map = mesa.space.ContinuousSpace(self.x_max, self.y_max, False, self.x_min, self.y_min)
        self.schedule = mesa.time.RandomActivationByType(self)
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "TRIP_STARTS": lambda m: sum([a.persons for a in m.schedule.agents_by_type[Passenger].values() if a.TRAVEL_TIME != None and a.activation == m.schedule.steps]),
                "TRIP_ENDS": lambda m: sum([a.persons for a in m.schedule.agents_by_type[Passenger].values() if a.E_TIME.hour * 60 + a.E_TIME.minute == m.schedule.steps]),
                "MILANO CENTRALE": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                  a.unique_id == m.transit_stations['MILANO CENTRALE']]),
                "MILANO BOVISA FNM": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                  a.unique_id == m.transit_stations['MILANO BOVISA FNM']]),
                "MILANO PORTA GARIBALDI": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                         a.unique_id == m.transit_stations['MILANO PORTA GARIBALDI']]),
                "MILANO CADORNA": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                 a.unique_id == m.transit_stations['MILANO CADORNA']]),
                "SARONNO": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                          a.unique_id == m.transit_stations['SARONNO']]),
                "RESCALDINA": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                             a.unique_id == m.transit_stations['RESCALDINA']]),
                "CASTELLANZA": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                               a.unique_id == m.transit_stations['CASTELLANZA']]),
                "BUSTO ARSIZIO FN": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                  a.unique_id == m.transit_stations['BUSTO ARSIZIO FN']]),
                "MILANO CENTRALE BUS": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                       a.unique_id == m.transit_stations['MILANO CENTRALE BUS']]),
                "LOTTO BUS": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                            a.unique_id == m.transit_stations['LOTTO BUS']]),
                "FIERAMILANOCITY BUS": lambda m: sum([a.traffic for a in m.schedule.agents_by_type[Station].values() if
                                                      a.unique_id == m.transit_stations['FIERAMILANOCITY BUS']]),
            },
            agent_reporters={
                "FLIGHT": lambda a: self.get_KPI(a, "flight"), "NO_PERSONS": lambda a: self.get_KPI(a, "persons"),
                "REGION": lambda a: self.get_KPI(a, "NIL"), "BAGS": lambda a: self.get_KPI(a, "bags"),
                "PASSPORT CONTROL": lambda a: self.get_KPI(a, "passport"),
                "MODE": lambda a: self.get_KPI(a, "MODE"), "START_TIME": lambda a: self.get_KPI(a, "S_TIME"),
                "END_TIME": lambda a: self.get_KPI(a, "E_TIME"), "TRAVEL_TIME": lambda a: self.get_KPI(a, "TRAVEL_TIME"),
                "SAFETY_MARGIN": lambda a: self.get_KPI(a, "SAFETY_MARGIN"),
                "BOARD_TIME": lambda a: self.get_KPI(a, "BOARD_TIME"), "LINE_USED": lambda a: self.get_KPI(a, "LINE_USED"),
                "TRANSFERS": lambda a: self.get_KPI(a, "TRANSFERS"),
                "TRANSIT_STATION": lambda a: self.get_KPI(a, "TRANSIT_STATION_NAME"),
                "ACCESS_TIME": lambda a: self.get_KPI(a, "ACCESS_TIME"),
                "TRANSFER_TIME": lambda a: self.get_KPI(a, "TRANSFER_TIME"), "IR_RATIO": lambda a: self.get_KPI(a, "IR_RATIO"),
                "WAITING_TIME": lambda a: self.get_KPI(a, "WAITING_TIME"), "WALK_TIME": lambda a: self.get_KPI(a, "WALK_TIME"),
                "MULTIMODAL_EFFECT": lambda a: self.get_KPI(a, "MULTIMODAL_EFFECT"), "APPROACH": lambda a: self.get_KPI(a, "APPROACH"),
                "DISTANCE": lambda a: self.get_KPI(a, "DISTANCE_CAR"), "DROP_OFF": lambda a: self.get_KPI(a, "DROP_OFF_CAR"),
                "STATUS": lambda a: self.get_KPI(a, "STATUS"),"GATE": lambda a: self.get_KPI(a, "gate"),"DEPARTURE": lambda a: self.get_KPI(a, "departure"),
                "ACTIVATION": lambda a: self.get_KPI(a, "activation"),"PROC_TIME": lambda a: self.get_KPI(a, "proc_time")
            }
        )
 
        # Load Station agents from file
        stat_distr = pd.read_csv('data/milano/stations_all.csv', delimiter=',').values
        for idx in range(stat_distr.shape[0]):
            x, y = stat_distr[idx][4], stat_distr[idx][5]
            name = stat_distr[idx][1]
            station = Station(int(stat_distr[idx][0]), self, (x, y), name)

            # Store Transit Station nodes - MXP Express
            if name in self.transit_stations.keys():
                self.transit_stations[name] = int(stat_distr[idx][0])

            # Place Station on the Map and to the schedule
            self.map.place_agent(station, (x, y))
            self.schedule.add(station)

    def place_passenger_agent(self, pass_distr):
        '''
        Initializes Passenger agents for the current step based on generated demand for that time-window

        :param pass_distr (pd.DataFrame): Exact trip information for passengers at this time-window 
        '''
        for _, r in pass_distr.iterrows():

            # Create a Passenger agent
            passenger = Passenger(
                f'P{self.pax_id}',  # Agent ID
                self,  # Model reference
                (r[1], r[0]),  # (lon, lat)
                (r[2], r[3]),  # (x, y)
                r[4],  # no_persons
                r[5],  # activation
                r[6],  # departure time
                r[7],  # flight
                r[8],  # NIL
                r[9],  # Gate
                r[10],  # Passport
                r[11],  # Bags
                r[12]  # Self-Check
            )

            # Place agent on the map and schedule
            self.map.place_agent(passenger, (r[2], r[3]))
            self.schedule.add(passenger)
            self.pax_id += 1

    def get_KPI(self, agent, KPI):
        '''
        Get Key Performance Indicator (KPI) for a specific Passenger agent.

        :param agent (mesa.Agent): The specific Passenger Agent for which the KPI is requested.
        :param KPI (str): The name of the requested KPI; consult documentation for proper usage.

        :return: The value of the requested KPI, which may be numeric, datetime, or string.
        '''
        if type(agent) == Passenger:
            attr = getattr(agent, KPI)
            try:
                # Round numeric KPIs except for "MULTIMODAL_EFFECT" and "IR_RATIO"
                if KPI != "MULTIMODAL_EFFECT" and KPI != "IR_RATIO":
                    attr = round(attr)
            except:
                pass
            return attr

    def step(self):
        '''
        Step Function that updates simulation by the minute
        '''   
        self.schedule.steps += 1 #important for data collector to track number of steps
    
    def run_model(self, step_count, start):
        '''
        Runs the model for a specified number of steps.

        :param step_count (int): Total steps in the simulation.
        :param start (int): Flag to ignore assignment on steps before this.

        '''
        # Initialize/Load log file for pre-exisiting traffic 
        flow_update = {}
        station_update = {}
        line_update = {}
        modes_track = {'CAR':0,"TRAIN" :0, "COACH" :0,"TAXI" :0}
        terminal_report = {'check_in': 0,'x_ray':0,'servers':0,'queue_x_ray':0,'avg_proc':0}

        tot_arrs = 0
        arrs = [0 for _ in range(1440)]
        save = {}
        dis,c = end_disruption_visual(self)
        avg_proc = []
        self.track_st = self.args.min_open
        term_announce = ""
        keep_extra = ""
        for st in range(step_count):

            if st < 7*60 or st >=20*60:
                model.args.modal_split_car, model.args.modal_split_train, model.args.modal_split_coach,model.args.modal_split_taxi = 0.64,0.08,0.13,0.15
            elif st >=9*60 and st < 15*60 :
                model.args.modal_split_car, model.args.modal_split_train, model.args.modal_split_coach,model.args.modal_split_taxi = 0.63,0.17,0.13,0.07
            else:
                model.args.modal_split_car, model.args.modal_split_train, model.args.modal_split_coach,model.args.modal_split_taxi = 0.53,0.3,0.13,0.04
            

            # Disruption related Input
            self.visualization = {'dispatch' : ""}
            dis,c = end_disruption_visual(self,dis,c)           
            done = False

            # Determine if road is experiencing a disruption now
            road_show = {}           
            model.active_road_disruption = []
            if model.args.road_disruption_N != []:
                
                if model.schedule.steps in model.disruption_range_N:
                    model.active_road_disruption = model.args.road_disruption_N
                    road_show['north'] = "Delays on SS336 - North Side"

            if model.args.road_disruption_S != []:
                if model.schedule.steps in model.disruption_range_S:
                    model.active_road_disruption = model.args.road_disruption_S
                    road_show['south'] = "Delays on SS336 - South Side"

            # Initialize State prior to simulation start
            if self.schedule.steps % self.window_len == 0:

                self.cluster = 1 + self.schedule.steps // self.window_len
                self.flights = self.departures_matrix[str(self.cluster)]
                
                pass_dem = generate_passenger_demand(self.pop_data, self.departures_matrix, str(self.cluster),
                                                    self.date_str, self.varese_pop)
                pass_distr = demand_to_flight(self.date_str, self.cluster, pass_dem, self.departures_matrix,
                                            self.polygons, self.varese_pop, self.departures_plan)
                
                # Initialize State of the airport before Simulation
                if st < start and model.args.initial_state:
                    pass_distr = initial_state(self,pass_distr)                                
                    for agent, r in pass_distr.iterrows():
                        flow_update = update_flows(self,r.MODE,r.Bags,r.Gate,r.no_persons,r.ARR_TIME,flow_update)
                        modes_track[r.MODE] +=r.no_persons
                        arrs[r.ARR_TIME] += r.no_persons
                        tot_arrs += r.no_persons
                        MISSED,_,proc_time = update_safety_margins(self,r.ARR_TIME,r.departure-r.activation_time,r.Bags,r.MODE,r.Gate,r.ARR_TIME)
                        avg_proc.append(proc_time)
                        self.exits[r.departure] += r.no_persons
                        self.MISSED += MISSED
                        if r.Passport:
                            self.non_schengen +=r.no_persons
                        else:
                            self.schengen +=r.no_persons

                        if r.Bags:    
                            self.bags_pax += r.no_persons

                    # Concatenate along rows (axis=0)
                    self.store_generated = pd.concat([self.store_generated, pass_distr], axis=0)
                    # Reset index if needed
                    self.store_generated = self.store_generated.reset_index(drop=True)                   
                    if len(avg_proc) >= 1:
                        terminal_report['avg_proc'] = round(sum(avg_proc)/len(avg_proc))
                    else:
                        terminal_report['avg_proc'] = 0
                    avg_proc = []
                    

                if st >= start:
                    self.pass_distr = pass_distr
           
           # Assign Examined agents
            if st >= start:
                pass_cur = self.pass_distr[self.pass_distr['activation_time'] == st]
                self.place_passenger_agent(pass_cur)
                self.pass_shuffle = list(self.schedule.agents_by_type[Passenger].values())

                for agent in self.pass_shuffle:      
                    if self.schedule.steps == agent.activation:
                        
                        assign(agent,self)
                        arrs[agent.ARR_TIME] +=agent.persons   
                        tot_arrs += agent.persons                  

                        flow_update = update_flows(self,agent.MODE,agent.bags,agent.gate,agent.persons,agent.ARR_TIME,flow_update)
                        station_update,line_update,self = check_lines_stations(self,agent,station_update,line_update)
                        if agent.TRAVEL_TIME != None and agent.TRAVEL_TIME != "None":
                            modes_track[agent.MODE] +=agent.persons
                            agent.TRAVEL_TIME += model.delay_lines[agent.LINE_USED]
                            agent.E_TIME += pd.Timedelta(minutes=model.delay_lines[agent.LINE_USED])
                            agent.SAFETY_MARGIN -=  model.delay_lines[agent.LINE_USED]

                        MISSED,agent.SAFETY_MARGIN,agent.proc_time = update_safety_margins(self,agent.ARR_TIME,agent.SAFETY_MARGIN,agent.bags,agent.MODE,agent.gate,agent.ARR_TIME)
                        avg_proc.append(agent.proc_time)
                        if MISSED == 0 :
                            self.exits[agent.departure] += agent.persons
                        self.MISSED += MISSED
                        if agent.passport:
                            self.non_schengen +=agent.persons
                        else:
                            self.schengen +=agent.persons
                        if agent.bags:    
                            self.bags_pax += agent.persons 
            report_metrics = {"en_route" : tot_arrs-sum(arrs[0:st]),"mxp" : sum(arrs[0:st])-sum(self.exits[0:st]), "left" : sum(self.exits[0:st]), 'missed' : self.MISSED,
                              "schengen" : self.schengen,"non_schengen" : self.non_schengen, "Luggage" : self.bags_pax}
            
            # Update Queues every n minutes
            if self.schedule.steps % 10 == 0:
                flows = {k: v for (k, v) in flow_update.items() if k[0] <= self.schedule.steps}
                dataset = pd.Series(flows)
                if flows != {}:
                    f_df = pd.DataFrame.from_dict(flows, orient='index')
                    f_df = dataset.unstack()
                    f_df = f_df.fillna(1e-16)
                    self.waiting_time,servers,queue_people = get_queues(f_df, self.queue_chars,self)
                    keys = self.waiting_time.keys()
                    values = [round(x[st]) if type(x) != int else 0 for x in self.waiting_time.values()]
                    self.waiting_time= dict(zip(keys, values))
                    values = [round(x[st]) if type(x) != int else 0 for x in queue_people.values()]
                    self.queue_report = dict(zip(keys, values))
                    try:               
                        self.waiting_time['servers'] = servers[st]
                    except:
                        servers = [int(args.min_open) for x in range(st)]
                        self.waiting_time['servers'] = int(self.args.min_open)
    
                    if self.track_st != servers[st-1]:
                        term_announce = f"STAFF CHANGE - THERE ARE {servers[st-1]} X-RAY OPEN"
                        self.track_st = servers[st-1]
                    else:
                        term_announce = ""
                

                    # Filter keys starting with 'C' and get their values
                    c_values = [value for key, value in self.waiting_time.items() if key.startswith('C')]
                    terminal_report['check_in'] = max(c_values)
                    terminal_report['x_ray'] = self.waiting_time['X-RAY']
                    terminal_report['servers'] = self.waiting_time['servers']
                    terminal_report['queue_x_ray'] = round(self.queue_report['X-RAY'])
                    if st >= start:
                        if len(avg_proc) >= 1:
                            terminal_report['avg_proc'] = round(sum(avg_proc)/len(avg_proc))
                        else:
                            terminal_report['avg_proc'] = 0
                        avg_proc = []
                        
            # Update Station Situations
            for station in self.schedule.agents_by_type[Station].values():
                if self.schedule.steps == self.break_time and station.name == self.break_station:
                    
                    flow_update= break_train(self.pass_shuffle, self,station,flow_update)
                    break_station = station
                    dis = f"TRAIN BROKE DOWN IN {break_station.name}"
                    done = True

            for key in station_update.keys():
                if key[0] is not None:

                    # Empty station if an MXP bound train line is leaving 
                    station = self.schedule.agents_by_type[Station][key[0]]
                    if station.next_stop_time is None:
                        station.determine_first_stop(st)

                    if station.next_stop_time.hour * 60 + station.next_stop_time.minute == self.schedule.steps:
                        if station.name == model.break_station and self.schedule.steps == model.break_time:
                            pass
                        else:
                            station.empty()

                    # Update current Traffic for Transit Stations
                    if key[1] == self.schedule.steps:
                        station.update(station_update[key])

            # Check if a dispatch must happen
            if done:
                flow_update = check_dispatch(model,break_station,flow_update)
                done = False
            
            report_metrics["prioritized"]= sum([x.persons for x in self.priority if st <=x.departure])
           
            if report_metrics["prioritized"] > 0 :
                keep_extra = f"DISRUPTED USERS - USED EXTRA X-RAY"
            else:
                keep_extra = ""
            
            term_announcement = {'staff_change': term_announce,'keep_extra' : keep_extra}
            
            self.datacollector.collect(self)
            self.step()
            if model.args.visualization:
                update_visualization(self, terminal_report, report_metrics, dis, start, modes_track,term_announcement,road_show)
                save[st] = self.visualization
                pygame.display.flip()
                escape_pressed = map_running(map_properties, self.visualization, st)
                

                if st == step_count-1 or escape_pressed: 
                    pygame.quit()
                    print("Simulation Stopped")
                    file_path = 'my_dict.json'

                    # Save the dictionary to a file
                    with open(file_path, 'w') as file:
                        json.dump(save, file)
                    break 

            
         
if __name__ == "__main__":

    # Clarify user inputs from GUI
    args = get_config()

    # Open OpenRouteService and initiate client
    open_ORS()
    client = openrouteservice.Client(base_url='http://localhost:8080/ors')

    # Transform date to be readable from GTFS wrapper
    year, month, day = args.date.split("-")
    month,day = month.zfill(2),day.zfill(2)
    output_date = int(f"{year}{month}{day}")

    # Load PT schedule for the examined date
    if args.GTFS:
        GTFS_wrapper.main('milano',output_date,[0,1,2,3,4]) # Metro, Train, Tram ,Bus
        build_transfer_file.main('milano',270) # Max walking time 270 

    # Define simulation start time and total steps
    hours, minutes = map(int, args.start.split(':'))
    start = (hours * 60) + minutes
    steps = start + int(args.simulated_time)
    args.start_stamp = start

    # Call the MESA model
    model = Milano(args,client)

    # Insert planned train cancellations from the GUI
    # Full Cancellations
    model.cancellations = []
    flags = ["Full" if x else "None" for x in [args.xp1_freq, args.xp2_freq, args.r28_freq]]
    disruptions =  {'XP1' : (flags[0],"1009"), "XP2" : (flags[1],"1010"), "R28" : (flags[2],"1007")}
    model.stoptimes_dict = insert_disruption(model,disruptions)

    # Custom Cancelations
    lines = {'XP1_Custom' : [args.xp1_custom,"1009"], "XP2_Custom" : [args.xp2_custom,"1010"], "R28_Custom" : [args.r28_custom,"1007"]}
    
    for line in lines.items():
        disruptions = {'XP1_Custom' : ["","1009"], "XP2_Custom" : ["","1010"], "R28_Custom" : ["","1007"]}
        for st_time in line[1][0].split(";"):
            disruptions[line[0]][0] = st_time
            model.stoptimes_dict = insert_disruption(model,disruptions)
            
    model.cancellations = [x for x in model.cancellations if x!={}]
    model.cancellations = {k: v for d in model.cancellations for k, v in d.items()}
    model.base = 0
    model.track = 0

    # Insert failure if it exists 
    failures =  {"SARONNO" : 4144, "RESCALDINA" : 4146, "MILANO BOVISA FNM" : 3686,"BUSTO ARSIZIO FN" : 4148, "CASTELLANZA" : 4147, "MILANO PORTA GARIBALDI" : 3730}
    if args.break_station != 'None':
        get_affected_line(model,failures,args.break_station,st = args.break_time)

    # Insert Road Disruptions
    model.disruption_range = range(1)
    model.args.road_disruption_S = []
    model.args.road_disruption_N = []
    for y in range(2):
        if (args.speed_reduction >0.0 and y == 0) or (args.speed_reduction_S >0.0 and y == 1):
            if y == 0:
                disruption = {'name':'SS336_N','perc_road':0.75,"slow_down" : True, "slow_down_perc" : (1-float(args.speed_reduction)+0.0001)**(-1)}
            else:
                disruption = {'name':'SS336_S','perc_road':0.75,"slow_down" : True, "slow_down_perc" : (1-float(args.speed_reduction_S)+0.0001)**(-1)}

        try:
            if disruption['perc_road'] !=0:
                dis_poly,dis_plot,disruption['edges_speed'] = insert_disruption_road(client,disruption['name'],disruption['perc_road'],disruption['slow_down'],disruption['slow_down_perc'])
                disruption['avoid_polygon'] = {"coordinates": [dis_poly],"type": "Polygon"}
                if y == 0:
                    model.args.road_disruption_N = disruption
                    from datetime import datetime
                    time_object  = datetime.strptime(model.args.disruption_time_road.split(';')[0], '%H:%M')      
                    road_start = time_object .hour * 60 + time_object .minute
                    time_object  = datetime.strptime(model.args.disruption_time_road.split(';')[1], '%H:%M')
                    road_finish = time_object .hour * 60 + time_object.minute
                    model.disruption_range_N = range(road_start,road_finish)
                else:
                    model.args.road_disruption_S = disruption
                    from datetime import datetime
                    time_object  = datetime.strptime(model.args.disruption_time_road_S.split(';')[0], '%H:%M')      
                    road_start = time_object .hour * 60 + time_object .minute
                    time_object  = datetime.strptime(model.args.disruption_time_road_S.split(';')[1], '%H:%M')
                    road_finish = time_object .hour * 60 + time_object.minute
                    model.disruption_range_S = range(road_start,road_finish)                
        except:
            pass
    model.args.delay_line = 1

    #model.disruption_range_S = range(1)
    model.disruption_range_N = range(1)
    # Initialize the Map
    if model.args.visualization:
        
        map_properties = map_initialization(reso=(900,700))

    st = time.time()
    model.run_model(step_count=steps,start=start)
    end = time.time()

    results = model.datacollector.get_model_vars_dataframe()

    # Isolate Agent Results
    agent_results = model.datacollector.get_agent_vars_dataframe()
    agent_results = agent_results.reset_index(level=['Step','AgentID'])
    agent_results = agent_results[agent_results["Step"] == steps-1].drop(columns=['Step']).set_index("AgentID")

    #print(agent_results)
    agents_mod =  agent_results.dropna(subset=['NO_PERSONS'])
    agents_mod = agents_mod[["FLIGHT","GATE","DEPARTURE","BAGS","PASSPORT CONTROL","END_TIME","APPROACH", "DROP_OFF", "STATUS","REGION","NO_PERSONS", "MODE", "LINE_USED",'ACTIVATION']]
    agents_mod = get_flows(agents_mod)
    model.store_generated.columns = model.store_generated.columns.str.upper()
    agents_gen = get_flows(model.store_generated)
    agents_mod = pd.concat([agents_mod, agents_gen], axis=0)

    # Reset index if needed
    agents_mod = agents_mod.reset_index(drop=True)

    agents_mod.to_excel(f'data/passengers/{model.month_name}/{model.date_str}/agents_{start}_{steps}.xlsx')
    
    # Save information to excel 
    PT_AGENTS = pd.concat([agent_results[agent_results['MODE']=='TRAIN'],agent_results[agent_results['MODE']=='COACH']]).dropna(axis=1)
    PT_AGENTS = PT_AGENTS.drop(['APPROACH','DISTANCE','DROP_OFF'],axis=1)
    PT_AGENTS = PT_AGENTS[PT_AGENTS['ACTIVATION']<=steps]
    PT_AGENTS.to_excel(f'data/passengers/{model.month_name}/{model.date_str}/PT_{start}_{steps}.xlsx')
    CAR_AGENTS =  pd.concat([agent_results[agent_results['MODE']=='CAR'],agent_results[agent_results['MODE']=='TAXI']]).dropna(axis=1)
    CAR_AGENTS = CAR_AGENTS.drop(['ACCESS_TIME'],axis=1)
    CAR_AGENTS.to_excel(f'data/passengers/{model.month_name}/{model.date_str}/CAR_{start}_{steps}.xlsx')

    print(end-st)

    close_ORS()

