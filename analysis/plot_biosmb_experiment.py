"""Generate reusable, resolution-separated BioSMB experiment figures."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.biosmb_experiment_data import (  # noqa: E402
    BLOCK_COLUMN,
    FLOW_COLUMNS,
    PH2_COLUMN,
    SCHEDULE_COLUMN,
    TIME_COLUMN,
    aggregate_time_bins,
    assign_reconstructed_schedule,
    build_mass_flow_intervals,
    calculate_mass_flow_metrics,
    calculate_tracking_metrics,
    default_stream_specs,
    detect_controller_actions,
    load_biosmb_experiment,
)
from helpers.biosmb_experiment_plotting import (  # noqa: E402
    plot_mass_flow_intervals,
    plot_minute_tracking_and_inputs,
    plot_seconds_tracking_and_inputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create separate second-level and one-minute BioSMB figure and "
            "table packages using reusable helpers."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data/Aug7 BioSMB RL Test.csv"),
    )
    parser.add_argument("--utc-date", type=date.fromisoformat)
    parser.add_argument(
        "--experiment-label",
        default="Aug. 7 BioSMB RL Test",
    )
    parser.add_argument("--file-prefix", default="aug7")
    parser.add_argument(
        "--target-values",
        nargs="+",
        type=float,
        default=[3.9, 4.3, 4.7, 5.1, 5.5],
    )
    parser.add_argument("--steps-per-setpoint", type=int, default=30)
    parser.add_argument("--target-tolerance", type=float, default=0.1)
    parser.add_argument("--seconds-interval", type=float, default=4.0)
    parser.add_argument("--minute-interval", type=float, default=60.0)
    parser.add_argument("--flow-change-threshold", type=float, default=1.0e-6)
    parser.add_argument("--acid-density", type=float, default=1.0)
    parser.add_argument("--sodium-density", type=float, default=1.0)
    parser.add_argument("--water-density", type=float, default=1.0)
    parser.add_argument(
        "--water-mass-valid",
        action="store_true",
        help="Treat the water reservoir mass as valid for actual-flow output.",
    )
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.steps_per_setpoint <= 0:
        raise ValueError("--steps-per-setpoint must be positive.")
    if args.target_tolerance < 0.0:
        raise ValueError("--target-tolerance must be nonnegative.")
    if args.seconds_interval <= 0.0 or args.minute_interval <= 0.0:
        raise ValueError("Both analysis intervals must be positive.")
    if args.minute_interval <= args.seconds_interval:
        raise ValueError("Minute interval must exceed the seconds interval.")
    if args.flow_change_threshold < 0.0:
        raise ValueError("--flow-change-threshold must be nonnegative.")
    if any(
        density <= 0.0
        for density in (
            args.acid_density,
            args.sodium_density,
            args.water_density,
        )
    ):
        raise ValueError("All densities must be positive.")
    allowed_prefix_characters = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_-"
    )
    if not args.file_prefix or any(
        character not in allowed_prefix_characters
        for character in args.file_prefix
    ):
        raise ValueError("--file-prefix may contain only letters, numbers, _ and -.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_state() -> tuple[str | None, bool | None]:
    try:
        sha = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                "rev-parse",
                "HEAD",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty_output = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                "status",
                "--porcelain",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return sha, bool(dirty_output.strip())
    except (OSError, subprocess.CalledProcessError):
        return None, None


def write_csv(data: pd.DataFrame, path: Path) -> None:
    """Write a table with fixed-format parseable UTC timestamp columns."""

    exported = data.copy()
    for column in exported.columns:
        if isinstance(exported[column].dtype, pd.DatetimeTZDtype):
            exported[column] = exported[column].dt.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
    exported.to_csv(path, index=False)


def build_setpoint_blocks(
    data: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    records = []
    grouped = list(events.groupby(BLOCK_COLUMN, sort=True))
    for position, (block_index, block_events) in enumerate(grouped):
        start_index = int(block_events["sample_index"].iloc[0])
        if position + 1 < len(grouped):
            end_index = int(grouped[position + 1][1]["sample_index"].iloc[0])
            end_time = pd.Timestamp(data[TIME_COLUMN].iloc[end_index])
        else:
            end_index = len(data)
            end_time = pd.Timestamp(data[TIME_COLUMN].iloc[-1])
        segment = data.iloc[start_index:end_index]
        start_time = pd.Timestamp(segment[TIME_COLUMN].iloc[0])
        tail_start = end_time - pd.Timedelta(minutes=5.0)
        tail = segment.loc[segment[TIME_COLUMN].ge(tail_start)]
        target = float(block_events[SCHEDULE_COLUMN].iloc[0])
        tail_error = tail[PH2_COLUMN].to_numpy(dtype=float) - target
        records.append(
            {
                BLOCK_COLUMN: int(block_index),
                "target_ph_reconstructed": target,
                "action_count": len(block_events),
                "start_utc": start_time.isoformat(),
                "end_utc": end_time.isoformat(),
                "duration_min": (end_time - start_time).total_seconds() / 60.0,
                "ph2_full_block_mean": float(segment[PH2_COLUMN].mean()),
                "ph2_tail_5min_mean": float(tail[PH2_COLUMN].mean()),
                "ph2_tail_5min_std": float(tail[PH2_COLUMN].std(ddof=0)),
                "tail_5min_mean_error_ph": float(np.mean(tail_error)),
                "tail_5min_mae_ph": float(np.mean(np.abs(tail_error))),
            }
        )
    return pd.DataFrame(records)


def tracking_export_columns(stream_specs) -> list[str]:
    return [
        TIME_COLUMN,
        "elapsed_seconds",
        BLOCK_COLUMN,
        SCHEDULE_COLUMN,
        PH2_COLUMN,
        *[spec.flow_column for spec in stream_specs],
        *[spec.mass_column for spec in stream_specs],
    ]


def main() -> None:
    args = parse_args()
    validate_args(args)
    generated_at = datetime.now(timezone.utc)
    run_stamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path(
        f"results/{args.file_prefix}_biosmb_figures_{run_stamp}"
    )
    seconds_figure_dir = output_dir / "seconds" / "figures"
    seconds_table_dir = output_dir / "seconds" / "tables"
    minutes_figure_dir = output_dir / "minutes" / "figures"
    minutes_table_dir = output_dir / "minutes" / "tables"
    metadata_dir = output_dir / "metadata"
    for directory in (
        seconds_figure_dir,
        seconds_table_dir,
        minutes_figure_dir,
        minutes_table_dir,
        metadata_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    stream_specs = default_stream_specs(
        water_mass_valid=args.water_mass_valid
    )
    densities = {
        "acid": args.acid_density,
        "sodium_acetate": args.sodium_density,
        "water": args.water_density,
    }
    input_hash = sha256_file(args.input)
    data = load_biosmb_experiment(
        args.input,
        stream_specs=stream_specs,
        utc_date=args.utc_date,
    )
    events = detect_controller_actions(
        data,
        stream_specs=stream_specs,
        flow_change_threshold=args.flow_change_threshold,
    )
    data, events = assign_reconstructed_schedule(
        data,
        events,
        target_values=args.target_values,
        steps_per_setpoint=args.steps_per_setpoint,
    )
    minute_data = aggregate_time_bins(
        data,
        interval_seconds=args.minute_interval,
        stream_specs=stream_specs,
    )
    second_mass_flows = build_mass_flow_intervals(
        data,
        interval_seconds=args.seconds_interval,
        stream_specs=stream_specs,
        densities_g_ml=densities,
        flow_change_threshold=args.flow_change_threshold,
    )
    minute_mass_flows = build_mass_flow_intervals(
        data,
        interval_seconds=args.minute_interval,
        stream_specs=stream_specs,
        densities_g_ml=densities,
        flow_change_threshold=args.flow_change_threshold,
    )
    seconds_tracking_metrics = calculate_tracking_metrics(
        data[PH2_COLUMN].to_numpy(dtype=float),
        data[SCHEDULE_COLUMN].to_numpy(dtype=float),
        resolution="raw_seconds_logs",
    )
    minutes_tracking_metrics = calculate_tracking_metrics(
        minute_data["ph2_mean"].to_numpy(dtype=float),
        minute_data[SCHEDULE_COLUMN].to_numpy(dtype=float),
        resolution=f"elapsed_{args.minute_interval:g}_second_bins",
    )
    seconds_mass_metrics = calculate_mass_flow_metrics(
        second_mass_flows,
        resolution=f"selected_{args.seconds_interval:g}_second_intervals",
    )
    minutes_mass_metrics = calculate_mass_flow_metrics(
        minute_mass_flows,
        resolution=f"selected_{args.minute_interval:g}_second_intervals",
    )
    blocks = build_setpoint_blocks(data, events)

    seconds_tracking_path = (
        seconds_table_dir / "tracking_and_flows_seconds.csv"
    )
    seconds_mass_path = seconds_table_dir / (
        f"mass_derived_flow_{args.seconds_interval:g}_second.csv"
    )
    seconds_tracking_metrics_path = (
        seconds_table_dir / "tracking_metrics_seconds.csv"
    )
    seconds_mass_metrics_path = (
        seconds_table_dir / "mass_flow_metrics_seconds.csv"
    )
    minutes_tracking_path = (
        minutes_table_dir / "tracking_and_flows_one_minute.csv"
    )
    minutes_mass_path = (
        minutes_table_dir / "mass_derived_flow_one_minute.csv"
    )
    minutes_tracking_metrics_path = (
        minutes_table_dir / "tracking_metrics_one_minute.csv"
    )
    minutes_mass_metrics_path = (
        minutes_table_dir / "mass_flow_metrics_one_minute.csv"
    )
    events_path = metadata_dir / "reconstructed_controller_actions.csv"
    blocks_path = metadata_dir / "reconstructed_setpoint_blocks.csv"

    write_csv(data[tracking_export_columns(stream_specs)], seconds_tracking_path)
    write_csv(second_mass_flows, seconds_mass_path)
    write_csv(seconds_tracking_metrics, seconds_tracking_metrics_path)
    write_csv(seconds_mass_metrics, seconds_mass_metrics_path)
    write_csv(minute_data, minutes_tracking_path)
    write_csv(minute_mass_flows, minutes_mass_path)
    write_csv(minutes_tracking_metrics, minutes_tracking_metrics_path)
    write_csv(minutes_mass_metrics, minutes_mass_metrics_path)
    write_csv(events, events_path)
    write_csv(blocks, blocks_path)

    seconds_tracking_figure = (
        seconds_figure_dir
        / f"{args.file_prefix}_ph2_tracking_and_inputs_seconds.png"
    )
    minutes_tracking_figure = (
        minutes_figure_dir
        / f"{args.file_prefix}_ph2_tracking_and_inputs_one_minute.png"
    )
    plot_seconds_tracking_and_inputs(
        data,
        events,
        stream_specs,
        tolerance=args.target_tolerance,
        experiment_label=args.experiment_label,
        figure_path=seconds_tracking_figure,
        generated_at=generated_at,
    )
    plot_minute_tracking_and_inputs(
        minute_data,
        events,
        stream_specs,
        tolerance=args.target_tolerance,
        experiment_label=args.experiment_label,
        figure_path=minutes_tracking_figure,
        generated_at=generated_at,
    )

    seconds_figures = [seconds_tracking_figure]
    minutes_figures = [minutes_tracking_figure]
    for spec in stream_specs:
        seconds_path = seconds_figure_dir / (
            f"{args.file_prefix}_{spec.key}_flow_"
            f"{args.seconds_interval:g}_second.png"
        )
        minutes_path = minutes_figure_dir / (
            f"{args.file_prefix}_{spec.key}_flow_one_minute.png"
        )
        plot_mass_flow_intervals(
            second_mass_flows,
            spec,
            interval_label=f"{args.seconds_interval:g}-Second",
            experiment_label=args.experiment_label,
            figure_path=seconds_path,
            generated_at=generated_at,
        )
        plot_mass_flow_intervals(
            minute_mass_flows,
            spec,
            interval_label="One-Minute",
            experiment_label=args.experiment_label,
            figure_path=minutes_path,
            generated_at=generated_at,
        )
        seconds_figures.append(seconds_path)
        minutes_figures.append(minutes_path)

    git_sha, git_dirty = repository_state()
    effective_configuration = {
        "input": str(args.input.as_posix()),
        "input_sha256": input_hash,
        "utc_date": args.utc_date.isoformat() if args.utc_date else None,
        "experiment_label": args.experiment_label,
        "target_values": args.target_values,
        "target_values_are_reconstructed_not_logged": True,
        "steps_per_setpoint": args.steps_per_setpoint,
        "target_tolerance_ph": args.target_tolerance,
        "seconds_interval": args.seconds_interval,
        "minute_interval": args.minute_interval,
        "flow_change_threshold": args.flow_change_threshold,
        "densities_g_ml": densities,
        "stream_specs": [spec.to_dict() for spec in stream_specs],
    }
    configuration_text = json.dumps(
        effective_configuration,
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest = {
        "schema_version": 1,
        "run_id": output_dir.name,
        "created_at_utc": generated_at.isoformat(),
        "repository": str(ROOT.as_posix()),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "entrypoint": str(Path(__file__).as_posix()),
        "configuration": effective_configuration,
        "configuration_sha256": hashlib.sha256(
            configuration_text.encode("utf-8")
        ).hexdigest(),
        "data_summary": {
            "sample_count": len(data),
            "start_utc": data[TIME_COLUMN].iloc[0].isoformat(),
            "end_utc": data[TIME_COLUMN].iloc[-1].isoformat(),
            "duration_minutes": float(data["elapsed_seconds"].iloc[-1] / 60.0),
            "controller_action_count": len(events),
            "setpoint_block_count": int(events[BLOCK_COLUMN].nunique()),
        },
        "seconds_results": {
            "definition": (
                "every raw pH and command log for tracking; first real CSV "
                f"row per elapsed {args.seconds_interval:g}-second bin for "
                "gravimetric differences"
            ),
            "figures": [str(path.as_posix()) for path in seconds_figures],
            "tables": [
                str(seconds_tracking_path.as_posix()),
                str(seconds_mass_path.as_posix()),
                str(seconds_tracking_metrics_path.as_posix()),
                str(seconds_mass_metrics_path.as_posix()),
            ],
        },
        "minutes_results": {
            "definition": (
                f"independent elapsed {args.minute_interval:g}-second pH and "
                "command summaries; first real CSV row per bin for "
                "gravimetric differences"
            ),
            "figures": [str(path.as_posix()) for path in minutes_figures],
            "tables": [
                str(minutes_tracking_path.as_posix()),
                str(minutes_mass_path.as_posix()),
                str(minutes_tracking_metrics_path.as_posix()),
                str(minutes_mass_metrics_path.as_posix()),
            ],
        },
        "shared_metadata": [str(events_path.as_posix()), str(blocks_path.as_posix())],
        "claim_ledger": [
            {
                "claim": "seconds and minutes outputs use separate analysis windows",
                "class": "verified implementation",
                "evidence": "separate result directories and interval tables",
            },
            {
                "claim": (
                    "target schedule values follow the supplied ping-pong "
                    "sequence"
                ),
                "class": "reconstruction",
                "evidence": "supplied target values and 30-action grouping",
                "limitation": "target_ph is not logged in the source CSV",
            },
            {
                "claim": "water mass is invalid for actual-flow calculation",
                "class": "validated exclusion",
                "evidence": "water mass does not decrease during positive command",
            },
        ],
    }
    manifest_path = output_dir / "biosmb_figure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Output directory: {output_dir}")
    print(f"Selected samples: {len(data)}")
    print(f"Controller actions: {len(events)}")
    print(f"Seconds figures: {len(seconds_figures)}")
    print(f"Minutes figures: {len(minutes_figures)}")
    print(f"Seconds tables: {seconds_table_dir}")
    print(f"Minutes tables: {minutes_table_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
