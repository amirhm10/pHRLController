from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.data_preparation import (
    DEFAULT_DATA_PATH,
    TimeFeatureSelection,
    load_raw_time_feature_csv,
    prepare_time_feature_data,
    select_time_and_last_features,
)
from helpers.hh_residual_shift_diagnostic import make_residual_shift_diagnostic
from helpers.hh_residual_shift_plotting import create_hh_residual_shift_figures
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


METHOD_NAME = "hh_residual_shift_diagnostic"
REPORT_PATH = Path("reports/hh_residual_shift_diagnostic.md")


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")

    result_dir = setup_output_dir(Path("results") / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(result_dir / "tables")
    figure_dir = setup_output_dir(result_dir / "figures")

    config = PHProcessConfig()
    model = HendersonHasselbalchModel.from_config(config)

    raw_data = load_raw_time_feature_csv(DEFAULT_DATA_PATH)
    selected_data = select_time_and_last_features(
        raw_data,
        TimeFeatureSelection(time_column="time", feature_count=4),
    )
    prepared_data = prepare_time_feature_data(selected_data)
    diagnostic = make_residual_shift_diagnostic(raw_data, prepared_data, model)

    for name, table in diagnostic.items():
        if name == "comparison":
            continue
        table.to_csv(table_dir / f"{name}.csv", index=False)

    comparison = diagnostic["comparison"]
    comparison.to_csv(table_dir / "hh_model_comparison_with_shift_context.csv", index=False)

    changepoint_row = diagnostic["changepoint"].iloc[0]
    changepoint = int(changepoint_row["changepoint_sample_index"])
    phase2_start = int(changepoint_row["phase2_start_sample_index"])
    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    figure_paths = create_hh_residual_shift_figures(
        raw_data=raw_data,
        comparison=comparison,
        changepoint=changepoint,
        phase2_start=phase2_start,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    write_report(
        result_dir=result_dir,
        model=model,
        changepoint=diagnostic["changepoint"],
        segment_metrics=diagnostic["segment_metrics"],
        flow_source_metrics=diagnostic["flow_source_metrics"],
        selected_column_medians=diagnostic["selected_column_medians"],
        column_shift_ranking=diagnostic["column_shift_ranking"],
        long_gap_events=diagnostic["long_gap_events"],
        figure_paths=figure_paths,
        run_time_display=run_time_display,
    )

    print("HH residual shift diagnostic completed.")
    print(f"Source data: {DEFAULT_DATA_PATH}")
    print(f"Run time: {run_time_display}")
    print(f"Report: {REPORT_PATH}")
    print(f"Results: {result_dir}")
    print(f"Tables: {table_dir}")
    print(f"Figures: {figure_dir}")
    print()
    print(diagnostic["changepoint"].round(4).to_string(index=False))
    print()
    print(diagnostic["segment_metrics"].round(4).to_string(index=False))


def write_report(
    result_dir: Path,
    model: HendersonHasselbalchModel,
    changepoint: pd.DataFrame,
    segment_metrics: pd.DataFrame,
    flow_source_metrics: pd.DataFrame,
    selected_column_medians: pd.DataFrame,
    column_shift_ranking: pd.DataFrame,
    long_gap_events: pd.DataFrame,
    figure_paths: dict[str, Path],
    run_time_display: str,
) -> None:
    cp = changepoint.iloc[0]
    key_columns = [
        "observation.biosmb-sensors.PH_1",
        "observation.biosmb-sensors.PH_2",
        "observation.biosmb-sensors.COND_3",
        "observation.biosmb-sensors.COND_4",
        "observation.biosmb-sensors.UV_3B",
        "observation.mfcs-mass.acid-mass-grams",
        "observation.mfcs-mass.sodium-mass-grams",
        "observation.mfcs-mass.water-mass-grams",
        "ph_minus_ph_predicted",
    ]
    median_subset = selected_column_medians[
        selected_column_medians["column"].isin(key_columns)
    ].copy()
    top_shifts = column_shift_ranking.head(12)
    flow_source_subset = flow_source_metrics[
        flow_source_metrics["segment"].isin(
            ["pre_jump", "post_jump_same_sampling", "phase2"]
        )
    ].copy()

    report = f"""# HH Residual Shift Diagnostic

Generated: {run_time_display}

Source data:

```text
{DEFAULT_DATA_PATH}
```

Generated artifacts:

```text
{result_dir}
```

## Objective

Check why the Henderson-Hasselbalch residual changes inside the slower-sampling phase before the main sampling-rate transition. The specific question is whether a hidden change in the original dataset, such as flow source, sensor behavior, reservoir state, stock concentration, or effective pKa, explains the shift near sample 200.

## Method

The static model remains

$$
\\mathrm{{pH}}_{{HH,k}} = pK_a + \\log_{{10}}\\left(\\frac{{C_A F_{{A,k}}}}{{C_H F_{{H,k}}}}\\right),
$$

with `pK_a = {model.pKa:.3f}`, `C_H = {model.acid_stock_mol_l:.3f}` mol/L, and `C_A = {model.base_stock_mol_l:.3f}` mol/L.

The residual is

$$
e_k = \\mathrm{{pH}}_k - \\mathrm{{pH}}_{{HH,k}}.
$$

A single mean-residual changepoint scan found the largest persistent shift at sample `{int(cp["changepoint_sample_index"])}`. The sampling-rate phase change starts later at sample `{int(cp["phase2_start_sample_index"])}`.

## Main Finding

The residual shift starts at sample `{int(cp["changepoint_sample_index"])}`, not at the sampling-rate change. At the shift sample, `delta_t_min = {cp["changepoint_delta_t_min"]:.1f}` min because the dataset crosses an overnight lab-session gap. After that boundary, the residual stays near the later biased regime even though the sampling interval remains about 2.33 min until sample `{int(cp["phase2_start_sample_index"])}`.

Changepoint summary:

{markdown_table(changepoint)}

Segment metrics:

{markdown_table(segment_metrics)}

## Flow Source Check

Using the raw `observation.biosmb-flows[0:2]` columns does not remove the jump. It makes the residual more negative than the treated last-column flows. Therefore the shift is not explained by accidentally using the wrong flow columns.

{markdown_table(flow_source_subset)}

## Effective pKa Or Concentration Interpretation

If the model is written as

$$
\\mathrm{{pH}}_k = pK_a^{{eff}} + \\log_{{10}}\\left(\\frac{{F_{{A,k}}}}{{F_{{H,k}}}}\\right),
$$

then `pK_a^{{eff}}` changes from about `4.72` before the jump to about `4.42` after the jump. A real acetic-acid `pK_a` change of about `0.30` pH units is not a normal explanation for the same chemistry. It is better interpreted as either a pH measurement offset, a stock/pump ratio change, or another session-level system change.

If the shift were explained only by effective stock concentration ratio, the post-jump data would imply

$$
\\frac{{(C_A/C_H)_{{actual}}}}{{(C_A/C_H)_{{assumed}}}} \\approx 10^{{\\bar e}} \\approx 0.46.
$$

That would mean the effective sodium-acetate-to-acetic-acid strength was roughly half of the assumed ratio after the jump. The CSV has no direct stock concentration column, so this cannot be confirmed from the log alone.

## Raw Column Evidence

Several raw fields change at the same boundary. Most importantly, `PH_1` jumps from the low-pH range to about 8, and the reservoir mass readings reset upward. This supports a lab-session or hardware/state change rather than a simple sampling-interval effect.

Selected medians by segment:

{markdown_table(median_subset)}

Top local mean shifts around the residual jump:

{markdown_table(top_shifts)}

Long-gap events:

{markdown_table(long_gap_events)}

## Figures

### Residual Overview

![Residual overview]({relative_report_path(figure_paths["residual_overview"])})

### Local Context

![Local context]({relative_report_path(figure_paths["local_context"])})

## Interpretation

The shift is not caused by the later sampling-rate phase change. The strongest evidence is that the residual changes at sample 183, after an overnight gap and session reset, while the sampling interval remains in the slower regime. The pH-model trend remains highly correlated after the jump, which means the acid/base ratio still explains direction, but the intercept has changed.

The most plausible explanations from the available log are:

1. A pH measurement calibration or probe-state offset changed at the new session.
2. The effective acid/base stock or pump calibration ratio changed after reservoir replacement or setup changes.
3. The treated flow columns encode a corrected flow estimate, but the raw observed flow columns do not explain the offset.

## Recommended Next Step

Treat samples before 183 and after 183 as separate calibration regimes. Fit an intercept-only calibration or effective `pK_a` for each regime, then test whether the residual structure remains after this regime correction. If the offset disappears but lag structure remains, move next to delay and sensor-response identification.

## Remaining Uncertainty

The CSV does not contain direct stock concentration, pH probe calibration records, tubing/plumbing changes, or operator notes for the overnight transition. Therefore the diagnostic can identify the timing and likely class of cause, but it cannot prove whether the cause was sensor calibration, concentration, pump calibration, or physical setup.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def markdown_table(df: pd.DataFrame, digits: int = 3) -> str:
    if df.empty:
        return "_No rows._"

    formatted = df.copy()
    for column in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[column]):
            formatted[column] = formatted[column].map(format_float(digits))
    headers = [str(column) for column in formatted.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in formatted.iterrows():
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def format_float(digits: int):
    def _format(value) -> str:
        if pd.isna(value):
            return ""
        return f"{value:.{digits}f}"

    return _format


def relative_report_path(path: Path) -> str:
    return Path("..", path).as_posix()


if __name__ == "__main__":
    main()
