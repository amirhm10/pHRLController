from __future__ import annotations

from datetime import datetime
from pathlib import Path

from helpers.first_principles_improvement import (
    STATIC_MODEL_STAGES,
    add_split,
    build_chemistry_dataset,
    fit_static_chemistry_models,
    make_model_metrics,
    select_static_comparison_columns,
)
from helpers.first_principles_improvement_plotting import (
    create_static_calibration_figures,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
METHOD_NAME = "effective_static_chemistry_calibration"
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

    fit_mask = chemistry["valid_for_model"] & chemistry["split"].eq("train")
    comparison, parameters = fit_static_chemistry_models(chemistry, fit_mask)
    metrics = make_model_metrics(comparison, STATIC_MODEL_STAGES)
    comparison_table = select_static_comparison_columns(comparison)

    preprocessed.to_csv(table_dir / "preprocessed_lab_data.csv", index=False)
    comparison_table.to_csv(table_dir / "static_chemistry_comparison.csv", index=False)
    metrics.to_csv(table_dir / "train_test_metrics.csv", index=False)
    parameters.to_csv(table_dir / "fitted_parameters.csv", index=False)
    trial_split_summary.to_csv(table_dir / "trial_split_summary.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    create_static_calibration_figures(
        df=comparison,
        metrics=metrics,
        stages=STATIC_MODEL_STAGES,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    print("Effective static chemistry calibration completed.")
    print(f"Results: {result_dir}")
    print(metrics.loc[metrics["split"].eq("test")].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
