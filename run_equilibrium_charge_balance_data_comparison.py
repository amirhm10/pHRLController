from __future__ import annotations

from datetime import datetime
from pathlib import Path

from helpers.equilibrium_model_validation import (
    add_affine_diagnostic_column,
    add_equilibrium_charge_balance_predictions,
    make_affine_diagnostic,
    make_lag_scan,
    make_overall_metrics,
    make_trial_metrics,
    select_model_comparison_columns,
)
from helpers.equilibrium_model_validation_plotting import (
    create_equilibrium_validation_figures,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
METHOD_NAME = "equilibrium_charge_balance_lab_validation"


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    result_dir = setup_output_dir(Path("results") / f"{METHOD_NAME}_{run_stamp}")
    figure_dir = setup_output_dir(result_dir / "figures")
    table_dir = setup_output_dir(result_dir / "tables")

    config = PHProcessConfig()
    column_map = LabPHColumnMap()
    model = EquilibriumChargeBalanceModel.from_config(config)

    raw_data = load_lab_csv(DATA_PATH, column_map)
    preprocessed = preprocess_lab_data(raw_data, column_map, config)
    comparison = add_equilibrium_charge_balance_predictions(preprocessed, model)
    affine_diagnostic = make_affine_diagnostic(comparison)
    comparison = add_affine_diagnostic_column(comparison, affine_diagnostic)

    overall_metrics = make_overall_metrics(comparison)
    trial_metrics = make_trial_metrics(comparison)
    lag_scan = make_lag_scan(comparison)
    comparison_table = select_model_comparison_columns(comparison)

    preprocessed.to_csv(table_dir / "preprocessed_lab_data.csv", index=False)
    comparison_table.to_csv(table_dir / "equilibrium_model_comparison.csv", index=False)
    overall_metrics.to_csv(table_dir / "overall_metrics.csv", index=False)
    trial_metrics.to_csv(table_dir / "metrics_by_trial.csv", index=False)
    lag_scan.to_csv(table_dir / "lag_scan.csv", index=False)
    affine_diagnostic.to_csv(table_dir / "affine_diagnostic.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    figure_paths = create_equilibrium_validation_figures(
        df=comparison,
        lag_scan=lag_scan,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
        config=config,
    )

    print("Equilibrium charge-balance lab validation completed.")
    print(f"Source data: {DATA_PATH}")
    print(f"Model: {model.display_name}")
    print(f"Run time: {run_time_display}")
    print(f"Results: {result_dir}")
    print(f"Tables: {table_dir}")
    print(f"Figures: {figure_dir}")
    print()
    print("Generated tables:")
    for path in sorted(table_dir.glob("*.csv")):
        print(f"  {path}")
    print()
    print("Generated figures:")
    for path in figure_paths.values():
        print(f"  {path}")
    print()
    print(overall_metrics.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
