from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


@dataclass(frozen=True)
class AffineCalibration:
    intercept: float
    slope: float
    n_train: int


@dataclass(frozen=True)
class DynamicFit:
    tau_s: float
    train_rmse: float
    success: bool


MODEL_SPECS = {
    "equilibrium_baseline": {
        "prediction": "prediction_equilibrium_baseline",
        "residual": "residual_equilibrium_baseline",
        "label": "Equilibrium baseline",
    },
    "static_calibrated": {
        "prediction": "prediction_static_calibrated",
        "residual": "residual_static_calibrated",
        "label": "Static calibrated",
    },
    "lag_calibrated": {
        "prediction": "prediction_lag_calibrated",
        "residual": "residual_lag_calibrated",
        "label": "Lag calibrated",
    },
    "dynamic_first_order": {
        "prediction": "prediction_dynamic_first_order",
        "residual": "residual_dynamic_first_order",
        "label": "First-order dynamic",
    },
}


def add_equilibrium_predictions(
    df: pd.DataFrame,
    model: EquilibriumChargeBalanceModel,
) -> pd.DataFrame:
    enriched = df.copy()
    for column in [
        "acid_analytical_mol_l",
        "acetate_analytical_mol_l",
        "total_buffer_mol_l",
        "sodium_mol_l",
    ]:
        enriched[column] = np.nan

    valid = enriched["valid_for_model"]
    for row in enriched.loc[valid].itertuples():
        concentrations = model.mixed_concentrations(
            row.acid_flow,
            row.acetate_flow,
            row.water_flow,
        )
        enriched.loc[row.Index, "acid_analytical_mol_l"] = concentrations[
            "acid_analytical_mol_l"
        ]
        enriched.loc[row.Index, "acetate_analytical_mol_l"] = concentrations[
            "acetate_analytical_mol_l"
        ]
        enriched.loc[row.Index, "total_buffer_mol_l"] = concentrations[
            "total_buffer_mol_l"
        ]
        enriched.loc[row.Index, "sodium_mol_l"] = concentrations["sodium_mol_l"]

    enriched["ph_equilibrium_charge_balance"] = model.predict_array(
        enriched["acid_flow"],
        enriched["acetate_flow"],
        enriched["water_flow"],
    )
    enriched.loc[~valid, "ph_equilibrium_charge_balance"] = np.nan
    return enriched


def add_trial_split(
    df: pd.DataFrame,
    train_fraction: float = 0.70,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_df = df.copy()
    trial_ids = sorted(split_df["trial_id"].dropna().unique())
    if len(trial_ids) < 2:
        raise ValueError("At least two trials are required for a train/test split.")

    n_train_trials = int(np.floor(train_fraction * len(trial_ids)))
    n_train_trials = max(1, min(n_train_trials, len(trial_ids) - 1))
    train_trials = set(trial_ids[:n_train_trials])
    split_df["split"] = np.where(
        split_df["trial_id"].isin(train_trials),
        "train",
        "test",
    )

    rows = []
    for trial_id, group in split_df.groupby("trial_id", sort=True):
        rows.append({
            "trial_id": int(trial_id),
            "split": str(group["split"].iloc[0]),
            "n_total": int(len(group)),
            "n_model_valid": int(group["valid_for_model"].sum()),
            "start_time": str(group["utc_datetime"].iloc[0]),
            "end_time": str(group["utc_datetime"].iloc[-1]),
            "duration_min": float(
                (group["utc_datetime"].iloc[-1] - group["utc_datetime"].iloc[0])
                .total_seconds()
                / 60.0
            ),
        })

    return split_df, pd.DataFrame(rows)


def fit_affine_calibration(
    df: pd.DataFrame,
    feature_col: str,
    split: str = "train",
) -> AffineCalibration:
    mask = (
        df["valid_for_model"]
        & df["split"].eq(split)
        & df[feature_col].notna()
        & df["ph_measured"].notna()
    )
    x = df.loc[mask, feature_col].to_numpy(dtype=float)
    y = df.loc[mask, "ph_measured"].to_numpy(dtype=float)
    if len(x) < 2:
        raise ValueError(f"Not enough {split} samples to fit affine calibration.")

    intercept, slope = np.linalg.lstsq(
        np.column_stack([np.ones_like(x), x]),
        y,
        rcond=None,
    )[0]
    return AffineCalibration(
        intercept=float(intercept),
        slope=float(slope),
        n_train=int(len(x)),
    )


def apply_affine_calibration(
    df: pd.DataFrame,
    feature_col: str,
    calibration: AffineCalibration,
    prediction_col: str,
    residual_col: str,
) -> pd.DataFrame:
    enriched = df.copy()
    enriched[prediction_col] = (
        calibration.intercept + calibration.slope * enriched[feature_col]
    )
    enriched.loc[~enriched["valid_for_model"], prediction_col] = np.nan
    enriched[residual_col] = enriched["ph_measured"] - enriched[prediction_col]
    return enriched


def add_baseline_predictions(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["prediction_equilibrium_baseline"] = enriched[
        "ph_equilibrium_charge_balance"
    ]
    enriched["residual_equilibrium_baseline"] = (
        enriched["ph_measured"] - enriched["prediction_equilibrium_baseline"]
    )
    return enriched


def lag_feature_within_trial(df: pd.DataFrame, source_col: str, lag_samples: int) -> pd.Series:
    if lag_samples < 0:
        raise ValueError("lag_samples must be nonnegative.")
    return df.groupby("trial_id", sort=False)[source_col].shift(lag_samples)


def search_lag_models(
    df: pd.DataFrame,
    source_col: str = "ph_equilibrium_charge_balance",
    max_lag_samples: int = 10,
) -> tuple[pd.DataFrame, int, AffineCalibration]:
    rows = []
    calibrations: dict[int, AffineCalibration] = {}

    for lag in range(max_lag_samples + 1):
        feature_col = f"_lag_feature_{lag}"
        lagged = lag_feature_within_trial(df, source_col, lag)
        working = df.copy()
        working[feature_col] = lagged
        calibration = fit_affine_calibration(working, feature_col, split="train")
        calibrations[lag] = calibration
        prediction = calibration.intercept + calibration.slope * working[feature_col]
        residual = working["ph_measured"] - prediction

        for split in ["train", "test"]:
            mask = (
                working["valid_for_model"]
                & working["split"].eq(split)
                & working[feature_col].notna()
                & working["ph_measured"].notna()
            )
            rows.append({
                "lag_samples": int(lag),
                "split": split,
                "n": int(mask.sum()),
                "intercept": float(calibration.intercept),
                "slope": float(calibration.slope),
                **metric_values(
                    working.loc[mask, "ph_measured"],
                    prediction.loc[mask],
                    residual.loc[mask],
                ),
            })

    lag_metrics = pd.DataFrame(rows)
    train_metrics = lag_metrics.loc[lag_metrics["split"] == "train"]
    best_lag = int(train_metrics.sort_values(["rmse", "lag_samples"]).iloc[0]["lag_samples"])
    return lag_metrics, best_lag, calibrations[best_lag]


def add_lag_calibrated_prediction(
    df: pd.DataFrame,
    lag_samples: int,
    calibration: AffineCalibration,
) -> pd.DataFrame:
    enriched = df.copy()
    enriched["lagged_ph_equilibrium"] = lag_feature_within_trial(
        enriched,
        "ph_equilibrium_charge_balance",
        lag_samples,
    )
    enriched["prediction_lag_calibrated"] = (
        calibration.intercept + calibration.slope * enriched["lagged_ph_equilibrium"]
    )
    enriched.loc[~enriched["valid_for_model"], "prediction_lag_calibrated"] = np.nan
    enriched["residual_lag_calibrated"] = (
        enriched["ph_measured"] - enriched["prediction_lag_calibrated"]
    )
    return enriched


def simulate_first_order_response(
    df: pd.DataFrame,
    input_col: str,
    tau_s: float,
) -> pd.Series:
    if tau_s <= 0:
        raise ValueError("tau_s must be positive.")

    prediction = pd.Series(np.nan, index=df.index, dtype=float)
    for _, group in df.groupby("trial_id", sort=False):
        previous = np.nan
        for row in group.itertuples():
            driving_value = getattr(row, input_col)
            if not np.isfinite(driving_value):
                previous = np.nan
                continue

            if not np.isfinite(previous):
                current = float(driving_value)
            else:
                dt_s = row.dt_s
                if not np.isfinite(dt_s) or dt_s < 0.0:
                    dt_s = 0.0
                alpha = float(np.exp(-dt_s / tau_s))
                current = alpha * previous + (1.0 - alpha) * float(driving_value)
            prediction.loc[row.Index] = current
            previous = current

    return prediction


def fit_first_order_tau(
    df: pd.DataFrame,
    input_col: str,
    lower_tau_s: float = 1.0,
    upper_tau_s: float = 20_000.0,
) -> DynamicFit:
    train_mask = (
        df["valid_for_model"]
        & df["split"].eq("train")
        & df[input_col].notna()
        & df["ph_measured"].notna()
    )
    if train_mask.sum() < 3:
        raise ValueError("Not enough train samples to fit first-order dynamics.")

    def objective(log_tau: float) -> float:
        tau_s = float(np.exp(log_tau))
        prediction = simulate_first_order_response(df, input_col, tau_s)
        residual = df.loc[train_mask, "ph_measured"] - prediction.loc[train_mask]
        return rmse(residual)

    result = minimize_scalar(
        objective,
        bounds=(np.log(lower_tau_s), np.log(upper_tau_s)),
        method="bounded",
        options={"xatol": 1e-4},
    )
    tau_s = float(np.exp(result.x))
    return DynamicFit(
        tau_s=tau_s,
        train_rmse=float(result.fun),
        success=bool(result.success),
    )


def add_dynamic_prediction(
    df: pd.DataFrame,
    tau_s: float,
    input_col: str = "prediction_lag_calibrated",
) -> pd.DataFrame:
    enriched = df.copy()
    enriched["prediction_dynamic_first_order"] = simulate_first_order_response(
        enriched,
        input_col,
        tau_s,
    )
    enriched.loc[~enriched["valid_for_model"], "prediction_dynamic_first_order"] = np.nan
    enriched["residual_dynamic_first_order"] = (
        enriched["ph_measured"] - enriched["prediction_dynamic_first_order"]
    )
    return enriched


def make_model_metrics_train_test(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model_key, spec in MODEL_SPECS.items():
        prediction_col = spec["prediction"]
        residual_col = spec["residual"]
        for split in ["train", "test"]:
            mask = (
                df["valid_for_model"]
                & df["split"].eq(split)
                & df[prediction_col].notna()
                & df["ph_measured"].notna()
            )
            rows.append({
                "model_stage": model_key,
                "model_label": spec["label"],
                "split": split,
                "n": int(mask.sum()),
                **metric_values(
                    df.loc[mask, "ph_measured"],
                    df.loc[mask, prediction_col],
                    df.loc[mask, residual_col],
                ),
            })
    return pd.DataFrame(rows)


def make_static_calibration_table(calibration: AffineCalibration) -> pd.DataFrame:
    return pd.DataFrame([{
        "calibration": "PH_2 = b0 + b1 * pH_equilibrium",
        "b0_intercept": float(calibration.intercept),
        "b1_slope": float(calibration.slope),
        "n_train": int(calibration.n_train),
    }])


def make_dynamic_parameters_table(
    dynamic_fit: DynamicFit,
    best_lag_samples: int,
    lag_calibration: AffineCalibration,
    df: pd.DataFrame,
) -> pd.DataFrame:
    valid = df["valid_for_model"]
    median_dt_s = float(df.loc[valid, "dt_s"].dropna().median())
    median_total_flow_ml_min = float(df.loc[valid, "total_flow"].dropna().median())
    theta_approx_s = float(best_lag_samples * median_dt_s)
    volume_effective_ml = float(dynamic_fit.tau_s * median_total_flow_ml_min / 60.0)
    return pd.DataFrame([{
        "best_lag_samples": int(best_lag_samples),
        "theta_approx_s": theta_approx_s,
        "theta_approx_min": theta_approx_s / 60.0,
        "tau_s": float(dynamic_fit.tau_s),
        "tau_min": float(dynamic_fit.tau_s / 60.0),
        "median_dt_s": median_dt_s,
        "median_total_flow_ml_min": median_total_flow_ml_min,
        "v_effective_approx_ml": volume_effective_ml,
        "lag_calibration_intercept": float(lag_calibration.intercept),
        "lag_calibration_slope": float(lag_calibration.slope),
        "train_rmse_at_tau": float(dynamic_fit.train_rmse),
        "optimizer_success": bool(dynamic_fit.success),
        "physical_interpretation": "provisional_without_geometry",
    }])


def select_dynamic_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "sample_index",
        "utc_time",
        "utc_datetime",
        "elapsed_min",
        "elapsed_h",
        "dt_s",
        "session_id",
        "trial_id",
        "split",
        "episode_number",
        "step_number",
        "ph_measured",
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "total_flow",
        "valid_for_model",
        "total_buffer_mol_l",
        "ph_equilibrium_charge_balance",
        "prediction_equilibrium_baseline",
        "residual_equilibrium_baseline",
        "prediction_static_calibrated",
        "residual_static_calibrated",
        "lagged_ph_equilibrium",
        "prediction_lag_calibrated",
        "residual_lag_calibrated",
        "prediction_dynamic_first_order",
        "residual_dynamic_first_order",
    ]
    return df[columns].copy()


def metric_values(
    measured: pd.Series,
    predicted: pd.Series,
    residual: pd.Series,
) -> dict[str, float]:
    residual = pd.Series(residual).dropna()
    measured = pd.Series(measured).dropna()
    predicted = pd.Series(predicted).dropna()
    if len(residual) == 0:
        return {
            "mean_error": np.nan,
            "mae": np.nan,
            "rmse": np.nan,
            "max_abs": np.nan,
            "correlation": np.nan,
        }
    return {
        "mean_error": float(residual.mean()),
        "mae": float(residual.abs().mean()),
        "rmse": rmse(residual),
        "max_abs": float(residual.abs().max()),
        "correlation": float(measured.corr(predicted)) if len(measured) > 1 else np.nan,
    }


def rmse(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return np.nan
    return float(np.sqrt(np.mean(array**2)))


def markdown_table(df: pd.DataFrame, digits: int = 4) -> str:
    rounded = df.copy()
    for column in rounded.columns:
        if pd.api.types.is_float_dtype(rounded[column]):
            rounded[column] = rounded[column].map(format_float(digits))
    headers = [str(column) for column in rounded.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in rounded.iterrows():
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def format_float(digits: int):
    def _format(value: float) -> str:
        if pd.isna(value):
            return ""
        return f"{float(value):.{digits}f}"

    return _format
