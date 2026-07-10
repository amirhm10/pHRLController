"""Deploy the repository's custom pH TD3 actor against BioSMB telemetry.

This file follows the structure of the original Stable-Baselines3 SAC example,
but it uses the custom PyTorch TD3 actor developed in the main repository.

Important safety boundary
-------------------------
The default mode is ``suggest_only``.  In that mode the complete observation,
state, inference, action-mapping, safety, and logging path runs, but no BioSMB
write method is called.  Active control requires several explicit physical
verification flags plus a nonpersistent environment arming value.

This is deployment code only.  It never trains the actor, updates a critic,
uses exploration noise, or loads a replay buffer.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Standard-library imports
# ---------------------------------------------------------------------------

import argparse
import asyncio
import json
import os
import signal
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# 2. Numerical library; network libraries are imported only after policy checks
# ---------------------------------------------------------------------------

import numpy as np

# ---------------------------------------------------------------------------
# 3. Custom TD3 deployment contract
# ---------------------------------------------------------------------------

# When this nested reference project is launched directly from the repository,
# make the root custom Actor package importable.  The container already places
# TD3Agent beside main.py, so this branch has no effect there.
LOCAL_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if (LOCAL_REPOSITORY_ROOT / "TD3Agent" / "actor.py").is_file():
    repository_root_text = str(LOCAL_REPOSITORY_ROOT)
    if repository_root_text not in sys.path:
        sys.path.insert(0, repository_root_text)

from td3_deployment import (
    ActionMappingError,
    FrozenTD3Policy,
    LogicalFlows,
    PolicyBundleError,
    PolicyInputError,
    RatioSumActionMapper,
    build_td3_state,
    extract_logical_flows,
    logical_flows_to_pump_array,
    validate_flow_transition,
    validate_pump_map,
)


# ---------------------------------------------------------------------------
# 4. Exceptions used to separate safety stops from ordinary software failures
# ---------------------------------------------------------------------------

class SafetyShutdown(RuntimeError):
    """Raised when the session must stop because a safety rule failed."""


class ConfigurationError(ValueError):
    """Raised before hardware connection when deployment settings are invalid."""


# ---------------------------------------------------------------------------
# 5. Configuration loading and command-line overrides
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path(__file__).with_name("deployment_settings.json")


def validate_session_limit(config: Mapping[str, Any], control_mode: str) -> int:
    """Return the finite step limit and forbid indefinite active sessions."""

    try:
        max_steps = int(config["timing"].get("max_control_steps", 0))
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError("max_control_steps must be an integer.") from exc
    if max_steps < 0:
        raise ConfigurationError("max_control_steps cannot be negative.")
    if control_mode == "active_control" and max_steps <= 0:
        raise ConfigurationError("Active control requires a finite positive step limit.")
    return max_steps


def load_deployment_config(path: str | Path) -> dict[str, Any]:
    """Load the human-readable deployment settings and check core fields."""

    config_path = Path(path).resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Could not read deployment config: {config_path}") from exc
    if not isinstance(config, dict):
        raise ConfigurationError("Deployment config must contain a JSON object.")

    required_sections = [
        "control",
        "policy",
        "connections",
        "database",
        "target",
        "hardware",
        "safety",
        "timing",
        "mfcs_mass_nodes",
    ]
    missing = [section for section in required_sections if section not in config]
    if missing:
        raise ConfigurationError(f"Deployment config is missing sections: {missing}")

    # JSON strings such as "false" are truthy in Python.  Require literal
    # booleans for every field that can enable a deployment path or fallback.
    boolean_fields = {
        "target": ["use_redis", "allow_fixed_fallback"],
        "hardware": [
            "pump_mapping_verified",
            "mass_mapping_verified",
            "outlet_path_verified",
            "exclusive_pump_control_verified",
            "flow_readback_semantics_verified",
        ],
    }
    for section, fields in boolean_fields.items():
        for field in fields:
            if type(config[section].get(field)) is not bool:
                raise ConfigurationError(
                    f"{section}.{field} must be a JSON boolean."
                )

    mode = config["control"].get("mode")
    if mode not in {"suggest_only", "active_control"}:
        raise ConfigurationError(
            "control.mode must be exactly 'suggest_only' or 'active_control'."
        )

    pump_map = validate_pump_map(config["hardware"].get("pump_map", {}))
    config["hardware"]["pump_map"] = pump_map

    decision_interval = float(config["timing"].get("decision_interval_seconds", 0))
    monitor_interval = float(config["timing"].get("monitor_interval_seconds", 0))
    if decision_interval <= 0 or monitor_interval <= 0:
        raise ConfigurationError("Decision and monitor intervals must be positive.")
    if monitor_interval > decision_interval:
        raise ConfigurationError("Monitor interval cannot exceed decision interval.")

    warmup_samples = int(config["timing"].get("warmup_samples", 0))
    if warmup_samples <= 0:
        raise ConfigurationError("warmup_samples must be a positive integer.")

    validate_session_limit(config, str(mode))

    try:
        hard_ph_min = float(config["safety"]["hard_ph_min"])
        hard_ph_max = float(config["safety"]["hard_ph_max"])
        approved_min = float(config["target"]["approved_min"])
        approved_max = float(config["target"]["approved_max"])
        fixed_target = float(config["target"]["fixed_target_ph"])
        minimum_mass = float(config["safety"]["minimum_mass_grams"])
        max_total_flow = float(config["safety"]["max_total_flow_ml_min"])
        max_pump_step = float(config["safety"]["max_pump_step_ml_min"])
        readback_tolerance = float(
            config["safety"]["flow_readback_tolerance_ml_min"]
        )
        max_rejections = int(config["safety"]["max_consecutive_rejections"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError("Deployment safety settings are incomplete.") from exc
    numeric_values = [
        hard_ph_min,
        hard_ph_max,
        approved_min,
        approved_max,
        fixed_target,
        minimum_mass,
        max_total_flow,
        max_pump_step,
        readback_tolerance,
    ]
    if not np.all(np.isfinite(numeric_values)):
        raise ConfigurationError("Deployment safety settings must be finite.")
    if hard_ph_min >= hard_ph_max:
        raise ConfigurationError("hard_ph_min must be below hard_ph_max.")
    if approved_min >= approved_max:
        raise ConfigurationError("target approved_min must be below approved_max.")
    if not approved_min <= fixed_target <= approved_max:
        raise ConfigurationError("fixed_target_ph is outside the approved interval.")
    if minimum_mass < 0 or max_total_flow <= 0 or max_pump_step <= 0:
        raise ConfigurationError("Mass and flow safety limits are invalid.")
    if readback_tolerance < 0 or max_rejections <= 0:
        raise ConfigurationError("Readback tolerance/rejection limit is invalid.")

    required_mass_names = {
        "acid-mass-grams",
        "acetate-mass-grams",
        "water-mass-grams",
    }
    if set(config["mfcs_mass_nodes"]) != required_mass_names:
        raise ConfigurationError(
            "mfcs_mass_nodes must explicitly map acid, acetate, and water mass."
        )

    config["config_path"] = str(config_path)
    return config


def resolve_manifest_path(config: Mapping[str, Any], override: str | None) -> Path:
    """Resolve config paths by config location and CLI paths by current directory."""

    if override is not None:
        path = Path(override)
        return path.resolve()

    path = Path(str(config["policy"]["manifest_path"]))
    if not path.is_absolute():
        path = Path(config["config_path"]).parent / path
    return path.resolve()


def parse_args() -> argparse.Namespace:
    """Expose only deployment choices that are useful during review."""

    parser = argparse.ArgumentParser(
        description="Run the custom pH TD3 actor in BioSMB shadow or active mode."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--manifest", default=None)
    parser.add_argument(
        "--control-mode",
        choices=["suggest_only", "active_control"],
        default=None,
        help="Override the config mode. The default config remains suggest_only.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Override the finite session step count. Zero means indefinite shadow.",
    )
    parser.add_argument(
        "--validate-policy-only",
        action="store_true",
        help="Verify the manifest, hash, architecture, and golden vectors without network access.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 6. Mongo-safe conversion and durable event logging
# ---------------------------------------------------------------------------

def make_mongo_safe(value: Any) -> Any:
    """Convert NumPy and nested values into MongoDB-compatible values."""

    if isinstance(value, dict):
        return {str(key): make_mongo_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_mongo_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return make_mongo_safe(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, datetime):
        return value
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for audit records."""

    return datetime.now(timezone.utc)


def log_event(collection, event: Mapping[str, Any], *, required: bool) -> None:
    """Insert one audit event before or after a possible hardware action."""

    if collection is None:
        if required:
            raise RuntimeError("Active control requires deployment logging.")
        return
    try:
        collection.insert_one(make_mongo_safe(dict(event)))
    except Exception:
        if required:
            raise
        print("Warning: could not write optional shadow deployment log.")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 7. Live BioSMB and MFCS observation acquisition
# ---------------------------------------------------------------------------

async def get_mfcs_data(config: Mapping[str, Any]) -> dict[str, float]:
    """Read configured bottle-mass nodes from the MFCS OPC-UA endpoint."""

    from asyncua import Client

    mass_values: dict[str, float] = {}
    endpoint = str(config["connections"]["mfcs_url"])
    async with Client(endpoint) as mfcs_client:
        for name, node_id in config["mfcs_mass_nodes"].items():
            mass_values[name] = await mfcs_client.get_node(node_id).get_value()
    return mass_values


async def collect_biosmb_data(
    biosmb_manager: BioSMBManager,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Collect one raw sensor, pump, and mass observation."""

    started_utc = utc_now()
    started_monotonic = time.monotonic()

    # The reliable controlled measurement is PH_2.  All sensors are retained
    # in the raw record, but PH_1 is never used to construct the TD3 state.
    sensors = biosmb_manager.get_all_sensors()
    pump_flows = biosmb_manager.get_all_flows()
    masses = await asyncio.wait_for(
        get_mfcs_data(config),
        timeout=float(config["connections"].get("socket_timeout_seconds", 5.0)),
    )

    completed_utc = utc_now()
    return {
        "acquisition_started_utc": started_utc,
        "acquisition_completed_utc": completed_utc,
        "acquisition_duration_seconds": time.monotonic() - started_monotonic,
        "biosmb-sensors": sensors,
        "biosmb-flows": pump_flows,
        "mfcs-mass": masses,
    }


def get_observation(
    biosmb_manager: BioSMBManager,
    config: Mapping[str, Any],
    *,
    redis_client=None,
    raw_collection=None,
    session_id: str,
) -> dict[str, Any]:
    """Acquire, label, validate, and optionally persist one raw observation."""

    observation = asyncio.run(collect_biosmb_data(biosmb_manager, config))
    observation["session_id"] = session_id
    if redis_client is not None:
        experiment_key = str(config["target"].get("experiment_name_key", ""))
        try:
            observation["experiment_name"] = (
                redis_client.get(experiment_key) if experiment_key else None
            )
        except Exception as exc:
            observation["experiment_name"] = None
            observation["experiment_name_read_error"] = (
                f"{type(exc).__name__}: {exc}"
            )

    valid, reason = validate_observation(observation, config)
    observation["observation_valid"] = valid
    observation["observation_failure_reason"] = reason
    if raw_collection is not None:
        raw_collection.insert_one(make_mongo_safe(observation.copy()))
    return observation


# ---------------------------------------------------------------------------
# 8. Observation, mass, pH, and target validation
# ---------------------------------------------------------------------------

def get_controller_ph(observation: Mapping[str, Any]) -> float:
    """Read PH_2, the only pH measurement permitted in controller state."""

    return float(observation["biosmb-sensors"]["PH_2"])


def validate_observation(
    observation: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[bool, str]:
    """Check the data needed to build one TD3 state."""

    for key in ["biosmb-sensors", "biosmb-flows", "mfcs-mass"]:
        if key not in observation:
            return False, f"missing_{key}"
    sensors = observation["biosmb-sensors"]
    if "PH_2" not in sensors:
        return False, "missing_PH_2"
    try:
        ph_value = float(sensors["PH_2"])
    except (TypeError, ValueError):
        return False, "invalid_PH_2"
    if not np.isfinite(ph_value):
        return False, "nonfinite_PH_2"

    flow_array = np.asarray(observation["biosmb-flows"], dtype=float).reshape(-1)
    if flow_array.shape != (7,) or not np.all(np.isfinite(flow_array)):
        return False, "invalid_seven_pump_flow_array"

    hard_low = float(config["safety"]["hard_ph_min"])
    hard_high = float(config["safety"]["hard_ph_max"])
    if not hard_low <= ph_value <= hard_high:
        return False, "PH_2_outside_hard_envelope"
    return True, "valid"


def check_mass_safety(
    observation: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[bool, str]:
    """Check all three verified reagent inventories against their minima."""

    if not bool(config["hardware"].get("mass_mapping_verified", False)):
        return False, "mfcs_mass_mapping_not_verified"
    masses = observation.get("mfcs-mass")
    if not isinstance(masses, Mapping):
        return False, "missing_mfcs_mass"
    minimum = float(config["safety"]["minimum_mass_grams"])
    for name in config["mfcs_mass_nodes"]:
        if name not in masses:
            return False, f"missing_{name}"
        try:
            value = float(masses[name])
        except (TypeError, ValueError):
            return False, f"invalid_{name}"
        if not np.isfinite(value):
            return False, f"nonfinite_{name}"
        if value < minimum:
            return False, f"{name}_below_{minimum}_grams"
    return True, "valid"


def read_target_ph(
    redis_client,
    config: Mapping[str, Any],
    policy: FrozenTD3Policy,
    *,
    control_mode: str,
) -> tuple[float, str]:
    """Read and validate the target without silently clipping operator intent."""

    target_config = config["target"]
    raw_value = None
    source = "fixed_config"
    if bool(target_config.get("use_redis", True)) and redis_client is not None:
        try:
            raw_value = redis_client.get(str(target_config["redis_key"]))
            if raw_value is not None:
                source = "redis"
        except Exception:
            raw_value = None
            print("Warning: Redis target read failed.")
            traceback.print_exc()

    if raw_value is None:
        allow_fallback = bool(target_config.get("allow_fixed_fallback", False))
        if control_mode == "active_control" and not allow_fallback:
            raise SafetyShutdown("No valid live target and fixed fallback is disabled.")
        raw_value = target_config["fixed_target_ph"]
        source = "fixed_config"

    try:
        target = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise SafetyShutdown("Target pH is not numeric.") from exc
    if not np.isfinite(target):
        raise SafetyShutdown("Target pH is not finite.")

    config_low = float(target_config["approved_min"])
    config_high = float(target_config["approved_max"])
    policy_low, policy_high = policy.target_ph_bounds
    accepted_low = max(config_low, policy_low)
    accepted_high = min(config_high, policy_high)
    if not accepted_low <= target <= accepted_high:
        raise SafetyShutdown(
            f"Target {target} is outside approved interval [{accepted_low}, {accepted_high}]."
        )
    return target, source


# ---------------------------------------------------------------------------
# 9. Active-control preflight and nonpersistent arming
# ---------------------------------------------------------------------------

def validate_active_control_preconditions(
    config: Mapping[str, Any],
    policy: FrozenTD3Policy,
    control_mode: str,
) -> None:
    """Fail before OPC connection unless all active-control gates are explicit."""

    if control_mode == "suggest_only":
        return
    if control_mode != "active_control":
        raise ConfigurationError(f"Unsupported control mode: {control_mode}")

    required_flags = [
        "pump_mapping_verified",
        "mass_mapping_verified",
        "outlet_path_verified",
        "exclusive_pump_control_verified",
        "flow_readback_semantics_verified",
    ]
    for flag in required_flags:
        if not bool(config["hardware"].get(flag, False)):
            raise ConfigurationError(f"Active control requires {flag}=true.")

    source = policy.source_metadata
    required_policy_evidence = {
        "simulation_only": False,
        "lab_validated": True,
        "dynamic_model_validated": True,
        "frozen_policy_validated": True,
    }
    for field, required_value in required_policy_evidence.items():
        if source.get(field) is not required_value:
            raise ConfigurationError(
                f"Active control requires policy source.{field}={required_value}."
            )

    approved_hash = str(
        config["policy"].get("approved_manifest_sha256", "")
    ).lower()
    if len(approved_hash) != 64 or any(
        character not in "0123456789abcdef" for character in approved_hash
    ):
        raise ConfigurationError(
            "Active control requires an independently approved manifest SHA-256."
        )
    if policy.manifest_sha256 != approved_hash:
        raise ConfigurationError(
            "Loaded policy manifest does not match the approved SHA-256."
        )

    arm_variable = str(config["control"]["arming_environment_variable"])
    required_value = str(config["control"]["required_arming_value"])
    if os.environ.get(arm_variable) != required_value:
        raise ConfigurationError(
            f"Active control is not armed. Set {arm_variable} only for one reviewed session."
        )


def verify_controlled_pumps_enabled(
    biosmb_manager: BioSMBManager,
    pump_map: Mapping[str, int],
) -> None:
    """Require the operator or PLC to enable each mapped pump before control."""

    from biosmb_interface.enum import PumpEnabledState

    for stream, pump_number in pump_map.items():
        state = biosmb_manager.get_pump_enabled(pump_number)
        if state is not PumpEnabledState.ENABLED:
            raise SafetyShutdown(
                f"Mapped {stream} pump {pump_number} is not enabled."
            )


# ---------------------------------------------------------------------------
# 10. One-write command execution and immediate readback verification
# ---------------------------------------------------------------------------

def write_and_verify_flows(
    biosmb_manager: BioSMBManager,
    proposed: LogicalFlows,
    current_pump_flows: Sequence[float],
    pump_map: Mapping[str, int],
    *,
    readback_tolerance: float,
) -> dict[str, Any]:
    """Write one merged seven-pump array and verify controlled readback values."""

    requested_array = logical_flows_to_pump_array(
        logical_flows=proposed,
        current_pump_flows=current_pump_flows,
        pump_map=pump_map,
    )

    write_started = utc_now()
    try:
        biosmb_manager.set_all_flows(requested_array)
    except Exception as exc:
        return {
            "write_started_utc": write_started,
            "write_completed_utc": utc_now(),
            "requested_pump_flows": requested_array,
            "readback_pump_flows": None,
            "readback_valid": False,
            "readback_mismatches": {
                "write_exception": f"{type(exc).__name__}: {exc}"
            },
        }
    try:
        raw_readback = biosmb_manager.get_all_flows()
    except Exception as exc:
        return {
            "write_started_utc": write_started,
            "write_completed_utc": utc_now(),
            "requested_pump_flows": requested_array,
            "readback_pump_flows": None,
            "readback_valid": False,
            "readback_mismatches": {
                "readback_exception": f"{type(exc).__name__}: {exc}"
            },
        }
    write_completed = utc_now()

    try:
        readback_values = np.asarray(raw_readback, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        readback_values = np.array([], dtype=float)
    if readback_values.shape != (7,) or not np.all(np.isfinite(readback_values)):
        return {
            "write_started_utc": write_started,
            "write_completed_utc": write_completed,
            "requested_pump_flows": requested_array,
            "readback_pump_flows": make_mongo_safe(raw_readback),
            "readback_valid": False,
            "readback_mismatches": {
                "readback_array": "expected seven finite pump values"
            },
        }
    readback_array = readback_values.astype(float).tolist()

    mapping = validate_pump_map(pump_map)
    mismatches = {}
    for stream, pump_number in mapping.items():
        requested = float(requested_array[pump_number - 1])
        actual = float(readback_array[pump_number - 1])
        if abs(actual - requested) > float(readback_tolerance):
            mismatches[stream] = {"requested": requested, "readback": actual}

    # Verify that the merged write preserved pumps outside this pH experiment.
    controlled_indices = {number - 1 for number in mapping.values()}
    for index, (before, after) in enumerate(zip(current_pump_flows, readback_array)):
        uncontrolled_changed = (
            index not in controlled_indices
            and abs(float(after) - float(before)) > readback_tolerance
        )
        if uncontrolled_changed:
            mismatches[f"uncontrolled_pump_{index + 1}"] = {
                "before": float(before),
                "readback": float(after),
            }

    return {
        "write_started_utc": write_started,
        "write_completed_utc": write_completed,
        "requested_pump_flows": requested_array,
        "readback_pump_flows": readback_array,
        "readback_valid": not mismatches,
        "readback_mismatches": mismatches,
    }


def stop_controlled_pumps(
    biosmb_manager: BioSMBManager | None,
    pump_map: Mapping[str, int],
    *,
    readback_tolerance: float,
) -> dict[str, Any]:
    """Zero and disable mapped pumps, returning an auditable shutdown receipt."""

    from biosmb_interface.enum import PumpEnabledState

    receipt: dict[str, Any] = {
        "zero_command_attempted": False,
        "disable_attempted_pumps": [],
        "zero_readback_pump_flows": None,
        "shutdown_errors": [],
    }
    if biosmb_manager is None:
        receipt["shutdown_errors"].append("BioSMB manager was not initialized.")
        receipt["shutdown_verified"] = False
        return receipt
    mapping = validate_pump_map(pump_map)
    try:
        current_values = np.asarray(
            biosmb_manager.get_all_flows(),
            dtype=float,
        ).reshape(-1)
        if current_values.shape != (7,) or not np.all(np.isfinite(current_values)):
            raise ValueError("expected seven finite pre-shutdown pump values")
        current = current_values.astype(float).tolist()
        stopped = current.copy()
        for pump_number in mapping.values():
            stopped[pump_number - 1] = 0.0
        receipt["zero_command_attempted"] = True
        biosmb_manager.set_all_flows(stopped)
        print("Controlled pH pump flow commands set to zero.")
        zero_readback = np.asarray(
            biosmb_manager.get_all_flows(),
            dtype=float,
        ).reshape(-1)
        receipt["zero_readback_pump_flows"] = zero_readback.astype(float).tolist()
        if zero_readback.shape != (7,) or not np.all(np.isfinite(zero_readback)):
            raise ValueError("expected seven finite shutdown readback values")
        for stream, pump_number in mapping.items():
            if abs(float(zero_readback[pump_number - 1])) > readback_tolerance:
                receipt["shutdown_errors"].append(
                    f"{stream} pump {pump_number} did not read back zero flow"
                )
    except Exception as exc:
        print("Could not zero controlled pH pump flow commands.")
        traceback.print_exc()
        receipt["shutdown_errors"].append(
            f"zero_or_readback_exception:{type(exc).__name__}:{exc}"
        )
    for stream, pump_number in mapping.items():
        try:
            receipt["disable_attempted_pumps"].append(pump_number)
            biosmb_manager.disable_pump(pump_number)
            enabled_state = biosmb_manager.get_pump_enabled(pump_number)
            if enabled_state is not PumpEnabledState.DISABLED:
                receipt["shutdown_errors"].append(
                    f"{stream} pump {pump_number} did not read back disabled"
                )
        except Exception as exc:
            print(f"Could not disable controlled pump {pump_number}.")
            traceback.print_exc()
            receipt["shutdown_errors"].append(
                f"disable_exception_pump_{pump_number}:{type(exc).__name__}:{exc}"
            )
    receipt["shutdown_verified"] = not receipt["shutdown_errors"]
    return receipt


# ---------------------------------------------------------------------------
# 11. Deadline-based monitoring between TD3 decisions
# ---------------------------------------------------------------------------

def monitor_until_deadline(
    deadline: float,
    biosmb_manager: BioSMBManager,
    config: Mapping[str, Any],
    *,
    redis_client,
    raw_collection,
    session_id: str,
) -> dict[str, Any]:
    """Poll PH_2 and inventory until the next monotonic control deadline."""

    monitor_interval = float(config["timing"]["monitor_interval_seconds"])
    latest = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(monitor_interval, remaining))
        latest = get_observation(
            biosmb_manager,
            config,
            redis_client=redis_client,
            raw_collection=raw_collection,
            session_id=session_id,
        )
        if time.monotonic() > deadline:
            raise SafetyShutdown("Monitoring acquisition exceeded the decision deadline.")
        if not latest["observation_valid"]:
            raise SafetyShutdown(
                f"Invalid observation during hold: {latest['observation_failure_reason']}"
            )
        mass_safe, mass_reason = check_mass_safety(latest, config)
        if not mass_safe and bool(config["hardware"].get("mass_mapping_verified", False)):
            raise SafetyShutdown(mass_reason)
    if latest is None:
        latest = get_observation(
            biosmb_manager,
            config,
            redis_client=redis_client,
            raw_collection=raw_collection,
            session_id=session_id,
        )
    return latest


# ---------------------------------------------------------------------------
# 12. Warm-up and startup reconciliation from real flow readback
# ---------------------------------------------------------------------------

def run_warmup(
    biosmb_manager: BioSMBManager,
    config: Mapping[str, Any],
    *,
    redis_client,
    raw_collection,
    session_id: str,
) -> dict[str, Any]:
    """Collect consecutive observations without assuming initial pump flows."""

    sample_count = int(config["timing"].get("warmup_samples", 1))
    interval = float(config["timing"]["monitor_interval_seconds"])
    latest = None
    for index in range(sample_count):
        latest = get_observation(
            biosmb_manager,
            config,
            redis_client=redis_client,
            raw_collection=raw_collection,
            session_id=session_id,
        )
        if not latest["observation_valid"]:
            raise SafetyShutdown(
                f"Invalid warm-up observation: {latest['observation_failure_reason']}"
            )
        mass_safe, mass_reason = check_mass_safety(latest, config)
        if bool(config["hardware"].get("mass_mapping_verified", False)) and not mass_safe:
            raise SafetyShutdown(f"Warm-up mass safety failure: {mass_reason}")
        print(
            f"Warm-up {index + 1}/{sample_count} | "
            f"PH_2={get_controller_ph(latest):.5f}"
        )
        if index + 1 < sample_count:
            time.sleep(interval)
    assert latest is not None
    return latest


# ---------------------------------------------------------------------------
# 13. Main finite deployment loop
# ---------------------------------------------------------------------------

def run_deployment_loop(
    policy: FrozenTD3Policy,
    biosmb_manager: BioSMBManager,
    config: Mapping[str, Any],
    *,
    control_mode: str,
    redis_client,
    raw_collection,
    deployment_collection,
    session_id: str,
) -> None:
    """Run frozen TD3 inference with shadow-first execution and full logging."""

    pump_map = config["hardware"]["pump_map"]
    mapper = RatioSumActionMapper(policy.flow_mapping)
    max_steps = int(config["timing"]["max_control_steps"])
    interval = float(config["timing"]["decision_interval_seconds"])
    required_logging = control_mode == "active_control"
    max_rejections = int(config["safety"]["max_consecutive_rejections"])
    consecutive_rejections = 0

    warmup_observation = run_warmup(
        biosmb_manager,
        config,
        redis_client=redis_client,
        raw_collection=raw_collection,
        session_id=session_id,
    )

    # The first actor state uses actual pump readback.  It never assumes that
    # the laboratory starts at [1, 1, 1] mL/min.
    previous_flows = extract_logical_flows(
        warmup_observation["biosmb-flows"],
        pump_map,
    )
    mapper.flows_to_action(previous_flows)

    if control_mode == "active_control":
        verify_controlled_pumps_enabled(biosmb_manager, pump_map)

    step_number = 0
    while max_steps <= 0 or step_number < max_steps:
        step_started_monotonic = time.monotonic()
        step_started_utc = utc_now()
        deadline = step_started_monotonic + interval

        observation_before = get_observation(
            biosmb_manager,
            config,
            redis_client=redis_client,
            raw_collection=raw_collection,
            session_id=session_id,
        )
        if not observation_before["observation_valid"]:
            raise SafetyShutdown(observation_before["observation_failure_reason"])

        measured_ph_before = get_controller_ph(observation_before)
        target_ph, target_source = read_target_ph(
            redis_client,
            config,
            policy,
            control_mode=control_mode,
        )

        # Reconcile every decision with the most recent physical pump array.
        previous_flows = extract_logical_flows(
            observation_before["biosmb-flows"],
            pump_map,
        )
        state = build_td3_state(
            measured_ph=measured_ph_before,
            target_ph=target_ph,
            verified_flows=previous_flows,
            mapper=mapper,
        )
        normalized_action = policy.predict(state)
        proposed_flows = mapper.action_to_flows(normalized_action)

        flow_valid, flow_reason = validate_flow_transition(
            proposed=proposed_flows,
            previous=previous_flows,
            mapper=mapper,
            max_step_change=float(config["safety"]["max_pump_step_ml_min"]),
            max_total_flow=float(config["safety"]["max_total_flow_ml_min"]),
        )
        mass_safe, mass_reason = check_mass_safety(observation_before, config)
        if control_mode == "active_control" and not mass_safe:
            raise SafetyShutdown(f"Mass safety failure: {mass_reason}")
        active_readiness = {
            "pump_mapping_verified": bool(
                config["hardware"].get("pump_mapping_verified", False)
            ),
            "mass_mapping_verified": bool(
                config["hardware"].get("mass_mapping_verified", False)
            ),
            "outlet_path_verified": bool(
                config["hardware"].get("outlet_path_verified", False)
            ),
            "exclusive_pump_control_verified": bool(
                config["hardware"].get("exclusive_pump_control_verified", False)
            ),
            "flow_readback_semantics_verified": bool(
                config["hardware"].get(
                    "flow_readback_semantics_verified",
                    False,
                )
            ),
        }

        # Keep numerical policy feasibility separate from authorization to
        # write hardware. Shadow data can therefore never be mistaken for an
        # active-ready candidate while commissioning flags remain false.
        policy_candidate_valid = flow_valid
        active_eligible = flow_valid and mass_safe and all(active_readiness.values())
        if not flow_valid:
            candidate_reason = flow_reason
        elif not mass_safe:
            candidate_reason = mass_reason
        elif not all(active_readiness.values()):
            candidate_reason = "hardware_commissioning_incomplete"
        elif control_mode == "suggest_only":
            candidate_reason = "valid_shadow_candidate"
        else:
            candidate_reason = "valid_active_candidate"

        command_intent = {
            "event_type": "command_intent",
            "utc_time": utc_now(),
            "session_id": session_id,
            "step_number": step_number,
            "control_mode": control_mode,
            "target_ph": target_ph,
            "target_source": target_source,
            "measured_ph_before": measured_ph_before,
            "state_variables": policy.manifest["state_variables"],
            "state": state,
            "normalized_td3_action": normalized_action,
            "proposed_logical_flows": proposed_flows.to_dict(),
            "previous_logical_flows": previous_flows.to_dict(),
            "candidate_valid": policy_candidate_valid,
            "policy_candidate_valid": policy_candidate_valid,
            "active_eligible": active_eligible,
            "candidate_reason": candidate_reason,
            "mass_safe": mass_safe,
            "mass_reason": mass_reason,
            "active_readiness": active_readiness,
            "write_planned": control_mode == "active_control" and active_eligible,
            "write_attempted": False,
            "policy_manifest": str(policy.manifest_path),
            "policy_manifest_sha256": policy.manifest_sha256,
            "policy_weights_sha256": policy.manifest["weights_sha256"],
        }
        log_event(
            deployment_collection,
            command_intent,
            required=required_logging,
        )

        command_receipt = {
            "write_attempted": False,
            "readback_valid": None,
            "pre_command_pump_flows": observation_before["biosmb-flows"],
        }
        rejection_limit_reached = False
        if control_mode == "active_control":
            if not active_eligible:
                consecutive_rejections += 1
                command_receipt["candidate_rejected"] = True
                command_receipt["consecutive_rejections"] = consecutive_rejections
                if consecutive_rejections >= max_rejections:
                    rejection_limit_reached = True
            else:
                command_receipt = write_and_verify_flows(
                    biosmb_manager=biosmb_manager,
                    proposed=proposed_flows,
                    current_pump_flows=observation_before["biosmb-flows"],
                    pump_map=pump_map,
                    readback_tolerance=float(
                        config["safety"]["flow_readback_tolerance_ml_min"]
                    ),
                )
                command_receipt["write_attempted"] = True
                consecutive_rejections = 0
                if not command_receipt["readback_valid"]:
                    log_event(
                        deployment_collection,
                        {
                            **command_receipt,
                            "event_type": "command_readback_failure",
                            "utc_time": utc_now(),
                            "session_id": session_id,
                            "step_number": step_number,
                        },
                        required=True,
                    )
                    raise SafetyShutdown("BioSMB flow command readback mismatch.")

        # A command receipt is logged immediately.  Shadow receipts explicitly
        # prove that no write was attempted.
        log_event(
            deployment_collection,
            {
                **command_receipt,
                "event_type": "command_receipt",
                "utc_time": utc_now(),
                "session_id": session_id,
                "step_number": step_number,
                "control_mode": control_mode,
            },
            required=required_logging,
        )
        if rejection_limit_reached:
            raise SafetyShutdown(
                "Maximum consecutive TD3 candidate rejections reached."
            )

        if time.monotonic() >= deadline:
            raise SafetyShutdown("TD3 decision missed its configured deadline.")
        observation_after = monitor_until_deadline(
            deadline,
            biosmb_manager,
            config,
            redis_client=redis_client,
            raw_collection=raw_collection,
            session_id=session_id,
        )
        measured_ph_after = get_controller_ph(observation_after)

        log_event(
            deployment_collection,
            {
                "event_type": "deployment_step_complete",
                "utc_time": utc_now(),
                "session_id": session_id,
                "step_number": step_number,
                "control_mode": control_mode,
                "step_started_utc": step_started_utc,
                "step_duration_seconds": time.monotonic() - step_started_monotonic,
                "target_ph": target_ph,
                "target_source": target_source,
                "measured_ph_before": measured_ph_before,
                "measured_ph_after": measured_ph_after,
                "absolute_ph_error_after": abs(measured_ph_after - target_ph),
                "candidate_valid": policy_candidate_valid,
                "policy_candidate_valid": policy_candidate_valid,
                "active_eligible": active_eligible,
                "candidate_reason": candidate_reason,
                "normalized_td3_action": normalized_action,
                "proposed_logical_flows": proposed_flows.to_dict(),
                "write_attempted": command_receipt["write_attempted"],
                "readback_valid": command_receipt["readback_valid"],
            },
            required=required_logging,
        )

        print(
            f"Step {step_number} | mode={control_mode} | target={target_ph:.4f} | "
            f"PH_2={measured_ph_after:.4f} | candidate={proposed_flows.to_dict()} | "
            f"write_attempted={command_receipt['write_attempted']}"
        )
        step_number += 1


# ---------------------------------------------------------------------------
# 14. Program entrypoint and guaranteed active-session cleanup
# ---------------------------------------------------------------------------

def main() -> None:
    """Load the policy first, then create network clients and run one session."""

    args = parse_args()
    config = load_deployment_config(args.config)
    if args.control_mode is not None:
        config["control"]["mode"] = args.control_mode
    if args.max_steps is not None:
        config["timing"]["max_control_steps"] = int(args.max_steps)
    control_mode = str(config["control"]["mode"])
    validate_session_limit(config, control_mode)

    # Policy validation occurs before any BioSMB or database connection.  A
    # bad hash, schema, state order, network shape, or golden vector stops here.
    manifest_path = resolve_manifest_path(config, args.manifest)
    policy = FrozenTD3Policy.load(
        manifest_path,
        device=str(config["policy"].get("device", "cpu")),
    )
    validate_active_control_preconditions(config, policy, control_mode)

    print("Custom pH TD3 actor bundle validated.")
    print(f"Manifest: {policy.manifest_path}")
    print(f"Manifest SHA-256: {policy.manifest_sha256}")
    print(f"Control mode: {control_mode}")
    if args.validate_policy_only:
        print("Policy-only validation complete. No network connection was opened.")
        return

    # Hardware and database packages are intentionally imported only after the
    # actor contract has passed.  This also keeps --validate-policy-only usable
    # in the research environment without the laboratory communication stack.
    from asyncua.sync import Client as ClientSync
    from pymongo import MongoClient
    from redis import Redis

    from biosmb_interface.manager import BioSMBManager

    mongo_env_name = str(config["connections"]["mongo_url_environment"])
    mongo_url = os.environ.get(mongo_env_name)
    if not mongo_url:
        raise ConfigurationError(
            f"MongoDB URL is required in environment variable {mongo_env_name}."
        )

    session_id = str(uuid.uuid4())
    pump_map = config["hardware"]["pump_map"]
    biosmb_manager = None
    deployment_collection = None
    shutdown_reason = "normal_completion"

    # Docker sends SIGTERM during `compose stop`. Convert it into the same
    # exception path as another safety stop so the active-session `finally`
    # block can zero and disable the mapped pumps before the grace period ends.
    previous_sigterm_handler = signal.getsignal(signal.SIGTERM)

    def handle_sigterm(signum, _frame) -> None:
        signal_name = signal.Signals(signum).name
        raise SafetyShutdown(f"termination_signal:{signal_name}")

    signal.signal(signal.SIGTERM, handle_sigterm)

    redis_client = Redis(
        host=str(config["connections"]["redis_host"]),
        port=int(config["connections"].get("redis_port", 6379)),
        decode_responses=True,
        socket_timeout=float(config["connections"].get("socket_timeout_seconds", 5.0)),
    )

    mongo_client = MongoClient(
        mongo_url,
        serverSelectionTimeoutMS=int(
            1000 * float(config["connections"].get("socket_timeout_seconds", 5.0))
        ),
    )
    try:
        database = mongo_client.get_database(str(config["database"]["name"]))
        raw_collection = database.get_collection(
            str(config["database"]["raw_observation_collection"])
        )
        deployment_collection = database.get_collection(
            str(config["database"]["deployment_collection"])
        )

        log_event(
            deployment_collection,
            {
                "event_type": "session_start",
                "utc_time": utc_now(),
                "session_id": session_id,
                "control_mode": control_mode,
                "config_path": config["config_path"],
                "pump_map": pump_map,
                "policy_manifest": str(policy.manifest_path),
                "policy_manifest_sha256": policy.manifest_sha256,
                "policy_weights_sha256": policy.manifest["weights_sha256"],
            },
            required=control_mode == "active_control",
        )

        # Cleanup is nested inside the OPC context so active shutdown still has
        # a live connection when it zeros and disables the mapped pumps.
        with ClientSync(str(config["connections"]["biosmb_url"])) as opc_client:
            biosmb_manager = BioSMBManager(
                opc_client,
                settings_file=str(
                    Path(config["config_path"]).parent
                    / config["hardware"]["biosmb_settings_file"]
                ),
            )
            try:
                run_deployment_loop(
                    policy,
                    biosmb_manager,
                    config,
                    control_mode=control_mode,
                    redis_client=redis_client,
                    raw_collection=raw_collection,
                    deployment_collection=deployment_collection,
                    session_id=session_id,
                )
            except KeyboardInterrupt:
                shutdown_reason = "manual_keyboard_interrupt"
                print("Manual stop requested.")
            except SafetyShutdown as exc:
                shutdown_reason = f"safety_shutdown:{exc}"
                print(f"Safety shutdown: {exc}")
            except Exception as exc:
                shutdown_reason = f"software_exception:{exc}"
                print("Deployment session failed.")
                traceback.print_exc()
                raise
            finally:
                shutdown_receipt = None
                if control_mode == "active_control":
                    shutdown_receipt = stop_controlled_pumps(
                        biosmb_manager,
                        pump_map,
                        readback_tolerance=float(
                            config["safety"]["flow_readback_tolerance_ml_min"]
                        ),
                    )
                    if not shutdown_receipt["shutdown_verified"]:
                        shutdown_reason += "|shutdown_not_verified"
                log_event(
                    deployment_collection,
                    {
                        "event_type": "session_shutdown",
                        "utc_time": utc_now(),
                        "session_id": session_id,
                        "control_mode": control_mode,
                        "shutdown_reason": shutdown_reason,
                        "shutdown_receipt": shutdown_receipt,
                    },
                    required=False,
                )
    finally:
        mongo_client.close()
        signal.signal(signal.SIGTERM, previous_sigterm_handler)


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, PolicyBundleError, PolicyInputError, ActionMappingError) as exc:
        print(f"Startup or policy-contract error: {exc}")
        raise SystemExit(2) from exc
