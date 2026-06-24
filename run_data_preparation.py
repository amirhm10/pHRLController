from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.data_preparation import (
    DEFAULT_DATA_PATH,
    TimeFeatureSelection,
    load_raw_time_feature_csv,
    make_column_mapping,
    make_feature_summary,
    make_preparation_overview,
    prepare_time_feature_data,
    select_time_and_last_features,
)
from helpers.data_preparation_plotting import (
    PLOT_GAP_THRESHOLD_MIN,
    create_data_preparation_figures,
)
from helpers.plotting import setup_output_dir


METHOD_NAME = "data_preparation"
REPORT_PATH = Path("reports/data_preparation_report.md")


def main() -> None:
    args = parse_args()
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")

    result_dir = setup_output_dir(Path("results") / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(result_dir / "tables")
    figure_dir = setup_output_dir(result_dir / "figures")

    selection = TimeFeatureSelection(
        time_column=args.time_column,
        feature_count=args.feature_count,
    )
    raw_data = load_raw_time_feature_csv(args.data_path)
    selected_data = select_time_and_last_features(raw_data, selection)
    prepared_data = prepare_time_feature_data(selected_data)

    overview = make_preparation_overview(raw_data, selected_data, prepared_data)
    feature_summary = make_feature_summary(prepared_data)
    column_mapping = make_column_mapping(prepared_data)

    selected_data.to_csv(table_dir / "selected_time_and_last_four_columns.csv", index=False)
    prepared_data.to_csv(table_dir / "prepared_time_feature_data.csv", index=False)
    overview.to_csv(table_dir / "preparation_overview.csv", index=False)
    feature_summary.to_csv(table_dir / "feature_summary.csv", index=False)
    column_mapping.to_csv(table_dir / "column_mapping.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    figure_paths = create_data_preparation_figures(
        prepared_data=prepared_data,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    write_report(
        data_path=args.data_path,
        result_dir=result_dir,
        overview=overview,
        feature_summary=feature_summary,
        column_mapping=column_mapping,
        figure_paths=figure_paths,
        run_time_display=run_time_display,
    )

    print("Data preparation completed.")
    print(f"Source data: {args.data_path}")
    print(f"Run time: {run_time_display}")
    print(f"Report: {REPORT_PATH}")
    print(f"Results: {result_dir}")
    print(f"Tables: {table_dir}")
    print(f"Figures: {figure_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract timestep plus the last four pH experiment features."
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Raw CSV path.",
    )
    parser.add_argument(
        "--time-column",
        default="time",
        help="Column to use as the timestep axis.",
    )
    parser.add_argument(
        "--feature-count",
        type=int,
        default=4,
        help="Number of final CSV columns to extract as features.",
    )
    return parser.parse_args()


def write_report(
    data_path: Path,
    result_dir: Path,
    overview: pd.DataFrame,
    feature_summary: pd.DataFrame,
    column_mapping: pd.DataFrame,
    figure_paths: dict[str, Path],
    run_time_display: str,
) -> None:
    overview_row = overview.iloc[0]
    report = f"""# Data Preparation Report

Generated: {run_time_display}

Source data:

```text
{data_path}
```

Generated artifacts:

```text
{result_dir}
```

## Objective

Start the new data-analysis workflow by preparing only the timestep column and the last four columns from the updated lab CSV. This is intentionally limited to data preparation and visual inspection. No new chemistry model, controller, MPC, or RL logic is added here.

## Method

The raw CSV is loaded without editing the file. The preparation script selects:

- timestep column: `{overview_row["time_column"]}`
- final feature columns: `{overview_row["feature_columns"]}`

The selected feature columns are standardized for downstream code:

{markdown_table(column_mapping)}

The prepared time-series vector for sample `k` is

$$
z_k = \\left[t_k, F_{{H,k}}, F_{{A,k}}, F_{{W,k}}, \\mathrm{{pH}}_k\\right],
$$

where `F_H` is acetic acid flow, `F_A` is sodium acetate flow, `F_W` is water flow, and `pH_k` is the measured pH sensor value from the treated dataset. The plotted x-axis uses elapsed minutes derived from the selected timestep column. Plot lines are broken across gaps larger than {PLOT_GAP_THRESHOLD_MIN:.0f} minutes so separate lab blocks are not shown as artificial ramps.

## Dataset Summary

{markdown_table(overview)}

## Feature Summary

{markdown_table(feature_summary)}

## Generated Tables

- `tables/selected_time_and_last_four_columns.csv`: exact extraction of timestep plus the last four CSV columns.
- `tables/prepared_time_feature_data.csv`: standardized feature names plus basic derived columns for future analysis.
- `tables/preparation_overview.csv`: source and selected-data metadata.
- `tables/feature_summary.csv`: numeric summary of the prepared features.
- `tables/column_mapping.csv`: source-column to prepared-column mapping.

## Figures

### Individual feature traces

![Acid flow]({relative_report_path(figure_paths["acid_flow_timeseries"])})

![Sodium acetate flow]({relative_report_path(figure_paths["acetate_flow_timeseries"])})

![Water flow]({relative_report_path(figure_paths["water_flow_timeseries"])})

![Measured pH]({relative_report_path(figure_paths["ph_measured_timeseries"])})

### Four-feature overview

![All features]({relative_report_path(figure_paths["all_features_four_subplots"])})

### pH with acid/base flows

![pH with acid and base flows]({relative_report_path(figure_paths["ph_with_acid_base_flows"])})

## Initial Interpretation

The prepared dataset is a compact time-series view of the experiment: acid flow, sodium acetate flow, water flow, and pH. The first useful checks are visual continuity, flow ranges, abrupt setpoint-like moves, and whether pH responds after flow changes. This report does not yet separate trials, estimate delays, or fit any static or dynamic model.

## Risks And Notes

- The selected `time` column appears to be a numeric timestamp in day units in this file, so elapsed minutes are derived by subtracting the first value and multiplying by 1440.
- Existing validation runners still point to the previous treated CSV name. They should be updated only after this new prepared dataset is inspected.
- The current report treats the last four columns as the working features because that is the stated data-preparation rule for this step.

## Recommended Next Step

After visually checking these figures, the next small step is to add trial/session segmentation and simple lag-aware pH response diagnostics using this prepared table. That should happen before any new controller or RL work.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def markdown_table(df: pd.DataFrame, digits: int = 3) -> str:
    if df.empty:
        return "_No rows._"

    formatted = df.copy()
    for column in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[column]):
            formatted[column] = formatted[column].map(lambda value: f"{value:.{digits}f}")
    headers = [str(column) for column in formatted.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in formatted.iterrows():
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def relative_report_path(path: Path) -> str:
    return Path("..", path).as_posix()


if __name__ == "__main__":
    main()
