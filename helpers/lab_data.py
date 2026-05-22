from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from simulation.config import PHProcessConfig


@dataclass(frozen=True)
class LabPHColumnMap:
    """Column mapping for the treated lab pH CSV."""

    utc_time: str = "utc_time"
    ph_measured: str = "observation.biosmb-sensors.PH_2"
    acid_flow: str = "observation.biosmb-flows[0]"
    acetate_flow: str = "observation.biosmb-flows[1]"
    water_flow: str = "observation.biosmb-flows[2]"
    episode_number: str = "episode_number"
    step_number: str = "step_number"

    def required_columns(self) -> tuple[str, ...]:
        return (
            self.utc_time,
            self.ph_measured,
            self.acid_flow,
            self.acetate_flow,
            self.water_flow,
        )


def load_lab_csv(path: str | Path, column_map: LabPHColumnMap | None = None) -> pd.DataFrame:
    column_map = column_map or LabPHColumnMap()
    path = Path(path)
    df = pd.read_csv(path)
    missing_columns = [col for col in column_map.required_columns() if col not in df.columns]
    if missing_columns:
        raise KeyError(f"Missing required lab CSV columns: {missing_columns}")

    df.attrs["source_path"] = str(path)
    df.attrs["source_columns"] = int(df.shape[1])
    df.attrs["source_missing_values"] = int(df.isna().sum().sum())
    return df


def preprocess_lab_data(
    df: pd.DataFrame,
    column_map: LabPHColumnMap | None = None,
    config: PHProcessConfig | None = None,
    long_gap_s: float = 900.0,
    exclude_uninformative_flat_ph_trials: bool = True,
    flat_ph_trial_min_samples: int = 5,
    flat_ph_range_max: float = 0.05,
    flat_log10_ratio_range_min: float = 0.5,
) -> pd.DataFrame:
    """Prepare lab data for inlet-flow to PH_2 model validation."""
    column_map = column_map or LabPHColumnMap()
    config = config or PHProcessConfig()

    prepared = pd.DataFrame()
    prepared["utc_time"] = df[column_map.utc_time]
    prepared["utc_datetime"] = pd.to_datetime(df[column_map.utc_time], utc=True)
    prepared["episode_number"] = optional_numeric_column(df, column_map.episode_number)
    prepared["step_number"] = optional_numeric_column(df, column_map.step_number)
    prepared["ph_measured"] = pd.to_numeric(df[column_map.ph_measured], errors="coerce")
    prepared["acid_flow"] = pd.to_numeric(df[column_map.acid_flow], errors="coerce")
    prepared["acetate_flow"] = pd.to_numeric(df[column_map.acetate_flow], errors="coerce")
    prepared["water_flow"] = pd.to_numeric(df[column_map.water_flow], errors="coerce")

    prepared = prepared.sort_values("utc_datetime").reset_index(drop=True)
    prepared.insert(0, "sample_index", np.arange(len(prepared), dtype=int))
    prepared["elapsed_s"] = (
        prepared["utc_datetime"] - prepared["utc_datetime"].iloc[0]
    ).dt.total_seconds()
    prepared["elapsed_min"] = prepared["elapsed_s"] / 60.0
    prepared["elapsed_h"] = prepared["elapsed_min"] / 60.0
    prepared["dt_s"] = prepared["utc_datetime"].diff().dt.total_seconds()

    new_session = prepared["dt_s"].gt(long_gap_s).fillna(True)
    prepared["session_id"] = new_session.cumsum().astype(int)

    step_reset = prepared["step_number"].lt(prepared["step_number"].shift()).fillna(False)
    episode_reset = prepared["episode_number"].lt(
        prepared["episode_number"].shift()
    ).fillna(False)
    new_trial = (new_session | step_reset | episode_reset).fillna(True)
    prepared["trial_id"] = new_trial.cumsum().astype(int)

    prepared["total_flow"] = (
        prepared["acid_flow"] + prepared["acetate_flow"] + prepared["water_flow"]
    )
    prepared["valid_for_model"] = (
        prepared["ph_measured"].notna()
        & prepared["acid_flow"].gt(0.0)
        & prepared["acetate_flow"].gt(0.0)
        & prepared["water_flow"].gt(0.0)
    )
    prepared["flow_ratio_acetate_acid"] = np.nan
    valid = prepared["valid_for_model"]
    prepared.loc[valid, "flow_ratio_acetate_acid"] = (
        prepared.loc[valid, "acetate_flow"] / prepared.loc[valid, "acid_flow"]
    )
    prepared["log10_flow_ratio_acetate_acid"] = np.log10(
        prepared["flow_ratio_acetate_acid"]
    )

    flat_trial_stats = make_flat_ph_trial_stats(prepared)
    prepared = prepared.join(flat_trial_stats, on="trial_id")
    prepared["uninformative_flat_ph_trial"] = (
        prepared["trial_n_total"].ge(flat_ph_trial_min_samples)
        & prepared["trial_ph_range"].le(flat_ph_range_max)
        & prepared["trial_log10_flow_ratio_range"].ge(flat_log10_ratio_range_min)
    )
    prepared["valid_for_model_before_flat_trial_filter"] = prepared["valid_for_model"]
    if exclude_uninformative_flat_ph_trials:
        prepared["valid_for_model"] = (
            prepared["valid_for_model"] & ~prepared["uninformative_flat_ph_trial"]
        )

    prepared["acid_flow_in_bounds"] = prepared["acid_flow"].between(
        config.acid_flow_min,
        config.acid_flow_max,
        inclusive="both",
    )
    prepared["acetate_flow_in_bounds"] = prepared["acetate_flow"].between(
        config.acetate_flow_min,
        config.acetate_flow_max,
        inclusive="both",
    )
    prepared["water_flow_in_bounds"] = prepared["water_flow"].between(
        config.water_flow_min,
        config.water_flow_max,
        inclusive="both",
    )

    prepared.attrs.update(df.attrs)
    prepared.attrs["analysis_columns"] = int(prepared.shape[1])
    prepared.attrs["long_gap_s"] = float(long_gap_s)
    prepared.attrs["exclude_uninformative_flat_ph_trials"] = bool(
        exclude_uninformative_flat_ph_trials
    )
    prepared.attrs["flat_ph_trial_min_samples"] = int(flat_ph_trial_min_samples)
    prepared.attrs["flat_ph_range_max"] = float(flat_ph_range_max)
    prepared.attrs["flat_log10_ratio_range_min"] = float(flat_log10_ratio_range_min)
    return prepared


def optional_numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column], errors="coerce")


def make_flat_ph_trial_stats(prepared: pd.DataFrame) -> pd.DataFrame:
    """Summarize each trial for low-information flat-pH detection."""
    valid = prepared["valid_for_model"]
    valid_only = prepared.loc[valid].copy()
    stats = valid_only.groupby("trial_id").agg(
        trial_n_model_valid=("ph_measured", "size"),
        trial_ph_min=("ph_measured", "min"),
        trial_ph_max=("ph_measured", "max"),
        trial_log10_ratio_min=("log10_flow_ratio_acetate_acid", "min"),
        trial_log10_ratio_max=("log10_flow_ratio_acetate_acid", "max"),
        trial_total_flow_min=("total_flow", "min"),
        trial_total_flow_max=("total_flow", "max"),
    )
    total_count = prepared.groupby("trial_id").size().rename("trial_n_total")
    stats = stats.join(total_count, how="outer")
    stats["trial_n_model_valid"] = stats["trial_n_model_valid"].fillna(0).astype(int)
    stats["trial_n_total"] = stats["trial_n_total"].fillna(0).astype(int)
    stats["trial_ph_range"] = stats["trial_ph_max"] - stats["trial_ph_min"]
    stats["trial_log10_flow_ratio_range"] = (
        stats["trial_log10_ratio_max"] - stats["trial_log10_ratio_min"]
    )
    stats["trial_total_flow_range"] = (
        stats["trial_total_flow_max"] - stats["trial_total_flow_min"]
    )
    return stats
