from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager
import time

if __name__== "__main__":
    inlet_names = [
        "EtOH",
        "NaCl",
        "Buf",
        "Lys",
        "H20",
        "",
        ""
    ]

    outlet_names = [
        "LB",
        "Waste",
        "Prod",
        "",
        "",
        ""
    ]


    with Client(url="opc.tcp://localhost:4842") as client:
        biosmb = BioSMBManager(client, 
                               inlet_names=inlet_names, 
                               outlet_names=outlet_names)

        print("*** Reseting system ***")
        biosmb.zero_all_flows()
        time.sleep(1)
        biosmb.close_all_valves()
        time.sleep(0.5)

        print("*** Setting up flowpath ***")
        biosmb.open_valve("A5")
        biosmb.open_valve("A11")
        time.sleep(0.5)

        print("*** Starting pump 4 ***")
        biosmb.enable_all_pumps()
        biosmb.set_flow(4, 2.5)
        
        biosmb.print_status()

        while(True):
            uv_value = biosmb.get_uv(1)
            if(uv_value["A"] > 2.9):
                break
            print(f"Waiting for breakthrough... UV = {uv_value['A']}")
            time.sleep(1)

        print("*** Stopping pump ***")
        biosmb.set_flow(4, 0)
        time.sleep(0.5)

        print("*** Setting up flowpath ***")
        biosmb.close_valve("A5")
        biosmb.open_valve("A4")
        time.sleep(0.5)

        print("*** Starting wash pump ***")
        biosmb.set_flow(3, 2.5)
        biosmb.print_status()
        time.sleep(3)