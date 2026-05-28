from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from asyncua import ua

from simulation.ph_emulator_process import PHEmulatorProcess


RESULTS_ROOT = Path("results")
METHOD_NAME = "biosmb_ph_emulator_step_test"
VALVE_COLUMNS = "ABCDEFGHIJKLMNOP"


def main() -> None:
    if sys.version_info >= (3, 14):
        raise SystemExit(
            "asyncua currently fails in this workspace on Python 3.14. "
            "Run this emulator script with Python 3.13, for example: "
            "py -3.13 run_biosmb_ph_emulator_step_test.py"
        )

    args = parse_args()
    pump_map = {
        "acid": args.acid_pump,
        "acetate": args.acetate_pump,
        "water": args.water_pump,
    }
    inlet_rows = {
        "acid": args.acid_inlet_row,
        "acetate": args.acetate_inlet_row,
        "water": args.water_inlet_row,
    }
    validate_pump_mapping(pump_map)
    validate_inlet_rows(inlet_rows)
    validate_outlet_ph_sensor(args.outlet_ph_sensor)
    validate_valve_names(args.valves)
    valve_path_id = args.valve_path_id or make_default_valve_path_id(args.valves)
    biosmb_modules = load_biosmb_modules()
    run_time = datetime.now()
    output_dir = RESULTS_ROOT / f"{METHOD_NAME}_{run_time:%Y%m%d_%H%M%S}"
    table_dir = output_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    log_path = table_dir / "emulator_step_test_log.csv"

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
            pump_map,
        ),
        daemon=True,
    )
    server_thread.start()
    namespace_id = wait_for_namespace(server_state)
    settings_path = write_temp_emulator_settings(namespace_id)

    try:
        run_client_step_test(
            client_class=biosmb_modules["Client"],
            manager_class=biosmb_modules["BioSMBManager"],
            url=f"opc.tcp://127.0.0.1:{args.port}/BioSMB/",
            settings_path=settings_path,
            log_path=log_path,
            sample_s=args.sample_s,
            hold_s=args.hold_s,
            pump_map=pump_map,
            inlet_rows=inlet_rows,
            valve_names=args.valves,
            valve_path_id=valve_path_id,
            outlet_ph_sensor=args.outlet_ph_sensor,
        )
    finally:
        stop_event.set()
        server_thread.join(timeout=5)
        settings_path.unlink(missing_ok=True)

    print(f"BioSMB pH emulator step test complete: {output_dir}")
    print(f"Log written: {log_path}")
    print(
        "Pump mapping: "
        f"acid=pump {pump_map['acid']}, "
        f"acetate=pump {pump_map['acetate']}, "
        f"water=pump {pump_map['water']}"
    )
    print(
        "Physical inlet rows/tubes: "
        f"acid=row {inlet_rows['acid']}, "
        f"acetate=row {inlet_rows['acetate']}, "
        f"water=row {inlet_rows['water']}"
    )
    print(
        "Outlet pH measurement: "
        f"PH_{args.outlet_ph_sensor} via get_ph({args.outlet_ph_sensor})."
    )
    print("Valve coordinates: columns A-P left-to-right, rows 1-15 top-to-bottom.")
    print(f"Open valves: {' '.join(args.valves)}")
    print("Physical outlet path remains unverified; confirm the route before hardware.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a pH-aware one-pump step test against the local BioSMB OPC "
            "emulator without modifying BIOSMBControlLibrary."
        )
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4860)
    parser.add_argument("--hold-s", type=float, default=6.0)
    parser.add_argument("--sample-s", type=float, default=1.0)
    parser.add_argument("--server-sample-s", type=float, default=0.5)
    parser.add_argument(
        "--acid-pump",
        type=int,
        default=2,
        help=(
            "One-indexed BioSMB pump number for acetic acid. The pH setup "
            "uses pump 2 because pump 1 is reported unavailable."
        ),
    )
    parser.add_argument(
        "--acetate-pump",
        type=int,
        default=3,
        help=(
            "One-indexed BioSMB pump number for sodium acetate. The pH setup "
            "uses pump 3."
        ),
    )
    parser.add_argument(
        "--water-pump",
        type=int,
        default=4,
        help=(
            "One-indexed BioSMB pump number for Arium water. The pH setup "
            "uses pump 4."
        ),
    )
    parser.add_argument(
        "--acid-inlet-row",
        type=int,
        default=2,
        help="Physical valve-block row/tube for acetic acid.",
    )
    parser.add_argument(
        "--acetate-inlet-row",
        type=int,
        default=3,
        help="Physical valve-block row/tube for sodium acetate.",
    )
    parser.add_argument(
        "--water-inlet-row",
        type=int,
        default=4,
        help="Physical valve-block row/tube for Arium water.",
    )
    parser.add_argument(
        "--valves",
        nargs="*",
        default=["P2", "P3", "P4"],
        help=(
            "Valve names to open. Defaults mirror the pH expert sketch, but "
            "the physical outlet path is not verified by this script."
        ),
    )
    parser.add_argument(
        "--valve-path-id",
        default="",
        help="Operator label for the valve/outlet path, if physically verified.",
    )
    parser.add_argument(
        "--outlet-ph-sensor",
        type=int,
        default=2,
        choices=(1, 2),
        help="pH sensor used as the outlet pH measurement. Default matches get_ph(2).",
    )
    args = parser.parse_args()
    args.valves = [valve.upper() for valve in args.valves]
    return args


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
    pump_map: dict[str, int],
) -> None:
    async def runner() -> None:
        emulator = emulator_class(host, port)
        process = PHEmulatorProcess()
        await emulator._configure_server()
        server_state["namespace_id"] = emulator._namespace_id
        async with emulator._server:
            while not stop_event.is_set():
                flows = await emulator.pump_flows.read_value()
                acid_flow, acetate_flow, water_flow = read_mapped_flows(
                    flows,
                    pump_map,
                )
                state = process.step(
                    acid_flow,
                    acetate_flow,
                    water_flow,
                    sample_s,
                )
                total_flow = max(state["total_flow"], 0.0)
                ph2 = float(state["ph_sensor"])
                ph1 = ph2 + 0.15
                conductivity = 0.2 + 0.02 * total_flow
                pressure = 1.0 + 0.03 * total_flow

                for idx, node in enumerate(emulator.ph):
                    value = ph1 if idx == 0 else ph2
                    await node.write_value(ua.Variant(value, ua.VariantType.Float))
                for node in emulator.conductivity:
                    await node.write_value(
                        ua.Variant(conductivity, ua.VariantType.Float)
                    )
                for node in emulator.pressures:
                    await node.write_value(ua.Variant(pressure, ua.VariantType.Float))
                for idx in range(emulator.num_uv):
                    await emulator.uv_a[idx].write_value(
                        ua.Variant(2.0, ua.VariantType.Float)
                    )
                    await emulator.uv_b[idx].write_value(
                        ua.Variant(2.0, ua.VariantType.Float)
                    )
                    await emulator.uv_c[idx].write_value(
                        ua.Variant(2.0, ua.VariantType.Float)
                    )
                await asyncio.sleep(sample_s)

    try:
        asyncio.run(runner())
    except Exception as exc:
        server_state["error"] = repr(exc)
        raise


def wait_for_namespace(server_state: dict[str, object], timeout_s: float = 10.0) -> int:
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


def run_client_step_test(
    client_class,
    manager_class,
    url: str,
    settings_path: Path,
    log_path: Path,
    sample_s: float,
    hold_s: float,
    pump_map: dict[str, int],
    inlet_rows: dict[str, int],
    valve_names: list[str],
    valve_path_id: str,
    outlet_ph_sensor: int,
) -> None:
    schedule = one_pump_step_schedule(hold_s)
    process = PHEmulatorProcess()
    fieldnames = make_log_fieldnames()
    sample_index = 0
    start_time = time.monotonic()

    with client_class(url=url) as client:
        biosmb = manager_class(
            client,
            settings_file=str(settings_path),
            inlet_names=make_inlet_names(pump_map),
            outlet_names=[f"PH_{outlet_ph_sensor} measurement", "", "", "", "", ""],
        )
        with log_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            try:
                biosmb.zero_all_flows()
                biosmb.disable_all_pumps()
                biosmb.close_all_valves()
                for valve_name in valve_names:
                    biosmb.open_valve(valve_name)
                for pump_number in pump_map.values():
                    biosmb.enable_pump(pump_number)

                for step in schedule:
                    biosmb.set_flow(
                        pump_map["acid"],
                        step["acid_flow_cmd_ml_min"],
                    )
                    biosmb.set_flow(
                        pump_map["acetate"],
                        step["acetate_flow_cmd_ml_min"],
                    )
                    biosmb.set_flow(
                        pump_map["water"],
                        step["water_flow_cmd_ml_min"],
                    )
                    step_start = time.monotonic()
                    while time.monotonic() - step_start <= step["hold_s"]:
                        flows = biosmb.get_all_flows()
                        sensors = biosmb.get_all_sensors()
                        ph_measured = biosmb.get_ph(outlet_ph_sensor)
                        sensors[f"PH_{outlet_ph_sensor}"] = ph_measured
                        static = process.static_prediction(
                            step["acid_flow_cmd_ml_min"],
                            step["acetate_flow_cmd_ml_min"],
                            step["water_flow_cmd_ml_min"],
                        )
                        row = make_log_row(
                            sample_index=sample_index,
                            elapsed_s=time.monotonic() - start_time,
                            hold_elapsed_s=time.monotonic() - step_start,
                            step=step,
                            flows=flows,
                            sensors=sensors,
                            static=static,
                            pump_map=pump_map,
                            inlet_rows=inlet_rows,
                            valve_names=valve_names,
                            valve_path_id=valve_path_id,
                            outlet_ph_sensor=outlet_ph_sensor,
                            ph_measured=ph_measured,
                        )
                        writer.writerow(row)
                        sample_index += 1
                        time.sleep(sample_s)
            finally:
                biosmb.zero_all_flows()
                biosmb.disable_all_pumps()
                biosmb.close_all_valves()


def one_pump_step_schedule(hold_s: float) -> list[dict[str, float | str | int]]:
    rows = [
        ("baseline", 3.0, 3.0, 3.0),
        ("acid_positive_step", 6.0, 3.0, 3.0),
        ("baseline_return", 3.0, 3.0, 3.0),
        ("acetate_positive_step", 3.0, 6.0, 3.0),
        ("baseline_return", 3.0, 3.0, 3.0),
        ("water_positive_step", 3.0, 3.0, 6.0),
        ("baseline_return", 3.0, 3.0, 3.0),
    ]
    schedule = []
    for step_id, (step_type, acid, acetate, water) in enumerate(rows):
        schedule.append({
            "block_id": "one_pump_local_steps",
            "step_id": step_id,
            "step_type": step_type,
            "acid_flow_cmd_ml_min": acid,
            "acetate_flow_cmd_ml_min": acetate,
            "water_flow_cmd_ml_min": water,
            "total_flow_cmd_ml_min": acid + acetate + water,
            "hold_s": float(hold_s),
        })
    return schedule


def make_log_fieldnames() -> list[str]:
    return [
        "utc_time",
        "sample_index",
        "elapsed_s",
        "hold_elapsed_s",
        "block_id",
        "step_id",
        "step_type",
        "acid_pump_number",
        "acetate_pump_number",
        "water_pump_number",
        "acid_inlet_row",
        "acetate_inlet_row",
        "water_inlet_row",
        "valve_path_id",
        "open_valves",
        "outlet_path_verified",
        "outlet_ph_sensor_number",
        "outlet_ph_sensor_name",
        "acid_flow_cmd_ml_min",
        "acetate_flow_cmd_ml_min",
        "water_flow_cmd_ml_min",
        "total_flow_cmd_ml_min",
        "acid_flow_meas_ml_min",
        "acetate_flow_meas_ml_min",
        "water_flow_meas_ml_min",
        "total_flow_meas_ml_min",
        "buffer_flow_sum_ml_min",
        "flow_ratio_acetate_acid",
        "log10_flow_ratio_acetate_acid",
        "water_fraction",
        "ph_equilibrium_charge_balance",
        "ph_equilibrium_affine",
        "ph_measured",
        *make_sensor_fieldnames(),
    ]


def make_log_row(
    sample_index: int,
    elapsed_s: float,
    hold_elapsed_s: float,
    step: dict[str, float | str | int],
    flows: list[float],
    sensors: dict[str, float],
    static: dict[str, float],
    pump_map: dict[str, int],
    inlet_rows: dict[str, int],
    valve_names: list[str],
    valve_path_id: str,
    outlet_ph_sensor: int,
    ph_measured: float,
) -> dict[str, float | str | int]:
    acid_meas, acetate_meas, water_meas = read_mapped_flows(flows, pump_map)
    total_meas = acid_meas + acetate_meas + water_meas
    ratio = acid_meas and acetate_meas / acid_meas
    sensor_values = {
        name: sensors.get(name, "")
        for name in make_sensor_fieldnames()
    }
    return {
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "sample_index": sample_index,
        "elapsed_s": elapsed_s,
        "hold_elapsed_s": hold_elapsed_s,
        "block_id": step["block_id"],
        "step_id": step["step_id"],
        "step_type": step["step_type"],
        "acid_pump_number": pump_map["acid"],
        "acetate_pump_number": pump_map["acetate"],
        "water_pump_number": pump_map["water"],
        "acid_inlet_row": inlet_rows["acid"],
        "acetate_inlet_row": inlet_rows["acetate"],
        "water_inlet_row": inlet_rows["water"],
        "valve_path_id": valve_path_id,
        "open_valves": " ".join(valve_names),
        "outlet_path_verified": False,
        "outlet_ph_sensor_number": outlet_ph_sensor,
        "outlet_ph_sensor_name": f"PH_{outlet_ph_sensor}",
        "acid_flow_cmd_ml_min": step["acid_flow_cmd_ml_min"],
        "acetate_flow_cmd_ml_min": step["acetate_flow_cmd_ml_min"],
        "water_flow_cmd_ml_min": step["water_flow_cmd_ml_min"],
        "total_flow_cmd_ml_min": step["total_flow_cmd_ml_min"],
        "acid_flow_meas_ml_min": acid_meas,
        "acetate_flow_meas_ml_min": acetate_meas,
        "water_flow_meas_ml_min": water_meas,
        "total_flow_meas_ml_min": total_meas,
        "buffer_flow_sum_ml_min": acid_meas + acetate_meas,
        "flow_ratio_acetate_acid": ratio,
        "log10_flow_ratio_acetate_acid": np_log10_or_nan(ratio),
        "water_fraction": water_meas / total_meas if total_meas > 0.0 else "",
        "ph_equilibrium_charge_balance": static["ph_equilibrium_charge_balance"],
        "ph_equilibrium_affine": static["ph_equilibrium_affine"],
        "ph_measured": ph_measured,
        **sensor_values,
    }


def np_log10_or_nan(value: float) -> float:
    if value <= 0.0:
        return float("nan")
    import math

    return math.log10(value)


def make_sensor_fieldnames() -> list[str]:
    return (
        [f"P_{i}" for i in range(1, 8)]
        + ["PH_1", "PH_2"]
        + [f"COND_{i}" for i in range(1, 5)]
    )


def validate_pump_mapping(pump_map: dict[str, int]) -> None:
    pump_numbers = list(pump_map.values())
    invalid = [number for number in pump_numbers if number < 1 or number > 7]
    if invalid:
        raise ValueError(f"BioSMB pump numbers must be 1 through 7: {invalid}")
    if len(set(pump_numbers)) != len(pump_numbers):
        raise ValueError(f"Pump mapping must use distinct pumps: {pump_map}")


def validate_inlet_rows(inlet_rows: dict[str, int]) -> None:
    rows = list(inlet_rows.values())
    invalid = [number for number in rows if number < 1 or number > 15]
    if invalid:
        raise ValueError(f"BioSMB inlet rows must be 1 through 15: {invalid}")
    if len(set(rows)) != len(rows):
        raise ValueError(f"Inlet row mapping must use distinct rows: {inlet_rows}")


def validate_outlet_ph_sensor(sensor_number: int) -> None:
    if sensor_number not in (1, 2):
        raise ValueError(f"Outlet pH sensor must be 1 or 2: {sensor_number}")


def validate_valve_names(valve_names: list[str]) -> None:
    for valve_name in valve_names:
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


def make_default_valve_path_id(valve_names: list[str]) -> str:
    parsed = [parse_valve_name(name) for name in valve_names]
    columns = {column for column, _ in parsed}
    rows = sorted(row for _, row in parsed)
    if columns == {"P"} and rows == [2, 3, 4]:
        return "p_column_rows_2_3_4_outlet_path_unverified"
    if not valve_names:
        return "no_valves_outlet_path_unverified"
    return f"valves_{'_'.join(valve_names)}_outlet_path_unverified"


def make_inlet_names(pump_map: dict[str, int]) -> list[str]:
    names = [""] * 7
    names[pump_map["acid"] - 1] = "Acid"
    names[pump_map["acetate"] - 1] = "Acetate"
    names[pump_map["water"] - 1] = "Water"
    return names


def read_mapped_flows(
    flows: list[float],
    pump_map: dict[str, int],
) -> tuple[float, float, float]:
    return (
        float(flows[pump_map["acid"] - 1]),
        float(flows[pump_map["acetate"] - 1]),
        float(flows[pump_map["water"] - 1]),
    )


if __name__ == "__main__":
    main()
