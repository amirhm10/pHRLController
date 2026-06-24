from __future__ import annotations

import numpy as np
import pandas as pd

from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


def add_henderson_hasselbalch_prepared_predictions(
    prepared_data: pd.DataFrame,
    model: HendersonHasselbalchModel,
) -> pd.DataFrame:
    """Add static Henderson-Hasselbalch predictions to prepared pH data."""
    comparison = prepared_data.copy()
    valid = (
        comparison["ph_measured"].notna()
        & comparison["acid_flow"].gt(0.0)
        & comparison["acetate_flow"].gt(0.0)
        & comparison["water_flow"].ge(0.0)
    )
    comparison["valid_hh_model"] = valid
    comparison["molar_base_acid_ratio"] = np.nan
    comparison.loc[valid, "molar_base_acid_ratio"] = (
        model.base_stock_mol_l * comparison.loc[valid, "acetate_flow"]
    ) / (model.acid_stock_mol_l * comparison.loc[valid, "acid_flow"])
    comparison["log10_molar_base_acid_ratio"] = np.log10(
        comparison["molar_base_acid_ratio"]
    )
    comparison["ph_predicted_hh"] = model.predict_array(
        acid_flow=comparison["acid_flow"],
        base_flow=comparison["acetate_flow"],
        water_flow=comparison["water_flow"],
    )
    comparison.loc[~valid, "ph_predicted_hh"] = np.nan
    comparison["ph_minus_ph_predicted"] = (
        comparison["ph_measured"] - comparison["ph_predicted_hh"]
    )
    comparison["abs_ph_minus_ph_predicted"] = comparison[
        "ph_minus_ph_predicted"
    ].abs()
    comparison["hh_model_name"] = model.display_name
    comparison["hh_pKa"] = float(model.pKa)
    comparison["acid_stock_mol_l"] = float(model.acid_stock_mol_l)
    comparison["base_stock_mol_l"] = float(model.base_stock_mol_l)
    return comparison


def make_hh_overall_metrics(comparison: pd.DataFrame) -> pd.DataFrame:
    valid = comparison["valid_hh_model"] & comparison["ph_predicted_hh"].notna()
    error = comparison.loc[valid, "ph_minus_ph_predicted"]
    return pd.DataFrame(
        [
            {
                "metric_scope": "overall",
                "n": int(valid.sum()),
                "mean_error": safe_mean(error),
                "std_error": safe_std(error),
                "mae": safe_mae(error),
                "rmse": rmse(error),
                "max_abs_error": safe_max_abs(error),
                "correlation_measured_predicted": safe_corr(
                    comparison.loc[valid, "ph_measured"],
                    comparison.loc[valid, "ph_predicted_hh"],
                ),
            },
            {
                "metric_scope": "excluded_rows",
                "n": int((~valid).sum()),
                "mean_error": np.nan,
                "std_error": np.nan,
                "mae": np.nan,
                "rmse": np.nan,
                "max_abs_error": np.nan,
                "correlation_measured_predicted": np.nan,
            },
        ]
    )


def make_hh_sampling_phase_metrics(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for phase_id, group in comparison.groupby("sampling_phase_id", sort=True):
        valid = group["valid_hh_model"] & group["ph_predicted_hh"].notna()
        model_group = group.loc[valid]
        error = model_group["ph_minus_ph_predicted"]
        rows.append(
            {
                "sampling_phase_id": int(phase_id),
                "sampling_phase": str(group["sampling_phase"].iloc[0]),
                "n_total": int(len(group)),
                "n_model_valid": int(valid.sum()),
                "start_sample_index": int(group["sample_index"].iloc[0]),
                "end_sample_index": int(group["sample_index"].iloc[-1]),
                "median_delta_t_min": safe_median(
                    group.loc[~group["long_time_gap"], "delta_t_min"]
                ),
                "mean_error": safe_mean(error),
                "mae": safe_mae(error),
                "rmse": rmse(error),
                "max_abs_error": safe_max_abs(error),
                "correlation_measured_predicted": safe_corr(
                    model_group["ph_measured"],
                    model_group["ph_predicted_hh"],
                ),
                "median_molar_base_acid_ratio": safe_median(
                    model_group["molar_base_acid_ratio"]
                ),
            }
        )
    return pd.DataFrame(rows)


def make_hh_model_metadata(model: HendersonHasselbalchModel) -> pd.DataFrame:
    return pd.DataFrame([model.metadata()])


def select_hh_comparison_columns(comparison: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "sample_index",
        "time",
        "elapsed_min",
        "delta_t_min",
        "long_time_gap",
        "sampling_phase_id",
        "sampling_phase",
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "total_flow",
        "ph_measured",
        "valid_hh_model",
        "molar_base_acid_ratio",
        "log10_molar_base_acid_ratio",
        "ph_predicted_hh",
        "ph_minus_ph_predicted",
        "abs_ph_minus_ph_predicted",
        "hh_pKa",
        "acid_stock_mol_l",
        "base_stock_mol_l",
    ]
    return comparison[columns].copy()


def rmse(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    if len(series) == 0:
        return np.nan
    return float(np.sqrt(np.mean(np.square(series.to_numpy(dtype=float)))))


def safe_mean(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.mean()) if len(series) else np.nan


def safe_std(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.std()) if len(series) else np.nan


def safe_median(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.median()) if len(series) else np.nan


def safe_mae(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.abs().mean()) if len(series) else np.nan


def safe_max_abs(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.abs().max()) if len(series) else np.nan


def safe_corr(x_values: pd.Series, y_values: pd.Series) -> float:
    valid = x_values.notna() & y_values.notna()
    if valid.sum() < 2:
        return np.nan
    return float(x_values.loc[valid].corr(y_values.loc[valid]))
