"""The active relative-band-offset pH reward from the latest TD3 run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite

import numpy as np


@dataclass
class PHRewardConfig:
    """Only parameters used by the active relative-band-offset reward."""

    band_floor_ph: float = 0.01
    k_rel: float = 0.0
    q_band: float = 1.0
    r_move: float = 0.0
    default_flow_weight: float = 0.0
    sum_move_weight: float = 5.0
    tau_frac: float = 0.7
    gamma_out: float = 0.5
    gamma_in: float = 0.5
    lam_in: float = 1.0
    bonus_weight_abs: float = 0.05
    bonus_k: float = 6.0
    reward_scale: float = 1.0
    absolute_error_weight: float = 1.0
    tail_offset_weight: float = 0.0
    tail_start_fraction: float = 0.75

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            setattr(self, name, value)
        self.tail_start_fraction = float(
            np.clip(self.tail_start_fraction, 0.0, 1.0)
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class PHRewardBreakdown:
    mode: str
    reward: float
    setpoint_error: float
    squared_error_cost: float
    absolute_error_cost: float
    move_cost: float
    default_flow_cost: float
    sum_move_cost: float
    squared_error_term: float
    absolute_error_term: float
    move_penalty_term: float
    default_flow_term: float
    sum_move_penalty_term: float
    total_cost: float
    band_ph: float
    normalized_error: float
    inside_weight: float
    error_effective_term: float
    linear_out_term: float
    linear_in_term: float
    bonus_term: float
    tail_offset_cost: float
    tail_offset_term: float
    hold_progress: float
    hold_weight: float
    reward_scale: float

    def to_info_dict(self) -> dict[str, float | str]:
        return {
            "reward_mode": self.mode,
            "reward": float(self.reward),
            "reward_setpoint_error": float(self.setpoint_error),
            "reward_tracking_cost": float(self.squared_error_cost),
            "reward_squared_error_cost": float(self.squared_error_cost),
            "reward_absolute_error_cost": float(self.absolute_error_cost),
            "reward_move_cost": float(self.move_cost),
            "reward_default_flow_cost": float(self.default_flow_cost),
            "reward_sum_move_cost": float(self.sum_move_cost),
            "reward_squared_error_term": float(self.squared_error_term),
            "reward_absolute_error_term": float(self.absolute_error_term),
            "reward_move_penalty_term": float(self.move_penalty_term),
            "reward_default_flow_term": float(self.default_flow_term),
            "reward_sum_move_penalty_term": float(self.sum_move_penalty_term),
            "reward_total_cost": float(self.total_cost),
            "reward_band_ph": float(self.band_ph),
            "reward_normalized_error": float(self.normalized_error),
            "reward_inside_weight": float(self.inside_weight),
            "reward_error_effective_term": float(self.error_effective_term),
            "reward_linear_out_term": float(self.linear_out_term),
            "reward_linear_in_term": float(self.linear_in_term),
            "reward_bonus_term": float(self.bonus_term),
            "reward_tail_offset_cost": float(self.tail_offset_cost),
            "reward_tail_offset_term": float(self.tail_offset_term),
            "reward_hold_progress": float(self.hold_progress),
            "reward_hold_weight": float(self.hold_weight),
            "reward_scale": float(self.reward_scale),
        }


def compute_ph_reward(
    *,
    target_ph: float,
    ph: float,
    action,
    previous_action,
    config: PHRewardConfig | None = None,
    default_action=None,
    hold_progress: float | None = None,
    buffer_sum: float | None = None,
    previous_buffer_sum: float | None = None,
    buffer_sum_min: float | None = None,
    buffer_sum_max: float | None = None,
) -> PHRewardBreakdown:
    """Compute the exact active relative-band reward plus offset penalty."""

    cfg = config or PHRewardConfig()
    setpoint_error = float(target_ph) - float(ph)
    absolute_error = float(abs(setpoint_error))
    squared_error = float(setpoint_error**2)
    move_cost = _mean_square_delta(action, previous_action)
    default_flow_cost = (
        _mean_square_delta(action, default_action)
        if default_action is not None
        else 0.0
    )
    sum_move_cost = _normalized_scalar_delta(
        buffer_sum,
        previous_buffer_sum,
        buffer_sum_min,
        buffer_sum_max,
    )

    band_ph = max(cfg.k_rel * abs(float(target_ph)), cfg.band_floor_ph, 1.0e-12)
    tau_ph = max(cfg.tau_frac * band_ph, 1.0e-12)
    inside_weight = _sigmoid((band_ph - absolute_error) / tau_ph)
    normalized_error = absolute_error / band_ph
    error_quad = cfg.q_band * squared_error
    error_effective_term = (
        (1.0 - inside_weight) * error_quad
        + inside_weight * cfg.lam_in * error_quad
    )
    move_penalty_term = cfg.r_move * move_cost
    default_flow_term = cfg.default_flow_weight * default_flow_cost
    sum_move_penalty_term = cfg.sum_move_weight * sum_move_cost
    slope_at_edge = 2.0 * cfg.q_band * band_ph
    overflow = max(absolute_error - band_ph, 0.0)
    inside_magnitude = min(absolute_error, band_ph)
    linear_out_term = (
        (1.0 - inside_weight) * cfg.gamma_out * slope_at_edge * overflow
    )
    linear_in_term = (
        inside_weight * cfg.gamma_in * slope_at_edge * inside_magnitude
    )
    bonus_term = (
        inside_weight
        * cfg.bonus_weight_abs
        * _exponential_bonus(normalized_error, cfg.bonus_k)
    )
    base_cost = (
        error_effective_term
        + move_penalty_term
        + default_flow_term
        + sum_move_penalty_term
        + linear_out_term
        + linear_in_term
        - bonus_term
    )
    hold_weight = _hold_weight(hold_progress, cfg.tail_start_fraction)
    tail_offset_cost = hold_weight * absolute_error
    absolute_error_term = cfg.absolute_error_weight * absolute_error
    tail_offset_term = cfg.tail_offset_weight * tail_offset_cost
    base_reward = -base_cost * cfg.reward_scale
    reward = base_reward - (
        absolute_error_term + tail_offset_term
    ) * cfg.reward_scale

    return PHRewardBreakdown(
        mode="relative_band_offset",
        reward=float(reward),
        setpoint_error=setpoint_error,
        squared_error_cost=squared_error,
        absolute_error_cost=absolute_error,
        move_cost=move_cost,
        default_flow_cost=default_flow_cost,
        sum_move_cost=sum_move_cost,
        squared_error_term=error_quad,
        absolute_error_term=absolute_error_term,
        move_penalty_term=move_penalty_term,
        default_flow_term=default_flow_term,
        sum_move_penalty_term=sum_move_penalty_term,
        total_cost=float(-reward),
        band_ph=band_ph,
        normalized_error=normalized_error,
        inside_weight=inside_weight,
        error_effective_term=error_effective_term,
        linear_out_term=linear_out_term,
        linear_in_term=linear_in_term,
        bonus_term=bonus_term,
        tail_offset_cost=tail_offset_cost,
        tail_offset_term=tail_offset_term,
        hold_progress=_safe_hold_progress(hold_progress),
        hold_weight=hold_weight,
        reward_scale=cfg.reward_scale,
    )


def reward_definition_text(config: PHRewardConfig | None = None) -> str:
    del config
    return (
        "relative_band reward minus absolute-error penalty, with optional "
        "late-hold offset and normalized total-flow move penalties"
    )


def _as_vector(value) -> np.ndarray:
    values = np.asarray(value, dtype=float).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("reward action vectors must contain finite values.")
    return values


def _mean_square_delta(value, reference) -> float:
    current = _as_vector(value)
    previous = _as_vector(reference)
    if current.shape != previous.shape:
        raise ValueError("reward action vectors must have matching shapes.")
    return float(np.mean(np.square(current - previous)))


def _normalized_scalar_delta(value, reference, lower, upper) -> float:
    if value is None or reference is None or lower is None or upper is None:
        return 0.0
    values = [float(value), float(reference), float(lower), float(upper)]
    if not all(isfinite(item) for item in values):
        raise ValueError("sum-move penalty inputs must be finite.")
    span = values[3] - values[2]
    if span <= 0.0:
        raise ValueError("buffer_sum_max must be greater than buffer_sum_min.")
    return float(((values[0] - values[1]) / span) ** 2)


def _sigmoid(value: float) -> float:
    clipped = float(np.clip(value, -60.0, 60.0))
    return float(1.0 / (1.0 + exp(-clipped)))


def _exponential_bonus(normalized_error: float, bonus_k: float) -> float:
    value = float(np.clip(normalized_error, 0.0, 1.0))
    denominator = 1.0 - exp(-bonus_k)
    if abs(denominator) <= 1.0e-12:
        return 1.0 - value
    return (exp(-bonus_k * value) - exp(-bonus_k)) / denominator


def _safe_hold_progress(hold_progress: float | None) -> float:
    if hold_progress is None:
        return float("nan")
    return float(np.clip(float(hold_progress), 0.0, 1.0))


def _hold_weight(hold_progress: float | None, tail_start_fraction: float) -> float:
    if hold_progress is None:
        return 0.0
    progress = _safe_hold_progress(hold_progress)
    start = float(np.clip(tail_start_fraction, 0.0, 1.0))
    if start >= 1.0:
        return 1.0 if progress >= 1.0 else 0.0
    return float(np.clip((progress - start) / (1.0 - start), 0.0, 1.0))
