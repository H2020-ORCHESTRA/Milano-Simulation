"""
Builds the transfer.txt file.
"""
import pickle
from time import time

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from haversine import haversine_vector, Unit
from tqdm import tqdm

ox.settings.use_cache = False
ox.settings.log_console = False


def extract_graph(NETWORK_NAME: str) -> tuple:
    """
    Extracts the required OSM..

    Args:
        NETWORK_NAME (str): Network name

    Returns:
        networkx graph, list of tuple [(stop id, nearest OSM node)]
    """
    try:
        G = pickle.load(open(f"TransitRouting/GTFS/{NETWORK_NAME}/gtfs_o/{NETWORK_NAME}_G.pickle", 'rb'))
        # G = nx.read_gpickle(f"./GTFS/{NETWORK_NAME}/gtfs_o/{NETWORK_NAME}_G.pickle")
        print("Graph imported from disk")
    except (FileNotFoundError, ValueError, AttributeError) as error:
        print(f"Graph import failed {error}. Extracting OSM graph for {NETWORK_NAME}")
        G = ox.graph_from_place(f"{NETWORK_NAME}", network_type='drive')
        # TODO: Change this to bound box + 1 km
        print(f"Number of Edges: {len(G.edges())}")
        print(f"Number of Nodes: {len(G.nodes())}")
        print(f"Saving {NETWORK_NAME}")
        pickle.dump(G, open(f"TransitRouting/GTFS/{NETWORK_NAME}/gtfs_o/{NETWORK_NAME}_G.pickle", 'wb'))
        # nx.write_gpickle(G, f"./GTFS/{NETWORK_NAME}/gtfs_o/{NETWORK_NAME}_G.pickle")
    stops_db = pd.read_csv(f'TransitRouting/GTFS/{NETWORK_NAME}/stops.txt')
    stops_db = stops_db.sort_values(by='stop_id').reset_index(drop=True)
    stops_list = list(stops_db.stop_id)
    try:
        osm_nodes = ox.nearest_nodes(G, stops_db.stop_lon.to_list(), stops_db.stop_lat.to_list())
    except:
        print("Warning: OSMnx.nearest_nodes failed. Switching to Brute force for finding nearest OSM node...")
        print("Fix the above import for faster results")
        node_names, node_coordinates = [], []
        for node in G.nodes(data=True):
            node_coordinates.append((node[1]["y"], node[1]["x"]))
            node_names.append(node[0])
        dist_list = []
        for _, stop in tqdm(stops_db.iterrows()):
            dist_list.append(haversine_vector(node_coordinates, len(node_coordinates) * [(stop.stop_lat, stop.stop_lon)], unit=Unit.METERS))
        osm_nodes = [node_names[np.argmin(item)] for item in dist_list]
        print(f"Unique STOPS: {len(stops_db)}")
        print(f"Unique OSM nodes identified: {len(set(osm_nodes))}")
    stops_list = list(zip(stops_list, osm_nodes))
    return G, stops_list


def find_transfer_len(source_info: tuple, G,WALKING_LIMIT,stops_list) -> list:
    """
    Runs shortest path algorithm from source stop with cutoff limit of WALKING_LIMIT * 2
    Args:
        source_info (tuple): Format (stop id, nearest OSM node)

    Returns:
        list of
    """
    out = nx.single_source_dijkstra_path_length(G, source_info[1], cutoff=WALKING_LIMIT * 2, weight='length')
    reachable_osmnodes = set(out.keys())
    temp_list = [(source_info[0], stopid, round(out[osm_nodet], 1)) for (stopid, osm_nodet) in stops_list if osm_nodet in reachable_osmnodes]
    return temp_list


def transitive_closure(input_list) -> list:
    graph_object, connected_component = input_list
    new_edges = []
    for source in connected_component:
        for desti in connected_component:
            if source != desti and (source, desti) not in graph_object.edges():
                new_edges.append((source, desti, nx.dijkstra_path_length(graph_object, source, desti, weight="length")))
    return new_edges


def post_process(G_new, NETWORK_NAME: str, ini_len: int,start_time) -> None:
    """
    Post process the transfer file. Following functionality are included:
        1. Checks if the transfers graph is transitively closed.

    Args:
        transfer_file: GTFS transfers.txt file
        WALKING_LIMIT (int): Maximum walking limit
        NETWORK_NAME (str): Network name

    Returns:
        None
    """
    footpath = list(G_new.edges(data=True))
    reve_edges = [(x[1], x[0], x[-1]) for x in G_new.edges(data=True)]
    footpath.extend(reve_edges)
    transfer_file = pd.DataFrame(footpath)
    transfer_file[2] = transfer_file[2].apply(lambda x: list(x.values())[0])
    transfer_file.rename(columns={0: "from_stop_id", 1: "to_stop_id", 2: "min_transfer_time"}, inplace=True)
    transfer_file.sort_values(by=['min_transfer_time', 'from_stop_id', 'to_stop_id']).reset_index(drop=True)
    transfer_file.to_csv(f"TransitRouting/GTFS/{NETWORK_NAME}/transfers.csv", index=False)
    transfer_file.to_csv(f"TransitRouting/GTFS/{NETWORK_NAME}/transfers.txt", index=False)
    print(f"Before Transitive closure: {ini_len}")
    print(f"After  Transitive closure (final file): {len(transfer_file)}")
    print(f"Total transfers: {len(transfer_file)}")
    print(f"Longest transfer: {transfer_file.iloc[-1].min_transfer_time} seconds")
    print(f"Time required: {round((time() - start_time) / 60, 1)} minutes")
    return None


def initialize(NETWORK_NAME) -> tuple:
    """
    Initialize variables for building transfers file.

    Returns:
        G: Network graph of NETWORK NAME
        stops_list (list):
        WALKING_LIMIT (int): Maximum allowed walking time
        start_time: timestamp object
    Warnings:
        Building Transfers file requires OSMnX module.
    """

    start_time = time()

    G, stops_list = extract_graph(NETWORK_NAME)
    # stops_db = stops_db.sort_values(by='stop_id').reset_index(drop=True).reset_index().rename(columns={"index": 'new_stop_id'})
    return G, stops_list, start_time

def main(NETWORK_NAME,WALKING_LIMIT) -> None:
    """
    Main function

    Returns:
        None
    """

    G, stops_list, start_time = initialize(NETWORK_NAME)
    result = [find_transfer_len(source_info,G,WALKING_LIMIT,stops_list) for source_info in tqdm(stops_list)]
    stops_db, osm_nodes, G = 0, 0, 0
    result = [item2 for item in result for item2 in item]
    transfer_file = pd.DataFrame(result, columns=['from_stop_id', 'to_stop_id', 'min_transfer_time'])

    # Post-processing section
    transfer_file = transfer_file[transfer_file.from_stop_id != transfer_file.to_stop_id].drop_duplicates(subset=['from_stop_id', 'to_stop_id'])
    transfer_file = transfer_file[(transfer_file.min_transfer_time < WALKING_LIMIT) & (transfer_file.min_transfer_time > 0)].reset_index(drop=True)
    transfer_file.to_csv(f'TransitRouting/GTFS/{NETWORK_NAME}/gtfs_o/transfers.csv', index=False)
    transfer_file.to_csv(f'TransitRouting/GTFS/{NETWORK_NAME}/gtfs_o/transfers.txt', index=False)
    ini_len = len(transfer_file)
    G_new = nx.Graph()  # Ensure transitive closure of footpath graph
    edges = list(zip(transfer_file.from_stop_id, transfer_file.to_stop_id, transfer_file.min_transfer_time))
    G_new.add_weighted_edges_from(edges)
    connected_compnent_list = [(G_new, c) for c in nx.connected_components(G_new)]
    print(f"Total connected components identified: {len(connected_compnent_list)}")
    print("Ensuring Transitive closure in serial...")
    new_edge_list = [transitive_closure(input_list) for input_list in tqdm(connected_compnent_list)]
    new_edge_list = [y for x in new_edge_list for y in x]
    G_new.add_weighted_edges_from(new_edge_list)
    post_process(G_new, NETWORK_NAME, ini_len,start_time)

if __name__ == "__main__":
    main()
