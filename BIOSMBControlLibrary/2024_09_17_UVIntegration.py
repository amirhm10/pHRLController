from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager
import time
import pymongo 


if __name__== "__main__":

    sampling_freq = 10.0
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

    while(True):
        start_time = time.time()
        with Client(url="opc.tcp://192.168.0.2:4840") as client:
            with Client(url = "opc.tcp://192.168.0.162:4841") as uv_client:
                biosmb = BioSMBManager(client, 
                                    inlet_names=inlet_names, 
                                    outlet_names=outlet_names)


                observation = {}
                observation['smb_sensors'] = biosmb.get_all_sensors()
                #observation['smb_valves'] = biosmb.get_all_valves()
                observation['smb_flows']= biosmb.get_all_flows()

                observation['uv_time']= uv_client.get_node("ns=2;i=3").get_value()
                observation['uv_spectrum']= uv_client.get_node("ns=2;i=8").get_value()

        

        mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")

        db = mongo_client['UVTest']

        collection = db["observations"]
        collection.insert_one(observation)

        print("observation saved")
        elsapsed = time.time()- start_time
            
        if(elsapsed<sampling_freq):
            time.sleep(sampling_freq - elsapsed)