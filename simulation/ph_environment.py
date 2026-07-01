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
    move_penalty_weight: float = 0.01
    default_flow_penalty_weight: float = 0.001
    random_seed: int | None = 7


class PHEnvironment(gym.Env):
    """Gymnasium-style offline pH environment using ideal Henderson-Hasselbalch.

    The action is a normalized direct command for acid, acetate, and water
    flows. The static pH calculation uses only the accepted ideal
    Henderson-Hasselbalch acid/acetate ratio. Water is still included in the
    action and observation because it is a real actuator for later dynamic work.
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
        self.default_flows = self._clip_flows(
            np.array(
                [
                    0.5 * self.process_config.default_buffer_flow_sum,
                    0.5 * self.process_config.default_buffer_flow_sum,
                    self.process_config.default_water_flow,
                ],
                dtype=np.float32,
            )
        )

        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(3,),
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
                    -1.0,
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

        error = self.current_ph - self.target_ph
        tracking_cost = float(error**2)
        move_cost = float(np.mean((action_arr - previous_normalized_flows) ** 2))
        default_cost = float(
            np.mean((action_arr - self._normalize_flows(self.default_flows)) ** 2)
        )
        reward = -(
            self.env_config.tracking_weight * tracking_cost
            + self.env_config.move_penalty_weight * move_cost
            + self.env_config.default_flow_penalty_weight * default_cost
        )

        terminated = False
        truncated = self.step_count >= int(self.env_config.max_episode_steps)
        info = self._make_info(
            reward=float(reward),
            tracking_cost=tracking_cost,
            move_cost=move_cost,
            default_flow_cost=default_cost,
        )
        return self._make_observation(), float(reward), terminated, truncated, info

    def set_target_ph(self, target_ph: float) -> tuple[np.ndarray, dict]:
        """Update the current setpoint without resetting the simulated process."""
        self.target_ph = self.process_config.clip_target_ph(float(target_ph))
        return self._make_observation(), self._make_info()

    def action_to_flows(self, action) -> np.ndarray:
        """Map a normalized three-pump action to bounded physical flows."""
        return self._action_to_flows(self._validate_action(action))

    def flows_to_action(self, flows) -> np.ndarray:
        """Map physical acid, acetate, and water flows to normalized actions."""
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
        buffer_flow_sum = (
            self.process_config.default_buffer_flow_sum
            if buffer_flow_sum is None
            else float(buffer_flow_sum)
        )
        water_flow = (
            self.process_config.default_water_flow
            if water_flow is None
            else float(water_flow)
        )
        flow_ratio = (
            self.process_config.acid_stock_mol_l
            / self.process_config.acetate_stock_mol_l
            * 10.0 ** (target_ph - self.process_config.pKa)
        )
        acid_flow = buffer_flow_sum / (1.0 + flow_ratio)
        acetate_flow = buffer_flow_sum - acid_flow
        return self._clip_flows(
            np.array([acid_flow, acetate_flow, water_flow], dtype=np.float32)
        )

    def _validate_action(self, action) -> np.ndarray:
        action_arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if action_arr.size != 3:
            raise ValueError(f"action must have shape (3,), got {action_arr.shape}.")
        if not np.all(np.isfinite(action_arr)):
            raise ValueError("action must contain only finite values.")
        return np.clip(action_arr, -1.0, 1.0).astype(np.float32)

    def _clip_flows(self, flows: np.ndarray) -> np.ndarray:
        flows = np.asarray(flows, dtype=np.float32).reshape(-1)
        if flows.size != 3:
            raise ValueError(f"flows must have shape (3,), got {flows.shape}.")
        return np.clip(flows, self.flow_low, self.flow_high).astype(np.float32)

    def _action_to_flows(self, action: np.ndarray) -> np.ndarray:
        fraction = 0.5 * (action + 1.0)
        return (self.flow_low + fraction * (self.flow_high - self.flow_low)).astype(
            np.float32
        )

    def _normalize_flows(self, flows: np.ndarray) -> np.ndarray:
        flows = self._clip_flows(flows)
        scaled = 2.0 * (flows - self.flow_low) / (self.flow_high - self.flow_low) - 1.0
        return np.clip(scaled, -1.0, 1.0).astype(np.float32)

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
                *self._normalize_flows(self.current_flows),
                step_fraction,
            ],
            dtype=np.float32,
        )
        return observation

    def _make_info(
        self,
        reward: float | None = None,
        tracking_cost: float | None = None,
        move_cost: float | None = None,
        default_flow_cost: float | None = None,
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
            "flow_ratio_acetate_acid": float(acetate_flow / acid_flow),
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
                    "reward_tracking_cost": float(tracking_cost),
                    "reward_move_cost": float(move_cost),
                    "reward_default_flow_cost": float(default_flow_cost),
                }
            )
        return info
