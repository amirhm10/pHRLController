from typing import Dict, List
from biosmb_interface.enum import ValveState

def print_status_text(valve_state: Dict[str, ValveState], 
        flows:List[float], 
        inlet_names: List[str] = None, 
        outlet_names: List[str] = None):
    
    lines = _generate_whole_system(valve_state, flows, inlet_names, outlet_names)
    for i in range(len(lines)):
        print(lines[i])


def print_valve_state(valve_state: Dict[str, ValveState]):
    lines = _generate_valve_state(valve_state)
    for i in range(len(lines)):
        print(lines[i])


def _generate_valve_state(valve_state: Dict[str, ValveState]) -> List[str]:
    to_return = []
    to_return.append("  | A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P |")
    to_return.append("  +---------------------------------------------------------------+")

    for row in range(15):
        next_line = f"{row+1}|".rjust(3)
        for col in range(16):
            key = chr(col + 65) + str(row+1)
            valve_state[key]
            if(valve_state[key]== ValveState.OPEN):
                next_line += " ● |"
            else:
                next_line += " ◌ |"
        
        to_return.append(next_line)
        if(row == 7 or row == 8 or row == 14):
            to_return.append("  +---------------------------------------------------------------+")


    return to_return

def _generate_whole_system(
        valve_state: Dict[str, ValveState], 
        flows:List[float], 
        inlet_names: List[str] = None, 
        outlet_names: List[str] = None):
    
    to_return = []

    valve_block_lines = _generate_valve_state(valve_state)
    
    if(inlet_names is not None):
        inlet_name_length = len(max(inlet_names, key = len))

    if(outlet_names is not None):
        outlet_name_length = len(max(outlet_names, key=len))

    inlet_labels = []
    max_inlet_label_length = 0
    for i in range(7):
        to_add = f"PUMP {i+1} [{flows[i]:{5.2}}] "
        if(inlet_names is not None):
            to_add += f"--{inlet_names[i]}-->".rjust(inlet_name_length+5, "-") 
        else:
            to_add += "------> "
        if(len(to_add)>max_inlet_label_length):
            max_inlet_label_length = len(to_add)
        
        inlet_labels.append(to_add)

    outlet_labels = []
    for i in range(6):
        if(outlet_names is not None):
            outlet_labels.append(f" --{outlet_names[i]}--".ljust(outlet_name_length+5, "-") + ">")
        else:
            outlet_labels.append(" ------>")

    for i in range(len(valve_block_lines)):
        if i in range(3,10):
            to_return.append(inlet_labels[i-3] + valve_block_lines[i])
        elif i in range(13, 19):
            to_return.append(' '*max_inlet_label_length + valve_block_lines[i] + outlet_labels[i-13])
        else:
            to_return.append(' '*max_inlet_label_length + valve_block_lines[i])

    return to_return


        
                

    