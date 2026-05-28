from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager


with Client(url="opc.tcp://192.168.0.2:4840") as client:
    biosmb = BioSMBManager(client, 
                               inlet_names=inlet_names, 
                               outlet_names=outlet_names)

    biosmb.enable_all_pumps()

    biosmb.open_valve("P2")
    biosmb.open_valve("P3")
    biosmb.open_valve("P4")


    time.sleep(1)

    biosmb.set_flow(1, 2.0)
    biosmb.set_flow(2, 2.0)

    while(True):
        current_ph = biosmb.get_ph(2)

        print(f"current pH: {current_ph}")

        time.sleep(15)