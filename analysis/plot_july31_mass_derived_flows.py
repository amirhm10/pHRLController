"""Compare July 31 mass-derived and commanded flows without sample averaging."""

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

from plot_july31_biosmb_schedule import (
    TIME_COLUMN,
    find_controller_events,
    load_lab_data,
)


STREAM_DEFINITIONS = [
    {
        "key": "acid",
        "label": "Acetic acid",
        "mass_column": "mfcs-mass.acid-mass-grams",
        "command_column": "biosmb-flows[0]",
        "color": "#E15759",
    },
    {
        "key": "sodium_acetate",
        "label": "Sodium acetate",
        "mass_column": "mfcs-mass.sodium-mass-grams",
        "command_column": "biosmb-flows[1]",
        "color": "#59A14F",
    },
    {
        "key": "water",
        "label": "Arium water",
        "mass_column": "mfcs-mass.water-mass-grams",
        "command_column": "biosmb-flows[3]",
        "color": "#4E79A7",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Back-calculate July 31 bottle-out flows from mass loss and "
            "compare them with commanded flows at adjacent-log and "
            "one-minute intervals without averaging samples."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data/July31 BioSMB RL Test.csv"),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--acid-density", type=float, default=1.0)
    parser.add_argument("--sodium-density", type=float, default=1.0)
    parser.add_argument("--water-density", type=float, default=1.0)
    parser.add_argument("--flow-change-threshold", type=float, default=1.0e-6)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    densities = [
        args.acid_density,
        args.sodium_density,
        args.water_density,
    ]
    if any(density <= 0.0 for density in densities):
        raise ValueError("All stream densities must be positive.")
    if args.flow_change_threshold < 0.0:
        raise ValueError("--flow-change-threshold must be nonnegative.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_density_values(
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    densities = {
        "acid": args.acid_density,
        "sodium_acetate": args.sodium_density,
        "water": args.water_density,
    }
    return [
        {**definition, "density_g_ml": float(densities[definition["key"]])}
        for definition in STREAM_DEFINITIONS
    ]


def select_continuous_run(
    data: pd.DataFrame,
    flow_change_threshold: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    event_rows, _, event_diagnostics = find_controller_events(
        data,
        flow_change_threshold,
    )
    run_data = data.iloc[int(event_rows[0]) :].copy().reset_index()
    run_data = run_data.rename(columns={"index": "source_row_index"})
    run_start = run_data[TIME_COLUMN].iloc[0]
    run_data["elapsed_seconds"] = (
        run_data[TIME_COLUMN] - run_start
    ).dt.total_seconds()
    run_data["elapsed_min"] = run_data["elapsed_seconds"] / 60.0
    run_data["run_row_position"] = np.arange(len(run_data), dtype=int)
    return run_data, event_diagnostics


def validate_mass_columns(
    run_data: pd.DataFrame,
    stream_definitions: list[dict[str, object]],
) -> None:
    required = [
        str(definition["mass_column"])
        for definition in stream_definitions
    ]
    missing = [column for column in required if column not in run_data.columns]
    if missing:
        raise ValueError(f"Missing required mass columns: {missing}")
    for column in required:
        run_data[column] = pd.to_numeric(run_data[column], errors="coerce")
        if run_data[column].isna().any():
            raise ValueError(f"Mass column contains missing values: {column}")


def build_adjacent_interval_table(
    run_data: pd.DataFrame,
    stream_definitions: list[dict[str, object]],
    flow_change_threshold: float,
) -> pd.DataFrame:
    start_time = run_data[TIME_COLUMN].iloc[:-1].reset_index(drop=True)
    end_time = run_data[TIME_COLUMN].iloc[1:].reset_index(drop=True)
    interval_seconds = (
        end_time - start_time
    ).dt.total_seconds().to_numpy(dtype=float)
    if np.any(interval_seconds <= 0.0):
        raise ValueError("Adjacent log intervals must be positive.")

    tables = []
    for definition in stream_definitions:
        mass_column = str(definition["mass_column"])
        command_column = str(definition["command_column"])
        density = float(definition["density_g_ml"])
        mass = run_data[mass_column].to_numpy(dtype=float)
        command = run_data[command_column].to_numpy(dtype=float)
        mass_loss = mass[:-1] - mass[1:]
        actual_flow = mass_loss / density * 60.0 / interval_seconds
        command_change = np.abs(command[1:] - command[:-1])
        table = pd.DataFrame(
            {
                "interval_type": "adjacent_log_rows",
                "stream": str(definition["key"]),
                "stream_label": str(definition["label"]),
                "mass_column": mass_column,
                "command_column": command_column,
                "density_g_ml": density,
                "source_row_start": run_data[
                    "source_row_index"
                ].iloc[:-1].to_numpy(dtype=int),
                "source_row_end": run_data[
                    "source_row_index"
                ].iloc[1:].to_numpy(dtype=int),
                "utc_start": start_time.map(
                    lambda value: value.isoformat()
                ),
                "utc_end": end_time.map(lambda value: value.isoformat()),
                "elapsed_min_end": run_data["elapsed_min"].iloc[
                    1:
                ].to_numpy(dtype=float),
                "interval_seconds": interval_seconds,
                "mass_start_g": mass[:-1],
                "mass_end_g": mass[1:],
                "mass_loss_g": mass_loss,
                "actual_flow_ml_min": actual_flow,
                "commanded_flow_at_start_ml_min": command[:-1],
                "commanded_flow_at_end_ml_min": command[1:],
                "command_changed_within_interval": (
                    command_change > flow_change_threshold
                ),
            }
        )
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def select_one_minute_rows(run_data: pd.DataFrame) -> pd.DataFrame:
    minute_index = np.floor(
        run_data["elapsed_seconds"].to_numpy(dtype=float) / 60.0
    ).astype(int)
    prepared = run_data.assign(minute_index=minute_index)
    selected = (
        prepared.groupby("minute_index", sort=True)
        .head(1)
        .reset_index(drop=True)
    )
    if len(selected) < 2:
        raise ValueError("Fewer than two one-minute CSV rows were selected.")
    return selected


def build_one_minute_interval_table(
    run_data: pd.DataFrame,
    selected_rows: pd.DataFrame,
    stream_definitions: list[dict[str, object]],
    flow_change_threshold: float,
) -> pd.DataFrame:
    records = []
    selected_positions = selected_rows[
        "run_row_position"
    ].to_numpy(dtype=int)
    for interval_index in range(1, len(selected_rows)):
        start = selected_rows.iloc[interval_index - 1]
        end = selected_rows.iloc[interval_index]
        start_position = int(selected_positions[interval_index - 1])
        end_position = int(selected_positions[interval_index])
        interval_seconds = (
            end[TIME_COLUMN] - start[TIME_COLUMN]
        ).total_seconds()
        if interval_seconds <= 0.0:
            raise ValueError("One-minute intervals must be positive.")

        interval_rows = run_data.iloc[start_position : end_position + 1]
        for definition in stream_definitions:
            mass_column = str(definition["mass_column"])
            command_column = str(definition["command_column"])
            density = float(definition["density_g_ml"])
            mass_start = float(start[mass_column])
            mass_end = float(end[mass_column])
            mass_loss = mass_start - mass_end
            interval_commands = interval_rows[command_column].to_numpy(
                dtype=float
            )
            command_changed = (
                float(np.max(interval_commands) - np.min(interval_commands))
                > flow_change_threshold
            )
            records.append(
                {
                    "interval_type": "first_csv_row_each_elapsed_minute",
                    "stream": str(definition["key"]),
                    "stream_label": str(definition["label"]),
                    "mass_column": mass_column,
                    "command_column": command_column,
                    "density_g_ml": density,
                    "minute_interval_index": interval_index - 1,
                    "source_row_start": int(start["source_row_index"]),
                    "source_row_end": int(end["source_row_index"]),
                    "utc_start": start[TIME_COLUMN].isoformat(),
                    "utc_end": end[TIME_COLUMN].isoformat(),
                    "elapsed_min_end": float(end["elapsed_min"]),
                    "interval_seconds": interval_seconds,
                    "mass_start_g": mass_start,
                    "mass_end_g": mass_end,
                    "mass_loss_g": mass_loss,
                    "actual_flow_ml_min": (
                        mass_loss / density * 60.0 / interval_seconds
                    ),
                    "commanded_flow_at_start_ml_min": float(
                        start[command_column]
                    ),
                    "commanded_flow_at_end_ml_min": float(
                        end[command_column]
                    ),
                    "command_changed_within_interval": command_changed,
                }
            )
    return pd.DataFrame(records)


def safe_correlation(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.std(x) == 0.0 or np.std(y) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def calculate_metrics(
    interval_tables: list[pd.DataFrame],
) -> pd.DataFrame:
    records = []
    for table in interval_tables:
        interval_type = str(table["interval_type"].iloc[0])
        for stream, stream_data in table.groupby("stream", sort=True):
            scopes = {
                "all_intervals": stream_data,
                "constant_command_only": stream_data[
                    ~stream_data["command_changed_within_interval"]
                ],
            }
            for scope, evaluated in scopes.items():
                actual = evaluated["actual_flow_ml_min"].to_numpy(dtype=float)
                command = evaluated[
                    "commanded_flow_at_start_ml_min"
                ].to_numpy(dtype=float)
                error = actual - command
                records.append(
                    {
                        "interval_type": interval_type,
                        "stream": stream,
                        "scope": scope,
                        "interval_count": int(len(evaluated)),
                        "command_change_interval_count": int(
                            evaluated[
                                "command_changed_within_interval"
                            ].sum()
                        ),
                        "mean_actual_flow_ml_min": float(np.mean(actual)),
                        "median_actual_flow_ml_min": float(np.median(actual)),
                        "minimum_actual_flow_ml_min": float(np.min(actual)),
                        "maximum_actual_flow_ml_min": float(np.max(actual)),
                        "mean_commanded_flow_ml_min": float(
                            np.mean(command)
                        ),
                        "mean_error_ml_min": float(np.mean(error)),
                        "mae_ml_min": float(np.mean(np.abs(error))),
                        "rmse_ml_min": float(
                            np.sqrt(np.mean(np.square(error)))
                        ),
                        "correlation": safe_correlation(actual, command),
                    }
                )
    return pd.DataFrame(records)


def padded_limits(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    span = upper - lower
    padding = max(0.5, 0.06 * span)
    return lower - padding, upper + padding


def plot_stream_comparison(
    definition: dict[str, object],
    adjacent_table: pd.DataFrame,
    minute_table: pd.DataFrame,
    figure_path: Path,
    generated_at: datetime,
) -> None:
    stream = str(definition["key"])
    label = str(definition["label"])
    color = str(definition["color"])
    density = float(definition["density_g_ml"])
    adjacent = adjacent_table[adjacent_table["stream"] == stream]
    minute = minute_table[minute_table["stream"] == stream]

    figure, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(13.2, 8.4),
        sharex=True,
        gridspec_kw={"height_ratios": [1.0, 1.0]},
    )
    raw_axis, minute_axis = axes

    raw_x = adjacent["elapsed_min_end"].to_numpy(dtype=float)
    raw_actual = adjacent["actual_flow_ml_min"].to_numpy(dtype=float)
    raw_command = adjacent[
        "commanded_flow_at_start_ml_min"
    ].to_numpy(dtype=float)
    raw_axis.scatter(
        raw_x,
        raw_actual,
        s=5.0,
        alpha=0.32,
        color=color,
        edgecolors="none",
        label="Mass-derived flow over adjacent CSV rows",
        rasterized=True,
    )
    raw_axis.plot(
        raw_x,
        raw_command,
        color="#1A1A1A",
        linewidth=1.35,
        drawstyle="steps-post",
        label="Command at interval start",
    )
    raw_axis.axhline(0.0, color="#777777", linewidth=0.7, alpha=0.5)
    raw_axis.set_ylabel("Raw-log interval\nflow [mL/min]")
    raw_axis.set_ylim(
        *padded_limits(np.concatenate([raw_actual, raw_command]))
    )
    raw_axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
    raw_axis.legend(
        loc="upper right",
        frameon=True,
        framealpha=0.95,
        fontsize=8.5,
    )
    raw_axis.text(
        0.005,
        0.96,
        (
            f"Actual range: {np.min(raw_actual):.2f} to "
            f"{np.max(raw_actual):.2f} mL/min"
        ),
        transform=raw_axis.transAxes,
        ha="left",
        va="top",
        fontsize=8.3,
        color="#4A4A4A",
    )

    minute_x = minute["elapsed_min_end"].to_numpy(dtype=float)
    minute_actual = minute["actual_flow_ml_min"].to_numpy(dtype=float)
    minute_command = minute[
        "commanded_flow_at_start_ml_min"
    ].to_numpy(dtype=float)
    changed = minute["command_changed_within_interval"].to_numpy(dtype=bool)
    minute_axis.plot(
        minute_x,
        minute_actual,
        color=color,
        linewidth=1.25,
        marker="o",
        markersize=3.3,
        markeredgewidth=0.0,
        label="Mass-derived flow over selected one-minute interval",
    )
    minute_axis.plot(
        minute_x,
        minute_command,
        color="#1A1A1A",
        linewidth=1.35,
        drawstyle="steps-post",
        label="Command at interval start",
    )
    if np.any(changed):
        minute_axis.scatter(
            minute_x[changed],
            minute_actual[changed],
            s=34,
            marker="x",
            linewidths=1.0,
            color="#F28E2B",
            label="Command changed within interval",
            zorder=5,
        )
    minute_axis.axhline(0.0, color="#777777", linewidth=0.7, alpha=0.5)
    minute_axis.set_ylabel("One-minute interval\nflow [mL/min]")
    minute_axis.set_xlabel(
        "Elapsed time from reconstructed run start [min]"
    )
    minute_axis.set_ylim(
        *padded_limits(np.concatenate([minute_actual, minute_command]))
    )
    minute_axis.set_xlim(0.0, max(float(minute_x[-1]), 1.0))
    minute_axis.grid(True, which="major", alpha=0.22, linewidth=0.7)
    minute_axis.legend(
        loc="upper right",
        frameon=True,
        framealpha=0.95,
        fontsize=8.5,
    )

    raw_interval = adjacent["interval_seconds"].to_numpy(dtype=float)
    minute_interval = minute["interval_seconds"].to_numpy(dtype=float)
    figure.suptitle(
        f"{label}: Mass-Derived Actual vs Commanded Flow",
        fontsize=15,
        weight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.945,
        (
            f"No sample averaging | density = {density:.4f} g/mL | "
            f"raw median interval {np.median(raw_interval):.3f} s | "
            f"selected-minute median interval "
            f"{np.median(minute_interval):.3f} s"
        ),
        ha="center",
        va="top",
        fontsize=9.2,
        color="#4A4A4A",
    )
    figure.text(
        0.005,
        0.015,
        (
            "One-minute points use the first real CSV row in each elapsed-"
            "minute bin; commands are not averaged."
        ),
        ha="left",
        va="bottom",
        fontsize=8.3,
        color="#4A4A4A",
    )
    figure.text(
        0.995,
        0.015,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        ha="right",
        va="bottom",
        fontsize=8.3,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.10,
        right=0.985,
        top=0.90,
        bottom=0.09,
        hspace=0.15,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    validate_args(args)
    generated_at = datetime.now(timezone.utc)
    run_stamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path(
        f"results/july31_mass_derived_flows_{run_stamp}"
    )
    figure_dir = output_dir / "figures"
    table_dir = output_dir / "tables"
    figure_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    stream_definitions = add_density_values(args)
    data = load_lab_data(args.input)
    run_data, event_diagnostics = select_continuous_run(
        data,
        args.flow_change_threshold,
    )
    validate_mass_columns(run_data, stream_definitions)
    adjacent_table = build_adjacent_interval_table(
        run_data,
        stream_definitions,
        args.flow_change_threshold,
    )
    selected_minute_rows = select_one_minute_rows(run_data)
    minute_table = build_one_minute_interval_table(
        run_data,
        selected_minute_rows,
        stream_definitions,
        args.flow_change_threshold,
    )
    metrics = calculate_metrics([adjacent_table, minute_table])

    adjacent_path = table_dir / "mass_derived_flow_log_intervals.csv"
    minute_path = table_dir / "mass_derived_flow_one_minute_intervals.csv"
    metrics_path = table_dir / "mass_derived_flow_metrics.csv"
    adjacent_table.to_csv(adjacent_path, index=False)
    minute_table.to_csv(minute_path, index=False)
    metrics.to_csv(metrics_path, index=False)

    figure_paths = {}
    for definition in stream_definitions:
        stream = str(definition["key"])
        figure_path = (
            figure_dir
            / f"july31_{stream}_actual_vs_commanded_flow.png"
        )
        plot_stream_comparison(
            definition=definition,
            adjacent_table=adjacent_table,
            minute_table=minute_table,
            figure_path=figure_path,
            generated_at=generated_at,
        )
        figure_paths[stream] = str(figure_path.as_posix())

    interval_seconds = run_data[TIME_COLUMN].diff().dt.total_seconds().dropna()
    manifest = {
        "analysis": "July 31 mass-derived actual versus commanded flows",
        "generated_at_utc": generated_at.isoformat(),
        "script": str(Path(__file__).as_posix()),
        "input_file": str(args.input.as_posix()),
        "input_sha256": sha256_file(args.input),
        "selected_run_start_utc": run_data[TIME_COLUMN].iloc[0].isoformat(),
        "selected_run_end_utc": run_data[TIME_COLUMN].iloc[-1].isoformat(),
        "selected_run_sample_count": int(len(run_data)),
        "raw_log_interval_seconds": {
            "minimum": float(interval_seconds.min()),
            "median": float(interval_seconds.median()),
            "maximum": float(interval_seconds.max()),
        },
        "method": {
            "actual_flow_equation": (
                "(mass_start_g - mass_end_g) / density_g_ml * "
                "60 / interval_seconds"
            ),
            "adjacent_log_intervals": (
                "every consecutive pair of selected-run CSV rows"
            ),
            "one_minute_intervals": (
                "first real CSV row from each elapsed-minute bin, then "
                "consecutive selected rows"
            ),
            "sample_averaging": "none",
            "command_reference": "commanded flow at interval start",
            "command_change_handling": (
                "intervals containing a change are retained and flagged"
            ),
        },
        "stream_definitions": stream_definitions,
        "action_event_detection": event_diagnostics,
        "figures": figure_paths,
        "tables": {
            "adjacent_log_intervals": str(adjacent_path.as_posix()),
            "one_minute_intervals": str(minute_path.as_posix()),
            "metrics": str(metrics_path.as_posix()),
        },
        "limitations": [
            (
                "Density defaults are provisional 1.0 g/mL values and should "
                "be replaced with calibrated solution densities."
            ),
            (
                "Adjacent-row mass differences amplify scale quantization "
                "and timestamp jitter."
            ),
            (
                "The water mass channel increases during this run, so its "
                "mass-derived flow is not physically credible."
            ),
            (
                "Bottle mass loss measures liquid leaving the reservoir, not "
                "necessarily liquid reaching the mixer."
            ),
        ],
    }
    manifest_path = output_dir / "mass_derived_flow_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Output directory: {output_dir}")
    print(f"Adjacent-log table: {adjacent_path}")
    print(f"One-minute table: {minute_path}")
    print(f"Metrics table: {metrics_path}")
    for stream, figure_path in figure_paths.items():
        print(f"{stream} figure: {figure_path}")
    print(
        "One-minute selected rows: "
        f"{len(selected_minute_rows)} ({len(selected_minute_rows) - 1} intervals)"
    )


if __name__ == "__main__":
    main()
