from __future__ import annotations

import numpy as np
import pandas as pd

from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


def add_henderson_hasselbalch_predictions(
    df: pd.DataFrame,
    model: HendersonHasselbalchModel,
) -> pd.DataFrame:
    enriched = df.copy()
    enriched["molar_base_acid_ratio"] = np.nan
    valid = enriched["valid_for_model"]
    enriched.loc[valid, "molar_base_acid_ratio"] = (
        model.base_stock_mol_l * enriched.loc[valid, "acetate_flow"]
    ) / (model.acid_stock_mol_l * enriched.loc[valid, "acid_flow"])
    enriched["log10_molar_base_acid_ratio"] = np.log10(
        enriched["molar_base_acid_ratio"]
    )
    enriched["ph_henderson_hasselbalch"] = model.predict_array(
        enriched["acid_flow"],
        enriched["acetate_flow"],
        enriched["water_flow"],
    )
    enriched.loc[~valid, "ph_henderson_hasselbalch"] = np.nan
    enriched["measured_minus_hh"] = (
        enriched["ph_measured"] - enriched["ph_henderson_hasselbalch"]
    )
    enriched["hh_model_name"] = model.display_name
    enriched["hh_pKa"] = float(model.pKa)
    enriched["acid_stock_mol_l"] = float(model.acid_stock_mol_l)
    enriched["base_stock_mol_l"] = float(model.base_stock_mol_l)
    return enriched


def make_overall_metrics(df: pd.DataFrame) -> pd.DataFrame:
    valid = df["valid_for_model"] & df["ph_henderson_hasselbalch"].notna()
    error = df.loc[valid, "measured_minus_hh"]
    rows = [metric_row(
        label="PH_2 minus Henderson-Hasselbalch model",
        values=error,
        correlation=df.loc[valid, "ph_measured"].corr(
            df.loc[valid, "ph_henderson_hasselbalch"]
        ),
    )]
    rows.append({
        "metric": "PH_2 versus Henderson-Hasselbalch correlation",
        "n": int(valid.sum()),
        "mean": np.nan,
        "std": np.nan,
        "mae": np.nan,
        "rmse": np.nan,
        "max_abs": np.nan,
        "correlation": float(df.loc[valid, "ph_measured"].corr(
            df.loc[valid, "ph_henderson_hasselbalch"]
        )),
    })
    rows.append({
        "metric": "valid rows used for model metrics",
        "n": int(valid.sum()),
        "mean": np.nan,
        "std": np.nan,
        "mae": np.nan,
        "rmse": np.nan,
        "max_abs": np.nan,
        "correlation": np.nan,
    })
    rows.append({
        "metric": "rows excluded from model metrics",
        "n": int((~valid).sum()),
        "mean": np.nan,
        "std": np.nan,
        "mae": np.nan,
        "rmse": np.nan,
        "max_abs": np.nan,
        "correlation": np.nan,
    })
    return pd.DataFrame(rows)


def make_trial_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for trial_id, group in df.groupby("trial_id", sort=True):
        valid = group["valid_for_model"] & group["ph_henderson_hasselbalch"].notna()
        model_group = group.loc[valid]
        error = model_group["measured_minus_hh"]
        rows.append({
            "trial_id": int(trial_id),
            "session_id": int(group["session_id"].iloc[0]),
            "episode_number": nullable_int(group["episode_number"].iloc[0]),
            "n_total": int(len(group)),
            "n_model_valid": int(valid.sum()),
            "start_time": str(group["utc_datetime"].iloc[0]),
            "end_time": str(group["utc_datetime"].iloc[-1]),
            "duration_min": float(
                (group["utc_datetime"].iloc[-1] - group["utc_datetime"].iloc[0])
                .total_seconds()
                / 60.0
            ),
            "ph_measured_start": first_valid_float(group["ph_measured"]),
            "ph_measured_end": last_valid_float(group["ph_measured"]),
            "ph_hh_start": first_valid_float(model_group["ph_henderson_hasselbalch"]),
            "ph_hh_end": last_valid_float(model_group["ph_henderson_hasselbalch"]),
            "measured_minus_hh_mean": safe_mean(error),
            "measured_minus_hh_mae": safe_mae(error),
            "measured_minus_hh_rmse": rmse(error),
            "measured_minus_hh_final": last_valid_float(group["measured_minus_hh"]),
            "median_acid_flow": safe_median(model_group["acid_flow"]),
            "median_acetate_flow": safe_median(model_group["acetate_flow"]),
            "median_water_flow": safe_median(model_group["water_flow"]),
            "median_total_flow": safe_median(model_group["total_flow"]),
            "median_molar_base_acid_ratio": safe_median(
                model_group["molar_base_acid_ratio"]
            ),
        })
    return pd.DataFrame(rows)


def make_lag_scan(df: pd.DataFrame, max_lag_samples: int = 10) -> pd.DataFrame:
    rows = []
    for lag in range(max_lag_samples + 1):
        shifted_prediction = df.groupby("trial_id")["ph_henderson_hasselbalch"].shift(lag)
        valid = df["valid_for_model"] & shifted_prediction.notna()
        error = df.loc[valid, "ph_measured"] - shifted_prediction.loc[valid]
        rows.append({
            "lag_samples": int(lag),
            "n": int(valid.sum()),
            "correlation": float(
                df.loc[valid, "ph_measured"].corr(shifted_prediction.loc[valid])
            )
            if valid.sum() > 1
            else np.nan,
            "rmse": rmse(error),
            "mae": safe_mae(error),
            "mean_error": safe_mean(error),
        })
    return pd.DataFrame(rows)


def make_affine_diagnostic(df: pd.DataFrame) -> pd.DataFrame:
    valid = df["valid_for_model"] & df["ph_henderson_hasselbalch"].notna()
    x = df.loc[valid, "ph_henderson_hasselbalch"].to_numpy(dtype=float)
    y = df.loc[valid, "ph_measured"].to_numpy(dtype=float)
    if len(x) < 2:
        return pd.DataFrame([{
            "diagnostic": "PH_2 = intercept + slope * pH_HH",
            "n": int(len(x)),
            "intercept": np.nan,
            "slope": np.nan,
            "mae": np.nan,
            "rmse": np.nan,
            "correlation": np.nan,
        }])

    intercept, slope = np.linalg.lstsq(
        np.column_stack([np.ones_like(x), x]),
        y,
        rcond=None,
    )[0]
    fitted = intercept + slope * x
    error = y - fitted
    return pd.DataFrame([{
        "diagnostic": "PH_2 = intercept + slope * pH_HH",
        "n": int(len(x)),
        "intercept": float(intercept),
        "slope": float(slope),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "correlation": float(pd.Series(y).corr(pd.Series(fitted))),
    }])


def add_affine_diagnostic_column(
    df: pd.DataFrame,
    affine_diagnostic: pd.DataFrame,
) -> pd.DataFrame:
    enriched = df.copy()
    row = affine_diagnostic.iloc[0]
    intercept = row["intercept"]
    slope = row["slope"]
    if pd.isna(intercept) or pd.isna(slope):
        enriched["ph_hh_affine_diagnostic"] = np.nan
    else:
        enriched["ph_hh_affine_diagnostic"] = (
            float(intercept) + float(slope) * enriched["ph_henderson_hasselbalch"]
        )
    return enriched


def select_model_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "sample_index",
        "utc_time",
        "utc_datetime",
        "elapsed_min",
        "elapsed_h",
        "dt_s",
        "session_id",
        "trial_id",
        "episode_number",
        "step_number",
        "ph_measured",
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "total_flow",
        "valid_for_model",
        "flow_ratio_acetate_acid",
        "log10_flow_ratio_acetate_acid",
        "molar_base_acid_ratio",
        "log10_molar_base_acid_ratio",
        "ph_henderson_hasselbalch",
        "measured_minus_hh",
        "ph_hh_affine_diagnostic",
        "hh_model_name",
        "hh_pKa",
        "acid_stock_mol_l",
        "base_stock_mol_l",
    ]
    return df[columns].copy()


def metric_row(label: str, values: pd.Series, correlation: float) -> dict:
    values = values.dropna()
    return {
        "metric": label,
        "n": int(len(values)),
        "mean": safe_mean(values),
        "std": float(values.std()) if len(values) else np.nan,
        "mae": safe_mae(values),
        "rmse": rmse(values),
        "max_abs": float(values.abs().max()) if len(values) else np.nan,
        "correlation": float(correlation) if not pd.isna(correlation) else np.nan,
    }


def rmse(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return np.nan
    return float(np.sqrt(np.mean(array**2)))


def safe_mean(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.mean()) if len(values) else np.nan


def safe_median(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.median()) if len(values) else np.nan


def safe_mae(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.abs().mean()) if len(values) else np.nan


def first_valid_float(values: pd.Series) -> float:
    values = values.dropna()
    return float(values.iloc[0]) if len(values) else np.nan


def last_valid_float(values: pd.Series) -> float:
    values = values.dropna()
    return float(values.iloc[-1]) if len(values) else np.nan


def nullable_int(value) -> int | float:
    return np.nan if pd.isna(value) else int(value)
