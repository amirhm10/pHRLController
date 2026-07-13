import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# I changed this line: import our custom TD3 model helper instead of Stable-Baselines3 SAC.
from custom_td3 import BioSMBTD3Policy

from redis import Redis
from pymongo import MongoClient
from asyncua.sync import Client as ClientSync
from biosmb_interface.manager import BioSMBManager


# ============================================================
# Deployment settings
# ============================================================

# I changed this line: allow checked TD3 flow commands to be sent to the pumps.
control_mode = "active_control"   # "suggest_only" or "active_control"

# I changed this line: mark this run for online TD3 learning when the learning loop is added.
online_training_enabled = True

deployment_target_ph = 4.7

use_redis_target_ph = True
redis_target_ph_key = "biosmb-inline-mixing_target-ph"

decision_interval_seconds = 60      # controller decision interval
warmup_seconds = 60                 # wait before first control action

controlled_flow_indices = [0, 1, 2]

controlled_stream_names = {
    0: "acetic-acid",
    1: "sodium-acetate",
    2: "di-water",
}

min_flow_rate = 1.0
max_flow_rate = 10.0
# I changed this line: TD3 allows at most 20 mL/min buffer plus 5 mL/min water.
max_total_flow_rate = 25.0

# I changed this line: match the minimum acid-plus-acetate flow used in TD3 training.
min_buffer_flow_sum = 2.0
# I changed this line: match the maximum acid-plus-acetate flow used in TD3 training.
max_buffer_flow_sum = 20.0
# I changed this line: keep water at the fixed value used in TD3 training.
fixed_water_flow_rate = 5.0
# I changed this line: use the same water comparison tolerance as the TD3 flow converter.
water_flow_tolerance = 1.0e-3

minimum_mass_grams = 200.0 + 1000   # bottle mass + safety liquid amount

target_ph_tolerance = 0.1

state_sensor_key = "PH_2"

mfcs_mass_nodes = {
    "acid-mass-grams": "ns=2;s=U02.FWEIGHT_A.Value",
    "sodium-mass-grams": "ns=2;s=U02.FWEIGHT_B.Value",
    "water-mass-grams": "ns=2;s=U02.FWEIGHT_C.Value",
}

mass_safety_keys = [
    "acid-mass-grams",
    "sodium-mass-grams",
    "water-mass-grams",
]

redis_url = r"10.20.18.65"
mongo_url = r"mongodb://dsp_database_user:biosmb@10.20.18.65:27117/"
biosmb_url = r"opc.tcp://10.20.20.10:4840"
mfcs_url = r"opc.tcp://10.20.18.60:4840/BioPAT_MFCS"

settings_file = ".//settings.json"

raw_observation_collection_name = "biosmb-inline-mixing"
deployment_collection_name = "biosmb-rl-controller-deployment"

model_dir = "models"
# I changed this line: point to our TD3 model information file and remove the old SAC model names.
td3_manifest_path = os.path.join(model_dir, "td3_actor_manifest.json")


# ============================================================
# Exceptions
# ============================================================

class SafetyShutdown(Exception):
    """Raised when a hard safety condition is reached."""
    pass


# ============================================================
# Mongo-safe conversion
# ============================================================

def make_mongo_safe(value):
    """Converts common Python/NumPy/Pandas values into MongoDB-safe values."""

    if isinstance(value, dict):
        return {
            str(key): make_mongo_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_mongo_safe(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            make_mongo_safe(item)
            for item in value
        ]

    if isinstance(value, np.ndarray):
        return make_mongo_safe(value.tolist())

    if isinstance(value, np.generic):
        return value.item()

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, datetime):
        return value

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return value

    if isinstance(value, str):
        return value

    if value is None:
        return None

    return str(value)


# ============================================================
# Data collection
# ============================================================

async def get_mfcs_data() -> Dict:
    """Gets MFCS mass observations."""

    from asyncua import Client

    mfcs_mass = {}

    async with Client(mfcs_url) as mfcs_opc_client:
        for mass_name, node_id in mfcs_mass_nodes.items():
            node = mfcs_opc_client.get_node(node_id)
            mfcs_mass[mass_name] = await node.get_value()

    return mfcs_mass


async def get_biosmb_data(biosmb_manager) -> Dict:
    """Gets one observation from the real BioSMB and MFCS system."""

    observation = {"utc_time": datetime.now()}

    sensor_data = biosmb_manager.get_all_sensors()
    flow_data = biosmb_manager.get_all_flows()
    mfcs_mass = await get_mfcs_data()

    observation["biosmb-sensors"] = sensor_data
    observation["biosmb-flows"] = flow_data
    observation["mfcs-mass"] = mfcs_mass

    return observation


def get_observation(
    biosmb_manager,
    redis_client=None,
    raw_observation_collection=None,
) -> Dict:
    """Gets, validates, and optionally logs one online observation."""

    observation = asyncio.run(get_biosmb_data(biosmb_manager))

    if redis_client is not None:
        expr_name = redis_client.get("biosmb-inline-mixing_expriment-name")
        observation["expr_name"] = expr_name

    observation_valid, observation_failure_reason = validate_observation(observation)

    observation["observation_valid"] = observation_valid
    observation["observation_failure_reason"] = observation_failure_reason

    if raw_observation_collection is not None:
        raw_observation_collection.insert_one(
            make_mongo_safe(observation.copy())
        )

    return observation


# ============================================================
# Target pH
# ============================================================

def get_target_ph(redis_client=None) -> float:
    """Gets target pH from Redis if available; otherwise uses fixed value."""

    if use_redis_target_ph and redis_client is not None:
        try:
            target_value = redis_client.get(redis_target_ph_key)

            if target_value is not None:
                return float(target_value)

        except Exception:
            print("Could not read target pH from Redis. Using fixed target.")
            traceback.print_exc()

    return float(deployment_target_ph)


# ============================================================
# State construction
# ============================================================

# I changed this line: the loop now uses the TD3 model helper, so the old SAC state builder was removed.
def get_controller_ph(observation: Dict) -> float:
    """Returns the pH value used by the controller."""

    return float(observation["biosmb-sensors"][state_sensor_key])


# ============================================================
# Action handling
# ============================================================

# I changed this line: the old SAC default and three-flow converter were removed.
# I changed this line: validate the two TD3 values and the exact physical flow rules.
def check_action(action: Dict[str, List[float]]) -> Tuple[bool, str]:
    """Checks the normalized TD3 action and its physical flow values."""

    required_keys = [
        "raw_action",
        "controlled_flow_rates",
        "flow_rates",
        "total_controlled_flow_rate",
    ]
    for key in required_keys:
        if key not in action:
            return False, f"missing_action_{key}"

    try:
        raw_action = np.asarray(action["raw_action"], dtype=float).reshape(-1)
        controlled_flow_rates = np.asarray(
            action["controlled_flow_rates"],
            dtype=float,
        ).reshape(-1)
        flow_rates = np.asarray(action["flow_rates"], dtype=float).reshape(-1)
        reported_total = float(action["total_controlled_flow_rate"])
    except (TypeError, ValueError):
        return False, "action_values_not_numeric"

    if raw_action.shape != (2,):
        return False, "td3_action_must_have_2_values"

    if not np.all(np.isfinite(raw_action)):
        return False, "td3_action_not_finite"

    if np.any(np.abs(raw_action) > 1.0 + 1.0e-6):
        return False, "td3_action_outside_normalized_bounds"

    if controlled_flow_rates.shape != (3,):
        return False, "controlled_flow_list_must_have_3_values"

    if flow_rates.shape != (7,):
        return False, "flow_rate_list_must_have_7_values"

    if not np.all(np.isfinite(controlled_flow_rates)) or not np.all(
        np.isfinite(flow_rates)
    ):
        return False, "flow_rate_not_finite"

    for flow_rate in flow_rates:
        if flow_rate < 0:
            return False, "negative_flow_rate"

    mapped_controlled_flows = np.asarray(
        [flow_rates[index] for index in controlled_flow_indices],
        dtype=float,
    )
    if not np.allclose(
        controlled_flow_rates,
        mapped_controlled_flows,
        atol=1.0e-9,
        rtol=0.0,
    ):
        return False, "controlled_flows_do_not_match_pump_array"

    for flow_rate in controlled_flow_rates:
        if flow_rate < min_flow_rate:
            return False, "controlled_flow_below_minimum"

        if flow_rate > max_flow_rate:
            return False, "controlled_flow_above_maximum"

    acid_flow, acetate_flow, water_flow = controlled_flow_rates
    buffer_flow_sum = float(acid_flow + acetate_flow)
    if buffer_flow_sum < min_buffer_flow_sum:
        return False, "buffer_flow_sum_below_minimum"

    if buffer_flow_sum > max_buffer_flow_sum:
        return False, "buffer_flow_sum_above_maximum"

    if not np.isclose(
        water_flow,
        fixed_water_flow_rate,
        atol=water_flow_tolerance,
        rtol=0.0,
    ):
        return False, "water_flow_does_not_match_td3_fixed_value"

    total_controlled_flow_rate = float(np.sum(controlled_flow_rates))
    if not np.isclose(
        reported_total,
        total_controlled_flow_rate,
        atol=1.0e-9,
        rtol=0.0,
    ):
        return False, "reported_total_flow_does_not_match_action"

    if total_controlled_flow_rate > max_total_flow_rate:
        return False, "total_controlled_flow_above_maximum"

    return True, "valid"


def select_executed_action(
    proposed_action: Dict[str, List[float]],
    previous_executed_action: Dict[str, List[float]],
) -> Tuple[Dict[str, List[float]], bool, str]:
    """Uses proposed action if valid; otherwise repeats previous action."""

    action_valid, action_failure_reason = check_action(proposed_action)

    if action_valid:
        executed_action = proposed_action
    else:
        executed_action = previous_executed_action

    return executed_action, action_valid, action_failure_reason


def apply_action(
    action: Dict[str, List[float]],
    control_mode: str,
    biosmb_manager=None,
) -> None:
    """Applies or only suggests the selected action."""

    if control_mode == "suggest_only":
        return

    if control_mode == "active_control":
        if biosmb_manager is None:
            raise Exception("BioSMB manager is required for active control")

        for flow_index in controlled_flow_indices:
            pump_number = flow_index + 1
            flow_rate = action["flow_rates"][flow_index]

            biosmb_manager.set_flow(pump_number, flow_rate)

        return

    raise Exception("control_mode must be 'suggest_only' or 'active_control'")


# ============================================================
# Safety
# ============================================================

def validate_observation(observation: Dict) -> Tuple[bool, str]:
    """Checks whether observation has the values needed by the controller."""

    required_top_level_keys = [
        "utc_time",
        "biosmb-sensors",
    ]

    for key in required_top_level_keys:
        if key not in observation:
            return False, f"missing_{key}"

    sensor_data = observation["biosmb-sensors"]

    if state_sensor_key not in sensor_data:
        return False, f"missing_sensor_{state_sensor_key}"

    sensor_value = sensor_data[state_sensor_key]

    if sensor_value is None or not np.isfinite(float(sensor_value)):
        return False, f"invalid_sensor_{state_sensor_key}"

    return True, "valid"


def check_mass_safety(observation: Dict) -> Tuple[bool, str]:
    """Checks whether all monitored MFCS masses are above the safety limit."""

    if "mfcs-mass" not in observation:
        return False, "missing_mfcs_mass"

    mfcs_mass = observation["mfcs-mass"]

    for mass_name in mass_safety_keys:
        if mass_name not in mfcs_mass:
            return False, f"missing_{mass_name}"

        mass_value = float(mfcs_mass[mass_name])

        if not np.isfinite(mass_value):
            return False, f"invalid_{mass_name}"

        if mass_value < minimum_mass_grams:
            return False, f"{mass_name}_below_{minimum_mass_grams}_grams"

    return True, "valid"


def stop_biosmb_safely(biosmb_manager) -> None:
    """Stops BioSMB flow as safely as possible."""

    if biosmb_manager is None:
        return

    try:
        biosmb_manager.zero_all_flows()
        print("BioSMB flows set to zero.")
    except Exception:
        print("Could not zero BioSMB flows.")
        traceback.print_exc()

    try:
        biosmb_manager.disable_all_pumps()
        print("BioSMB pumps disabled.")
    except Exception:
        print("Could not disable BioSMB pumps.")
        traceback.print_exc()


# ============================================================
# Logging
# ============================================================

# I changed this line: include the measured action and both TD3 states in each step log.
def log_deployment_step(
    deployment_collection,
    target_ph: float,
    measured_ph_before: float,
    measured_ph_after: float,
    proposed_action: Dict,
    executed_action: Dict,
    measured_action: Dict,
    previous_executed_action: Dict,
    state: np.ndarray,
    next_state: np.ndarray,
    action_valid: bool,
    action_failure_reason: str,
    mass_safe: bool,
    mass_safety_reason: str,
    observation_before: Dict,
    observation_after: Dict,
    control_mode: str,
    step_number: int,
) -> None:
    """Logs only the essential deployment information."""

    if deployment_collection is None:
        return

    ph_error_after = abs(measured_ph_after - target_ph)

    deployment_log = {
        "utc_time": datetime.now(),
        "step_number": step_number,
        "control_mode": control_mode,

        "target_ph": target_ph,
        "measured_ph_before": measured_ph_before,
        "measured_ph_after": measured_ph_after,
        "ph_error_after": ph_error_after,
        "target_ph_tolerance": target_ph_tolerance,

        "proposed_action": proposed_action,
        "executed_action": executed_action,
        # I changed this line: log the normalized action reconstructed from measured flows.
        "measured_action": measured_action,
        "previous_executed_action": previous_executed_action,

        # I changed this line: save both TD3 states needed for a later replay transition.
        "state": state,
        "next_state": next_state,

        "action_valid": action_valid,
        "action_failure_reason": action_failure_reason,

        "mass_safe": mass_safe,
        "mass_safety_reason": mass_safety_reason,
        "minimum_mass_grams": minimum_mass_grams,

        "observation_before": observation_before,
        "observation_after": observation_after,

        "controller_metadata": {
            "mode": "deployment",
            "decision_interval_seconds": decision_interval_seconds,
            "warmup_seconds": warmup_seconds,
            "controlled_flow_indices": controlled_flow_indices,
            "controlled_stream_names": {
                str(flow_index): stream_name
                for flow_index, stream_name in controlled_stream_names.items()
            },
            "min_flow_rate": min_flow_rate,
            "max_flow_rate": max_flow_rate,
            "max_total_flow_rate": max_total_flow_rate,
            "min_buffer_flow_sum": min_buffer_flow_sum,
            "max_buffer_flow_sum": max_buffer_flow_sum,
            "fixed_water_flow_rate": fixed_water_flow_rate,
            "state_sensor_key": state_sensor_key,
            # I changed this line: log our TD3 model file instead of an SAC checkpoint.
            "td3_manifest_path": td3_manifest_path,
        },
    }

    deployment_collection.insert_one(
        make_mongo_safe(deployment_log)
    )


# ============================================================
# Main deployment loop
# ============================================================

def load_trained_model():
    # I changed this line: load and verify our saved custom TD3 actor weights.
    """Loads the verified custom TD3 actor for deployment."""

    print("Loading custom TD3 actor for deployment...")
    # I changed this line: pass the existing BioSMB mapping into our TD3 model helper.
    return BioSMBTD3Policy.load(
        td3_manifest_path,
        controlled_flow_indices=controlled_flow_indices,
        controlled_stream_names=controlled_stream_names,
        state_sensor_key=state_sensor_key,
        device="cpu",
    )


def run_deployment_loop(
    model,
    biosmb,
    redis_client,
    raw_observation_collection,
    deployment_collection,
) -> None:
    """Runs the deployed controller indefinitely."""

    # I changed this line: use the startup flows represented in TD3 action coordinates.
    previous_executed_action = model.default_action()
    step_number = 0

    print(f"Starting warm-up for {warmup_seconds} seconds...")

    for second in range(warmup_seconds):
        observation = get_observation(
            biosmb_manager=biosmb,
            redis_client=redis_client,
            raw_observation_collection=raw_observation_collection,
        )

        observation_valid = observation.get("observation_valid", False)

        if not observation_valid:
            raise Exception(
                f"Invalid observation during warm-up: "
                f"{observation.get('observation_failure_reason')}"
            )

        mass_safe, mass_safety_reason = check_mass_safety(observation)

        if not mass_safe:
            stop_biosmb_safely(biosmb)
            raise SafetyShutdown(mass_safety_reason)

        print(
            f"Warm-up {second + 1}/{warmup_seconds} | "
            f"PH_2={get_controller_ph(observation)}"
        )

        time.sleep(1)

    print("Warm-up complete. Deployment control can now begin.")

    while True:
        target_ph = get_target_ph(redis_client)

        observation_before = get_observation(
            biosmb_manager=biosmb,
            redis_client=redis_client,
            raw_observation_collection=raw_observation_collection,
        )

        if not observation_before.get("observation_valid", False):
            raise Exception(
                f"Invalid observation before action: "
                f"{observation_before.get('observation_failure_reason')}"
            )

        mass_safe, mass_safety_reason = check_mass_safety(observation_before)

        if not mass_safe:
            stop_biosmb_safely(biosmb)
            raise SafetyShutdown(mass_safety_reason)

        measured_ph_before = get_controller_ph(observation_before)

        # I changed this line: build the exact five-element state used in TD3 training.
        state = model.build_state(
            observation=observation_before,
            target_ph=target_ph,
            previous_executed_action=previous_executed_action,
        )

        raw_action, _ = model.predict(
            state,
            deterministic=True,
        )

        # I changed this line: map the two normalized TD3 outputs into BioSMB flows.
        proposed_action = model.format_action(raw_action)

        executed_action, action_valid, action_failure_reason = select_executed_action(
            proposed_action=proposed_action,
            previous_executed_action=previous_executed_action,
        )

        apply_action(
            action=executed_action,
            control_mode=control_mode,
            biosmb_manager=biosmb,
        )

        print(
            f"Step {step_number} | "
            f"Target pH={target_ph} | "
            f"PH before={measured_ph_before} | "
            f"Action valid={action_valid} | "
            f"Executed={executed_action['stream_flow_rates']}"
        )

        observation_after = observation_before

        for second in range(decision_interval_seconds):
            time.sleep(1)

            observation_after = get_observation(
                biosmb_manager=biosmb,
                redis_client=redis_client,
                raw_observation_collection=raw_observation_collection,
            )

            if not observation_after.get("observation_valid", False):
                raise Exception(
                    f"Invalid observation during decision interval: "
                    f"{observation_after.get('observation_failure_reason')}"
                )

            mass_safe, mass_safety_reason = check_mass_safety(observation_after)

            if not mass_safe:
                stop_biosmb_safely(biosmb)
                raise SafetyShutdown(mass_safety_reason)

        measured_ph_after = get_controller_ph(observation_after)

        # I changed this line: reconstruct the action that the measured pump flows represent.
        measured_action = model.action_from_observation(observation_after)
        measured_action_valid, measured_action_failure_reason = check_action(
            measured_action
        )
        if not measured_action_valid:
            stop_biosmb_safely(biosmb)
            raise SafetyShutdown(
                f"invalid_measured_action_{measured_action_failure_reason}"
            )

        # I changed this line: build the next TD3 state for a later replay transition.
        next_state = model.build_state(
            observation=observation_after,
            target_ph=target_ph,
            previous_executed_action=executed_action,
        )

        log_deployment_step(
            deployment_collection=deployment_collection,
            target_ph=target_ph,
            measured_ph_before=measured_ph_before,
            measured_ph_after=measured_ph_after,
            proposed_action=proposed_action,
            executed_action=executed_action,
            measured_action=measured_action,
            previous_executed_action=previous_executed_action,
            state=state,
            next_state=next_state,
            action_valid=action_valid,
            action_failure_reason=action_failure_reason,
            mass_safe=mass_safe,
            mass_safety_reason=mass_safety_reason,
            observation_before=observation_before,
            observation_after=observation_after,
            control_mode=control_mode,
            step_number=step_number,
        )

        ph_error_after = abs(measured_ph_after - target_ph)

        print(
            f"Step {step_number} complete | "
            f"Target pH={target_ph} | "
            f"PH after={measured_ph_after} | "
            f"Error={ph_error_after}"
        )

        # I changed this line: use measured flows as the previous action for the next step.
        previous_executed_action = measured_action
        step_number += 1


if __name__ == "__main__":

    biosmb = None

    try:
        print("Starting BioSMB RL deployment script...")
        print(f"control_mode = {control_mode}")

        redis_client = Redis(redis_url, decode_responses=True)

        model = load_trained_model()

        with MongoClient(mongo_url) as mongoclient:
            database = mongoclient.get_database("dsp_db")

            raw_observation_collection = database.get_collection(
                raw_observation_collection_name
            )

            deployment_collection = database.get_collection(
                deployment_collection_name
            )

            with ClientSync(biosmb_url) as biosmb_opc_client:
                biosmb = BioSMBManager(
                    biosmb_opc_client,
                    settings_file=settings_file,
                )

                run_deployment_loop(
                    model=model,
                    biosmb=biosmb,
                    redis_client=redis_client,
                    raw_observation_collection=raw_observation_collection,
                    deployment_collection=deployment_collection,
                )

    except KeyboardInterrupt:
        print("Manual stop requested.")

        if control_mode == "active_control":
            stop_biosmb_safely(biosmb)

    except SafetyShutdown as safety_error:
        print("Safety shutdown triggered.")
        print(safety_error)

        if control_mode == "active_control":
            stop_biosmb_safely(biosmb)

    except Exception as error:
        print("Deployment script crashed.")
        print(error)
        traceback.print_exc()

        if control_mode == "active_control":
            stop_biosmb_safely(biosmb)
