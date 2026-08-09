"""Reusable preparation and time-resolution helpers for BioSMB experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


TIME_COLUMN = "utc_time"
PH2_COLUMN = "biosmb-sensors.PH_2"
FLOW_COLUMNS = tuple(f"biosmb-flows[{index}]" for index in range(7))
SCHEDULE_COLUMN = "reconstructed_target_ph"
BLOCK_COLUMN = "setpoint_block_index"


class BioSMBDataError(ValueError):
    """Raised when a BioSMB CSV or analysis configuration is invalid."""


@dataclass(frozen=True)
class StreamSpec:
    """Describe one liquid stream and its physical CSV columns.

    Flow values are in mL/min and mass values are in grams. The validity flag
    states whether decreasing reservoir mass can be interpreted as actual
    bottle-out flow for the selected experiment.
    """

    key: str
    label: str
    flow_column: str
    mass_column: str
    color: str
    mass_signal_valid_for_actual_flow: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return asdict(self)


def default_stream_specs(
    *,
    include_water: bool = True,
    water_mass_valid: bool = False,
) -> tuple[StreamSpec, ...]:
    """Return the selected pump and scale mappings for the laboratory system.

    Water remains available for experiments with a valid water scale, while
    ``include_water=False`` gives the acid/base-only configuration used for
    the Aug. 7 experiment.
    """

    streams = [
        StreamSpec(
            key="acid",
            label="Acetic acid",
            flow_column="biosmb-flows[0]",
            mass_column="mfcs-mass.acid-mass-grams",
            color="#E15759",
        ),
        StreamSpec(
            key="sodium_acetate",
            label="Sodium acetate",
            flow_column="biosmb-flows[1]",
            mass_column="mfcs-mass.sodium-mass-grams",
            color="#59A14F",
        ),
    ]
    if include_water:
        streams.append(
            StreamSpec(
                key="water",
                label="Arium water",
                flow_column="biosmb-flows[3]",
                mass_column="mfcs-mass.water-mass-grams",
                color="#4E79A7",
                mass_signal_valid_for_actual_flow=water_mass_valid,
            )
        )
    return tuple(streams)


def _required_columns(stream_specs: Sequence[StreamSpec]) -> list[str]:
    return [
        TIME_COLUMN,
        PH2_COLUMN,
        *FLOW_COLUMNS,
        *[spec.mass_column for spec in stream_specs],
    ]


def load_biosmb_experiment(
    path: Path,
    *,
    stream_specs: Sequence[StreamSpec],
    utc_date: date | None = None,
) -> pd.DataFrame:
    """Load and validate one BioSMB experiment in chronological order.

    Parameters
    ----------
    path:
        CSV exported by the BioSMB logger.
    stream_specs:
        Physical flow-to-mass mappings used by the experiment.
    utc_date:
        Optional UTC date filter. Filtering is in memory and never modifies
        the source file.

    Returns
    -------
    pandas.DataFrame
        Time-major samples with parsed UTC timestamps, numeric physical
        signals, and ``elapsed_seconds`` from the first selected sample.
    """

    data = pd.read_csv(path, low_memory=False)
    missing = [
        column
        for column in _required_columns(stream_specs)
        if column not in data.columns
    ]
    if missing:
        raise BioSMBDataError(f"Missing required BioSMB columns: {missing}")

    data[TIME_COLUMN] = pd.to_datetime(
        data[TIME_COLUMN],
        utc=True,
        errors="raise",
        format="mixed",
    )
    if utc_date is not None:
        data = data.loc[data[TIME_COLUMN].dt.date.eq(utc_date)].copy()
    if data.empty:
        suffix = f" for UTC date {utc_date}" if utc_date else ""
        raise BioSMBDataError(f"No BioSMB rows were selected{suffix}.")

    numeric_columns = [
        PH2_COLUMN,
        *FLOW_COLUMNS,
        *[spec.mass_column for spec in stream_specs],
    ]
    data[numeric_columns] = data[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    invalid_columns = [
        column
        for column in numeric_columns
        if data[column].isna().any()
        or not np.isfinite(data[column].to_numpy(dtype=float)).all()
    ]
    if invalid_columns:
        raise BioSMBDataError(
            "Selected data contain missing or nonfinite values in: "
            f"{invalid_columns}"
        )

    data = data.sort_values(TIME_COLUMN).reset_index(drop=True)
    if data[TIME_COLUMN].duplicated().any():
        count = int(data[TIME_COLUMN].duplicated().sum())
        raise BioSMBDataError(
            f"Selected experiment contains {count} duplicate timestamps."
        )
    elapsed_seconds = (
        data[TIME_COLUMN] - data[TIME_COLUMN].iloc[0]
    ).dt.total_seconds()
    if len(data) > 1 and elapsed_seconds.diff().iloc[1:].le(0.0).any():
        raise BioSMBDataError("Experiment timestamps must increase strictly.")
    data["elapsed_seconds"] = elapsed_seconds
    return data


def detect_controller_actions(
    data: pd.DataFrame,
    *,
    stream_specs: Sequence[StreamSpec],
    flow_change_threshold: float = 1.0e-6,
) -> pd.DataFrame:
    """Detect controller actions from changes in controlled FLOW registers."""

    if flow_change_threshold < 0.0:
        raise BioSMBDataError("flow_change_threshold must be nonnegative.")
    flow_columns = [spec.flow_column for spec in stream_specs]
    flow_change = data[flow_columns].diff().abs().max(axis=1)
    action_rows = np.flatnonzero(
        flow_change.gt(flow_change_threshold).to_numpy(copy=True)
    )
    if len(action_rows) == 0:
        raise BioSMBDataError("No controlled-flow changes were detected.")

    events = data.iloc[action_rows].copy().reset_index().rename(
        columns={"index": "sample_index"}
    )
    events.insert(0, "action_number", np.arange(1, len(events) + 1))
    events["seconds_since_previous_action"] = (
        events[TIME_COLUMN].diff().dt.total_seconds()
    )
    return events[
        [
            "action_number",
            "sample_index",
            TIME_COLUMN,
            "elapsed_seconds",
            "seconds_since_previous_action",
            PH2_COLUMN,
            *flow_columns,
        ]
    ]


def ping_pong_targets(
    target_values: Sequence[float],
    block_count: int,
) -> np.ndarray:
    """Return a repeated forward-and-reverse scheduled-target sequence."""

    values = np.asarray(target_values, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise BioSMBDataError("At least two one-dimensional targets are required.")
    if not np.isfinite(values).all() or np.any(np.diff(values) <= 0.0):
        raise BioSMBDataError("Scheduled targets must be finite and increasing.")
    if block_count <= 0:
        raise BioSMBDataError("block_count must be positive.")
    cycle_indices = np.concatenate(
        [
            np.arange(len(values), dtype=int),
            np.arange(len(values) - 2, 0, -1, dtype=int),
        ]
    )
    repeated_indices = np.resize(cycle_indices, block_count)
    return values[repeated_indices]


def assign_reconstructed_schedule(
    data: pd.DataFrame,
    events: pd.DataFrame,
    *,
    target_values: Sequence[float],
    steps_per_setpoint: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign a supplied ping-pong schedule to samples and action events.

    The first detected FLOW change is controller action 1. Actions 1 through
    ``steps_per_setpoint`` belong to block zero. The CSV does not log the
    target, so the returned target is explicitly reconstructed.
    """

    if steps_per_setpoint <= 0:
        raise BioSMBDataError("steps_per_setpoint must be positive.")
    prepared_events = events.copy()
    block_indices = (
        prepared_events["action_number"].to_numpy(dtype=int) - 1
    ) // steps_per_setpoint
    prepared_events[BLOCK_COLUMN] = block_indices
    target_by_block = ping_pong_targets(
        target_values,
        int(block_indices.max()) + 1,
    )
    prepared_events[SCHEDULE_COLUMN] = target_by_block[block_indices]

    action_rows = prepared_events["sample_index"].to_numpy(dtype=int)
    last_action_indices = (
        np.searchsorted(
            action_rows,
            np.arange(len(data), dtype=int),
            side="right",
        )
        - 1
    )
    sample_blocks = np.maximum(last_action_indices, 0) // steps_per_setpoint
    prepared_data = data.copy()
    prepared_data[BLOCK_COLUMN] = sample_blocks
    prepared_data[SCHEDULE_COLUMN] = target_by_block[sample_blocks]
    return prepared_data, prepared_events


def aggregate_time_bins(
    data: pd.DataFrame,
    *,
    interval_seconds: float,
    stream_specs: Sequence[StreamSpec],
) -> pd.DataFrame:
    """Aggregate pH, commands, and masses over fixed elapsed-time bins."""

    if interval_seconds <= 0.0:
        raise BioSMBDataError("interval_seconds must be positive.")
    if SCHEDULE_COLUMN not in data or BLOCK_COLUMN not in data:
        raise BioSMBDataError("Schedule must be assigned before aggregation.")

    prepared = data.copy()
    prepared["interval_index"] = np.floor(
        prepared["elapsed_seconds"].to_numpy(dtype=float) / interval_seconds
    ).astype(int)
    grouped = prepared.groupby("interval_index", sort=True)
    summary = grouped.agg(
        utc_first=(TIME_COLUMN, "first"),
        utc_last=(TIME_COLUMN, "last"),
        elapsed_seconds_mean=("elapsed_seconds", "mean"),
        sample_count=(PH2_COLUMN, "size"),
        ph2_mean=(PH2_COLUMN, "mean"),
        ph2_std=(PH2_COLUMN, lambda values: values.std(ddof=0)),
        ph2_min=(PH2_COLUMN, "min"),
        ph2_max=(PH2_COLUMN, "max"),
    ).reset_index()

    centers = (
        summary["interval_index"].to_numpy(dtype=float) + 0.5
    ) * interval_seconds
    centers = np.minimum(centers, float(data["elapsed_seconds"].iloc[-1]))
    center_positions = (
        np.searchsorted(
            data["elapsed_seconds"].to_numpy(dtype=float),
            centers,
            side="right",
        )
        - 1
    )
    center_positions = np.clip(center_positions, 0, len(data) - 1)
    summary["elapsed_seconds_center"] = centers
    summary[BLOCK_COLUMN] = data[BLOCK_COLUMN].to_numpy(dtype=int)[
        center_positions
    ]
    summary[SCHEDULE_COLUMN] = data[SCHEDULE_COLUMN].to_numpy(dtype=float)[
        center_positions
    ]

    for spec in stream_specs:
        flow_group = grouped[spec.flow_column]
        summary[f"{spec.key}_flow_mean_ml_min"] = flow_group.mean().to_numpy()
        summary[f"{spec.key}_flow_min_ml_min"] = flow_group.min().to_numpy()
        summary[f"{spec.key}_flow_max_ml_min"] = flow_group.max().to_numpy()
        summary[f"{spec.key}_mass_mean_g"] = (
            grouped[spec.mass_column].mean().to_numpy()
        )
    return summary


def _time_weighted_command(
    interval_rows: pd.DataFrame,
    flow_column: str,
) -> float:
    times_ns = interval_rows[TIME_COLUMN].astype("int64").to_numpy()
    interval_seconds = np.diff(times_ns) / 1.0e9
    if len(interval_seconds) == 0 or float(np.sum(interval_seconds)) <= 0.0:
        return float("nan")
    commands = interval_rows[flow_column].to_numpy(dtype=float)[:-1]
    return float(np.sum(commands * interval_seconds) / np.sum(interval_seconds))


def build_mass_flow_intervals(
    data: pd.DataFrame,
    *,
    interval_seconds: float,
    stream_specs: Sequence[StreamSpec],
    densities_g_ml: dict[str, float],
    flow_change_threshold: float = 1.0e-6,
) -> pd.DataFrame:
    """Calculate gravimetric bottle-out flow over selected elapsed-time bins.

    The first real CSV row in each bin is selected. Consecutive selected rows
    define the exact interval. No mass samples are averaged. The FLOW command
    is time-weighted over all raw log rows inside the interval.
    """

    if interval_seconds <= 0.0:
        raise BioSMBDataError("interval_seconds must be positive.")
    missing_density = [
        spec.key
        for spec in stream_specs
        if spec.key not in densities_g_ml or densities_g_ml[spec.key] <= 0.0
    ]
    if missing_density:
        raise BioSMBDataError(
            f"Missing or nonpositive stream densities: {missing_density}"
        )

    bin_indices = np.floor(
        data["elapsed_seconds"].to_numpy(dtype=float) / interval_seconds
    ).astype(int)
    selected = (
        data.assign(_interval_bin=bin_indices)
        .groupby("_interval_bin", sort=True)
        .head(1)
    )
    selected_positions = selected.index.to_numpy(dtype=int)
    if len(selected_positions) < 2:
        raise BioSMBDataError("Fewer than two interval rows were selected.")

    records: list[dict[str, object]] = []
    for interval_index in range(len(selected_positions) - 1):
        start_position = int(selected_positions[interval_index])
        end_position = int(selected_positions[interval_index + 1])
        start = data.iloc[start_position]
        end = data.iloc[end_position]
        interval_rows = data.iloc[start_position : end_position + 1]
        duration_seconds = (
            pd.Timestamp(end[TIME_COLUMN]) - pd.Timestamp(start[TIME_COLUMN])
        ).total_seconds()
        if duration_seconds <= 0.0:
            raise BioSMBDataError("Mass-flow intervals must be positive.")

        for spec in stream_specs:
            density = float(densities_g_ml[spec.key])
            mass_start = float(start[spec.mass_column])
            mass_end = float(end[spec.mass_column])
            mass_loss = mass_start - mass_end
            mass_flow = mass_loss / density * 60.0 / duration_seconds
            command_values = interval_rows[spec.flow_column].to_numpy(
                dtype=float
            )
            command_changed = (
                float(np.max(command_values) - np.min(command_values))
                > flow_change_threshold
            )
            valid = spec.mass_signal_valid_for_actual_flow
            records.append(
                {
                    "interval_seconds_requested": float(interval_seconds),
                    "interval_index": interval_index,
                    "stream": spec.key,
                    "stream_label": spec.label,
                    "flow_column": spec.flow_column,
                    "mass_column": spec.mass_column,
                    "density_g_ml": density,
                    "utc_start": pd.Timestamp(start[TIME_COLUMN]).isoformat(),
                    "utc_end": pd.Timestamp(end[TIME_COLUMN]).isoformat(),
                    "elapsed_seconds_end": float(end["elapsed_seconds"]),
                    "duration_seconds": duration_seconds,
                    "mass_start_g": mass_start,
                    "mass_end_g": mass_end,
                    "mass_loss_g": mass_loss,
                    "mass_derived_flow_ml_min": mass_flow,
                    "mass_signal_valid_for_actual_flow": valid,
                    "actual_flow_ml_min": mass_flow if valid else np.nan,
                    "commanded_flow_time_weighted_ml_min": (
                        _time_weighted_command(interval_rows, spec.flow_column)
                    ),
                    "commanded_flow_start_ml_min": float(
                        start[spec.flow_column]
                    ),
                    "commanded_flow_end_ml_min": float(end[spec.flow_column]),
                    "command_changed_within_interval": command_changed,
                }
            )
    return pd.DataFrame(records)


def calculate_tracking_metrics(
    measured_ph: np.ndarray,
    target_ph: np.ndarray,
    *,
    resolution: str,
) -> pd.DataFrame:
    """Return overall pH tracking metrics for a defined time resolution."""

    measured = np.asarray(measured_ph, dtype=float)
    target = np.asarray(target_ph, dtype=float)
    if measured.shape != target.shape or measured.ndim != 1:
        raise BioSMBDataError("Measured and target pH must be equal 1-D arrays.")
    if len(measured) == 0 or not np.isfinite(measured).all():
        raise BioSMBDataError("Tracking arrays must be nonempty and finite.")
    error = measured - target
    return pd.DataFrame(
        [
            {
                "resolution": resolution,
                "sample_count": len(error),
                "mean_error_ph": float(np.mean(error)),
                "mae_ph": float(np.mean(np.abs(error))),
                "rmse_ph": float(np.sqrt(np.mean(np.square(error)))),
                "maximum_absolute_error_ph": float(np.max(np.abs(error))),
            }
        ]
    )


def calculate_mass_flow_metrics(
    intervals: pd.DataFrame,
    *,
    resolution: str,
) -> pd.DataFrame:
    """Return actual-versus-command metrics for valid mass signals."""

    records = []
    for stream, stream_data in intervals.groupby("stream", sort=True):
        if not bool(
            stream_data["mass_signal_valid_for_actual_flow"].iloc[0]
        ):
            continue
        for scope, evaluated in {
            "all_intervals": stream_data,
            "constant_command_only": stream_data.loc[
                ~stream_data["command_changed_within_interval"]
            ],
        }.items():
            actual = evaluated["actual_flow_ml_min"].to_numpy(dtype=float)
            command = evaluated[
                "commanded_flow_time_weighted_ml_min"
            ].to_numpy(dtype=float)
            error = actual - command
            correlation = (
                float(np.corrcoef(actual, command)[0, 1])
                if len(actual) > 1
                and np.std(actual) > 0.0
                and np.std(command) > 0.0
                else float("nan")
            )
            records.append(
                {
                    "resolution": resolution,
                    "stream": stream,
                    "scope": scope,
                    "interval_count": len(evaluated),
                    "mean_actual_flow_ml_min": float(np.mean(actual)),
                    "mean_commanded_flow_ml_min": float(np.mean(command)),
                    "mean_error_ml_min": float(np.mean(error)),
                    "mae_ml_min": float(np.mean(np.abs(error))),
                    "rmse_ml_min": float(
                        np.sqrt(np.mean(np.square(error)))
                    ),
                    "correlation": correlation,
                }
            )
    return pd.DataFrame(records)
