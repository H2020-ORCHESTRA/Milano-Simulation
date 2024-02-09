# Milano Simulation Living Lab

## Necessary Steps

1. **Install Necessary Libraries**: You can install the necessary libraries by using the provided environment.yml file. Run the following command to create a conda environment:

    ```bash
    conda env create -f environment.yml
    ```

2. **Load Your Own GTFS File or Use Provided Data**: You have the option to load your own GTFS (General Transit Feed Specification) file or use the one provided in the TransitRouting folder. To create your own GTFS file, you can utilize the routines in Toolkit/various_routines/GTFS_integration.

3. **Install Docker and Load a PBF File**: Docker is required for running this simulation. You can install Docker and load a PBF (Protocol Buffer Format) file from BBBike. Follow the instructions provided within the OSR (OpenStreetMap Routing) folder (DOCKER_HELP).

## Usage

After completing the necessary steps mentioned above, you can start using the Milano Simulation Living Lab. Once the environment is set up and data is loaded, you can run the simulation using the integrated GUI.


