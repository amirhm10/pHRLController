import asyncio
import json
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from asyncua import ua


@contextmanager
def local_biosmb_manager(
    host: str = "127.0.0.1",
    port: int = 4865,
    inlet_names: list[str] | None = None,
    outlet_names: list[str] | None = None,
    server_sample_s: float = 0.5,
):
    """Start the local OPC emulator and yield a connected BioSMBManager."""
    if sys.version_info >= (3, 14):
        raise SystemExit(
            "asyncua currently fails in this workspace on Python 3.14. "
            "Run with Python 3.13, for example: "
            "py -3.13 run_biosmb_ph_readonly_smoke_test.py"
        )

    modules = load_biosmb_modules()
    stop_event = threading.Event()
    server_state: dict[str, object] = {}
    server_thread = threading.Thread(
        target=start_emulator_thread,
        args=(
            modules["BioSMBOPCEmulator"],
            stop_event,
            server_state,
            host,
            port,
            server_sample_s,
        ),
        daemon=True,
    )
    server_thread.start()
    settings_path = write_temp_emulator_settings(wait_for_namespace(server_state))

    try:
        with modules["Client"](url=f"opc.tcp://{host}:{port}/BioSMB/") as client:
            yield modules["BioSMBManager"](
                client,
                settings_file=str(settings_path),
                inlet_names=inlet_names,
                outlet_names=outlet_names,
            )
    finally:
        stop_event.set()
        server_thread.join(timeout=5)
        settings_path.unlink(missing_ok=True)


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


def wait_for_namespace(
    server_state: dict[str, object],
    timeout_s: float = 10.0,
) -> int:
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
