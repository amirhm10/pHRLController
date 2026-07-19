"""Pure runtime helpers for scheduled targets and frozen TD3 actions."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


class RuntimeModeError(ValueError):
    """Raised when a deployment runtime mode is configured incorrectly."""


def validate_target_ph(
    target_ph: float,
    target_ph_min: float,
    target_ph_max: float,
    *,
    name: str = "target_ph",
) -> float:
    """Return a finite target inside the deployed actor's saved target bounds."""

    value = float(target_ph)
    lower = float(target_ph_min)
    upper = float(target_ph_max)
    if not np.isfinite(value):
        raise RuntimeModeError(f"{name} must be finite.")
    if value < lower or value > upper:
        raise RuntimeModeError(
            f"{name}={value} is outside the deployed target range "
            f"[{lower}, {upper}]."
        )
    return value


class ScheduledSetpointManager:
    """Advance through evenly spaced pH targets using two OR conditions."""

    def __init__(
        self,
        *,
        target_ph_min: float,
        target_ph_max: float,
        setpoint_count: int,
        max_steps_per_setpoint: int,
        consecutive_steps_required: int,
        tolerance: float,
    ) -> None:
        lower = float(target_ph_min)
        upper = float(target_ph_max)
        count = int(setpoint_count)
        max_steps = int(max_steps_per_setpoint)
        consecutive_required = int(consecutive_steps_required)
        tolerance_value = float(tolerance)

        if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
            raise RuntimeModeError(
                "Scheduled target_ph_min must be finite and lower than "
                "target_ph_max."
            )
        if count < 2:
            raise RuntimeModeError("scheduled_setpoint_count must be at least 2.")
        if max_steps <= 0:
            raise RuntimeModeError(
                "scheduled_max_steps_per_setpoint must be positive."
            )
        if consecutive_required <= 0:
            raise RuntimeModeError(
                "scheduled_consecutive_steps_required must be positive."
            )
        if not np.isfinite(tolerance_value) or tolerance_value < 0.0:
            raise RuntimeModeError("target_ph_tolerance must be nonnegative.")

        self.target_values = np.linspace(lower, upper, count, dtype=np.float64)
        forward_indices = np.arange(count, dtype=int)
        reverse_indices = np.arange(count - 2, 0, -1, dtype=int)
        self.cycle_indices = np.concatenate(
            [forward_indices, reverse_indices]
        )
        self.max_steps_per_setpoint = max_steps
        self.consecutive_steps_required = consecutive_required
        self.tolerance = tolerance_value
        self.cycle_position = 0
        self.steps_at_target = 0
        self.consecutive_steps_in_tolerance = 0

    @property
    def current_target_index(self) -> int:
        return int(self.cycle_indices[self.cycle_position])

    @property
    def current_target_ph(self) -> float:
        return float(self.target_values[self.current_target_index])

    def metadata(self) -> dict[str, Any]:
        """Return the immutable schedule definition for logging."""

        return {
            "target_values": self.target_values.tolist(),
            "cycle_indices": self.cycle_indices.tolist(),
            "cycle_mode": "ping_pong",
            "setpoint_count": int(len(self.target_values)),
            "max_steps_per_setpoint": self.max_steps_per_setpoint,
            "consecutive_steps_required": self.consecutive_steps_required,
            "tolerance": self.tolerance,
        }

    def observe(self, measured_ph: float) -> dict[str, Any]:
        """Record one completed control step and possibly advance the target."""

        measured_value = float(measured_ph)
        if not np.isfinite(measured_value):
            raise RuntimeModeError("measured_ph must be finite.")

        target_ph = self.current_target_ph
        target_index = self.current_target_index
        cycle_position = self.cycle_position
        self.steps_at_target += 1
        within_tolerance = abs(measured_value - target_ph) <= self.tolerance
        if within_tolerance:
            self.consecutive_steps_in_tolerance += 1
        else:
            self.consecutive_steps_in_tolerance = 0

        completed_steps = self.steps_at_target
        consecutive_steps = self.consecutive_steps_in_tolerance
        maximum_steps_reached = completed_steps >= self.max_steps_per_setpoint
        consecutive_requirement_reached = (
            consecutive_steps >= self.consecutive_steps_required
        )
        target_changed = maximum_steps_reached or consecutive_requirement_reached

        if maximum_steps_reached and consecutive_requirement_reached:
            change_reason = "maximum_steps_and_consecutive_in_tolerance"
        elif maximum_steps_reached:
            change_reason = "maximum_steps"
        elif consecutive_requirement_reached:
            change_reason = "consecutive_in_tolerance"
        else:
            change_reason = "hold"

        if target_changed:
            self.cycle_position = (self.cycle_position + 1) % len(
                self.cycle_indices
            )
            self.steps_at_target = 0
            self.consecutive_steps_in_tolerance = 0

        return {
            "mode": "scheduled",
            "target_ph": target_ph,
            "next_target_ph": self.current_target_ph,
            "target_index": target_index,
            "next_target_index": self.current_target_index,
            "cycle_position": cycle_position,
            "next_cycle_position": self.cycle_position,
            "steps_at_target": completed_steps,
            "consecutive_steps_in_tolerance": consecutive_steps,
            "within_tolerance": within_tolerance,
            "target_changed": target_changed,
            "change_reason": change_reason,
            "maximum_steps_reached": maximum_steps_reached,
            "consecutive_requirement_reached": consecutive_requirement_reached,
        }


def select_frozen_action(
    model,
    state: Sequence[float],
    *,
    action_mode: str,
    gaussian_noise_std: float,
    rng: np.random.Generator | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return a deterministic or explicitly noisy action from a frozen actor."""

    mode = str(action_mode).lower()
    if mode not in {"deterministic", "gaussian_noise"}:
        raise RuntimeModeError(
            "frozen_action_mode must be 'deterministic' or 'gaussian_noise'."
        )
    noise_std = float(gaussian_noise_std)
    if not np.isfinite(noise_std) or noise_std < 0.0:
        raise RuntimeModeError("frozen_action_noise_std must be nonnegative.")
    if mode == "gaussian_noise" and rng is None:
        raise RuntimeModeError("Gaussian frozen actions require a random generator.")

    clean_action, _ = model.predict(state, deterministic=True)
    clean_action = np.asarray(clean_action, dtype=np.float32).reshape(-1)
    if clean_action.shape != (2,) or not np.all(np.isfinite(clean_action)):
        raise RuntimeModeError("Frozen TD3 actor returned an invalid action.")

    sampled_noise = np.zeros_like(clean_action)
    if mode == "gaussian_noise":
        sampled_noise = rng.normal(
            loc=0.0,
            scale=noise_std,
            size=clean_action.shape,
        ).astype(np.float32)

    unclipped_action = clean_action + sampled_noise
    selected_action = np.clip(unclipped_action, -1.0, 1.0).astype(np.float32)
    applied_noise = selected_action - clean_action
    action_source = (
        "frozen_td3_deterministic"
        if mode == "deterministic"
        else "frozen_td3_gaussian_noise"
    )
    return selected_action, {
        "action_source": action_source,
        "frozen_action_mode": mode,
        "clean_action": clean_action,
        "sampled_noise": sampled_noise,
        "unclipped_action": unclipped_action,
        "selected_action": selected_action,
        "exploration_sigma": noise_std if mode == "gaussian_noise" else 0.0,
        "exploration_magnitude": float(np.mean(np.abs(applied_noise))),
        "action_saturation_fraction": float(
            np.mean(np.abs(selected_action) >= 1.0 - 1.0e-6)
        ),
        "online_action_step": None,
    }
