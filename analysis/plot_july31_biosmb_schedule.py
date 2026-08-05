"""Reconstruct and plot the July 31 BioSMB scheduled pH experiment.

The lab CSV did not log ``target_ph``. This script reconstructs the scheduled
target from the controller's ping-pong scheduler and averages the reliable
``PH_2`` measurement over consecutive elapsed 60-second bins. It also plots
the July 31 pump mapping for water, acetic acid, and sodium acetate as
synchronized subplots, both alone and beneath the pH tracking panel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "phrl_matplotlib"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PH2_COLUMN = "biosmb-sensors.PH_2"
TIME_COLUMN = "utc_time"
FLOW_COLUMNS = [f"biosmb-flows[{index}]" for index in range(7)]
# The July 31 hardware used pump 4 for Arium water, which appears in the
# zero-based CSV export as biosmb-flows[3]. This historical mapping differs
# from compact project datasets that expose water as biosmb-flows[2].
MANIPULATED_INPUTS = [
    ("biosmb-flows[3]", "Arium water", "#4E79A7"),
    ("biosmb-flows[0]", "Acetic acid", "#E15759"),
    ("biosmb-flows[1]", "Sodium acetate (base)", "#59A14F"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct the missing scheduled target and plot it against "
            "one-minute-average PH_2."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data/July31 BioSMB RL Test.csv"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--target-min", type=float, default=3.9)
    parser.add_argument("--target-max", type=float, default=5.5)
    parser.add_argument("--setpoint-count", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--consecutive-required", type=int, default=5)
    parser.add_argument("--tolerance", type=float, default=0.1)
    parser.add_argument("--bin-seconds", type=float, default=60.0)
    parser.add_argument("--flow-change-threshold", type=float, default=1.0e-6)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.target_min >= args.target_max:
        raise ValueError("--target-min must be smaller than --target-max.")
    if args.setpoint_count < 2:
        raise ValueError("--setpoint-count must be at least 2.")
    if args.max_steps <= 0 or args.consecutive_required <= 0:
        raise ValueError("Scheduler step counts must be positive.")
    if args.tolerance < 0.0:
        raise ValueError("--tolerance must be nonnegative.")
    if args.bin_seconds <= 0.0:
        raise ValueError("--bin-seconds must be positive.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lab_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    required = [TIME_COLUMN, PH2_COLUMN, *FLOW_COLUMNS]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required CSV columns: {missing}")

    data[TIME_COLUMN] = pd.to_datetime(
        data[TIME_COLUMN],
        utc=True,
        errors="raise",
    )
    numeric_columns = [PH2_COLUMN, *FLOW_COLUMNS]
    data[numeric_columns] = data[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if data[TIME_COLUMN].isna().any() or data[PH2_COLUMN].isna().any():
        raise ValueError("The time or PH_2 column contains invalid values.")
    if not data[TIME_COLUMN].is_monotonic_increasing:
        data = data.sort_values(TIME_COLUMN).reset_index(drop=True)
    return data


def find_controller_events(
    data: pd.DataFrame,
    flow_change_threshold: float,
) -> tuple[np.ndarray, int, dict[str, float]]:
    flow_change = data[FLOW_COLUMNS].diff().abs().max(axis=1)
    event_mask = flow_change.gt(flow_change_threshold).to_numpy(copy=True)
    event_mask[0] = True
    all_event_rows = np.flatnonzero(event_mask)
    if len(all_event_rows) < 2:
        raise ValueError("Fewer than two controller action events were found.")

    event_times = data.loc[all_event_rows, TIME_COLUMN].reset_index(drop=True)
    event_gaps = event_times.diff().dt.total_seconds().to_numpy()[1:]
    largest_gap_position = int(np.argmax(event_gaps))
    largest_gap_seconds = float(event_gaps[largest_gap_position])
    median_gap_seconds = float(np.median(event_gaps))

    run_event_offset = 0
    if largest_gap_seconds > 2.0 * median_gap_seconds:
        run_event_offset = largest_gap_position + 1

    run_event_rows = all_event_rows[run_event_offset:]
    regular_gaps = (
        data.loc[run_event_rows, TIME_COLUMN]
        .reset_index(drop=True)
        .diff()
        .dt.total_seconds()
        .dropna()
    )
    diagnostics = {
        "all_action_event_count": int(len(all_event_rows)),
        "selected_action_event_count": int(len(run_event_rows)),
        "largest_preselection_gap_seconds": largest_gap_seconds,
        "all_event_median_gap_seconds": median_gap_seconds,
        "selected_event_median_gap_seconds": float(regular_gaps.median()),
    }
    return run_event_rows, run_event_offset, diagnostics


def reconstruct_schedule(
    data: pd.DataFrame,
    event_rows: np.ndarray,
    target_min: float,
    target_max: float,
    setpoint_count: int,
    max_steps: int,
    consecutive_required: int,
    tolerance: float,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    target_values = np.linspace(target_min, target_max, setpoint_count)
    forward = np.arange(setpoint_count, dtype=int)
    reverse = np.arange(setpoint_count - 2, 0, -1, dtype=int)
    cycle_indices = np.concatenate([forward, reverse])

    cycle_position = 0
    steps_at_target = 0
    consecutive_in_tolerance = 0
    run_start_time = data.at[int(event_rows[0]), TIME_COLUMN]
    records: list[dict[str, object]] = []

    for action_index, row_index_raw in enumerate(event_rows):
        row_index = int(row_index_raw)
        timestamp = data.at[row_index, TIME_COLUMN]
        measured_ph = float(data.at[row_index, PH2_COLUMN])
        evaluated_target = float(target_values[cycle_indices[cycle_position]])
        within_tolerance: bool | None = None
        target_changed = False
        change_reason = "initialization" if action_index == 0 else "hold"

        if action_index > 0:
            steps_at_target += 1
            within_tolerance = abs(measured_ph - evaluated_target) <= tolerance
            if within_tolerance:
                consecutive_in_tolerance += 1
            else:
                consecutive_in_tolerance = 0

            maximum_reached = steps_at_target >= max_steps
            consecutive_reached = (
                consecutive_in_tolerance >= consecutive_required
            )
            target_changed = maximum_reached or consecutive_reached
            if maximum_reached and consecutive_reached:
                change_reason = "maximum_steps_and_consecutive_in_tolerance"
            elif maximum_reached:
                change_reason = "maximum_steps"
            elif consecutive_reached:
                change_reason = "consecutive_in_tolerance"

            if target_changed:
                cycle_position = (cycle_position + 1) % len(cycle_indices)

        applied_target = float(target_values[cycle_indices[cycle_position]])
        record: dict[str, object] = {
            "action_index": action_index,
            "source_row_index": row_index,
            "utc_time": timestamp.isoformat(),
            "elapsed_min": (
                timestamp - run_start_time
            ).total_seconds()
            / 60.0,
            "ph2_at_action": measured_ph,
            "evaluated_target_ph": (
                np.nan if action_index == 0 else evaluated_target
            ),
            "within_tolerance": within_tolerance,
            "completed_steps_at_target": (
                0 if action_index == 0 else steps_at_target
            ),
            "consecutive_steps_in_tolerance": (
                0 if action_index == 0 else consecutive_in_tolerance
            ),
            "target_changed": target_changed,
            "change_reason": change_reason,
            "applied_target_ph": applied_target,
        }
        for flow_column in FLOW_COLUMNS:
            record[flow_column] = float(data.at[row_index, flow_column])
        records.append(record)

        if target_changed:
            steps_at_target = 0
            consecutive_in_tolerance = 0

    return pd.DataFrame(records), target_values, cycle_indices


def assign_schedule_to_samples(
    data: pd.DataFrame,
    event_rows: np.ndarray,
    events: pd.DataFrame,
) -> pd.DataFrame:
    run_data = data.iloc[int(event_rows[0]) :].copy()
    source_rows = run_data.index.to_numpy()
    event_lookup = np.searchsorted(event_rows, source_rows, side="right") - 1
    event_targets = events["applied_target_ph"].to_numpy(dtype=float)
    run_data["reconstructed_target_ph"] = event_targets[event_lookup]
    run_start = run_data[TIME_COLUMN].iloc[0]
    run_data["elapsed_seconds"] = (
        run_data[TIME_COLUMN] - run_start
    ).dt.total_seconds()
    return run_data


def aggregate_one_minute(
    run_data: pd.DataFrame,
    events: pd.DataFrame,
    bin_seconds: float,
) -> pd.DataFrame:
    prepared = run_data.copy()
    prepared["minute_index"] = np.floor(
        prepared["elapsed_seconds"] / bin_seconds
    ).astype(int)
    grouped = prepared.groupby("minute_index", sort=True)

    summary = grouped.agg(
        ph2_mean=(PH2_COLUMN, "mean"),
        ph2_std=(PH2_COLUMN, lambda values: values.std(ddof=0)),
        ph2_min=(PH2_COLUMN, "min"),
        ph2_max=(PH2_COLUMN, "max"),
        sample_count=(PH2_COLUMN, "size"),
        elapsed_seconds_mean=("elapsed_seconds", "mean"),
        target_value_count=("reconstructed_target_ph", "nunique"),
    ).reset_index()

    dominant_targets = grouped["reconstructed_target_ph"].agg(
        lambda values: float(values.value_counts().index[0])
    )
    summary["dominant_target_ph"] = summary["minute_index"].map(
        dominant_targets
    )
    summary["target_changed_within_bin"] = (
        summary["target_value_count"] > 1
    )
    summary["elapsed_min_start"] = (
        summary["minute_index"] * bin_seconds / 60.0
    )
    summary["elapsed_min_center"] = (
        summary["elapsed_min_start"] + bin_seconds / 120.0
    )

    event_elapsed_seconds = (
        events["elapsed_min"].to_numpy(dtype=float) * 60.0
    )
    center_seconds = (
        summary["elapsed_min_center"].to_numpy(dtype=float) * 60.0
    )
    center_event_indices = (
        np.searchsorted(
            event_elapsed_seconds,
            center_seconds,
            side="right",
        )
        - 1
    )
    center_event_indices = np.clip(
        center_event_indices,
        0,
        len(events) - 1,
    )
    summary["target_ph_at_bin_center"] = events[
        "applied_target_ph"
    ].to_numpy(dtype=float)[center_event_indices]

    run_start = run_data[TIME_COLUMN].iloc[0]
    run_end = run_data[TIME_COLUMN].iloc[-1]
    utc_starts = run_start + pd.to_timedelta(
        summary["minute_index"] * bin_seconds,
        unit="s",
    )
    utc_ends = utc_starts + pd.to_timedelta(bin_seconds, unit="s")
    utc_ends = utc_ends.where(utc_ends <= run_end, run_end)
    summary["utc_start"] = utc_starts.map(lambda value: value.isoformat())
    summary["utc_end"] = utc_ends.map(lambda value: value.isoformat())
    return summary[
        [
            "minute_index",
            "utc_start",
            "utc_end",
            "elapsed_min_start",
            "elapsed_min_center",
            "elapsed_seconds_mean",
            "ph2_mean",
            "ph2_std",
            "ph2_min",
            "ph2_max",
            "sample_count",
            "target_ph_at_bin_center",
            "dominant_target_ph",
            "target_changed_within_bin",
        ]
    ]


def build_schedule_segments(
    events: pd.DataFrame,
    run_end_time: pd.Timestamp,
) -> pd.DataFrame:
    segment_id = events["applied_target_ph"].ne(
        events["applied_target_ph"].shift()
    ).cumsum()
    segments: list[dict[str, object]] = []
    grouped_events = list(events.groupby(segment_id, sort=True))
    for group_position, (_, group) in enumerate(grouped_events):
        start = pd.Timestamp(group["utc_time"].iloc[0])
        if group_position + 1 < len(grouped_events):
            next_group_first = grouped_events[group_position + 1][1].iloc[0]
            end = pd.Timestamp(next_group_first["utc_time"])
            completed_steps = int(
                next_group_first["completed_steps_at_target"]
            )
            advance_reason = str(next_group_first["change_reason"])
        else:
            end = run_end_time
            completed_steps = max(len(group) - 1, 0)
            advance_reason = "data_end_before_next_switch"
        segments.append(
            {
                "segment_index": group_position,
                "target_ph": float(group["applied_target_ph"].iloc[0]),
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "duration_min": (end - start).total_seconds() / 60.0,
                "start_action_index": int(group["action_index"].iloc[0]),
                "end_action_index": int(group["action_index"].iloc[-1]),
                "completed_controller_steps": completed_steps,
                "advance_reason": advance_reason,
            }
        )
    return pd.DataFrame(segments)


def calculate_tracking_metrics(
    minute_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    evaluated = minute_data.copy()
    evaluated["error"] = (
        evaluated["ph2_mean"] - evaluated["target_ph_at_bin_center"]
    )
    error = evaluated["error"].to_numpy(dtype=float)
    overall = pd.DataFrame(
        [
            {
                "minute_bin_count": len(evaluated),
                "target_transition_bin_count": int(
                    evaluated["target_changed_within_bin"].sum()
                ),
                "mean_error": float(np.mean(error)),
                "mae": float(np.mean(np.abs(error))),
                "rmse": float(np.sqrt(np.mean(np.square(error)))),
                "max_absolute_error": float(np.max(np.abs(error))),
                "fraction_within_0.1_ph": float(
                    np.mean(np.abs(error) <= 0.1)
                ),
            }
        ]
    )

    by_target_records = []
    for target, group in evaluated.groupby(
        "target_ph_at_bin_center",
        sort=True,
    ):
        target_error = group["error"].to_numpy(dtype=float)
        by_target_records.append(
            {
                "target_ph": float(target),
                "minute_bin_count": len(group),
                "mean_error": float(np.mean(target_error)),
                "mae": float(np.mean(np.abs(target_error))),
                "rmse": float(np.sqrt(np.mean(np.square(target_error)))),
                "max_absolute_error": float(
                    np.max(np.abs(target_error))
                ),
                "fraction_within_0.1_ph": float(
                    np.mean(np.abs(target_error) <= 0.1)
                ),
            }
        )
    return overall, pd.DataFrame(by_target_records)


def calculate_flow_switch_diagnostic(events: pd.DataFrame) -> dict[str, float]:
    acid = events[FLOW_COLUMNS[0]].to_numpy(dtype=float)
    acetate = events[FLOW_COLUMNS[1]].to_numpy(dtype=float)
    valid = (acid > 0.0) & (acetate > 0.0)
    log_ratio = np.full(len(events), np.nan)
    log_ratio[valid] = np.log10(acetate[valid] / acid[valid])
    ratio_change = np.abs(np.diff(log_ratio))
    switches = events["target_changed"].to_numpy(dtype=bool)[1:]
    return {
        "median_abs_log10_acetate_acid_ratio_change_at_switch": float(
            np.nanmedian(ratio_change[switches])
        ),
        "median_abs_log10_acetate_acid_ratio_change_while_holding": float(
            np.nanmedian(ratio_change[~switches])
        ),
    }


def calculate_raw_input_log_diagnostics(
    run_data: pd.DataFrame,
    flow_change_threshold: float,
) -> dict[str, object]:
    elapsed_seconds = run_data["elapsed_seconds"].to_numpy(dtype=float)
    sample_intervals = np.diff(elapsed_seconds)
    stream_diagnostics = []
    for column, label, _ in MANIPULATED_INPUTS:
        values = run_data[column].to_numpy(dtype=float)
        changes = np.abs(np.diff(values))
        stream_diagnostics.append(
            {
                "column": column,
                "stream": label,
                "minimum_ml_min": float(np.min(values)),
                "maximum_ml_min": float(np.max(values)),
                "unique_logged_value_count": int(
                    run_data[column].nunique()
                ),
                "sample_to_sample_change_count": int(
                    np.sum(changes > flow_change_threshold)
                ),
                "maximum_delta_below_change_threshold": float(
                    np.max(
                        changes[changes <= flow_change_threshold],
                        initial=0.0,
                    )
                ),
            }
        )
    return {
        "sample_count": int(len(run_data)),
        "duration_minutes": float(elapsed_seconds[-1] / 60.0),
        "sample_interval_seconds": {
            "minimum": float(np.min(sample_intervals)),
            "median": float(np.median(sample_intervals)),
            "mean": float(np.mean(sample_intervals)),
            "p95": float(np.quantile(sample_intervals, 0.95)),
            "maximum": float(np.max(sample_intervals)),
        },
        "averaging_or_resampling": "none",
        "streams": stream_diagnostics,
    }


def plot_results(
    minute_data: pd.DataFrame,
    events: pd.DataFrame,
    target_values: np.ndarray,
    tolerance: float,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    x_ph = minute_data["elapsed_min_center"].to_numpy(dtype=float)
    ph_mean = minute_data["ph2_mean"].to_numpy(dtype=float)
    ph_std = minute_data["ph2_std"].to_numpy(dtype=float)
    event_x = events["elapsed_min"].to_numpy(dtype=float)
    event_target = events["applied_target_ph"].to_numpy(dtype=float)
    experiment_end = max(float(x_ph[-1]), float(event_x[-1]))
    step_x = np.append(event_x, experiment_end)
    step_target = np.append(event_target, event_target[-1])

    figure, axis = plt.subplots(figsize=(13.2, 6.8))
    axis.fill_between(
        step_x,
        step_target - tolerance,
        step_target + tolerance,
        step="post",
        color="#F28E2B",
        alpha=0.12,
        label=f"Setpoint tolerance (±{tolerance:.1f} pH)",
    )
    axis.step(
        step_x,
        step_target,
        where="post",
        color="#D55E00",
        linewidth=2.3,
        label="Reconstructed scheduled setpoint",
        zorder=3,
    )
    axis.fill_between(
        x_ph,
        ph_mean - ph_std,
        ph_mean + ph_std,
        color="#0072B2",
        alpha=0.14,
        label="Within-minute PH₂ standard deviation",
    )
    axis.plot(
        x_ph,
        ph_mean,
        color="#0072B2",
        linewidth=1.8,
        marker="o",
        markersize=3.2,
        markeredgewidth=0.0,
        label="PH₂ mean over each elapsed 60-s bin",
        zorder=4,
    )

    switch_rows = events[events["target_changed"]]
    for switch_time in switch_rows["elapsed_min"].to_numpy(dtype=float):
        axis.axvline(
            switch_time,
            color="#6F6F6F",
            linewidth=0.55,
            alpha=0.18,
            zorder=0,
        )

    axis.set_title(
        "July 31 BioSMB RL Test: Scheduled Setpoint vs Observed PH₂",
        fontsize=15,
        weight="bold",
        pad=16,
    )
    axis.text(
        0.5,
        1.015,
        (
            "Setpoints reconstructed from scheduler behavior (not logged); "
            "PH₂ averaged over consecutive elapsed 60-second bins"
        ),
        transform=axis.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#4A4A4A",
    )
    axis.set_xlabel("Elapsed time from reconstructed run start [min]")
    axis.set_ylabel("pH")
    axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
    axis.set_xlim(0.0, max(float(step_x[-1]), 1.0))
    all_values = np.concatenate([ph_mean - ph_std, ph_mean + ph_std, step_target])
    axis.set_ylim(
        np.floor((np.nanmin(all_values) - 0.08) * 10.0) / 10.0,
        np.ceil((np.nanmax(all_values) + 0.08) * 10.0) / 10.0,
    )
    axis.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=9)
    axis.text(
        0.005,
        -0.17,
        (
            "Inferred target levels: "
            + ", ".join(f"{value:.1f}" for value in target_values)
            + " | Method: ping-pong scheduler reconstruction"
        ),
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    axis.text(
        0.995,
        -0.17,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    figure.subplots_adjust(left=0.075, right=0.985, top=0.86, bottom=0.20)
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_manipulated_inputs(
    events: pd.DataFrame,
    experiment_end_min: float,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    event_x = events["elapsed_min"].to_numpy(dtype=float)
    step_x = np.append(event_x, experiment_end_min)
    observed_max = max(
        float(events[column].max())
        for column, _, _ in MANIPULATED_INPUTS
    )
    y_upper = max(10.0, np.ceil(observed_max))

    figure, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(13.2, 8.4),
        sharex=True,
        sharey=True,
    )
    for axis, (column, label, color) in zip(axes, MANIPULATED_INPUTS):
        values = events[column].to_numpy(dtype=float)
        step_values = np.append(values, values[-1])
        axis.step(
            step_x,
            step_values,
            where="post",
            color=color,
            linewidth=1.8,
        )
        axis.set_ylabel(f"{label}\n[mL/min]")
        axis.set_ylim(-0.2, y_upper + 0.2)
        axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
        axis.text(
            0.995,
            0.88,
            f"Range: {np.min(values):.2f} to {np.max(values):.2f} mL/min",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=8.5,
            color="#4A4A4A",
        )

    axes[0].set_title(
        "July 31 BioSMB RL Test: Manipulated Input Flows",
        fontsize=15,
        weight="bold",
        pad=24,
    )
    axes[0].text(
        0.5,
        1.035,
        (
            "July 31 pump mapping; water = flows[3], "
            "acid = flows[0], base = flows[1]"
        ),
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#4A4A4A",
    )
    axes[-1].set_xlabel("Elapsed time from reconstructed run start [min]")
    axes[-1].set_xlim(0.0, max(experiment_end_min, 1.0))
    axes[-1].text(
        0.995,
        -0.28,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        transform=axes[-1].transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.12,
        right=0.985,
        top=0.87,
        bottom=0.12,
        hspace=0.12,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_raw_input_logs(
    run_data: pd.DataFrame,
    diagnostics: dict[str, object],
    figure_path: Path,
    generated_at: datetime,
) -> None:
    elapsed_min = (
        run_data["elapsed_seconds"].to_numpy(dtype=float) / 60.0
    )
    observed_max = max(
        float(run_data[column].max())
        for column, _, _ in MANIPULATED_INPUTS
    )
    y_upper = max(10.0, np.ceil(observed_max))
    interval_stats = diagnostics["sample_interval_seconds"]

    figure, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(13.2, 8.4),
        sharex=True,
        sharey=True,
    )
    for axis, (column, label, color) in zip(axes, MANIPULATED_INPUTS):
        values = run_data[column].to_numpy(dtype=float)
        axis.plot(
            elapsed_min,
            values,
            color=color,
            linewidth=0.8,
            marker=".",
            markersize=1.2,
            markeredgewidth=0.0,
        )
        axis.set_ylabel(f"{label}\n[mL/min]")
        axis.set_ylim(-0.2, y_upper + 0.2)
        axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
        axis.text(
            0.995,
            0.88,
            (
                f"Range: {np.min(values):.2f} to "
                f"{np.max(values):.2f} mL/min"
            ),
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=8.5,
            color="#4A4A4A",
        )

    axes[0].set_title(
        "July 31 BioSMB RL Test: Raw Approximately 1-Second Input Logs",
        fontsize=15,
        weight="bold",
        pad=24,
    )
    axes[0].text(
        0.5,
        1.035,
        (
            f"All {diagnostics['sample_count']:,} selected-run CSV samples "
            "at actual timestamps; no averaging or resampling | "
            f"median interval {interval_stats['median']:.3f} s"
        ),
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.3,
        color="#4A4A4A",
    )
    axes[-1].set_xlabel("Elapsed time from reconstructed run start [min]")
    axes[-1].set_xlim(0.0, max(float(elapsed_min[-1]), 1.0))
    axes[-1].text(
        0.005,
        -0.28,
        (
            "July 31 mapping: water = flows[3], acid = flows[0], "
            "sodium acetate = flows[1]"
        ),
        transform=axes[-1].transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    axes[-1].text(
        0.995,
        -0.28,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        transform=axes[-1].transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.12,
        right=0.985,
        top=0.87,
        bottom=0.12,
        hspace=0.12,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_tracking_and_inputs(
    minute_data: pd.DataFrame,
    events: pd.DataFrame,
    tolerance: float,
    experiment_end_min: float,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    x_ph = minute_data["elapsed_min_center"].to_numpy(dtype=float)
    ph_mean = minute_data["ph2_mean"].to_numpy(dtype=float)
    ph_std = minute_data["ph2_std"].to_numpy(dtype=float)
    event_x = events["elapsed_min"].to_numpy(dtype=float)
    event_target = events["applied_target_ph"].to_numpy(dtype=float)
    step_x = np.append(event_x, experiment_end_min)
    step_target = np.append(event_target, event_target[-1])
    observed_flow_max = max(
        float(events[column].max())
        for column, _, _ in MANIPULATED_INPUTS
    )
    flow_y_upper = max(10.0, np.ceil(observed_flow_max))

    figure, axes = plt.subplots(
        nrows=4,
        ncols=1,
        figsize=(13.2, 10.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.45, 1.0, 1.0, 1.0]},
    )
    tracking_axis = axes[0]
    tracking_axis.fill_between(
        step_x,
        step_target - tolerance,
        step_target + tolerance,
        step="post",
        color="#F28E2B",
        alpha=0.12,
        label=f"Setpoint tolerance (+/-{tolerance:.1f} pH)",
    )
    tracking_axis.step(
        step_x,
        step_target,
        where="post",
        color="#D55E00",
        linewidth=2.1,
        label="Reconstructed setpoint",
        zorder=3,
    )
    tracking_axis.fill_between(
        x_ph,
        ph_mean - ph_std,
        ph_mean + ph_std,
        color="#0072B2",
        alpha=0.14,
        label="Within-minute PH2 standard deviation",
    )
    tracking_axis.plot(
        x_ph,
        ph_mean,
        color="#0072B2",
        linewidth=1.7,
        marker="o",
        markersize=2.6,
        markeredgewidth=0.0,
        label="PH2 one-minute mean",
        zorder=4,
    )
    tracking_axis.set_ylabel("Tracking\n[pH]")
    tracking_axis.legend(
        loc="upper right",
        ncols=2,
        frameon=True,
        framealpha=0.95,
        fontsize=8.2,
    )
    tracking_axis.grid(True, which="major", alpha=0.22, linewidth=0.7)

    for axis, (column, label, color) in zip(axes[1:], MANIPULATED_INPUTS):
        values = events[column].to_numpy(dtype=float)
        step_values = np.append(values, values[-1])
        axis.step(
            step_x,
            step_values,
            where="post",
            color=color,
            linewidth=1.7,
        )
        axis.set_ylabel(f"{label}\n[mL/min]")
        axis.set_ylim(-0.2, flow_y_upper + 0.2)
        axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
        axis.text(
            0.995,
            0.84,
            f"Range: {np.min(values):.2f} to {np.max(values):.2f} mL/min",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=8.2,
            color="#4A4A4A",
        )

    axes[0].set_title(
        "July 31 BioSMB RL Test: pH Tracking and Manipulated Inputs",
        fontsize=15,
        weight="bold",
        pad=24,
    )
    axes[0].text(
        0.5,
        1.035,
        (
            "PH2 and reconstructed schedule with water = flows[3], "
            "acid = flows[0], and sodium acetate = flows[1]"
        ),
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#4A4A4A",
    )
    axes[-1].set_xlabel("Elapsed time from reconstructed run start [min]")
    axes[-1].set_xlim(0.0, max(experiment_end_min, 1.0))
    axes[-1].text(
        0.995,
        -0.31,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        transform=axes[-1].transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.12,
        right=0.985,
        top=0.90,
        bottom=0.10,
        hspace=0.12,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    validate_args(args)
    generated_at = datetime.now(timezone.utc)
    run_stamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path(
        f"results/july31_biosmb_schedule_{run_stamp}"
    )
    table_dir = output_dir / "tables"
    figure_dir = output_dir / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    data = load_lab_data(args.input)
    event_rows, event_offset, event_diagnostics = find_controller_events(
        data,
        args.flow_change_threshold,
    )
    events, target_values, cycle_indices = reconstruct_schedule(
        data=data,
        event_rows=event_rows,
        target_min=args.target_min,
        target_max=args.target_max,
        setpoint_count=args.setpoint_count,
        max_steps=args.max_steps,
        consecutive_required=args.consecutive_required,
        tolerance=args.tolerance,
    )
    run_data = assign_schedule_to_samples(data, event_rows, events)
    minute_data = aggregate_one_minute(
        run_data,
        events,
        args.bin_seconds,
    )
    schedule_segments = build_schedule_segments(
        events,
        run_data[TIME_COLUMN].iloc[-1],
    )
    overall_metrics, metrics_by_target = calculate_tracking_metrics(
        minute_data
    )
    flow_switch_diagnostic = calculate_flow_switch_diagnostic(events)
    raw_input_log_diagnostics = calculate_raw_input_log_diagnostics(
        run_data,
        args.flow_change_threshold,
    )

    event_path = table_dir / "reconstructed_controller_events.csv"
    minute_path = table_dir / "ph2_one_minute_average.csv"
    segment_path = table_dir / "reconstructed_schedule_segments.csv"
    overall_metric_path = table_dir / "tracking_metrics_1min.csv"
    target_metric_path = table_dir / "tracking_metrics_by_target_1min.csv"
    figure_path = (
        figure_dir / "july31_ph2_vs_reconstructed_setpoint_1min.png"
    )
    input_figure_path = (
        figure_dir / "july31_water_acid_base_flows.png"
    )
    combined_figure_path = (
        figure_dir / "july31_ph2_tracking_and_input_flows.png"
    )
    raw_input_figure_path = (
        figure_dir / "july31_raw_input_logs_no_averaging.png"
    )
    events.to_csv(event_path, index=False)
    minute_data.to_csv(minute_path, index=False)
    schedule_segments.to_csv(segment_path, index=False)
    overall_metrics.to_csv(overall_metric_path, index=False)
    metrics_by_target.to_csv(target_metric_path, index=False)
    plot_results(
        minute_data=minute_data,
        events=events,
        target_values=target_values,
        tolerance=args.tolerance,
        figure_path=figure_path,
        generated_at=generated_at,
    )
    experiment_end_min = float(run_data["elapsed_seconds"].iloc[-1]) / 60.0
    plot_manipulated_inputs(
        events=events,
        experiment_end_min=experiment_end_min,
        figure_path=input_figure_path,
        generated_at=generated_at,
    )
    plot_tracking_and_inputs(
        minute_data=minute_data,
        events=events,
        tolerance=args.tolerance,
        experiment_end_min=experiment_end_min,
        figure_path=combined_figure_path,
        generated_at=generated_at,
    )
    plot_raw_input_logs(
        run_data=run_data,
        diagnostics=raw_input_log_diagnostics,
        figure_path=raw_input_figure_path,
        generated_at=generated_at,
    )

    run_start_row = int(event_rows[0])
    manifest = {
        "analysis": "July 31 BioSMB reconstructed schedule versus PH_2",
        "generated_at_utc": generated_at.isoformat(),
        "script": str(Path(__file__).as_posix()),
        "input_file": str(args.input.as_posix()),
        "input_sha256": sha256_file(args.input),
        "input_row_count": int(len(data)),
        "selected_run_row_count": int(len(run_data)),
        "excluded_pre_run_row_count": run_start_row,
        "selected_run_start_utc": data.at[
            run_start_row,
            TIME_COLUMN,
        ].isoformat(),
        "selected_run_end_utc": run_data[TIME_COLUMN].iloc[-1].isoformat(),
        "action_event_detection": {
            "flow_columns": FLOW_COLUMNS,
            "flow_change_threshold": args.flow_change_threshold,
            "pre_run_event_count": int(event_offset),
            **event_diagnostics,
        },
        "scheduler_reconstruction": {
            "target_values": target_values.tolist(),
            "target_values_status": (
                "inferred because target_ph was not logged; override with "
                "--target-min and --target-max if the recorded settings are "
                "later recovered"
            ),
            "cycle_indices": cycle_indices.tolist(),
            "cycle_mode": "ping_pong",
            "maximum_steps_per_setpoint": args.max_steps,
            "consecutive_steps_required": args.consecutive_required,
            "tolerance": args.tolerance,
            "target_switch_count": int(events["target_changed"].sum()),
            "target_switch_reasons": events.loc[
                events["target_changed"],
                "change_reason",
            ].value_counts().to_dict(),
        },
        "averaging": {
            "measurement": PH2_COLUMN,
            "bin_width_seconds": args.bin_seconds,
            "bin_origin": "selected run start",
            "ph2_statistic": "arithmetic mean",
            "setpoint_handling": (
                "not averaged; plotted as reconstructed step signal"
            ),
            "metric_reference": (
                "reconstructed setpoint active at each bin center"
            ),
        },
        "flow_switch_diagnostic": flow_switch_diagnostic,
        "raw_input_log_diagnostics": raw_input_log_diagnostics,
        "manipulated_input_plot": {
            "figure": str(input_figure_path.as_posix()),
            "combined_tracking_figure": str(
                combined_figure_path.as_posix()
            ),
            "raw_no_averaging_figure": str(
                raw_input_figure_path.as_posix()
            ),
            "mapping_note": (
                "July 31 used pump 4 for Arium water, exported as the "
                "zero-based biosmb-flows[3] column"
            ),
            "time_representation": (
                "controller action values held piecewise constant between "
                "detected action events"
            ),
            "subplots": [
                {
                    "column": column,
                    "stream": label,
                    "units": "mL/min",
                }
                for column, label, _ in MANIPULATED_INPUTS
            ],
        },
        "limitations": [
            "The target values were not logged and are reconstructed.",
            (
                "The pre-run records are excluded at the largest action-event "
                "gap, which separates startup attempts from the continuous run."
            ),
            (
                "One-minute averaging smooths sub-minute transients; raw data "
                "remain unchanged in the source CSV."
            ),
        ],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Output directory: {output_dir}")
    print(f"Figure: {figure_path}")
    print(f"Input-flow figure: {input_figure_path}")
    print(f"Combined tracking/input figure: {combined_figure_path}")
    print(f"Raw no-averaging input figure: {raw_input_figure_path}")
    print(f"Minute-average table: {minute_path}")
    print(f"Selected run start: {manifest['selected_run_start_utc']}")
    print(f"Action events: {len(events)}")
    print(f"Target switches: {int(events['target_changed'].sum())}")
    print(
        "Inferred targets: "
        + ", ".join(f"{value:.1f}" for value in target_values)
    )
    print(
        "One-minute tracking MAE: "
        f"{overall_metrics.at[0, 'mae']:.4f} pH"
    )


if __name__ == "__main__":
    main()
