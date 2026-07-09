from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from simulation.ph_reward import PHRewardConfig, compute_ph_reward


def float_or_nan(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def add_hh_consistency_columns(trajectory: pd.DataFrame, config: dict) -> pd.DataFrame:
    process_config = config.get("process_config", {})
    pka = float_or_nan(process_config.get("pKa", 4.76))
    out = trajectory.copy()
    ratio = out["flow_ratio_acetate_acid"].to_numpy(float)
    out["log10_flow_ratio"] = np.log10(np.maximum(ratio, 1e-12))
    out["hh_ph_from_ratio"] = pka + out["log10_flow_ratio"]
    out["hh_ratio_residual"] = out["ph"] - out["hh_ph_from_ratio"]
    out["abs_ph_error"] = np.abs(out["ph_error"])
    if "reward_squared_error_cost" not in out:
        out["reward_squared_error_cost"] = np.square(out["ph_error"].to_numpy(float))
    if "reward_absolute_error_cost" not in out:
        out["reward_absolute_error_cost"] = out["abs_ph_error"]
    if "reward_move_cost" not in out:
        action_columns = [
            column
            for column in [
                "action_ratio",
                "action_buffer_sum",
                "action_acid",
                "action_acetate",
                "action_water",
            ]
            if column in out
        ]
        if action_columns:
            actions = out[action_columns].to_numpy(float)
            deltas = np.diff(actions, axis=0, prepend=actions[:1])
            out["reward_move_cost"] = np.mean(np.square(deltas), axis=1)
        else:
            out["reward_move_cost"] = 0.0
    if "reward_total_cost" not in out:
        out["reward_total_cost"] = -out["reward"].to_numpy(float)
    for column in [
        "action_ratio",
        "action_buffer_sum",
        "action_acid",
        "action_acetate",
        "action_water",
    ]:
        if column in out:
            out[f"abs_{column}"] = np.abs(out[column])
    return out


def sum_optional(frame: pd.DataFrame, column: str) -> float:
    if column not in frame:
        return np.nan
    return float(frame[column].sum())


def metric_row(label: str, frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "scope": label,
            "steps": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "max_abs_error": np.nan,
            "iae": np.nan,
            "ise": np.nan,
            "mean_reward": np.nan,
            "total_reward": np.nan,
            "squared_error_cost_sum": np.nan,
            "absolute_error_cost_sum": np.nan,
            "move_cost_sum": np.nan,
            "sum_move_cost_sum": np.nan,
            "sum_move_penalty_sum": np.nan,
            "total_cost_sum": np.nan,
            "error_effective_term_sum": np.nan,
            "linear_out_term_sum": np.nan,
            "linear_in_term_sum": np.nan,
            "bonus_term_sum": np.nan,
            "tail_offset_term_sum": np.nan,
            "mean_ph": np.nan,
            "mean_target_ph": np.nan,
            "train_updates": 0,
        }
    error = frame["ph_error"].to_numpy(float)
    reward = frame["reward"].to_numpy(float)
    return {
        "scope": label,
        "steps": int(len(frame)),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "max_abs_error": float(np.max(np.abs(error))),
        "iae": float(np.sum(np.abs(error))),
        "ise": float(np.sum(error**2)),
        "mean_reward": float(np.mean(reward)),
        "total_reward": float(np.sum(reward)),
        "squared_error_cost_sum": sum_optional(frame, "reward_squared_error_cost"),
        "absolute_error_cost_sum": sum_optional(frame, "reward_absolute_error_cost"),
        "move_cost_sum": sum_optional(frame, "reward_move_cost"),
        "sum_move_cost_sum": sum_optional(frame, "reward_sum_move_cost"),
        "sum_move_penalty_sum": sum_optional(
            frame,
            "reward_sum_move_penalty_term",
        ),
        "total_cost_sum": sum_optional(frame, "reward_total_cost"),
        "error_effective_term_sum": sum_optional(
            frame, "reward_error_effective_term"
        ),
        "linear_out_term_sum": sum_optional(frame, "reward_linear_out_term"),
        "linear_in_term_sum": sum_optional(frame, "reward_linear_in_term"),
        "bonus_term_sum": sum_optional(frame, "reward_bonus_term"),
        "tail_offset_term_sum": sum_optional(frame, "reward_tail_offset_term"),
        "mean_ph": float(np.mean(frame["ph"])),
        "mean_target_ph": float(np.mean(frame["target_ph"])),
        "train_updates": int(frame["train_updated"].sum())
        if "train_updated" in frame
        else 0,
    }


def compute_summary_metrics(trajectory: pd.DataFrame) -> pd.DataFrame:
    warm = trajectory["is_warm_start"].astype(bool)
    test = trajectory["is_test"].astype(bool)
    summary = [metric_row("all_steps", trajectory)]
    if bool(warm.any()):
        summary.append(metric_row("hh_warm_start", trajectory[warm]))
    summary.extend(
        [
            metric_row("td3_training_steps", trajectory[(~warm) & (~test)]),
            metric_row("td3_eval_steps", trajectory[test]),
        ]
    )
    return pd.DataFrame(summary)


def compute_flow_diagnostics(trajectory: pd.DataFrame, config: dict) -> pd.DataFrame:
    process_config = config.get("process_config", {})
    specs = [
        ("acid", "acid_flow", "acid_flow_min", "acid_flow_max"),
        ("acetate", "acetate_flow", "acetate_flow_min", "acetate_flow_max"),
        ("water", "water_flow", "water_flow_min", "water_flow_max"),
    ]
    rows = []
    for label, column, low_key, high_key in specs:
        values = trajectory[column].to_numpy(float)
        deltas = np.diff(values)
        low = float_or_nan(process_config.get(low_key, 1.0))
        high = float_or_nan(process_config.get(high_key, 10.0))
        tol = 1e-7
        rows.append(
            {
                "flow": label,
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "p05": float(np.percentile(values, 5)),
                "p95": float(np.percentile(values, 95)),
                "lower_bound": low,
                "upper_bound": high,
                "lower_saturation_fraction": float(np.mean(values <= low + tol)),
                "upper_saturation_fraction": float(np.mean(values >= high - tol)),
                "mean_abs_step_change": float(np.mean(np.abs(deltas)))
                if deltas.size
                else 0.0,
                "max_abs_step_change": float(np.max(np.abs(deltas)))
                if deltas.size
                else 0.0,
            }
        )
    if "buffer_flow_sum" in trajectory:
        values = trajectory["buffer_flow_sum"].to_numpy(float)
        rollout = config.get("resolved_rollout", {})
        lower = float_or_nan(rollout.get("buffer_flow_sum_min", np.nan))
        upper = float_or_nan(rollout.get("buffer_flow_sum_max", np.nan))
        if not np.isfinite(lower) or not np.isfinite(upper):
            fixed = float_or_nan(rollout.get("fixed_buffer_flow_sum", np.nan))
            lower = fixed
            upper = fixed
        deltas = np.diff(values)
        rows.append(
            {
                "flow": "buffer_sum",
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "p05": float(np.percentile(values, 5)),
                "p95": float(np.percentile(values, 95)),
                "lower_bound": lower,
                "upper_bound": upper,
                "lower_saturation_fraction": np.nan,
                "upper_saturation_fraction": np.nan,
                "mean_abs_step_change": float(np.mean(np.abs(deltas)))
                if deltas.size
                else 0.0,
                "max_abs_step_change": float(np.max(np.abs(deltas)))
                if deltas.size
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def compute_hh_consistency(trajectory: pd.DataFrame) -> pd.DataFrame:
    residual = trajectory["hh_ratio_residual"].to_numpy(float)
    return pd.DataFrame(
        [
            {
                "check": "ideal_hh_ratio_consistency",
                "max_abs_residual": float(np.max(np.abs(residual))),
                "rmse_residual": float(np.sqrt(np.mean(residual**2))),
                "mean_abs_residual": float(np.mean(np.abs(residual))),
                "interpretation": (
                    "pH follows pKa + log10(F_acetate/F_acid) in the saved static environment"
                ),
            }
        ]
    )


def compute_setpoint_reward_metrics(trajectory: pd.DataFrame) -> pd.DataFrame:
    """Summarize reward and tracking quality for each held setpoint segment."""
    grouped = trajectory.groupby("cycle", as_index=False)
    return grouped.agg(
        target_ph=("target_ph", "first"),
        is_test=("is_test", "max"),
        start_step=("step", "min"),
        end_step=("step", "max"),
        steps=("step", "count"),
        mean_reward=("reward", "mean"),
        reward_sum=("reward", "sum"),
        mean_abs_error=("ph_error", lambda x: float(np.mean(np.abs(x)))),
        rmse=("ph_error", lambda x: float(np.sqrt(np.mean(np.square(x))))),
        max_abs_error=("ph_error", lambda x: float(np.max(np.abs(x)))),
    )


def save_figure(fig: plt.Figure, output_dir: Path, name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def reward_band_from_trajectory(trajectory: pd.DataFrame, fallback: float = 0.01) -> float:
    if "reward_band_ph" not in trajectory:
        return float(fallback)
    values = trajectory["reward_band_ph"].to_numpy(float)
    values = values[np.isfinite(values) & (values > 0.0)]
    if values.size == 0:
        return float(fallback)
    return float(np.median(values))


def boolean_spans(frame: pd.DataFrame, column: str) -> list[tuple[int, int]]:
    if column not in frame:
        return []
    mask = frame[column].astype(bool).to_numpy()
    steps = frame["step"].to_numpy(int)
    spans = []
    start = None
    last = None
    for flag, step in zip(mask, steps):
        if flag and start is None:
            start = int(step)
        if not flag and start is not None:
            spans.append((start, int(last)))
            start = None
        last = int(step)
    if start is not None and last is not None:
        spans.append((start, int(last)))
    return spans


def shade_protocol_regions(ax: plt.Axes, trajectory: pd.DataFrame) -> None:
    for start, end in boolean_spans(trajectory, "is_warm_start"):
        ax.axvspan(start, end, color="#D9D9D9", alpha=0.25)
    for start, end in boolean_spans(trajectory, "is_test"):
        ax.axvspan(start, end, color="#F2C14E", alpha=0.18)


def mark_setpoint_boundaries(ax: plt.Axes, trajectory: pd.DataFrame) -> None:
    for _, frame in trajectory.groupby("cycle"):
        start = int(frame["step"].min())
        ax.axvline(start, color="#BBBBBB", linewidth=0.55, alpha=0.65)


def plot_tracking_reward(trajectory: pd.DataFrame, output_dir: Path) -> Path:
    fig, axs = plt.subplots(4, 1, figsize=(10.5, 10.2), sharex=True)
    steps = trajectory["step"]
    reward_band = reward_band_from_trajectory(trajectory)

    axs[0].plot(steps, trajectory["ph"], color="#1F77B4", linewidth=1.8, label="pH")
    axs[0].step(
        steps,
        trajectory["target_ph"],
        where="post",
        color="#222222",
        linestyle="--",
        linewidth=1.3,
        label="target",
    )
    shade_protocol_regions(axs[0], trajectory)
    axs[0].set_ylabel("pH")
    axs[0].set_title("Offline TD3 pH Tracking")
    axs[0].grid(alpha=0.28)
    axs[0].legend(loc="best")

    axs[1].plot(steps, trajectory["ph_error"], color="#D55E00", linewidth=1.3)
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    axs[1].axhline(reward_band, color="#777777", linestyle=":", linewidth=0.9)
    axs[1].axhline(-reward_band, color="#777777", linestyle=":", linewidth=0.9)
    shade_protocol_regions(axs[1], trajectory)
    axs[1].set_ylabel("pH error")
    axs[1].grid(alpha=0.28)

    axs[2].plot(steps, trajectory["reward"], color="#009E73", linewidth=1.3)
    shade_protocol_regions(axs[2], trajectory)
    axs[2].set_ylabel("reward")
    axs[2].grid(alpha=0.28)

    axs[3].plot(
        steps,
        trajectory["reward_squared_error_cost"],
        color="#CC6677",
        linewidth=1.15,
        label="squared error",
    )
    axs[3].plot(
        steps,
        trajectory["reward_absolute_error_cost"],
        color="#4477AA",
        linewidth=1.15,
        label="absolute error",
    )
    axs[3].plot(
        steps,
        trajectory["reward_move_cost"],
        color="#AA4499",
        linewidth=1.15,
        label="action move cost",
    )
    if "reward_sum_move_cost" in trajectory:
        axs[3].plot(
            steps,
            trajectory["reward_sum_move_cost"],
            color="#E69F00",
            linewidth=1.15,
            label="sum-flow move cost",
        )
    shade_protocol_regions(axs[3], trajectory)
    axs[3].set_xlabel("step")
    axs[3].set_ylabel("raw costs")
    axs[3].grid(alpha=0.28)
    axs[3].legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_ph_tracking_error_reward.png")


def plot_flow_commands(trajectory: pd.DataFrame, output_dir: Path, config: dict) -> Path:
    process_config = config.get("process_config", {})
    steps = trajectory["step"]
    fig, axs = plt.subplots(3, 1, figsize=(10.5, 8.8), sharex=True)
    colors = {
        "acid_flow": "#CC6677",
        "acetate_flow": "#4477AA",
        "water_flow": "#228833",
    }
    labels = {
        "acid_flow": "acid",
        "acetate_flow": "acetate",
        "water_flow": "water",
    }
    for column, color in colors.items():
        axs[0].plot(
            steps,
            trajectory[column],
            color=color,
            linewidth=1.5,
            label=labels[column],
        )
    for low_key, high_key in [
        ("acid_flow_min", "acid_flow_max"),
        ("water_flow_min", "water_flow_max"),
    ]:
        low = float_or_nan(process_config.get(low_key, 1.0))
        high = float_or_nan(process_config.get(high_key, 10.0))
        axs[0].axhline(low, color="#777777", linestyle=":", linewidth=0.8)
        axs[0].axhline(high, color="#777777", linestyle=":", linewidth=0.8)
    shade_protocol_regions(axs[0], trajectory)
    axs[0].set_ylabel("flow (mL/min)")
    axs[0].set_title("TD3 Pump Commands (Water Fixed)")
    axs[0].grid(alpha=0.28)
    axs[0].legend(loc="best")

    if "buffer_flow_sum" in trajectory:
        rollout = config.get("resolved_rollout", {})
        sum_low = float_or_nan(rollout.get("buffer_flow_sum_min", np.nan))
        sum_high = float_or_nan(rollout.get("buffer_flow_sum_max", np.nan))
        fixed_sum = float_or_nan(rollout.get("fixed_buffer_flow_sum", np.nan))
        axs[1].plot(
            steps,
            trajectory["buffer_flow_sum"],
            color="#E69F00",
            linewidth=1.4,
            label="acid + acetate",
        )
        if np.isfinite(sum_low) and np.isfinite(sum_high):
            axs[1].axhline(sum_low, color="#777777", linestyle=":", linewidth=0.8)
            axs[1].axhline(sum_high, color="#777777", linestyle=":", linewidth=0.8)
        elif np.isfinite(fixed_sum):
            axs[1].axhline(fixed_sum, color="#777777", linestyle=":", linewidth=0.8)
        shade_protocol_regions(axs[1], trajectory)
        axs[1].set_ylabel("buffer sum")
        axs[1].grid(alpha=0.28)
        axs[1].legend(loc="best")

    axs[2].plot(
        steps,
        trajectory["log10_flow_ratio"],
        color="#AA4499",
        linewidth=1.5,
        label="log10(acetate/acid)",
    )
    axs[2].axhline(0.0, color="#222222", linewidth=0.8)
    shade_protocol_regions(axs[2], trajectory)
    axs[2].set_xlabel("step")
    axs[2].set_ylabel("log flow ratio")
    axs[2].grid(alpha=0.28)
    axs[2].legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_flow_commands_and_ratio.png")


def plot_cycle_metrics(episode_metrics: pd.DataFrame, output_dir: Path) -> Path:
    fig, axs = plt.subplots(2, 1, figsize=(10.0, 6.8), sharex=True)
    x = episode_metrics["cycle"].to_numpy(int)
    width = 0.36
    mean_reward = (
        episode_metrics["mean_reward"].to_numpy(float)
        if "mean_reward" in episode_metrics
        else episode_metrics["reward_sum"].to_numpy(float)
        / np.maximum(episode_metrics["steps"].to_numpy(float), 1.0)
    )
    axs[0].bar(
        x - width / 2,
        episode_metrics["mean_abs_error"],
        width=width,
        color="#4477AA",
        label="MAE",
    )
    axs[0].bar(
        x + width / 2,
        episode_metrics["rmse"],
        width=width,
        color="#EE6677",
        label="RMSE",
    )
    axs[0].set_ylabel("pH error")
    axs[0].set_title("Per-Setpoint Tracking Metrics")
    axs[0].grid(axis="y", alpha=0.28)
    axs[0].legend(loc="best")

    axs[1].plot(
        x,
        mean_reward,
        color="#228833",
        linewidth=1.4,
        marker="o",
        markersize=3.2,
        markerfacecolor="#FFFFFF",
        markeredgewidth=0.8,
    )
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    axs[1].set_xlabel("setpoint cycle")
    axs[1].set_ylabel("mean reward")
    axs[1].grid(axis="y", alpha=0.28)
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_cycle_metrics.png")


def plot_setpoint_average_reward(
    setpoint_rewards: pd.DataFrame,
    output_dir: Path,
) -> Path:
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    x = setpoint_rewards["cycle"].to_numpy(int)
    y = setpoint_rewards["mean_reward"].to_numpy(float)
    is_test = setpoint_rewards["is_test"].astype(bool).to_numpy()

    train_mask = ~is_test
    ax.plot(
        x,
        y,
        color="#444444",
        linewidth=1.1,
        alpha=0.75,
        zorder=1,
    )
    if train_mask.any():
        ax.scatter(
            x[train_mask],
            y[train_mask],
            s=28,
            color="#228833",
            edgecolor="#222222",
            linewidth=0.25,
            label="training setpoint hold",
            zorder=2,
        )
    if is_test.any():
        ax.scatter(
            x[is_test],
            y[is_test],
            s=42,
            color="#E69F00",
            edgecolor="#222222",
            linewidth=0.35,
            label="evaluation setpoint hold",
            zorder=3,
        )
    ax.axhline(0.0, color="#222222", linewidth=0.8)
    ax.set_xlabel("setpoint cycle")
    ax.set_ylabel("average reward per step")
    ax.set_title("Average Reward Per Setpoint Hold")
    ax.grid(axis="y", alpha=0.28)
    ax.legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_setpoint_average_reward.png")


def select_last_setpoint_cycles(
    trajectory: pd.DataFrame,
    n_cycles: int = 5,
) -> pd.DataFrame:
    cycles = np.sort(trajectory["cycle"].unique())
    keep = set(cycles[-max(1, int(n_cycles)) :])
    return trajectory[trajectory["cycle"].isin(keep)].copy()


def plot_last_setpoint_tracking(
    trajectory: pd.DataFrame,
    output_dir: Path,
    n_cycles: int = 5,
) -> Path:
    subset = select_last_setpoint_cycles(trajectory, n_cycles=n_cycles)
    steps = subset["step"]
    reward_band = reward_band_from_trajectory(subset)
    fig, axs = plt.subplots(5, 1, figsize=(10.8, 12.4), sharex=True)

    axs[0].plot(steps, subset["ph"], color="#1F77B4", linewidth=1.8, label="pH")
    axs[0].step(
        steps,
        subset["target_ph"],
        where="post",
        color="#222222",
        linestyle="--",
        linewidth=1.3,
        label="target",
    )
    axs[0].set_ylabel("pH")
    axs[0].set_title(f"Last {subset['cycle'].nunique()} Setpoint Holds")
    axs[0].grid(alpha=0.28)
    axs[0].legend(loc="best")

    axs[1].plot(steps, subset["ph_error"], color="#D55E00", linewidth=1.3)
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    axs[1].axhline(reward_band, color="#777777", linestyle=":", linewidth=0.9)
    axs[1].axhline(-reward_band, color="#777777", linestyle=":", linewidth=0.9)
    axs[1].set_ylabel("pH error")
    axs[1].grid(alpha=0.28)

    axs[2].plot(steps, subset["reward"], color="#009E73", linewidth=1.3)
    axs[2].axhline(0.0, color="#222222", linewidth=0.8)
    axs[2].set_ylabel("reward")
    axs[2].grid(alpha=0.28)

    axs[3].plot(steps, subset["acid_flow"], color="#CC6677", linewidth=1.3, label="acid")
    axs[3].plot(
        steps,
        subset["acetate_flow"],
        color="#4477AA",
        linewidth=1.3,
        label="acetate",
    )
    axs[3].plot(steps, subset["water_flow"], color="#228833", linewidth=1.2, label="water")
    axs[3].set_ylabel("flow (mL/min)")
    axs[3].grid(alpha=0.28)
    axs[3].legend(loc="best")

    if "action_ratio" in subset:
        axs[4].plot(
            steps,
            subset["action_ratio"],
            color="#AA4499",
            linewidth=1.3,
            label="ratio action",
        )
        if "action_buffer_sum" in subset:
            axs[4].plot(
                steps,
                subset["action_buffer_sum"],
                color="#E69F00",
                linewidth=1.2,
                label="sum action",
            )
        axs[4].axhline(1.0, color="#777777", linestyle=":", linewidth=0.8)
        axs[4].axhline(-1.0, color="#777777", linestyle=":", linewidth=0.8)
        axs[4].set_ylabel("action")
    else:
        axs[4].plot(
            steps,
            subset["log10_flow_ratio"],
            color="#AA4499",
            linewidth=1.3,
            label="log10(acetate/acid)",
        )
        axs[4].set_ylabel("log ratio")
    if "exploration_sigma" in subset:
        axs[4].plot(
            steps,
            subset["exploration_sigma"],
            color="#0072B2",
            linewidth=1.0,
            alpha=0.75,
            label="noise sigma",
        )
    axs[4].set_xlabel("step")
    axs[4].grid(alpha=0.28)
    axs[4].legend(loc="best")

    for ax in axs:
        mark_setpoint_boundaries(ax, subset)
        shade_protocol_regions(ax, subset)
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_last_5_setpoint_tracking.png")


def plot_action_diagnostics(trajectory: pd.DataFrame, output_dir: Path) -> Path:
    has_exploration = (
        "exploration_sigma" in trajectory
        or "exploration_magnitude" in trajectory
        or "action_saturation_fraction" in trajectory
    )
    row_count = 3 if has_exploration else 2
    fig, axs = plt.subplots(row_count, 1, figsize=(10.5, 9.4 if has_exploration else 7.2))
    steps = trajectory["step"]
    action_specs = [
        ("action_ratio", "#AA4499", "ratio action"),
        ("action_buffer_sum", "#E69F00", "sum action"),
        ("action_acid", "#CC6677", "acid action"),
        ("action_acetate", "#4477AA", "acetate action"),
        ("action_water", "#228833", "water action"),
    ]
    for column, color, label in action_specs:
        if column not in trajectory:
            continue
        axs[0].plot(steps, trajectory[column], color=color, linewidth=1.3, label=label)
    axs[0].axhline(1.0, color="#777777", linestyle=":", linewidth=0.8)
    axs[0].axhline(-1.0, color="#777777", linestyle=":", linewidth=0.8)
    shade_protocol_regions(axs[0], trajectory)
    axs[0].set_ylabel("normalized action")
    axs[0].set_title("Action-Space Diagnostics")
    axs[0].grid(alpha=0.28)
    axs[0].legend(loc="best")

    if "action_ratio" in trajectory and "action_buffer_sum" in trajectory:
        scatter = axs[1].scatter(
            trajectory["action_ratio"],
            trajectory["action_buffer_sum"],
            c=trajectory["abs_ph_error"],
            cmap="viridis",
            s=34,
            edgecolor="#222222",
            linewidth=0.25,
        )
        axs[1].set_xlabel("ratio action")
        axs[1].set_ylabel("sum action")
        axs[1].set_xlim(-1.05, 1.05)
        axs[1].set_ylim(-1.05, 1.05)
    elif "action_ratio" in trajectory:
        scatter = axs[1].scatter(
            trajectory["action_ratio"],
            trajectory["log10_flow_ratio"],
            c=trajectory["abs_ph_error"],
            cmap="viridis",
            s=34,
            edgecolor="#222222",
            linewidth=0.25,
        )
        axs[1].set_xlabel("ratio action")
        axs[1].set_ylabel("log10(acetate/acid)")
        axs[1].set_xlim(-1.05, 1.05)
    else:
        scatter = axs[1].scatter(
            trajectory["action_acid"],
            trajectory["action_acetate"],
            c=trajectory["abs_ph_error"],
            cmap="viridis",
            s=34,
            edgecolor="#222222",
            linewidth=0.25,
        )
        axs[1].set_xlabel("acid action")
        axs[1].set_ylabel("acetate action")
        axs[1].set_xlim(-1.05, 1.05)
        axs[1].set_ylim(-1.05, 1.05)
    axs[1].grid(alpha=0.28)
    fig.colorbar(scatter, ax=axs[1], label="absolute pH error")
    if has_exploration:
        if "exploration_sigma" in trajectory:
            axs[2].plot(
                steps,
                trajectory["exploration_sigma"],
                color="#0072B2",
                linewidth=1.3,
                label="noise sigma",
            )
        if "exploration_magnitude" in trajectory:
            axs[2].plot(
                steps,
                trajectory["exploration_magnitude"],
                color="#D55E00",
                linewidth=1.3,
                label="mean |noise|",
            )
        if "action_saturation_fraction" in trajectory:
            axs[2].plot(
                steps,
                trajectory["action_saturation_fraction"],
                color="#009E73",
                linewidth=1.1,
                label="saturation fraction",
            )
        shade_protocol_regions(axs[2], trajectory)
        axs[2].set_xlabel("step")
        axs[2].set_ylabel("exploration")
        axs[2].grid(alpha=0.28)
        axs[2].legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_action_diagnostics.png")


def plot_hh_ratio_consistency(
    trajectory: pd.DataFrame,
    output_dir: Path,
    config: dict,
) -> Path:
    process_config = config.get("process_config", {})
    pka = float_or_nan(process_config.get("pKa", 4.76))
    x = trajectory["log10_flow_ratio"].to_numpy(float)
    x_line = np.linspace(float(np.min(x)), float(np.max(x)), 200)
    y_line = pka + x_line

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    water_values = trajectory["water_flow"].to_numpy(float)
    water_range = float(np.nanmax(water_values) - np.nanmin(water_values))
    if water_range <= 1e-9:
        scatter = None
        ax.scatter(
            trajectory["log10_flow_ratio"],
            trajectory["ph"],
            color="#AA4499",
            s=42,
            edgecolor="#222222",
            linewidth=0.25,
            label=f"simulated steps, water={water_values[0]:.2f} mL/min",
        )
    else:
        scatter = ax.scatter(
            trajectory["log10_flow_ratio"],
            trajectory["ph"],
            c=trajectory["water_flow"],
            cmap="plasma",
            s=42,
            edgecolor="#222222",
            linewidth=0.25,
            label="simulated steps",
        )
    ax.plot(
        x_line,
        y_line,
        color="#222222",
        linestyle="--",
        linewidth=1.4,
        label="ideal HH line",
    )
    ax.set_xlabel("log10(F_acetate / F_acid)")
    ax.set_ylabel("pH")
    ax.set_title("Ideal Henderson-Hasselbalch Ratio Check")
    ax.grid(alpha=0.28)
    ax.legend(loc="best")
    if scatter is not None:
        fig.colorbar(scatter, ax=ax, label="water flow (mL/min)")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_hh_ratio_consistency.png")


def plot_training_losses(trajectory: pd.DataFrame, output_dir: Path) -> Path | None:
    train_rows = trajectory[trajectory["train_updated"].astype(bool)].copy()
    if train_rows.empty:
        return None
    has_critic = "critic_loss" in train_rows and train_rows["critic_loss"].notna().any()
    has_actor = "actor_loss" in train_rows and train_rows["actor_loss"].notna().any()
    if not has_critic and not has_actor:
        return None

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    if has_critic:
        ax.plot(
            train_rows["step"],
            train_rows["critic_loss"],
            color="#0072B2",
            linewidth=1.4,
            label="critic loss",
        )
    if has_actor:
        ax.plot(
            train_rows["step"],
            train_rows["actor_loss"],
            color="#D55E00",
            linewidth=1.4,
            label="actor loss",
        )
    ax.set_xlabel("step")
    ax.set_ylabel("loss")
    ax.set_title("TD3 Train-Step Loss Trace")
    ax.grid(alpha=0.28)
    ax.legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_training_losses.png")


def reward_config_from_snapshot(config: dict) -> PHRewardConfig:
    reward_data = config.get("resolved_rollout", {}).get("reward_config", {})
    if not isinstance(reward_data, dict) or not reward_data:
        reward_data = {"mode": "relative_band_offset"}
    return PHRewardConfig(**reward_data)


def plot_reward_shape_comparison(output_dir: Path, config: dict) -> Path:
    process_config = config.get("process_config", {})
    target_ph = float_or_nan(process_config.get("pKa", 4.76))
    if not np.isfinite(target_ph):
        target_ph = 4.76
    base_cfg = reward_config_from_snapshot(config)
    if base_cfg.mode == "three_term":
        base_cfg = replace(base_cfg, mode="relative_band_offset")

    rollout = config.get("resolved_rollout", {})
    buffer_sum_min = float_or_nan(rollout.get("buffer_flow_sum_min", 2.0))
    buffer_sum_max = float_or_nan(rollout.get("buffer_flow_sum_max", 20.0))
    fixed_sum = float_or_nan(rollout.get("fixed_buffer_flow_sum", 15.0))
    if not np.isfinite(buffer_sum_min):
        buffer_sum_min = 2.0
    if not np.isfinite(buffer_sum_max):
        buffer_sum_max = 20.0
    if not np.isfinite(fixed_sum):
        fixed_sum = 15.0

    errors = np.linspace(-0.05, 0.05, 401)
    action = np.zeros(2, dtype=np.float32)
    previous_action = np.zeros(2, dtype=np.float32)
    curves = [
        ("full shaped", base_cfg, "#0072B2"),
        ("no bonus", replace(base_cfg, beta=0.0), "#D55E00"),
        (
            "no linear terms",
            replace(base_cfg, gamma_out=0.0, gamma_in=0.0),
            "#009E73",
        ),
        (
            "no bonus or linear",
            replace(base_cfg, beta=0.0, gamma_out=0.0, gamma_in=0.0),
            "#AA4499",
        ),
    ]

    fig, axs = plt.subplots(
        2,
        1,
        figsize=(8.8, 7.4),
        sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.0]},
    )
    reward_curves: dict[str, np.ndarray] = {}
    for label, cfg, color in curves:
        rewards = np.array(
            [
                compute_ph_reward(
                    target_ph=target_ph,
                    ph=target_ph + float(error),
                    action=action,
                    previous_action=previous_action,
                    config=cfg,
                    hold_progress=1.0,
                    buffer_sum=fixed_sum,
                    previous_buffer_sum=fixed_sum,
                    buffer_sum_min=buffer_sum_min,
                    buffer_sum_max=buffer_sum_max,
                ).reward
                for error in errors
            ],
            dtype=float,
        )
        reward_curves[label] = rewards
        axs[0].plot(errors, rewards, color=color, linewidth=1.8, label=label)

    band = base_cfg.band_floor_ph
    for ax in axs:
        ax.axvline(0.0, color="#222222", linewidth=0.8)
        ax.axvline(band, color="#777777", linestyle=":", linewidth=0.9)
        ax.axvline(-band, color="#777777", linestyle=":", linewidth=0.9)
        ax.grid(alpha=0.28)
    axs[0].set_ylabel("instantaneous reward")
    axs[0].set_title("Shaped Reward Components Around Setpoint")
    axs[0].legend(loc="best")

    full = reward_curves["full shaped"]
    delta_specs = [
        ("bonus contribution", full - reward_curves["no bonus"], "#D55E00"),
        (
            "linear contribution",
            full - reward_curves["no linear terms"],
            "#009E73",
        ),
        (
            "bonus + linear contribution",
            full - reward_curves["no bonus or linear"],
            "#AA4499",
        ),
    ]
    for label, delta, color in delta_specs:
        axs[1].plot(errors, delta, color=color, linewidth=1.5, label=label)
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    axs[1].set_xlabel("logged pH error, pH - target")
    axs[1].set_ylabel("reward delta")
    axs[1].legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_reward_shape_comparison.png")


def write_result_artifact_manifest(
    output_dir: Path,
    figures: list[Path],
    tables: list[Path],
) -> Path:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_dir": str(output_dir),
        "figures": [str(path.relative_to(output_dir)) for path in figures],
        "tables": [str(path.relative_to(output_dir)) for path in tables],
        "simulation_only": True,
        "uses_biosmb_or_emulator": False,
    }
    path = output_dir / "tables" / "result_artifact_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def save_offline_ph_td3_result_artifacts(
    output_dir: Path,
    trajectory: pd.DataFrame,
    episode_metrics: pd.DataFrame,
    training_summary: pd.DataFrame,
    config: dict,
) -> dict[str, list[Path] | Path | pd.DataFrame]:
    """Save reusable TD3 pH diagnostics inside a runner result directory."""
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    diagnostic_trajectory = add_hh_consistency_columns(trajectory, config)
    summary_metrics = compute_summary_metrics(diagnostic_trajectory)
    flow_diagnostics = compute_flow_diagnostics(diagnostic_trajectory, config)
    hh_consistency = compute_hh_consistency(diagnostic_trajectory)
    setpoint_reward_metrics = compute_setpoint_reward_metrics(diagnostic_trajectory)

    diagnostic_trajectory_path = tables_dir / "trajectory_diagnostics.csv"
    summary_metrics_path = tables_dir / "summary_metrics.csv"
    flow_diagnostics_path = tables_dir / "flow_diagnostics.csv"
    hh_consistency_path = tables_dir / "hh_consistency.csv"
    setpoint_reward_metrics_path = tables_dir / "setpoint_reward_metrics.csv"
    source_training_summary_path = tables_dir / "source_training_summary.csv"

    diagnostic_trajectory.to_csv(diagnostic_trajectory_path, index=False)
    summary_metrics.to_csv(summary_metrics_path, index=False)
    flow_diagnostics.to_csv(flow_diagnostics_path, index=False)
    hh_consistency.to_csv(hh_consistency_path, index=False)
    setpoint_reward_metrics.to_csv(setpoint_reward_metrics_path, index=False)
    training_summary.to_csv(source_training_summary_path, index=False)

    figures = [
        plot_tracking_reward(diagnostic_trajectory, figures_dir),
        plot_flow_commands(diagnostic_trajectory, figures_dir, config),
        plot_cycle_metrics(episode_metrics, figures_dir),
        plot_setpoint_average_reward(setpoint_reward_metrics, figures_dir),
        plot_last_setpoint_tracking(diagnostic_trajectory, figures_dir),
        plot_action_diagnostics(diagnostic_trajectory, figures_dir),
        plot_hh_ratio_consistency(diagnostic_trajectory, figures_dir, config),
        plot_reward_shape_comparison(figures_dir, config),
    ]
    loss_figure = plot_training_losses(diagnostic_trajectory, figures_dir)
    if loss_figure is not None:
        figures.append(loss_figure)

    tables = [
        diagnostic_trajectory_path,
        summary_metrics_path,
        flow_diagnostics_path,
        hh_consistency_path,
        setpoint_reward_metrics_path,
        source_training_summary_path,
    ]
    manifest_path = write_result_artifact_manifest(output_dir, figures, tables)
    tables.append(manifest_path)

    return {
        "figures_dir": figures_dir,
        "tables_dir": tables_dir,
        "figures": figures,
        "tables": tables,
        "diagnostic_trajectory": diagnostic_trajectory,
        "summary_metrics": summary_metrics,
        "flow_diagnostics": flow_diagnostics,
        "hh_consistency": hh_consistency,
        "setpoint_reward_metrics": setpoint_reward_metrics,
    }
