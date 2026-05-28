import asyncio
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

from asyncua import ua

sys.path.insert(0, str(Path("BIOSMBControlLibrary").resolve()))
sys.path.insert(0, str(Path("BIOSMBControlLibrary/opc_emulator").resolve()))

from asyncua.sync import Client
from biosmb_interface.manager import BioSMBManager
from biosmb_opc_emulator import BioSMBOPCEmulator


HOST = "127.0.0.1"
PORT = 4865

PUMP_STREAMS = {
    2: "acetic acid",
    3: "sodium acetate",
    4: "Arium water",
}
PH_VALVES = ["P2", "P3", "P4"]

inlet_names = ["", "Acetic acid", "Sodium acetate", "Arium water", "", "", ""]
outlet_names = ["PH_2 measurement", "", "", "", "", ""]


def start_emulator(stop_event, server_state):
    async def runner():
        emulator = BioSMBOPCEmulator(HOST, PORT)
        await emulator._configure_server()
        server_state["namespace_id"] = emulator._namespace_id
        async with emulator._server:
            while not stop_event.is_set():
                await write_emulator_values(emulator)
                await asyncio.sleep(0.5)

    try:
        asyncio.run(runner())
    except Exception as exc:
        server_state["error"] = repr(exc)
        raise


async def write_emulator_values(emulator):
    for idx, node in enumerate(emulator.ph):
        ph_value = 4.65 if idx == 0 else 4.50
        await node.write_value(ua.Variant(ph_value, ua.VariantType.Float))
    for node in emulator.conductivity:
        await node.write_value(ua.Variant(0.30, ua.VariantType.Float))
    for node in emulator.pressures:
        await node.write_value(ua.Variant(1.20, ua.VariantType.Float))
    for idx in range(emulator.num_uv):
        await emulator.uv_a[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))
        await emulator.uv_b[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))
        await emulator.uv_c[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))


def wait_for_namespace(server_state, timeout_s=10.0):
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        if "error" in server_state:
            raise RuntimeError(f"emulator failed: {server_state['error']}")
        namespace_id = server_state.get("namespace_id")
        if namespace_id is not None:
            return int(namespace_id)
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for emulator namespace id.")


def make_emulator_settings(namespace_id):
    ns = int(namespace_id)
    settings = {
        "YV_AD_1": f"ns={ns};s=Discrete_Out.YV_AD_1",
        "YV_EH_1": f"ns={ns};s=Discrete_Out.YV_EH_1",
        "YV_IL_1": f"ns={ns};s=Discrete_Out.YV_IL_1",
        "YV_MP_1": f"ns={ns};s=Discrete_Out.YV_MP_1",
        "FLOW": f"ns={ns};s=PUMP.FLOW",
        "EN": f"ns={ns};s=PUMP.EN",
        "PRESSURE": [f"ns={ns};s=TBIOSMB2DELTAV.P_{i}" for i in range(1, 8)],
        "PH": [f"ns={ns};s=TBIOSMB2DELTAV.PH_{i}" for i in range(1, 3)],
        "CONDUCTIVITY": [
            f"ns={ns};s=TBIOSMB2DELTAV.COND_{i}" for i in range(1, 5)
        ],
        "UV": [
            {
                "A": f"ns={ns};s=TBIOSMB2DELTAV.UV_{i}A",
                "B": f"ns={ns};s=TBIOSMB2DELTAV.UV_{i}B",
                "C": f"ns={ns};s=TBIOSMB2DELTAV.UV_{i}C",
            }
            for i in range(1, 5)
        ],
    }
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    with handle:
        json.dump(settings, handle)
    return Path(handle.name)


stop_event = threading.Event()
server_state = {}
server_thread = threading.Thread(
    target=start_emulator,
    args=(stop_event, server_state),
    daemon=True,
)
server_thread.start()
settings_file = make_emulator_settings(wait_for_namespace(server_state))

try:
    with Client(url=f"opc.tcp://{HOST}:{PORT}/BioSMB/") as client:
        biosmb = BioSMBManager(
            client,
            settings_file=str(settings_file),
            inlet_names=inlet_names,
            outlet_names=outlet_names,
        )

        flows = biosmb.get_all_flows()

        print("Pump readbacks")
        for pump_number, stream_name in PUMP_STREAMS.items():
            flow = flows[pump_number - 1]
            print(f"pump {pump_number}: {stream_name}, {flow:.3f} mL/min")

        print("\nValve states")
        for valve_name in PH_VALVES:
            state = biosmb.get_valve(valve_name)
            print(f"{valve_name}: {state.name.lower()}")

        current_ph = biosmb.get_ph(2)
        print(f"\ncurrent pH from PH_2: {current_ph:.4f}")

        sensors = biosmb.get_all_sensors()
        print("\nSensor keys")
        print(", ".join(sorted(sensors.keys())))
finally:
    stop_event.set()
    server_thread.join(timeout=5)
    settings_file.unlink(missing_ok=True)

print("\nRead-only emulator smoke test complete.")
print("No pump enables, flow writes, or valve-open commands were issued.")
