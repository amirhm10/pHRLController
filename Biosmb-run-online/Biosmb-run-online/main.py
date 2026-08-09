import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# I changed this line: import our custom TD3 deployment, scheduling, and runtime-mode helpers.
from custom_td3 import (
    BioSMBOnlineTD3Trainer,
    BioSMBTD3Policy,
    RuntimeModeError,
    ScheduledSetpointManager,
    select_frozen_action,
    validate_target_ph,
)

from redis import Redis
from pymongo import MongoClient
from asyncua.sync import Client as ClientSync
from biosmb_interface.manager import BioSMBManager


# ============================================================
# Deployment settings
# ============================================================

# I changed this line: allow checked TD3 flow commands to be sent to the pumps.
control_mode = "active_control"   # "suggest_only" or "active_control"

# I changed this line: select fixed, scheduled, or legacy Redis target handling.
target_ph_mode = "fixed"   # "fixed", "scheduled", or "redis"
deployment_target_ph = 4.7

# I changed this line: define the requested scheduled pH range and switching conditions.
scheduled_target_ph_min = 3.76
scheduled_target_ph_max = 5.70
scheduled_setpoint_count = 5
scheduled_max_steps_per_setpoint = 50
scheduled_consecutive_steps_required = 10
target_ph_tolerance = 0.1

redis_target_ph_key = "biosmb-inline-mixing_target-ph"

# I changed this line: allow online learning to be disabled without changing the deployed actor.
online_training_enabled = False
# I changed this line: choose deterministic or small-noise frozen actions when learning is off.
frozen_action_mode = "deterministic"   # "deterministic" or "gaussian_noise"
frozen_action_noise_std = 0.01
frozen_action_noise_seed = 7

decision_interval_seconds = 60      # controller decision interval
warmup_seconds = 60                 # wait before first control action

controlled_flow_indices = [0, 1, 3]

controlled_stream_names = {
    0: "acetic-acid",
    1: "sodium-acetate",
    3: "di-water",
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
# I changed this line: allow fixed-water readback to vary by 0.1 mL/min around 5 mL/min.
water_flow_tolerance = 0.1

minimum_mass_grams = 200.0 + 1000   # bottle mass + safety liquid amount

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
# I changed this line: load the exact active online TD3 settings from the model folder.
td3_online_training_config_path = os.path.join(
    model_dir,
    "td3_online_training_config.json",
)
# I changed this line: begin online learning from the latest trusted offline actor and critic.
td3_training_checkpoint_path = os.path.join(
    model_dir,
    "td3_training_checkpoint.pkl",
)
# I changed this line: save complete online-resume checkpoints in a separate folder.
td3_online_checkpoint_dir = os.path.join(model_dir, "online_checkpoints")


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
    """Gets the configured fixed or Redis target pH."""

    if target_ph_mode == "fixed":
        return float(deployment_target_ph)

    if target_ph_mode == "redis" and redis_client is not None:
        try:
            target_value = redis_client.get(redis_target_ph_key)

            if target_value is not None:
                return float(target_value)

        except Exception:
            print("Could not read target pH from Redis. Using fixed target.")
            traceback.print_exc()

    if target_ph_mode == "scheduled":
        raise RuntimeModeError(
            "Scheduled targets must come from ScheduledSetpointManager."
        )

    return float(deployment_target_ph)


# I changed this line: validate all user-selectable runtime modes before opening the lab control loop.
def prepare_runtime_modes(model):
    """Validate settings and create the optional scheduler and noise generator."""

    if control_mode not in {"suggest_only", "active_control"}:
        raise RuntimeModeError(
            "control_mode must be 'suggest_only' or 'active_control'."
        )
    if target_ph_mode not in {"fixed", "scheduled", "redis"}:
        raise RuntimeModeError(
            "target_ph_mode must be 'fixed', 'scheduled', or 'redis'."
        )
    if frozen_action_mode not in {"deterministic", "gaussian_noise"}:
        raise RuntimeModeError(
            "frozen_action_mode must be 'deterministic' or 'gaussian_noise'."
        )
    if online_training_enabled and control_mode != "active_control":
        raise RuntimeModeError(
            "Online training requires active_control because suggested actions "
            "must not be stored as executed transitions."
        )
    if not np.isfinite(frozen_action_noise_std) or frozen_action_noise_std < 0.0:
        raise RuntimeModeError("frozen_action_noise_std must be nonnegative.")

    state_bounds = np.asarray(model.manifest["state_bounds"], dtype=float)
    if state_bounds.shape != (5, 2):
        raise RuntimeModeError("TD3 manifest has invalid state bounds.")
    target_ph_bounds = (
        float(state_bounds[1, 0]),
        float(state_bounds[1, 1]),
    )
    validate_target_ph(
        deployment_target_ph,
        *target_ph_bounds,
        name="deployment_target_ph",
    )

    target_scheduler = None
    if target_ph_mode == "scheduled":
        validate_target_ph(
            scheduled_target_ph_min,
            *target_ph_bounds,
            name="scheduled_target_ph_min",
        )
        validate_target_ph(
            scheduled_target_ph_max,
            *target_ph_bounds,
            name="scheduled_target_ph_max",
        )
        target_scheduler = ScheduledSetpointManager(
            target_ph_min=scheduled_target_ph_min,
            target_ph_max=scheduled_target_ph_max,
            setpoint_count=scheduled_setpoint_count,
            max_steps_per_setpoint=scheduled_max_steps_per_setpoint,
            consecutive_steps_required=scheduled_consecutive_steps_required,
            tolerance=target_ph_tolerance,
        )

    frozen_action_rng = None
    if not online_training_enabled and frozen_action_mode == "gaussian_noise":
        frozen_action_rng = np.random.default_rng(frozen_action_noise_seed)

    return target_scheduler, frozen_action_rng, target_ph_bounds


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
# I changed this line: keep fixed-water enforcement for commands but allow measured readback to be checked separately.
def check_action(
    action: Dict[str, List[float]],
    *,
    enforce_fixed_water: bool = True,
) -> Tuple[bool, str]:
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

    # I changed this line: only reject a water mismatch when validating a command sent to the pumps.
    if enforce_fixed_water and not np.isclose(
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


# I changed this line: describe a measured water-flow mismatch without stopping the process.
def get_water_flow_warning(action: Dict[str, List[float]]) -> Dict:
    """Returns warning details when measured water differs from 5 mL/min."""

    controlled_flow_rates = np.asarray(
        action["controlled_flow_rates"],
        dtype=float,
    ).reshape(-1)
    water_flow = float(controlled_flow_rates[2])
    absolute_deviation = abs(water_flow - fixed_water_flow_rate)
    warning_active = absolute_deviation > water_flow_tolerance

    return {
        "active": warning_active,
        "reason": (
            "measured_water_flow_outside_tolerance"
            if warning_active
            else "within_tolerance"
        ),
        "measured_water_flow_rate": water_flow,
        "fixed_water_flow_rate": fixed_water_flow_rate,
        "absolute_deviation": absolute_deviation,
        "tolerance": water_flow_tolerance,
    }


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
    water_flow_warning: Dict,
    reward_info: Dict,
    exploration_info: Dict,
    online_training_info: Dict,
    target_update_info: Dict,
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
        # I changed this line: record how and why the runtime target will change for the next state.
        "target_update_info": target_update_info,
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
        # I changed this line: log water readback deviations as warnings instead of shutdown reasons.
        "water_flow_warning": water_flow_warning,

        # I changed this line: log the exact shaped reward used in the replay transition.
        "reward": reward_info.get("reward"),
        "reward_info": reward_info,
        # I changed this line: log exploration noise and every online TD3 update diagnostic.
        "exploration_info": exploration_info,
        "online_training_info": online_training_info,

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
            # I changed this line: log the shared fixed-water tolerance used by safety and TD3 conversion.
            "water_flow_tolerance": water_flow_tolerance,
            "state_sensor_key": state_sensor_key,
            # I changed this line: log every user-selectable fixed and scheduled target setting.
            "target_ph_mode": target_ph_mode,
            "deployment_target_ph": deployment_target_ph,
            "scheduled_target_ph_min": scheduled_target_ph_min,
            "scheduled_target_ph_max": scheduled_target_ph_max,
            "scheduled_setpoint_count": scheduled_setpoint_count,
            "scheduled_max_steps_per_setpoint": (
                scheduled_max_steps_per_setpoint
            ),
            "scheduled_consecutive_steps_required": (
                scheduled_consecutive_steps_required
            ),
            # I changed this line: distinguish frozen deterministic and frozen Gaussian action runs.
            "frozen_action_mode": frozen_action_mode,
            "frozen_action_noise_std": frozen_action_noise_std,
            "frozen_action_noise_seed": frozen_action_noise_seed,
            # I changed this line: record the active online-training settings and source checkpoint.
            "online_training_enabled": online_training_enabled,
            "td3_online_training_config_path": td3_online_training_config_path,
            "td3_training_checkpoint_path": td3_training_checkpoint_path,
            "td3_online_checkpoint_dir": td3_online_checkpoint_dir,
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
        # I changed this line: give the TD3 helper the threshold used for measured-water warnings.
        water_flow_tolerance=water_flow_tolerance,
        device="cpu",
    )


# I changed this line: create the active TD3 learner from our offline actor and critic checkpoint.
def load_online_trainer(model):
    """Loads and verifies the active online TD3 continuation helper."""

    if not online_training_enabled:
        return None

    print("Loading custom TD3 agent for active online training...")
    trainer = BioSMBOnlineTD3Trainer.load(
        config_path=td3_online_training_config_path,
        source_checkpoint=td3_training_checkpoint_path,
        checkpoint_directory=td3_online_checkpoint_dir,
        device="cpu",
    )
    trainer.verify_initial_actor(model)
    print(
        "Online TD3 ready | "
        f"batch size={trainer.agent.batch_size} | "
        f"buffer capacity={trainer.agent.buffer.capacity}"
    )
    return trainer


def run_deployment_loop(
    model,
    online_trainer,
    target_scheduler,
    frozen_action_rng,
    target_ph_bounds,
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

    # I changed this line: initialize one target that will remain consistent with each stored TD3 state.
    if target_scheduler is not None:
        target_ph = target_scheduler.current_target_ph
        print(f"Scheduled pH targets: {target_scheduler.metadata()}")
    else:
        target_ph = validate_target_ph(
            get_target_ph(redis_client),
            *target_ph_bounds,
        )

    while True:
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

        # I changed this line: separate online exploration from frozen deterministic or fixed-noise actions.
        if online_trainer is not None:
            raw_action, exploration_info = online_trainer.take_action(state)
        else:
            raw_action, exploration_info = select_frozen_action(
                model,
                state,
                action_mode=frozen_action_mode,
                gaussian_noise_std=frozen_action_noise_std,
                rng=frozen_action_rng,
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
        # I changed this line: do not reject measured pump readback only because water missed its target.
        measured_action_valid, measured_action_failure_reason = check_action(
            measured_action,
            enforce_fixed_water=False,
        )
        if not measured_action_valid:
            stop_biosmb_safely(biosmb)
            raise SafetyShutdown(
                f"invalid_measured_action_{measured_action_failure_reason}"
            )

        # I changed this line: record and display a non-blocking warning for imperfect water-pump readback.
        water_flow_warning = get_water_flow_warning(measured_action)
        if water_flow_warning["active"]:
            print(
                f"WARNING: measured water flow "
                f"{water_flow_warning['measured_water_flow_rate']:.4f} mL/min "
                f"differs from {fixed_water_flow_rate:.4f} mL/min by "
                f"{water_flow_warning['absolute_deviation']:.4f} mL/min."
            )

        # I changed this line: apply the scheduled OR rule after one completed controller step.
        if target_scheduler is not None:
            target_update_info = target_scheduler.observe(measured_ph_after)
            if not np.isclose(
                target_update_info["target_ph"],
                target_ph,
                atol=1.0e-9,
                rtol=0.0,
            ):
                raise RuntimeModeError(
                    "Scheduled target state does not match the active target."
                )
            next_target_ph = float(target_update_info["next_target_ph"])
        elif target_ph_mode == "redis":
            next_target_ph = validate_target_ph(
                get_target_ph(redis_client),
                *target_ph_bounds,
            )
            target_changed = not np.isclose(
                next_target_ph,
                target_ph,
                atol=1.0e-9,
                rtol=0.0,
            )
            target_update_info = {
                "mode": "redis",
                "target_ph": target_ph,
                "next_target_ph": next_target_ph,
                "target_changed": target_changed,
                "change_reason": (
                    "redis_target_changed" if target_changed else "hold"
                ),
                "within_tolerance": (
                    abs(measured_ph_after - target_ph) <= target_ph_tolerance
                ),
            }
        else:
            next_target_ph = target_ph
            target_update_info = {
                "mode": "fixed",
                "target_ph": target_ph,
                "next_target_ph": next_target_ph,
                "target_changed": False,
                "change_reason": "hold",
                "within_tolerance": (
                    abs(measured_ph_after - target_ph) <= target_ph_tolerance
                ),
            }

        # I changed this line: use the next scheduled target in the next TD3 state while rewarding the old target.
        next_state = model.build_state(
            observation=observation_after,
            target_ph=next_target_ph,
            previous_executed_action=executed_action,
        )

        # I changed this line: compute our shaped reward, store the transition, and update TD3 online.
        if online_trainer is not None:
            executed_controlled_flows = np.asarray(
                executed_action["controlled_flow_rates"],
                dtype=float,
            )
            previous_controlled_flows = np.asarray(
                previous_executed_action["controlled_flow_rates"],
                dtype=float,
            )
            reward_info, online_training_info = online_trainer.record_transition(
                state=state,
                action=executed_action["raw_action"],
                reward_target_ph=target_ph,
                measured_ph_after=measured_ph_after,
                previous_action=previous_executed_action["raw_action"],
                default_action=model.default_action()["raw_action"],
                next_state=next_state,
                buffer_sum=float(np.sum(executed_controlled_flows[:2])),
                previous_buffer_sum=float(
                    np.sum(previous_controlled_flows[:2])
                ),
                buffer_sum_min=min_buffer_flow_sum,
                buffer_sum_max=max_buffer_flow_sum,
                # I changed this line: use the refined action's optional-flow fraction in the online reward.
                economic_flow_fraction=float(
                    np.clip(
                        0.5 * (executed_action["raw_action"][1] + 1.0),
                        0.0,
                        1.0,
                    )
                ),
                done=False,
            )
            online_training_info["checkpoint_saved"] = False
            if online_trainer.should_save(step_number + 1):
                checkpoint_path = online_trainer.save()
                online_training_info["checkpoint_saved"] = True
                online_training_info["last_checkpoint_path"] = checkpoint_path
        else:
            reward_info = {"reward_mode": None, "reward": None}
            online_training_info = {
                "enabled": False,
                "transition_stored": False,
                "train_updated": False,
            }

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
            # I changed this line: include the non-blocking water warning in the MongoDB step log.
            water_flow_warning=water_flow_warning,
            # I changed this line: save the reward and online-learning values used at this step.
            reward_info=reward_info,
            exploration_info=exploration_info,
            online_training_info=online_training_info,
            target_update_info=target_update_info,
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
            f"Error={ph_error_after} | "
            f"Reward={reward_info.get('reward')} | "
            f"Replay size={online_training_info.get('buffer_size', 0)}"
        )

        # I changed this line: keep the last validated command as fallback instead of re-commanding imperfect readback.
        previous_executed_action = executed_action
        # I changed this line: carry forward the exact target already encoded in next_state.
        target_ph = next_target_ph
        step_number += 1


if __name__ == "__main__":

    biosmb = None
    # I changed this line: keep the learner available for a final checkpoint on every controlled exit.
    online_trainer = None
    # I changed this line: keep runtime mode state explicit before any lab connection is opened.
    target_scheduler = None
    frozen_action_rng = None
    target_ph_bounds = None

    try:
        print("Starting BioSMB RL deployment script...")
        print(f"control_mode = {control_mode}")
        print(f"target_ph_mode = {target_ph_mode}")
        print(f"online_training_enabled = {online_training_enabled}")
        print(f"frozen_action_mode = {frozen_action_mode}")

        redis_client = Redis(redis_url, decode_responses=True)

        model = load_trained_model()
        # I changed this line: validate target and action modes before loading a learner or commanding pumps.
        (
            target_scheduler,
            frozen_action_rng,
            target_ph_bounds,
        ) = prepare_runtime_modes(model)
        # I changed this line: start the verified active online TD3 learner when enabled.
        online_trainer = load_online_trainer(model)

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
                    online_trainer=online_trainer,
                    target_scheduler=target_scheduler,
                    frozen_action_rng=frozen_action_rng,
                    target_ph_bounds=target_ph_bounds,
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

    finally:
        # I changed this line: save the learned actor, critics, optimizers, replay, and RNG state after the run.
        if online_trainer is not None:
            try:
                final_checkpoint = online_trainer.save(
                    prefix="td3_online_final"
                )
                print(f"Saved final online TD3 checkpoint: {final_checkpoint}")
            except Exception:
                print("Could not save the final online TD3 checkpoint.")
                traceback.print_exc()
