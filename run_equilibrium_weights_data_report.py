from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helpers.dynamic_model_identification import (
    make_sampling_summary,
    make_trial_sampling_summary,
    profile_dataframe_columns,
)
from helpers.equilibrium_main_model_report import (
    EQUILIBRIUM_MAIN_STAGES,
    create_equilibrium_main_figures,
    extract_equilibrium_calibration,
    make_calibration_table,
    make_generated_grid_summary,
    make_generated_pump_grid,
    make_generated_target_flow_sweep,
    select_equilibrium_comparison_columns,
)
from helpers.first_principles_improvement import (
    add_split,
    build_chemistry_dataset,
    fit_static_chemistry_models,
    make_model_metrics,
)
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv")
RESULTS_ROOT = Path("results")

METHOD_NAME = "equilibrium_weights_data_report"
TRAIN_FRACTION = 0.70

TIMING_REGIMES = (
    ("two_minute_140s", "sessions 0-3, approximately 140 s sampling", (0, 3)),
    ("one_minute_69s", "sessions 4-6, approximately 69 s sampling", (4, 6)),
)

NEW_COLUMN_MAP = LabPHColumnMap(
    ph_measured="pH-sensor",
    acid_flow="flow-acid",
    acetate_flow="flow-sodium",
    water_flow="flow-water",
)

LEGACY_COLUMN_MAP = LabPHColumnMap()


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    output_dir = setup_output_dir(RESULTS_ROOT / f"{METHOD_NAME}_{run_stamp}")
    table_dir = setup_output_dir(output_dir / "tables")
    figure_dir = setup_output_dir(output_dir / "figures")
    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"

    config = PHProcessConfig()
    equilibrium_model = EquilibriumChargeBalanceModel.from_config(config)

    raw_data = load_lab_csv(DATA_PATH, NEW_COLUMN_MAP)
    raw_column_profile = profile_dataframe_columns(raw_data, "weights_corrected_raw_csv")
    preprocessed = preprocess_lab_data(raw_data, NEW_COLUMN_MAP, config)
    chemistry = build_chemistry_dataset(preprocessed, config)
    chemistry, trial_split_summary = add_split(chemistry, TRAIN_FRACTION)

    fit_mask = chemistry["valid_for_model"] & chemistry["split"].eq("train")
    comparison, fitted_parameters = fit_static_chemistry_models(chemistry, fit_mask)
    lab_metrics = make_model_metrics(comparison, EQUILIBRIUM_MAIN_STAGES)
    lab_comparison = select_equilibrium_comparison_columns(comparison)
    bounded_metrics = make_bounded_metrics(comparison)
    timing_comparison = add_timing_regime_diagnostics(comparison)
    timing_regime_summary = make_timing_regime_summary(timing_comparison)
    timing_regime_metrics = make_timing_regime_metrics(timing_comparison)

    calibration = extract_equilibrium_calibration(fitted_parameters)
    calibration_parameters = make_calibration_table(fitted_parameters, calibration)
    pump_grid = make_generated_pump_grid(config, equilibrium_model, calibration)
    target_sweep = make_generated_target_flow_sweep(
        config,
        equilibrium_model,
        calibration,
    )
    grid_summary = make_generated_grid_summary(pump_grid, target_sweep)
    source_summary = make_source_comparison_summary(raw_data)
    row_summary = make_row_summary(raw_data, preprocessed)
    sampling_summary = make_sampling_summary(comparison)
    trial_sampling_summary = make_trial_sampling_summary(comparison)
    preprocessed_column_profile = profile_dataframe_columns(
        preprocessed,
        "weights_corrected_preprocessed",
    )

    save_tables(
        table_dir=table_dir,
        raw_column_profile=raw_column_profile,
        preprocessed_column_profile=preprocessed_column_profile,
        preprocessed=preprocessed,
        lab_comparison=lab_comparison,
        lab_metrics=lab_metrics,
        bounded_metrics=bounded_metrics,
        timing_comparison=timing_comparison,
        timing_regime_summary=timing_regime_summary,
        timing_regime_metrics=timing_regime_metrics,
        calibration_parameters=calibration_parameters,
        trial_split_summary=trial_split_summary,
        sampling_summary=sampling_summary,
        trial_sampling_summary=trial_sampling_summary,
        source_summary=source_summary,
        row_summary=row_summary,
        pump_grid=pump_grid,
        target_sweep=target_sweep,
        grid_summary=grid_summary,
    )
    create_equilibrium_main_figures(
        lab_df=comparison,
        lab_metrics=lab_metrics,
        pump_grid=pump_grid,
        target_sweep=target_sweep,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )
    create_weight_data_figures(
        raw_data=raw_data,
        comparison=comparison,
        timing_comparison=timing_comparison,
        timing_regime_summary=timing_regime_summary,
        calibration=calibration,
        source_summary=source_summary,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )

    print(f"Equilibrium weights-data report artifacts complete: {output_dir}")
    print(f"Tables written: {table_dir}")
    print(f"Figures written: {figure_dir}")
    print(make_console_summary(
        lab_metrics,
        bounded_metrics,
        timing_regime_summary,
        calibration,
        row_summary,
    ))


def make_bounded_metrics(comparison: pd.DataFrame) -> pd.DataFrame:
    bounded = (
        comparison["valid_for_model"]
        & comparison["acid_flow_in_bounds"]
        & comparison["acetate_flow_in_bounds"]
        & comparison["water_flow_in_bounds"]
    )
    return make_model_metrics(comparison, EQUILIBRIUM_MAIN_STAGES, mask=bounded)


def add_timing_regime_diagnostics(comparison: pd.DataFrame) -> pd.DataFrame:
    enriched = comparison.copy()
    enriched["timing_regime"] = "other"
    enriched["timing_regime_description"] = ""
    enriched["prediction_timing_local_affine"] = np.nan
    enriched["residual_timing_local_affine"] = np.nan
    enriched["timing_local_affine_intercept"] = np.nan
    enriched["timing_local_affine_slope"] = np.nan

    for regime, description, session_range in TIMING_REGIMES:
        mask = timing_regime_mask(enriched, session_range)
        enriched.loc[mask, "timing_regime"] = regime
        enriched.loc[mask, "timing_regime_description"] = description

        fit_mask = (
            mask
            & enriched["valid_for_model"]
            & enriched["ph_equilibrium_charge_balance"].notna()
            & enriched["ph_measured"].notna()
        )
        if fit_mask.sum() < 2:
            continue

        x = enriched.loc[fit_mask, "ph_equilibrium_charge_balance"].to_numpy(dtype=float)
        y = enriched.loc[fit_mask, "ph_measured"].to_numpy(dtype=float)
        intercept, slope = np.linalg.lstsq(
            np.column_stack([np.ones(len(x)), x]),
            y,
            rcond=None,
        )[0]
        pred_mask = mask & enriched["ph_equilibrium_charge_balance"].notna()
        prediction = (
            float(intercept)
            + float(slope) * enriched.loc[pred_mask, "ph_equilibrium_charge_balance"]
        )
        enriched.loc[pred_mask, "prediction_timing_local_affine"] = prediction
        enriched.loc[pred_mask, "residual_timing_local_affine"] = (
            enriched.loc[pred_mask, "ph_measured"] - prediction
        )
        enriched.loc[mask, "timing_local_affine_intercept"] = float(intercept)
        enriched.loc[mask, "timing_local_affine_slope"] = float(slope)
    return enriched


def timing_regime_mask(df: pd.DataFrame, session_range: tuple[int, int]) -> pd.Series:
    start, end = session_range
    return df["session_id"].between(start, end, inclusive="both")


def make_timing_regime_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime, description, session_range in TIMING_REGIMES:
        mask = timing_regime_mask(df, session_range)
        group = df.loc[mask].copy()
        valid = group["valid_for_model"].astype(bool)
        valid_group = group.loc[valid]
        dt = pd.to_numeric(group["dt_s"], errors="coerce").dropna()
        dt = dt.loc[dt > 0.0]
        row = {
            "timing_regime": regime,
            "description": description,
            "session_id_min": int(session_range[0]),
            "session_id_max": int(session_range[1]),
            "sample_index_min": int(group["sample_index"].min()) if len(group) else np.nan,
            "sample_index_max": int(group["sample_index"].max()) if len(group) else np.nan,
            "n_total": int(len(group)),
            "n_valid": int(valid.sum()),
            "median_dt_s": safe_float(dt.median()),
            "p05_dt_s": safe_float(dt.quantile(0.05)),
            "p95_dt_s": safe_float(dt.quantile(0.95)),
            "intervals_gt_15_min": int(dt.gt(900.0).sum()) if len(dt) else 0,
            "ph_min": safe_float(valid_group["ph_measured"].min()),
            "ph_median": safe_float(valid_group["ph_measured"].median()),
            "ph_max": safe_float(valid_group["ph_measured"].max()),
            "ph_eq_min": safe_float(valid_group["ph_equilibrium_charge_balance"].min()),
            "ph_eq_median": safe_float(valid_group["ph_equilibrium_charge_balance"].median()),
            "ph_eq_max": safe_float(valid_group["ph_equilibrium_charge_balance"].max()),
            "acid_median": safe_float(valid_group["acid_flow"].median()),
            "acetate_median": safe_float(valid_group["acetate_flow"].median()),
            "water_median": safe_float(valid_group["water_flow"].median()),
            "total_flow_median": safe_float(valid_group["total_flow"].median()),
            "rows_any_flow_above_10": int((
                valid_group["acid_flow"].gt(10.0)
                | valid_group["acetate_flow"].gt(10.0)
                | valid_group["water_flow"].gt(10.0)
            ).sum()),
            "local_affine_intercept": safe_float(
                valid_group["timing_local_affine_intercept"].dropna().iloc[0]
            )
            if valid_group["timing_local_affine_intercept"].notna().any()
            else np.nan,
            "local_affine_slope": safe_float(
                valid_group["timing_local_affine_slope"].dropna().iloc[0]
            )
            if valid_group["timing_local_affine_slope"].notna().any()
            else np.nan,
        }
        for key, residual_col in [
            ("raw", "residual_equilibrium_raw"),
            ("global_affine", "residual_equilibrium_affine"),
            ("local_affine", "residual_timing_local_affine"),
        ]:
            residual = valid_group[residual_col].dropna()
            row[f"{key}_mean_error"] = safe_float(residual.mean())
            row[f"{key}_mae"] = safe_float(residual.abs().mean())
            row[f"{key}_rmse"] = residual_rmse(residual)
            row[f"{key}_max_abs"] = safe_float(residual.abs().max())
        rows.append(row)
    return pd.DataFrame(rows)


def make_timing_regime_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [
        ("raw", "Raw equilibrium", "prediction_equilibrium_raw", "residual_equilibrium_raw"),
        (
            "global_affine",
            "Global equilibrium affine",
            "prediction_equilibrium_affine",
            "residual_equilibrium_affine",
        ),
        (
            "timing_local_affine",
            "Timing-local equilibrium affine",
            "prediction_timing_local_affine",
            "residual_timing_local_affine",
        ),
    ]
    for regime, description, session_range in TIMING_REGIMES:
        mask = timing_regime_mask(df, session_range) & df["valid_for_model"]
        for key, label, prediction_col, residual_col in specs:
            metric_mask = mask & df[prediction_col].notna() & df["ph_measured"].notna()
            residual = df.loc[metric_mask, residual_col].dropna()
            measured = df.loc[metric_mask, "ph_measured"]
            predicted = df.loc[metric_mask, prediction_col]
            rows.append({
                "timing_regime": regime,
                "description": description,
                "model_stage": key,
                "model_label": label,
                "n": int(metric_mask.sum()),
                "mean_error": safe_float(residual.mean()),
                "mae": safe_float(residual.abs().mean()),
                "rmse": residual_rmse(residual),
                "max_abs": safe_float(residual.abs().max()),
                "correlation": safe_float(measured.corr(predicted))
                if len(measured.dropna()) > 1
                else np.nan,
            })
    return pd.DataFrame(rows)


def make_source_comparison_summary(raw_data: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("acid_flow", "flow-acid", "observation.biosmb-flows[0]"),
        ("acetate_flow", "flow-sodium", "observation.biosmb-flows[1]"),
        ("water_flow", "flow-water", "observation.biosmb-flows[2]"),
        ("ph_sensor", "pH-sensor", "observation.biosmb-sensors.PH_2"),
    ]
    rows = []
    for label, corrected_col, legacy_col in pairs:
        corrected = pd.to_numeric(raw_data[corrected_col], errors="coerce")
        legacy = pd.to_numeric(raw_data[legacy_col], errors="coerce")
        delta = corrected - legacy
        rows.append({
            "quantity": label,
            "corrected_column": corrected_col,
            "legacy_column": legacy_col,
            "n": int(delta.notna().sum()),
            "corrected_min": safe_float(corrected.min()),
            "corrected_median": safe_float(corrected.median()),
            "corrected_max": safe_float(corrected.max()),
            "legacy_min": safe_float(legacy.min()),
            "legacy_median": safe_float(legacy.median()),
            "legacy_max": safe_float(legacy.max()),
            "delta_mean": safe_float(delta.mean()),
            "delta_median": safe_float(delta.median()),
            "delta_std": safe_float(delta.std()),
            "delta_min": safe_float(delta.min()),
            "delta_max": safe_float(delta.max()),
            "correlation": safe_float(corrected.corr(legacy)),
        })
    return pd.DataFrame(rows)


def make_row_summary(raw_data: pd.DataFrame, preprocessed: pd.DataFrame) -> pd.DataFrame:
    positive_flow = (
        preprocessed["acid_flow"].gt(0.0)
        & preprocessed["acetate_flow"].gt(0.0)
        & preprocessed["water_flow"].gt(0.0)
    )
    bounded = (
        preprocessed["acid_flow_in_bounds"]
        & preprocessed["acetate_flow_in_bounds"]
        & preprocessed["water_flow_in_bounds"]
    )
    rows = [
        ("raw_rows", len(raw_data)),
        ("positive_flow_rows", int(positive_flow.sum())),
        (
            "valid_before_flat_trial_filter",
            int(preprocessed["valid_for_model_before_flat_trial_filter"].sum()),
        ),
        ("flat_trial_rows_flagged", int(preprocessed["uninformative_flat_ph_trial"].sum())),
        ("valid_for_model_rows", int(preprocessed["valid_for_model"].sum())),
        ("all_three_flows_in_nominal_bounds", int((positive_flow & bounded).sum())),
        ("acid_above_10_ml_min", int(preprocessed["acid_flow"].gt(10.0).sum())),
        ("acetate_above_10_ml_min", int(preprocessed["acetate_flow"].gt(10.0).sum())),
        ("water_above_10_ml_min", int(preprocessed["water_flow"].gt(10.0).sum())),
        ("any_flow_above_10_ml_min", int((positive_flow & ~bounded).sum())),
    ]
    return pd.DataFrame(rows, columns=["check", "value"])


def create_weight_data_figures(
    raw_data: pd.DataFrame,
    comparison: pd.DataFrame,
    timing_comparison: pd.DataFrame,
    timing_regime_summary: pd.DataFrame,
    calibration: dict[str, float | int],
    source_summary: pd.DataFrame,
    figure_dir: Path,
    stamp_text: str,
) -> dict[str, Path]:
    paths = {
        "corrected_input_output_behavior": (
            figure_dir / "corrected_input_output_behavior.png"
        ),
        "legacy_vs_weight_flows": figure_dir / "legacy_vs_weight_flows.png",
        "flow_correction_deltas": figure_dir / "flow_correction_deltas.png",
        "weights_residual_histogram": figure_dir / "weights_residual_histogram.png",
        "timing_regime_scatter": figure_dir / "timing_regime_equilibrium_scatter.png",
        "timing_regime_residual_boxplot": (
            figure_dir / "timing_regime_residual_boxplot.png"
        ),
    }
    plot_corrected_input_output_behavior(comparison, paths["corrected_input_output_behavior"], stamp_text)
    plot_legacy_vs_weight_flows(raw_data, paths["legacy_vs_weight_flows"], stamp_text)
    plot_flow_correction_deltas(raw_data, paths["flow_correction_deltas"], stamp_text)
    plot_weights_residual_histogram(comparison, paths["weights_residual_histogram"], stamp_text)
    plot_timing_regime_scatter(
        timing_comparison,
        timing_regime_summary,
        calibration,
        paths["timing_regime_scatter"],
        stamp_text,
    )
    plot_timing_regime_residual_boxplot(
        timing_comparison,
        paths["timing_regime_residual_boxplot"],
        stamp_text,
    )
    source_summary.to_csv(figure_dir / "source_summary_used_for_figures.csv", index=False)
    return paths


def plot_corrected_input_output_behavior(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    x = df["sample_index"]
    fig, axes = plt.subplots(4, 1, figsize=(12, 10.2), sharex=True)
    axes[0].plot(x, df["ph_measured"], color="#005f73", linewidth=1.2)
    axes[0].set_ylabel("pH-sensor")
    axes[0].set_title("Weights-corrected pH and inlet behavior")

    axes[1].plot(x, df["acid_flow"], color="#ae2012", label="acid")
    axes[1].plot(x, df["acetate_flow"], color="#0a9396", label="sodium acetate")
    axes[1].plot(x, df["water_flow"], color="#005f73", label="water")
    axes[1].axhline(10.0, color="0.35", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Flow (mL/min)")
    axes[1].legend(loc="best", ncols=3)

    axes[2].plot(x, df["total_flow"], color="#5f0f40", linewidth=1.2)
    axes[2].set_ylabel("Total flow\n(mL/min)")

    axes[3].plot(
        x,
        df["log10_molar_base_acid_ratio"],
        color="#ee9b00",
        linewidth=1.2,
    )
    axes[3].axhline(0.0, color="0.35", linestyle="--", linewidth=1.0)
    axes[3].set_ylabel("log10\nacetate/acid")
    axes[3].set_xlabel("Chronological sample index")

    for ax in axes:
        mark_flat_trial_regions(ax, df)
        mark_test_region(ax, df)
        ax.grid(True, alpha=0.3)
    finalize_figure(fig, path, stamp_text)


def plot_legacy_vs_weight_flows(raw_data: pd.DataFrame, path: Path, stamp_text: str) -> None:
    specs = [
        ("flow-acid", "observation.biosmb-flows[0]", "Acid"),
        ("flow-sodium", "observation.biosmb-flows[1]", "Sodium acetate"),
        ("flow-water", "observation.biosmb-flows[2]", "Water"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.5))
    for ax, (corrected_col, legacy_col, label) in zip(axes, specs):
        corrected = pd.to_numeric(raw_data[corrected_col], errors="coerce")
        legacy = pd.to_numeric(raw_data[legacy_col], errors="coerce")
        ax.scatter(legacy, corrected, s=18, alpha=0.55, color="#0a9396")
        lo = min(float(legacy.min()), float(corrected.min())) - 0.3
        hi = max(float(legacy.max()), float(corrected.max())) + 0.3
        ax.plot([lo, hi], [lo, hi], "--", color="0.35", linewidth=1.0)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("logged flow column (mL/min)")
        ax.set_ylabel("weight-backcalculated flow (mL/min)")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Weight-backcalculated flows versus logged flow columns")
    finalize_figure(fig, path, stamp_text)


def plot_flow_correction_deltas(raw_data: pd.DataFrame, path: Path, stamp_text: str) -> None:
    specs = [
        ("flow-acid", "observation.biosmb-flows[0]", "acid"),
        ("flow-sodium", "observation.biosmb-flows[1]", "sodium acetate"),
        ("flow-water", "observation.biosmb-flows[2]", "water"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    bins = np.linspace(-2.2, 3.0, 60)
    colors = ["#ae2012", "#0a9396", "#005f73"]
    for (corrected_col, legacy_col, label), color in zip(specs, colors):
        delta = (
            pd.to_numeric(raw_data[corrected_col], errors="coerce")
            - pd.to_numeric(raw_data[legacy_col], errors="coerce")
        ).dropna()
        ax.hist(delta, bins=bins, histtype="step", linewidth=1.7, color=color, label=label)
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("weight-backcalculated flow minus logged flow (mL/min)")
    ax.set_ylabel("Sample count")
    ax.set_title("Flow correction distributions")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_weights_residual_histogram(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))
    test = df["valid_for_model"] & df["split"].eq("test")
    bins = np.linspace(-1.0, 1.0, 50)
    for residual_col, label, color in [
        ("residual_equilibrium_raw", "raw equilibrium", "#ae2012"),
        ("residual_equilibrium_bias", "equilibrium + bias", "#ee9b00"),
        ("residual_equilibrium_affine", "equilibrium affine", "#0a9396"),
    ]:
        residual = df.loc[test, residual_col].dropna()
        ax.hist(residual, bins=bins, histtype="step", linewidth=1.7, color=color, label=label)
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Test residual, pH-sensor - prediction")
    ax.set_ylabel("Sample count")
    ax.set_title("Weights-corrected test residual distributions")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_timing_regime_scatter(
    df: pd.DataFrame,
    timing_regime_summary: pd.DataFrame,
    calibration: dict[str, float | int],
    path: Path,
    stamp_text: str,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.8), sharex=True, sharey=True)
    x_min = df.loc[df["valid_for_model"], "ph_equilibrium_charge_balance"].min() - 0.1
    x_max = df.loc[df["valid_for_model"], "ph_equilibrium_charge_balance"].max() + 0.1
    grid = np.linspace(float(x_min), float(x_max), 100)

    for ax, (regime, description, _) in zip(axes, TIMING_REGIMES):
        subset = df.loc[df["timing_regime"].eq(regime) & df["valid_for_model"]]
        summary = timing_regime_summary.loc[
            timing_regime_summary["timing_regime"].eq(regime)
        ].iloc[0]
        ax.scatter(
            subset["ph_equilibrium_charge_balance"],
            subset["ph_measured"],
            s=24,
            alpha=0.62,
            color="#0a9396",
            label="samples",
        )
        ax.plot(grid, grid, "--", color="0.35", linewidth=1.0, label="identity")
        ax.plot(
            grid,
            float(calibration["intercept"]) + float(calibration["slope"]) * grid,
            color="#ae2012",
            linewidth=1.5,
            label="global affine",
        )
        ax.plot(
            grid,
            summary["local_affine_intercept"] + summary["local_affine_slope"] * grid,
            color="#005f73",
            linewidth=1.5,
            label="timing-local affine",
        )
        ax.set_title(description)
        ax.set_xlabel("raw equilibrium pH")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("measured pH-sensor")
    axes[0].legend(loc="best")
    fig.suptitle("Equilibrium pH versus measured pH by sampling regime")
    finalize_figure(fig, path, stamp_text)


def plot_timing_regime_residual_boxplot(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    rows = []
    for regime, description, _ in TIMING_REGIMES:
        subset = df.loc[df["timing_regime"].eq(regime) & df["valid_for_model"]]
        for residual_col, label in [
            ("residual_equilibrium_raw", "raw"),
            ("residual_equilibrium_affine", "global affine"),
            ("residual_timing_local_affine", "timing-local affine"),
        ]:
            for value in subset[residual_col].dropna():
                rows.append({
                    "timing_regime": regime,
                    "description": description,
                    "model": label,
                    "residual": float(value),
                })
    plot_df = pd.DataFrame(rows)
    labels = []
    data = []
    colors = []
    palette = {
        "raw": "#ae2012",
        "global affine": "#ee9b00",
        "timing-local affine": "#0a9396",
    }
    for regime, description, _ in TIMING_REGIMES:
        for model in ["raw", "global affine", "timing-local affine"]:
            values = plot_df.loc[
                plot_df["timing_regime"].eq(regime) & plot_df["model"].eq(model),
                "residual",
            ].to_numpy(dtype=float)
            labels.append(f"{description.split(',')[0]}\n{model}")
            data.append(values)
            colors.append(palette[model])

    fig, ax = plt.subplots(figsize=(12.0, 5.8))
    box = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=False)
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.35)
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_ylabel("residual, pH-sensor - prediction")
    ax.set_title("Residual distributions by timing regime")
    ax.grid(True, axis="y", alpha=0.3)
    finalize_figure(fig, path, stamp_text)


def mark_test_region(ax, df: pd.DataFrame) -> None:
    test = df.loc[df["split"].eq("test")]
    if test.empty:
        return
    ax.axvspan(
        test["sample_index"].min(),
        test["sample_index"].max(),
        color="#f4a261",
        alpha=0.08,
        label="test region",
    )


def mark_flat_trial_regions(ax, df: pd.DataFrame) -> None:
    if "uninformative_flat_ph_trial" not in df.columns:
        return
    flat = df.loc[df["uninformative_flat_ph_trial"].astype(bool)]
    if flat.empty:
        return
    for _, group in flat.groupby("trial_id", sort=True):
        ax.axvspan(
            group["sample_index"].min(),
            group["sample_index"].max(),
            color="#d62828",
            alpha=0.08,
        )


def finalize_figure(fig, path: Path, stamp_text: str) -> None:
    fig.text(
        0.99,
        0.01,
        stamp_text,
        ha="right",
        va="bottom",
        fontsize=8,
        color="0.35",
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def save_tables(
    table_dir: Path,
    raw_column_profile: pd.DataFrame,
    preprocessed_column_profile: pd.DataFrame,
    preprocessed: pd.DataFrame,
    lab_comparison: pd.DataFrame,
    lab_metrics: pd.DataFrame,
    bounded_metrics: pd.DataFrame,
    timing_comparison: pd.DataFrame,
    timing_regime_summary: pd.DataFrame,
    timing_regime_metrics: pd.DataFrame,
    calibration_parameters: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
    sampling_summary: pd.DataFrame,
    trial_sampling_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    row_summary: pd.DataFrame,
    pump_grid: pd.DataFrame,
    target_sweep: pd.DataFrame,
    grid_summary: pd.DataFrame,
) -> dict[str, Path]:
    tables = {
        "raw_column_profile": table_dir / "raw_column_profile.csv",
        "preprocessed_column_profile": table_dir / "preprocessed_column_profile.csv",
        "preprocessed_lab_data": table_dir / "preprocessed_lab_data.csv",
        "lab_equilibrium_model_comparison": (
            table_dir / "lab_equilibrium_model_comparison.csv"
        ),
        "lab_metrics": table_dir / "lab_metrics.csv",
        "bounded_metrics": table_dir / "bounded_metrics.csv",
        "timing_regime_comparison": table_dir / "timing_regime_comparison.csv",
        "timing_regime_summary": table_dir / "timing_regime_summary.csv",
        "timing_regime_metrics": table_dir / "timing_regime_metrics.csv",
        "calibration_parameters": table_dir / "calibration_parameters.csv",
        "trial_split_summary": table_dir / "trial_split_summary.csv",
        "sampling_summary": table_dir / "sampling_summary.csv",
        "trial_sampling_summary": table_dir / "trial_sampling_summary.csv",
        "flow_source_comparison_summary": table_dir / "flow_source_comparison_summary.csv",
        "row_summary": table_dir / "row_summary.csv",
        "generated_pump_grid": table_dir / "generated_pump_grid.csv",
        "generated_target_flow_sweep": table_dir / "generated_target_flow_sweep.csv",
        "generated_grid_summary": table_dir / "generated_grid_summary.csv",
    }
    raw_column_profile.to_csv(tables["raw_column_profile"], index=False)
    preprocessed_column_profile.to_csv(tables["preprocessed_column_profile"], index=False)
    preprocessed.to_csv(tables["preprocessed_lab_data"], index=False)
    lab_comparison.to_csv(tables["lab_equilibrium_model_comparison"], index=False)
    lab_metrics.to_csv(tables["lab_metrics"], index=False)
    bounded_metrics.to_csv(tables["bounded_metrics"], index=False)
    timing_comparison.to_csv(tables["timing_regime_comparison"], index=False)
    timing_regime_summary.to_csv(tables["timing_regime_summary"], index=False)
    timing_regime_metrics.to_csv(tables["timing_regime_metrics"], index=False)
    calibration_parameters.to_csv(tables["calibration_parameters"], index=False)
    trial_split_summary.to_csv(tables["trial_split_summary"], index=False)
    sampling_summary.to_csv(tables["sampling_summary"], index=False)
    trial_sampling_summary.to_csv(tables["trial_sampling_summary"], index=False)
    source_summary.to_csv(tables["flow_source_comparison_summary"], index=False)
    row_summary.to_csv(tables["row_summary"], index=False)
    pump_grid.to_csv(tables["generated_pump_grid"], index=False)
    target_sweep.to_csv(tables["generated_target_flow_sweep"], index=False)
    grid_summary.to_csv(tables["generated_grid_summary"], index=False)
    return tables


def make_console_summary(
    lab_metrics: pd.DataFrame,
    bounded_metrics: pd.DataFrame,
    timing_regime_summary: pd.DataFrame,
    calibration: dict[str, float | int],
    row_summary: pd.DataFrame,
) -> str:
    raw_test = metric_row(lab_metrics, "equilibrium_raw", "test")
    affine_test = metric_row(lab_metrics, "equilibrium_affine", "test")
    bounded_affine_test = metric_row(bounded_metrics, "equilibrium_affine", "test")
    valid_rows = int(row_summary.loc[row_summary["check"].eq("valid_for_model_rows"), "value"].iloc[0])
    out_of_bound = int(row_summary.loc[row_summary["check"].eq("any_flow_above_10_ml_min"), "value"].iloc[0])
    two_min = timing_regime_summary.loc[
        timing_regime_summary["timing_regime"].eq("two_minute_140s")
    ].iloc[0]
    one_min = timing_regime_summary.loc[
        timing_regime_summary["timing_regime"].eq("one_minute_69s")
    ].iloc[0]
    return (
        "Key checks: "
        f"valid rows={valid_rows}; "
        f"rows with any inferred flow above 10 mL/min={out_of_bound}; "
        f"raw equilibrium test RMSE={raw_test['rmse']:.4f} pH; "
        f"affine test RMSE={affine_test['rmse']:.4f} pH; "
        f"bounded affine test RMSE={bounded_affine_test['rmse']:.4f} pH; "
        f"two-minute local RMSE={two_min['local_affine_rmse']:.4f} pH; "
        f"one-minute local RMSE={one_min['local_affine_rmse']:.4f} pH; "
        f"affine b0={calibration['intercept']:.4f}, "
        f"b1={calibration['slope']:.4f}."
    )


def metric_row(metrics: pd.DataFrame, model_stage: str, split: str) -> pd.Series:
    return metrics.loc[
        metrics["model_stage"].eq(model_stage) & metrics["split"].eq(split)
    ].iloc[0]


def safe_float(value: float) -> float:
    return float(value) if pd.notna(value) else np.nan


def residual_rmse(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0:
        return np.nan
    return float(np.sqrt(np.mean(array**2)))


if __name__ == "__main__":
    main()
