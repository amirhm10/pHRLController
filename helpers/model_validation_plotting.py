from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from simulation.config import PHProcessConfig


def create_model_validation_figures(
    df: pd.DataFrame,
    lag_scan: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
    config: PHProcessConfig | None = None,
) -> dict[str, Path]:
    config = config or PHProcessConfig()
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "measured_vs_prediction_time": figure_dir / "measured_vs_hh_prediction_time.png",
        "measured_vs_prediction_scatter": figure_dir / "measured_vs_hh_prediction_scatter.png",
        "residual_time": figure_dir / "measured_minus_hh_time.png",
        "residual_histogram": figure_dir / "measured_minus_hh_histogram.png",
        "flow_trajectories": figure_dir / "inlet_flow_trajectories.png",
        "total_flow": figure_dir / "total_flow_trajectory.png",
        "flow_ratio_response": figure_dir / "flow_ratio_response_map.png",
        "lag_scan": figure_dir / "lag_scan_diagnostic.png",
    }

    plot_measured_vs_prediction_time(df, paths["measured_vs_prediction_time"], stamp_text)
    plot_measured_vs_prediction_scatter(
        df,
        paths["measured_vs_prediction_scatter"],
        stamp_text,
    )
    plot_residual_time(df, paths["residual_time"], stamp_text)
    plot_residual_histogram(df, paths["residual_histogram"], stamp_text)
    plot_flow_trajectories(df, paths["flow_trajectories"], stamp_text, config)
    plot_total_flow(df, paths["total_flow"], stamp_text)
    plot_flow_ratio_response(df, paths["flow_ratio_response"], stamp_text)
    plot_lag_scan(lag_scan, paths["lag_scan"], stamp_text)
    return paths


def plot_measured_vs_prediction_time(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"].astype(bool)
    x = df["sample_index"]
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        x,
        df["ph_measured"].where(valid),
        color="#005f73",
        linewidth=1.25,
        label="measured PH_2 (model-valid)",
    )
    ax.plot(
        x,
        df["ph_henderson_hasselbalch"].where(valid),
        color="#ae2012",
        linewidth=1.15,
        label="ideal Henderson-Hasselbalch",
    )
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("Measured PH_2 versus ideal first-principles prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_measured_vs_prediction_scatter(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"]
    fig, ax = plt.subplots(figsize=(8, 6.2))
    scatter = ax.scatter(
        df.loc[valid, "ph_henderson_hasselbalch"],
        df.loc[valid, "ph_measured"],
        c=df.loc[valid, "elapsed_h"],
        cmap="viridis",
        alpha=0.68,
        s=26,
        label="lab samples",
    )
    lo = min(
        df.loc[valid, "ph_henderson_hasselbalch"].min(),
        df.loc[valid, "ph_measured"].min(),
    ) - 0.1
    hi = max(
        df.loc[valid, "ph_henderson_hasselbalch"].max(),
        df.loc[valid, "ph_measured"].max(),
    ) + 0.1
    grid = np.linspace(lo, hi, 100)
    ax.plot(grid, grid, "--", color="0.35", linewidth=1.2, label="measured = predicted")
    ax.set_xlabel("Ideal Henderson-Hasselbalch pH")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Measured pH versus first-principles prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Elapsed time (h)")
    finalize_figure(fig, path, stamp_text)


def plot_residual_time(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["measured_minus_hh"].where(valid),
        color="#9b2226",
        linewidth=1.15,
    )
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.axhspan(-0.2, 0.2, color="#94d2bd", alpha=0.18, label="+/- 0.2 pH")
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("PH_2 - ideal HH pH")
    ax.set_title("First-principles model residual over time")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_residual_histogram(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    residual = df.loc[df["valid_for_model"], "measured_minus_hh"].dropna()
    fig, ax = plt.subplots(figsize=(8, 5.8))
    ax.hist(residual, bins=35, color="#005f73", alpha=0.84)
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.2)
    if len(residual):
        ax.axvline(
            residual.mean(),
            color="#ee9b00",
            linewidth=1.5,
            label=f"mean={residual.mean():.3f}",
        )
    ax.set_xlabel("PH_2 - ideal HH pH")
    ax.set_ylabel("Sample count")
    ax.set_title("First-principles model residual distribution")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_flow_trajectories(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
    config: PHProcessConfig,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(df["sample_index"], df["acid_flow"], color="#ae2012", label="acetic acid")
    ax.plot(
        df["sample_index"],
        df["acetate_flow"],
        color="#0a9396",
        label="sodium acetate",
    )
    ax.plot(df["sample_index"], df["water_flow"], color="#005f73", label="Arium water")
    ax.axhline(
        config.acid_flow_min,
        color="0.35",
        linestyle="--",
        linewidth=1.0,
        label="1-10 mL/min bounds",
    )
    ax.axhline(config.acid_flow_max, color="0.35", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("Flowrate (mL/min)")
    ax.set_title("Inlet flow trajectories")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", ncols=2)
    finalize_figure(fig, path, stamp_text)


def plot_total_flow(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(df["sample_index"], df["total_flow"], color="#5f0f40", linewidth=1.2)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("Total inlet flow (mL/min)")
    ax.set_title("Total inlet flow for residence-time diagnostics")
    ax.grid(True, alpha=0.3)
    finalize_figure(fig, path, stamp_text)


def plot_flow_ratio_response(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"]
    sorted_df = df.loc[valid].sort_values("log10_molar_base_acid_ratio")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        sorted_df["log10_molar_base_acid_ratio"],
        sorted_df["ph_measured"],
        color="#005f73",
        alpha=0.55,
        s=26,
        label="measured PH_2",
    )
    ax.plot(
        sorted_df["log10_molar_base_acid_ratio"],
        sorted_df["ph_henderson_hasselbalch"],
        color="#ae2012",
        linewidth=1.8,
        label="ideal HH pH",
    )
    ax.set_xlabel("log10(molar acetate / molar acid)")
    ax.set_ylabel("pH")
    ax.set_title("pH response to acid/base inlet ratio")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_lag_scan(lag_scan: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax1 = plt.subplots(figsize=(9, 5.8))
    ax1.plot(
        lag_scan["lag_samples"],
        lag_scan["correlation"],
        marker="o",
        color="#005f73",
        label="correlation",
    )
    ax1.set_xlabel("Ideal HH prediction lag behind PH_2 (samples)")
    ax1.set_ylabel("Correlation")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(
        lag_scan["lag_samples"],
        lag_scan["rmse"],
        marker="s",
        color="#ae2012",
        label="RMSE",
    )
    ax2.set_ylabel("RMSE (pH)")
    ax1.set_title("Discrete lag diagnostic")

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="best")
    finalize_figure(fig, path, stamp_text)


def finalize_figure(fig, path: Path, stamp_text: str) -> None:
    fig.text(
        0.99,
        0.01,
        stamp_text,
        ha="right",
        va="bottom",
        fontsize=8,
        color="0.35",
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)
