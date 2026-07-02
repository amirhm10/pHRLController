from __future__ import annotations

from dataclasses import dataclass, field

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from simulation.config import PHProcessConfig
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


@dataclass
class PHEnvironmentConfig:
    """Configuration for the offline ideal-HH pH learning environment."""

    process_config: PHProcessConfig = field(default_factory=PHProcessConfig)
    target_ph: float | None = None
    max_episode_steps: int = 100
    target_tolerance: float = 0.02
    tracking_weight: float = 1.0
    absolute_error_weight: float = 1.0
    move_penalty_weight: float = 0.01
    default_flow_penalty_weight: float = 0.0
    fixed_buffer_flow_sum: float = 15.0
    random_seed: int | None = 7


def fixed_buffer_acid_bounds(
    process_config: PHProcessConfig,
    fixed_buffer_flow_sum: float,
) -> tuple[float, float]:
    """Return feasible acid-flow bounds for a fixed acid+acetate sum."""
    total = float(fixed_buffer_flow_sum)
    acid_low = max(process_config.acid_flow_min, total - process_config.acetate_flow_max)
    acid_high = min(process_config.acid_flow_max, total - process_config.acetate_flow_min)
    if acid_low > acid_high:
        raise ValueError(
            "fixed_buffer_flow_sum is infeasible for configured acid/acetate bounds."
        )
    return float(acid_low), float(acid_high)


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


class PHEnvironment(gym.Env):
    """Gymnasium-style offline pH environment using ideal Henderson-Hasselbalch.

    The action is a normalized acid/acetate ratio command. Acid plus acetate
    flow is fixed, and water is fixed at the configured default flow. The
    static pH calculation uses only the accepted ideal Henderson-Hasselbalch
    acid/acetate ratio.
    """

    metadata = {"render_modes": []}

    def __init__(self, config: PHEnvironmentConfig | None = None) -> None:
        super().__init__()
        self.env_config = config or PHEnvironmentConfig()
        self.process_config = self.env_config.process_config
        self.model = HendersonHasselbalchModel.from_config(self.process_config)
        self._rng = np.random.default_rng(self.env_config.random_seed)

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
        self.acid_flow_low_for_sum, self.acid_flow_high_for_sum = fixed_buffer_acid_bounds(
            process_config=self.process_config,
            fixed_buffer_flow_sum=self.fixed_buffer_flow_sum,
        )
        self.flow_ratio_low = (
            self.fixed_buffer_flow_sum - self.acid_flow_high_for_sum
        ) / self.acid_flow_high_for_sum
        self.flow_ratio_high = (
            self.fixed_buffer_flow_sum - self.acid_flow_low_for_sum
        ) / self.acid_flow_low_for_sum
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
            shape=(1,),
            dtype=np.float32,
        )
        error_span = self.process_config.target_ph_max - self.process_config.target_ph_min
        self.observation_space = spaces.Box(
            low=np.array(
                [
                    self.process_config.target_ph_min,
                    self.process_config.target_ph_min,
                    -error_span,
                    -1.0,
                    0.0,
                ],
                dtype=np.float32,
            ),
            high=np.array(
                [
                    self.process_config.target_ph_max,
                    self.process_config.target_ph_max,
                    error_span,
                    1.0,
                    1.0,
                ],
                dtype=np.float32,
            ),
            dtype=np.float32,
        )

        self.target_ph = float(self.process_config.pKa)
        self.current_flows = self.default_flows.copy()
        self.current_ph = float(self.process_config.pKa)
        self.step_count = 0

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

        observation = self._make_observation()
        return observation, self._make_info()

    def step(
        self,
        action,
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        action_arr = self._validate_action(action)
        previous_normalized_flows = self._normalize_flows(self.current_flows)

        self.current_flows = self._action_to_flows(action_arr)
        self.current_ph = self._predict_ph_from_flows(self.current_flows)
        self.step_count += 1

        setpoint_error = self.target_ph - self.current_ph
        tracking_cost = float(setpoint_error**2)
        absolute_error_cost = float(abs(setpoint_error))
        move_cost = float(np.mean((action_arr - previous_normalized_flows) ** 2))
        default_cost = float(
            np.mean((action_arr - self._normalize_flows(self.default_flows)) ** 2)
        )
        tracking_term = self.env_config.tracking_weight * tracking_cost
        absolute_error_term = self.env_config.absolute_error_weight * absolute_error_cost
        move_term = self.env_config.move_penalty_weight * move_cost
        default_flow_term = self.env_config.default_flow_penalty_weight * default_cost
        total_cost = (
            tracking_term
            + absolute_error_term
            + move_term
            + default_flow_term
        )
        reward = -total_cost

        terminated = False
        truncated = self.step_count >= int(self.env_config.max_episode_steps)
        info = self._make_info(
            reward=float(reward),
            setpoint_error=setpoint_error,
            tracking_cost=tracking_cost,
            absolute_error_cost=absolute_error_cost,
            move_cost=move_cost,
            default_flow_cost=default_cost,
            tracking_term=tracking_term,
            absolute_error_term=absolute_error_term,
            move_term=move_term,
            default_flow_term=default_flow_term,
            total_cost=total_cost,
        )
        return self._make_observation(), float(reward), terminated, truncated, info

    def set_target_ph(self, target_ph: float) -> tuple[np.ndarray, dict]:
        """Update the current setpoint without resetting the simulated process."""
        self.target_ph = self.process_config.clip_target_ph(float(target_ph))
        return self._make_observation(), self._make_info()

    def action_to_flows(self, action) -> np.ndarray:
        """Map a normalized ratio action to bounded physical flows."""
        return self._action_to_flows(self._validate_action(action))

    def flows_to_action(self, flows) -> np.ndarray:
        """Map physical acid and acetate flows to a normalized ratio action."""
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
        del buffer_flow_sum
        del water_flow
        flow_ratio = (
            self.process_config.acid_stock_mol_l
            / self.process_config.acetate_stock_mol_l
            * 10.0 ** (target_ph - self.process_config.pKa)
        )
        flow_ratio = float(np.clip(flow_ratio, self.flow_ratio_low, self.flow_ratio_high))
        acid_flow = self.fixed_buffer_flow_sum / (1.0 + flow_ratio)
        acetate_flow = self.fixed_buffer_flow_sum - acid_flow
        return self._clip_flows(
            np.array([acid_flow, acetate_flow, self.fixed_water_flow], dtype=np.float32)
        )

    def _validate_action(self, action) -> np.ndarray:
        action_arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if action_arr.size != 1:
            raise ValueError(f"action must have shape (1,), got {action_arr.shape}.")
        if not np.all(np.isfinite(action_arr)):
            raise ValueError("action must contain only finite values.")
        return np.clip(action_arr, -1.0, 1.0).astype(np.float32)

    def _clip_flows(self, flows: np.ndarray) -> np.ndarray:
        flows = np.asarray(flows, dtype=np.float32).reshape(-1)
        if flows.size not in {2, 3}:
            raise ValueError(f"flows must have shape (2,) or (3,), got {flows.shape}.")
        acid_flow = float(
            np.clip(
                flows[0],
                self.acid_flow_low_for_sum,
                self.acid_flow_high_for_sum,
            )
        )
        acetate_flow = self.fixed_buffer_flow_sum - acid_flow
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
        if abs(buffer_sum - self.fixed_buffer_flow_sum) > tolerance:
            raise ValueError(
                f"{context} violates fixed buffer-flow sum: "
                f"{buffer_sum} != {self.fixed_buffer_flow_sum}."
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
            "fixed_water_flow": float(self.fixed_water_flow),
        }

    def _action_to_flows(self, action: np.ndarray) -> np.ndarray:
        fraction = float(0.5 * (action[0] + 1.0))
        log_ratio = self.log_ratio_low + fraction * (
            self.log_ratio_high - self.log_ratio_low
        )
        flow_ratio = 10.0 ** log_ratio
        acid_flow = self.fixed_buffer_flow_sum / (1.0 + flow_ratio)
        acetate_flow = self.fixed_buffer_flow_sum - acid_flow
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
        log_ratio = float(
            np.log10(np.clip(ratio, self.flow_ratio_low, self.flow_ratio_high))
        )
        scaled = 2.0 * (log_ratio - self.log_ratio_low) / (
            self.log_ratio_high - self.log_ratio_low
        ) - 1.0
        return np.array([np.clip(scaled, -1.0, 1.0)], dtype=np.float32)

    def _predict_ph_from_flows(self, flows: np.ndarray) -> float:
        return self.model.predict_ph(
            acid_flow=float(flows[0]),
            base_flow=float(flows[1]),
            water_flow=float(flows[2]),
        )

    def _make_observation(self) -> np.ndarray:
        error = self.current_ph - self.target_ph
        step_fraction = min(
            1.0,
            self.step_count / max(1, int(self.env_config.max_episode_steps)),
        )
        observation = np.array(
            [
                self.current_ph,
                self.target_ph,
                error,
                self._normalize_flows(self.current_flows)[0],
                step_fraction,
            ],
            dtype=np.float32,
        )
        return observation

    def _make_info(
        self,
        reward: float | None = None,
        setpoint_error: float | None = None,
        tracking_cost: float | None = None,
        absolute_error_cost: float | None = None,
        move_cost: float | None = None,
        default_flow_cost: float | None = None,
        tracking_term: float | None = None,
        absolute_error_term: float | None = None,
        move_term: float | None = None,
        default_flow_term: float | None = None,
        total_cost: float | None = None,
    ) -> dict:
        acid_flow, acetate_flow, water_flow = map(float, self.current_flows)
        error = float(self.current_ph - self.target_ph)
        info = {
            "ph": float(self.current_ph),
            "target_ph": float(self.target_ph),
            "ph_error": error,
            "acid_flow": acid_flow,
            "acetate_flow": acetate_flow,
            "water_flow": water_flow,
            "buffer_flow_sum": float(acid_flow + acetate_flow),
            "flow_ratio_acetate_acid": float(acetate_flow / acid_flow),
            "log10_flow_ratio_acetate_acid": float(np.log10(acetate_flow / acid_flow)),
            "ratio_action": float(self._normalize_flows(self.current_flows)[0]),
            "molar_base_acid_ratio": float(
                self.model.molar_base_acid_ratio(
                    acid_flow=acid_flow,
                    base_flow=acetate_flow,
                    water_flow=water_flow,
                )
            ),
            "success": bool(abs(error) <= self.env_config.target_tolerance),
            "step_count": int(self.step_count),
        }
        if reward is not None:
            info.update(
                {
                    "reward": float(reward),
                    "reward_setpoint_error": float(setpoint_error),
                    "reward_tracking_cost": float(tracking_cost),
                    "reward_squared_error_cost": float(tracking_cost),
                    "reward_absolute_error_cost": float(absolute_error_cost),
                    "reward_move_cost": float(move_cost),
                    "reward_default_flow_cost": float(default_flow_cost),
                    "reward_squared_error_term": float(tracking_term),
                    "reward_absolute_error_term": float(absolute_error_term),
                    "reward_move_penalty_term": float(move_term),
                    "reward_default_flow_term": float(default_flow_term),
                    "reward_total_cost": float(total_cost),
                }
            )
        return info
