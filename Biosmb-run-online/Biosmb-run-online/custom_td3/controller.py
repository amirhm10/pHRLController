"""Compatibility facade for later use by the original BioSMB main file."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import (
    LogicalFlows,
    TD3ContractError,
    build_td3_state,
    format_biosmb_action,
    format_logical_flows,
    logical_flows_from_formatted_action,
)
from .policy import TD3Policy


class BioSMBTD3Policy:
    """Small TD3 API designed around the original BioSMB action dictionary.

    The class performs no OPC-UA, Redis, MongoDB, or pump writes. It only loads
    the actor, constructs its state, predicts normalized actions, and formats
    logical flows for the existing main-file helpers.
    """

    def __init__(
        self,
        policy: TD3Policy,
        *,
        controlled_flow_indices: Sequence[int] = (0, 1, 2),
        controlled_stream_names: Mapping[int, str] | None = None,
        state_sensor_key: str = "PH_2",
        pump_count: int = 7,
    ) -> None:
        indices = tuple(int(value) for value in controlled_flow_indices)
        if len(indices) != 3 or len(set(indices)) != 3:
            raise TD3ContractError(
                "BioSMB TD3 requires three unique controlled flow indices."
            )
        if any(index < 0 or index >= pump_count for index in indices):
            raise TD3ContractError("Controlled flow index is outside pump array.")
        self.policy = policy
        self.controlled_flow_indices = indices
        self.controlled_stream_names = controlled_stream_names or {
            indices[0]: "acetic-acid",
            indices[1]: "sodium-acetate",
            indices[2]: "di-water",
        }
        self.state_sensor_key = str(state_sensor_key)
        self.pump_count = int(pump_count)

    @classmethod
    def load(
        cls,
        manifest_path: str | Path,
        *,
        controlled_flow_indices: Sequence[int] = (0, 1, 2),
        controlled_stream_names: Mapping[int, str] | None = None,
        state_sensor_key: str = "PH_2",
        pump_count: int = 7,
        device: str = "cpu",
    ) -> "BioSMBTD3Policy":
        """Load a verified actor and its BioSMB compatibility settings."""

        return cls(
            TD3Policy.load(manifest_path, device=device),
            controlled_flow_indices=controlled_flow_indices,
            controlled_stream_names=controlled_stream_names,
            state_sensor_key=state_sensor_key,
            pump_count=pump_count,
        )

    @property
    def manifest(self) -> dict[str, Any]:
        return self.policy.manifest

    def _flows_from_observation(self, observation: Mapping[str, Any]) -> LogicalFlows:
        """Read current logical flows from the original seven-pump observation."""

        try:
            pump_flows = np.asarray(
                observation["biosmb-flows"],
                dtype=float,
            ).reshape(-1)
        except (KeyError, TypeError, ValueError) as exc:
            raise TD3ContractError(
                "Observation does not contain a valid biosmb-flows array."
            ) from exc
        if pump_flows.shape != (self.pump_count,) or not np.all(
            np.isfinite(pump_flows)
        ):
            raise TD3ContractError(
                f"biosmb-flows must contain {self.pump_count} finite values."
            )
        values = [float(pump_flows[index]) for index in self.controlled_flow_indices]
        return LogicalFlows(*values)

    def build_state(
        self,
        observation: Mapping[str, Any],
        target_ph: float,
        previous_executed_action: Mapping[str, Any] | None = None,
    ) -> np.ndarray:
        """Build the custom TD3 state from the original observation structure.

        Current pump readback is preferred because it represents the physical
        state. The previous action dictionary is only a fallback when the
        observation has no flow array.
        """

        try:
            measured_ph = float(
                observation["biosmb-sensors"][self.state_sensor_key]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TD3ContractError(
                f"Observation does not contain a valid {self.state_sensor_key}."
            ) from exc

        if "biosmb-flows" in observation:
            previous_flows = self._flows_from_observation(observation)
        elif previous_executed_action is not None:
            previous_flows = logical_flows_from_formatted_action(
                previous_executed_action
            )
        else:
            raise TD3ContractError(
                "State construction requires flow readback or a previous action."
            )
        state = build_td3_state(
            measured_ph,
            target_ph,
            previous_flows,
            self.policy.mapper,
        )
        return self.policy.validate_state(state)

    def predict(
        self,
        state: Sequence[float],
        *,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, None]:
        """Expose the same prediction call shape as the original SAC model."""

        return self.policy.predict(state, deterministic=deterministic)

    def format_action(self, normalized_action: Sequence[float]) -> dict[str, Any]:
        """Convert the two TD3 actions to the original action dictionary."""

        return format_biosmb_action(
            normalized_action,
            self.policy.mapper,
            controlled_flow_indices=self.controlled_flow_indices,
            controlled_stream_names=self.controlled_stream_names,
            pump_count=self.pump_count,
        )

    def default_action(self) -> dict[str, Any]:
        """Return a manifest-compatible 5/5/5 mL/min startup representation."""

        flows = LogicalFlows(
            acid_flow=5.0,
            acetate_flow=5.0,
            water_flow=self.policy.flow_mapping.fixed_water_flow,
        )
        self.policy.mapper.validate_flows(flows)
        return format_logical_flows(
            flows,
            raw_action=self.policy.mapper.flows_to_action(flows),
            controlled_flow_indices=self.controlled_flow_indices,
            controlled_stream_names=self.controlled_stream_names,
            pump_count=self.pump_count,
        )
