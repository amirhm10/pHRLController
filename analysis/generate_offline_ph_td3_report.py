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
    out["abs_action_acid"] = np.abs(out["action_acid"])
    out["abs_action_acetate"] = np.abs(out["action_acetate"])
    out["abs_action_water"] = np.abs(out["action_water"])
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
    fig, axs = plt.subplots(3, 1, figsize=(10.5, 8.0), sharex=True)
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
    axs[2].set_xlabel("step")
    axs[2].set_ylabel("reward")
    axs[2].grid(alpha=0.28)
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
    axs[0].set_title("TD3 Pump Commands")
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
    fig, axs = plt.subplots(2, 1, figsize=(10.5, 7.2))
    steps = trajectory["step"]
    actions = ["action_acid", "action_acetate", "action_water"]
    colors = ["#CC6677", "#4477AA", "#228833"]
    labels = ["acid action", "acetate action", "water action"]
    for column, color, label in zip(actions, colors, labels):
        axs[0].plot(steps, trajectory[column], color=color, linewidth=1.3, label=label)
    axs[0].axhline(1.0, color="#777777", linestyle=":", linewidth=0.8)
    axs[0].axhline(-1.0, color="#777777", linestyle=":", linewidth=0.8)
    shade_protocol_regions(axs[0], trajectory)
    axs[0].set_ylabel("normalized action")
    axs[0].set_title("Action-Space Diagnostics")
    axs[0].grid(alpha=0.28)
    axs[0].legend(loc="best")

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
    fig.tight_layout()
    return save_figure(fig, output_dir, "fig_action_diagnostics.png")


def plot_hh_ratio_consistency(trajectory: pd.DataFrame, output_dir: Path, config: dict) -> Path:
    process_config = config.get("process_config", {})
    pka = float_or_nan(process_config.get("pKa", 4.76))
    x = trajectory["log10_flow_ratio"].to_numpy(float)
    x_line = np.linspace(float(np.min(x)), float(np.max(x)), 200)
    y_line = pka + x_line

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
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
    summary_metrics: pd.DataFrame,
    flow_diagnostics: pd.DataFrame,
    episode_metrics: pd.DataFrame,
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
        "The purpose is to create editable figures and a first write-up around the new direct-flow TD3 scaffold. The result should be treated as an offline software diagnostic, not as a validated pH controller."
    )
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "The environment state is the seven-element vector"
    )
    lines.append("")
    lines.append(
        "$$ s_t = [\\mathrm{pH}_t,\\ \\mathrm{pH}^{\\mathrm{sp}}_t,\\ e_t,\\ a_{HAc,t},\\ a_{Ac,t},\\ a_{W,t},\\ \\tau_t], $$"
    )
    lines.append("")
    lines.append("where `e_t = pH_t - pH_sp,t`. The TD3 action is")
    lines.append("")
    lines.append(
        "$$ a_t = [a_{HAc,t},\\ a_{Ac,t},\\ a_{W,t}],\\quad a_i \\in [-1,1]. $$"
    )
    lines.append("")
    lines.append("Each action coordinate is mapped to a physical pump command by")
    lines.append("")
    lines.append(
        "$$ F_i = F_{i,\\min} + \\frac{a_i + 1}{2}(F_{i,\\max}-F_{i,\\min}). $$"
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
    lines.append("The saved runner reward is")
    lines.append("")
    lines.append("$$ r_t = -(\\mathrm{pH}_t - \\mathrm{pH}^{\\mathrm{sp}}_t)^2. $$")
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
                ("train_updates", "Train updates"),
            ],
        )
    )
    lines.append("")
    lines.append(
        f"Overall MAE is {overall['mae']:.4g} pH and overall RMSE is {overall['rmse']:.4g} pH. The evaluation-window MAE is {eval_mae:.4g} pH and evaluation-window RMSE is {eval_rmse:.4g} pH. These values depend on the saved run length and random seed."
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
            "This figure is the main tracking diagnostic. The gray span marks an optional legacy HH warm-start segment if present, and the gold span marks the final evaluation segment."
        )
        lines.append("")
    if "fig_flow_commands_and_ratio" in figure_lookup:
        lines.append(
            f"![flow commands and ratio]({report_rel(figure_lookup['fig_flow_commands_and_ratio'], report_path)})"
        )
        lines.append("")
        lines.append(
            "This figure shows the actual flow commands and the acid/acetate log-ratio that drives the ideal HH pH."
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
    if "fig_hh_ratio_consistency" in figure_lookup:
        lines.append(
            f"![HH ratio consistency]({report_rel(figure_lookup['fig_hh_ratio_consistency'], report_path)})"
        )
        lines.append("")
        lines.append(
            f"The maximum absolute residual against the ideal HH ratio line is {hh_row['max_abs_residual']:.3e} pH. The water-flow color does not create an independent pH offset in this static ideal model."
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
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "The current scaffold is behaving consistently with the intended static first-principles pH model. The action-to-flow mapping is bounded, the reward sign is correct for setpoint tracking, and the logged pH follows the acid/acetate ratio."
    )
    lines.append("")
    lines.append(
        "The result is not enough to claim controller quality. For a short smoke run, a low final evaluation error can occur because the ideal HH mapping is simple and the final setpoint may be easy. A longer multi-seed run is needed before comparing learning behavior."
    )
    lines.append("")
    lines.append("## Bugs, Inconsistencies, Or Risks")
    lines.append("")
    lines.append("- The plant is static ideal HH, so it does not include delay, mixing, residence time, sensor lag, or lab mismatch.")
    lines.append("- Water is a controlled actuator and is plotted, but it does not directly shift ideal HH pH with equal acid and acetate stocks.")
    lines.append("- The final evaluation result is run-dependent and should not be treated as generalization evidence.")
    lines.append("- The report reads saved CSV files, so stale figures are possible if the report is not regenerated after a new run.")
    lines.append("")
    lines.append("## Recommended Next Experiment")
    lines.append("")
    lines.append(
        "Run the default offline simulation with no HH warm-start segment and one final evaluation cycle. Use the same report script afterward and compare `td3_training_steps`, evaluation MAE, max absolute error, flow saturation fractions, and the action scatter plot."
    )
    lines.append("")
    lines.append("Example:")
    lines.append("")
    lines.append("```powershell")
    lines.append(
        "& 'C:\\Users\\HAMEDI\\miniconda3\\envs\\rl\\python.exe' run_offline_ph_td3_training.py --total-steps 25000 --n-tests 10 --batch-size 64 --buffer-size 5000 --seed 21"
    )
    lines.append(
        "& 'C:\\Users\\HAMEDI\\miniconda3\\envs\\rl\\python.exe' analysis\\generate_offline_ph_td3_report.py"
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
        "external: RL_assisted_MPC/Simulation/rl_sim.py",
        "external: RL_assisted_MPC/report/scripts/analyze_distillation_all_runners_latest_20260609.py",
        "external: RL_assisted_MPC/report/generate_rl_state_scaling_report.py",
        "external: RL_assisted_MPC/utils/plotting_core.py",
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

    summary_path = output_dir / "summary_metrics.csv"
    flow_path = output_dir / "flow_diagnostics.csv"
    episode_path = output_dir / "cycle_metrics.csv"
    hh_path = output_dir / "hh_consistency.csv"
    source_summary_path = output_dir / "source_training_summary.csv"

    summary_metrics.to_csv(summary_path, index=False)
    flow_diagnostics.to_csv(flow_path, index=False)
    episode_metrics.to_csv(episode_path, index=False)
    hh_consistency.to_csv(hh_path, index=False)
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
            "RL_assisted_MPC/Simulation/rl_sim.py",
            "RL_assisted_MPC/report/scripts/analyze_distillation_all_runners_latest_20260609.py",
            "RL_assisted_MPC/report/generate_rl_state_scaling_report.py",
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
        hh_consistency=hh_consistency,
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
