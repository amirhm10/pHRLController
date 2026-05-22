from __future__ import annotations

from datetime import datetime
from pathlib import Path

from helpers.first_principles_improvement import (
    add_split,
    build_chemistry_dataset,
    fit_activity_dilution_models,
    make_model_metrics,
)
from helpers.first_principles_improvement_plotting import (
    create_activity_dilution_figures,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
METHOD_NAME = "activity_dilution_correction"
TRAIN_FRACTION = 0.70


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    result_dir = setup_output_dir(Path("results") / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(result_dir / "tables")
    figure_dir = setup_output_dir(result_dir / "figures")

    config = PHProcessConfig()
    column_map = LabPHColumnMap()
    raw = load_lab_csv(DATA_PATH, column_map)
    preprocessed = preprocess_lab_data(raw, column_map, config)
    chemistry = build_chemistry_dataset(preprocessed, config)
    chemistry, trial_split_summary = add_split(chemistry, TRAIN_FRACTION)

    comparison, parameters, stages = fit_activity_dilution_models(chemistry)
    metrics = make_model_metrics(comparison, stages)

    preprocessed.to_csv(table_dir / "preprocessed_lab_data.csv", index=False)
    comparison.to_csv(table_dir / "activity_dilution_model_comparison.csv", index=False)
    metrics.to_csv(table_dir / "correction_model_metrics.csv", index=False)
    parameters.to_csv(table_dir / "correction_model_parameters.csv", index=False)
    trial_split_summary.to_csv(table_dir / "trial_split_summary.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    create_activity_dilution_figures(
        df=comparison,
        metrics=metrics,
        parameters=parameters,
        stages=stages,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    print("Activity/dilution empirical correction completed.")
    print(f"Results: {result_dir}")
    print(metrics.loc[metrics["split"].eq("test")].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
