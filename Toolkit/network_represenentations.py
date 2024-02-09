##################################################################### Network Representations for Use-Cases ##################################################################

import subprocess
import requests
from shapely.geometry import LineString,MultiLineString
from shapely.ops import unary_union,linemerge
import json
import geopandas as gpd
import os
import pandas as pd
from pyproj import Geod
import folium
from time import sleep
import webbrowser
import random
import numpy as np

def weighted_choice(percent=50):
    return random.randrange(100) < percent

def open_ORS():
    '''
    Process to turn on the OpenRouteService API
    '''
    print("Started loading ORS")
    subprocess.Popen('wsl ~ docker compose -f ~/milano/docker-compose.yml up',stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT, shell=True)

    # Making a GET request to ensure that ORS is up
    while True:
        try:
            r = requests.get('http://localhost:8080/ors')
            break
        except:
            pass

    print("ORS is up")

def close_ORS():
    '''
    Process to turn off the OpenRouteService API
    '''
    subprocess.Popen('wsl ~ docker compose -f ~/milano/docker-compose.yml down',stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT, shell=True)
    print("ORS is closed")

def get_road_geometry(client,road_name,start,finish,save=True):
    '''
    Process to get the polyline for an examined route. 

    Args:
        client (openrouteservice.client) : The loaded local instance of the ORS router
        road_name (str) : Examined road name as listed in the CSV on the data/disruptions/roads.csv file
        start (list): Starting position for the route in the (long,lat) format
        finish (list) : Finishing position for the route in the (long,lat) format

    Returns:
        polyline (shapely.LineString) : Polyline form in the examined route
    '''

    # Call Router
    request_params = {'coordinates': [start,finish],
                    'format_out': 'geojson',
                    'profile': 'driving-hgv',
                    'preference': 'recommended',
                    'attributes' : ['avgspeed'],
                    'instructions': True}
    
    route_directions = client.directions(**request_params)
    loc = route_directions['features'][0]['geometry']['coordinates']

    # Reverse x,y because of ORS
    loc = [(x[1],x[0]) for x in loc]
    polyline = LineString(loc)

    # Convert the geometry to a GeoJSON-like dictionary
    geometry_dict = polyline.__geo_interface__

    # Save the dictionary to a GeoJSON file
    if save:
        output_file = f"data/disruptions/{road_name}.geojson"
        with open(output_file, "w") as f:
            json.dump(geometry_dict, f)

        output_file = f"data/disruptions/{road_name}_speed.json"
        speed = route_directions['features'][0]['properties']['segments'][0]['steps']
        with open(output_file, "w") as f:
            json.dump(speed, f)        
    return polyline,speed

def get_disruption_from_file(df,road_name):
    '''
    Process to read disruption from file. 

    Args:
        df (pd.DataFrame) : Dataframe stored in the data/disruptions/roads.csv file
        road_name (str) : Examined road name as listed in the CSV on the data/disruptions/roads.csv file

    Returns:
        start : List of coordinates in the long,lat format (starting position)
        finish : List of coordinates in the long,lat format (starting position)
    '''
    ex_road = df[df['name'] == road_name]
    start,finish = ex_road.iloc[0][1],ex_road.iloc[0][2]
    start,finish = list(start.split(",")),list(finish.split(","))
    start,finish = [float(x) for x in start],[float(x) for x in finish]

    return start,finish

def segments(curve):
    '''
    Splits LineString to multiple linestrings

    Args:
        curve (shapely.LineString) : Polyline of a route

    Returns:
        List of linestrings
    '''
    return list(map(LineString, zip(curve.coords[:-1], curve.coords[1:])))


def plot_map(heroya_point,disruption,lines=[]):

    '''
    Produces route visualizations. 

    Args:
        heroya_point (list) : Coordinates in the long,lat format
        disruption (list) : List of coordinates forming the polygon under disruption
        lines ([]) : List of routes to be visualized

    Returns:
    '''
    map = folium.Map(location=heroya_point,zoom_start=10)

    if disruption !=[]:
        folium.PolyLine(disruption,color='red',weight=10,opacity=0.8).add_to(map)

    for line in lines:
        folium.PolyLine(line,color='yellow',weight=5,opacity=0.8).add_to(map)

    map.save("map.html")
    webbrowser.get('windows-default').open("map.html")
    sleep(10)
    os.remove("map.html") 

def insert_disruption(model, canceled):
    '''
    Insert a disruption in the transit model based on canceled routes and a time window.

    :param model: The transit model to be modified.
    :param canceled: A dictionary mapping route IDs to cancellation status (True or False).
    :param time: A time window represented as a list [start_time, end_time].
    
    :return: The modified transit model.
    '''
    trips = pd.read_csv("TransitRouting/GTFS/milano/gtfs_o/trips.txt", low_memory=False)
    canc = {}
    for key, val in canceled.items():
       
        if val[0] == 'None' or val[0] == "":
            continue

        times = get_durations(key,val[0],model.start_stamp,model.args.simulated_time,path='TransitRouting/GTFS/milano/stop_times.txt')
        for dt in times:
            hour = np.datetime64(dt[0], 'h').astype(int) % 24
            minute = np.datetime64(dt[0], 'm').astype(int) % 60

            # Calculate minutes from midnight
            minutes_from_midnight = hour * 60 + minute
            time_string = np.datetime_as_string(dt[0], unit='s')[-8:]
            canc[minutes_from_midnight] = f"{key} starting on {time_string} - CANCELLED"
            
        routes = trips[trips['route_id'] == key]
        routes = routes['service_id'].values.tolist()

        affected_route = model.stoptimes_dict[int(val[1])]
        b = model.stoptimes_dict.copy()
        mod_route = []
        for route in affected_route:
            fl = False
            for stop in route:       
                for time in times:
                    if stop[1] >= time[0] and stop[1] <= time[1]:
                        fl = True
                        break
                    else:
                        fl = False
            if fl == False:
                mod_route.append(route)

            # Editing the GTFS
            model.stoptimes_dict[int(val[1])] = mod_route
    model.cancellations.append(canc)
    return model.stoptimes_dict

def isolate_route(id, TRANS_ROUTE, S_TIME, ACCESS_TIME, CH_DELTA):
    '''
    Isolate and format a route segment for a Passenger.

    :param id: Passenger ID.
    :param TRANS_ROUTE: Transit route information.
    :param S_TIME: Start time.
    :param ACCESS_TIME: Access time.
    :param CH_DELTA: Change time delta.
    
    :return: A list of route information for the Passenger.
    '''
    info_route = []

    for idx, leg in enumerate(TRANS_ROUTE):
        if idx == 0:
            if leg[0] == "walking":
                info_route.append([id, int(leg[2]), S_TIME.floor("T"), TRANS_ROUTE[idx + 1][0] - CH_DELTA, 'walking'])
            else:
                info_route.append([id, int(leg[1]), (leg[0] - ACCESS_TIME - CH_DELTA).floor("T"), leg[0], leg[-1]])
                info_route.append([int(leg[1]), int(leg[2]), leg[0], leg[3], leg[-1]])
        else:
            # Omit small walking paths from routes
            if leg[0] == "walking":
                if leg[3] <= pd.Timedelta(minutes=0.5):
                    continue
                else:
                    info_route.append([int(leg[1]), int(leg[2]), (leg[4] - leg[3]), leg[4], 'walking'])
            else:
                info_route.append([int(leg[1]), int(leg[2]), leg[0], leg[3], leg[-1]])
    
    return info_route

def split_and_keep_first(text):
    parts = text.split("_")
    return parts[0] if len(parts) > 0 else ''

def get_durations(line,flag,time,duration,path='TransitRouting/GTFS/milano/stop_times.txt'):
    
    # Data regarding lines from GTFS
    info = {"XP1" : "1009", "XP2" : "1010", "R28" : "1007",
            "XP1_Custom" : "1009", "XP2_Custom" : "1010", "R28_Custom" : "1007"}
    durs = {"XP1_Custom" : 38, "XP2_Custom" : 52, "R28_Custom" : 52}
    data = pd.read_csv(path)

    # Keep data based on starting point
    data['line'] = data['trip_id'].apply(split_and_keep_first)
    data['arrival_time'] = pd.to_datetime(data['arrival_time'])
    data = data[data["line"] == info[line]]
    data = data[data["arrival_time"] >= pd.Timestamp(time)]
    start = data[data["stop_sequence"] == 0].sort_values(by=["arrival_time"])
    
    # Keep data based on ending point 
    start = start[start["arrival_time"]<=time+pd.Timedelta(minutes=int(duration))].reset_index(drop=True)
    end_flag = max(data["stop_sequence"])
    end = data[data["stop_sequence"] == end_flag].sort_values(by=["arrival_time"])
    end = end.merge(start[['trip_id']], on='trip_id', how='inner').reset_index(drop=True)
    durations = []
    if flag == "Earliest":
        durations = [[start[start.index == 0]["arrival_time"].values[0],end[end.index == 0]["arrival_time"].values[0]]]
    elif flag == "Full":
        for idx, _ in start.iterrows():
            durations.append([start.loc[idx,"arrival_time"].to_numpy(),end.loc[idx,"arrival_time"].to_numpy()])
    else:
        cust_time = str(time).split(" ")[0]+" " + f"{flag}"
        durations.append([np.datetime64(cust_time),np.datetime64(cust_time)+np.timedelta64(durs[line], 'm')])
    return durations



def filter_tuples(tuples_list, search_value):
    '''
    Function to filter and extract the matching tuple
    '''
    for item in tuples_list:
        if item[0] == search_value:
            return [item]
    return []

def get_affected_line(model,failures,station,st=""):

    if st == "":
        dis_time = model.start_stamp
    else:
        cust_time = str(model.start_stamp).split(" ")[0]+" " + f"{st}"
        dis_time = pd.Timestamp(cust_time)
    keys_to_search = {1009, 1010, 1007}

    # Initialize a list to store occurrences
    occurrences = []

    # Iterate through the dictionary and nested lists with tuples
    for label, outer_list in model.stoptimes_dict.items():
        # Check if the label is in the set of keys to search
        if label in keys_to_search:
            for inner_list in outer_list:
                for item_tuple in inner_list:
                    if failures[station] in item_tuple:
                        occurrences.append({'Label': label, 'Value': inner_list})

    df = pd.DataFrame(occurrences)

    # Apply the filter function to extract the matching tuple
    df['Timestamp'] = df['Value'].apply(lambda x: filter_tuples(x, failures[station]))
    df['Timestamp'] = df['Timestamp'].apply(lambda x: x[0][1])

    df = df.drop(columns=['Value'])

    # Calculate the time difference between the input timestamp and each value in the 'Timestamp' column
    time_diff = (df['Timestamp'] - dis_time).dt.total_seconds()

    # Filter to keep only rows where the timestamp is after the input timestamp
    filtered_df = df[df['Timestamp'] >= dis_time]

    # Find the index of the row with the minimum positive time difference
    closest_index = time_diff[time_diff >= 0].idxmin()

    # Get the closest value
    closest_value = df.loc[closest_index, 'Timestamp']
    time_value = closest_value
    closest_line = df.loc[closest_index, 'Label']
    df = df[df['Label'] == closest_line].reset_index(drop=True)
    closest_value = df[df["Timestamp"] ==closest_value]
    index = closest_value.index[0]
    closest_value = closest_value.values[0]
    model.break_line = f"{closest_line}_{index}"
    model.break_time = time_value.hour * 60 + time_value.minute


def get_road_geometry(client,road_name,start,finish,save=True):
    '''
    Process to get the polyline for an examined route. 

    Args:
        client (openrouteservice.client) : The loaded local instance of the ORS router
        road_name (str) : Examined road name as listed in the CSV on the data/disruptions/roads.csv file
        start (list): Starting position for the route in the (long,lat) format
        finish (list) : Finishing position for the route in the (long,lat) format

    Returns:
        polyline (shapely.LineString) : Polyline form in the examined route
    '''

    # Call Router
    request_params = {'coordinates': [start,finish],
                    'format_out': 'geojson',
                    'profile': 'driving-car',
                    'preference': 'recommended',
                    'attributes' : ['avgspeed'],
                    'instructions': True}
    
    route_directions = client.directions(**request_params)
    loc = route_directions['features'][0]['geometry']['coordinates']

    # Reverse x,y because of ORS
    loc = [(x[1],x[0]) for x in loc]
    polyline = LineString(loc)

    # Convert the geometry to a GeoJSON-like dictionary
    geometry_dict = polyline.__geo_interface__

    # Save the dictionary to a GeoJSON file
    if save:
        output_file = f"data/disruptions/{road_name}.geojson"
        with open(output_file, "w") as f:
            json.dump(geometry_dict, f)

        output_file = f"data/disruptions/{road_name}_speed.json"
        speed = route_directions['features'][0]['properties']['segments'][0]['steps']
        with open(output_file, "w") as f:
            json.dump(speed, f)        
    return polyline,speed

def get_disruption_from_file(df,road_name):
    '''
    Process to read disruption from file. 

    Args:
        df (pd.DataFrame) : Dataframe stored in the data/disruptions/roads.csv file
        road_name (str) : Examined road name as listed in the CSV on the data/disruptions/roads.csv file

    Returns:
        start : List of coordinates in the long,lat format (starting position)
        finish : List of coordinates in the long,lat format (starting position)
    '''
    ex_road = df[df['name'] == road_name]
    start,finish = ex_road.iloc[0][1],ex_road.iloc[0][2]
    start,finish = list(start.split(",")),list(finish.split(","))
    start,finish = [float(x) for x in start],[float(x) for x in finish]

    return start,finish

def segments(curve):
    '''
    Splits LineString to multiple linestrings

    Args:
        curve (shapely.LineString) : Polyline of a route

    Returns:
        List of linestrings
    '''
    return list(map(LineString, zip(curve.coords[:-1], curve.coords[1:])))


def insert_disruption_road(client,road_name,perc = 1,slow_down = False,slow_perc = 2):
    '''
    Process to get the polyline for an examined route. 

    Args:
        client (openrouteservice.client) : The loaded local instance of the ORS router
        road_name (str) : Examined road name as listed in the CSV on the data/disruptions/roads.csv file
        perc (float) : Percentage of the road that is affected

    Returns:
        polygon_avoid : List of coordinates forming a polygon in the long,lat format
        polygon_plot : List of coordinates forming a polygon in the lat,long format
    '''

    if os.path.exists(f"data/disruptions/{road_name}.geojson"):
        polyline = gpd.read_file(f"data/disruptions/{road_name}.geojson")
        polyline = polyline.iloc[0][0]
        speed = json.load(open(f'data/disruptions/{road_name}_speed.json'))
        print("Loaded disruption from GeoJSON")
    else:
        roads = pd.read_csv("data/disruptions/roads.csv")
        ex_road = roads[roads['name'] == road_name]
        if ex_road.empty:
            print('No such road on file - No Disruption applied')
            return None
        else:
            start,finish = get_disruption_from_file(roads,road_name)        
            polyline,speed = get_road_geometry(client,road_name,start,finish,save=True)
    
    if polyline != None:
        
        # Reduce from start up to examined percentage
        seg = segments(polyline)
        seg = MultiLineString(seg[0:int(perc*len(seg))])
        reduced_polyline = linemerge(seg)

        # Create a buffer around the polyline
        buffer_distance = 1e-5 # Adjust this value to control the buffer size
        buffered_polyline = reduced_polyline.buffer(buffer_distance)

        # If you want to handle multiple buffers as a single geometry (e.g., for overlapping buffers)
        buffered_union = unary_union(buffered_polyline)
        xx, yy = buffered_union.exterior.coords.xy      
        polygon_avoid = [[y,x] for x,y in zip(xx,yy)]
        polygon_plot = [[[x,y] for x,y in zip(xx,yy)]]

        # Print Geodesic area covered 
        geod = Geod(ellps="WGS84")
        area = abs(geod.geometry_area_perimeter(buffered_union)[0])
        print('# Geodesic area: {:.3f} m^2'.format(area))
        
        if slow_down == False:
            return polygon_avoid,polygon_plot,{}
        else:
            edge_speed_keys = [x['name'] for x in speed]
            edge_speed_values = [slow_perc*perc*x['duration']+(1-perc)*x['duration'] for x in speed]
            edge_speed = {index: element for index, element in zip(edge_speed_keys,edge_speed_values)}
            return polygon_avoid,polygon_plot,edge_speed    

def plot_map(heroya_point,disruption,lines=[]):

    '''
    Produces route visualizations. 

    Args:
        heroya_point (list) : Coordinates in the long,lat format
        disruption (list) : List of coordinates forming the polygon under disruption
        lines ([]) : List of routes to be visualized

    Returns:
    '''
    map = folium.Map(location=heroya_point,zoom_start=10)

    if disruption !=[]:
        folium.PolyLine(disruption,color='red',weight=10,opacity=0.8).add_to(map)

    for line in lines:
        folium.PolyLine(line,color='yellow',weight=5,opacity=0.8).add_to(map)

    map.save("map.html")
    webbrowser.get('windows-default').open("map.html")
    sleep(10)
    os.remove("map.html") 


