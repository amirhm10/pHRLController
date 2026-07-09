from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from simulation.config import PHProcessConfig
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel
from simulation.ph_reward import (
    PHRewardBreakdown,
    PHRewardConfig,
    compute_ph_reward,
)

PHActionMode = Literal["ratio", "ratio_buffer_sum"]


@dataclass
class PHEnvironmentConfig:
    """Configuration for the offline ideal-HH pH learning environment."""

    process_config: PHProcessConfig = field(default_factory=PHProcessConfig)
    target_ph: float | None = None
    max_episode_steps: int = 100
    target_tolerance: float = 0.02
    tracking_weight: float = 1.0
    absolute_error_weight: float = 1.0
    move_penalty_weight: float = 0.0
    sum_move_penalty_weight: float = 1.0
    default_flow_penalty_weight: float = 0.0
    reward_config: PHRewardConfig | None = None
    setpoint_hold_steps: int | None = None
    action_mode: PHActionMode = "ratio_buffer_sum"
    fixed_buffer_flow_sum: float = 15.0
    buffer_flow_sum_min: float | None = None
    buffer_flow_sum_max: float | None = None
    random_seed: int | None = 7

    def __post_init__(self) -> None:
        self.action_mode = str(self.action_mode)
        if self.action_mode not in {"ratio", "ratio_buffer_sum"}:
            raise ValueError("action_mode must be 'ratio' or 'ratio_buffer_sum'.")

    def resolved_reward_config(self) -> PHRewardConfig:
        """Return an explicit reward config while preserving legacy fields."""
        if self.reward_config is not None:
            return self.reward_config
        return PHRewardConfig(
            mode="three_term",
            q_squared=self.tracking_weight,
            q_absolute=self.absolute_error_weight,
            move_weight=self.move_penalty_weight,
            sum_move_weight=self.sum_move_penalty_weight,
            default_flow_weight=self.default_flow_penalty_weight,
        )


def buffer_acid_bounds(
    process_config: PHProcessConfig,
    buffer_flow_sum: float,
) -> tuple[float, float]:
    """Return feasible acid-flow bounds for a chosen acid+acetate sum."""
    total = float(buffer_flow_sum)
    acid_low = max(process_config.acid_flow_min, total - process_config.acetate_flow_max)
    acid_high = min(process_config.acid_flow_max, total - process_config.acetate_flow_min)
    if acid_low > acid_high:
        raise ValueError(
            "buffer_flow_sum is infeasible for configured acid/acetate bounds."
        )
    return float(acid_low), float(acid_high)


def fixed_buffer_acid_bounds(
    process_config: PHProcessConfig,
    fixed_buffer_flow_sum: float,
) -> tuple[float, float]:
    """Return feasible acid-flow bounds for a fixed acid+acetate sum."""
    return buffer_acid_bounds(
        process_config=process_config,
        buffer_flow_sum=fixed_buffer_flow_sum,
    )


def flow_ratio_bounds_for_sum(
    process_config: PHProcessConfig,
    buffer_flow_sum: float,
) -> tuple[float, float]:
    """Return feasible acetate/acid ratio bounds for a buffer-flow sum."""
    acid_low, acid_high = buffer_acid_bounds(
        process_config=process_config,
        buffer_flow_sum=buffer_flow_sum,
    )
    total = float(buffer_flow_sum)
    ratio_low = (total - acid_high) / acid_high
    ratio_high = (total - acid_low) / acid_low
    if ratio_low <= 0.0 or ratio_high <= 0.0:
        raise ValueError("flow-ratio bounds must be positive.")
    return float(ratio_low), float(ratio_high)


def fixed_buffer_target_ph_bounds(
    process_config: PHProcessConfig,
    fixed_buffer_flow_sum: float,
) -> tuple[float, float]:
    """Return reachable ideal-HH pH bounds under a fixed acid+acetate sum."""
    acid_low, acid_high = fixed_buffer_acid_bounds(
        process_config=process_config,
        fixed_buffer_flow_sum=fixed_buffer_flow_sum,
    )
    total = float(fixed_buffer_flow_sum)
    ratio_low = (total - acid_high) / acid_high
    ratio_high = (total - acid_low) / acid_low
    stock_ratio = process_config.acetate_stock_mol_l / process_config.acid_stock_mol_l
    ph_low = process_config.pKa + np.log10(stock_ratio * ratio_low)
    ph_high = process_config.pKa + np.log10(stock_ratio * ratio_high)
    target_low = float(max(process_config.target_ph_min, ph_low))
    target_high = float(min(process_config.target_ph_max, ph_high))
    if target_low >= target_high:
        raise ValueError(
            "fixed_buffer_flow_sum gives no reachable pH range inside configured target bounds."
        )
    return target_low, target_high


def variable_buffer_target_ph_bounds(
    process_config: PHProcessConfig,
    buffer_flow_sum_min: float,
    buffer_flow_sum_max: float,
) -> tuple[float, float]:
    """Return reachable ideal-HH pH bounds across a total-flow sum interval."""
    sum_min = float(buffer_flow_sum_min)
    sum_max = float(buffer_flow_sum_max)
    if sum_min > sum_max:
        raise ValueError("buffer_flow_sum_min must not exceed buffer_flow_sum_max.")
    candidate_sums = np.linspace(sum_min, sum_max, num=2001)
    ratio_lows: list[float] = []
    ratio_highs: list[float] = []
    for total in candidate_sums:
        try:
            ratio_low, ratio_high = flow_ratio_bounds_for_sum(
                process_config=process_config,
                buffer_flow_sum=float(total),
            )
        except ValueError:
            continue
        ratio_lows.append(ratio_low)
        ratio_highs.append(ratio_high)
    if not ratio_lows:
        raise ValueError("buffer-flow sum range contains no feasible pump allocation.")
    stock_ratio = process_config.acetate_stock_mol_l / process_config.acid_stock_mol_l
    ph_low = process_config.pKa + np.log10(stock_ratio * min(ratio_lows))
    ph_high = process_config.pKa + np.log10(stock_ratio * max(ratio_highs))
    target_low = float(max(process_config.target_ph_min, ph_low))
    target_high = float(min(process_config.target_ph_max, ph_high))
    if target_low >= target_high:
        raise ValueError(
            "buffer-flow sum range gives no reachable pH range inside configured target bounds."
        )
    return target_low, target_high


class PHEnvironment(gym.Env):
    """Gymnasium-style offline pH environment using ideal Henderson-Hasselbalch.

    The default action is a normalized acid/acetate ratio command plus a
    normalized acid+acetate total-flow command. A legacy ratio-only mode is
    retained for ablations. Water is fixed at the configured default flow.
    The static pH calculation uses only the accepted ideal Henderson-Hasselbalch
    acid/acetate ratio.
    """

    metadata = {"render_modes": []}

    def __init__(self, config: PHEnvironmentConfig | None = None) -> None:
        super().__init__()
        self.env_config = config or PHEnvironmentConfig()
        self.process_config = self.env_config.process_config
        self.reward_config = self.env_config.resolved_reward_config()
        self.model = HendersonHasselbalchModel.from_config(self.process_config)
        self._rng = np.random.default_rng(self.env_config.random_seed)
        self.action_mode = self.env_config.action_mode

        self.flow_low = np.array(
            [
                self.process_config.acid_flow_min,
                self.process_config.acetate_flow_min,
                self.process_config.water_flow_min,
            ],
            dtype=np.float32,
        )
        self.flow_high = np.array(
            [
                self.process_config.acid_flow_max,
                self.process_config.acetate_flow_max,
                self.process_config.water_flow_max,
            ],
            dtype=np.float32,
        )
        self.fixed_buffer_flow_sum = float(self.env_config.fixed_buffer_flow_sum)
        self.buffer_flow_sum_min = (
            self.process_config.acid_flow_min + self.process_config.acetate_flow_min
            if self.env_config.buffer_flow_sum_min is None
            else float(self.env_config.buffer_flow_sum_min)
        )
        self.buffer_flow_sum_max = (
            self.process_config.acid_flow_max + self.process_config.acetate_flow_max
            if self.env_config.buffer_flow_sum_max is None
            else float(self.env_config.buffer_flow_sum_max)
        )
        self._validate_buffer_sum_range()
        self.fixed_buffer_flow_sum = float(
            np.clip(
                self.fixed_buffer_flow_sum,
                self.buffer_flow_sum_min,
                self.buffer_flow_sum_max,
            )
        )
        self.acid_flow_low_for_sum, self.acid_flow_high_for_sum = fixed_buffer_acid_bounds(
            process_config=self.process_config,
            fixed_buffer_flow_sum=self.fixed_buffer_flow_sum,
        )
        self.flow_ratio_low, self.flow_ratio_high = flow_ratio_bounds_for_sum(
            process_config=self.process_config,
            buffer_flow_sum=self.fixed_buffer_flow_sum,
        )
        self.log_ratio_low = float(np.log10(self.flow_ratio_low))
        self.log_ratio_high = float(np.log10(self.flow_ratio_high))
        self.fixed_water_flow = float(
            np.clip(
                self.process_config.default_water_flow,
                self.process_config.water_flow_min,
                self.process_config.water_flow_max,
            )
        )
        self.default_flows = self.target_to_nominal_flows(
            target_ph=self.process_config.pKa
        )

        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.action_dim,),
            dtype=np.float32,
        )
        error_span = self.process_config.target_ph_max - self.process_config.target_ph_min
        observation_low = [
            self.process_config.target_ph_min,
            self.process_config.target_ph_min,
            -error_span,
            -1.0,
        ]
        observation_high = [
            self.process_config.target_ph_max,
            self.process_config.target_ph_max,
            error_span,
            1.0,
        ]
        if self.action_mode == "ratio_buffer_sum":
            observation_low.append(-1.0)
            observation_high.append(1.0)
        self.observation_space = spaces.Box(
            low=np.array(observation_low, dtype=np.float32),
            high=np.array(observation_high, dtype=np.float32),
            dtype=np.float32,
        )

        self.target_ph = float(self.process_config.pKa)
        self.current_flows = self.default_flows.copy()
        self.current_ph = float(self.process_config.pKa)
        self.step_count = 0
        self.setpoint_hold_step = 0

    @property
    def action_dim(self) -> int:
        return 2 if self.action_mode == "ratio_buffer_sum" else 1

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        options = options or {}
        target_ph = options.get("target_ph", self.env_config.target_ph)
        if target_ph is None:
            target_ph = self._rng.uniform(
                self.process_config.target_ph_min,
                self.process_config.target_ph_max,
            )
        self.target_ph = self.process_config.clip_target_ph(float(target_ph))

        initial_flows = options.get("initial_flows", self.default_flows)
        self.current_flows = self._clip_flows(np.asarray(initial_flows, dtype=np.float32))
        self.current_ph = self._predict_ph_from_flows(self.current_flows)
        self.step_count = 0
        self.setpoint_hold_step = 0

        observation = self._make_observation()
        return observation, self._make_info()

    def step(
        self,
        action,
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        action_arr = self._validate_action(action)
        previous_flows = self.current_flows.copy()
        previous_normalized_flows = self._normalize_flows(previous_flows)
        previous_buffer_sum = float(previous_flows[0] + previous_flows[1])

        self.current_flows = self._action_to_flows(action_arr)
        self.current_ph = self._predict_ph_from_flows(self.current_flows)
        current_buffer_sum = float(self.current_flows[0] + self.current_flows[1])
        self.step_count += 1
        self.setpoint_hold_step += 1

        reward_breakdown = compute_ph_reward(
            target_ph=self.target_ph,
            ph=self.current_ph,
            action=action_arr,
            previous_action=previous_normalized_flows,
            default_action=self._normalize_flows(self.default_flows),
            hold_progress=self._setpoint_hold_progress(),
            buffer_sum=current_buffer_sum,
            previous_buffer_sum=previous_buffer_sum,
            buffer_sum_min=self.buffer_flow_sum_min,
            buffer_sum_max=self.buffer_flow_sum_max,
            config=self.reward_config,
        )
        reward = reward_breakdown.reward

        terminated = False
        truncated = self.step_count >= int(self.env_config.max_episode_steps)
        info = self._make_info(reward_breakdown=reward_breakdown)
        return self._make_observation(), float(reward), terminated, truncated, info

    def set_target_ph(self, target_ph: float) -> tuple[np.ndarray, dict]:
        """Update the current setpoint without resetting the simulated process."""
        self.target_ph = self.process_config.clip_target_ph(float(target_ph))
        self.setpoint_hold_step = 0
        return self._make_observation(), self._make_info()

    def action_to_flows(self, action) -> np.ndarray:
        """Map a normalized action to bounded physical flows."""
        return self._action_to_flows(self._validate_action(action))

    def flows_to_action(self, flows) -> np.ndarray:
        """Map physical flows to the configured normalized action."""
        return self._normalize_flows(np.asarray(flows, dtype=np.float32))

    def target_to_nominal_flows(
        self,
        target_ph: float,
        buffer_flow_sum: float | None = None,
        water_flow: float | None = None,
    ) -> np.ndarray:
        """Return a clipped ideal-HH flow allocation for a target pH.

        This is only a simulation helper for warm starts and diagnostics. It
        uses the accepted Henderson-Hasselbalch ratio and does not modify the
        chemistry model.
        """
        target_ph = self.process_config.clip_target_ph(float(target_ph))
        if buffer_flow_sum is None:
            buffer_flow_sum = self.fixed_buffer_flow_sum
        buffer_flow_sum = float(
            np.clip(
                float(buffer_flow_sum),
                self.buffer_flow_sum_min,
                self.buffer_flow_sum_max,
            )
        )
        if water_flow is None:
            water_flow = self.fixed_water_flow
        water_flow = float(
            np.clip(
                float(water_flow),
                self.process_config.water_flow_min,
                self.process_config.water_flow_max,
            )
        )
        ratio_low, ratio_high = flow_ratio_bounds_for_sum(
            process_config=self.process_config,
            buffer_flow_sum=buffer_flow_sum,
        )
        flow_ratio = (
            self.process_config.acid_stock_mol_l
            / self.process_config.acetate_stock_mol_l
            * 10.0 ** (target_ph - self.process_config.pKa)
        )
        flow_ratio = float(np.clip(flow_ratio, ratio_low, ratio_high))
        acid_flow = buffer_flow_sum / (1.0 + flow_ratio)
        acid_low, acid_high = buffer_acid_bounds(
            process_config=self.process_config,
            buffer_flow_sum=buffer_flow_sum,
        )
        acid_flow = float(np.clip(acid_flow, acid_low, acid_high))
        acetate_flow = buffer_flow_sum - acid_flow
        return self._clip_flows(
            np.array([acid_flow, acetate_flow, water_flow], dtype=np.float32)
        )

    def _validate_action(self, action) -> np.ndarray:
        action_arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if action_arr.size != self.action_dim:
            raise ValueError(
                f"action must have shape ({self.action_dim},), got {action_arr.shape}."
            )
        if not np.all(np.isfinite(action_arr)):
            raise ValueError("action must contain only finite values.")
        return np.clip(action_arr, -1.0, 1.0).astype(np.float32)

    def _clip_flows(self, flows: np.ndarray) -> np.ndarray:
        flows = np.asarray(flows, dtype=np.float32).reshape(-1)
        if flows.size not in {2, 3}:
            raise ValueError(f"flows must have shape (2,) or (3,), got {flows.shape}.")
        if self.action_mode == "ratio":
            acid_flow = float(
                np.clip(
                    flows[0],
                    self.acid_flow_low_for_sum,
                    self.acid_flow_high_for_sum,
                )
            )
            acetate_flow = self.fixed_buffer_flow_sum - acid_flow
        else:
            acid_flow = float(
                np.clip(
                    flows[0],
                    self.process_config.acid_flow_min,
                    self.process_config.acid_flow_max,
                )
            )
            acetate_flow = float(
                np.clip(
                    flows[1],
                    self.process_config.acetate_flow_min,
                    self.process_config.acetate_flow_max,
                )
            )
            buffer_sum = acid_flow + acetate_flow
            clipped_sum = float(
                np.clip(buffer_sum, self.buffer_flow_sum_min, self.buffer_flow_sum_max)
            )
            if not np.isclose(buffer_sum, clipped_sum):
                ratio = acetate_flow / max(acid_flow, 1.0e-12)
                acid_low, acid_high = buffer_acid_bounds(
                    process_config=self.process_config,
                    buffer_flow_sum=clipped_sum,
                )
                acid_flow = float(
                    np.clip(clipped_sum / (1.0 + ratio), acid_low, acid_high)
                )
                acetate_flow = clipped_sum - acid_flow
        return self._assert_flow_constraints(
            np.array(
                [acid_flow, acetate_flow, self.fixed_water_flow],
                dtype=np.float32,
            ),
            context="clipped flows",
        )

    def _assert_flow_constraints(
        self,
        flows: np.ndarray,
        context: str,
        tolerance: float = 1e-6,
    ) -> np.ndarray:
        flows = np.asarray(flows, dtype=np.float32).reshape(-1)
        if flows.size != 3:
            raise ValueError(f"{context} must have shape (3,), got {flows.shape}.")
        if not np.all(np.isfinite(flows)):
            raise ValueError(f"{context} must contain only finite flow values.")

        below = flows < self.flow_low - tolerance
        above = flows > self.flow_high + tolerance
        if bool(np.any(below) or np.any(above)):
            raise ValueError(
                f"{context} outside pump bounds. "
                f"flows={flows.tolist()}, lower={self.flow_low.tolist()}, "
                f"upper={self.flow_high.tolist()}"
            )

        buffer_sum = float(flows[0] + flows[1])
        if self.action_mode == "ratio":
            if abs(buffer_sum - self.fixed_buffer_flow_sum) > tolerance:
                raise ValueError(
                    f"{context} violates fixed buffer-flow sum: "
                    f"{buffer_sum} != {self.fixed_buffer_flow_sum}."
                )
        elif (
            buffer_sum < self.buffer_flow_sum_min - tolerance
            or buffer_sum > self.buffer_flow_sum_max + tolerance
        ):
            raise ValueError(
                f"{context} violates buffer-flow sum bounds: "
                f"{buffer_sum} outside "
                f"[{self.buffer_flow_sum_min}, {self.buffer_flow_sum_max}]."
            )
        if abs(float(flows[2]) - self.fixed_water_flow) > tolerance:
            raise ValueError(
                f"{context} violates fixed water flow: "
                f"{float(flows[2])} != {self.fixed_water_flow}."
            )
        return flows.astype(np.float32)

    def assert_current_flow_constraints(self) -> None:
        """Raise if the current physical flows violate configured constraints."""
        self._assert_flow_constraints(self.current_flows, context="current flows")

    def flow_constraint_summary(self) -> dict[str, float]:
        """Return active physical flow constraints for diagnostics."""
        return {
            "acid_flow_min": float(self.flow_low[0]),
            "acid_flow_max": float(self.flow_high[0]),
            "acetate_flow_min": float(self.flow_low[1]),
            "acetate_flow_max": float(self.flow_high[1]),
            "water_flow_min": float(self.flow_low[2]),
            "water_flow_max": float(self.flow_high[2]),
            "fixed_buffer_flow_sum": float(self.fixed_buffer_flow_sum),
            "buffer_flow_sum_min": float(self.buffer_flow_sum_min),
            "buffer_flow_sum_max": float(self.buffer_flow_sum_max),
            "fixed_water_flow": float(self.fixed_water_flow),
            "action_mode": self.action_mode,
        }

    def _action_to_flows(self, action: np.ndarray) -> np.ndarray:
        buffer_sum = self._buffer_sum_from_action(action)
        ratio_low, ratio_high = flow_ratio_bounds_for_sum(
            process_config=self.process_config,
            buffer_flow_sum=buffer_sum,
        )
        log_ratio_low = float(np.log10(ratio_low))
        log_ratio_high = float(np.log10(ratio_high))
        fraction = float(0.5 * (action[0] + 1.0))
        log_ratio = log_ratio_low + fraction * (log_ratio_high - log_ratio_low)
        flow_ratio = 10.0 ** log_ratio
        acid_flow = buffer_sum / (1.0 + flow_ratio)
        acid_low, acid_high = buffer_acid_bounds(
            process_config=self.process_config,
            buffer_flow_sum=buffer_sum,
        )
        acid_flow = float(np.clip(acid_flow, acid_low, acid_high))
        acetate_flow = buffer_sum - acid_flow
        return self._assert_flow_constraints(
            np.array(
                [acid_flow, acetate_flow, self.fixed_water_flow],
                dtype=np.float32,
            ),
            context="action-mapped flows",
        )

    def _normalize_flows(self, flows: np.ndarray) -> np.ndarray:
        flows = self._clip_flows(flows)
        ratio = float(flows[1] / flows[0])
        buffer_sum = float(flows[0] + flows[1])
        ratio_low, ratio_high = flow_ratio_bounds_for_sum(
            process_config=self.process_config,
            buffer_flow_sum=buffer_sum,
        )
        log_ratio_low = float(np.log10(ratio_low))
        log_ratio_high = float(np.log10(ratio_high))
        log_ratio = float(
            np.log10(np.clip(ratio, ratio_low, ratio_high))
        )
        log_span = log_ratio_high - log_ratio_low
        if abs(log_span) <= 1.0e-12:
            ratio_action = 0.0
        else:
            ratio_action = 2.0 * (log_ratio - log_ratio_low) / log_span - 1.0
        if self.action_mode == "ratio":
            return np.array([np.clip(ratio_action, -1.0, 1.0)], dtype=np.float32)
        sum_action = self._normalize_buffer_sum(buffer_sum)
        return np.array(
            [
                np.clip(ratio_action, -1.0, 1.0),
                np.clip(sum_action, -1.0, 1.0),
            ],
            dtype=np.float32,
        )

    def _buffer_sum_from_action(self, action: np.ndarray) -> float:
        if self.action_mode == "ratio":
            return float(self.fixed_buffer_flow_sum)
        fraction = float(0.5 * (action[1] + 1.0))
        return float(
            self.buffer_flow_sum_min
            + fraction * (self.buffer_flow_sum_max - self.buffer_flow_sum_min)
        )

    def _normalize_buffer_sum(self, buffer_sum: float) -> float:
        span = self.buffer_flow_sum_max - self.buffer_flow_sum_min
        if span <= 0.0:
            raise ValueError("buffer_flow_sum_max must be greater than buffer_flow_sum_min.")
        return float(
            2.0 * (float(buffer_sum) - self.buffer_flow_sum_min) / span - 1.0
        )

    def _validate_buffer_sum_range(self) -> None:
        feasible_min = self.process_config.acid_flow_min + self.process_config.acetate_flow_min
        feasible_max = self.process_config.acid_flow_max + self.process_config.acetate_flow_max
        if self.buffer_flow_sum_min < feasible_min:
            raise ValueError(
                f"buffer_flow_sum_min must be at least {float(feasible_min)}."
            )
        if self.buffer_flow_sum_max > feasible_max:
            raise ValueError(
                f"buffer_flow_sum_max must be at most {float(feasible_max)}."
            )
        if self.buffer_flow_sum_min >= self.buffer_flow_sum_max:
            raise ValueError("buffer_flow_sum_min must be lower than buffer_flow_sum_max.")

    def _predict_ph_from_flows(self, flows: np.ndarray) -> float:
        return self.model.predict_ph(
            acid_flow=float(flows[0]),
            base_flow=float(flows[1]),
            water_flow=float(flows[2]),
        )

    def _setpoint_hold_progress(self) -> float | None:
        if self.env_config.setpoint_hold_steps is None:
            return None
        hold_steps = max(1, int(self.env_config.setpoint_hold_steps))
        return min(1.0, self.setpoint_hold_step / hold_steps)

    def _make_observation(self) -> np.ndarray:
        error = self.current_ph - self.target_ph
        normalized_action = self._normalize_flows(self.current_flows)
        observation = np.array(
            [self.current_ph, self.target_ph, error, *normalized_action],
            dtype=np.float32,
        )
        return observation

    def _make_info(
        self,
        reward_breakdown: PHRewardBreakdown | None = None,
    ) -> dict:
        acid_flow, acetate_flow, water_flow = map(float, self.current_flows)
        error = float(self.current_ph - self.target_ph)
        normalized_action = self._normalize_flows(self.current_flows)
        info = {
            "action_mode": self.action_mode,
            "ph": float(self.current_ph),
            "target_ph": float(self.target_ph),
            "ph_error": error,
            "acid_flow": acid_flow,
            "acetate_flow": acetate_flow,
            "water_flow": water_flow,
            "buffer_flow_sum": float(acid_flow + acetate_flow),
            "buffer_flow_sum_min": float(self.buffer_flow_sum_min),
            "buffer_flow_sum_max": float(self.buffer_flow_sum_max),
            "flow_ratio_acetate_acid": float(acetate_flow / acid_flow),
            "log10_flow_ratio_acetate_acid": float(np.log10(acetate_flow / acid_flow)),
            "ratio_action": float(normalized_action[0]),
            "normalized_buffer_sum_action": float(normalized_action[1])
            if normalized_action.size > 1
            else float("nan"),
            "molar_base_acid_ratio": float(
                self.model.molar_base_acid_ratio(
                    acid_flow=acid_flow,
                    base_flow=acetate_flow,
                    water_flow=water_flow,
                )
            ),
            "success": bool(abs(error) <= self.env_config.target_tolerance),
            "step_count": int(self.step_count),
            "setpoint_hold_step": int(self.setpoint_hold_step),
            "setpoint_hold_progress": self._setpoint_hold_progress(),
        }
        if reward_breakdown is not None:
            info.update(reward_breakdown.to_info_dict())
        return info
