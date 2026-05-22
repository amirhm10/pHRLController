from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from helpers.dynamic_model_identification import add_trial_split
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


@dataclass(frozen=True)
class ModelStage:
    key: str
    label: str
    prediction_col: str


STATIC_MODEL_STAGES = [
    ModelStage("hh_raw", "Raw Henderson-Hasselbalch", "prediction_hh_raw"),
    ModelStage("equilibrium_raw", "Raw equilibrium", "prediction_equilibrium_raw"),
    ModelStage("equilibrium_bias", "Equilibrium + bias", "prediction_equilibrium_bias"),
    ModelStage("hh_effective_pka", "HH effective pKa", "prediction_hh_effective_pka"),
    ModelStage("hh_affine", "HH affine", "prediction_hh_affine"),
    ModelStage("equilibrium_affine", "Equilibrium affine", "prediction_equilibrium_affine"),
]


def build_chemistry_dataset(
    preprocessed: pd.DataFrame,
    config: PHProcessConfig,
) -> pd.DataFrame:
    """Add HH, equilibrium, and diagnostic chemistry features."""
    hh_model = HendersonHasselbalchModel.from_config(config)
    equilibrium_model = EquilibriumChargeBalanceModel.from_config(config)
    df = preprocessed.copy()
    valid = df["valid_for_model"]

    df["molar_base_acid_ratio"] = np.nan
    df.loc[valid, "molar_base_acid_ratio"] = (
        hh_model.base_stock_mol_l * df.loc[valid, "acetate_flow"]
    ) / (hh_model.acid_stock_mol_l * df.loc[valid, "acid_flow"])
    df["log10_molar_base_acid_ratio"] = np.log10(df["molar_base_acid_ratio"])
    df["ph_henderson_hasselbalch"] = hh_model.predict_array(
        df["acid_flow"],
        df["acetate_flow"],
        df["water_flow"],
    )
    df.loc[~valid, "ph_henderson_hasselbalch"] = np.nan

    for column in [
        "acid_analytical_mol_l",
        "acetate_analytical_mol_l",
        "total_buffer_mol_l",
        "sodium_mol_l",
    ]:
        df[column] = np.nan

    for row in df.loc[valid].itertuples():
        concentrations = equilibrium_model.mixed_concentrations(
            row.acid_flow,
            row.acetate_flow,
            row.water_flow,
        )
        df.loc[row.Index, "acid_analytical_mol_l"] = concentrations[
            "acid_analytical_mol_l"
        ]
        df.loc[row.Index, "acetate_analytical_mol_l"] = concentrations[
            "acetate_analytical_mol_l"
        ]
        df.loc[row.Index, "total_buffer_mol_l"] = concentrations[
            "total_buffer_mol_l"
        ]
        df.loc[row.Index, "sodium_mol_l"] = concentrations["sodium_mol_l"]

    df["ph_equilibrium_charge_balance"] = equilibrium_model.predict_array(
        df["acid_flow"],
        df["acetate_flow"],
        df["water_flow"],
    )
    df.loc[~valid, "ph_equilibrium_charge_balance"] = np.nan
    df["water_fraction"] = df["water_flow"] / df["total_flow"]
    df["buffer_flow_fraction"] = (
        df["acid_flow"] + df["acetate_flow"]
    ) / df["total_flow"]
    df["log10_total_buffer_mol_l"] = np.log10(df["total_buffer_mol_l"])
    df["measured_minus_hh_raw"] = df["ph_measured"] - df["ph_henderson_hasselbalch"]
    df["measured_minus_equilibrium_raw"] = (
        df["ph_measured"] - df["ph_equilibrium_charge_balance"]
    )
    return df


def add_split(df: pd.DataFrame, train_fraction: float = 0.70) -> tuple[pd.DataFrame, pd.DataFrame]:
    return add_trial_split(df, train_fraction=train_fraction)


def fit_static_chemistry_models(
    df: pd.DataFrame,
    fit_mask: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit constrained static chemistry calibrations on train rows only."""
    enriched = df.copy()
    if fit_mask is None:
        fit_mask = enriched["valid_for_model"] & enriched["split"].eq("train")
    else:
        fit_mask = fit_mask.reindex(enriched.index).fillna(False)

    enriched["prediction_hh_raw"] = enriched["ph_henderson_hasselbalch"]
    enriched["prediction_equilibrium_raw"] = enriched["ph_equilibrium_charge_balance"]

    parameter_rows = []

    bias = fit_offset_model(
        enriched,
        offset_col="ph_equilibrium_charge_balance",
        fit_mask=fit_mask,
        parameter_name="bias",
    )
    enriched["prediction_equilibrium_bias"] = (
        enriched["ph_equilibrium_charge_balance"] + bias["bias"]
    )
    parameter_rows.append({
        "model_stage": "equilibrium_bias",
        "model_label": "Equilibrium + bias",
        "parameter": "bias",
        "value": bias["bias"],
        "feature": "ph_equilibrium_charge_balance",
        "n_fit": bias["n_fit"],
        "fit_method": bias["fit_method"],
        "condition_number": np.nan,
    })

    effective_pka = fit_offset_model(
        enriched,
        offset_col="log10_molar_base_acid_ratio",
        fit_mask=fit_mask,
        parameter_name="effective_pKa",
    )
    enriched["prediction_hh_effective_pka"] = (
        effective_pka["effective_pKa"] + enriched["log10_molar_base_acid_ratio"]
    )
    parameter_rows.append({
        "model_stage": "hh_effective_pka",
        "model_label": "HH effective pKa",
        "parameter": "effective_pKa",
        "value": effective_pka["effective_pKa"],
        "feature": "log10_molar_base_acid_ratio",
        "n_fit": effective_pka["n_fit"],
        "fit_method": effective_pka["fit_method"],
        "condition_number": np.nan,
    })

    hh_affine = fit_linear_model(
        enriched,
        feature_cols=["ph_henderson_hasselbalch"],
        fit_mask=fit_mask,
        model_stage="hh_affine",
        model_label="HH affine",
    )
    enriched["prediction_hh_affine"] = predict_linear_model(
        enriched,
        ["ph_henderson_hasselbalch"],
        hh_affine,
    )
    parameter_rows.extend(parameter_rows_from_linear_fit(hh_affine))

    eq_affine = fit_linear_model(
        enriched,
        feature_cols=["ph_equilibrium_charge_balance"],
        fit_mask=fit_mask,
        model_stage="equilibrium_affine",
        model_label="Equilibrium affine",
    )
    enriched["prediction_equilibrium_affine"] = predict_linear_model(
        enriched,
        ["ph_equilibrium_charge_balance"],
        eq_affine,
    )
    parameter_rows.extend(parameter_rows_from_linear_fit(eq_affine))

    for stage in STATIC_MODEL_STAGES:
        residual_col = f"residual_{stage.key}"
        enriched[residual_col] = enriched["ph_measured"] - enriched[stage.prediction_col]
        enriched.loc[~enriched["valid_for_model"], stage.prediction_col] = np.nan
        enriched.loc[~enriched["valid_for_model"], residual_col] = np.nan

    return enriched, pd.DataFrame(parameter_rows)


def fit_offset_model(
    df: pd.DataFrame,
    offset_col: str,
    fit_mask: pd.Series,
    parameter_name: str,
) -> dict[str, float | int | str]:
    mask = fit_mask & df[offset_col].notna() & df["ph_measured"].notna()
    if mask.sum() == 0:
        value = np.nan
    else:
        value = float((df.loc[mask, "ph_measured"] - df.loc[mask, offset_col]).mean())
    return {
        parameter_name: value,
        "n_fit": int(mask.sum()),
        "fit_method": "train_mean_offset",
    }


def fit_linear_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    fit_mask: pd.Series,
    model_stage: str,
    model_label: str,
) -> dict:
    mask = fit_mask & df["ph_measured"].notna()
    for column in feature_cols:
        mask = mask & df[column].notna()

    x = df.loc[mask, feature_cols].to_numpy(dtype=float)
    y = df.loc[mask, "ph_measured"].to_numpy(dtype=float)
    if len(y) < len(feature_cols) + 1:
        coefficients = np.full(len(feature_cols) + 1, np.nan, dtype=float)
        condition_number = np.nan
    else:
        design = np.column_stack([np.ones(len(x)), x])
        coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
        condition_number = float(np.linalg.cond(design))

    return {
        "model_stage": model_stage,
        "model_label": model_label,
        "feature_cols": feature_cols,
        "coefficients": coefficients,
        "condition_number": condition_number,
        "n_fit": int(mask.sum()),
        "fit_method": "ordinary_least_squares",
    }


def predict_linear_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    fit: dict,
) -> pd.Series:
    coefficients = np.asarray(fit["coefficients"], dtype=float)
    prediction = pd.Series(np.nan, index=df.index, dtype=float)
    if np.any(~np.isfinite(coefficients)):
        return prediction
    mask = df[feature_cols].notna().all(axis=1)
    x = df.loc[mask, feature_cols].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    prediction.loc[mask] = design @ coefficients
    return prediction


def parameter_rows_from_linear_fit(fit: dict) -> list[dict]:
    rows = [{
        "model_stage": fit["model_stage"],
        "model_label": fit["model_label"],
        "parameter": "intercept",
        "value": float(fit["coefficients"][0]),
        "feature": "intercept",
        "n_fit": int(fit["n_fit"]),
        "fit_method": fit["fit_method"],
        "condition_number": fit["condition_number"],
    }]
    for feature, value in zip(fit["feature_cols"], fit["coefficients"][1:]):
        rows.append({
            "model_stage": fit["model_stage"],
            "model_label": fit["model_label"],
            "parameter": f"coefficient_{feature}",
            "value": float(value),
            "feature": feature,
            "n_fit": int(fit["n_fit"]),
            "fit_method": fit["fit_method"],
            "condition_number": fit["condition_number"],
        })
    return rows


def make_model_metrics(
    df: pd.DataFrame,
    stages: list[ModelStage],
    mask: pd.Series | None = None,
) -> pd.DataFrame:
    if mask is None:
        base_mask = df["valid_for_model"]
    else:
        base_mask = mask.reindex(df.index).fillna(False)

    rows = []
    for stage in stages:
        residual_col = f"residual_{stage.key}"
        for split in ["train", "test"]:
            split_mask = (
                base_mask
                & df["split"].eq(split)
                & df[stage.prediction_col].notna()
                & df["ph_measured"].notna()
            )
            residual = df.loc[split_mask, "ph_measured"] - df.loc[
                split_mask,
                stage.prediction_col,
            ]
            rows.append({
                "model_stage": stage.key,
                "model_label": stage.label,
                "split": split,
                "n": int(split_mask.sum()),
                **metric_values(
                    df.loc[split_mask, "ph_measured"],
                    df.loc[split_mask, stage.prediction_col],
                    residual,
                ),
            })
        all_mask = base_mask & df[stage.prediction_col].notna() & df["ph_measured"].notna()
        residual = df.loc[all_mask, "ph_measured"] - df.loc[all_mask, stage.prediction_col]
        rows.append({
            "model_stage": stage.key,
            "model_label": stage.label,
            "split": "all",
            "n": int(all_mask.sum()),
            **metric_values(
                df.loc[all_mask, "ph_measured"],
                df.loc[all_mask, stage.prediction_col],
                residual,
            ),
        })
        if residual_col not in df.columns:
            continue
    return pd.DataFrame(rows)


def select_static_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
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
        "water_fraction",
        "valid_for_model",
        "valid_for_model_before_flat_trial_filter",
        "uninformative_flat_ph_trial",
        "trial_ph_range",
        "trial_log10_flow_ratio_range",
        "trial_total_flow_range",
        "flow_ratio_acetate_acid",
        "log10_molar_base_acid_ratio",
        "total_buffer_mol_l",
        "ph_henderson_hasselbalch",
        "ph_equilibrium_charge_balance",
    ]
    for stage in STATIC_MODEL_STAGES:
        columns.append(stage.prediction_col)
        columns.append(f"residual_{stage.key}")
    extra = [column for column in df.columns if column.startswith("is_settled_")]
    return df[columns + extra].copy()


def add_settled_flags(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["delta_log10_ratio"] = (
        enriched.groupby("trial_id")["log10_molar_base_acid_ratio"].diff().abs()
    )
    enriched["delta_total_flow"] = (
        enriched.groupby("trial_id")["total_flow"].diff().abs()
    )
    flow_cols = ["acid_flow", "acetate_flow", "water_flow"]
    enriched["delta_max_stream_flow"] = (
        enriched.groupby("trial_id")[flow_cols].diff().abs().max(axis=1)
    )
    rules = settled_rules()
    for rule_name, ratio_threshold, total_threshold in rules:
        enriched[f"is_settled_{rule_name}"] = (
            enriched["valid_for_model"]
            & enriched["delta_log10_ratio"].le(ratio_threshold)
            & enriched["delta_total_flow"].le(total_threshold)
        )
    return enriched


def settled_rules() -> list[tuple[str, float, float]]:
    return [
        ("strict", 0.10, 1.0),
        ("primary", 0.25, 2.0),
        ("relaxed", 0.50, 5.0),
    ]


def make_settled_rule_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rule_name, ratio_threshold, total_threshold in settled_rules():
        rule_col = f"is_settled_{rule_name}"
        for split in ["train", "test", "all"]:
            if split == "all":
                mask = df[rule_col]
            else:
                mask = df[rule_col] & df["split"].eq(split)
            rows.append({
                "rule": rule_name,
                "split": split,
                "delta_log10_ratio_max": ratio_threshold,
                "delta_total_flow_max_ml_min": total_threshold,
                "n": int(mask.sum()),
                "fraction_of_valid": float(mask.sum() / max(df["valid_for_model"].sum(), 1)),
            })
    return pd.DataFrame(rows)


def make_residual_feature_correlations(
    df: pd.DataFrame,
    residual_col: str = "residual_equilibrium_raw",
) -> pd.DataFrame:
    feature_cols = diagnostic_feature_columns()
    rows = []
    valid = df["valid_for_model"] & df[residual_col].notna()
    for feature in feature_cols:
        feature_valid = valid & df[feature].notna()
        rows.append({
            "residual": residual_col,
            "feature": feature,
            "n": int(feature_valid.sum()),
            "correlation": float(df.loc[feature_valid, residual_col].corr(
                df.loc[feature_valid, feature]
            ))
            if feature_valid.sum() > 1
            else np.nan,
        })
    return pd.DataFrame(rows)


def diagnostic_feature_columns() -> list[str]:
    return [
        "total_flow",
        "water_fraction",
        "total_buffer_mol_l",
        "log10_molar_base_acid_ratio",
        "elapsed_h",
        "acid_flow",
        "acetate_flow",
        "water_flow",
    ]


def make_binned_residual_summary(
    df: pd.DataFrame,
    residual_col: str = "residual_equilibrium_raw",
    bins: int = 6,
) -> pd.DataFrame:
    rows = []
    valid = df["valid_for_model"] & df[residual_col].notna()
    for feature in diagnostic_feature_columns():
        feature_valid = valid & df[feature].notna()
        if feature_valid.sum() < bins:
            continue
        try:
            groups = pd.qcut(
                df.loc[feature_valid, feature],
                q=bins,
                duplicates="drop",
            )
        except ValueError:
            continue
        grouped = df.loc[feature_valid].groupby(groups, observed=True)
        for interval, group in grouped:
            residual = group[residual_col]
            rows.append({
                "feature": feature,
                "bin": str(interval),
                "n": int(len(group)),
                "feature_min": float(group[feature].min()),
                "feature_max": float(group[feature].max()),
                "mean_error": safe_mean(residual),
                "mae": safe_mae(residual),
                "rmse": rmse(residual),
            })
    return pd.DataFrame(rows)


def make_group_residual_summary(
    df: pd.DataFrame,
    group_col: str,
    residual_col: str = "residual_equilibrium_raw",
) -> pd.DataFrame:
    rows = []
    for group_value, group in df.groupby(group_col, sort=True):
        valid = group["valid_for_model"] & group[residual_col].notna()
        residual = group.loc[valid, residual_col]
        rows.append({
            group_col: group_value,
            "n": int(valid.sum()),
            "mean_error": safe_mean(residual),
            "mae": safe_mae(residual),
            "rmse": rmse(residual),
            "median_total_flow": safe_median(group.loc[valid, "total_flow"]),
            "median_water_fraction": safe_median(group.loc[valid, "water_fraction"]),
            "median_total_buffer_mol_l": safe_median(group.loc[valid, "total_buffer_mol_l"]),
        })
    return pd.DataFrame(rows)


def fit_activity_dilution_models(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[ModelStage]]:
    enriched = df.copy()
    train = enriched["valid_for_model"] & enriched["split"].eq("train")
    c_ref = float(enriched.loc[train, "total_buffer_mol_l"].median())
    total_ref = float(enriched.loc[train, "total_flow"].median())
    enriched["log10_total_buffer_relative"] = np.log10(
        enriched["total_buffer_mol_l"] / c_ref
    )
    enriched["total_flow_centered"] = enriched["total_flow"] - total_ref

    specs = [
        ("eq_bias", "Equilibrium + bias", [], "ph_equilibrium_charge_balance"),
        ("eq_affine", "Equilibrium affine", ["ph_equilibrium_charge_balance"], None),
        (
            "eq_affine_buffer",
            "Equilibrium affine + buffer strength",
            ["ph_equilibrium_charge_balance", "log10_total_buffer_relative"],
            None,
        ),
        (
            "eq_affine_water",
            "Equilibrium affine + water fraction",
            ["ph_equilibrium_charge_balance", "water_fraction"],
            None,
        ),
        (
            "eq_affine_total_flow",
            "Equilibrium affine + total flow",
            ["ph_equilibrium_charge_balance", "total_flow_centered"],
            None,
        ),
        (
            "eq_affine_empirical_physical",
            "Equilibrium affine + buffer/water/flow",
            [
                "ph_equilibrium_charge_balance",
                "log10_total_buffer_relative",
                "water_fraction",
                "total_flow_centered",
            ],
            None,
        ),
    ]

    parameter_rows = [
        {
            "model_stage": "reference",
            "model_label": "Reference constants",
            "parameter": "total_buffer_reference_mol_l",
            "value": c_ref,
            "feature": "total_buffer_mol_l",
            "n_fit": int(train.sum()),
            "fit_method": "train_median",
            "condition_number": np.nan,
        },
        {
            "model_stage": "reference",
            "model_label": "Reference constants",
            "parameter": "total_flow_reference_ml_min",
            "value": total_ref,
            "feature": "total_flow",
            "n_fit": int(train.sum()),
            "fit_method": "train_median",
            "condition_number": np.nan,
        },
    ]
    stages = []
    for key, label, features, offset_col in specs:
        if offset_col is not None:
            fit = fit_offset_model(enriched, offset_col, train, "bias")
            enriched[f"prediction_{key}"] = enriched[offset_col] + fit["bias"]
            parameter_rows.append({
                "model_stage": key,
                "model_label": label,
                "parameter": "bias",
                "value": fit["bias"],
                "feature": "offset",
                "n_fit": fit["n_fit"],
                "fit_method": fit["fit_method"],
                "condition_number": np.nan,
            })
        else:
            fit = fit_linear_model(enriched, features, train, key, label)
            enriched[f"prediction_{key}"] = predict_linear_model(enriched, features, fit)
            parameter_rows.extend(parameter_rows_from_linear_fit(fit))

        enriched[f"residual_{key}"] = enriched["ph_measured"] - enriched[f"prediction_{key}"]
        stages.append(ModelStage(key, label, f"prediction_{key}"))

    return enriched, pd.DataFrame(parameter_rows), stages


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
        "mean_error": safe_mean(residual),
        "mae": safe_mae(residual),
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


def safe_mean(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.mean()) if len(values) else np.nan


def safe_median(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.median()) if len(values) else np.nan


def safe_mae(values: pd.Series | np.ndarray) -> float:
    values = pd.Series(values).dropna()
    return float(values.abs().mean()) if len(values) else np.nan
