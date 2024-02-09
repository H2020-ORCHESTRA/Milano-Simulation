##################################################################### Demand Generation ##################################################################

import os
import pandas as pd
import numpy as np
from shapely import geometry
import random
import utm
import calendar
import math
pd.options.mode.chained_assignment = None 

def weighted_choice(percent=50):
    return random.randrange(100) < percent

def generate_passenger_demand (pop_data,passenger_data,cluster,date,varese_pop,flag="departures",save=False):

    '''
    Dividing expected passenger per cluster to regions according to population densities:

    Args:
        pop_data (xlsx file): Dataframe read that should be stored in path data/milano/milano_population_data.xlsx directory;
                                    derived from https://dati.comune.milano.it/dataset/ds25-popolazione-proiezione-popolazione-quartiere    
        passenger_data (csv file): Dataframe read that should be stored in path data/mxp/<examined month (Name)>/<examined date (%d-%m-%YYYY)>/trip_matrix.csv;
                                    derived from flights_to_demand.ipynb\
        cluster (int) : Examined time-window
        date (str) : date in the (%d-%m-%YYYY) format
        varese_pop (xlsx file): Dataframe read that should be stored in path data/milano/varese_population_data.xlsx directory;
                                    derived from wikipedia
        save (bool) : Optional parameter to save all resulting Dataframes

    Returns:
        demand (pd.Dataframe): Dataframe indexed by the NIL of the region and number of travelers associated to the NIL for that time-window.

    '''
    # Create probabilities for each region
    pop_data = pop_data[pop_data["Anno"]==2018]
    pop_data = pop_data[["Quartiere","NIL","Totale"]]
    #

    population = pop_data["Totale"].sum(axis=0)
    pop_data["Percentage"] = (0.46)*pop_data["Totale"]/population # Milano Share/(Milano + Varese Share)


    varese_pop = varese_pop[["Quartiere","NIL","Totale"]]
    varese_population = varese_pop["Totale"].sum(axis=0)
    varese_pop["Percentage"] = varese_pop["Totale"]/varese_population
    varese_pop["Percentage"] = 0.15*varese_pop["Totale"]/varese_population  # Varese Share/(Milano + Varese Share)

    direct_mxp = pd.DataFrame([["MXP",999,0,0.39]],columns=["Quartiere","NIL","Totale","Percentage"])
    pop_data = pd.concat([pop_data, varese_pop,direct_mxp], axis=0)
    pop_data["Cum_perc"] = pop_data["Percentage"].cumsum()
    pop_data = pop_data.reset_index(drop=True)

    # Assign travelers to regions based on created probabilities
    pop_data["Travellers"] = 0
    users = int(passenger_data[str(cluster)].sum())
    for _ in range(users):
        prob = np.random.rand()
        high = pop_data[pop_data["Cum_perc"]>=prob]
        row = high[high["Cum_perc"]-high["Percentage"]<=prob]
        pop_data.loc[row.index,"Travellers"]+=1

    # Examined Month
    m = int(date.split("-")[1])

    # Create a new directory because it does not exist
    path = f"data/milano/{calendar.month_name[m]}/{date}"
    isExist = os.path.exists(path)
    if not isExist:
        os.makedirs(path)

    # Save to file if desired
    if save :
        pop_data[['NIL','Travellers']].to_csv(f'{path}/demand_{flag}_{cluster}.csv',index=False)
    
    # Return demand to the simulation
    demand = pop_data[['NIL','Travellers']]
    demand.index = demand.NIL
    return demand


def generate_random_coordinates(number, polygon):

    '''
    Generates random points within a specified region:

    Args:
        number (int): Amount of points to be generated  
        polygon (shapely.geometry) : Polygon derived from the NILs GeoJSON that was downloaded from 
                                    https://dati.comune.milano.it/dataset/ds964-nil-vigenti-pgt-2030/resource/9c4e0776-56fc-4f3d-8a90-f4992a3be426 

    Returns:
        points (list of shapely.Point): List of Longitude,Latitude coordinates in the WGS84 format.

    '''

    points = []
    
    # Set bounds of the examined NIL
    minx, miny, maxx, maxy = polygon.bounds
    while len(points) < number:

        # Uniformly select from within the boundaries
        a,b = np.random.uniform(minx, maxx), np.random.uniform(miny, maxy)
        pnt = geometry.Point(a,b)
        if polygon.contains(pnt):
            rand = 1
            for i in range(rand):
                points.append((a,b))
    points = points[0:number]
    return points

def rand_coord_within_circle(point,radius):

    '''
    Generates random points within a specified region:

    Args:
        point (shapely.Point) : Point in Longitude,Latitude coordinates in the WGS84 format
        radius (int) : Radius of the designated circle by the point.

    Returns:
        point (list of shapely.Point): List of Longitude,Latitude coordinates in the WGS84 format.

    '''

    x1,y1,z_n,z_l = utm.from_latlon(point.x,point.y)
    t = random.random()
    u = random.random()
    x = x1 + radius * math.sqrt(t) * math.cos(2 * math.pi * u)
    y = y1 + radius * math.sqrt(t) * math.sin(2 * math.pi * u)

    x,y = utm.to_latlon(x, y, z_n,z_l)
    return (y,x)


def demand_to_flight(date,cluster,demand,passenger_data,polygons,varese_pop,flight_data,no_persons=list(range(1,6)),flag='departures',save=False):
    
    '''
    Generates exact trip characteristics per cluster based on the generate_demand provided information:

    Args:
        date (str) : date in the (%d-%m-%YYYY) format
        cluster (int) : Examined time-window
        demand (csv file): Dataframe that is direct output of the generate_demand function.;
                            File should be located in  data/milano/<examined month (Name)>/<examined date (%d-%m-%YYYY)>/demand_<examined cluster>.csv 
        passenger_data (csv file): Dataframe read that should be stored in path data/mxp/<examined month (Name)>/<examined date (%d-%m-%YYYY)>/trip_matrix.csv;
                                    derived from flights_to_demand.ipynb\
        polygon (GeoJSON) : Set of polygons describing the spatial characteristics of the NILS; derived from the link below :
                                    https://dati.comune.milano.it/dataset/ds964-nil-vigenti-pgt-2030/resource/9c4e0776-56fc-4f3d-8a90-f4992a3be426 
        flight_data (csv file): Dataframe read that should be stored in path data/milano/departure_plan.csv directory;
                                derived from flights_to_demand.ipynb
        varese_pop (xlsx file): Dataframe read that should be stored in path data/milano/varese_population_data.xlsx directory;
                                    derived from wikipedia
        no_persons (list) : The possible group size of all trips
        save (bool) : Optional parameter to save all resulting Dataframe

    Returns:
        user_df (pd.Dataframe): Dataframe containing exact information per initiated trip for that time-window.

    '''

    # We isolate the flights occurring within this cluster
    flights = passenger_data[str(cluster)]

    users = []
    for idx,f in flights.items():
        gate = flight_data[flight_data['Flight Code']==idx]['Gate'].values[0]
        passport = flight_data[flight_data['Flight Code']==idx]['Passport'].values[0]
        f_type = flight_data[flight_data['Flight Code']==idx]['TYPE'].values[0]

        # We start sampling for users per flight
        choice = []
        for _ in range(int(f)):

            # Weights are updated each choice to make sure that a region provides exactly the demand its has
            weight_values = demand['Travellers'].tolist()/demand['Travellers'].sum()
            weights = {NIL :  w for NIL,w in zip(demand.index.tolist(),weight_values)}
            c = np.random.choice(list(weights.keys()), p = list(weights.values()))

            # Remove travelers from that demand and append region of choice
            demand.at[c,"Travellers"]-=1
            choice.append(c)

        # Sort choice list to identify potential groups of passengers
        choice.sort()
        
        # Start sampling different group sizes
        p_list = []
        set_nils = list(set(choice)) # Reduce choice to single NIL observations
        for c in set_nils:
            count = choice.count(c) # Count observations

            # Sample number of persons as long as they are less than the current counts
            while True:
                sample = random.choice(no_persons)
                if sample <= count:
                    p_list.append(sample)
                    count-=sample

                if count == 0:
                    break
        
        # Complete df by sampling random point and adding X,Y
        counter = 0
        for u in p_list:

            if choice[counter] <= 100:
                poly = polygons[polygons["ID_NIL"]==choice[counter]]['geometry'].values[0]
                point = generate_random_coordinates(1,poly)
                lon,lat = point[0]
            elif choice[counter] <= 200 :
                central_point = geometry.Point(varese_pop[varese_pop["NIL"]==choice[counter]].values[0][-2:])
                point = [rand_coord_within_circle(central_point,radius = 3000)]
                lon,lat = point[0]
            else:
                lon,lat = 8.711128,45.62712
            
            X,Y,A,B = utm.from_latlon(lat,lon)
            if passport == 1:
                bags = weighted_choice(0.8) # 55 percent checks bags
            else:
                if f_type == "LEG":
                    bags = weighted_choice(0.75) # 55 percent checks bags
                else:
                    bags = weighted_choice(0.33) # 55 percent checks bags

            if flag == 'departures':
                dep_time = int(idx.split("|")[2])                
                self_service =  weighted_choice(15)
                users.append([lat,lon,X,Y,u,random.randrange((cluster-1)*30,cluster*30),idx,dep_time,choice[counter],gate,passport,bags,self_service])
            else:
                arr_time = int(idx.split("|")[2])     
                car =   weighted_choice(55)
                users.append([lat,lon,X,Y,u,arr_time,idx,arr_time,choice[counter],gate,passport,bags,car])
                
            counter+=u

    # Examined Month
    m = int(date.split("-")[1])

    # Create a new directory because it does not exist
    path = f"data/passengers/{calendar.month_name[m]}/{date}"
    isExist = os.path.exists(path)
    if not isExist:
        os.makedirs(path)

    
    if flag == 'departures':
        user_df = pd.DataFrame(users,columns = ["lat","lon",'X','Y','no_persons','activation_time','flight','departure','NIL_ID','Gate','Passport','Bags','Self-Check'])
        if save:
            user_df.to_csv(f'{path}/pax_departures_{cluster}.csv',index=False)
    else:
        user_df = pd.DataFrame(users,columns = ["lat","lon",'X','Y','no_persons','activation_time','flight','arrival','NIL_ID','Gate','Passport','Bags','Car'])
        if save:
            user_df.to_csv(f'{path}/pax_arrivals_{cluster}.csv',index=False)
    return user_df
