"""Reusable plotting functions for BioSMB experiment time resolutions."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
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
    TIME_COLUMN,
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
        label=f"Reconstructed target +/- {tolerance:.2f} pH",
    )
    axis.step(
        step_x,
        step_target,
        where="post",
        color="#D55E00",
        linewidth=2.0,
        label="Reconstructed target",
        zorder=3,
    )
    axis.set_ylabel("Tracking [pH]")
    axis.grid(True, alpha=0.22, linewidth=0.7)


def _finish_tracking_and_inputs_figure(
    figure: plt.Figure,
    axes: Sequence[plt.Axes],
    *,
    title: str,
    subtitle: str,
    experiment_end_min: float,
    generated_at: datetime,
    figure_path: Path,
) -> None:
    axes[0].set_title(title, fontsize=15, weight="bold", pad=24)
    axes[0].text(
        0.5,
        1.035,
        subtitle,
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.2,
        color="#4A4A4A",
    )
    axes[-1].set_xlabel("Elapsed time from selected experiment start [min]")
    axes[-1].set_xlim(0.0, max(experiment_end_min, 1.0))
    axes[-1].text(
        0.995,
        -0.31,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        transform=axes[-1].transAxes,
        ha="right",
        va="top",
        fontsize=8.2,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.105,
        right=0.985,
        top=0.87,
        bottom=0.12,
        hspace=0.14,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_seconds_tracking_and_inputs(
    data: pd.DataFrame,
    events: pd.DataFrame,
    stream_specs: Sequence[StreamSpec],
    *,
    tolerance: float,
    experiment_label: str,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    """Plot every raw pH and FLOW log without averaging or resampling."""

    elapsed_min = data["elapsed_seconds"].to_numpy(dtype=float) / 60.0
    experiment_end_min = float(elapsed_min[-1])
    step_x, step_target = _schedule_step_arrays(events, experiment_end_min)
    sample_intervals = data[TIME_COLUMN].diff().dt.total_seconds().dropna()

    figure, axes = plt.subplots(
        nrows=4,
        ncols=1,
        figsize=(13.5, 10.4),
        sharex=True,
        gridspec_kw={"height_ratios": [1.45, 1.0, 1.0, 1.0]},
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

    flow_upper = max(
        10.0,
        np.ceil(max(float(data[spec.flow_column].max()) for spec in stream_specs)),
    )
    for axis, spec in zip(axes[1:], stream_specs):
        values = data[spec.flow_column].to_numpy(dtype=float)
        axis.plot(
            elapsed_min,
            values,
            color=spec.color,
            linewidth=0.8,
            drawstyle="steps-post",
        )
        axis.set_ylabel(f"{spec.label}\n[mL/min]")
        axis.set_ylim(-0.2, flow_upper + 0.2)
        axis.grid(True, alpha=0.22, linewidth=0.7)
        axis.text(
            0.995,
            0.84,
            f"Range: {np.min(values):.2f} to {np.max(values):.2f} mL/min",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=8.0,
            color="#4A4A4A",
        )

    _finish_tracking_and_inputs_figure(
        figure,
        axes,
        title=f"{experiment_label}: Second-Level Logs",
        subtitle=(
            f"All {len(data):,} raw samples; no averaging | median sample "
            f"interval {sample_intervals.median():.3f} s | target reconstructed"
        ),
        experiment_end_min=experiment_end_min,
        generated_at=generated_at,
        figure_path=figure_path,
    )


def plot_minute_tracking_and_inputs(
    minute_data: pd.DataFrame,
    events: pd.DataFrame,
    stream_specs: Sequence[StreamSpec],
    *,
    tolerance: float,
    experiment_label: str,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    """Plot independent one-minute pH and FLOW summaries."""

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
        nrows=4,
        ncols=1,
        figsize=(13.5, 10.4),
        sharex=True,
        gridspec_kw={"height_ratios": [1.45, 1.0, 1.0, 1.0]},
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

    flow_upper = max(
        10.0,
        np.ceil(
            max(
                float(minute_data[f"{spec.key}_flow_max_ml_min"].max())
                for spec in stream_specs
            )
        ),
    )
    for axis, spec in zip(axes[1:], stream_specs):
        mean = minute_data[f"{spec.key}_flow_mean_ml_min"].to_numpy(
            dtype=float
        )
        lower = minute_data[f"{spec.key}_flow_min_ml_min"].to_numpy(
            dtype=float
        )
        upper = minute_data[f"{spec.key}_flow_max_ml_min"].to_numpy(
            dtype=float
        )
        axis.fill_between(
            elapsed_min,
            lower,
            upper,
            color=spec.color,
            alpha=0.12,
            label="Within-minute range",
        )
        axis.plot(
            elapsed_min,
            mean,
            color=spec.color,
            linewidth=1.35,
            marker="o",
            markersize=2.2,
            markeredgewidth=0.0,
            label="One-minute mean",
        )
        axis.set_ylabel(f"{spec.label}\n[mL/min]")
        axis.set_ylim(-0.2, flow_upper + 0.2)
        axis.grid(True, alpha=0.22, linewidth=0.7)
        axis.legend(loc="upper right", fontsize=7.5, ncols=2)

    _finish_tracking_and_inputs_figure(
        figure,
        axes,
        title=f"{experiment_label}: One-Minute Summaries",
        subtitle=(
            f"{len(minute_data):,} independent elapsed 60-second bins | "
            "mean and within-bin variability shown | target reconstructed"
        ),
        experiment_end_min=experiment_end_min,
        generated_at=generated_at,
        figure_path=figure_path,
    )


def _padded_limits(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    padding = max(0.5, 0.06 * (upper - lower))
    return lower - padding, upper + padding


def _draw_mass_flow_series(
    axis: plt.Axes,
    *,
    x: np.ndarray,
    mass_flow: np.ndarray,
    command: np.ndarray,
    changed: np.ndarray,
    stream_spec: StreamSpec,
    interval_label: str,
    show_legend: bool,
) -> None:
    axis.plot(
        x,
        mass_flow,
        color=stream_spec.color,
        linewidth=1.15,
        marker="o",
        markersize=2.7,
        markeredgewidth=0.0,
        label=(
            f"Mass-derived actual flow ({interval_label})"
            if stream_spec.mass_signal_valid_for_actual_flow
            else f"Invalid scale derivative ({interval_label})"
        ),
    )
    axis.plot(
        x,
        command,
        color="#1A1A1A",
        linewidth=1.4,
        drawstyle="steps-post",
        label="Time-weighted FLOW command",
    )
    if np.any(changed):
        axis.scatter(
            x[changed],
            mass_flow[changed],
            color="#F28E2B",
            marker="x",
            s=28,
            linewidths=1.0,
            label="Command changed inside interval",
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
    interval_label: str,
    experiment_label: str,
    figure_path: Path,
    generated_at: datetime,
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
            interval_label=interval_label,
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
            interval_label=interval_label,
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
            interval_label=interval_label,
            show_legend=True,
        )
        axis.set_ylim(*full_limits)

    axis.set_xlabel("Elapsed time from selected experiment start [min]")
    durations = stream_data["duration_seconds"].to_numpy(dtype=float)
    density = float(stream_data["density_g_ml"].iloc[0])
    figure.suptitle(
        f"{experiment_label}: {stream_spec.label} {interval_label} Flow",
        fontsize=15,
        weight="bold",
        y=0.985,
    )
    figure.text(
        0.5,
        0.945,
        (
            f"No mass averaging | density {density:.4f} g/mL | "
            f"mean exact interval {np.mean(durations):.3f} s"
        ),
        ha="center",
        va="top",
        fontsize=9.0,
        color="#4A4A4A",
    )
    footer = (
        "Bottle-out interval-average flow; not an instantaneous flowmeter."
        if stream_spec.mass_signal_valid_for_actual_flow
        else (
            "Diagnostic only: the water mass signal is invalid for actual "
            "reservoir-out flow in this experiment."
        )
    )
    figure.text(
        0.005,
        0.015,
        footer,
        ha="left",
        va="bottom",
        fontsize=8.2,
        color="#4A4A4A",
    )
    figure.text(
        0.995,
        0.015,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        ha="right",
        va="bottom",
        fontsize=8.2,
        color="#4A4A4A",
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
