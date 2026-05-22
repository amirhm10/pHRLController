from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.dynamic_model_identification import (
    add_baseline_predictions,
    add_dynamic_prediction,
    add_equilibrium_predictions,
    add_lag_calibrated_prediction,
    add_trial_split,
    apply_affine_calibration,
    fit_affine_calibration,
    fit_first_order_tau,
    make_dynamic_parameters_table,
    make_model_metrics_train_test,
    make_static_calibration_table,
    search_lag_models,
    select_dynamic_comparison_columns,
)
from helpers.dynamic_model_plotting import create_dynamic_model_figures
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
RESULTS_ROOT = Path("results")

METHOD_NAME = "dynamic_model_identification"
TRAIN_FRACTION = 0.70
MAX_LAG_SAMPLES = 10


def main() -> None:
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = setup_output_dir(RESULTS_ROOT / f"{METHOD_NAME}_{run_stamp}")
    figure_dir = setup_output_dir(output_dir / "figures")
    table_dir = setup_output_dir(output_dir / "tables")
    stamp_text = f"{METHOD_NAME} | {run_stamp}"

    config = PHProcessConfig()
    column_map = LabPHColumnMap()
    equilibrium_model = EquilibriumChargeBalanceModel.from_config(config)

    raw_data = load_lab_csv(DATA_PATH, column_map)
    preprocessed = preprocess_lab_data(raw_data, column_map, config)
    preprocessed = add_equilibrium_predictions(preprocessed, equilibrium_model)
    identified, trial_split_summary = add_trial_split(
        preprocessed,
        train_fraction=TRAIN_FRACTION,
    )

    identified = add_baseline_predictions(identified)
    static_calibration = fit_affine_calibration(
        identified,
        feature_col="ph_equilibrium_charge_balance",
        split="train",
    )
    identified = apply_affine_calibration(
        identified,
        feature_col="ph_equilibrium_charge_balance",
        calibration=static_calibration,
        prediction_col="prediction_static_calibrated",
        residual_col="residual_static_calibrated",
    )

    lag_search, best_lag_samples, lag_calibration = search_lag_models(
        identified,
        source_col="ph_equilibrium_charge_balance",
        max_lag_samples=MAX_LAG_SAMPLES,
    )
    identified = add_lag_calibrated_prediction(
        identified,
        lag_samples=best_lag_samples,
        calibration=lag_calibration,
    )

    dynamic_fit = fit_first_order_tau(
        identified,
        input_col="prediction_lag_calibrated",
    )
    identified = add_dynamic_prediction(
        identified,
        tau_s=dynamic_fit.tau_s,
        input_col="prediction_lag_calibrated",
    )

    comparison = select_dynamic_comparison_columns(identified)
    metrics = make_model_metrics_train_test(identified)
    static_parameters = make_static_calibration_table(static_calibration)
    dynamic_parameters = make_dynamic_parameters_table(
        dynamic_fit=dynamic_fit,
        best_lag_samples=best_lag_samples,
        lag_calibration=lag_calibration,
        df=identified,
    )

    save_tables(
        table_dir=table_dir,
        preprocessed=preprocessed,
        comparison=comparison,
        metrics=metrics,
        static_parameters=static_parameters,
        lag_search=lag_search,
        dynamic_parameters=dynamic_parameters,
        trial_split_summary=trial_split_summary,
    )
    create_dynamic_model_figures(
        df=identified,
        metrics=metrics,
        lag_search=lag_search,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    summary = make_console_summary(metrics, dynamic_parameters)
    print(f"Dynamic model identification complete: {output_dir}")
    print(f"Tables written: {table_dir}")
    print(f"Figures written: {figure_dir}")
    print("Report was not written automatically. Create the report after reviewing artifacts.")
    print(summary)


def save_tables(
    table_dir: Path,
    preprocessed: pd.DataFrame,
    comparison: pd.DataFrame,
    metrics: pd.DataFrame,
    static_parameters: pd.DataFrame,
    lag_search: pd.DataFrame,
    dynamic_parameters: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
) -> dict[str, Path]:
    tables = {
        "preprocessed_lab_data": table_dir / "preprocessed_lab_data.csv",
        "dynamic_model_comparison": table_dir / "dynamic_model_comparison.csv",
        "model_metrics_train_test": table_dir / "model_metrics_train_test.csv",
        "static_calibration_parameters": table_dir / "static_calibration_parameters.csv",
        "lag_search_metrics": table_dir / "lag_search_metrics.csv",
        "dynamic_parameters": table_dir / "dynamic_parameters.csv",
        "trial_split_summary": table_dir / "trial_split_summary.csv",
    }
    preprocessed.to_csv(tables["preprocessed_lab_data"], index=False)
    comparison.to_csv(tables["dynamic_model_comparison"], index=False)
    metrics.to_csv(tables["model_metrics_train_test"], index=False)
    static_parameters.to_csv(tables["static_calibration_parameters"], index=False)
    lag_search.to_csv(tables["lag_search_metrics"], index=False)
    dynamic_parameters.to_csv(tables["dynamic_parameters"], index=False)
    trial_split_summary.to_csv(tables["trial_split_summary"], index=False)
    return tables


def make_console_summary(metrics: pd.DataFrame, dynamic_parameters: pd.DataFrame) -> str:
    pivot = metrics.pivot(index="model_stage", columns="split", values="rmse")
    best_test = metrics.loc[metrics["split"].eq("test")].sort_values("rmse").iloc[0]
    tau_s = float(dynamic_parameters["tau_s"].iloc[0])
    lag = int(dynamic_parameters["best_lag_samples"].iloc[0])
    return (
        "Test RMSE: "
        f"equilibrium={pivot.loc['equilibrium_baseline', 'test']:.4f}, "
        f"static={pivot.loc['static_calibrated', 'test']:.4f}, "
        f"lag={pivot.loc['lag_calibrated', 'test']:.4f}, "
        f"dynamic={pivot.loc['dynamic_first_order', 'test']:.4f}. "
        f"Best test stage={best_test['model_label']}; lag={lag}; tau={tau_s:.1f} s."
    )


if __name__ == "__main__":
    main()
