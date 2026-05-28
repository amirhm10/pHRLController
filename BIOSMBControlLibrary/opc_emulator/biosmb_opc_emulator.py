import asyncio
import numpy as np
from asyncua import Server
from asyncua import ua


class BioSMBOPCEmulator():
    def __init__(self, ip_address, tcpip_port) -> None:
        self.tcpip_port = tcpip_port
        self._hosting_url = f"opc.tcp://{ip_address}:{self.tcpip_port}/BioSMB/"
        self._namespace_uri = "https://www.sartorius.com/en/products/process-chromatography/chromatography-systems/continuous-chromatography/multi-column-chromatography"
        self._namespace_id = None
        self._server = None

        self.valve_array_names = [
            "YV_AD_1",
            "YV_EH_1",
            "YV_IL_1",
            "YV_MP_1",
        ]
        self.valve_arrays = [None for i in range(len(self.valve_array_names))]

        self.num_pumps = 7
        self.pump_flows = None
        self.pump_enable = None

        self.num_pressures = 7
        self.pressures = [None for i in range(self.num_pressures)]

        self.num_conductivity = 4
        self.conductivity = [None for i in range(self.num_conductivity)]

        self.num_ph = 2
        self.ph = [None for i in range(self.num_ph)]

        self.num_uv = 4
        self.uv_a = [None for i in range(self.num_uv)]
        self.uv_b = [None for i in range(self.num_uv)]
        self.uv_c = [None for i in range(self.num_uv)]


        

    async def run_server(self):
        await self._configure_server()

        async with self._server:
            while(True):
                
                # make up fake conductivity values
                for i in range(self.num_conductivity):
                    await self.conductivity[i].write_value(ua.Variant(.3 +np.random.normal(0.0, 0.05), ua.VariantType.Float))

                # make up fake pH values
                for i in range(self.num_ph):
                    await self.ph[i].write_value(ua.Variant(4.5 +np.random.normal(0.0, 0.2), ua.VariantType.Float))

                # make up fake pressure values
                for i in range(self.num_pressures):
                    await self.pressures[i].write_value(ua.Variant(1.2 +np.random.normal(0.0, 0.5), ua.VariantType.Float))

                # make up fake UV values
                for i in range(self.num_uv):
                    await self.uv_a[i].write_value(ua.Variant(2 +np.random.normal(0.0, 1), ua.VariantType.Float))
                    await self.uv_b[i].write_value(ua.Variant(2 +np.random.normal(0.0, 1), ua.VariantType.Float))
                    await self.uv_c[i].write_value(ua.Variant(2 +np.random.normal(0.0, 1), ua.VariantType.Float))

                await asyncio.sleep(1)

    async def _configure_server(self):
        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self._hosting_url)
        self._namespace_id = await self._server.register_namespace(self._namespace_uri)

        plc_obj = await self._server.nodes.objects.add_object(self._namespace_id, "PLC1")

        

        # Set up discrete outputs for valve arrays
        for i in range(len(self.valve_arrays)):
            opc_id = f"ns={self._namespace_id}; s=Discrete_Out.{self.valve_array_names[i]}"

            # initialize a byte array 
            values = [0 for j in range(8)]
            values = ua.Variant(values, ua.VariantType.Byte)

            # add to server
            self.valve_arrays[i] = await plc_obj.add_variable(opc_id, self.valve_array_names[i],  values)
            await self.valve_arrays[i].set_writable()
        
        # Set up pumps
        opc_id = f"ns={self._namespace_id}; s=PUMP.FLOW"
        values = [0.0 for j in range(self.num_pumps)]
        values = ua.Variant(values, ua.VariantType.Float)
        self.pump_flows = await plc_obj.add_variable(opc_id, "FLOW", values)
        await self.pump_flows.set_writable()

        opc_id = f"ns={self._namespace_id}; s=PUMP.EN"
        values = [False for j in range(self.num_pumps)]
        values = ua.Variant(values, ua.VariantType.Boolean)
        self.pump_enable = await plc_obj.add_variable(opc_id, "EN", values)
        await self.pump_enable.set_writable()


        # set up pressures
        for i in range(self.num_pressures):
            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.P_{i+1}"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.pressures[i] = await plc_obj.add_variable(opc_id, f"P_{i+1}", values)


        # set up conductivity
        for i in range(self.num_conductivity):
            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.COND_{i+1}"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.conductivity[i] = await plc_obj.add_variable(opc_id, f"COND_{i+1}", values)

        # set up pH
        for i in range(self.num_ph):
            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.PH_{i+1}"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.ph[i] = await plc_obj.add_variable(opc_id, f"PH_{i+1}", values)


        # set up UV
        for i in range(self.num_uv):
            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.UV_{i+1}A"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.uv_a[i] = await plc_obj.add_variable(opc_id, f"UV_{i+1}A", values)

            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.UV_{i+1}B"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.uv_b[i] = await plc_obj.add_variable(opc_id, f"UV_{i+1}B", values)

            opc_id = f"ns={self._namespace_id}; s=TBIOSMB2DELTAV.UV_{i+1}C"
            values = 0.0
            values = ua.Variant(values, ua.VariantType.Float)
            self.uv_c[i] = await plc_obj.add_variable(opc_id, f"UV_{i+1}C", values)




