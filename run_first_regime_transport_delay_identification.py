from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.dynamic_model_identification import (
    add_equilibrium_predictions,
    add_trial_split,
    make_sampling_summary,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from helpers.transport_delay_identification import (
    add_cumulative_transport_volume,
    add_transport_delay_dynamic_prediction,
    add_transport_delay_predictions,
    fit_transport_delay_model,
    make_transport_delay_parameters,
    make_transport_model_metrics,
    make_trial_transport_delay_summary,
    select_transport_comparison_columns,
)
from helpers.transport_delay_plotting import create_transport_delay_figures
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
RESULTS_ROOT = Path("results")

METHOD_NAME = "first_regime_transport_delay_identification"
TRAIN_FRACTION = 0.70
MAX_VOLUME_ML = 60.0
GRID_STEP_ML = 0.5

# Sessions 0-3 are the earlier operating regime with roughly 140-142 s sampling.
MAX_TWO_MINUTE_SESSION_ID = 3


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
    preprocessed_full = preprocess_lab_data(raw_data, column_map, config)
    preprocessed_full = add_equilibrium_predictions(preprocessed_full, equilibrium_model)
    preprocessed = select_two_minute_first_regime(preprocessed_full)
    identified, trial_split_summary = add_trial_split(
        preprocessed,
        train_fraction=TRAIN_FRACTION,
    )
    identified = add_cumulative_transport_volume(identified)

    delay_search, transport_fit = fit_transport_delay_model(
        identified,
        source_col="ph_equilibrium_charge_balance",
        max_volume_ml=MAX_VOLUME_ML,
        grid_step_ml=GRID_STEP_ML,
    )
    identified = add_transport_delay_predictions(
        identified,
        transport_fit,
        source_col="ph_equilibrium_charge_balance",
    )
    identified, dynamic_fit = add_transport_delay_dynamic_prediction(identified)

    comparison = select_transport_comparison_columns(identified)
    metrics = make_transport_model_metrics(identified)
    parameters = make_transport_delay_parameters(
        df=identified,
        metrics=metrics,
        transport_fit=transport_fit,
        dynamic_fit=dynamic_fit,
        max_volume_ml=MAX_VOLUME_ML,
    )
    trial_delay_summary = make_trial_transport_delay_summary(identified)
    sampling_summary = make_sampling_summary(identified)
    subset_summary = make_first_regime_subset_summary(preprocessed_full, identified)

    save_tables(
        table_dir=table_dir,
        preprocessed=preprocessed,
        comparison=comparison,
        metrics=metrics,
        delay_search=delay_search,
        parameters=parameters,
        trial_delay_summary=trial_delay_summary,
        trial_split_summary=trial_split_summary,
        sampling_summary=sampling_summary,
        subset_summary=subset_summary,
    )
    create_transport_delay_figures(
        df=identified,
        metrics=metrics,
        search=delay_search,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    print(f"First-regime transport-delay identification complete: {output_dir}")
    print(f"Tables written: {table_dir}")
    print(f"Figures written: {figure_dir}")
    print("Report was not written automatically. Create the report after reviewing artifacts.")
    print(make_console_summary(parameters, metrics, subset_summary))


def select_two_minute_first_regime(preprocessed: pd.DataFrame) -> pd.DataFrame:
    subset = preprocessed.loc[
        preprocessed["session_id"].le(MAX_TWO_MINUTE_SESSION_ID)
    ].copy()
    if subset["trial_id"].nunique() < 2:
        raise ValueError("The first-regime subset needs at least two trials.")
    return subset


def make_first_regime_subset_summary(
    full_df: pd.DataFrame,
    subset: pd.DataFrame,
) -> pd.DataFrame:
    valid = subset["valid_for_model"].astype(bool)
    dt = subset["dt_s"].dropna()
    positive_dt = dt.loc[dt > 0.0]
    return pd.DataFrame([{
        "subset_name": "two_minute_first_regime",
        "filter_rule": f"session_id <= {MAX_TWO_MINUTE_SESSION_ID}",
        "source_rows": int(len(full_df)),
        "subset_rows": int(len(subset)),
        "subset_model_valid_rows": int(valid.sum()),
        "session_ids": ",".join(str(int(x)) for x in sorted(subset["session_id"].unique())),
        "sample_index_min": int(subset["sample_index"].min()),
        "sample_index_max": int(subset["sample_index"].max()),
        "trial_id_min": int(subset["trial_id"].min()),
        "trial_id_max": int(subset["trial_id"].max()),
        "median_dt_s": float(positive_dt.median()),
        "p05_dt_s": float(positive_dt.quantile(0.05)),
        "p95_dt_s": float(positive_dt.quantile(0.95)),
        "median_total_flow_ml_min": float(subset.loc[valid, "total_flow"].median()),
        "median_ph_measured": float(subset.loc[valid, "ph_measured"].median()),
    }])


def save_tables(
    table_dir: Path,
    preprocessed: pd.DataFrame,
    comparison: pd.DataFrame,
    metrics: pd.DataFrame,
    delay_search: pd.DataFrame,
    parameters: pd.DataFrame,
    trial_delay_summary: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
    sampling_summary: pd.DataFrame,
    subset_summary: pd.DataFrame,
) -> dict[str, Path]:
    tables = {
        "preprocessed_lab_data": table_dir / "preprocessed_lab_data.csv",
        "transport_delay_model_comparison": (
            table_dir / "transport_delay_model_comparison.csv"
        ),
        "model_metrics_train_test": table_dir / "model_metrics_train_test.csv",
        "transport_delay_search": table_dir / "transport_delay_search.csv",
        "transport_delay_parameters": table_dir / "transport_delay_parameters.csv",
        "trial_transport_delay_summary": (
            table_dir / "trial_transport_delay_summary.csv"
        ),
        "trial_split_summary": table_dir / "trial_split_summary.csv",
        "sampling_summary": table_dir / "sampling_summary.csv",
        "first_regime_subset_summary": table_dir / "first_regime_subset_summary.csv",
    }
    preprocessed.to_csv(tables["preprocessed_lab_data"], index=False)
    comparison.to_csv(tables["transport_delay_model_comparison"], index=False)
    metrics.to_csv(tables["model_metrics_train_test"], index=False)
    delay_search.to_csv(tables["transport_delay_search"], index=False)
    parameters.to_csv(tables["transport_delay_parameters"], index=False)
    trial_delay_summary.to_csv(tables["trial_transport_delay_summary"], index=False)
    trial_split_summary.to_csv(tables["trial_split_summary"], index=False)
    sampling_summary.to_csv(tables["sampling_summary"], index=False)
    subset_summary.to_csv(tables["first_regime_subset_summary"], index=False)
    return tables


def make_console_summary(
    parameters: pd.DataFrame,
    metrics: pd.DataFrame,
    subset_summary: pd.DataFrame,
) -> str:
    row = parameters.iloc[0]
    subset = subset_summary.iloc[0]
    pivot = metrics.pivot(index="model_stage", columns="split", values="rmse")
    return (
        f"Subset sessions={subset['session_ids']}; "
        f"median dt={float(subset['median_dt_s']):.1f} s. "
        "Test RMSE: "
        f"equilibrium={pivot.loc['equilibrium_baseline', 'test']:.4f}, "
        f"static={pivot.loc['static_calibrated', 'test']:.4f}, "
        f"transport={pivot.loc['transport_delay_calibrated', 'test']:.4f}, "
        f"transport+dynamic={pivot.loc['transport_delay_dynamic', 'test']:.4f}. "
        f"Best V_tube={float(row['best_v_tube_ml']):.3f} mL; "
        f"median theta={float(row['median_theta_transport_s']):.2f} s; "
        f"identifiability={row['identifiability']}."
    )


if __name__ == "__main__":
    main()
