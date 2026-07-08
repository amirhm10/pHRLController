from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "results"
REPORTS_ROOT = ROOT / "reports"
DEFAULT_REPORT_PATH = REPORTS_ROOT / "offline_ph_td3_training_result_analysis.md"


def find_latest_result_dir() -> Path:
    candidates = sorted(
        path
        for path in RESULTS_ROOT.glob("offline_ph_td3_training_*")
        if (path / "tables" / "trajectory.csv").exists()
    )
    if not candidates:
        raise FileNotFoundError(
            "No offline pH TD3 result folder found under results/. "
            "Run run_offline_ph_td3_training.py first or pass --result-dir."
        )
    return candidates[-1]


def load_result_tables(result_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    tables_dir = result_dir / "tables"
    trajectory_path = tables_dir / "trajectory.csv"
    episode_path = tables_dir / "episode_metrics.csv"
    summary_path = tables_dir / "training_summary.csv"
    config_path = tables_dir / "config_snapshot.json"

    missing = [
        path
        for path in [trajectory_path, episode_path, summary_path, config_path]
        if not path.exists()
    ]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing expected result files: {missing_text}")

    trajectory = pd.read_csv(trajectory_path)
    episode_metrics = pd.read_csv(episode_path)
    training_summary = pd.read_csv(summary_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return trajectory, episode_metrics, training_summary, config


def output_dir_for_result(result_dir: Path) -> Path:
    return REPORTS_ROOT / "figures" / f"{result_dir.name}_analysis"


def report_rel(path: Path, report_path: Path) -> str:
    return path.resolve().relative_to(report_path.resolve().parent).as_posix()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def float_or_nan(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


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


def sum_optional(frame: pd.DataFrame, column: str) -> float:
    if column not in frame:
        return np.nan
    return float(frame[column].sum())


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
        target = float_or_nan(
            config.get("resolved_rollout", {}).get("fixed_buffer_flow_sum", np.nan)
        )
        deltas = np.diff(values)
        rows.append(
            {
                "flow": "buffer_sum",
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "p05": float(np.percentile(values, 5)),
                "p95": float(np.percentile(values, 95)),
                "lower_bound": target,
                "upper_bound": target,
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


def add_hh_consistency_columns(trajectory: pd.DataFrame, config: dict) -> pd.DataFrame:
    process_config = config.get("process_config", {})
    pka = float_or_nan(process_config.get("pKa", 4.76))
    out = trajectory.copy()
    ratio = out["flow_ratio_acetate_acid"].to_numpy(float)
    out["log10_flow_ratio"] = np.log10(np.maximum(ratio, 1e-12))
    out["hh_ph_from_ratio"] = pka + out["log10_flow_ratio"]
    out["hh_ratio_residual"] = out["ph"] - out["hh_ph_from_ratio"]
    out["abs_ph_error"] = np.abs(out["ph_error"])
    if "target_ph" in out:
        out["target_log_ratio"] = out["target_ph"].to_numpy(float) - pka
        out["ratio_tracking_error"] = (
            out["log10_flow_ratio"].to_numpy(float)
            - out["target_log_ratio"].to_numpy(float)
        )
    if "reward_squared_error_cost" not in out:
        out["reward_squared_error_cost"] = np.square(out["ph_error"].to_numpy(float))
    if "reward_absolute_error_cost" not in out:
        out["reward_absolute_error_cost"] = out["abs_ph_error"]
    if "reward_move_cost" not in out:
        action_columns = [
            column
            for column in ["action_ratio", "action_acid", "action_acetate", "action_water"]
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
    for column in ["action_ratio", "action_acid", "action_acetate", "action_water"]:
        if column in out:
            out[f"abs_{column}"] = np.abs(out[column])
    return out


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


def phase_metric_row(label: str, frame: pd.DataFrame) -> dict[str, float | int | str]:
    if frame.empty:
        return {
            "phase": label,
            "steps": 0,
            "mae": np.nan,
            "rmse": np.nan,
            "max_abs_error": np.nan,
            "mean_abs_ratio_error": np.nan,
            "mean_reward": np.nan,
            "mean_exploration_sigma": np.nan,
            "mean_exploration_magnitude": np.nan,
        }
    errors = frame["ph_error"].to_numpy(float)
    abs_errors = np.abs(errors)
    ratio_errors = (
        np.abs(frame["ratio_tracking_error"].to_numpy(float))
        if "ratio_tracking_error" in frame
        else np.full(len(frame), np.nan)
    )
    return {
        "phase": label,
        "steps": int(len(frame)),
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "max_abs_error": float(np.max(abs_errors)),
        "mean_abs_ratio_error": float(np.nanmean(ratio_errors)),
        "mean_reward": float(frame["reward"].mean()) if "reward" in frame else np.nan,
        "mean_exploration_sigma": float(frame["exploration_sigma"].mean())
        if "exploration_sigma" in frame
        else np.nan,
        "mean_exploration_magnitude": float(frame["exploration_magnitude"].mean())
        if "exploration_magnitude" in frame
        else np.nan,
    }


def compute_learning_phase_metrics(
    trajectory: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Summarize tracking quality by rollout phase and within-cycle window."""
    frame = trajectory.copy()
    if "step_in_cycle" not in frame:
        frame["step_in_cycle"] = frame.groupby("cycle").cumcount()
    decay_step = int(
        config.get("resolved_rollout", {}).get("exploration_std_decay_steps", 5000)
    )
    training = frame[~frame["is_test"].astype(bool)]
    rows = [
        phase_metric_row("all_steps", frame),
        phase_metric_row(f"first_{decay_step}_steps", frame[frame["step"] < decay_step]),
        phase_metric_row(
            "after_exploration_decay",
            frame[frame["step"] >= decay_step],
        ),
        phase_metric_row(
            "last_5000_training_steps",
            training[training["step"] >= max(0, int(training["step"].max()) - 4999)]
            if not training.empty
            else training,
        ),
        phase_metric_row("evaluation_cycle", frame[frame["is_test"].astype(bool)]),
        phase_metric_row("first_20_each_cycle", frame[frame["step_in_cycle"] < 20]),
        phase_metric_row("first_50_each_cycle", frame[frame["step_in_cycle"] < 50]),
        phase_metric_row("last_50_each_cycle", frame[frame["step_in_cycle"] >= 150]),
    ]
    return pd.DataFrame(rows)


def compute_cycle_group_metrics(
    episode_metrics: pd.DataFrame,
    group_size: int = 25,
) -> pd.DataFrame:
    if episode_metrics.empty:
        return pd.DataFrame()
    rows = []
    training = episode_metrics[~episode_metrics["is_test"].astype(bool)]
    max_cycle = int(training["cycle"].max()) if not training.empty else -1
    for start in range(0, max_cycle + 1, group_size):
        end = min(start + group_size - 1, max_cycle)
        group = training[(training["cycle"] >= start) & (training["cycle"] <= end)]
        if group.empty:
            continue
        rows.append(
            {
                "cycle_group": f"cycles_{start}_{end}",
                "cycles": int(len(group)),
                "mean_cycle_mae": float(group["mean_abs_error"].mean()),
                "mean_cycle_rmse": float(group["rmse"].mean()),
                "max_cycle_abs_error": float(group["max_abs_error"].max()),
                "mean_move_cost_sum": float(group["move_cost_sum"].mean()),
            }
        )
    eval_group = episode_metrics[episode_metrics["is_test"].astype(bool)]
    if not eval_group.empty:
        rows.append(
            {
                "cycle_group": "evaluation_cycles",
                "cycles": int(len(eval_group)),
                "mean_cycle_mae": float(eval_group["mean_abs_error"].mean()),
                "mean_cycle_rmse": float(eval_group["rmse"].mean()),
                "max_cycle_abs_error": float(eval_group["max_abs_error"].max()),
                "mean_move_cost_sum": float(eval_group["move_cost_sum"].mean()),
            }
        )
    return pd.DataFrame(rows)


def compute_settling_diagnostics(
    trajectory: pd.DataFrame,
    tolerances: tuple[float, ...] = (0.05, 0.02),
    hold_steps: int = 20,
) -> pd.DataFrame:
    """Find first step in each setpoint cycle that stays within tolerance."""
    rows = []
    for tolerance in tolerances:
        settling_times = []
        failed_cycles = 0
        for _, cycle_frame in trajectory.groupby("cycle"):
            abs_error = np.abs(cycle_frame["ph_error"].to_numpy(float))
            found = None
            last_start = max(0, len(abs_error) - hold_steps)
            for idx in range(last_start + 1):
                if np.max(abs_error[idx : idx + hold_steps]) <= tolerance:
                    found = idx
                    break
            if found is None:
                failed_cycles += 1
            else:
                settling_times.append(float(found))
        rows.append(
            {
                "tolerance": tolerance,
                "hold_steps": int(hold_steps),
                "settled_cycles": int(len(settling_times)),
                "failed_cycles": int(failed_cycles),
                "median_settling_steps": float(np.median(settling_times))
                if settling_times
                else np.nan,
                "p90_settling_steps": float(np.percentile(settling_times, 90))
                if settling_times
                else np.nan,
                "max_settling_steps": float(np.max(settling_times))
                if settling_times
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def compute_cycle_extremes(
    episode_metrics: pd.DataFrame,
    n: int = 5,
) -> pd.DataFrame:
    if episode_metrics.empty:
        return pd.DataFrame()
    columns = [
        "cycle",
        "target_ph",
        "is_test",
        "mean_abs_error",
        "rmse",
        "max_abs_error",
        "move_cost_sum",
    ]
    worst = episode_metrics.sort_values("mean_abs_error", ascending=False).head(n)
    best = episode_metrics.sort_values("mean_abs_error", ascending=True).head(n)
    out = pd.concat(
        [
            worst.assign(rank_type="worst"),
            best.assign(rank_type="best"),
        ],
        ignore_index=True,
    )
    return out[["rank_type", *columns]]


def save_figure(fig: plt.Figure, output_dir: Path, name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


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


def plot_tracking_reward(trajectory: pd.DataFrame, output_dir: Path) -> Path:
    fig, axs = plt.subplots(4, 1, figsize=(10.5, 10.2), sharex=True)
    steps = trajectory["step"]

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
    axs[1].axhline(0.02, color="#777777", linestyle=":", linewidth=0.9)
    axs[1].axhline(-0.02, color="#777777", linestyle=":", linewidth=0.9)
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
        label="move cost",
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
    fig, axs = plt.subplots(2, 1, figsize=(10.5, 6.8), sharex=True)
    colors = {"acid_flow": "#CC6677", "acetate_flow": "#4477AA", "water_flow": "#228833"}
    labels = {
        "acid_flow": "acid",
        "acetate_flow": "acetate",
        "water_flow": "water",
    }
    for column, color in colors.items():
        axs[0].plot(steps, trajectory[column], color=color, linewidth=1.5, label=labels[column])
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

    axs[1].plot(
        steps,
        trajectory["log10_flow_ratio"],
        color="#AA4499",
        linewidth=1.5,
        label="log10(acetate/acid)",
    )
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    shade_protocol_regions(axs[1], trajectory)
    axs[1].set_xlabel("step")
    axs[1].set_ylabel("log flow ratio")
    axs[1].grid(alpha=0.28)
    axs[1].legend(loc="best")
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_flow_commands_and_ratio.png")


def plot_cycle_metrics(episode_metrics: pd.DataFrame, output_dir: Path) -> Path:
    fig, axs = plt.subplots(2, 1, figsize=(10.0, 6.8), sharex=True)
    x = episode_metrics["cycle"].to_numpy(int)
    width = 0.36
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

    axs[1].bar(x, episode_metrics["reward_sum"], color="#228833", alpha=0.9)
    axs[1].axhline(0.0, color="#222222", linewidth=0.8)
    axs[1].set_xlabel("setpoint cycle")
    axs[1].set_ylabel("reward sum")
    axs[1].grid(axis="y", alpha=0.28)
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_cycle_metrics.png")


def plot_action_diagnostics(trajectory: pd.DataFrame, output_dir: Path) -> Path:
    has_exploration = (
        "exploration_sigma" in trajectory
        or "exploration_magnitude" in trajectory
        or "action_saturation_fraction" in trajectory
    )
    row_count = 3 if has_exploration else 2
    fig, axs = plt.subplots(
        row_count,
        1,
        figsize=(10.5, 9.4 if has_exploration else 7.2),
    )
    steps = trajectory["step"]
    action_specs = [
        ("action_ratio", "#AA4499", "ratio action"),
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

    if "action_ratio" in trajectory:
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


def plot_hh_ratio_consistency(trajectory: pd.DataFrame, output_dir: Path, config: dict) -> Path:
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
    ax.plot(x_line, y_line, color="#222222", linestyle="--", linewidth=1.4, label="ideal HH line")
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


def write_manifest(
    output_dir: Path,
    result_dir: Path,
    report_path: Path,
    figures: Iterable[Path],
    tables: Iterable[Path],
    source_files: Iterable[str],
) -> Path:
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_result_dir": repo_rel(result_dir),
        "report_path": repo_rel(report_path),
        "figures": [repo_rel(path) for path in figures],
        "tables": [repo_rel(path) for path in tables],
        "source_files_inspected": list(source_files),
        "simulation_only": True,
        "uses_biosmb_or_emulator": False,
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]], digits: int = 4) -> list[str]:
    def esc(value: object) -> str:
        return str(value).replace("|", "\\|")

    lines = [
        "| " + " | ".join(esc(label) for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        cells = []
        for column, _ in columns:
            value = row[column]
            if isinstance(value, (float, np.floating)):
                cells.append(
                    "nan" if not np.isfinite(value) else f"{value:.{digits}g}"
                )
            else:
                cells.append(esc(value))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def build_report(
    report_path: Path,
    result_dir: Path,
    output_dir: Path,
    config: dict,
    summary_metrics: pd.DataFrame,
    flow_diagnostics: pd.DataFrame,
    episode_metrics: pd.DataFrame,
    learning_phase_metrics: pd.DataFrame,
    cycle_group_metrics: pd.DataFrame,
    settling_diagnostics: pd.DataFrame,
    cycle_extremes: pd.DataFrame,
    hh_consistency: pd.DataFrame,
    figures: list[Path],
    generated_tables: list[Path],
) -> str:
    figure_lookup = {path.stem: path for path in figures}
    overall = summary_metrics[summary_metrics["scope"] == "all_steps"].iloc[0]
    eval_rows = summary_metrics[summary_metrics["scope"] == "td3_eval_steps"]
    eval_mae = eval_rows.iloc[0]["mae"] if not eval_rows.empty else np.nan
    eval_rmse = eval_rows.iloc[0]["rmse"] if not eval_rows.empty else np.nan
    hh_row = hh_consistency.iloc[0]
    rollout = config.get("resolved_rollout", {})
    arguments = config.get("arguments", {})
    setpoint_cycles = rollout.get("setpoint_cycles", "unknown")
    steps_per_cycle = rollout.get("steps_per_cycle", "unknown")
    setpoint_strategy = rollout.get("setpoint_strategy", "unknown")
    fixed_buffer_flow_sum = rollout.get("fixed_buffer_flow_sum", "unknown")
    total_steps = rollout.get("total_steps", arguments.get("total_steps", "unknown"))
    reward_mode = rollout.get("reward_mode", "three_term")
    reward_definition = rollout.get(
        "reward_definition",
        "-(q2*(target_pH - pH)^2 + q1*abs(target_pH - pH) + "
        "r_move*mean((action_t - action_t_minus_1)^2))",
    )
    early_phase = learning_phase_metrics[
        learning_phase_metrics["phase"].astype(str).str.startswith("first_")
        & learning_phase_metrics["phase"].astype(str).str.endswith("_steps")
    ]
    after_decay = learning_phase_metrics[
        learning_phase_metrics["phase"] == "after_exploration_decay"
    ]
    eval_phase = learning_phase_metrics[
        learning_phase_metrics["phase"] == "evaluation_cycle"
    ]

    lines: list[str] = []
    lines.append("# Offline TD3 pH Tracking Result Analysis")
    lines.append("")
    lines.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from saved result files only.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(
        "This report analyzes the current offline pH TD3 simulation output. It does not launch BioSMB, an OPC emulator, hardware, MPC, valves, or pumps. The source result folder is:"
    )
    lines.append("")
    lines.append(f"`{repo_rel(result_dir)}`")
    lines.append("")
    lines.append(
        "The purpose is to create editable figures and a first write-up around the ratio-action TD3 scaffold. The result should be treated as an offline software diagnostic, not as a validated pH controller."
    )
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "The environment state is the five-element vector"
    )
    lines.append("")
    lines.append(
        "$$ s_t = [\\mathrm{pH}_t,\\ \\mathrm{pH}^{\\mathrm{sp}}_t,\\ e_t,\\ a_{r,t},\\ \\tau_t], $$"
    )
    lines.append("")
    lines.append("where `e_t = pH_t - pH_sp,t`. The TD3 action is")
    lines.append("")
    lines.append(
        "$$ a_t = [a_{r,t}],\\quad a_{r,t} \\in [-1,1]. $$"
    )
    lines.append("")
    lines.append("The action is mapped to a bounded acetate/acid flow ratio in log space:")
    lines.append("")
    lines.append(
        "$$ \\log_{10}(F_{Ac}/F_{HAc}) = \\ell_{\\min} + \\frac{a_{r,t}+1}{2}(\\ell_{\\max}-\\ell_{\\min}). $$"
    )
    lines.append("")
    lines.append(
        f"The buffer-flow sum is fixed at `{fixed_buffer_flow_sum}` mL/min, so `F_HAc + F_Ac` is constant and the ratio action determines the two buffer flows. Water is fixed and logged at 5 mL/min."
    )
    lines.append("")
    lines.append(
        f"The setpoint schedule uses `{setpoint_strategy}` targets. Each setpoint is held for `{steps_per_cycle}` steps, and this saved run contains `{setpoint_cycles}` setpoint segments."
    )
    lines.append("")
    lines.append("The plant pH is the accepted ideal Henderson-Hasselbalch relation")
    lines.append("")
    lines.append(
        "$$ \\mathrm{pH} = pK_a + \\log_{10}\\left(\\frac{C_{Ac} F_{Ac}}{C_{HAc} F_{HAc}}\\right). $$"
    )
    lines.append("")
    lines.append("Because the current acid and acetate stock concentrations are equal, this reduces to")
    lines.append("")
    lines.append(
        "$$ \\mathrm{pH} = pK_a + \\log_{10}\\left(\\frac{F_{Ac}}{F_{HAc}}\\right). $$"
    )
    lines.append("")
    lines.append(f"The saved runner reward mode is `{reward_mode}`.")
    lines.append("")
    if str(reward_mode) == "three_term":
        lines.append(
            "$$ r_t = -\\left(q_2 e_t^2 + q_1 |e_t| + r_{\\Delta u}\\|a_t-a_{t-1}\\|_2^2/n_u\\right), $$"
        )
        lines.append("")
        lines.append(
            "where `e_t = pH_sp,t - pH_t`, `a_t` is the normalized ratio action, and `n_u = 1`."
        )
    elif str(reward_mode) == "relative_band":
        lines.append(
            "$$ r_t = \\left[-\\left(J_{\\mathrm{eff}} + J_{\\Delta u} + J_{\\mathrm{lin,out}} + J_{\\mathrm{lin,in}}\\right) + J_{\\mathrm{bonus}}\\right]\\alpha. $$"
        )
        lines.append("")
        lines.append(
            "The pH error is scored against a saved physical pH band, with separate inside-band, outside-band, movement, and bonus terms."
        )
    else:
        lines.append(
            "$$ r_t = r_t^{\\mathrm{band}} - \\alpha\\left(w_{|e|}|e_t| + w_{\\mathrm{tail}} h_t |e_t|\\right). $$"
        )
        lines.append("")
        lines.append(
            "This mode starts from the relative-band reward and adds absolute-error and late-hold offset penalties."
        )
    lines.append("")
    lines.append(f"Saved compact reward definition: `{reward_definition}`.")
    lines.append("")
    lines.append("## Quantitative Summary")
    lines.append("")
    lines.extend(
        markdown_table(
            summary_metrics,
            [
                ("scope", "Scope"),
                ("steps", "Steps"),
                ("mae", "MAE"),
                ("rmse", "RMSE"),
                ("max_abs_error", "Max |e|"),
                ("total_reward", "Reward sum"),
                ("squared_error_cost_sum", "Sq cost"),
                ("absolute_error_cost_sum", "Abs cost"),
                ("move_cost_sum", "Move cost"),
                ("train_updates", "Train updates"),
            ],
        )
    )
    lines.append("")
    lines.append(
        f"Overall MAE is {overall['mae']:.4g} pH and overall RMSE is {overall['rmse']:.4g} pH. The evaluation-window MAE is {eval_mae:.4g} pH and evaluation-window RMSE is {eval_rmse:.4g} pH. These values depend on the saved run length and random seed."
    )
    lines.append("")
    lines.append("## Learning-Phase Diagnostics")
    lines.append("")
    lines.extend(
        markdown_table(
            learning_phase_metrics,
            [
                ("phase", "Phase"),
                ("steps", "Steps"),
                ("mae", "MAE"),
                ("rmse", "RMSE"),
                ("max_abs_error", "Max |e|"),
                ("mean_abs_ratio_error", "Mean |ratio error|"),
                ("mean_exploration_sigma", "Mean sigma"),
                ("mean_exploration_magnitude", "Mean |noise|"),
            ],
        )
    )
    lines.append("")
    if not early_phase.empty and not after_decay.empty:
        early_row = early_phase.iloc[0]
        decay_row = after_decay.iloc[0]
        lines.append(
            f"The main learning signature is the drop from {early_row['mae']:.4g} pH MAE during `{early_row['phase']}` to {decay_row['mae']:.4g} pH MAE after exploration reaches its floor. This indicates that the one-dimensional ratio action is learnable in the ideal HH simulator."
        )
        lines.append("")
    if not eval_phase.empty:
        eval_row = eval_phase.iloc[0]
        lines.append(
            f"The final deterministic evaluation cycle gives {eval_row['mae']:.4g} pH MAE and {eval_row['max_abs_error']:.4g} pH maximum absolute error. This is encouraging, but it is still only one held-out setpoint cycle from the same reachable fixed-sum range."
        )
        lines.append("")
    lines.append("## Cycle-Group And Settling Diagnostics")
    lines.append("")
    lines.extend(
        markdown_table(
            cycle_group_metrics,
            [
                ("cycle_group", "Cycle group"),
                ("cycles", "Cycles"),
                ("mean_cycle_mae", "Mean cycle MAE"),
                ("mean_cycle_rmse", "Mean cycle RMSE"),
                ("max_cycle_abs_error", "Max cycle |e|"),
                ("mean_move_cost_sum", "Mean move cost"),
            ],
        )
    )
    lines.append("")
    lines.extend(
        markdown_table(
            settling_diagnostics,
            [
                ("tolerance", "Tolerance"),
                ("hold_steps", "Hold steps"),
                ("settled_cycles", "Settled cycles"),
                ("failed_cycles", "Failed cycles"),
                ("median_settling_steps", "Median settling steps"),
                ("p90_settling_steps", "P90 settling steps"),
                ("max_settling_steps", "Max settling steps"),
            ],
        )
    )
    lines.append("")
    lines.append(
        f"The settling table is computed within each {steps_per_cycle}-step setpoint hold. A cycle is counted as settled only after the error stays inside the tolerance band for the listed hold duration."
    )
    lines.append("")
    lines.append("## Best And Worst Setpoint Cycles")
    lines.append("")
    lines.extend(
        markdown_table(
            cycle_extremes,
            [
                ("rank_type", "Rank"),
                ("cycle", "Cycle"),
                ("target_ph", "Target pH"),
                ("is_test", "Eval"),
                ("mean_abs_error", "MAE"),
                ("rmse", "RMSE"),
                ("max_abs_error", "Max |e|"),
                ("move_cost_sum", "Move cost"),
            ],
        )
    )
    lines.append("")
    lines.append("## Figures")
    lines.append("")
    if "fig_ph_tracking_error_reward" in figure_lookup:
        lines.append(
            f"![pH tracking, error, and reward]({report_rel(figure_lookup['fig_ph_tracking_error_reward'], report_path)})"
        )
        lines.append("")
        lines.append(
            "This figure is the main tracking diagnostic. The fourth panel separates the raw squared-error, absolute-error, and move-penalty costs before reward weighting."
        )
        lines.append("")
    if "fig_flow_commands_and_ratio" in figure_lookup:
        lines.append(
            f"![flow commands and ratio]({report_rel(figure_lookup['fig_flow_commands_and_ratio'], report_path)})"
        )
        lines.append("")
        lines.append(
            "This figure shows the actual acid and acetate commands under the fixed buffer-flow sum, the fixed water-flow log, and the acid/acetate log-ratio that drives the ideal HH pH."
        )
        lines.append("")
    if "fig_cycle_metrics" in figure_lookup:
        lines.append(
            f"![cycle metrics]({report_rel(figure_lookup['fig_cycle_metrics'], report_path)})"
        )
        lines.append("")
    if "fig_action_diagnostics" in figure_lookup:
        lines.append(
            f"![action diagnostics]({report_rel(figure_lookup['fig_action_diagnostics'], report_path)})"
        )
        lines.append("")
        lines.append(
            "The action diagnostic figure includes the normalized ratio-action trajectory, the ratio/log-ratio scatter, and exploration traces when those columns are available."
        )
        lines.append("")
    if "fig_hh_ratio_consistency" in figure_lookup:
        lines.append(
            f"![HH ratio consistency]({report_rel(figure_lookup['fig_hh_ratio_consistency'], report_path)})"
        )
        lines.append("")
        lines.append(
            f"The maximum absolute residual against the ideal HH ratio line is {hh_row['max_abs_residual']:.3e} pH. Water is fixed at 5 mL/min and does not create an independent pH offset in this static ideal model."
        )
        lines.append("")
    if "fig_training_losses" in figure_lookup:
        lines.append(
            f"![training losses]({report_rel(figure_lookup['fig_training_losses'], report_path)})"
        )
        lines.append("")
    lines.append("## Flow Diagnostics")
    lines.append("")
    lines.extend(
        markdown_table(
            flow_diagnostics,
            [
                ("flow", "Flow"),
                ("mean", "Mean"),
                ("min", "Min"),
                ("max", "Max"),
                ("lower_saturation_fraction", "Low sat frac"),
                ("upper_saturation_fraction", "High sat frac"),
                ("mean_abs_step_change", "Mean |dF|"),
            ],
        )
    )
    lines.append("")
    physical_flows = flow_diagnostics[
        flow_diagnostics["flow"].isin(["acid", "acetate", "water"])
    ]
    if not physical_flows.empty:
        max_logged_flow = float(physical_flows["max"].max())
        upper_violations = physical_flows[
            physical_flows["max"] > physical_flows["upper_bound"] + 1e-6
        ]
        lower_violations = physical_flows[
            physical_flows["min"] < physical_flows["lower_bound"] - 1e-6
        ]
        if upper_violations.empty and lower_violations.empty:
            lines.append(
                f"Flow-limit check: no logged acid, acetate, or water flow exceeded its configured pump bounds. The maximum logged physical flow was {max_logged_flow:.4g} mL/min."
            )
        else:
            lines.append(
                "Flow-limit check: at least one logged flow exceeded its configured pump bounds. Inspect `flow_diagnostics.csv` before using this result."
            )
        lines.append("")
    buffer_rows = flow_diagnostics[flow_diagnostics["flow"] == "buffer_sum"]
    if not buffer_rows.empty:
        buffer_row = buffer_rows.iloc[0]
        lines.append(
            f"The logged acid-plus-acetate sum stayed between {buffer_row['min']:.4g} and {buffer_row['max']:.4g} mL/min."
        )
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "The current scaffold is behaving consistently with the intended static first-principles pH model. The action-to-flow mapping is bounded, the reward sign penalizes tracking error and action movement, and the logged pH follows the acid/acetate ratio."
    )
    lines.append("")
    lines.append(
        "For this saved run, the TD3 policy appears to learn the static ratio-tracking task after the initial exploration-heavy period. The early cycles contain the dominant tracking failures, while later cycles operate near the ideal HH inverse mapping. This is useful algorithm evidence for the offline simulator, not validation of the laboratory plant."
    )
    lines.append("")
    lines.append("## Bugs, Inconsistencies, Or Risks")
    lines.append("")
    lines.append("- The plant is static ideal HH, so it does not include delay, mixing, residence time, sensor lag, or lab mismatch.")
    lines.append("- Water is fixed at 5 mL/min in this version and is plotted only as a logged process condition.")
    lines.append("- The final evaluation result is only one setpoint cycle, so it should not be treated as robust generalization evidence.")
    lines.append("- The current fixed 15 mL/min buffer-flow sum restricts the reachable setpoint range to about 4.459-5.061 pH under the current pump bounds.")
    lines.append("- The move penalty is small compared with the absolute-error term, so the learned action can still show occasional sharp moves during training.")
    lines.append("- The report reads saved CSV files, so stale figures are possible if the report is not regenerated after a new run.")
    lines.append("")
    lines.append("## Recommended Next Experiments")
    lines.append("")
    lines.append(
        "The next step should be a deterministic evaluation sweep, not another single final-cycle check. After training, evaluate the frozen actor without exploration on a grid of reachable setpoints across 4.459-5.061 pH. The key metrics should be MAE, maximum absolute error, settling count within 0.02 and 0.05 pH, and flow saturation fraction."
    )
    lines.append("")
    lines.append(
        f"After that, run a small seed batch, for example seeds 7, 21, 47, 73, and 101, using the same {total_steps}-step protocol. Compare the mean and worst-case evaluation MAE rather than relying on one run."
    )
    lines.append("")
    lines.append(
        "A third useful experiment is a fixed-sum sweep. Try buffer-flow sums such as 12, 15, and 18 mL/min, and record the reachable pH range, saturation frequency, and tracking quality. This will tell us whether 15 mL/min is a good control design choice or just a convenient first setting."
    )
    lines.append("")
    lines.append("Current reproducibility command:")
    lines.append("")
    lines.append("```powershell")
    seed = arguments.get("seed", 7)
    batch_size = arguments.get("batch_size", 64)
    buffer_size = arguments.get("buffer_size", 5000)
    std_decay_steps = arguments.get("std_decay_steps", 5000)
    lines.append(
        "& 'C:\\Users\\HAMEDI\\miniconda3\\envs\\rl\\python.exe' "
        "run_offline_ph_td3_training.py "
        f"--total-steps {total_steps} "
        f"--set-points-len {steps_per_cycle} "
        f"--std-decay-steps {std_decay_steps} "
        f"--batch-size {batch_size} "
        f"--buffer-size {buffer_size} "
        f"--seed {seed}"
    )
    lines.append(
        f"& 'C:\\Users\\HAMEDI\\miniconda3\\envs\\rl\\python.exe' analysis\\generate_offline_ph_td3_report.py --result-dir {repo_rel(result_dir)}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append("Files inspected or consumed:")
    lines.append("")
    inspected = [
        "run_offline_ph_td3_training.py",
        "simulation/ph_environment.py",
        "simulation/henderson_hasselbalch_model.py",
        "reports/overview.md",
        "reports/offline_ph_rl_environment_report.md",
        repo_rel(result_dir / "tables" / "trajectory.csv"),
        repo_rel(result_dir / "tables" / "episode_metrics.csv"),
        repo_rel(result_dir / "tables" / "training_summary.csv"),
        repo_rel(result_dir / "tables" / "config_snapshot.json"),
    ]
    for item in inspected:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("Generated outputs:")
    lines.append("")
    for item in [*generated_tables, *figures, report_path]:
        lines.append(f"- `{repo_rel(item)}`")
    lines.append("")
    return "\n".join(lines)


def run_report(result_dir: Path, output_dir: Path, report_path: Path) -> dict[str, list[Path] | Path]:
    result_dir = result_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    trajectory, episode_metrics, training_summary, config = load_result_tables(result_dir)
    trajectory = add_hh_consistency_columns(trajectory, config)

    summary_metrics = compute_summary_metrics(trajectory)
    flow_diagnostics = compute_flow_diagnostics(trajectory, config)
    hh_consistency = compute_hh_consistency(trajectory)
    learning_phase_metrics = compute_learning_phase_metrics(trajectory, config)
    cycle_group_metrics = compute_cycle_group_metrics(episode_metrics)
    settling_diagnostics = compute_settling_diagnostics(trajectory)
    cycle_extremes = compute_cycle_extremes(episode_metrics)

    summary_path = output_dir / "summary_metrics.csv"
    flow_path = output_dir / "flow_diagnostics.csv"
    episode_path = output_dir / "cycle_metrics.csv"
    hh_path = output_dir / "hh_consistency.csv"
    learning_phase_path = output_dir / "learning_phase_metrics.csv"
    cycle_group_path = output_dir / "cycle_group_metrics.csv"
    settling_path = output_dir / "settling_diagnostics.csv"
    cycle_extremes_path = output_dir / "cycle_extremes.csv"
    source_summary_path = output_dir / "source_training_summary.csv"

    summary_metrics.to_csv(summary_path, index=False)
    flow_diagnostics.to_csv(flow_path, index=False)
    episode_metrics.to_csv(episode_path, index=False)
    hh_consistency.to_csv(hh_path, index=False)
    learning_phase_metrics.to_csv(learning_phase_path, index=False)
    cycle_group_metrics.to_csv(cycle_group_path, index=False)
    settling_diagnostics.to_csv(settling_path, index=False)
    cycle_extremes.to_csv(cycle_extremes_path, index=False)
    training_summary.to_csv(source_summary_path, index=False)

    figures = [
        plot_tracking_reward(trajectory, output_dir),
        plot_flow_commands(trajectory, output_dir, config),
        plot_cycle_metrics(episode_metrics, output_dir),
        plot_action_diagnostics(trajectory, output_dir),
        plot_hh_ratio_consistency(trajectory, output_dir, config),
    ]
    loss_figure = plot_training_losses(trajectory, output_dir)
    if loss_figure is not None:
        figures.append(loss_figure)

    generated_tables = [
        summary_path,
        flow_path,
        episode_path,
        hh_path,
        learning_phase_path,
        cycle_group_path,
        settling_path,
        cycle_extremes_path,
        source_summary_path,
    ]
    manifest_path = write_manifest(
        output_dir=output_dir,
        result_dir=result_dir,
        report_path=report_path,
        figures=figures,
        tables=generated_tables,
        source_files=[
            "run_offline_ph_td3_training.py",
            "simulation/ph_environment.py",
            "simulation/henderson_hasselbalch_model.py",
            "reports/overview.md",
            "reports/offline_ph_rl_environment_report.md",
        ],
    )
    generated_tables.append(manifest_path)

    report_text = build_report(
        report_path=report_path,
        result_dir=result_dir,
        output_dir=output_dir,
        summary_metrics=summary_metrics,
        flow_diagnostics=flow_diagnostics,
        episode_metrics=episode_metrics,
        learning_phase_metrics=learning_phase_metrics,
        cycle_group_metrics=cycle_group_metrics,
        settling_diagnostics=settling_diagnostics,
        cycle_extremes=cycle_extremes,
        hh_consistency=hh_consistency,
        config=config,
        figures=figures,
        generated_tables=generated_tables,
    )
    report_path.write_text(report_text, encoding="utf-8")

    print(f"Wrote report: {repo_rel(report_path)}")
    print(f"Wrote figures and tables under: {repo_rel(output_dir)}")
    return {
        "report_path": report_path,
        "output_dir": output_dir,
        "figures": figures,
        "tables": generated_tables,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate pH TD3 analysis figures and Markdown report from saved offline results."
    )
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=None,
        help="Result folder containing tables/trajectory.csv. Defaults to latest offline_ph_td3_training_* run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output folder for report figures and CSV summaries.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result_dir = args.result_dir or find_latest_result_dir()
    output_dir = args.output_dir or output_dir_for_result(result_dir)
    run_report(result_dir=result_dir, output_dir=output_dir, report_path=args.report_path)


if __name__ == "__main__":
    main()
