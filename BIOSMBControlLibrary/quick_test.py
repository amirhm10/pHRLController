from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager
import time

if __name__ == "__main__":
    biosmb_url = "opc.tcp://192.168.0.2:4840"



    col = "A"
    with Client(biosmb_url) as client:
        biosmb = BioSMBManager(client)

        biosmb.open_valve(f"{col}2")
        biosmb.open_valve(f"{col}9")
        biosmb.open_valve(f"{col}15")

        biosmb.print_status()

        time.sleep(1)
        biosmb.enable_pump(1)
        time.sleep(1)
        biosmb.set_flow(1, 2.5)

        print(biosmb.get_uv(1))

        time.sleep(15)

        biosmb.zero_all_flows()
        time.sleep(1)
        biosmb.close_all_valves()



    
