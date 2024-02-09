"""
Module contains miscellaneous functions used for reading data, printing logo etc.
"""
import os
import numpy as np



def read_testcase(NETWORK_NAME: str) -> tuple:
    """
    Reads the GTFS network and preprocessed dict. If the dicts are not present, dict_builder_functions are called to construct them.

    Args:
        NETWORK_NAME (str): GTFS path

    Returns:
        stops_file (pandas.dataframe):  stops.txt file in GTFS.
        trips_file (pandas.dataframe): trips.txt file in GTFS.
        stop_times_file (pandas.dataframe): stop_times.txt file in GTFS.
        transfers_file (pandas.dataframe): dataframe with transfers (footpath) details.
        stops_dict (dict): keys: route_id, values: list of stop id in the route_id. Format-> dict[route_id] = [stop_id]
        stoptimes_dict (dict): keys: route ID, values: list of trips in the increasing order of start time. Format-> dict[route_ID] = [trip_1, trip_2] where trip_1 = [(stop id, arrival time), (stop id, arrival time)]
        footpath_dict (dict): keys: from stop_id, values: list of tuples of form (to stop id, footpath duration). Format-> dict[stop_id]=[(stop_id, footpath_duration)]
        route_by_stop_dict_new (dict): keys: stop_id, values: list of routes passing through the stop_id. Format-> dict[stop_id] = [route_id]
        idx_by_route_stop_dict (dict): preprocessed dict. Format {(route id, stop id): stop index in route}.

    Examples:
        >>> NETWORK_NAME = './anaheim'
        >>> read_testcase('NETWORK_NAME')
    """
    import TransitRouting.dict_builder_functions as dict_builder_functions
    stops_file, trips_file, stop_times_file, transfers_file = load_all_db(NETWORK_NAME)
    if not os.path.exists(f'./TransitRouting/dict_builder/'):
        os.makedirs(f'./TransitRouting/dict_builder/')
    
    try:
        stops_dict, stoptimes_dict, footpath_dict, routes_by_stop_dict, idx_by_route_stop_dict, routesindx_by_stop_dict = load_all_dict(
            NETWORK_NAME)
    except FileNotFoundError:
        print("Building required dictionaries")
        stops_dict = dict_builder_functions.build_save_stops_dict(stop_times_file, trips_file, NETWORK_NAME)
        stoptimes_dict = dict_builder_functions.build_save_stopstimes_dict(stop_times_file, trips_file, NETWORK_NAME)
        routes_by_stop_dict = dict_builder_functions.build_save_route_by_stop(stop_times_file, NETWORK_NAME)
        footpath_dict = dict_builder_functions.build_save_footpath_dict(transfers_file, NETWORK_NAME)
        idx_by_route_stop_dict = dict_builder_functions.build_stop_idx_in_route(stop_times_file, NETWORK_NAME)
        routesindx_by_stop_dict = dict_builder_functions.build_routesindx_by_stop_dict(NETWORK_NAME)
    return stops_file, trips_file, stop_times_file, transfers_file, stops_dict, stoptimes_dict, footpath_dict, routes_by_stop_dict, idx_by_route_stop_dict, routesindx_by_stop_dict

def load_all_dict(NETWORK_NAME: str):
    """
    Args:
        NETWORK_NAME (str): network NETWORK_NAME.

    Returns:
        stops_dict (dict): preprocessed dict. Format {route_id: [ids of stops in the route]}.
        stoptimes_dict (dict): keys: route ID, values: list of trips in the increasing order of start time. Format-> dict[route_ID] = [trip_1, trip_2] where trip_1 = [(stop id, arrival time), (stop id, arrival time)]
        footpath_dict (dict): preprocessed dict. Format {from_stop_id: [(to_stop_id, footpath_time)]}.
        routes_by_stop_dict (dict): preprocessed dict. Format {stop_id: [id of routes passing through stop]}.
        idx_by_route_stop_dict (dict): preprocessed dict. Format {(route id, stop id): stop index in route}.
        routesindx_by_stop_dict (dict): Keys: stop id, value: [(route_id, stop index), (route_id, stop index)]
    """
    import pickle
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/stops_dict_pkl.pkl', 'rb') as file:
        stops_dict = pickle.load(file)
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/stoptimes_dict_pkl.pkl', 'rb') as file:
        stoptimes_dict = pickle.load(file)
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/transfers_dict_full.pkl', 'rb') as file:
        footpath_dict = pickle.load(file)
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/routes_by_stop.pkl', 'rb') as file:
        routes_by_stop_dict = pickle.load(file)
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/idx_by_route_stop.pkl', 'rb') as file:
        idx_by_route_stop_dict = pickle.load(file)
    with open(f'./TransitRouting/dict_builder/{NETWORK_NAME}/routesindx_by_stop.pkl', 'rb') as file:
        routesindx_by_stop_dict = pickle.load(file)
    return stops_dict, stoptimes_dict, footpath_dict, routes_by_stop_dict, idx_by_route_stop_dict, routesindx_by_stop_dict


def load_all_db(NETWORK_NAME: str):
    """
    Args:
        NETWORK_NAME (str): path to network NETWORK_NAME.

    Returns:
        stops_file (pandas.dataframe): dataframe with stop details.
        trips_file (pandas.dataframe): dataframe with trip details.
        stop_times_file (pandas.dataframe): dataframe with stoptimes details.
        transfers_file (pandas.dataframe): dataframe with transfers (footpath) details.
    """
    import pandas as pd
    import os
    cwd = os.getcwd()
    path = f"{cwd}\\TransitRouting\\GTFS\\{NETWORK_NAME}"
    stops_file = pd.read_csv(f'{path}/stops.txt', sep=',').sort_values(by=['stop_id']).reset_index(drop=True)
    trips_file = pd.read_csv(f'{path}/trips.txt', sep=',')
    stop_times_file = pd.read_csv(f'{path}/stop_times.txt', sep=',')
    stop_times_file.arrival_time = pd.to_datetime(stop_times_file.arrival_time)
    if "route_id" not in stop_times_file.columns:
        stop_times_file = pd.merge(stop_times_file, trips_file, on='trip_id')
    transfers_file = pd.read_csv(f'{path}/transfers.txt', sep=',')
    return stops_file, trips_file, stop_times_file, transfers_file