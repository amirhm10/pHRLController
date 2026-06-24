from __future__ import annotations

import os
from pathlib import Path

MPL_CONFIG_DIR = Path("results") / ".matplotlib-cache"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib.pyplot as plt
import pandas as pd

from helpers.data_preparation_plotting import add_phase_background, finalize_figure


MEASURED_COLOR = "#5f5572"
PREDICTED_COLOR = "#7d6f45"
ACID_COLOR = "#7f4f5f"
ACETATE_COLOR = "#416f6f"
RESIDUAL_COLOR = "#744d56"
ZERO_LINE_COLOR = "#2f2f2f"


def create_hh_prepared_figures(
    comparison: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    figure_paths = {
        "ph_vs_prediction": figure_dir / "ph_vs_hh_prediction.png",
        "ph_vs_prediction_with_flows": figure_dir
        / "ph_vs_hh_prediction_with_acid_base_flows.png",
        "residual": figure_dir / "ph_minus_hh_prediction.png",
    }
    plot_ph_vs_prediction(comparison, figure_paths["ph_vs_prediction"], stamp_text)
    plot_ph_vs_prediction_with_flows(
        comparison,
        figure_paths["ph_vs_prediction_with_flows"],
        stamp_text,
    )
    plot_residual(comparison, figure_paths["residual"], stamp_text)
    return figure_paths


def plot_ph_vs_prediction(
    comparison: pd.DataFrame,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    valid = comparison["valid_hh_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        comparison["sample_index"],
        comparison["ph_measured"].where(valid),
        color=MEASURED_COLOR,
        linewidth=1.35,
        label="Measured pH",
    )
    ax.plot(
        comparison["sample_index"],
        comparison["ph_predicted_hh"].where(valid),
        color=PREDICTED_COLOR,
        linewidth=1.25,
        label="HH predicted pH",
    )
    add_phase_background(ax, comparison)
    ax.set_xlabel("Sequential sample index")
    ax.set_ylabel("pH")
    ax.set_title("Measured pH and Henderson-Hasselbalch prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, output_path, stamp_text)


def plot_ph_vs_prediction_with_flows(
    comparison: pd.DataFrame,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    valid = comparison["valid_hh_model"].astype(bool)
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.2), sharex=True)

    axes[0].plot(
        comparison["sample_index"],
        comparison["ph_measured"].where(valid),
        color=MEASURED_COLOR,
        linewidth=1.35,
        label="Measured pH",
    )
    axes[0].plot(
        comparison["sample_index"],
        comparison["ph_predicted_hh"].where(valid),
        color=PREDICTED_COLOR,
        linewidth=1.25,
        label="HH predicted pH",
    )
    add_phase_background(axes[0], comparison)
    axes[0].set_ylabel("pH")
    axes[0].set_title("Measured pH and Henderson-Hasselbalch prediction")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    axes[1].plot(
        comparison["sample_index"],
        comparison["acid_flow"],
        color=ACID_COLOR,
        linewidth=1.2,
        label="Acetic acid flow",
    )
    axes[1].plot(
        comparison["sample_index"],
        comparison["acetate_flow"],
        color=ACETATE_COLOR,
        linewidth=1.2,
        label="Sodium acetate flow",
    )
    add_phase_background(axes[1], comparison)
    axes[1].set_xlabel("Sequential sample index")
    axes[1].set_ylabel("Flowrate (mL/min)")
    axes[1].set_title("Acid and conjugate-base flows")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")

    finalize_figure(fig, output_path, stamp_text)


def plot_residual(
    comparison: pd.DataFrame,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    valid = comparison["valid_hh_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        comparison["sample_index"],
        comparison["ph_minus_ph_predicted"].where(valid),
        color=RESIDUAL_COLOR,
        linewidth=1.25,
        label="pH - HH predicted pH",
    )
    ax.axhline(
        0.0,
        color=ZERO_LINE_COLOR,
        linestyle="--",
        linewidth=1.2,
        label="zero error",
    )
    add_phase_background(ax, comparison)
    ax.set_xlabel("Sequential sample index")
    ax.set_ylabel("pH - predicted pH")
    ax.set_title("Henderson-Hasselbalch prediction residual")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, output_path, stamp_text)
