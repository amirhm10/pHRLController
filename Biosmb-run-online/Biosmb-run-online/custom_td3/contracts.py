"""Pure state and action contracts for the custom pH TD3 actor.

This module has no BioSMB or database dependency. It translates between the
five-element TD3 state, the two normalized actor outputs, and the physical
acid, acetate, and Arium-water flow representation used by the lab script.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


STATE_VARIABLES = (
    "current_ph",
    "target_ph",
    "current_ph_minus_target_ph",
    "normalized_ratio_action",
    "normalized_optional_flow_action",
)

ACTION_VARIABLES = (
    "normalized_acetate_acid_ratio",
    "normalized_optional_total_flow_fraction",
)

MAPPING_VERSION = "ratio_preserving_flow_v1"


class TD3ContractError(ValueError):
    """Raised when state, action, flow, or mapping data are incompatible."""


@dataclass(frozen=True)
class LogicalFlows:
    """Logical process streams independent of physical pump numbering."""

    acid_flow: float
    acetate_flow: float
    water_flow: float

    @property
    def buffer_flow_sum(self) -> float:
        return float(self.acid_flow + self.acetate_flow)

    @property
    def total_flow(self) -> float:
        return float(self.buffer_flow_sum + self.water_flow)

    def as_list(self) -> list[float]:
        return [
            float(self.acid_flow),
            float(self.acetate_flow),
            float(self.water_flow),
        ]


@dataclass(frozen=True)
class FlowMapping:
    """Manifest parameters for ratio-preserving action conversion."""

    acid_flow_min: float
    acid_flow_max: float
    acetate_flow_min: float
    acetate_flow_max: float
    water_flow_min: float
    water_flow_max: float
    buffer_flow_sum_min: float
    buffer_flow_sum_max: float
    fixed_water_flow: float
    mapping_version: str = MAPPING_VERSION

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> "FlowMapping":
        """Create and validate the mapping stored in a policy manifest."""

        raw = manifest.get("action_mapping")
        if not isinstance(raw, Mapping):
            raise TD3ContractError("Manifest action_mapping must be an object.")
        required = set(cls.__dataclass_fields__)
        missing = sorted(required.difference(raw))
        if missing:
            raise TD3ContractError(
                f"Manifest action_mapping is missing fields: {missing}."
            )
        try:
            values = {
                name: (
                    str(raw[name])
                    if name == "mapping_version"
                    else float(raw[name])
                )
                for name in cls.__dataclass_fields__
            }
        except (TypeError, ValueError) as exc:
            raise TD3ContractError("Action-mapping values must be numeric.") from exc
        mapping = cls(**values)
        mapping.validate()
        return mapping

    def validate(self) -> None:
        """Check mapping version, finite values, and physical feasibility."""

        numeric = np.asarray(
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
        if not np.all(np.isfinite(numeric)):
            raise TD3ContractError("Flow-mapping values must be finite.")
        if self.mapping_version != MAPPING_VERSION:
            raise TD3ContractError(
                f"Unsupported action mapping {self.mapping_version!r}."
            )
        if self.acid_flow_min <= 0 or self.acid_flow_min >= self.acid_flow_max:
            raise TD3ContractError("Acid-flow bounds are invalid.")
        if (
            self.acetate_flow_min <= 0
            or self.acetate_flow_min >= self.acetate_flow_max
        ):
            raise TD3ContractError("Acetate-flow bounds are invalid.")
        if self.water_flow_min <= 0 or self.water_flow_min >= self.water_flow_max:
            raise TD3ContractError("Water-flow bounds are invalid.")
        feasible_sum_min = self.acid_flow_min + self.acetate_flow_min
        feasible_sum_max = self.acid_flow_max + self.acetate_flow_max
        if not (
            feasible_sum_min
            <= self.buffer_flow_sum_min
            < self.buffer_flow_sum_max
            <= feasible_sum_max
        ):
            raise TD3ContractError("Buffer-flow-sum bounds are infeasible.")
        if not self.water_flow_min <= self.fixed_water_flow <= self.water_flow_max:
            raise TD3ContractError("Fixed water flow is outside its bounds.")


class RatioSumActionMapper:
    """Exact mapper used by the offline `ratio_preserving_flow` environment."""

    def __init__(self, mapping: FlowMapping):
        mapping.validate()
        self.mapping = mapping

    def _global_ratio_bounds(self) -> tuple[float, float]:
        ratio_low = self.mapping.acetate_flow_min / self.mapping.acid_flow_max
        ratio_high = self.mapping.acetate_flow_max / self.mapping.acid_flow_min
        return float(ratio_low), float(ratio_high)

    def _sum_bounds_for_ratio(self, ratio: float) -> tuple[float, float]:
        ratio = float(ratio)
        if not np.isfinite(ratio) or ratio <= 0.0:
            raise TD3ContractError("Flow ratio must be finite and positive.")
        one_plus_ratio = 1.0 + ratio
        sum_low = max(
            self.mapping.buffer_flow_sum_min,
            self.mapping.acid_flow_min * one_plus_ratio,
            self.mapping.acetate_flow_min * one_plus_ratio / ratio,
        )
        sum_high = min(
            self.mapping.buffer_flow_sum_max,
            self.mapping.acid_flow_max * one_plus_ratio,
            self.mapping.acetate_flow_max * one_plus_ratio / ratio,
        )
        if sum_low > sum_high + 1.0e-10:
            raise TD3ContractError(
                "Selected flow ratio has no feasible total-flow interval."
            )
        if sum_low > sum_high:
            midpoint = 0.5 * (sum_low + sum_high)
            sum_low = midpoint
            sum_high = midpoint
        return float(sum_low), float(sum_high)

    def action_to_flows(self, action: Sequence[float]) -> LogicalFlows:
        """Convert `[global ratio, optional flow]` to three logical flows."""

        values = np.asarray(action, dtype=np.float32).reshape(-1)
        if values.shape != (2,):
            raise TD3ContractError(
                f"TD3 action must have shape (2,), received {values.shape}."
            )
        if not np.all(np.isfinite(values)):
            raise TD3ContractError("TD3 action contains NaN or infinity.")
        if np.any(np.abs(values) > 1.0 + 1.0e-6):
            raise TD3ContractError("TD3 action is outside normalized bounds.")
        ratio_action, optional_flow_action = np.clip(values, -1.0, 1.0)

        ratio_low, ratio_high = self._global_ratio_bounds()
        log_low = float(np.log10(ratio_low))
        log_high = float(np.log10(ratio_high))
        ratio_fraction = float(0.5 * (ratio_action + 1.0))
        ratio = float(
            10.0 ** (log_low + ratio_fraction * (log_high - log_low))
        )
        sum_low, sum_high = self._sum_bounds_for_ratio(ratio)
        optional_flow_fraction = float(0.5 * (optional_flow_action + 1.0))
        buffer_sum = float(
            sum_low + optional_flow_fraction * (sum_high - sum_low)
        )

        acid_flow = float(buffer_sum / (1.0 + ratio))
        flow_values = np.asarray(
            [acid_flow, ratio * acid_flow, self.mapping.fixed_water_flow],
            dtype=np.float32,
        )
        flows = LogicalFlows(*flow_values.astype(float).tolist())
        self.validate_flows(flows)
        return flows

    def flows_to_action(
        self,
        flows: LogicalFlows,
        *,
        water_tolerance: float = 0.1,
        enforce_water_tolerance: bool = True,
    ) -> np.ndarray:
        """Recover the previous normalized action from physical flow values."""

        self.validate_flows(flows, require_fixed_water=False)
        if (
            enforce_water_tolerance
            and abs(flows.water_flow - self.mapping.fixed_water_flow)
            > water_tolerance
        ):
            raise TD3ContractError(
                "Water flow does not match the fixed-water TD3 contract."
            )
        buffer_sum = flows.buffer_flow_sum
        if not (
            self.mapping.buffer_flow_sum_min
            <= buffer_sum
            <= self.mapping.buffer_flow_sum_max
        ):
            raise TD3ContractError("Buffer-flow sum is outside TD3 bounds.")

        ratio = float(flows.acetate_flow / flows.acid_flow)
        ratio_low, ratio_high = self._global_ratio_bounds()
        log_low = float(np.log10(ratio_low))
        log_high = float(np.log10(ratio_high))
        log_span = log_high - log_low
        if abs(log_span) <= 1.0e-12:
            ratio_action = 0.0
        else:
            log_ratio = float(np.log10(np.clip(ratio, ratio_low, ratio_high)))
            ratio_action = 2.0 * (log_ratio - log_low) / log_span - 1.0
        sum_low, sum_high = self._sum_bounds_for_ratio(ratio)
        if not sum_low - 1.0e-6 <= buffer_sum <= sum_high + 1.0e-6:
            raise TD3ContractError(
                "Buffer-flow sum is outside the selected ratio's feasible interval."
            )
        sum_span = sum_high - sum_low
        if sum_span <= 1.0e-12:
            optional_flow_action = -1.0
        else:
            optional_flow_action = (
                2.0 * (buffer_sum - sum_low) / sum_span - 1.0
            )
        return np.asarray(
            [
                np.clip(ratio_action, -1.0, 1.0),
                np.clip(optional_flow_action, -1.0, 1.0),
            ],
            dtype=np.float32,
        )

    def economic_flow_fraction(self, flows: LogicalFlows) -> float:
        """Return the optional fraction above the ratio-specific minimum."""

        normalized_action = self.flows_to_action(
            flows,
            enforce_water_tolerance=False,
        )
        return float(np.clip(0.5 * (normalized_action[1] + 1.0), 0.0, 1.0))

    def validate_flows(
        self,
        flows: LogicalFlows,
        *,
        require_fixed_water: bool = True,
    ) -> None:
        """Validate one logical physical-flow triplet."""

        values = np.asarray(flows.as_list(), dtype=float)
        if not np.all(np.isfinite(values)):
            raise TD3ContractError("Physical flows contain NaN or infinity.")
        if not self.mapping.acid_flow_min <= flows.acid_flow <= self.mapping.acid_flow_max:
            raise TD3ContractError("Acid flow is outside manifest bounds.")
        if not (
            self.mapping.acetate_flow_min
            <= flows.acetate_flow
            <= self.mapping.acetate_flow_max
        ):
            raise TD3ContractError("Acetate flow is outside manifest bounds.")
        if not self.mapping.water_flow_min <= flows.water_flow <= self.mapping.water_flow_max:
            raise TD3ContractError("Water flow is outside manifest bounds.")
        if require_fixed_water and not np.isclose(
            flows.water_flow,
            self.mapping.fixed_water_flow,
            atol=1.0e-6,
        ):
            raise TD3ContractError("TD3 action changed the fixed water flow.")


def build_td3_state(
    measured_ph: float,
    target_ph: float,
    previous_flows: LogicalFlows,
    mapper: RatioSumActionMapper,
    *,
    water_tolerance: float = 0.1,
    enforce_water_tolerance: bool = False,
) -> np.ndarray:
    """Build the exact five-element state used during offline TD3 training."""

    ph = float(measured_ph)
    target = float(target_ph)
    if not np.all(np.isfinite([ph, target])):
        raise TD3ContractError("Measured and target pH must be finite.")
    previous_action = mapper.flows_to_action(
        previous_flows,
        water_tolerance=water_tolerance,
        enforce_water_tolerance=enforce_water_tolerance,
    )
    return np.asarray(
        [ph, target, ph - target, previous_action[0], previous_action[1]],
        dtype=np.float32,
    )


def logical_flows_from_formatted_action(action: Mapping[str, Any]) -> LogicalFlows:
    """Read logical flows from the original BioSMB action dictionary schema."""

    try:
        values = np.asarray(action["controlled_flow_rates"], dtype=float).reshape(-1)
    except (KeyError, TypeError, ValueError) as exc:
        raise TD3ContractError(
            "Action must contain three controlled_flow_rates."
        ) from exc
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise TD3ContractError("controlled_flow_rates must have three finite values.")
    return LogicalFlows(*values.astype(float).tolist())


def format_biosmb_action(
    normalized_action: Sequence[float],
    mapper: RatioSumActionMapper,
    *,
    controlled_flow_indices: Sequence[int] = (0, 1, 2),
    controlled_stream_names: Mapping[int, str] | None = None,
    pump_count: int = 7,
) -> dict[str, Any]:
    """Return the action dictionary already expected by the original main file."""

    raw_action = np.asarray(normalized_action, dtype=np.float32).reshape(-1)
    flows = mapper.action_to_flows(raw_action)
    return format_logical_flows(
        flows,
        raw_action=raw_action,
        controlled_flow_indices=controlled_flow_indices,
        controlled_stream_names=controlled_stream_names,
        pump_count=pump_count,
    )


def format_logical_flows(
    flows: LogicalFlows,
    *,
    raw_action: Sequence[float] | None,
    controlled_flow_indices: Sequence[int] = (0, 1, 2),
    controlled_stream_names: Mapping[int, str] | None = None,
    pump_count: int = 7,
) -> dict[str, Any]:
    """Format known logical flows without rerunning the normalized mapper."""

    indices = tuple(int(value) for value in controlled_flow_indices)
    if len(indices) != 3 or len(set(indices)) != 3:
        raise TD3ContractError("Exactly three unique controlled indices are required.")
    if any(index < 0 or index >= pump_count for index in indices):
        raise TD3ContractError("Controlled flow index is outside the pump array.")
    names = controlled_stream_names or {
        indices[0]: "acetic-acid",
        indices[1]: "sodium-acetate",
        indices[2]: "di-water",
    }
    if any(index not in names for index in indices):
        raise TD3ContractError("Each controlled index requires a stream name.")

    controlled = flows.as_list()
    pump_flows = [0.0 for _ in range(int(pump_count))]
    for index, value in zip(indices, controlled):
        pump_flows[index] = float(value)
    return {
        "raw_action": (
            None
            if raw_action is None
            else np.asarray(raw_action, dtype=np.float32).reshape(-1).tolist()
        ),
        "controlled_flow_rates": controlled,
        "flow_rates": pump_flows,
        "total_controlled_flow_rate": float(sum(controlled)),
        "stream_flow_rates": {
            str(names[index]): float(pump_flows[index])
            for index in indices
        },
    }
