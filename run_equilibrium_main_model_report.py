from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.equilibrium_main_model_report import (
    EQUILIBRIUM_MAIN_STAGES,
    create_equilibrium_main_figures,
    extract_equilibrium_calibration,
    make_calibration_table,
    make_generated_grid_summary,
    make_generated_pump_grid,
    make_generated_target_flow_sweep,
    select_equilibrium_comparison_columns,
)
from helpers.first_principles_improvement import (
    add_split,
    build_chemistry_dataset,
    fit_static_chemistry_models,
    make_model_metrics,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
RESULTS_ROOT = Path("results")

METHOD_NAME = "equilibrium_main_model"
TRAIN_FRACTION = 0.70


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    output_dir = setup_output_dir(RESULTS_ROOT / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(output_dir / "tables")
    figure_dir = setup_output_dir(output_dir / "figures")
    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"

    config = PHProcessConfig()
    column_map = LabPHColumnMap()
    equilibrium_model = EquilibriumChargeBalanceModel.from_config(config)

    raw_data = load_lab_csv(DATA_PATH, column_map)
    preprocessed = preprocess_lab_data(raw_data, column_map, config)
    chemistry = build_chemistry_dataset(preprocessed, config)
    chemistry, trial_split_summary = add_split(chemistry, TRAIN_FRACTION)

    fit_mask = chemistry["valid_for_model"] & chemistry["split"].eq("train")
    comparison, fitted_parameters = fit_static_chemistry_models(chemistry, fit_mask)
    lab_metrics = make_model_metrics(comparison, EQUILIBRIUM_MAIN_STAGES)
    lab_comparison = select_equilibrium_comparison_columns(comparison)

    calibration = extract_equilibrium_calibration(fitted_parameters)
    calibration_parameters = make_calibration_table(fitted_parameters, calibration)
    pump_grid = make_generated_pump_grid(config, equilibrium_model, calibration)
    target_sweep = make_generated_target_flow_sweep(
        config,
        equilibrium_model,
        calibration,
    )
    grid_summary = make_generated_grid_summary(pump_grid, target_sweep)

    save_tables(
        table_dir=table_dir,
        preprocessed=preprocessed,
        lab_comparison=lab_comparison,
        lab_metrics=lab_metrics,
        calibration_parameters=calibration_parameters,
        trial_split_summary=trial_split_summary,
        pump_grid=pump_grid,
        target_sweep=target_sweep,
        grid_summary=grid_summary,
    )
    create_equilibrium_main_figures(
        lab_df=comparison,
        lab_metrics=lab_metrics,
        pump_grid=pump_grid,
        target_sweep=target_sweep,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    print(f"Equilibrium main model report artifacts complete: {output_dir}")
    print(f"Tables written: {table_dir}")
    print(f"Figures written: {figure_dir}")
    print(make_console_summary(lab_metrics, calibration, pump_grid, target_sweep))


def save_tables(
    table_dir: Path,
    preprocessed: pd.DataFrame,
    lab_comparison: pd.DataFrame,
    lab_metrics: pd.DataFrame,
    calibration_parameters: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
    pump_grid: pd.DataFrame,
    target_sweep: pd.DataFrame,
    grid_summary: pd.DataFrame,
) -> dict[str, Path]:
    tables = {
        "preprocessed_lab_data": table_dir / "preprocessed_lab_data.csv",
        "lab_equilibrium_model_comparison": (
            table_dir / "lab_equilibrium_model_comparison.csv"
        ),
        "lab_metrics": table_dir / "lab_metrics.csv",
        "calibration_parameters": table_dir / "calibration_parameters.csv",
        "trial_split_summary": table_dir / "trial_split_summary.csv",
        "generated_pump_grid": table_dir / "generated_pump_grid.csv",
        "generated_target_flow_sweep": table_dir / "generated_target_flow_sweep.csv",
        "generated_grid_summary": table_dir / "generated_grid_summary.csv",
    }
    preprocessed.to_csv(tables["preprocessed_lab_data"], index=False)
    lab_comparison.to_csv(tables["lab_equilibrium_model_comparison"], index=False)
    lab_metrics.to_csv(tables["lab_metrics"], index=False)
    calibration_parameters.to_csv(tables["calibration_parameters"], index=False)
    trial_split_summary.to_csv(tables["trial_split_summary"], index=False)
    pump_grid.to_csv(tables["generated_pump_grid"], index=False)
    target_sweep.to_csv(tables["generated_target_flow_sweep"], index=False)
    grid_summary.to_csv(tables["generated_grid_summary"], index=False)
    return tables


def make_console_summary(
    lab_metrics: pd.DataFrame,
    calibration: dict[str, float | int],
    pump_grid: pd.DataFrame,
    target_sweep: pd.DataFrame,
) -> str:
    all_metrics = lab_metrics.loc[
        lab_metrics["split"].eq("all")
        & lab_metrics["model_stage"].eq("equilibrium_raw")
    ].iloc[0]
    test_affine = lab_metrics.loc[
        lab_metrics["split"].eq("test")
        & lab_metrics["model_stage"].eq("equilibrium_affine")
    ].iloc[0]
    return (
        "Key checks: "
        f"raw equilibrium all-row RMSE={all_metrics['rmse']:.4f} pH; "
        f"affine test RMSE={test_affine['rmse']:.4f} pH; "
        f"affine b0={calibration['intercept']:.4f}, "
        f"b1={calibration['slope']:.4f}; "
        f"pump-grid pH range="
        f"{pump_grid['ph_equilibrium_charge_balance'].min():.4f}-"
        f"{pump_grid['ph_equilibrium_charge_balance'].max():.4f}; "
        f"target-sweep rows={len(target_sweep)}."
    )


if __name__ == "__main__":
    main()
