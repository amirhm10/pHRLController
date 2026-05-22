from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from helpers.dynamic_model_identification import (
    AffineCalibration,
    DynamicFit,
    fit_first_order_tau,
    metric_values,
    rmse,
    simulate_first_order_response,
)


@dataclass(frozen=True)
class TransportDelayFit:
    v_tube_ml: float
    calibration: AffineCalibration
    train_rmse: float
    optimizer_success: bool


TRANSPORT_MODEL_SPECS = {
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
    "transport_delay_calibrated": {
        "prediction": "prediction_transport_delay_calibrated",
        "residual": "residual_transport_delay_calibrated",
        "label": "Transport-delay calibrated",
    },
    "transport_delay_dynamic": {
        "prediction": "prediction_transport_delay_dynamic",
        "residual": "residual_transport_delay_dynamic",
        "label": "Transport-delay plus first-order",
    },
}


def add_cumulative_transport_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Add within-trial cumulative transported volume using zero-order-held flow."""
    enriched = df.copy()
    cumulative_volume = pd.Series(np.nan, index=enriched.index, dtype=float)

    for _, group in enriched.groupby("trial_id", sort=False):
        q_ml = 0.0
        previous_index = None
        for index, row in group.iterrows():
            if previous_index is None:
                cumulative_volume.loc[index] = 0.0
                previous_index = index
                continue

            dt_s = float(row["dt_s"]) if np.isfinite(row["dt_s"]) else 0.0
            if dt_s < 0.0:
                dt_s = 0.0
            previous_flow = enriched.loc[previous_index, "total_flow"]
            if np.isfinite(previous_flow) and previous_flow > 0.0:
                q_ml += float(previous_flow) * dt_s / 60.0
            cumulative_volume.loc[index] = q_ml
            previous_index = index

    enriched["cumulative_transport_volume_ml"] = cumulative_volume
    return enriched


def delayed_source_by_transport_volume(
    df: pd.DataFrame,
    source_col: str,
    v_tube_ml: float,
) -> pd.Series:
    """Delay a chemistry source by a fixed transported volume within each trial."""
    delayed = pd.Series(np.nan, index=df.index, dtype=float)
    volume = float(v_tube_ml)
    if volume < 0.0:
        raise ValueError("v_tube_ml must be nonnegative.")

    for _, group in df.groupby("trial_id", sort=False):
        q = group["cumulative_transport_volume_ml"].to_numpy(dtype=float)
        y = group[source_col].to_numpy(dtype=float)
        valid = np.isfinite(q) & np.isfinite(y)
        if valid.sum() == 0:
            continue

        interp_source = (
            pd.DataFrame({"q": q[valid], "y": y[valid]})
            .groupby("q", as_index=False)["y"]
            .mean()
            .sort_values("q")
        )
        q_valid = interp_source["q"].to_numpy(dtype=float)
        y_valid = interp_source["y"].to_numpy(dtype=float)
        q_delay = q - volume

        if len(q_valid) == 1:
            values = np.where(np.isclose(q_delay, q_valid[0]), y_valid[0], np.nan)
        else:
            values = np.interp(q_delay, q_valid, y_valid, left=np.nan, right=np.nan)
        delayed.loc[group.index] = values

    return delayed


def fit_transport_delay_model(
    df: pd.DataFrame,
    source_col: str = "ph_equilibrium_charge_balance",
    max_volume_ml: float = 60.0,
    grid_step_ml: float = 0.5,
) -> tuple[pd.DataFrame, TransportDelayFit]:
    grid = np.arange(0.0, max_volume_ml + grid_step_ml / 2.0, grid_step_ml)
    evaluations: dict[float, tuple[AffineCalibration | None, float]] = {}

    def objective(volume_ml: float) -> float:
        rounded_volume = round(float(volume_ml), 8)
        if rounded_volume not in evaluations:
            delayed = delayed_source_by_transport_volume(df, source_col, rounded_volume)
            calibration = fit_affine_from_series(df, delayed, split="train")
            if calibration is None:
                evaluations[rounded_volume] = (None, np.inf)
            else:
                prediction = calibration.intercept + calibration.slope * delayed
                train = metric_mask(df, delayed, "train")
                residual = df.loc[train, "ph_measured"] - prediction.loc[train]
                evaluations[rounded_volume] = (calibration, rmse(residual))
        return evaluations[rounded_volume][1]

    grid_rmse = np.array([objective(volume) for volume in grid], dtype=float)
    finite_grid = np.isfinite(grid_rmse)
    if not finite_grid.any():
        raise ValueError("No valid train samples were available for transport-delay fitting.")

    best_grid_index = int(np.nanargmin(grid_rmse))
    best_grid_volume = float(grid[best_grid_index])
    lower = max(0.0, best_grid_volume - grid_step_ml)
    upper = min(float(max_volume_ml), best_grid_volume + grid_step_ml)
    if np.isclose(lower, upper):
        refined_volume = best_grid_volume
        optimizer_success = True
    else:
        result = minimize_scalar(
            objective,
            bounds=(lower, upper),
            method="bounded",
            options={"xatol": 1e-4},
        )
        refined_volume = float(result.x)
        optimizer_success = bool(result.success)

    refined_rmse = objective(refined_volume)
    best_grid_rmse = objective(best_grid_volume)
    if best_grid_rmse <= refined_rmse:
        final_volume = best_grid_volume
    else:
        final_volume = refined_volume

    search_rows = []
    for volume in grid:
        search_rows.extend(evaluate_transport_candidate(df, source_col, volume, "grid"))
    search_rows.extend(
        evaluate_transport_candidate(df, source_col, refined_volume, "refined")
    )
    search = pd.DataFrame(search_rows).sort_values(
        ["candidate_type", "v_tube_ml", "split"]
    )

    final_key = round(final_volume, 8)
    calibration, train_rmse = evaluations[final_key]
    if calibration is None:
        raise ValueError("Selected transport-delay fit did not produce a calibration.")

    fit = TransportDelayFit(
        v_tube_ml=final_volume,
        calibration=calibration,
        train_rmse=float(train_rmse),
        optimizer_success=optimizer_success,
    )
    return search, fit


def evaluate_transport_candidate(
    df: pd.DataFrame,
    source_col: str,
    v_tube_ml: float,
    candidate_type: str,
) -> list[dict[str, float | str | int]]:
    delayed = delayed_source_by_transport_volume(df, source_col, v_tube_ml)
    calibration = fit_affine_from_series(df, delayed, split="train")
    rows = []

    if calibration is None:
        for split in ["train", "test"]:
            rows.append({
                "candidate_type": candidate_type,
                "v_tube_ml": float(v_tube_ml),
                "split": split,
                "n": 0,
                "intercept": np.nan,
                "slope": np.nan,
                "mean_error": np.nan,
                "mae": np.nan,
                "rmse": np.nan,
                "max_abs": np.nan,
                "correlation": np.nan,
            })
        return rows

    prediction = calibration.intercept + calibration.slope * delayed
    residual = df["ph_measured"] - prediction
    for split in ["train", "test"]:
        mask = metric_mask(df, delayed, split)
        rows.append({
            "candidate_type": candidate_type,
            "v_tube_ml": float(v_tube_ml),
            "split": split,
            "n": int(mask.sum()),
            "intercept": float(calibration.intercept),
            "slope": float(calibration.slope),
            **metric_values(
                df.loc[mask, "ph_measured"],
                prediction.loc[mask],
                residual.loc[mask],
            ),
        })
    return rows


def fit_affine_from_series(
    df: pd.DataFrame,
    feature: pd.Series,
    split: str = "train",
) -> AffineCalibration | None:
    mask = metric_mask(df, feature, split)
    x = feature.loc[mask].to_numpy(dtype=float)
    y = df.loc[mask, "ph_measured"].to_numpy(dtype=float)
    if len(x) < 2:
        return None

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


def metric_mask(df: pd.DataFrame, feature: pd.Series, split: str) -> pd.Series:
    return (
        df["valid_for_model"].astype(bool)
        & df["split"].eq(split)
        & feature.notna()
        & df["ph_measured"].notna()
    )


def add_transport_delay_predictions(
    df: pd.DataFrame,
    transport_fit: TransportDelayFit,
    source_col: str = "ph_equilibrium_charge_balance",
) -> pd.DataFrame:
    enriched = df.copy()
    enriched["prediction_equilibrium_baseline"] = enriched[source_col]
    enriched["residual_equilibrium_baseline"] = (
        enriched["ph_measured"] - enriched["prediction_equilibrium_baseline"]
    )

    static_calibration = fit_affine_from_series(
        enriched,
        enriched[source_col],
        split="train",
    )
    if static_calibration is None:
        raise ValueError("Static calibration could not be fit.")
    enriched["prediction_static_calibrated"] = (
        static_calibration.intercept + static_calibration.slope * enriched[source_col]
    )
    enriched["residual_static_calibrated"] = (
        enriched["ph_measured"] - enriched["prediction_static_calibrated"]
    )

    delayed_source = delayed_source_by_transport_volume(
        enriched,
        source_col,
        transport_fit.v_tube_ml,
    )
    enriched["transport_delayed_volume_coordinate_ml"] = (
        enriched["cumulative_transport_volume_ml"] - transport_fit.v_tube_ml
    )
    enriched["ph_equilibrium_transport_delayed"] = delayed_source
    enriched["theta_transport_s"] = np.where(
        enriched["total_flow"].gt(0.0),
        60.0 * transport_fit.v_tube_ml / enriched["total_flow"],
        np.nan,
    )
    enriched["prediction_transport_delay_calibrated"] = (
        transport_fit.calibration.intercept
        + transport_fit.calibration.slope * delayed_source
    )
    enriched["residual_transport_delay_calibrated"] = (
        enriched["ph_measured"] - enriched["prediction_transport_delay_calibrated"]
    )

    for column in [
        "prediction_equilibrium_baseline",
        "prediction_static_calibrated",
        "prediction_transport_delay_calibrated",
    ]:
        enriched.loc[~enriched["valid_for_model"], column] = np.nan
    for column in [
        "residual_equilibrium_baseline",
        "residual_static_calibrated",
        "residual_transport_delay_calibrated",
    ]:
        enriched.loc[~enriched["valid_for_model"], column] = np.nan

    return enriched


def add_transport_delay_dynamic_prediction(
    df: pd.DataFrame,
    input_col: str = "prediction_transport_delay_calibrated",
) -> tuple[pd.DataFrame, DynamicFit]:
    fit = fit_first_order_tau(df, input_col=input_col)
    enriched = df.copy()
    enriched["prediction_transport_delay_dynamic"] = simulate_first_order_response(
        enriched,
        input_col,
        fit.tau_s,
    )
    enriched.loc[~enriched["valid_for_model"], "prediction_transport_delay_dynamic"] = np.nan
    enriched["residual_transport_delay_dynamic"] = (
        enriched["ph_measured"] - enriched["prediction_transport_delay_dynamic"]
    )
    enriched.loc[~enriched["valid_for_model"], "residual_transport_delay_dynamic"] = np.nan
    return enriched, fit


def make_transport_model_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model_key, spec in TRANSPORT_MODEL_SPECS.items():
        prediction_col = spec["prediction"]
        residual_col = spec["residual"]
        for split in ["train", "test"]:
            mask = (
                df["valid_for_model"].astype(bool)
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


def make_transport_delay_parameters(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    transport_fit: TransportDelayFit,
    dynamic_fit: DynamicFit,
    max_volume_ml: float,
    near_zero_volume_threshold_ml: float = 0.5,
    minimum_improvement_threshold_ph: float = 0.005,
) -> pd.DataFrame:
    static_train = metric_rmse(metrics, "static_calibrated", "train")
    static_test = metric_rmse(metrics, "static_calibrated", "test")
    transport_train = metric_rmse(metrics, "transport_delay_calibrated", "train")
    transport_test = metric_rmse(metrics, "transport_delay_calibrated", "test")
    train_improvement = static_train - transport_train
    test_improvement = static_test - transport_test

    if transport_fit.v_tube_ml <= near_zero_volume_threshold_ml:
        identifiability = "weak_non_identifiable_near_zero_volume"
    elif test_improvement <= 0.0:
        identifiability = "not_supported_on_held_out_trials"
    elif (
        train_improvement < minimum_improvement_threshold_ph
        and test_improvement < minimum_improvement_threshold_ph
    ):
        identifiability = "weak_non_identifiable_small_rmse_gain"
    else:
        identifiability = "empirically_supported_effective_delay"

    valid_theta = df.loc[df["valid_for_model"], "theta_transport_s"].dropna()
    valid_flow = df.loc[df["valid_for_model"], "total_flow"].dropna()
    return pd.DataFrame([{
        "best_v_tube_ml": float(transport_fit.v_tube_ml),
        "max_search_volume_ml": float(max_volume_ml),
        "transport_intercept": float(transport_fit.calibration.intercept),
        "transport_slope": float(transport_fit.calibration.slope),
        "transport_n_train": int(transport_fit.calibration.n_train),
        "static_train_rmse": float(static_train),
        "static_test_rmse": float(static_test),
        "transport_train_rmse": float(transport_train),
        "transport_test_rmse": float(transport_test),
        "train_rmse_improvement_vs_static": float(train_improvement),
        "test_rmse_improvement_vs_static": float(test_improvement),
        "median_total_flow_ml_min": float(valid_flow.median()),
        "median_theta_transport_s": float(valid_theta.median()),
        "min_theta_transport_s": float(valid_theta.min()),
        "max_theta_transport_s": float(valid_theta.max()),
        "dynamic_tau_s": float(dynamic_fit.tau_s),
        "dynamic_train_rmse": metric_rmse(metrics, "transport_delay_dynamic", "train"),
        "dynamic_test_rmse": metric_rmse(metrics, "transport_delay_dynamic", "test"),
        "optimizer_success": bool(transport_fit.optimizer_success),
        "dynamic_optimizer_success": bool(dynamic_fit.success),
        "near_zero_volume_threshold_ml": float(near_zero_volume_threshold_ml),
        "minimum_improvement_threshold_ph": float(minimum_improvement_threshold_ph),
        "identifiability": identifiability,
        "physical_interpretation": "effective_delay_volume_not_hardware_geometry",
    }])


def metric_rmse(metrics: pd.DataFrame, model_stage: str, split: str) -> float:
    value = metrics.loc[
        metrics["model_stage"].eq(model_stage) & metrics["split"].eq(split),
        "rmse",
    ]
    if value.empty:
        return np.nan
    return float(value.iloc[0])


def make_trial_transport_delay_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for trial_id, group in df.groupby("trial_id", sort=True):
        valid = group["valid_for_model"].astype(bool)
        row = {
            "trial_id": int(trial_id),
            "session_id": int(group["session_id"].iloc[0]),
            "split": str(group["split"].iloc[0]),
            "n_total": int(len(group)),
            "n_model_valid": int(valid.sum()),
            "start_time": str(group["utc_datetime"].iloc[0]),
            "end_time": str(group["utc_datetime"].iloc[-1]),
            "max_cumulative_volume_ml": float(
                group["cumulative_transport_volume_ml"].dropna().max()
            ),
            "median_theta_transport_s": float(
                group.loc[valid, "theta_transport_s"].dropna().median()
            ),
            "static_rmse": rmse(group.loc[valid, "residual_static_calibrated"]),
            "transport_delay_rmse": rmse(
                group.loc[valid, "residual_transport_delay_calibrated"]
            ),
            "transport_dynamic_rmse": rmse(
                group.loc[valid, "residual_transport_delay_dynamic"]
            ),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def select_transport_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
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
        "uninformative_flat_ph_trial",
        "total_buffer_mol_l",
        "ph_equilibrium_charge_balance",
        "cumulative_transport_volume_ml",
        "transport_delayed_volume_coordinate_ml",
        "theta_transport_s",
        "ph_equilibrium_transport_delayed",
        "prediction_equilibrium_baseline",
        "residual_equilibrium_baseline",
        "prediction_static_calibrated",
        "residual_static_calibrated",
        "prediction_transport_delay_calibrated",
        "residual_transport_delay_calibrated",
        "prediction_transport_delay_dynamic",
        "residual_transport_delay_dynamic",
    ]
    return df[columns].copy()
