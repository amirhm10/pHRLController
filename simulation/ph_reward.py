from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite, log1p
from typing import Literal

import numpy as np


RewardMode = Literal["three_term", "relative_band", "relative_band_offset"]


@dataclass
class PHRewardConfig:
    """Reward-shaping parameters for the offline pH simulation scaffold."""

    mode: RewardMode = "three_term"
    q_squared: float = 1.0
    q_absolute: float = 1.0
    move_weight: float = 0.0
    default_flow_weight: float = 0.0
    band_floor_ph: float = 0.01
    k_rel: float = 0.0
    q_band: float = 1.0
    r_move: float = 0.0
    sum_move_weight: float = 0.0
    tau_frac: float = 0.7
    gamma_out: float = 0.5
    gamma_in: float = 0.5
    beta: float = 0.0
    lam_in: float = 1.0
    bonus_kind: str = "exp"
    bonus_weight_abs: float = 0.05
    bonus_k: float = 6.0
    bonus_p: float = 0.6
    bonus_c: float = 20.0
    reward_scale: float = 1.0
    absolute_error_weight: float = 1.0
    tail_offset_weight: float = 0.0
    tail_start_fraction: float = 0.75

    def __post_init__(self) -> None:
        self.mode = str(self.mode)
        if self.mode not in {"three_term", "relative_band", "relative_band_offset"}:
            raise ValueError(
                "reward mode must be 'three_term', 'relative_band', "
                "or 'relative_band_offset'."
            )
        nonnegative_names = [
            "q_squared",
            "q_absolute",
            "move_weight",
            "default_flow_weight",
            "band_floor_ph",
            "k_rel",
            "q_band",
            "r_move",
            "sum_move_weight",
            "tau_frac",
            "gamma_out",
            "gamma_in",
            "beta",
            "lam_in",
            "bonus_weight_abs",
            "bonus_k",
            "bonus_p",
            "bonus_c",
            "reward_scale",
            "absolute_error_weight",
            "tail_offset_weight",
        ]
        for name in nonnegative_names:
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            setattr(self, name, value)
        self.tail_start_fraction = float(np.clip(self.tail_start_fraction, 0.0, 1.0))
        if self.bonus_kind not in {"linear", "quadratic", "exp", "power", "log"}:
            raise ValueError(
                "bonus_kind must be 'linear', 'quadratic', 'exp', 'power', or 'log'."
            )

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass
class PHRewardBreakdown:
    """Scalar reward and logged component terms for pH reward diagnostics."""

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
    band_ph: float = float("nan")
    normalized_error: float = float("nan")
    inside_weight: float = float("nan")
    error_effective_term: float = 0.0
    linear_out_term: float = 0.0
    linear_in_term: float = 0.0
    bonus_term: float = 0.0
    tail_offset_cost: float = 0.0
    tail_offset_term: float = 0.0
    hold_progress: float = float("nan")
    hold_weight: float = 0.0
    reward_scale: float = 1.0

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


def compute_three_term_ph_reward(
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
    """Compute the existing squared, absolute, and move-penalty pH reward."""
    cfg = config or PHRewardConfig(mode="three_term")
    setpoint_error = float(target_ph) - float(ph)
    squared_error_cost = float(setpoint_error**2)
    absolute_error_cost = float(abs(setpoint_error))
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

    squared_error_term = cfg.q_squared * squared_error_cost
    absolute_error_term = cfg.q_absolute * absolute_error_cost
    move_penalty_term = cfg.move_weight * move_cost
    default_flow_term = cfg.default_flow_weight * default_flow_cost
    sum_move_penalty_term = cfg.sum_move_weight * sum_move_cost
    unscaled_cost = (
        squared_error_term
        + absolute_error_term
        + move_penalty_term
        + default_flow_term
        + sum_move_penalty_term
    )
    reward = -unscaled_cost * cfg.reward_scale

    return PHRewardBreakdown(
        mode="three_term",
        reward=float(reward),
        setpoint_error=setpoint_error,
        squared_error_cost=squared_error_cost,
        absolute_error_cost=absolute_error_cost,
        move_cost=move_cost,
        default_flow_cost=default_flow_cost,
        sum_move_cost=sum_move_cost,
        squared_error_term=squared_error_term,
        absolute_error_term=absolute_error_term,
        move_penalty_term=move_penalty_term,
        default_flow_term=default_flow_term,
        sum_move_penalty_term=sum_move_penalty_term,
        total_cost=float(-reward),
        hold_progress=_safe_hold_progress(hold_progress),
        reward_scale=cfg.reward_scale,
    )


def compute_relative_band_ph_reward(
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
    """Compute an RL-assisted-MPC-style relative-band pH reward."""
    cfg = config or PHRewardConfig(mode="relative_band")
    setpoint_error = float(target_ph) - float(ph)
    abs_error = float(abs(setpoint_error))
    squared_error_cost = float(setpoint_error**2)
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
    inside_weight = _sigmoid((band_ph - abs_error) / tau_ph)
    normalized_error = abs_error / band_ph

    error_quad = cfg.q_band * squared_error_cost
    error_effective_term = (
        (1.0 - inside_weight) * error_quad
        + inside_weight * cfg.lam_in * error_quad
    )
    move_penalty_term = cfg.r_move * move_cost
    default_flow_term = cfg.default_flow_weight * default_flow_cost
    sum_move_penalty_term = cfg.sum_move_weight * sum_move_cost

    slope_at_edge = 2.0 * cfg.q_band * band_ph
    overflow = max(abs_error - band_ph, 0.0)
    inside_magnitude = min(abs_error, band_ph)
    linear_out_term = (
        (1.0 - inside_weight) * cfg.gamma_out * slope_at_edge * overflow
    )
    linear_in_term = inside_weight * cfg.gamma_in * slope_at_edge * inside_magnitude
    bonus_term = (
        inside_weight
        * cfg.bonus_weight_abs
        * _bonus_shape(normalized_error, cfg)
    )

    unscaled_cost = (
        error_effective_term
        + move_penalty_term
        + default_flow_term
        + sum_move_penalty_term
        + linear_out_term
        + linear_in_term
        - bonus_term
    )
    reward = -unscaled_cost * cfg.reward_scale

    return PHRewardBreakdown(
        mode="relative_band",
        reward=float(reward),
        setpoint_error=setpoint_error,
        squared_error_cost=squared_error_cost,
        absolute_error_cost=abs_error,
        move_cost=move_cost,
        default_flow_cost=default_flow_cost,
        sum_move_cost=sum_move_cost,
        squared_error_term=error_quad,
        absolute_error_term=0.0,
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
        hold_progress=_safe_hold_progress(hold_progress),
        reward_scale=cfg.reward_scale,
    )


def compute_relative_band_offset_ph_reward(
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
    """Compute the relative-band reward with explicit offset-reduction terms."""
    cfg = config or PHRewardConfig(mode="relative_band_offset")
    breakdown = compute_relative_band_ph_reward(
        target_ph=target_ph,
        ph=ph,
        action=action,
        previous_action=previous_action,
        config=cfg,
        default_action=default_action,
        hold_progress=hold_progress,
        buffer_sum=buffer_sum,
        previous_buffer_sum=previous_buffer_sum,
        buffer_sum_min=buffer_sum_min,
        buffer_sum_max=buffer_sum_max,
    )
    hold_weight = _hold_weight(hold_progress, cfg.tail_start_fraction)
    tail_offset_cost = hold_weight * breakdown.absolute_error_cost
    absolute_error_term = cfg.absolute_error_weight * breakdown.absolute_error_cost
    tail_offset_term = cfg.tail_offset_weight * tail_offset_cost
    extra_cost = absolute_error_term + tail_offset_term
    reward = breakdown.reward - extra_cost * cfg.reward_scale

    breakdown.mode = "relative_band_offset"
    breakdown.reward = float(reward)
    breakdown.absolute_error_term = absolute_error_term
    breakdown.tail_offset_cost = tail_offset_cost
    breakdown.tail_offset_term = tail_offset_term
    breakdown.hold_weight = hold_weight
    breakdown.total_cost = float(-reward)
    return breakdown


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
    """Dispatch to the selected pH reward mode."""
    cfg = config or PHRewardConfig()
    if cfg.mode == "three_term":
        return compute_three_term_ph_reward(
            target_ph=target_ph,
            ph=ph,
            action=action,
            previous_action=previous_action,
            config=cfg,
            default_action=default_action,
            hold_progress=hold_progress,
            buffer_sum=buffer_sum,
            previous_buffer_sum=previous_buffer_sum,
            buffer_sum_min=buffer_sum_min,
            buffer_sum_max=buffer_sum_max,
        )
    if cfg.mode == "relative_band":
        return compute_relative_band_ph_reward(
            target_ph=target_ph,
            ph=ph,
            action=action,
            previous_action=previous_action,
            config=cfg,
            default_action=default_action,
            hold_progress=hold_progress,
            buffer_sum=buffer_sum,
            previous_buffer_sum=previous_buffer_sum,
            buffer_sum_min=buffer_sum_min,
            buffer_sum_max=buffer_sum_max,
        )
    if cfg.mode == "relative_band_offset":
        return compute_relative_band_offset_ph_reward(
            target_ph=target_ph,
            ph=ph,
            action=action,
            previous_action=previous_action,
            config=cfg,
            default_action=default_action,
            hold_progress=hold_progress,
            buffer_sum=buffer_sum,
            previous_buffer_sum=previous_buffer_sum,
            buffer_sum_min=buffer_sum_min,
            buffer_sum_max=buffer_sum_max,
        )
    raise ValueError(
        "reward mode must be 'three_term', 'relative_band', or 'relative_band_offset'."
    )


def reward_definition_text(config: PHRewardConfig | None = None) -> str:
    """Return a compact, saved-text definition of the selected reward."""
    cfg = config or PHRewardConfig()
    if cfg.mode == "three_term":
        return (
            "-(q2*(target_pH - pH)^2 + q1*abs(target_pH - pH) + "
            "r_move*mean((action_t - action_t_minus_1)^2) + "
            "r_sum*((S_t - S_t_minus_1)/(S_max - S_min))^2)"
        )
    if cfg.mode == "relative_band":
        return (
            "[-(J_eff + J_move + J_delta_sum + J_lin_out + J_lin_in) + "
            "J_bonus_abs] * reward_scale"
        )
    return (
        "relative_band reward minus absolute-error penalty, with optional "
        "late-hold offset and normalized total-flow move penalties"
    )


def _as_vector(value) -> np.ndarray:
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        raise ValueError("reward action vectors must contain finite values.")
    return arr


def _mean_square_delta(value, reference) -> float:
    current = _as_vector(value)
    previous = _as_vector(reference)
    if current.shape != previous.shape:
        raise ValueError("reward action vectors must have matching shapes.")
    return float(np.mean(np.square(current - previous)))


def _normalized_scalar_delta(
    value: float | None,
    reference: float | None,
    lower: float | None,
    upper: float | None,
) -> float:
    if value is None or reference is None or lower is None or upper is None:
        return 0.0
    value = float(value)
    reference = float(reference)
    lower = float(lower)
    upper = float(upper)
    if not all(isfinite(item) for item in [value, reference, lower, upper]):
        raise ValueError("sum-move penalty inputs must be finite.")
    span = upper - lower
    if span <= 0.0:
        raise ValueError("buffer_sum_max must be greater than buffer_sum_min.")
    return float(((value - reference) / span) ** 2)


def _sigmoid(value: float) -> float:
    clipped = float(np.clip(value, -60.0, 60.0))
    return float(1.0 / (1.0 + exp(-clipped)))


def _bonus_shape(normalized_error: float, config: PHRewardConfig) -> float:
    z = float(np.clip(normalized_error, 0.0, 1.0))
    if config.bonus_kind == "linear":
        return 1.0 - z
    if config.bonus_kind == "quadratic":
        return (1.0 - z) ** 2
    if config.bonus_kind == "exp":
        denom = 1.0 - exp(-config.bonus_k)
        if abs(denom) <= 1.0e-12:
            return 1.0 - z
        return (exp(-config.bonus_k * z) - exp(-config.bonus_k)) / denom
    if config.bonus_kind == "power":
        return 1.0 - float(np.power(z, config.bonus_p))
    if config.bonus_kind == "log":
        return log1p(config.bonus_c * (1.0 - z)) / log1p(config.bonus_c)
    raise ValueError(f"unsupported bonus kind: {config.bonus_kind}")


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
