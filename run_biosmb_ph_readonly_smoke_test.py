import argparse
import asyncio
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

from asyncua import ua


PUMP_STREAM_MAP = {
    2: "acetic acid",
    3: "sodium acetate",
    4: "Arium water",
}
PH_VALVES = ["P2", "P3", "P4"]
OUTLET_PH_SENSOR = 2
VALVE_COLUMNS = "ABCDEFGHIJKLMNOP"


def main() -> None:
    if sys.version_info >= (3, 14):
        raise SystemExit(
            "asyncua currently fails in this workspace on Python 3.14. "
            "Run this smoke test with Python 3.13, for example: "
            "py -3.13 run_biosmb_ph_readonly_smoke_test.py"
        )

    args = parse_args()
    validate_valves(PH_VALVES)
    biosmb_modules = load_biosmb_modules()

    stop_event = threading.Event()
    server_state: dict[str, object] = {}
    server_thread = threading.Thread(
        target=start_emulator_thread,
        args=(
            biosmb_modules["BioSMBOPCEmulator"],
            stop_event,
            server_state,
            args.host,
            args.port,
            args.server_sample_s,
        ),
        daemon=True,
    )
    server_thread.start()
    namespace_id = wait_for_namespace(server_state, args.timeout_s)
    settings_path = write_temp_emulator_settings(namespace_id)

    try:
        run_readonly_check(
            client_class=biosmb_modules["Client"],
            manager_class=biosmb_modules["BioSMBManager"],
            url=f"opc.tcp://{args.host}:{args.port}/BioSMB/",
            settings_path=settings_path,
        )
    finally:
        stop_event.set()
        server_thread.join(timeout=5)
        settings_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only pH plumbing smoke test against the local BioSMB OPC "
            "emulator. This script does not enable pumps, set flows, or open "
            "valves."
        )
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4865)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--server-sample-s", type=float, default=0.5)
    return parser.parse_args()


def load_biosmb_modules() -> dict[str, object]:
    sys.path.insert(0, str(Path("BIOSMBControlLibrary").resolve()))
    sys.path.insert(0, str(Path("BIOSMBControlLibrary/opc_emulator").resolve()))
    from asyncua.sync import Client
    from biosmb_interface.manager import BioSMBManager
    from biosmb_opc_emulator import BioSMBOPCEmulator

    return {
        "Client": Client,
        "BioSMBManager": BioSMBManager,
        "BioSMBOPCEmulator": BioSMBOPCEmulator,
    }


def start_emulator_thread(
    emulator_class,
    stop_event: threading.Event,
    server_state: dict[str, object],
    host: str,
    port: int,
    sample_s: float,
) -> None:
    async def runner() -> None:
        emulator = emulator_class(host, port)
        await emulator._configure_server()
        server_state["namespace_id"] = emulator._namespace_id
        async with emulator._server:
            while not stop_event.is_set():
                await write_stable_sensor_values(emulator)
                await asyncio.sleep(sample_s)

    try:
        asyncio.run(runner())
    except Exception as exc:
        server_state["error"] = repr(exc)
        raise


async def write_stable_sensor_values(emulator) -> None:
    for idx, node in enumerate(emulator.ph):
        value = 4.65 if idx == 0 else 4.50
        await node.write_value(ua.Variant(value, ua.VariantType.Float))
    for node in emulator.conductivity:
        await node.write_value(ua.Variant(0.30, ua.VariantType.Float))
    for node in emulator.pressures:
        await node.write_value(ua.Variant(1.20, ua.VariantType.Float))
    for idx in range(emulator.num_uv):
        await emulator.uv_a[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))
        await emulator.uv_b[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))
        await emulator.uv_c[idx].write_value(ua.Variant(2.0, ua.VariantType.Float))


def wait_for_namespace(server_state: dict[str, object], timeout_s: float) -> int:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        if "error" in server_state:
            raise RuntimeError(f"emulator failed: {server_state['error']}")
        namespace_id = server_state.get("namespace_id")
        if namespace_id is not None:
            return int(namespace_id)
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for emulator namespace id.")


def write_temp_emulator_settings(namespace_id: int) -> Path:
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


def run_readonly_check(
    client_class,
    manager_class,
    url: str,
    settings_path: Path,
) -> None:
    with client_class(url=url) as client:
        biosmb = manager_class(
            client,
            settings_file=str(settings_path),
            inlet_names=make_inlet_names(),
            outlet_names=["PH_2 measurement", "", "", "", "", ""],
        )
        flows = biosmb.get_all_flows()
        valve_states = {valve: biosmb.get_valve(valve) for valve in PH_VALVES}
        ph2 = biosmb.get_ph(OUTLET_PH_SENSOR)
        sensors = biosmb.get_all_sensors()

    print("BioSMB pH read-only emulator smoke test passed.")
    print("No pump enables, flow writes, or valve-open commands were issued.")
    print("Pump mapping:")
    for pump_number, stream_name in PUMP_STREAM_MAP.items():
        print(f"  pump {pump_number}: {stream_name}, flow={flows[pump_number - 1]:.3f} mL/min")
    print("Valve coordinate convention: columns A-P left-to-right, rows 1-15.")
    print("pH-case valve labels:")
    for valve_name, state in valve_states.items():
        column, row = parse_valve_name(valve_name)
        print(f"  {valve_name}: column {column}, row {row}, state={state.name.lower()}")
    print(f"Outlet pH measurement: PH_2 = get_ph(2) = {ph2:.4f}")
    print("Sensor keys available for later logging:")
    print("  " + ", ".join(sorted(sensors.keys())))


def make_inlet_names() -> list[str]:
    names = [""] * 7
    for pump_number, stream_name in PUMP_STREAM_MAP.items():
        names[pump_number - 1] = stream_name
    return names


def validate_valves(valves: list[str]) -> None:
    for valve_name in valves:
        parse_valve_name(valve_name)


def parse_valve_name(valve_name: str) -> tuple[str, int]:
    name = valve_name.strip().upper()
    if len(name) < 2:
        raise ValueError(f"Valve name must look like A1 through P15: {valve_name}")
    column = name[0]
    row_text = name[1:]
    if column not in VALVE_COLUMNS or not row_text.isdigit():
        raise ValueError(f"Valve name must look like A1 through P15: {valve_name}")
    row = int(row_text)
    if row < 1 or row > 15:
        raise ValueError(f"Valve row must be 1 through 15: {valve_name}")
    return column, row


if __name__ == "__main__":
    main()
