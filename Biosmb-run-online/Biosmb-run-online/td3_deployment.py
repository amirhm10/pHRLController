"""Frozen custom-TD3 inference and pH action-contract utilities.

This module deliberately contains no training, replay-buffer, critic, or
exploration code.  It reconstructs the actor used by the main pH repository,
checks its manifest and hash, builds the exact five-element TD3 state, and maps
the two normalized TD3 actions into physical acid, acetate, and water flows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from TD3Agent.actor import Actor


EXPECTED_STATE_VARIABLES = [
    "current_ph",
    "target_ph",
    "current_ph_minus_target_ph",
    "normalized_ratio_action",
    "normalized_buffer_sum_action",
]

EXPECTED_ACTION_VARIABLES = [
    "normalized_acetate_acid_ratio",
    "normalized_acid_acetate_total_flow",
]

EXPECTED_MAPPING_VERSION = "ratio_buffer_sum_v1"


class PolicyBundleError(RuntimeError):
    """Raised when a policy bundle is missing, corrupt, or incompatible."""


class PolicyInputError(ValueError):
    """Raised when a live controller state is invalid or out of contract."""


class ActionMappingError(ValueError):
    """Raised when an RL action or physical-flow mapping is invalid."""


def sha256_file(path: str | Path) -> str:
    """Return a lowercase SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_keys(data: Mapping[str, Any], keys: Sequence[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise PolicyBundleError(f"{context} is missing required keys: {missing}")


@dataclass(frozen=True)
class LogicalFlows:
    """Logical pH-process flows independent of physical pump numbering."""

    acid_flow: float
    acetate_flow: float
    water_flow: float

    @property
    def buffer_flow_sum(self) -> float:
        return float(self.acid_flow + self.acetate_flow)

    @property
    def total_flow(self) -> float:
        return float(self.acid_flow + self.acetate_flow + self.water_flow)

    def to_dict(self) -> dict[str, float]:
        return {key: float(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class FlowMappingConfig:
    """Physical bounds used by the normalized TD3 ratio/sum action."""

    acid_flow_min: float
    acid_flow_max: float
    acetate_flow_min: float
    acetate_flow_max: float
    water_flow_min: float
    water_flow_max: float
    buffer_flow_sum_min: float
    buffer_flow_sum_max: float
    fixed_water_flow: float
    mapping_version: str = EXPECTED_MAPPING_VERSION

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> "FlowMappingConfig":
        mapping = manifest.get("action_mapping")
        if not isinstance(mapping, Mapping):
            raise PolicyBundleError("Manifest action_mapping must be an object.")
        _require_keys(
            mapping,
            [
                "mapping_version",
                "acid_flow_min",
                "acid_flow_max",
                "acetate_flow_min",
                "acetate_flow_max",
                "water_flow_min",
                "water_flow_max",
                "buffer_flow_sum_min",
                "buffer_flow_sum_max",
                "fixed_water_flow",
            ],
            "Manifest action_mapping",
        )
        try:
            values = {
                key: (
                    str(mapping[key])
                    if key == "mapping_version"
                    else float(mapping[key])
                )
                for key in cls.__dataclass_fields__
            }
            config = cls(**values)
        except (TypeError, ValueError) as exc:
            raise PolicyBundleError(
                "Manifest action_mapping contains invalid value types."
            ) from exc
        config.validate()
        return config

    def validate(self) -> None:
        values = np.array(
            [
                self.acid_flow_min,
                self.acid_flow_max,
                self.acetate_flow_min,
                self.acetate_flow_max,
                self.water_flow_min,
                self.water_flow_max,
                self.buffer_flow_sum_min,
                self.buffer_flow_sum_max,
                self.fixed_water_flow,
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(values)):
            raise PolicyBundleError("Flow mapping values must all be finite.")
        if self.mapping_version != EXPECTED_MAPPING_VERSION:
            raise PolicyBundleError(
                f"Unsupported action mapping version: {self.mapping_version}"
            )
        if self.acid_flow_min <= 0 or self.acid_flow_min >= self.acid_flow_max:
            raise PolicyBundleError("Invalid acid-flow bounds in manifest.")
        if (
            self.acetate_flow_min <= 0
            or self.acetate_flow_min >= self.acetate_flow_max
        ):
            raise PolicyBundleError("Invalid acetate-flow bounds in manifest.")
        if self.water_flow_min <= 0 or self.water_flow_min >= self.water_flow_max:
            raise PolicyBundleError("Invalid water-flow bounds in manifest.")

        feasible_sum_min = self.acid_flow_min + self.acetate_flow_min
        feasible_sum_max = self.acid_flow_max + self.acetate_flow_max
        if self.buffer_flow_sum_min < feasible_sum_min:
            raise PolicyBundleError("buffer_flow_sum_min is physically infeasible.")
        if self.buffer_flow_sum_max > feasible_sum_max:
            raise PolicyBundleError("buffer_flow_sum_max is physically infeasible.")
        if self.buffer_flow_sum_min >= self.buffer_flow_sum_max:
            raise PolicyBundleError("Invalid acid-plus-acetate sum bounds.")
        if not self.water_flow_min <= self.fixed_water_flow <= self.water_flow_max:
            raise PolicyBundleError("fixed_water_flow is outside water bounds.")


class RatioSumActionMapper:
    """Exact normalized TD3 action mapping used by the offline environment."""

    def __init__(self, config: FlowMappingConfig):
        config.validate()
        self.config = config

    def _acid_bounds_for_sum(self, buffer_sum: float) -> tuple[float, float]:
        total = float(buffer_sum)
        acid_low = max(
            self.config.acid_flow_min,
            total - self.config.acetate_flow_max,
        )
        acid_high = min(
            self.config.acid_flow_max,
            total - self.config.acetate_flow_min,
        )
        if acid_low > acid_high:
            raise ActionMappingError(
                f"Acid-plus-acetate sum {total} is infeasible for pump bounds."
            )
        return float(acid_low), float(acid_high)

    def _ratio_bounds_for_sum(self, buffer_sum: float) -> tuple[float, float]:
        acid_low, acid_high = self._acid_bounds_for_sum(buffer_sum)
        total = float(buffer_sum)
        ratio_low = (total - acid_high) / acid_high
        ratio_high = (total - acid_low) / acid_low
        return float(ratio_low), float(ratio_high)

    def action_to_flows(self, action: Sequence[float]) -> LogicalFlows:
        """Map `[ratio_action, sum_action]` from `[-1,1]^2` to flows."""

        action_array = np.asarray(action, dtype=np.float32).reshape(-1)
        if action_array.shape != (2,):
            raise ActionMappingError(
                f"TD3 action must have shape (2,), got {action_array.shape}."
            )
        if not np.all(np.isfinite(action_array)):
            raise ActionMappingError("TD3 action contains NaN or infinity.")
        if np.any(np.abs(action_array) > 1.0 + 1.0e-6):
            raise ActionMappingError("TD3 action is materially outside [-1, 1].")
        action_array = np.clip(action_array, -1.0, 1.0)

        sum_fraction = float(0.5 * (action_array[1] + 1.0))
        buffer_sum = float(
            self.config.buffer_flow_sum_min
            + sum_fraction
            * (
                self.config.buffer_flow_sum_max
                - self.config.buffer_flow_sum_min
            )
        )

        ratio_low, ratio_high = self._ratio_bounds_for_sum(buffer_sum)
        log_ratio_low = float(np.log10(ratio_low))
        log_ratio_high = float(np.log10(ratio_high))
        ratio_fraction = float(0.5 * (action_array[0] + 1.0))
        log_ratio = log_ratio_low + ratio_fraction * (
            log_ratio_high - log_ratio_low
        )
        ratio = float(10.0**log_ratio)

        acid_flow = float(buffer_sum / (1.0 + ratio))
        acid_low, acid_high = self._acid_bounds_for_sum(buffer_sum)
        acid_flow = float(np.clip(acid_flow, acid_low, acid_high))
        acetate_flow = float(buffer_sum - acid_flow)
        flows = LogicalFlows(
            acid_flow=acid_flow,
            acetate_flow=acetate_flow,
            water_flow=float(self.config.fixed_water_flow),
        )
        self.validate_flows(flows, require_fixed_water=True)
        return flows

    def flows_to_action(
        self,
        flows: LogicalFlows,
        *,
        water_tolerance: float = 1.0e-3,
    ) -> np.ndarray:
        """Recover the normalized previous action from verified flow readback."""

        self.validate_flows(flows, require_fixed_water=False)
        if abs(flows.water_flow - self.config.fixed_water_flow) > water_tolerance:
            raise ActionMappingError(
                "Live water flow does not match the fixed-water TD3 contract."
            )

        buffer_sum = flows.buffer_flow_sum
        if not (
            self.config.buffer_flow_sum_min
            <= buffer_sum
            <= self.config.buffer_flow_sum_max
        ):
            raise ActionMappingError(
                "Live acid-plus-acetate sum is outside the TD3 mapping bounds."
            )
        sum_span = (
            self.config.buffer_flow_sum_max
            - self.config.buffer_flow_sum_min
        )
        sum_action = (
            2.0
            * (buffer_sum - self.config.buffer_flow_sum_min)
            / sum_span
            - 1.0
        )

        ratio = float(flows.acetate_flow / flows.acid_flow)
        ratio_low, ratio_high = self._ratio_bounds_for_sum(buffer_sum)
        log_low = float(np.log10(ratio_low))
        log_high = float(np.log10(ratio_high))
        log_ratio = float(np.log10(np.clip(ratio, ratio_low, ratio_high)))
        log_span = log_high - log_low
        ratio_action = (
            0.0
            if abs(log_span) <= 1.0e-12
            else 2.0 * (log_ratio - log_low) / log_span - 1.0
        )
        return np.array(
            [
                np.clip(ratio_action, -1.0, 1.0),
                np.clip(sum_action, -1.0, 1.0),
            ],
            dtype=np.float32,
        )

    def validate_flows(
        self,
        flows: LogicalFlows,
        *,
        require_fixed_water: bool,
    ) -> None:
        values = np.array(
            [flows.acid_flow, flows.acetate_flow, flows.water_flow],
            dtype=float,
        )
        if not np.all(np.isfinite(values)):
            raise ActionMappingError("Physical flows contain NaN or infinity.")
        if not self.config.acid_flow_min <= flows.acid_flow <= self.config.acid_flow_max:
            raise ActionMappingError("Acid flow is outside manifest bounds.")
        if not (
            self.config.acetate_flow_min
            <= flows.acetate_flow
            <= self.config.acetate_flow_max
        ):
            raise ActionMappingError("Acetate flow is outside manifest bounds.")
        if not self.config.water_flow_min <= flows.water_flow <= self.config.water_flow_max:
            raise ActionMappingError("Water flow is outside manifest bounds.")
        if require_fixed_water and not np.isclose(
            flows.water_flow,
            self.config.fixed_water_flow,
            atol=1.0e-6,
        ):
            raise ActionMappingError("TD3 proposal changed the fixed water flow.")


class FrozenTD3Policy:
    """Actor-only custom TD3 policy loaded from a verified deployment bundle."""

    def __init__(
        self,
        actor: Actor,
        manifest: dict[str, Any],
        manifest_path: Path,
    ):
        self.actor = actor
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.manifest_sha256 = sha256_file(manifest_path)
        self.flow_mapping = FlowMappingConfig.from_manifest(manifest)

    @classmethod
    def load(
        cls,
        manifest_path: str | Path,
        *,
        device: str | torch.device = "cpu",
    ) -> "FrozenTD3Policy":
        """Load, hash-check, reconstruct, and golden-test the frozen actor."""

        manifest_file = Path(manifest_path).resolve()
        if not manifest_file.is_file():
            raise PolicyBundleError(f"Policy manifest not found: {manifest_file}")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PolicyBundleError("Policy manifest is not valid JSON.") from exc
        if not isinstance(manifest, dict):
            raise PolicyBundleError("Policy manifest must contain a JSON object.")

        _require_keys(
            manifest,
            [
                "schema_version",
                "algorithm",
                "policy_id",
                "weights_file",
                "weights_format",
                "weights_sha256",
                "state_dim",
                "state_dtype",
                "state_scaling",
                "controlled_measurement",
                "error_definition",
                "state_variables",
                "state_bounds",
                "action_dim",
                "action_dtype",
                "action_semantics",
                "action_variables",
                "action_bounds",
                "actor",
                "action_mapping",
                "target_ph_bounds",
                "golden_tolerance",
                "golden_cases",
            ],
            "Policy manifest",
        )
        if manifest["schema_version"] != 1:
            raise PolicyBundleError("Unsupported policy manifest schema version.")
        if manifest["algorithm"] != "custom_td3":
            raise PolicyBundleError("Policy manifest does not describe custom TD3.")
        if manifest["weights_format"] != "pytorch_state_dict_weights_only":
            raise PolicyBundleError("Policy weights format is not approved.")
        if manifest["state_dtype"] != "float32" or manifest["action_dtype"] != "float32":
            raise PolicyBundleError("Policy state/action dtype must be float32.")
        if manifest["state_scaling"] != "none":
            raise PolicyBundleError("Policy state scaling is incompatible.")
        if manifest["controlled_measurement"] != "PH_2":
            raise PolicyBundleError("Policy must use PH_2 as its controlled measurement.")
        if manifest["error_definition"] != "current_ph_minus_target_ph":
            raise PolicyBundleError("Policy pH-error definition is incompatible.")
        if manifest["action_semantics"] != "normalized_ratio_and_buffer_flow_sum":
            raise PolicyBundleError("Policy action semantics are incompatible.")
        if manifest["state_dim"] != 5 or manifest["action_dim"] != 2:
            raise PolicyBundleError("Policy manifest has wrong state/action dimensions.")
        if manifest["state_variables"] != EXPECTED_STATE_VARIABLES:
            raise PolicyBundleError("Policy state variable order is incompatible.")
        if manifest["action_variables"] != EXPECTED_ACTION_VARIABLES:
            raise PolicyBundleError("Policy action variable order is incompatible.")
        try:
            state_bounds = np.asarray(manifest["state_bounds"], dtype=float)
            action_bounds = np.asarray(manifest["action_bounds"], dtype=float)
        except (TypeError, ValueError) as exc:
            raise PolicyBundleError("Policy bounds must be numeric.") from exc
        if (
            state_bounds.shape != (5, 2)
            or not np.all(np.isfinite(state_bounds))
            or np.any(state_bounds[:, 0] >= state_bounds[:, 1])
        ):
            raise PolicyBundleError("Policy state bounds are invalid.")
        if not np.array_equal(
            action_bounds,
            np.array([[-1.0, 1.0], [-1.0, 1.0]]),
        ):
            raise PolicyBundleError("Policy action bounds must be [-1,1]^2.")
        if not np.array_equal(state_bounds[3:], action_bounds):
            raise PolicyBundleError("Previous-action state bounds are incompatible.")
        target_bounds = np.asarray(manifest["target_ph_bounds"], dtype=float)
        if target_bounds.shape != (2,) or not np.array_equal(
            state_bounds[1],
            target_bounds,
        ):
            raise PolicyBundleError("Target-pH bounds disagree within the manifest.")
        expected_error_bounds = np.array(
            [
                state_bounds[0, 0] - state_bounds[1, 1],
                state_bounds[0, 1] - state_bounds[1, 0],
            ]
        )
        if not np.allclose(state_bounds[2], expected_error_bounds, atol=1.0e-9):
            raise PolicyBundleError("Policy pH-error bounds are inconsistent.")

        actor_config = manifest["actor"]
        if not isinstance(actor_config, Mapping):
            raise PolicyBundleError("Manifest actor field must be an object.")
        _require_keys(
            actor_config,
            [
                "state_dim",
                "action_dim",
                "hidden_dims",
                "activation",
                "use_layernorm",
                "dropout",
                "max_action",
                "squash",
            ],
            "Manifest actor",
        )
        if actor_config["state_dim"] != 5 or actor_config["action_dim"] != 2:
            raise PolicyBundleError("Actor dimensions disagree with pH TD3 contract.")
        hidden_dims = actor_config["hidden_dims"]
        if (
            not isinstance(hidden_dims, list)
            or not hidden_dims
            or any(type(value) is not int or value <= 0 for value in hidden_dims)
        ):
            raise PolicyBundleError("Actor hidden dimensions are invalid.")
        if str(actor_config["squash"]).lower() != "tanh":
            raise PolicyBundleError("Deployment actor must use tanh output squashing.")
        try:
            max_action = float(actor_config["max_action"])
            golden_tolerance = float(manifest["golden_tolerance"])
        except (TypeError, ValueError) as exc:
            raise PolicyBundleError("Actor or golden numeric metadata is invalid.") from exc
        if not np.isclose(max_action, 1.0):
            raise PolicyBundleError("Deployment actor maximum action must equal one.")
        if (
            not np.isfinite(golden_tolerance)
            or golden_tolerance <= 0
            or golden_tolerance > 1.0e-5
        ):
            raise PolicyBundleError("Policy golden tolerance is invalid.")

        # Validate the flow mapping before touching model weights.
        FlowMappingConfig.from_manifest(manifest)

        weights_name = Path(str(manifest["weights_file"]))
        if weights_name.is_absolute() or weights_name.name != str(weights_name):
            raise PolicyBundleError("Actor weights must be inside the policy bundle.")
        weights_path = (manifest_file.parent / weights_name).resolve()
        if not weights_path.is_file():
            raise PolicyBundleError(f"Actor weights not found: {weights_path}")
        actual_hash = sha256_file(weights_path)
        expected_hash = str(manifest["weights_sha256"]).lower()
        if actual_hash != expected_hash:
            raise PolicyBundleError(
                "Actor weight SHA-256 does not match the policy manifest."
            )
        if manifest["policy_id"] != f"custom_td3_{actual_hash[:16]}":
            raise PolicyBundleError("Policy ID does not match the actor weight hash.")

        try:
            torch_device = torch.device(device)
        except (RuntimeError, TypeError) as exc:
            raise PolicyBundleError("Policy device is invalid.") from exc
        try:
            # Use an already-open stream for reliable Windows/OneDrive path
            # handling; weights_only=True still blocks general pickle objects.
            with weights_path.open("rb") as stream:
                state_dict = torch.load(
                    stream,
                    map_location=torch_device,
                    weights_only=True,
                )
        except Exception as exc:
            raise PolicyBundleError("Could not load actor weights safely.") from exc
        if not isinstance(state_dict, Mapping):
            raise PolicyBundleError("Actor weight file must contain a state dictionary.")
        for name, tensor in state_dict.items():
            if not isinstance(name, str) or not isinstance(tensor, torch.Tensor):
                raise PolicyBundleError("Actor state dictionary has invalid entries.")
            if not torch.isfinite(tensor).all():
                raise PolicyBundleError(f"Actor tensor {name!r} is not finite.")

        try:
            actor = Actor(
                state_dim=5,
                action_dim=2,
                hidden_dims=hidden_dims,
                activation=str(actor_config["activation"]),
                use_layernorm=bool(actor_config["use_layernorm"]),
                dropout=float(actor_config["dropout"]),
                max_action=float(actor_config["max_action"]),
                squash=str(actor_config["squash"]),
            ).to(torch_device)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            raise PolicyBundleError("Actor architecture is invalid.") from exc
        try:
            actor.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise PolicyBundleError(
                "Actor weights do not match the declared architecture."
            ) from exc
        actor.eval()
        actor.requires_grad_(False)

        policy = cls(actor=actor, manifest=manifest, manifest_path=manifest_file)
        policy._verify_golden_cases()
        return policy

    @property
    def target_ph_bounds(self) -> tuple[float, float]:
        low, high = self.manifest["target_ph_bounds"]
        return float(low), float(high)

    @property
    def source_metadata(self) -> dict[str, Any]:
        source = self.manifest.get("source", {})
        return dict(source) if isinstance(source, Mapping) else {}

    def _verify_golden_cases(self) -> None:
        cases = self.manifest["golden_cases"]
        if not isinstance(cases, list) or len(cases) < 3:
            raise PolicyBundleError("Policy manifest requires at least three golden cases.")
        tolerance = float(self.manifest["golden_tolerance"])
        for index, case in enumerate(cases):
            if not isinstance(case, Mapping):
                raise PolicyBundleError("Golden policy case must be an object.")
            expected = np.asarray(case.get("expected_action"), dtype=np.float32)
            actual = self.predict(case.get("state"), validate_bounds=True)
            if expected.shape != (2,) or not np.allclose(
                actual,
                expected,
                atol=tolerance,
                rtol=0.0,
            ):
                raise PolicyBundleError(
                    f"Actor golden inference case {index} did not match."
                )

    def predict(
        self,
        state: Sequence[float],
        *,
        validate_bounds: bool = True,
    ) -> np.ndarray:
        """Return one deterministic normalized TD3 action."""

        state_array = np.asarray(state, dtype=np.float32).reshape(-1)
        if state_array.shape != (5,):
            raise PolicyInputError(
                f"TD3 state must have shape (5,), got {state_array.shape}."
            )
        if not np.all(np.isfinite(state_array)):
            raise PolicyInputError("TD3 state contains NaN or infinity.")
        if validate_bounds:
            bounds = np.asarray(self.manifest["state_bounds"], dtype=float)
            if bounds.shape != (5, 2):
                raise PolicyBundleError("Manifest state bounds must have shape (5,2).")
            below = state_array < bounds[:, 0] - 1.0e-6
            above = state_array > bounds[:, 1] + 1.0e-6
            if np.any(below | above):
                raise PolicyInputError("TD3 state is outside manifest bounds.")

        device = next(self.actor.parameters()).device
        with torch.inference_mode():
            state_tensor = torch.as_tensor(state_array, device=device).reshape(1, -1)
            action = self.actor(state_tensor).cpu().numpy().reshape(-1)
        if action.shape != (2,) or not np.all(np.isfinite(action)):
            raise PolicyInputError("TD3 actor returned an invalid action.")
        if np.any(np.abs(action) > 1.0 + 1.0e-6):
            raise PolicyInputError("TD3 actor returned an action outside [-1,1].")
        return np.clip(action, -1.0, 1.0).astype(np.float32)


def build_td3_state(
    measured_ph: float,
    target_ph: float,
    verified_flows: LogicalFlows,
    mapper: RatioSumActionMapper,
) -> np.ndarray:
    """Build the exact state used during current pH TD3 training."""

    ph = float(measured_ph)
    target = float(target_ph)
    if not np.isfinite([ph, target]).all():
        raise PolicyInputError("Measured and target pH must be finite.")
    previous_action = mapper.flows_to_action(verified_flows)
    return np.array(
        [ph, target, ph - target, previous_action[0], previous_action[1]],
        dtype=np.float32,
    )


def validate_pump_map(
    pump_map: Mapping[str, int],
    *,
    pump_count: int = 7,
) -> dict[str, int]:
    """Validate logical stream names and unique one-indexed pump numbers."""

    required = ["acid", "acetate", "water"]
    if sorted(pump_map.keys()) != sorted(required):
        raise ActionMappingError(f"Pump map must contain exactly {required}.")
    normalized = {name: int(pump_map[name]) for name in required}
    values = list(normalized.values())
    if len(set(values)) != len(values):
        raise ActionMappingError("Each logical stream must use a different pump.")
    if any(number < 1 or number > pump_count for number in values):
        raise ActionMappingError(f"Pump numbers must be inside 1..{pump_count}.")
    return normalized


def extract_logical_flows(
    pump_flows: Sequence[float],
    pump_map: Mapping[str, int],
) -> LogicalFlows:
    """Extract acid, acetate, and water from a physical pump array."""

    flow_array = np.asarray(pump_flows, dtype=float).reshape(-1)
    mapping = validate_pump_map(pump_map, pump_count=flow_array.size)
    if not np.all(np.isfinite(flow_array)):
        raise ActionMappingError("Pump-flow readback contains NaN or infinity.")
    return LogicalFlows(
        acid_flow=float(flow_array[mapping["acid"] - 1]),
        acetate_flow=float(flow_array[mapping["acetate"] - 1]),
        water_flow=float(flow_array[mapping["water"] - 1]),
    )


def logical_flows_to_pump_array(
    logical_flows: LogicalFlows,
    current_pump_flows: Sequence[float],
    pump_map: Mapping[str, int],
) -> list[float]:
    """Merge a logical action into a seven-pump array without changing others."""

    pump_array = np.asarray(current_pump_flows, dtype=float).reshape(-1).copy()
    mapping = validate_pump_map(pump_map, pump_count=pump_array.size)
    if not np.all(np.isfinite(pump_array)):
        raise ActionMappingError("Current pump array contains NaN or infinity.")
    pump_array[mapping["acid"] - 1] = logical_flows.acid_flow
    pump_array[mapping["acetate"] - 1] = logical_flows.acetate_flow
    pump_array[mapping["water"] - 1] = logical_flows.water_flow
    return pump_array.astype(float).tolist()


def validate_flow_transition(
    proposed: LogicalFlows,
    previous: LogicalFlows,
    mapper: RatioSumActionMapper,
    *,
    max_step_change: float,
    max_total_flow: float,
) -> tuple[bool, str]:
    """Apply deployment-only flow and slew checks to one TD3 proposal."""

    try:
        mapper.validate_flows(proposed, require_fixed_water=True)
    except ActionMappingError as exc:
        return False, str(exc)
    if proposed.total_flow > float(max_total_flow):
        return False, "Proposed total flow exceeds deployment limit."
    step_changes = np.abs(
        np.array(
            [
                proposed.acid_flow - previous.acid_flow,
                proposed.acetate_flow - previous.acetate_flow,
                proposed.water_flow - previous.water_flow,
            ],
            dtype=float,
        )
    )
    if np.any(step_changes > float(max_step_change) + 1.0e-9):
        return False, "Proposed pump step exceeds deployment slew limit."
    return True, "valid"
