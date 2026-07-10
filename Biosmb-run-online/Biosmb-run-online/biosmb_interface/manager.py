from collections import namedtuple
from asyncua.sync import Client
import asyncua.ua as ua
import json
from typing import Dict, List
from biosmb_interface.enum import ValveState, PumpEnabledState
from biosmb_interface.utility import print_status_text


OPCValveIndex = namedtuple("ValveOPCIndex", ["node_id", "array_index", "bit_index"])

class BioSMBManager():
    def __init__(self,
                 opc_client:Client,
                 settings_file="settings.json",
                 inlet_names: List[str] = None,
                 outlet_names: List[str] = None):
        """_summary_

        Args:
            opc_client (Client): A synchronous opc-ua client with an OPEN connection to the BioSMB (or opcua emulator)
            settings_file (str, optional): A json file with node ids for the OPC-UA nodes in BioSMB. Defaults to "settings.json".
        """
        self.opc_client = opc_client
        self.inlet_names = inlet_names
        self.outlet_names = outlet_names

        with open(settings_file) as f:
            settings = json.load(f)

        self.node_id_list = [
            settings["YV_AD_1"],
            settings["YV_EH_1"],
            settings["YV_IL_1"],
            settings["YV_MP_1"],
        ]
        self._initialize_valve_map()

        self.flow_id = settings["FLOW"]
        self.enable_id = settings["EN"]
        self.pressure_ids = settings["PRESSURE"]
        self.ph_ids = settings["PH"]
        self.conductivity_ids = settings["CONDUCTIVITY"]
        self.uv_ids =settings["UV"]


    def _initialize_valve_map(self):
        """ This function initializes a dictionary map between
            user friendly names for valves (ie "A3") and the
            OPC-UA node, array index, and bit number that corresponds
            to the valve in the BioSMB PLC's digital output space.
        """
        self.valve_map = {}

        node_index = 0
        array_index = 0
        bit_index = 0

        for column in range(16):
            for row in range(15):
                friendly_name = chr(column+65) + str(row+1)
                self.valve_map[friendly_name] = OPCValveIndex(
                    node_id=self.node_id_list[node_index],
                    array_index=array_index,
                    bit_index=bit_index
                )

                bit_index += 1
                if(bit_index>=8):
                    bit_index = 0
                    array_index += 1

            if(column %4 == 3):
                node_index += 1
                bit_index = 0
                array_index = 0

    def get_valve(self, valve_name:str) -> ValveState:
        """ This function gets the state of an individual valve based on the
        user friendly name for that valve (ie "A3")

        Args:
            valve_name (str): The user friendly name for the valve (ie "A3") note that the frist row is row 1 (same as labeling on BioSMB)

        Returns:
            ValveState: The current state of the valve (either open or closed)
        """
        idx = self.valve_map[valve_name]
        valve_int_array = self.opc_client.get_node(idx.node_id).get_value()
        valve_int = valve_int_array[idx.array_index]
        if((valve_int >> idx.bit_index)&1 == 1):
            return ValveState.OPEN
        else:
            return ValveState.CLOSED


    def set_valve(self, valve_name:str, new_state:ValveState) -> None:
        """ Sets the state of an individual valve based on the user frindely name for
        that valve (ie "A3")

        Args:
            valve_name (str): The user friendly name for the valve (ie "A3").  Note that the first row is 1 (same as labeling on BioSMB)
            new_state (ValveState): The desired state for the valve (open or closed)
        """
        idx = self.valve_map[valve_name]
        node = self.opc_client.get_node(idx.node_id)
        valve_int_array = node.get_value()
        valve_int = valve_int_array[idx.array_index]

        if(new_state == ValveState.OPEN):
            valve_int = valve_int | (1<<idx.bit_index)
        elif(new_state == ValveState.CLOSED):
            valve_int = valve_int & ~(1<<idx.bit_index)

        valve_int_array[idx.array_index] = valve_int

        valve_int_array = ua.DataValue(ua.Variant(valve_int_array, ua.VariantType.Byte))
        node.write_value(valve_int_array)


    def open_valve(self, valve_name:str) -> None:
        """Opens the specified valve based on the user friendly name (ie "A3")

        Args:
            valve_name (str): The name of the valve to open (ie "A3")
        """

        self.set_valve(valve_name, ValveState.OPEN)

    def close_valve(self, valve_name:str) -> None:
        """Closes the specified valve based on the user friendly name (ie "A3")

        Args:
            valve_name (str): The name of the valve to close (ie "A3")
        """

        self.set_valve(valve_name, ValveState.CLOSED)

    def get_all_valves(self) -> Dict[str, ValveState]:
        """ Returns a dictionary with the current states of all valves.  This is implemented
        with the fewist possible OPC-UA calls (ie most efficient) to prevent network delays

        Returns:
            Dict[str, ValveState]: A dictionary where the key is the user friendly name of the valve (ie "A3") and
            the value is the state of the valve (open or closed)
        """
        row_number = 0
        column_number = 0

        toReturn = {}

        all_values = {}
        for k in range(len(self.node_id_list)):
            all_values[self.node_id_list[k]] = self.opc_client.get_node(self.node_id_list[k]).get_value()


        for column in range(16):
            for row in range(15):
                key = chr(column+65) +str(row +1)
                idx: OPCValveIndex = self.valve_map[key]

                value_int = all_values[idx.node_id][idx.array_index]
                if((value_int >> idx.bit_index)&1 == 1):
                    toReturn[key] = ValveState.OPEN
                else:
                    toReturn[key] = ValveState.CLOSED


        return toReturn

    def close_all_valves(self):
        """Closes all valves using the fewest possible OPC-UA writes
        """

        for k in range(len(self.node_id_list)):
            node =self.opc_client.get_node(self.node_id_list[k])
            valve_int_array = node.get_value()

            for i in range(8):
                valve_int_array[i] = 0

            valve_int_array = ua.DataValue(ua.Variant(valve_int_array, ua.VariantType.Byte))
            node.write_value(valve_int_array)


    def get_flow(self, pump_number:int) -> float:
        """Returns the current flow rate for the specified pump in ml/min.  Note
        that pumps are numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.

        Args:
            pump_number (int): A number between 1 to 7 specifying for which pump to get a flow rate value.

        Returns:
            float: The current pump flow rate in ml/min.
        """

        flow_values = self.opc_client.get_node(self.flow_id).get_value()
        return flow_values[pump_number - 1]


    def set_flow(self, pump_number:int, flow_rate: float)-> None:
        """Sets the flow rate of a specified pump in ml/min.  NOte that pumps
        are numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.
        Also note that pumps must be enabled in order to actually run.

        Args:
            pump_number (int): A number between 1 to 7 specifying for which pump to get a flow rate value.
            flow_rate (float): The desired flow rate in ml/min

        """

        node = self.opc_client.get_node(self.flow_id)
        flow_values = node.get_value()
        flow_values[pump_number -1] = flow_rate
        flow_values = ua.DataValue(ua.Variant(flow_values, ua.VariantType.Float))
        node.write_value(flow_values)


    def set_all_flows(self, flow_values: List[float]) -> None:
        """Sets the flow rates of all pumps (in ml/min) at the same time.  Note that pumps
        are numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.  Also
        note that pumps must be enabled in order to actually run.

        Args:
            flow_values (List[float]): A list of floating point values with exactly 7 floating point numbers representing
            the desired flow rates for each pump in ml/min.

        Raises:
            Exception: Raised if an incorrect number of flow rates is specified (must be exactly 7)
        """


        if(len(flow_values) != 7):
            raise Exception("Flow values must be a list of floats with exactly 7 values (one for each pump)")

        node = self.opc_client.get_node(self.flow_id)
        flow_values = ua.DataValue(ua.Variant(flow_values, ua.VariantType.Float))
        node.write_value(flow_values)

    def get_all_flows(self) -> List[float]:
        """Gets all flow rates of all pumps (in ml/min) at the same time. Note that pumps
        are numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.  Also
        note that pumps must be enabled in order to actually run.

        Returns:
            List[float]: A list with 7 floating point values representing the flow rate of each of the 7 pumps.
        """

        flow_values = self.opc_client.get_node(self.flow_id).get_value()
        return flow_values


    def zero_all_flows(self) -> None:
        """Sets all flow rates of all pumps to 0.0
        """
        self.set_all_flows([0.0 for _ in range(7)])

    def get_pump_enabled(self, pump_number:int)-> PumpEnabledState:
        """Gets the current enabled/disabled state of the specified pump

        Args:
            pump_number (int): The pump for which to get the enabled state.  Note that pumps are
            numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.

        Returns:
            PumpEnabledState: The current state of the selected pump (as an enumeration)
        """
        enable_values = self.opc_client.get_node(self.enable_id).get_value()

        if enable_values[pump_number-1]:
            return PumpEnabledState.ENABLED
        else:
            return PumpEnabledState.DISABLED


    def set_pump_enabled(self, pump_number:int, target_state: PumpEnabledState)->None:
        """Sets the enabled/disabled state of the

        Args:
            pump_number (int): The pump for which to set the enabled state.  Note that pumps are
            numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.
            target_state (PumpEnabledState): The desired state of the pump
        """
        node = self.opc_client.get_node(self.enable_id)
        enable_values = node.get_value()
        if(target_state == PumpEnabledState.ENABLED):
            enable_values[pump_number-1] = True
        elif(target_state == PumpEnabledState.DISABLED):
            enable_values[pump_number-1] = False
        enable_values = ua.DataValue(ua.Variant(enable_values, ua.VariantType.Boolean))
        node.write_value(enable_values)

    def enable_pump(self, pump_number:int) -> None:
        """Enables the specified pump.

        Args:
            pump_number (int): The pump to enable.  Note that pumps are
            numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.
        """
        self.set_pump_enabled(pump_number, PumpEnabledState.ENABLED)

    def disable_pump(self, pump_number:int) -> None:
        """Disables the specified pump.

        Args:
            pump_number (int): The pump to disable.  Note that pumps are
            numbered from 1 to 7 with pump 1 feeding row 2 of the valve block.
        """
        self.set_pump_enabled(pump_number, PumpEnabledState.DISABLED)

    def enable_all_pumps(self) -> None:
        """Enables all of the pumps
        """
        enable_values =[True for i in range(7)]
        enable_values =ua.DataValue(ua.Variant(enable_values, ua.VariantType.Boolean))
        self.opc_client.get_node(self.enable_id).write_value(enable_values)


    def disable_all_pumps(self) -> None:
        """Disables all of the pumps
        """
        enable_values =[False for i in range(7)]
        enable_values =ua.DataValue(ua.Variant(enable_values, ua.VariantType.Boolean))
        self.opc_client.get_node(self.enable_id).write_value(enable_values)


    def get_pressure(self, sensor_number:int) -> float:
        """Reads the current pressure for the specified pressure sensor (note 1 indexed)

        Args:
            sensor_number (int): The sensor number (between 1 and 7)

        Returns:
            float: The current pressure measured by this sensor
        """
        return self.opc_client.get_node(self.pressure_ids[sensor_number-1]).get_value()

    def get_ph(self, sensor_number: int) -> float:
        """Reads the current pH for the specified pH sensor (note 1 indexed)

        Args:
            sensor_number (int): The sensor number (1 or 2)

        Returns:
            float: The current pH measured by this sensor
        """
        return self.opc_client.get_node(self.ph_ids[sensor_number-1]).get_value()


    def get_conductivity(self, sensor_number:int) -> float:
        """Reads the current conductivity for the specified conductivity sensor (note 1 indexed)

        Args:
            sensor_number (int): The sensor number (between 1 and 4)

        Returns:
            float: The current conductivity measured by this sensor
        """
        return self.opc_client.get_node(self.conductivity_ids[sensor_number-1]).get_value()


    def get_uv(self, sensor_number:int) -> Dict[str, float]:
        """Reads the current UV for the specified UV sensor (note 1 indexed)

        Args:
            sensor_number (int): The sensor number (between 1 and 4)

        Returns:
            Dict[str, float]: A dictionary with keys "A", "B", and "C" for the current values
            of each of the three wavelengths reported by this sensor.
        """
        to_return= {}

        to_return["A"] = self.opc_client.get_node(self.uv_ids[sensor_number-1]["A"]).get_value()
        to_return["B"] = self.opc_client.get_node(self.uv_ids[sensor_number-1]["B"]).get_value()
        to_return["C"] = self.opc_client.get_node(self.uv_ids[sensor_number-1]["C"]).get_value()

        return to_return


    def get_all_sensors(self) -> Dict[str, float]:
        """Gets a dictionary with the current value of all BioSMB sensors

        Returns:
            Dict[str, float]: A dictinoary with keys for each sensor and the corresponding floating
            point measurements.
        """
        to_return = {}

        for i in range(len(self.pressure_ids)):
            to_return[f"P_{i+1}"] = self.opc_client.get_node(self.pressure_ids[i]).get_value()

        for i in range(len(self.ph_ids)):
            to_return[f"PH_{i+1}"]= self.opc_client.get_node(self.ph_ids[i]).get_value()

        for i in range(len(self.conductivity_ids)):
            to_return[f"COND_{i+1}"]= self.opc_client.get_node(self.conductivity_ids[i]).get_value()

        for i in range(len(self.uv_ids)):
            to_return[f"UV_{i+1}A"]= self.opc_client.get_node(self.uv_ids[i]["A"]).get_value()
            to_return[f"UV_{i+1}B"]= self.opc_client.get_node(self.uv_ids[i]["B"]).get_value()
            to_return[f"UV_{i+1}C"]= self.opc_client.get_node(self.uv_ids[i]["C"]).get_value()

        return to_return


    def print_status(self):
        valve_state = self.get_all_valves()
        flows = self.get_all_flows()
        print_status_text(valve_state, flows, self.inlet_names, self.outlet_names)
