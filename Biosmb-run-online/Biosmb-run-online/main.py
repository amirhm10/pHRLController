import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from stable_baselines3 import SAC

from redis import Redis
from pymongo import MongoClient
from asyncua.sync import Client as ClientSync
from biosmb_interface.manager import BioSMBManager


# ============================================================
# Deployment settings
# ============================================================

control_mode = "active control"   # "suggest_only" or "active_control"

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
max_total_flow_rate = 30.0

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
model_checkpoint_name = f"{model_dir}/sac_biosmb_mixing_online_checkpoint"
model_name_online = f"{model_dir}/sac_biosmb_mixing_online"


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

def get_controller_ph(observation: Dict) -> float:
    """Returns the pH value used by the controller."""

    return float(observation["biosmb-sensors"][state_sensor_key])


def build_state(
    observation: Dict,
    previous_executed_action: Dict[str, List[float]],
    target_ph: float,
) -> np.ndarray:
    """Builds the trained model state vector.

    State structure:
        [PH_2, target_ph, previous_acetic_acid_flow,
         previous_sodium_acetate_flow, previous_di_water_flow]
    """

    measured_ph = get_controller_ph(observation)

    state = [
        float(measured_ph),
        float(target_ph),
    ]

    state.extend(previous_executed_action["controlled_flow_rates"])

    return np.array(state, dtype=np.float32)


# ============================================================
# Action handling
# ============================================================

def get_default_action() -> Dict[str, List[float]]:
    """Returns a conservative default action."""

    flow_rates = [0.0 for _ in range(7)]

    default_flow_rate = min_flow_rate

    for flow_index in controlled_flow_indices:
        flow_rates[flow_index] = default_flow_rate

    action = {
        "raw_action": None,
        "controlled_flow_rates": [
            default_flow_rate
            for _ in controlled_flow_indices
        ],
        "flow_rates": flow_rates,
        "total_controlled_flow_rate": float(
            default_flow_rate * len(controlled_flow_indices)
        ),
        "stream_flow_rates": {
            controlled_stream_names[flow_index]: flow_rates[flow_index]
            for flow_index in controlled_flow_indices
        },
    }

    return action


def action_to_flow_rates(action: np.ndarray) -> Dict[str, List[float]]:
    """Converts SAC action into seven BioSMB pump flowrates.

    Action structure:
        action[0] = acetic acid flowrate
        action[1] = sodium acetate flowrate
        action[2] = DI water flowrate
    """

    action = np.asarray(action, dtype=np.float32)

    controlled_flow_rates = [
        float(value)
        for value in action
    ]

    flow_rates = [0.0 for _ in range(7)]

    for i, flow_index in enumerate(controlled_flow_indices):
        flow_rates[flow_index] = controlled_flow_rates[i]

    total_controlled_flow_rate = sum(
        flow_rates[flow_index]
        for flow_index in controlled_flow_indices
    )

    formatted_action = {
        "raw_action": action.tolist(),
        "controlled_flow_rates": controlled_flow_rates,
        "flow_rates": flow_rates,
        "total_controlled_flow_rate": float(total_controlled_flow_rate),
        "stream_flow_rates": {
            controlled_stream_names[flow_index]: flow_rates[flow_index]
            for flow_index in controlled_flow_indices
        },
    }

    return formatted_action


def check_action(action: Dict[str, List[float]]) -> Tuple[bool, str]:
    """Checks whether the proposed action is valid."""

    flow_rates = action["flow_rates"]

    if len(flow_rates) != 7:
        return False, "flow_rate_list_must_have_7_values"

    for flow_rate in flow_rates:
        if not np.isfinite(flow_rate):
            return False, "flow_rate_not_finite"

        if flow_rate < 0:
            return False, "negative_flow_rate"

    for flow_index in controlled_flow_indices:
        flow_rate = flow_rates[flow_index]

        if flow_rate < min_flow_rate:
            return False, "controlled_flow_below_minimum"

        if flow_rate > max_flow_rate:
            return False, "controlled_flow_above_maximum"

    total_controlled_flow_rate = sum(
        flow_rates[flow_index]
        for flow_index in controlled_flow_indices
    )

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

def log_deployment_step(
    deployment_collection,
    target_ph: float,
    measured_ph_before: float,
    measured_ph_after: float,
    proposed_action: Dict,
    executed_action: Dict,
    previous_executed_action: Dict,
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
        "previous_executed_action": previous_executed_action,

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
            "state_sensor_key": state_sensor_key,
            "model_checkpoint_name": model_checkpoint_name,
        },
    }

    deployment_collection.insert_one(
        make_mongo_safe(deployment_log)
    )


# ============================================================
# Main deployment loop
# ============================================================

def load_trained_model():
    """Loads the trained SAC model for deployment."""

    if os.path.exists(model_checkpoint_name + ".zip"):
        print("Loading checkpoint model for deployment...")
        return SAC.load(model_checkpoint_name)

    if os.path.exists(model_name_online + ".zip"):
        print("Loading online model for deployment...")
        return SAC.load(model_name_online)

    raise Exception("No trained model found. Deployment cannot start.")


def run_deployment_loop(
    model,
    biosmb,
    redis_client,
    raw_observation_collection,
    deployment_collection,
) -> None:
    """Runs the deployed controller indefinitely."""

    previous_executed_action = get_default_action()
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

        state = build_state(
            observation=observation_before,
            previous_executed_action=previous_executed_action,
            target_ph=target_ph,
        )

        raw_action, _ = model.predict(
            state,
            deterministic=True,
        )

        proposed_action = action_to_flow_rates(raw_action)

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

        log_deployment_step(
            deployment_collection=deployment_collection,
            target_ph=target_ph,
            measured_ph_before=measured_ph_before,
            measured_ph_after=measured_ph_after,
            proposed_action=proposed_action,
            executed_action=executed_action,
            previous_executed_action=previous_executed_action,
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

        previous_executed_action = executed_action
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
