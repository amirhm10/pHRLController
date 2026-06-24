from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
import pandas as pd


DEFAULT_DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv")
SAMPLING_PHASE_SPLIT_DT_MIN = 1.7
LONG_GAP_DT_MIN = 30.0

KNOWN_FEATURE_RENAMES = {
    "flow-acid": "acid_flow",
    "flow-sodium": "acetate_flow",
    "flow-water": "water_flow",
    "pH-sensor": "ph_measured",
}


@dataclass(frozen=True)
class TimeFeatureSelection:
    """Select the timestep column and the final feature columns from a raw CSV."""

    time_column: str = "time"
    feature_count: int = 4


def load_raw_time_feature_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path)
    df.attrs["source_path"] = str(path)
    df.attrs["source_rows"] = int(df.shape[0])
    df.attrs["source_columns"] = int(df.shape[1])
    df.attrs["source_missing_values"] = int(df.isna().sum().sum())
    return df


def select_time_and_last_features(
    raw_data: pd.DataFrame,
    selection: TimeFeatureSelection | None = None,
) -> pd.DataFrame:
    selection = selection or TimeFeatureSelection()
    if selection.time_column not in raw_data.columns:
        raise KeyError(f"Missing timestep column: {selection.time_column}")
    if raw_data.shape[1] < selection.feature_count:
        raise ValueError(
            f"Need at least {selection.feature_count} columns to select final features."
        )

    feature_columns = tuple(raw_data.columns[-selection.feature_count :])
    selected_columns = (selection.time_column, *feature_columns)
    selected = raw_data.loc[:, selected_columns].copy()
    selected.attrs.update(raw_data.attrs)
    selected.attrs["time_column"] = selection.time_column
    selected.attrs["feature_columns"] = feature_columns
    selected.attrs["selected_columns"] = selected_columns
    return selected


def prepare_time_feature_data(selected_data: pd.DataFrame) -> pd.DataFrame:
    time_column = selected_data.attrs.get("time_column", selected_data.columns[0])
    feature_columns = tuple(selected_data.attrs.get("feature_columns", selected_data.columns[1:]))

    prepared = pd.DataFrame(index=selected_data.index)
    prepared["sample_index"] = np.arange(len(selected_data), dtype=int)
    prepared["time"] = pd.to_numeric(selected_data[time_column], errors="coerce")
    prepared["elapsed_min"] = make_elapsed_minutes(selected_data[time_column])
    prepared["delta_t_min"] = prepared["elapsed_min"].diff()

    mapping_rows = []
    used_names: set[str] = set()
    for source_column in feature_columns:
        prepared_name = standardize_feature_name(source_column)
        prepared_name = make_unique_name(prepared_name, used_names)
        used_names.add(prepared_name)
        prepared[prepared_name] = pd.to_numeric(selected_data[source_column], errors="coerce")
        mapping_rows.append(
            {
                "source_column": source_column,
                "prepared_column": prepared_name,
            }
        )

    add_basic_derived_columns(prepared)
    add_sampling_phase_columns(prepared)
    prepared.attrs.update(selected_data.attrs)
    prepared.attrs["column_mapping"] = mapping_rows
    prepared.attrs["analysis_columns"] = int(prepared.shape[1])
    return prepared


def make_elapsed_minutes(time_values: pd.Series) -> pd.Series:
    numeric_time = pd.to_numeric(time_values, errors="coerce")
    if numeric_time.notna().any():
        first_time = numeric_time.dropna().iloc[0]
        elapsed = numeric_time - first_time
        if first_time > 20000.0:
            elapsed = elapsed * 24.0 * 60.0
        return elapsed

    datetimes = pd.to_datetime(time_values, utc=True, errors="coerce")
    if datetimes.notna().any():
        first_time = datetimes.dropna().iloc[0]
        return (datetimes - first_time).dt.total_seconds() / 60.0

    return pd.Series(np.nan, index=time_values.index, dtype=float)


def standardize_feature_name(source_column: str) -> str:
    if source_column in KNOWN_FEATURE_RENAMES:
        return KNOWN_FEATURE_RENAMES[source_column]

    name = re.sub(r"[^0-9A-Za-z]+", "_", source_column).strip("_").lower()
    return name or "feature"


def make_unique_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        return name

    index = 2
    while f"{name}_{index}" in used_names:
        index += 1
    return f"{name}_{index}"


def add_basic_derived_columns(prepared: pd.DataFrame) -> None:
    required_flows = {"acid_flow", "acetate_flow", "water_flow"}
    if required_flows.issubset(prepared.columns):
        prepared["total_flow"] = (
            prepared["acid_flow"] + prepared["acetate_flow"] + prepared["water_flow"]
        )
        valid_ratio = prepared["acid_flow"].gt(0.0) & prepared["acetate_flow"].gt(0.0)
        prepared["acetate_acid_ratio"] = np.nan
        prepared.loc[valid_ratio, "acetate_acid_ratio"] = (
            prepared.loc[valid_ratio, "acetate_flow"]
            / prepared.loc[valid_ratio, "acid_flow"]
        )
        prepared["log10_acetate_acid_ratio"] = np.log10(
            prepared["acetate_acid_ratio"]
        )


def add_sampling_phase_columns(
    prepared: pd.DataFrame,
    split_dt_min: float = SAMPLING_PHASE_SPLIT_DT_MIN,
    long_gap_dt_min: float = LONG_GAP_DT_MIN,
) -> None:
    """Label sequential sampling phases from the original timestamp spacing."""
    delta_t = pd.to_numeric(prepared["delta_t_min"], errors="coerce")
    normal_dt = delta_t.gt(0.0) & delta_t.le(long_gap_dt_min)

    interval_regime = pd.Series(pd.NA, index=prepared.index, dtype="object")
    interval_regime.loc[normal_dt & delta_t.le(split_dt_min)] = "fast_sampling"
    interval_regime.loc[normal_dt & delta_t.gt(split_dt_min)] = "slow_sampling"

    sample_regime = interval_regime.bfill().ffill()
    if sample_regime.isna().all():
        sample_regime = pd.Series("unknown_sampling", index=prepared.index)

    phase_change = sample_regime.ne(sample_regime.shift()).fillna(True)
    phase_id = phase_change.cumsum().astype(int)

    prepared["long_time_gap"] = delta_t.gt(long_gap_dt_min).fillna(False)
    prepared["sampling_regime"] = sample_regime.astype(str)
    prepared["sampling_phase_id"] = phase_id
    prepared["sampling_phase"] = [
        make_sampling_phase_label(pid, regime)
        for pid, regime in zip(phase_id, prepared["sampling_regime"])
    ]
    prepared["sampling_phase_transition"] = phase_change


def make_sampling_phase_label(phase_id: int, regime: str) -> str:
    regime_labels = {
        "slow_sampling": "slower sampling",
        "fast_sampling": "faster sampling",
        "unknown_sampling": "unknown sampling",
    }
    return f"Phase {phase_id}: {regime_labels.get(regime, regime.replace('_', ' '))}"


def make_preparation_overview(
    raw_data: pd.DataFrame,
    selected_data: pd.DataFrame,
    prepared_data: pd.DataFrame,
) -> pd.DataFrame:
    elapsed = pd.to_numeric(prepared_data["elapsed_min"], errors="coerce")
    overview = {
        "source_path": raw_data.attrs.get("source_path", ""),
        "raw_rows": int(raw_data.shape[0]),
        "raw_columns": int(raw_data.shape[1]),
        "selected_columns": int(selected_data.shape[1]),
        "prepared_columns": int(prepared_data.shape[1]),
        "source_missing_values": int(raw_data.attrs.get("source_missing_values", 0)),
        "prepared_missing_values": int(prepared_data.isna().sum().sum()),
        "time_column": str(selected_data.attrs.get("time_column", "")),
        "feature_columns": ", ".join(selected_data.attrs.get("feature_columns", ())),
        "elapsed_min_start": float(elapsed.min()),
        "elapsed_min_end": float(elapsed.max()),
        "elapsed_min_span": float(elapsed.max() - elapsed.min()),
        "sampling_phase_count": int(prepared_data["sampling_phase_id"].nunique()),
        "long_time_gap_count": int(prepared_data["long_time_gap"].sum()),
    }
    return pd.DataFrame([overview])


def make_feature_summary(prepared_data: pd.DataFrame) -> pd.DataFrame:
    preferred_columns = [
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "ph_measured",
        "total_flow",
        "acetate_acid_ratio",
    ]
    summary_columns = [col for col in preferred_columns if col in prepared_data.columns]
    rows = []
    for column in summary_columns:
        values = pd.to_numeric(prepared_data[column], errors="coerce")
        rows.append(
            {
                "column": column,
                "n": int(values.notna().sum()),
                "missing": int(values.isna().sum()),
                "min": float(values.min()),
                "mean": float(values.mean()),
                "std": float(values.std()),
                "median": float(values.median()),
                "max": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def make_column_mapping(prepared_data: pd.DataFrame) -> pd.DataFrame:
    mapping_rows = prepared_data.attrs.get("column_mapping", [])
    return pd.DataFrame(mapping_rows, columns=["source_column", "prepared_column"])


def make_sampling_phase_summary(prepared_data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for phase_id, group in prepared_data.groupby("sampling_phase_id", sort=True):
        normal_delta_t = group.loc[
            ~group["long_time_gap"], "delta_t_min"
        ].dropna()
        rows.append(
            {
                "sampling_phase_id": int(phase_id),
                "sampling_phase": str(group["sampling_phase"].iloc[0]),
                "sampling_regime": str(group["sampling_regime"].iloc[0]),
                "start_sample_index": int(group["sample_index"].iloc[0]),
                "end_sample_index": int(group["sample_index"].iloc[-1]),
                "n": int(len(group)),
                "median_delta_t_min": float(normal_delta_t.median()),
                "min_delta_t_min": float(normal_delta_t.min()),
                "max_delta_t_min": float(normal_delta_t.max()),
                "long_time_gap_count": int(group["long_time_gap"].sum()),
            }
        )
    return pd.DataFrame(rows)
