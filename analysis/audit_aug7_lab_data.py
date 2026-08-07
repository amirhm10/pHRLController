"""Audit the Aug. 7 BioSMB export and save an experiment-only derivative."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
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


TIME_COLUMN = "utc_time"
PH2_COLUMN = "biosmb-sensors.PH_2"
FLOW_COLUMNS = [f"biosmb-flows[{index}]" for index in range(7)]
STREAM_DEFINITIONS = [
    {
        "stream": "acid",
        "label": "Acetic acid",
        "flow_column": "biosmb-flows[0]",
        "mass_column": "mfcs-mass.acid-mass-grams",
        "color": "#E15759",
        "mass_signal_valid_for_actual_flow": True,
    },
    {
        "stream": "sodium_acetate",
        "label": "Sodium acetate",
        "flow_column": "biosmb-flows[1]",
        "mass_column": "mfcs-mass.sodium-mass-grams",
        "color": "#59A14F",
        "mass_signal_valid_for_actual_flow": True,
    },
    {
        "stream": "water",
        "label": "Arium water",
        "flow_column": "biosmb-flows[3]",
        "mass_column": "mfcs-mass.water-mass-grams",
        "color": "#4E79A7",
        "mass_signal_valid_for_actual_flow": False,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Filter a cumulative BioSMB CSV to one UTC experiment date and "
            "audit timing, controller actions, setpoint-length evidence, "
            "pH, flow commands, and reservoir mass balances."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data/Aug7 BioSMB RL Test.csv"),
    )
    parser.add_argument(
        "--utc-date",
        type=date.fromisoformat,
        default=date(2026, 8, 7),
    )
    parser.add_argument("--steps-per-setpoint", type=int, default=30)
    parser.add_argument("--flow-change-threshold", type=float, default=1.0e-6)
    parser.add_argument("--density", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.steps_per_setpoint <= 0:
        raise ValueError("--steps-per-setpoint must be positive.")
    if args.flow_change_threshold < 0.0:
        raise ValueError("--flow-change-threshold must be nonnegative.")
    if args.density <= 0.0:
        raise ValueError("--density must be positive.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_filter_data(
    path: Path,
    utc_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    raw = pd.read_csv(path, low_memory=False)
    original_columns = raw.columns.tolist()
    required = [
        TIME_COLUMN,
        PH2_COLUMN,
        *FLOW_COLUMNS,
        *[definition["mass_column"] for definition in STREAM_DEFINITIONS],
    ]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    raw[TIME_COLUMN] = pd.to_datetime(raw[TIME_COLUMN], utc=True, errors="raise")
    raw_time_monotonic = bool(raw[TIME_COLUMN].is_monotonic_increasing)
    date_counts = (
        raw[TIME_COLUMN]
        .dt.strftime("%Y-%m-%d")
        .value_counts()
        .sort_index()
        .rename_axis("utc_date")
        .reset_index(name="row_count")
    )
    selected_mask = raw[TIME_COLUMN].dt.date.eq(utc_date)
    selected = raw.loc[selected_mask, original_columns].copy()
    if selected.empty:
        raise ValueError(f"No records found for UTC date {utc_date.isoformat()}.")
    selected = selected.sort_values(TIME_COLUMN).reset_index(drop=True)

    numeric_columns = [
        PH2_COLUMN,
        *FLOW_COLUMNS,
        *[definition["mass_column"] for definition in STREAM_DEFINITIONS],
    ]
    selected[numeric_columns] = selected[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    required_numeric = [PH2_COLUMN, *FLOW_COLUMNS]
    if selected[required_numeric].isna().any().any():
        bad_columns = selected[required_numeric].columns[
            selected[required_numeric].isna().any()
        ].tolist()
        raise ValueError(f"Selected data contain missing numeric values: {bad_columns}")
    return raw, selected, date_counts, raw_time_monotonic


def build_action_events(
    data: pd.DataFrame,
    flow_change_threshold: float,
    steps_per_setpoint: int,
) -> pd.DataFrame:
    flow_change = data[FLOW_COLUMNS].diff().abs().max(axis=1)
    action_mask = flow_change.gt(flow_change_threshold).to_numpy(copy=True)
    action_rows = np.flatnonzero(action_mask)
    if len(action_rows) == 0:
        raise ValueError("No controller flow-change events were detected.")

    events = data.iloc[action_rows].copy().reset_index().rename(
        columns={"index": "selected_row_index"}
    )
    events.insert(0, "action_number", np.arange(1, len(events) + 1))
    events.insert(
        1,
        "setpoint_block_index",
        (events["action_number"] - 1) // steps_per_setpoint,
    )
    events["seconds_since_previous_action"] = (
        events[TIME_COLUMN].diff().dt.total_seconds()
    )
    columns = [
        "action_number",
        "setpoint_block_index",
        "selected_row_index",
        TIME_COLUMN,
        "seconds_since_previous_action",
        PH2_COLUMN,
        *FLOW_COLUMNS,
    ]
    return events[columns]


def time_weighted_command_mean(
    data: pd.DataFrame,
    start_position: int,
    end_position: int,
    end_time: pd.Timestamp,
    flow_column: str,
) -> float:
    segment = data.iloc[start_position:end_position]
    times = segment[TIME_COLUMN].tolist() + [end_time]
    intervals = np.diff(pd.DatetimeIndex(times).view("int64")) / 1.0e9
    duration = float(np.sum(intervals))
    if duration <= 0.0:
        return float("nan")
    commands = segment[flow_column].to_numpy(dtype=float)
    return float(np.sum(commands * intervals) / duration)


def build_setpoint_blocks(
    data: pd.DataFrame,
    events: pd.DataFrame,
    steps_per_setpoint: int,
    density: float,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    grouped_events = list(events.groupby("setpoint_block_index", sort=True))
    for position, (block_index, block_events) in enumerate(grouped_events):
        start_position = int(block_events["selected_row_index"].iloc[0])
        if position + 1 < len(grouped_events):
            next_events = grouped_events[position + 1][1]
            end_position = int(next_events["selected_row_index"].iloc[0])
            end_time = pd.Timestamp(next_events[TIME_COLUMN].iloc[0])
        else:
            end_position = len(data)
            end_time = pd.Timestamp(data[TIME_COLUMN].iloc[-1])

        segment = data.iloc[start_position:end_position]
        start_time = pd.Timestamp(segment[TIME_COLUMN].iloc[0])
        duration_min = (end_time - start_time).total_seconds() / 60.0
        tail_start = end_time - pd.Timedelta(minutes=5.0)
        tail = segment[segment[TIME_COLUMN].ge(tail_start)]
        record: dict[str, object] = {
            "setpoint_block_index": int(block_index),
            "action_count": int(len(block_events)),
            "complete_30_step_block": bool(
                len(block_events) == steps_per_setpoint
            ),
            "start_utc": start_time.isoformat(),
            "end_utc": end_time.isoformat(),
            "duration_min": duration_min,
            "sample_count": int(len(segment)),
            "ph2_start": float(segment[PH2_COLUMN].iloc[0]),
            "ph2_mean": float(segment[PH2_COLUMN].mean()),
            "ph2_min": float(segment[PH2_COLUMN].min()),
            "ph2_max": float(segment[PH2_COLUMN].max()),
            "ph2_tail_5min_mean": float(tail[PH2_COLUMN].mean()),
            "ph2_tail_5min_std": float(tail[PH2_COLUMN].std(ddof=0)),
        }
        endpoint = data.iloc[
            end_position if end_position < len(data) else len(data) - 1
        ]
        for definition in STREAM_DEFINITIONS:
            stream = str(definition["stream"])
            flow_column = str(definition["flow_column"])
            mass_column = str(definition["mass_column"])
            record[f"{stream}_command_mean_ml_min"] = time_weighted_command_mean(
                data,
                start_position,
                end_position,
                end_time,
                flow_column,
            )
            mass_loss = float(
                segment[mass_column].iloc[0] - endpoint[mass_column]
            )
            record[f"{stream}_mass_change_out_g"] = mass_loss
            record[f"{stream}_mass_derived_outflow_ml_min"] = (
                mass_loss / density / duration_min
                if duration_min > 0.0
                else float("nan")
            )
        records.append(record)
    return pd.DataFrame(records)


def integrate_stepwise_command(
    data: pd.DataFrame,
    flow_column: str,
) -> float:
    interval_min = (
        data[TIME_COLUMN].shift(-1) - data[TIME_COLUMN]
    ).dt.total_seconds() / 60.0
    return float(
        np.sum(
            data[flow_column].iloc[:-1].to_numpy(dtype=float)
            * interval_min.iloc[:-1].to_numpy(dtype=float)
        )
    )


def build_mass_balance(data: pd.DataFrame, density: float) -> pd.DataFrame:
    records = []
    duration_min = (
        data[TIME_COLUMN].iloc[-1] - data[TIME_COLUMN].iloc[0]
    ).total_seconds() / 60.0
    for definition in STREAM_DEFINITIONS:
        flow_column = str(definition["flow_column"])
        mass_column = str(definition["mass_column"])
        mass_start = float(data[mass_column].iloc[0])
        mass_end = float(data[mass_column].iloc[-1])
        mass_loss = mass_start - mass_end
        mass_derived_volume = mass_loss / density
        commanded_volume = integrate_stepwise_command(data, flow_column)
        valid = bool(definition["mass_signal_valid_for_actual_flow"])
        records.append(
            {
                "stream": str(definition["stream"]),
                "stream_label": str(definition["label"]),
                "flow_column": flow_column,
                "mass_column": mass_column,
                "density_g_ml": density,
                "duration_min": duration_min,
                "mass_start_g": mass_start,
                "mass_end_g": mass_end,
                "mass_loss_g": mass_loss,
                "mass_derived_volume_ml": mass_derived_volume,
                "mass_derived_mean_outflow_ml_min": (
                    mass_derived_volume / duration_min
                ),
                "integrated_command_volume_ml": commanded_volume,
                "mass_minus_command_volume_ml": (
                    mass_derived_volume - commanded_volume
                ),
                "mass_minus_command_percent": (
                    100.0
                    * (mass_derived_volume - commanded_volume)
                    / commanded_volume
                ),
                "mass_signal_valid_for_actual_flow": valid,
                "interpretation": (
                    "valid reservoir-depletion estimate"
                    if valid
                    else (
                        "invalid for actual flow because the logged source "
                        "mass increases during positive pump operation"
                    )
                ),
            }
        )
    return pd.DataFrame(records)


def build_audit_summary(
    raw: pd.DataFrame,
    selected: pd.DataFrame,
    events: pd.DataFrame,
    blocks: pd.DataFrame,
    utc_date: date,
    raw_time_monotonic: bool,
) -> pd.DataFrame:
    sample_intervals = selected[TIME_COLUMN].diff().dt.total_seconds().dropna()
    action_intervals = events[
        "seconds_since_previous_action"
    ].dropna()
    complete_blocks = blocks[blocks["complete_30_step_block"]]
    observation_valid = selected.get("observation_valid")
    valid_rows = (
        int(observation_valid.astype(str).str.lower().eq("true").sum())
        if observation_valid is not None
        else None
    )
    metrics: list[tuple[str, object]] = [
        ("selected_utc_date", utc_date.isoformat()),
        ("raw_row_count", len(raw)),
        ("selected_row_count", len(selected)),
        ("rows_outside_selected_date", len(raw) - len(selected)),
        ("selected_start_utc", selected[TIME_COLUMN].iloc[0].isoformat()),
        ("selected_end_utc", selected[TIME_COLUMN].iloc[-1].isoformat()),
        (
            "selected_duration_hours",
            (
                selected[TIME_COLUMN].iloc[-1]
                - selected[TIME_COLUMN].iloc[0]
            ).total_seconds()
            / 3600.0,
        ),
        ("raw_timestamps_monotonic", raw_time_monotonic),
        (
            "raw_backward_timestamp_count",
            raw[TIME_COLUMN].diff().dt.total_seconds().lt(0.0).sum(),
        ),
        ("raw_duplicate_timestamp_count", raw[TIME_COLUMN].duplicated().sum()),
        (
            "selected_timestamps_monotonic",
            selected[TIME_COLUMN].is_monotonic_increasing,
        ),
        (
            "selected_duplicate_timestamp_count",
            selected[TIME_COLUMN].duplicated().sum(),
        ),
        ("selected_valid_observation_rows", valid_rows),
        ("sample_interval_median_seconds", sample_intervals.median()),
        ("sample_interval_maximum_seconds", sample_intervals.max()),
        ("sample_gaps_over_5_seconds", sample_intervals.gt(5.0).sum()),
        ("controller_action_count", len(events)),
        ("controller_interval_mean_seconds", action_intervals.mean()),
        ("controller_interval_median_seconds", action_intervals.median()),
        ("complete_30_step_block_count", len(complete_blocks)),
        ("partial_block_count", (~blocks["complete_30_step_block"]).sum()),
        (
            "complete_block_duration_mean_minutes",
            complete_blocks["duration_min"].mean(),
        ),
        (
            "complete_block_duration_minimum_minutes",
            complete_blocks["duration_min"].min(),
        ),
        (
            "complete_block_duration_maximum_minutes",
            complete_blocks["duration_min"].max(),
        ),
        ("ph2_minimum", selected[PH2_COLUMN].min()),
        ("ph2_maximum", selected[PH2_COLUMN].max()),
        ("ph2_mean", selected[PH2_COLUMN].mean()),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def add_block_boundaries(
    axis: plt.Axes,
    events: pd.DataFrame,
    start_time: pd.Timestamp,
) -> None:
    starts = events.groupby("setpoint_block_index", sort=True).head(1)
    for row in starts.itertuples(index=False):
        elapsed_min = (
            pd.Timestamp(row.utc_time) - start_time
        ).total_seconds() / 60.0
        axis.axvline(elapsed_min, color="#777777", linewidth=0.7, alpha=0.45)


def plot_audit(
    data: pd.DataFrame,
    events: pd.DataFrame,
    blocks: pd.DataFrame,
    figure_path: Path,
    utc_date: date,
    generated_at: datetime,
) -> None:
    start_time = data[TIME_COLUMN].iloc[0]
    elapsed_min = (
        data[TIME_COLUMN] - start_time
    ).dt.total_seconds() / 60.0
    figure, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(14.0, 10.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.2, 1.0, 1.0]},
    )

    axes[0].plot(
        elapsed_min,
        data[PH2_COLUMN],
        color="#006D77",
        linewidth=1.1,
        label="Measured PH_2",
    )
    for block in blocks.itertuples(index=False):
        block_start = (
            pd.Timestamp(block.start_utc) - start_time
        ).total_seconds() / 60.0
        block_end = (
            pd.Timestamp(block.end_utc) - start_time
        ).total_seconds() / 60.0
        axes[0].hlines(
            block.ph2_tail_5min_mean,
            max(block_start, block_end - 5.0),
            block_end,
            color="#F28E2B",
            linewidth=2.2,
        )
        axes[0].text(
            (block_start + block_end) / 2.0,
            0.97,
            f"B{block.setpoint_block_index}",
            transform=axes[0].get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8.0,
            color="#555555",
        )
    axes[0].plot([], [], color="#F28E2B", linewidth=2.2, label="Final 5-min mean")
    axes[0].set_ylabel("pH")
    axes[0].set_title("Reliable outlet pH and 30-action block boundaries")
    axes[0].legend(loc="best", fontsize=8.5)

    for definition in STREAM_DEFINITIONS:
        axes[1].plot(
            elapsed_min,
            data[str(definition["flow_column"])],
            color=str(definition["color"]),
            linewidth=1.05,
            drawstyle="steps-post",
            label=str(definition["label"]),
        )
    axes[1].set_ylabel("Command [mL/min]")
    axes[1].set_title("Logged pump FLOW registers")
    axes[1].legend(loc="best", ncol=3, fontsize=8.5)

    for definition in STREAM_DEFINITIONS:
        axes[2].plot(
            elapsed_min,
            data[str(definition["mass_column"])],
            color=str(definition["color"]),
            linewidth=1.05,
            label=str(definition["label"]),
        )
    axes[2].set_ylabel("Recorded mass [g]")
    axes[2].set_xlabel("Elapsed time from selected UTC-date start [min]")
    axes[2].set_title("Reservoir mass signals; water remains diagnostic only")
    axes[2].legend(loc="best", ncol=3, fontsize=8.5)

    for axis in axes:
        add_block_boundaries(axis, events, start_time)
        axis.grid(True, alpha=0.22, linewidth=0.7)
        axis.set_xlim(0.0, float(elapsed_min.iloc[-1]))

    figure.suptitle(
        f"BioSMB Lab Data Audit: {utc_date.isoformat()} UTC",
        fontsize=15,
        weight="bold",
        y=0.985,
    )
    figure.text(
        0.005,
        0.012,
        (
            "Raw cumulative CSV preserved. Setpoint values are not logged; "
            "blocks group consecutive detected controller actions."
        ),
        ha="left",
        va="bottom",
        fontsize=8.2,
        color="#4A4A4A",
    )
    figure.text(
        0.995,
        0.012,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        ha="right",
        va="bottom",
        fontsize=8.2,
        color="#4A4A4A",
    )
    figure.subplots_adjust(
        left=0.085,
        right=0.985,
        top=0.93,
        bottom=0.075,
        hspace=0.23,
    )
    figure.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_args()
    validate_args(args)
    generated_at = datetime.now(timezone.utc)
    run_stamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path(
        f"results/aug7_data_audit_{run_stamp}"
    )
    table_dir = output_dir / "tables"
    figure_dir = output_dir / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    input_hash_before = sha256_file(args.input)
    raw, selected, date_counts, raw_time_monotonic = load_and_filter_data(
        args.input,
        args.utc_date,
    )
    events = build_action_events(
        selected,
        args.flow_change_threshold,
        args.steps_per_setpoint,
    )
    blocks = build_setpoint_blocks(
        selected,
        events,
        args.steps_per_setpoint,
        args.density,
    )
    mass_balance = build_mass_balance(selected, args.density)
    audit_summary = build_audit_summary(
        raw,
        selected,
        events,
        blocks,
        args.utc_date,
        raw_time_monotonic,
    )

    date_token = args.utc_date.strftime("%Y%m%d")
    selected_path = table_dir / f"biosmb_{date_token}_utc_only.csv"
    date_counts_path = table_dir / "utc_date_counts.csv"
    events_path = table_dir / "controller_action_events.csv"
    blocks_path = table_dir / "thirty_step_setpoint_blocks.csv"
    mass_balance_path = table_dir / "stream_mass_balance.csv"
    audit_summary_path = table_dir / "data_audit_summary.csv"
    figure_path = figure_dir / "aug7_utc_only_data_audit.png"

    selected_export = selected.copy()
    selected_export[TIME_COLUMN] = selected_export[TIME_COLUMN].dt.strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    events_export = events.copy()
    events_export[TIME_COLUMN] = events_export[TIME_COLUMN].dt.strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    selected_export.to_csv(selected_path, index=False)
    date_counts.to_csv(date_counts_path, index=False)
    events_export.to_csv(events_path, index=False)
    blocks.to_csv(blocks_path, index=False)
    mass_balance.to_csv(mass_balance_path, index=False)
    audit_summary.to_csv(audit_summary_path, index=False)
    plot_audit(
        selected,
        events,
        blocks,
        figure_path,
        args.utc_date,
        generated_at,
    )

    input_hash_after = sha256_file(args.input)
    if input_hash_after != input_hash_before:
        raise RuntimeError("Raw input changed while the audit was running.")

    manifest = {
        "analysis": "Aug. 7 UTC-only BioSMB lab-data audit",
        "generated_at_utc": generated_at.isoformat(),
        "script": str(Path(__file__).as_posix()),
        "input_file": str(args.input.as_posix()),
        "input_sha256_before_and_after": input_hash_before,
        "selected_utc_date": args.utc_date.isoformat(),
        "raw_file_preserved": True,
        "steps_per_setpoint_assumption": args.steps_per_setpoint,
        "flow_change_threshold": args.flow_change_threshold,
        "density_g_ml": args.density,
        "setpoint_values_logged_in_csv": False,
        "tables": {
            "utc_only_data": str(selected_path.as_posix()),
            "utc_date_counts": str(date_counts_path.as_posix()),
            "controller_action_events": str(events_path.as_posix()),
            "thirty_step_setpoint_blocks": str(blocks_path.as_posix()),
            "stream_mass_balance": str(mass_balance_path.as_posix()),
            "data_audit_summary": str(audit_summary_path.as_posix()),
        },
        "figures": {"data_audit": str(figure_path.as_posix())},
        "limitations": [
            (
                "The CSV does not log target_ph or the active scheduler "
                "configuration, so block numbers are reconstructed from "
                "detected controller actions and the supplied 30-step setting."
            ),
            (
                "The FLOW registers are treated as commands or readbacks, "
                "not independently verified delivered flows."
            ),
            (
                "The water mass increases during positive water-pump "
                "operation and remains invalid for actual-flow estimation."
            ),
        ],
    }
    manifest_path = output_dir / "aug7_data_audit_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Output directory: {output_dir}")
    print(f"Raw rows: {len(raw)}")
    print(f"Selected UTC-date rows: {len(selected)}")
    print(f"Rows excluded from derivative: {len(raw) - len(selected)}")
    print(f"Detected controller actions: {len(events)}")
    print(
        "Complete 30-step blocks: "
        f"{int(blocks['complete_30_step_block'].sum())}"
    )
    print(f"Partial blocks: {int((~blocks['complete_30_step_block']).sum())}")
    print(f"UTC-only data: {selected_path}")
    print(f"Audit summary: {audit_summary_path}")
    print(f"Block table: {blocks_path}")
    print(f"Mass balance: {mass_balance_path}")
    print(f"Figure: {figure_path}")


if __name__ == "__main__":
    main()
