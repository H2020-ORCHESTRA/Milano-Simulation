

import os
import pygame
import json
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
from visualization import map_initialization, map_running
map_properties = map_initialization(reso=(900,700))

file_path = 'output.json'

# Load the dictionary from the file
with open(file_path, 'r') as file:
    loaded_dict = json.load(file)
frame_counter = 0
for st in loaded_dict.keys():
    
    pygame.display.flip()
    escape_pressed = map_running(map_properties, loaded_dict[st], int(st))

    # Save each frame as an image
    frame_name = f'misc/pics3/frame_{frame_counter:04d}.png'
    pygame.image.save(map_properties['scr'], frame_name)
    frame_counter += 1

    if escape_pressed or st == list(loaded_dict.keys())[-1]: 
        pygame.quit()
        print("Simulation Stopped")

        break 


