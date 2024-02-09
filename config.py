# Loading configuration of optimization

# Importing Libraries
import argparse
from gooey import Gooey, GooeyParser



@Gooey(program_name='ORCHESTRA Simulation',image_dir="data",tabbed_groups=True,default_size=(900, 900),required_cols=1,optional_cols=1)
def get_config():

    # Creating configuration file
    parser = GooeyParser(description="Milano Living Lab")

    group1 =  parser.add_argument_group('Simulation Parameters',gooey_options={'show_underline': True})

    group1.add_argument('--query-string', help='the search string',gooey_options= {'visible': False})

    child_11 = group1.add_argument_group('Mandatory', gooey_options={'show_border': True,
        'columns': 3,'margin_top' : 25})

    #         gooey_options={'show_help': False}
    child_11.add_argument(
        "--start",
        metavar="Start Time",
        help="Select custom starting time of simulation in the HH:MM format.",
        required=True,
        default = '4:00',

    )

    child_11.add_argument(
            "--date",
            metavar="Examined date",
            help="Select date to initiate the simulation from the dropdown menu.",
            choices=["2023-6-1" ,"2023-6-2" ,"2023-6-3" , "2023-6-4","2023-6-5" ,"2023-6-6" ,"2023-6-7","2023-6-8","2023-6-9",
                     "2023-6-10"],
            widget="Dropdown",
            required=True,
            default = "2023-6-1"
        )

    child_11.add_argument(
            "--simulated_time",
            metavar="Simulated Time",
            help="Select simulated time for examined instance in minutes.",
            widget='Slider', gooey_options={
                'min': 30, 
                'max': 480, 
                'increment': 30},
            default=120
        )


    group5 = parser.add_argument_group('Conditions', gooey_options={'columns':3})

    group5.add_argument('--query-string5', help='the search string',gooey_options= {'visible': False})

    child_12 = group5.add_argument_group('Initial Flags', gooey_options={'show_border': True,
        'columns': 2,'margin_top' : 25})

    child_12.add_argument(
        "--visualization",
        metavar="Enable Visual Dashboard",
        action="store_true",
        )
    
    child_12.add_argument(
        "--GTFS",
        metavar="Load GTFS Schedule for Examined Day",
        action="store_true",
        )
    child_12.add_argument(
        "--initial_state",
        metavar="Initialize airport with previous traffic",
        action="store_true",
        )

    child_12.add_argument(
        "--skip_access",
        metavar="Initialize PT Transport by skipping the first mile",
        action="store_true",
        )

    group2 = parser.add_argument_group('Demand Related', gooey_options={'columns':3})

    group2.add_argument('--query-string2', help='the search string',gooey_options= {'visible': False})

    child_21 = group2.add_argument_group('Modal Split', gooey_options={'show_border': True,
        'columns': 2,'margin_top' : 25})
    child_21.add_argument(
            "--modal_split_train",
            metavar="Train",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.2
        )

    child_21.add_argument(
            "--modal_split_car",
            metavar="Car",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.5
        )

    child_21.add_argument(
            "--modal_split_taxi",
            metavar="Taxi",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.1
        )

    child_21.add_argument(
            "--modal_split_coach",
            metavar="Coach",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.2
        )



    child_1 = group2.add_argument_group('Passenger Behavior', gooey_options={'show_border': True,
        'columns': 2,'margin_top' : 25})
    child_1.add_argument(
        "--change_time",
        metavar="Transfer Time",
        help="Time between modal change (seconds).",
        widget='Slider', gooey_options={
            'min': 30, 
            'max': 480, 
            'increment': 30},
        default=120
    )
    child_1.add_argument(
        "--walk_time",
        metavar="Walk Time",
        help="Allowed Walk time for passengers (minutes).",
        widget='Slider', gooey_options={
            'min': 0, 
            'max': 5, 
            'increment': 30},
        default=120
    )

    child_1.add_argument(
        "--threshold",
        metavar="Minimum allowed safety margin",
        help="Allowed safety margin for passengers (minutes).",
        widget='Slider', gooey_options={
            'min': 0, 
            'max': 120, 
            'increment': 1},
        default=60
    )


    group4 = parser.add_argument_group('Terminal Related', gooey_options={'columns':3})

    group4.add_argument('--query-string4', help='the search string',gooey_options= {'visible': False})
    child_41 = group4.add_argument_group('Security Characteristics', gooey_options={'show_border': True,
        'columns': 2,'margin_top' : 25})
    child_41.add_argument(
        "--min_open",
        metavar="X-RAY security stands",
        help="Available stands at Security X-RAY",
        widget='Slider', gooey_options={
            'min': 0, 
            'max': 18, 
            'increment': 1},
        default=5
    )
    child_41.add_argument(
        "--trigger",
        metavar="Reported Waiting Time Trigger",
        help="Exceeding this waiting time (minutes) suggest staffing increase.",
        widget='Slider', gooey_options={
            'min': 1, 
            'max': 30, 
            'increment': 1},
        default=7
    )

    child_41.add_argument(
        "--increase",
        metavar="Stepwise increase of staff",
        help="Provide extra X-RAY machines to cater demand ",
        widget='Slider', gooey_options={
            'min': 1, 
            'max': 5, 
            'increment': 1},
        default=3
    )

    child_41.add_argument(
        "--check_in_proc",
        metavar="Amount of hourly users processed in Check-In Areas",
        help="Provide extra X-RAY machines to cater demand ",
        widget='Slider', gooey_options={
            'min': 0, 
            'max': 180, 
            'increment': 1},
        default=60
    )

    child_41.add_argument(
        "--x_ray_proc",
        metavar="Amount of hourly users processed in Check-In Areas",
        help="Provide extra X-RAY machines to cater demand ",
        widget='Slider', gooey_options={
            'min': 0, 
            'max': 400, 
            'increment': 1},
        default=200
    )


    child_41.add_argument(
        "--step_x",
        metavar="Re-evaluate open stands frequency. ",
        help="How often should staffing changes occur.",
        widget='Slider', gooey_options={
            'min': 10, 
            'max': 240, 
            'increment': 10},
        default=30
    )



    group6 = parser.add_argument_group('Disruptions - Train Cancelations', gooey_options={'columns':1})

    group6.add_argument('--query-string6', help='the search string',gooey_options= {'visible': False})

    child_one = group6.add_argument_group('Cancellation', gooey_options={'show_border': True,'columns':2})

    child_one_cancelation = child_one.add_argument_group('Cadorna - MXP', gooey_options={'show_border': True})

    child_one_cancelation.add_argument(
        "--xp1_freq",
        metavar="Cancel XP1",
        help="Check this box to fully cancel the XP1 train line",
        action="store_true",
    )

    child_one_cancelation.add_argument(
        "--xp1_custom",
        metavar="Cancel XP1 at specific time(s) of start from Milano Cadorna",
        help="Insert time(s) in the HH:MM format\n(Followed by semicolons in case of multiple cancellations)",
        default=""
    )

    child_two_cancelation = child_one.add_argument_group('Centrale - MXP', gooey_options={'show_border': True})
    child_two_cancelation.add_argument(
        "--xp2_freq",
        metavar="Cancel XP2",
        help="Check this box to fully cancel the XP2 train line",
        action="store_true",
    )

    child_two_cancelation.add_argument(
        "--xp2_custom",
        metavar="Cancel XP2 at specific time(s) of start from Milano Centrale",
        help="Insert time(s) in the HH:MM format\n(Followed by semicolons in case of multiple cancellations)",
        default=""
    )

    child_three_cancelation = child_one.add_argument_group('Centrale - MXP (via Rescaldina)', gooey_options={'show_border': True})
    child_three_cancelation.add_argument(
        "--r28_freq",
        metavar="Cancel R28",
        help="Check this box to fully cancel the R28 train line",
        action="store_true",
    )

    child_three_cancelation.add_argument(
        "--r28_custom",
        metavar="Cancel R28 at specific time(s) of start from Milano Centrale",
        help="Insert time(s) in the HH:MM format\n(Followed by semicolons in case of multiple cancellations)",
        default=""
    )

    group7 = parser.add_argument_group('Disruptions - Train Breaks', gooey_options={'columns':1})

    group7.add_argument('--query-string7', help='the search string',gooey_options= {'visible': False})
    child_two = group7.add_argument_group('Breakdowns', gooey_options={'show_border': True})

    child_two.add_argument(
        "--break_time",
        metavar="Time that passengers were stranded at affected station",
        help="Insert time in the HH:MM format\n(Default is the earliest line of associated Starting time)",
        widget="TextField",  # Use TextField widget for text input
        default = ""
    )

    child_two.add_argument(
        "--break_station",
        metavar="Affected station",
        help="Select a station to insert a disruption",
        choices=["BUSTO ARSIZIO FN","CASTELLANZA","MILANO BOVISA FNM","MILANO PORTA GARIBALDI","RESCALDINA","SARONNO", "None"],
        widget="Dropdown",
        default="None",
    )



    group8 = parser.add_argument_group('Disruptions - Road Network', gooey_options={'columns':1})

    group8.add_argument('--query-string8', help='the search string',gooey_options= {'visible': False})
    child_three = group8.add_argument_group('Delays on SS336', gooey_options={'show_border': True})        

    child_three.add_argument(
            "--speed_reduction",
            metavar="Speed reduction on SS336_N",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.0,
            type = float
        )

    child_three.add_argument(
        "--disruption_time_road",
        metavar="Disruption time period on SS336_N",
        help="Insert time(s) in the HH:MM format\n(Followed by semicolons start and end)",
        default=""
    )
    child_three.add_argument(
            "--speed_reduction_S",
            metavar="Speed reduction on SS336_S",
            help="",
            widget='DecimalField', gooey_options={
                'min': 0.0, 
                'max': 1.0, 
                'increment': 0.01},
            default=0.0,
            type = float
        )

    child_three.add_argument(
        "--disruption_time_road_S",
        metavar="Disruption time period on SS336_S",
        help="Insert time(s) in the HH:MM format\n(Followed by semicolons start and end)",
        default=""
    )
    return parser.parse_args()