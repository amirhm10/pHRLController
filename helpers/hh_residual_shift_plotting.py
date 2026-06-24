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
RESIDUAL_COLOR = "#744d56"
PH1_COLOR = "#6b6b6b"
MASS_COLORS = {
    "acid": "#7f4f5f",
    "sodium": "#416f6f",
    "water": "#5f7189",
}
CHANGEPOINT_COLOR = "#1f1f1f"
PHASE2_COLOR = "#4d4d4d"


def create_hh_residual_shift_figures(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
    changepoint: int,
    phase2_start: int,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "residual_overview": figure_dir / "hh_residual_shift_overview.png",
        "local_context": figure_dir / "hh_residual_shift_local_context.png",
    }
    plot_residual_overview(
        comparison,
        changepoint,
        phase2_start,
        paths["residual_overview"],
        stamp_text,
    )
    plot_local_context(
        raw_data,
        comparison,
        changepoint,
        paths["local_context"],
        stamp_text,
    )
    return paths


def plot_residual_overview(
    comparison: pd.DataFrame,
    changepoint: int,
    phase2_start: int,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        comparison["sample_index"],
        comparison["ph_minus_ph_predicted"],
        color=RESIDUAL_COLOR,
        linewidth=1.2,
        label="pH - HH predicted pH",
    )
    ax.axhline(0.0, color="0.2", linestyle="--", linewidth=1.1, label="zero error")
    add_phase_background(ax, comparison)
    add_vertical_marker(ax, changepoint, "residual jump")
    add_vertical_marker(
        ax,
        phase2_start,
        "sampling phase change",
        color=PHASE2_COLOR,
        linestyle=":",
    )
    ax.set_xlabel("Sequential sample index")
    ax.set_ylabel("pH - predicted pH")
    ax.set_title("HH residual shift occurs before the sampling-rate phase change")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, output_path, stamp_text)


def plot_local_context(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
    changepoint: int,
    output_path: str | Path,
    stamp_text: str,
    radius: int = 60,
) -> None:
    start = max(0, changepoint - radius)
    end = min(len(comparison), changepoint + radius + 1)
    local = comparison.iloc[start:end]
    raw_local = raw_data.iloc[start:end]

    fig, axes = plt.subplots(4, 1, figsize=(12, 10.5), sharex=True)

    axes[0].plot(
        local["sample_index"],
        local["ph_measured"],
        color=MEASURED_COLOR,
        linewidth=1.25,
        label="Measured pH",
    )
    axes[0].plot(
        local["sample_index"],
        local["ph_predicted_hh"],
        color=PREDICTED_COLOR,
        linewidth=1.2,
        label="HH predicted pH",
    )
    axes[0].set_ylabel("pH")
    axes[0].set_title("Local pH and prediction context")
    axes[0].legend(loc="best")

    axes[1].plot(
        local["sample_index"],
        local["ph_minus_ph_predicted"],
        color=RESIDUAL_COLOR,
        linewidth=1.2,
    )
    axes[1].axhline(0.0, color="0.2", linestyle="--", linewidth=1.0)
    axes[1].set_ylabel("Residual")
    axes[1].set_title("Residual changes at the lab-session boundary")

    axes[2].plot(
        local["sample_index"],
        pd.to_numeric(raw_local["observation.biosmb-sensors.PH_1"], errors="coerce"),
        color=PH1_COLOR,
        linewidth=1.15,
        label="PH_1",
    )
    axes[2].plot(
        local["sample_index"],
        pd.to_numeric(raw_local["observation.biosmb-sensors.PH_2"], errors="coerce"),
        color=MEASURED_COLOR,
        linewidth=1.15,
        label="PH_2",
    )
    axes[2].set_ylabel("pH")
    axes[2].set_title("Raw pH sensor channels")
    axes[2].legend(loc="best")

    axes[3].plot(
        local["sample_index"],
        pd.to_numeric(
            raw_local["observation.mfcs-mass.acid-mass-grams"],
            errors="coerce",
        ),
        color=MASS_COLORS["acid"],
        linewidth=1.15,
        label="acid mass",
    )
    axes[3].plot(
        local["sample_index"],
        pd.to_numeric(
            raw_local["observation.mfcs-mass.sodium-mass-grams"],
            errors="coerce",
        ),
        color=MASS_COLORS["sodium"],
        linewidth=1.15,
        label="sodium mass",
    )
    axes[3].plot(
        local["sample_index"],
        pd.to_numeric(
            raw_local["observation.mfcs-mass.water-mass-grams"],
            errors="coerce",
        ),
        color=MASS_COLORS["water"],
        linewidth=1.15,
        label="water mass",
    )
    axes[3].set_xlabel("Sequential sample index")
    axes[3].set_ylabel("Mass (g)")
    axes[3].set_title("Reservoir masses reset at the same boundary")
    axes[3].legend(loc="best", ncols=3)

    for ax in axes:
        add_phase_background(ax, comparison, label_phases=False)
        ax.set_xlim(
            float(local["sample_index"].iloc[0]) - 0.5,
            float(local["sample_index"].iloc[-1]) + 0.5,
        )
        add_vertical_marker(ax, changepoint, "residual jump")
        ax.grid(True, alpha=0.3)

    finalize_figure(fig, output_path, stamp_text)


def add_vertical_marker(
    ax,
    sample_index: int,
    label: str,
    color: str = CHANGEPOINT_COLOR,
    linestyle: str = "--",
) -> None:
    ax.axvline(
        sample_index - 0.5,
        color=color,
        linestyle=linestyle,
        linewidth=1.25,
        alpha=0.9,
        label=label,
    )
