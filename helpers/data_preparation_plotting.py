from __future__ import annotations

import os
from pathlib import Path

MPL_CONFIG_DIR = Path("results") / ".matplotlib-cache"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib.pyplot as plt
import pandas as pd


FEATURE_SPECS = {
    "acid_flow": {
        "label": "Acetic acid flow",
        "ylabel": "mL/min",
        "color": "#7f4f5f",
    },
    "acetate_flow": {
        "label": "Sodium acetate flow",
        "ylabel": "mL/min",
        "color": "#416f6f",
    },
    "water_flow": {
        "label": "Arium water flow",
        "ylabel": "mL/min",
        "color": "#5f7189",
    },
    "ph_measured": {
        "label": "Measured pH",
        "ylabel": "pH",
        "color": "#6a587f",
    },
}
PHASE_SHADE_COLORS = ("#efe7da", "#dce8e3", "#e6e1ec")
PHASE_SEPARATOR_COLOR = "#4d4d4d"


def create_data_preparation_figures(
    prepared_data: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    figure_paths: dict[str, Path] = {}
    for column in feature_columns_in_data(prepared_data):
        path = figure_dir / f"{column}_timeseries.png"
        plot_single_feature(prepared_data, column, path, stamp_text)
        figure_paths[f"{column}_timeseries"] = path

    all_features_path = figure_dir / "all_features_four_subplots.png"
    plot_all_features_four_subplots(prepared_data, all_features_path, stamp_text)
    figure_paths["all_features_four_subplots"] = all_features_path

    ph_acid_base_path = figure_dir / "ph_with_acid_base_flows.png"
    plot_ph_with_acid_base_flows(prepared_data, ph_acid_base_path, stamp_text)
    figure_paths["ph_with_acid_base_flows"] = ph_acid_base_path
    return figure_paths


def feature_columns_in_data(prepared_data: pd.DataFrame) -> list[str]:
    return [column for column in FEATURE_SPECS if column in prepared_data.columns]


def plot_single_feature(
    prepared_data: pd.DataFrame,
    column: str,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    spec = FEATURE_SPECS[column]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    plot_time_series(
        ax,
        prepared_data,
        column,
        color=spec["color"],
        linewidth=1.5,
        marker="o",
        markersize=2.6,
        markeredgewidth=0.0,
    )
    add_phase_background(ax, prepared_data)
    ax.set_xlabel("Sequential sample index")
    ax.set_ylabel(spec["ylabel"])
    ax.set_title(spec["label"])
    ax.grid(True, alpha=0.3)
    finalize_figure(fig, output_path, stamp_text)


def plot_all_features_four_subplots(
    prepared_data: pd.DataFrame,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    columns = feature_columns_in_data(prepared_data)
    fig, axes = plt.subplots(len(columns), 1, figsize=(12, 9.5), sharex=True)
    if len(columns) == 1:
        axes = [axes]

    for ax, column in zip(axes, columns):
        spec = FEATURE_SPECS[column]
        plot_time_series(
            ax,
            prepared_data,
            column,
            color=spec["color"],
            linewidth=1.35,
        )
        add_phase_background(ax, prepared_data)
        ax.set_ylabel(spec["ylabel"])
        ax.set_title(spec["label"], fontsize=11)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Sequential sample index")
    finalize_figure(fig, output_path, stamp_text)


def plot_ph_with_acid_base_flows(
    prepared_data: pd.DataFrame,
    output_path: str | Path,
    stamp_text: str,
) -> None:
    required_columns = {"ph_measured", "acid_flow", "acetate_flow"}
    missing_columns = required_columns.difference(prepared_data.columns)
    if missing_columns:
        raise KeyError(f"Missing columns for pH/acid/base plot: {sorted(missing_columns)}")

    fig, axes = plt.subplots(2, 1, figsize=(12, 7.8), sharex=True)
    plot_time_series(
        axes[0],
        prepared_data,
        "ph_measured",
        color=FEATURE_SPECS["ph_measured"]["color"],
        linewidth=1.45,
    )
    add_phase_background(axes[0], prepared_data)
    axes[0].set_ylabel("pH")
    axes[0].set_title("Measured pH")
    axes[0].grid(True, alpha=0.3)

    plot_time_series(
        axes[1],
        prepared_data,
        "acid_flow",
        color=FEATURE_SPECS["acid_flow"]["color"],
        linewidth=1.35,
        label="Acetic acid",
    )
    add_phase_background(axes[1], prepared_data)
    plot_time_series(
        axes[1],
        prepared_data,
        "acetate_flow",
        color=FEATURE_SPECS["acetate_flow"]["color"],
        linewidth=1.35,
        label="Sodium acetate",
    )
    axes[1].set_xlabel("Sequential sample index")
    axes[1].set_ylabel("Flowrate (mL/min)")
    axes[1].set_title("Acid and conjugate-base flows")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")
    finalize_figure(fig, output_path, stamp_text)


def plot_time_series(
    ax,
    prepared_data: pd.DataFrame,
    column: str,
    **plot_kwargs,
) -> None:
    ax.plot(prepared_data["sample_index"], prepared_data[column], **plot_kwargs)


def add_phase_background(ax, prepared_data: pd.DataFrame) -> None:
    if "sampling_phase_id" not in prepared_data.columns:
        return

    x_min = float(prepared_data["sample_index"].iloc[0]) - 0.5
    x_max = float(prepared_data["sample_index"].iloc[-1]) + 0.5
    previous_end = None
    for color_index, (_, group) in enumerate(
        prepared_data.groupby("sampling_phase_id", sort=True)
    ):
        start = float(group["sample_index"].iloc[0]) - 0.5
        end = float(group["sample_index"].iloc[-1]) + 0.5
        color = PHASE_SHADE_COLORS[color_index % len(PHASE_SHADE_COLORS)]
        ax.axvspan(start, end, color=color, alpha=0.55, zorder=-2)
        if previous_end is not None:
            separator_x = start
            ax.axvline(
                separator_x,
                color=PHASE_SEPARATOR_COLOR,
                linewidth=1.2,
                alpha=0.8,
                zorder=-1,
            )
        previous_end = end

        label = str(group["sampling_phase"].iloc[0])
        normal_delta_t = group.loc[~group["long_time_gap"], "delta_t_min"].dropna()
        if not normal_delta_t.empty:
            label = f"{label}\nmedian dt={normal_delta_t.median():.2f} min"
        center = (start + end) / 2.0
        ax.text(
            center,
            0.98,
            label,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8,
            color="0.25",
        )
    ax.set_xlim(x_min, x_max)


def finalize_figure(fig, output_path: str | Path, stamp_text: str) -> None:
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
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
