from __future__ import annotations

import numpy as np
import pandas as pd

from helpers.henderson_hasselbalch_prepared import (
    add_henderson_hasselbalch_prepared_predictions,
)
from simulation.henderson_hasselbalch_model import HendersonHasselbalchModel


RAW_FLOW_COLUMNS = (
    "observation.biosmb-flows[0]",
    "observation.biosmb-flows[1]",
    "observation.biosmb-flows[2]",
)
TREATED_FLOW_COLUMNS = ("flow-acid", "flow-sodium", "flow-water")

SELECTED_CONTEXT_COLUMNS = [
    "target_ph",
    "episode_number",
    "step_number",
    "time",
    "time_min_diff",
    "utc_time",
    "observation.biosmb-sensors.PH_1",
    "observation.biosmb-sensors.PH_2",
    "pH-sensor",
    "observation.biosmb-sensors.COND_1",
    "observation.biosmb-sensors.COND_2",
    "observation.biosmb-sensors.COND_3",
    "observation.biosmb-sensors.COND_4",
    "observation.biosmb-flows[0]",
    "observation.biosmb-flows[1]",
    "observation.biosmb-flows[2]",
    "flow-acid",
    "flow-sodium",
    "flow-water",
    "observation.mfcs-mass.acid-mass-grams",
    "observation.mfcs-mass.sodium-mass-grams",
    "observation.mfcs-mass.water-mass-grams",
]


def make_residual_shift_diagnostic(
    raw_data: pd.DataFrame,
    prepared_data: pd.DataFrame,
    model: HendersonHasselbalchModel,
    min_changepoint_samples: int = 30,
    local_window_radius: int = 60,
) -> dict[str, pd.DataFrame]:
    comparison = add_henderson_hasselbalch_prepared_predictions(prepared_data, model)
    changepoint = find_best_mean_residual_changepoint(
        comparison["ph_minus_ph_predicted"],
        min_changepoint_samples,
    )
    phase2_start = int(
        comparison.loc[
            comparison["sampling_phase_id"].gt(1),
            "sample_index",
        ].min()
    )
    segment_slices = make_segment_slices(len(comparison), changepoint, phase2_start)

    return {
        "comparison": comparison,
        "changepoint": make_changepoint_table(comparison, changepoint, phase2_start),
        "segment_metrics": make_segment_metrics(comparison, segment_slices),
        "flow_source_metrics": make_flow_source_metrics(
            raw_data,
            model,
            segment_slices,
        ),
        "local_context": make_local_context_table(
            raw_data,
            comparison,
            changepoint,
            radius=40,
        ),
        "column_shift_ranking": make_column_shift_ranking(
            raw_data,
            changepoint,
            radius=local_window_radius,
        ),
        "selected_column_medians": make_selected_column_medians(
            raw_data,
            comparison,
            segment_slices,
        ),
        "long_gap_events": make_long_gap_events(raw_data, comparison),
    }


def find_best_mean_residual_changepoint(
    residual: pd.Series,
    min_samples: int = 30,
) -> int:
    best_sse = np.inf
    best_index = int(min_samples)
    for index in range(min_samples, len(residual) - min_samples):
        left = residual.iloc[:index].dropna()
        right = residual.iloc[index:].dropna()
        if len(left) < min_samples or len(right) < min_samples:
            continue
        sse = float(((left - left.mean()) ** 2).sum())
        sse += float(((right - right.mean()) ** 2).sum())
        if sse < best_sse:
            best_sse = sse
            best_index = int(index)
    return best_index


def make_segment_slices(
    row_count: int,
    changepoint: int,
    phase2_start: int,
) -> dict[str, slice]:
    return {
        "pre_jump": slice(0, changepoint),
        "post_jump_same_sampling": slice(changepoint, phase2_start),
        "phase2": slice(phase2_start, row_count),
    }


def make_changepoint_table(
    comparison: pd.DataFrame,
    changepoint: int,
    phase2_start: int,
) -> pd.DataFrame:
    before = comparison.iloc[:changepoint]["ph_minus_ph_predicted"].dropna()
    after = comparison.iloc[changepoint:]["ph_minus_ph_predicted"].dropna()
    row = comparison.iloc[changepoint]
    return pd.DataFrame(
        [
            {
                "changepoint_sample_index": int(changepoint),
                "phase2_start_sample_index": int(phase2_start),
                "changepoint_delta_t_min": float(row["delta_t_min"]),
                "changepoint_sampling_phase": str(row["sampling_phase"]),
                "mean_residual_before": float(before.mean()),
                "mean_residual_after": float(after.mean()),
                "residual_step_change": float(after.mean() - before.mean()),
                "ph_measured_at_changepoint": float(row["ph_measured"]),
                "ph_predicted_at_changepoint": float(row["ph_predicted_hh"]),
                "residual_at_changepoint": float(row["ph_minus_ph_predicted"]),
                "molar_base_acid_ratio_at_changepoint": float(
                    row["molar_base_acid_ratio"]
                ),
            }
        ]
    )


def make_segment_metrics(
    comparison: pd.DataFrame,
    segment_slices: dict[str, slice],
) -> pd.DataFrame:
    rows = []
    for segment_name, segment_slice in segment_slices.items():
        group = comparison.iloc[segment_slice]
        residual = group["ph_minus_ph_predicted"].dropna()
        effective_pka = (
            group["ph_measured"] - group["log10_molar_base_acid_ratio"]
        ).dropna()
        normal_delta_t = group.loc[~group["long_time_gap"], "delta_t_min"].dropna()
        rows.append(
            {
                "segment": segment_name,
                "start_sample_index": int(group["sample_index"].iloc[0]),
                "end_sample_index": int(group["sample_index"].iloc[-1]),
                "n": int(len(group)),
                "median_delta_t_min": safe_median(normal_delta_t),
                "long_gap_count": int(group["long_time_gap"].sum()),
                "mean_residual": safe_mean(residual),
                "median_residual": safe_median(residual),
                "mae": safe_mae(residual),
                "rmse": rmse(residual),
                "max_abs_error": safe_max_abs(residual),
                "correlation_measured_predicted": safe_corr(
                    group["ph_measured"],
                    group["ph_predicted_hh"],
                ),
                "mean_effective_pka": safe_mean(effective_pka),
                "median_effective_pka": safe_median(effective_pka),
                "required_base_acid_stock_factor": float(
                    10.0 ** safe_mean(residual)
                ),
                "median_molar_base_acid_ratio": safe_median(
                    group["molar_base_acid_ratio"]
                ),
            }
        )
    return pd.DataFrame(rows)


def make_flow_source_metrics(
    raw_data: pd.DataFrame,
    model: HendersonHasselbalchModel,
    segment_slices: dict[str, slice],
) -> pd.DataFrame:
    ph = pd.to_numeric(raw_data["pH-sensor"], errors="coerce")
    rows = []
    for source_name, columns in {
        "treated_last_columns": TREATED_FLOW_COLUMNS,
        "raw_observation_flows": RAW_FLOW_COLUMNS,
    }.items():
        acid = pd.to_numeric(raw_data[columns[0]], errors="coerce")
        base = pd.to_numeric(raw_data[columns[1]], errors="coerce")
        ratio = (model.base_stock_mol_l * base) / (model.acid_stock_mol_l * acid)
        prediction = model.pKa + np.log10(ratio)
        residual = ph - prediction
        effective_pka = ph - np.log10(ratio)
        for segment_name, segment_slice in segment_slices.items():
            segment_residual = residual.iloc[segment_slice].dropna()
            segment_pka = effective_pka.iloc[segment_slice].dropna()
            rows.append(
                {
                    "flow_source": source_name,
                    "segment": segment_name,
                    "n": int(len(segment_residual)),
                    "mean_residual": safe_mean(segment_residual),
                    "median_residual": safe_median(segment_residual),
                    "mae": safe_mae(segment_residual),
                    "rmse": rmse(segment_residual),
                    "mean_effective_pka": safe_mean(segment_pka),
                    "median_effective_pka": safe_median(segment_pka),
                    "required_base_acid_stock_factor": float(
                        10.0 ** safe_mean(segment_residual)
                    ),
                    "correlation_measured_predicted": safe_corr(
                        ph.iloc[segment_slice],
                        prediction.iloc[segment_slice],
                    ),
                }
            )
    return pd.DataFrame(rows)


def make_local_context_table(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
    changepoint: int,
    radius: int = 40,
) -> pd.DataFrame:
    start = max(0, changepoint - radius)
    end = min(len(raw_data), changepoint + radius + 1)
    columns = [col for col in SELECTED_CONTEXT_COLUMNS if col in raw_data.columns]
    local = raw_data.loc[start : end - 1, columns].copy()
    local.insert(0, "sample_index", local.index)
    add_columns = [
        "delta_t_min",
        "sampling_phase",
        "ph_predicted_hh",
        "ph_minus_ph_predicted",
        "molar_base_acid_ratio",
    ]
    for column in add_columns:
        local[column] = comparison.loc[start : end - 1, column].to_numpy()
    return local


def make_column_shift_ranking(
    raw_data: pd.DataFrame,
    changepoint: int,
    radius: int = 60,
) -> pd.DataFrame:
    start = max(0, changepoint - radius)
    end = min(len(raw_data), changepoint + radius)
    left = raw_data.iloc[start:changepoint]
    right = raw_data.iloc[changepoint:end]
    rows = []
    for column in raw_data.columns:
        left_values = pd.to_numeric(left[column], errors="coerce")
        right_values = pd.to_numeric(right[column], errors="coerce")
        all_values = pd.to_numeric(raw_data[column], errors="coerce")
        if left_values.notna().sum() < 10 or right_values.notna().sum() < 10:
            continue
        global_std = all_values.std()
        if pd.isna(global_std) or global_std == 0.0:
            continue
        left_mean = float(left_values.mean())
        right_mean = float(right_values.mean())
        rows.append(
            {
                "column": column,
                "left_mean": left_mean,
                "right_mean": right_mean,
                "delta_mean": right_mean - left_mean,
                "abs_delta_over_global_std": abs(right_mean - left_mean)
                / float(global_std),
            }
        )
    ranking = pd.DataFrame(rows)
    return ranking.sort_values("abs_delta_over_global_std", ascending=False)


def make_selected_column_medians(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
    segment_slices: dict[str, slice],
) -> pd.DataFrame:
    columns = [
        "target_ph",
        "time_min_diff",
        "observation.biosmb-sensors.PH_1",
        "observation.biosmb-sensors.PH_2",
        "observation.biosmb-sensors.COND_3",
        "observation.biosmb-sensors.COND_4",
        "observation.biosmb-sensors.UV_3B",
        "flow-acid",
        "flow-sodium",
        "flow-water",
        "observation.mfcs-mass.acid-mass-grams",
        "observation.mfcs-mass.sodium-mass-grams",
        "observation.mfcs-mass.water-mass-grams",
    ]
    rows = []
    for segment_name, segment_slice in segment_slices.items():
        group = raw_data.iloc[segment_slice]
        comparison_group = comparison.iloc[segment_slice]
        for column in columns:
            if column not in raw_data.columns:
                continue
            values = pd.to_numeric(group[column], errors="coerce")
            rows.append(
                {
                    "segment": segment_name,
                    "column": column,
                    "median": safe_median(values),
                    "mean": safe_mean(values),
                    "min": float(values.min()),
                    "max": float(values.max()),
                }
            )
        residual = comparison_group["ph_minus_ph_predicted"]
        rows.append(
            {
                "segment": segment_name,
                "column": "ph_minus_ph_predicted",
                "median": safe_median(residual),
                "mean": safe_mean(residual),
                "min": float(residual.min()),
                "max": float(residual.max()),
            }
        )
    return pd.DataFrame(rows)


def make_long_gap_events(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    gap_indices = comparison.index[comparison["long_time_gap"]].tolist()
    for index in gap_indices:
        previous = max(0, index - 1)
        rows.append(
            {
                "gap_sample_index": int(index),
                "utc_time_before": str(raw_data.loc[previous, "utc_time"]),
                "utc_time_after": str(raw_data.loc[index, "utc_time"]),
                "delta_t_min": float(comparison.loc[index, "delta_t_min"]),
                "episode_before": nullable_int(raw_data.loc[previous, "episode_number"]),
                "episode_after": nullable_int(raw_data.loc[index, "episode_number"]),
                "step_before": nullable_int(raw_data.loc[previous, "step_number"]),
                "step_after": nullable_int(raw_data.loc[index, "step_number"]),
                "ph1_before": numeric_value(
                    raw_data.loc[previous, "observation.biosmb-sensors.PH_1"]
                ),
                "ph1_after": numeric_value(
                    raw_data.loc[index, "observation.biosmb-sensors.PH_1"]
                ),
                "ph2_before": numeric_value(raw_data.loc[previous, "pH-sensor"]),
                "ph2_after": numeric_value(raw_data.loc[index, "pH-sensor"]),
                "residual_before": float(
                    comparison.loc[previous, "ph_minus_ph_predicted"]
                ),
                "residual_after": float(comparison.loc[index, "ph_minus_ph_predicted"]),
                "acid_mass_before": numeric_value(
                    raw_data.loc[
                        previous,
                        "observation.mfcs-mass.acid-mass-grams",
                    ]
                ),
                "acid_mass_after": numeric_value(
                    raw_data.loc[index, "observation.mfcs-mass.acid-mass-grams"]
                ),
                "sodium_mass_before": numeric_value(
                    raw_data.loc[
                        previous,
                        "observation.mfcs-mass.sodium-mass-grams",
                    ]
                ),
                "sodium_mass_after": numeric_value(
                    raw_data.loc[index, "observation.mfcs-mass.sodium-mass-grams"]
                ),
                "water_mass_before": numeric_value(
                    raw_data.loc[
                        previous,
                        "observation.mfcs-mass.water-mass-grams",
                    ]
                ),
                "water_mass_after": numeric_value(
                    raw_data.loc[index, "observation.mfcs-mass.water-mass-grams"]
                ),
            }
        )
    return pd.DataFrame(rows)


def numeric_value(value) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0])


def nullable_int(value) -> int | float:
    if pd.isna(value):
        return np.nan
    return int(value)


def rmse(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    if len(series) == 0:
        return np.nan
    return float(np.sqrt(np.mean(np.square(series.to_numpy(dtype=float)))))


def safe_mean(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values).dropna()
    return float(series.mean()) if len(series) else np.nan


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
