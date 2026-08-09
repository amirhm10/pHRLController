"""Reusable plotting functions for BioSMB experiment time resolutions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "phrl_matplotlib"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helpers.biosmb_experiment_data import (
    PH2_COLUMN,
    SCHEDULE_COLUMN,
    StreamSpec,
)


def _schedule_step_arrays(
    events: pd.DataFrame,
    experiment_end_min: float,
) -> tuple[np.ndarray, np.ndarray]:
    block_starts = events.groupby("setpoint_block_index", sort=True).head(1)
    step_x = block_starts["elapsed_seconds"].to_numpy(dtype=float) / 60.0
    step_y = block_starts[SCHEDULE_COLUMN].to_numpy(dtype=float)
    if step_x[0] > 0.0:
        step_x = np.insert(step_x, 0, 0.0)
        step_y = np.insert(step_y, 0, step_y[0])
    step_x = np.append(step_x, experiment_end_min)
    step_y = np.append(step_y, step_y[-1])
    return step_x, step_y


def _style_tracking_axis(
    axis: plt.Axes,
    step_x: np.ndarray,
    step_target: np.ndarray,
    tolerance: float,
) -> None:
    axis.fill_between(
        step_x,
        step_target - tolerance,
        step_target + tolerance,
        step="post",
        color="#F28E2B",
        alpha=0.12,
        label=f"Target +/- {tolerance:.2f} pH",
    )
    axis.step(
        step_x,
        step_target,
        where="post",
        color="#D55E00",
        linewidth=2.0,
        label="Target",
        zorder=3,
    )
    axis.set_ylabel("Tracking [pH]")
    axis.grid(True, alpha=0.22, linewidth=0.7)


def _finish_tracking_and_inputs_figure(
    figure: plt.Figure,
    axes: Sequence[plt.Axes],
    *,
    title: str,
    experiment_end_min: float,
    figure_path: Path,
) -> None:
    axes[0].set_title(title, fontsize=15, weight="bold", pad=12)
    axes[-1].set_xlabel("Time [min]")
    axes[-1].set_xlim(0.0, max(experiment_end_min, 1.0))
    figure.subplots_adjust(
        left=0.105,
        right=0.985,
        top=0.87,
        bottom=0.08,
        hspace=0.14,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_seconds_tracking_and_inputs(
    data: pd.DataFrame,
    events: pd.DataFrame,
    mass_flow_intervals: pd.DataFrame,
    stream_specs: Sequence[StreamSpec],
    *,
    tolerance: float,
    experiment_label: str,
    figure_path: Path,
) -> None:
    """Plot raw pH/commands and interval mass-derived flows together."""

    if not stream_specs:
        raise ValueError("At least one stream is required for plotting.")

    elapsed_min = data["elapsed_seconds"].to_numpy(dtype=float) / 60.0
    experiment_end_min = float(elapsed_min[-1])
    step_x, step_target = _schedule_step_arrays(events, experiment_end_min)

    figure, axes = plt.subplots(
        nrows=1 + len(stream_specs),
        ncols=1,
        figsize=(13.5, 4.0 + 2.15 * len(stream_specs)),
        sharex=True,
        gridspec_kw={"height_ratios": [1.45, *([1.0] * len(stream_specs))]},
    )
    _style_tracking_axis(axes[0], step_x, step_target, tolerance)
    axes[0].plot(
        elapsed_min,
        data[PH2_COLUMN],
        color="#0072B2",
        linewidth=0.85,
        label="Measured PH_2 at every CSV timestamp",
        zorder=4,
    )
    axes[0].legend(
        loc="upper right",
        ncols=2,
        frameon=True,
        framealpha=0.95,
        fontsize=8.0,
    )

    for axis, spec in zip(axes[1:], stream_specs):
        _plot_combined_flow_axis(
            axis,
            command_x=elapsed_min,
            command=data[spec.flow_column].to_numpy(dtype=float),
            mass_flow_intervals=mass_flow_intervals,
            stream_spec=spec,
        )

    _finish_tracking_and_inputs_figure(
        figure,
        axes,
        title=experiment_label,
        experiment_end_min=experiment_end_min,
        figure_path=figure_path,
    )


def plot_minute_tracking_and_inputs(
    minute_data: pd.DataFrame,
    events: pd.DataFrame,
    mass_flow_intervals: pd.DataFrame,
    stream_specs: Sequence[StreamSpec],
    *,
    tolerance: float,
    experiment_label: str,
    figure_path: Path,
) -> None:
    """Plot one-minute pH, commands, and mass-derived flows together."""

    if not stream_specs:
        raise ValueError("At least one stream is required for plotting.")

    elapsed_min = (
        minute_data["elapsed_seconds_center"].to_numpy(dtype=float) / 60.0
    )
    experiment_end_min = max(
        float(minute_data["utc_last"].iloc[-1].timestamp()),
        float(minute_data["utc_first"].iloc[-1].timestamp()),
    )
    start_timestamp = float(minute_data["utc_first"].iloc[0].timestamp())
    experiment_end_min = (experiment_end_min - start_timestamp) / 60.0
    step_x, step_target = _schedule_step_arrays(events, experiment_end_min)

    figure, axes = plt.subplots(
        nrows=1 + len(stream_specs),
        ncols=1,
        figsize=(13.5, 4.0 + 2.15 * len(stream_specs)),
        sharex=True,
        gridspec_kw={"height_ratios": [1.45, *([1.0] * len(stream_specs))]},
    )
    _style_tracking_axis(axes[0], step_x, step_target, tolerance)
    ph_mean = minute_data["ph2_mean"].to_numpy(dtype=float)
    ph_std = minute_data["ph2_std"].to_numpy(dtype=float)
    axes[0].fill_between(
        elapsed_min,
        ph_mean - ph_std,
        ph_mean + ph_std,
        color="#0072B2",
        alpha=0.14,
        label="Within-minute PH_2 standard deviation",
    )
    axes[0].plot(
        elapsed_min,
        ph_mean,
        color="#0072B2",
        linewidth=1.6,
        marker="o",
        markersize=2.5,
        markeredgewidth=0.0,
        label="PH_2 one-minute mean",
        zorder=4,
    )
    axes[0].legend(
        loc="upper right",
        ncols=2,
        frameon=True,
        framealpha=0.95,
        fontsize=8.0,
    )

    for axis, spec in zip(axes[1:], stream_specs):
        stream_intervals = mass_flow_intervals.loc[
            mass_flow_intervals["stream"].eq(spec.key)
        ]
        _plot_combined_flow_axis(
            axis,
            command_x=(
                stream_intervals["elapsed_seconds_end"].to_numpy(dtype=float)
                / 60.0
            ),
            command=stream_intervals[
                "commanded_flow_time_weighted_ml_min"
            ].to_numpy(dtype=float),
            mass_flow_intervals=mass_flow_intervals,
            stream_spec=spec,
        )

    _finish_tracking_and_inputs_figure(
        figure,
        axes,
        title=experiment_label,
        experiment_end_min=experiment_end_min,
        figure_path=figure_path,
    )


def _padded_limits(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    padding = max(0.5, 0.06 * (upper - lower))
    return lower - padding, upper + padding


def _plot_combined_flow_axis(
    axis: plt.Axes,
    *,
    command_x: np.ndarray,
    command: np.ndarray,
    mass_flow_intervals: pd.DataFrame,
    stream_spec: StreamSpec,
) -> None:
    """Draw comparable commanded and gravimetric flow on one stream panel."""

    stream_data = mass_flow_intervals.loc[
        mass_flow_intervals["stream"].eq(stream_spec.key)
    ]
    if stream_data.empty:
        raise ValueError(f"No interval data found for {stream_spec.key}.")
    mass_x = (
        stream_data["elapsed_seconds_end"].to_numpy(dtype=float) / 60.0
    )
    value_column = (
        "actual_flow_ml_min"
        if stream_spec.mass_signal_valid_for_actual_flow
        else "mass_derived_flow_ml_min"
    )
    mass_flow = stream_data[value_column].to_numpy(dtype=float)
    if not np.isfinite(mass_flow).all():
        raise ValueError(
            f"Nonfinite mass-derived flow values found for {stream_spec.key}."
        )

    axis.plot(
        command_x,
        command,
        color="#1A1A1A",
        linewidth=1.25,
        drawstyle="steps-post",
        label="Commanded flow",
        zorder=2,
    )
    axis.plot(
        mass_x,
        mass_flow,
        color=stream_spec.color,
        linewidth=0.9,
        marker="o",
        markersize=2.0,
        markeredgewidth=0.0,
        alpha=0.88,
        label="Calculated flow",
        zorder=3,
    )
    axis.axhline(0.0, color="#777777", linewidth=0.7, alpha=0.5)
    axis.set_ylabel(f"{stream_spec.label}\n[mL/min]")
    axis.grid(True, alpha=0.22, linewidth=0.7)

    combined = np.concatenate([mass_flow, command])
    full_limits = _padded_limits(combined)
    quantile_limits = np.quantile(mass_flow, [0.001, 0.999])
    central_mass_flow = mass_flow[
        (mass_flow >= quantile_limits[0])
        & (mass_flow <= quantile_limits[1])
    ]
    central_limits = _padded_limits(
        np.concatenate([central_mass_flow, command])
    )
    full_span = full_limits[1] - full_limits[0]
    central_span = central_limits[1] - central_limits[0]
    use_full_range_inset = full_span > 3.0 * central_span
    axis.set_ylim(*(central_limits if use_full_range_inset else full_limits))

    negative_count = int(np.count_nonzero(mass_flow < 0.0))
    if negative_count:
        axis.text(
            0.005,
            0.04,
            (
                f"{negative_count} negative calculated interval(s): "
                "recorded mass increased over the interval"
            ),
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=7.4,
            color="#7A3E00",
            bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "none"},
            zorder=6,
        )

    if use_full_range_inset:
        inset = axis.inset_axes([0.72, 0.10, 0.27, 0.38])
        inset.plot(
            command_x,
            command,
            color="#1A1A1A",
            linewidth=0.7,
            drawstyle="steps-post",
        )
        inset.plot(
            mass_x,
            mass_flow,
            color=stream_spec.color,
            linewidth=0.55,
        )
        inset.axhline(0.0, color="#777777", linewidth=0.5, alpha=0.5)
        inset.set_xlim(axis.get_xlim())
        inset.set_ylim(*full_limits)
        inset.set_title("Full recorded range", fontsize=6.8, pad=1.5)
        inset.tick_params(labelsize=5.8, length=2)
        inset.grid(True, alpha=0.16, linewidth=0.4)

    axis.legend(loc="upper left", fontsize=7.4, ncols=2, framealpha=0.93)


def _draw_mass_flow_series(
    axis: plt.Axes,
    *,
    x: np.ndarray,
    mass_flow: np.ndarray,
    command: np.ndarray,
    changed: np.ndarray,
    stream_spec: StreamSpec,
    show_legend: bool,
) -> None:
    axis.plot(
        x,
        command,
        color="#1A1A1A",
        linewidth=1.4,
        drawstyle="steps-post",
        label="Commanded flow",
        zorder=2,
    )
    axis.plot(
        x,
        mass_flow,
        color=stream_spec.color,
        linewidth=1.15,
        marker="o",
        markersize=2.7,
        markeredgewidth=0.0,
        label="Calculated flow",
        zorder=3,
    )
    if np.any(changed):
        axis.scatter(
            x[changed],
            mass_flow[changed],
            color="#F28E2B",
            marker="x",
            s=28,
            linewidths=1.0,
            label="_nolegend_",
            zorder=5,
        )
    axis.axhline(0.0, color="#777777", linewidth=0.7, alpha=0.5)
    axis.set_xlim(0.0, max(float(x[-1]), 1.0))
    axis.set_ylabel("Flow [mL/min]")
    axis.grid(True, alpha=0.22, linewidth=0.7)
    if show_legend:
        axis.legend(loc="best", fontsize=8.5, framealpha=0.95)


def plot_mass_flow_intervals(
    interval_data: pd.DataFrame,
    stream_spec: StreamSpec,
    *,
    experiment_label: str,
    figure_path: Path,
) -> None:
    """Plot one stream's mass-derived and commanded flow at one resolution."""

    stream_data = interval_data.loc[
        interval_data["stream"].eq(stream_spec.key)
    ].copy()
    if stream_data.empty:
        raise ValueError(f"No interval data found for {stream_spec.key}.")
    x = stream_data["elapsed_seconds_end"].to_numpy(dtype=float) / 60.0
    command = stream_data[
        "commanded_flow_time_weighted_ml_min"
    ].to_numpy(dtype=float)
    value_column = (
        "actual_flow_ml_min"
        if stream_spec.mass_signal_valid_for_actual_flow
        else "mass_derived_flow_ml_min"
    )
    mass_flow = stream_data[value_column].to_numpy(dtype=float)
    changed = stream_data["command_changed_within_interval"].to_numpy(
        dtype=bool
    )
    full_values = np.concatenate([mass_flow, command])
    full_limits = _padded_limits(full_values)
    quantile_limits = np.quantile(mass_flow, [0.005, 0.995])
    central_mass_flow = mass_flow[
        (mass_flow >= quantile_limits[0])
        & (mass_flow <= quantile_limits[1])
    ]
    central_limits = _padded_limits(
        np.concatenate([central_mass_flow, command])
    )
    full_span = full_limits[1] - full_limits[0]
    central_span = central_limits[1] - central_limits[0]
    use_zoom_panel = full_span > 3.0 * central_span

    if use_zoom_panel:
        figure, axes = plt.subplots(
            nrows=2,
            ncols=1,
            figsize=(13.2, 8.2),
            sharex=True,
            gridspec_kw={"height_ratios": [0.8, 1.4]},
        )
        overview_axis, axis = axes
        _draw_mass_flow_series(
            overview_axis,
            x=x,
            mass_flow=mass_flow,
            command=command,
            changed=changed,
            stream_spec=stream_spec,
            show_legend=False,
        )
        overview_axis.set_ylim(*full_limits)
        overview_axis.text(
            0.005,
            0.94,
            "Full recorded range; outliers retained",
            transform=overview_axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.2,
            color="#4A4A4A",
        )
        _draw_mass_flow_series(
            axis,
            x=x,
            mass_flow=mass_flow,
            command=command,
            changed=changed,
            stream_spec=stream_spec,
            show_legend=True,
        )
        axis.set_ylim(*central_limits)
        axis.text(
            0.005,
            0.94,
            "Central 0.5-99.5% mass-flow range",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.2,
            color="#4A4A4A",
        )
    else:
        figure, axis = plt.subplots(figsize=(13.2, 6.8))
        axes = np.asarray([axis])
        _draw_mass_flow_series(
            axis,
            x=x,
            mass_flow=mass_flow,
            command=command,
            changed=changed,
            stream_spec=stream_spec,
            show_legend=True,
        )
        axis.set_ylim(*full_limits)

    axis.set_xlabel("Time [min]")
    figure.suptitle(
        experiment_label,
        fontsize=15,
        weight="bold",
        y=0.985,
    )
    figure.subplots_adjust(
        left=0.08,
        right=0.985,
        top=0.90,
        bottom=0.09,
        hspace=0.14 if use_zoom_panel else 0.0,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)
