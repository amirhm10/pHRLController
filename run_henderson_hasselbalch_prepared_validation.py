from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.data_preparation import (
    DEFAULT_DATA_PATH,
    TimeFeatureSelection,
    load_raw_time_feature_csv,
    make_sampling_phase_summary,
    prepare_time_feature_data,
    select_time_and_last_features,
)
from helpers.henderson_hasselbalch_prepared import (
    add_henderson_hasselbalch_prepared_predictions,
    make_hh_model_metadata,
    make_hh_overall_metrics,
    make_hh_sampling_phase_metrics,
    select_hh_comparison_columns,
)
from helpers.henderson_hasselbalch_prepared_plotting import create_hh_prepared_figures
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


METHOD_NAME = "henderson_hasselbalch_prepared_validation"
REPORT_PATH = Path("reports/henderson_hasselbalch_prepared_validation.md")


def main() -> None:
    args = parse_args()
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")

    result_dir = setup_output_dir(Path("results") / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(result_dir / "tables")
    figure_dir = setup_output_dir(result_dir / "figures")

    config = PHProcessConfig()
    model = HendersonHasselbalchModel.from_config(config)

    raw_data = load_raw_time_feature_csv(args.data_path)
    selected_data = select_time_and_last_features(
        raw_data,
        TimeFeatureSelection(
            time_column=args.time_column,
            feature_count=args.feature_count,
        ),
    )
    prepared_data = prepare_time_feature_data(selected_data)
    comparison = add_henderson_hasselbalch_prepared_predictions(
        prepared_data,
        model,
    )

    comparison_table = select_hh_comparison_columns(comparison)
    overall_metrics = make_hh_overall_metrics(comparison)
    phase_metrics = make_hh_sampling_phase_metrics(comparison)
    phase_summary = make_sampling_phase_summary(prepared_data)
    model_metadata = make_hh_model_metadata(model)

    prepared_data.to_csv(table_dir / "prepared_time_feature_data.csv", index=False)
    comparison_table.to_csv(table_dir / "hh_model_comparison.csv", index=False)
    overall_metrics.to_csv(table_dir / "overall_metrics.csv", index=False)
    phase_metrics.to_csv(table_dir / "metrics_by_sampling_phase.csv", index=False)
    phase_summary.to_csv(table_dir / "sampling_phase_summary.csv", index=False)
    model_metadata.to_csv(table_dir / "model_metadata.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    figure_paths = create_hh_prepared_figures(
        comparison=comparison,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    write_report(
        data_path=args.data_path,
        result_dir=result_dir,
        model_metadata=model_metadata,
        overall_metrics=overall_metrics,
        phase_metrics=phase_metrics,
        phase_summary=phase_summary,
        figure_paths=figure_paths,
        run_time_display=run_time_display,
    )

    print("Henderson-Hasselbalch prepared-data validation completed.")
    print(f"Source data: {args.data_path}")
    print(f"Model: {model.display_name}")
    print(f"Run time: {run_time_display}")
    print(f"Report: {REPORT_PATH}")
    print(f"Results: {result_dir}")
    print(f"Tables: {table_dir}")
    print(f"Figures: {figure_dir}")
    print()
    print(overall_metrics.round(4).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run static Henderson-Hasselbalch validation on prepared pH data."
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
        help="Column to use for original timestamp spacing.",
    )
    parser.add_argument(
        "--feature-count",
        type=int,
        default=4,
        help="Number of final CSV columns to extract as prepared features.",
    )
    return parser.parse_args()


def write_report(
    data_path: Path,
    result_dir: Path,
    model_metadata: pd.DataFrame,
    overall_metrics: pd.DataFrame,
    phase_metrics: pd.DataFrame,
    phase_summary: pd.DataFrame,
    figure_paths: dict[str, Path],
    run_time_display: str,
) -> None:
    metadata = model_metadata.iloc[0]
    report = f"""# Henderson-Hasselbalch Prepared-Data Validation

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

Apply the static Henderson-Hasselbalch acetate-buffer model to the newly prepared time-series data. This is a first-principles baseline only. No controller, MPC, RL, dynamic delay, or sensor-response model is added here.

## Model

The model uses the acetic-acid stream as acid and the sodium-acetate stream as conjugate base:

$$
\\mathrm{{pH}}_{{HH,k}} = pK_a + \\log_{{10}}\\left(\\frac{{C_A F_{{A,k}}}}{{C_H F_{{H,k}}}}\\right).
$$

For this dataset:

- `F_H` is `acid_flow`, the acetic-acid flow.
- `F_A` is `acetate_flow`, the sodium-acetate flow.
- `C_H = {metadata["acid_stock_mol_l"]:.3f}` mol/L.
- `C_A = {metadata["base_stock_mol_l"]:.3f}` mol/L.
- `pK_a = {metadata["pKa"]:.3f}`.

Because the acid and acetate stock concentrations are equal, the ideal static prediction is controlled by the acetate-to-acid flow ratio. Water is retained in the comparison table for later residence-time and dilution diagnostics, but it does not directly change this ideal ratio.

## Metrics

The residual is

$$
e_k = \\mathrm{{pH}}_k - \\mathrm{{pH}}_{{HH,k}}.
$$

Overall metrics:

{markdown_table(overall_metrics)}

Metrics by sampling phase:

{markdown_table(phase_metrics)}

Sampling phase summary:

{markdown_table(phase_summary)}

## Generated Tables

- `tables/prepared_time_feature_data.csv`: prepared time-series data used by the model.
- `tables/hh_model_comparison.csv`: measured pH, HH prediction, residual, ratio, and phase labels.
- `tables/overall_metrics.csv`: overall residual metrics.
- `tables/metrics_by_sampling_phase.csv`: residual metrics separated by sampling phase.
- `tables/sampling_phase_summary.csv`: detected sampling phases from `delta_t_min`.
- `tables/model_metadata.csv`: pKa and stock concentration values used for the run.

## Figures

### pH and prediction

![pH and prediction]({relative_report_path(figure_paths["ph_vs_prediction"])})

### pH, prediction, and acid/base flows

![pH and prediction with flows]({relative_report_path(figure_paths["ph_vs_prediction_with_flows"])})

### Residual

![Residual]({relative_report_path(figure_paths["residual"])})

## Initial Interpretation

This static model is expected to capture the ideal direction of pH change with the acetate-to-acid ratio. It is not expected to explain transport delay, mixing residence time, sensor response, calibration bias, or phase-dependent sampling behavior. Therefore, residual structure in these figures should be treated as evidence for the next dynamic-modeling step, not as a reason to add controller logic yet.

## Risks And Notes

- The model assumes ideal acetate-buffer behavior with equal 100 mM acid and acetate stocks.
- The pH sensor value is the prepared `pH-sensor` column from the treated dataset.
- The plot x-axis is sequential sample index. Use `delta_t_min` from the saved comparison table for physical delay calculations.
- The two shaded regions are sampling phases detected from the original timestep spacing.

## Recommended Next Step

Use `tables/hh_model_comparison.csv` to inspect residual structure by sampling phase and by acid/base ratio. The next model step should add calibration and dynamic delay/sensor response before any control design.
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
