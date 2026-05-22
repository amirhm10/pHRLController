from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helpers.first_principles_improvement import ModelStage, diagnostic_feature_columns


COLORS = {
    "ph_measured": "#005f73",
    "hh_raw": "#9b2226",
    "equilibrium_raw": "#ae2012",
    "equilibrium_bias": "#ee9b00",
    "hh_effective_pka": "#ca6702",
    "hh_affine": "#0a9396",
    "equilibrium_affine": "#005f73",
    "eq_bias": "#ee9b00",
    "eq_affine": "#0a9396",
    "eq_affine_buffer": "#005f73",
    "eq_affine_water": "#ca6702",
    "eq_affine_total_flow": "#bb3e03",
    "eq_affine_empirical_physical": "#ae2012",
}


def create_static_calibration_figures(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    stages: list[ModelStage],
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    display = [
        stage
        for stage in stages
        if stage.key in {"equilibrium_raw", "equilibrium_bias", "equilibrium_affine"}
    ]
    paths = {
        "prediction_time": figure_dir / "measured_vs_static_calibrations_time.png",
        "prediction_scatter": figure_dir / "measured_vs_best_static_scatter.png",
        "residual_histogram": figure_dir / "static_calibration_residual_histograms.png",
        "train_test_rmse": figure_dir / "static_calibration_train_test_rmse.png",
    }
    plot_prediction_time(df, display, paths["prediction_time"], stamp_text)
    plot_prediction_scatter(
        df,
        best_stage_from_metrics(metrics, stages),
        paths["prediction_scatter"],
        stamp_text,
    )
    plot_residual_histograms(df, display, paths["residual_histogram"], stamp_text)
    plot_train_test_rmse(metrics, paths["train_test_rmse"], stamp_text)
    return paths


def create_settled_calibration_figures(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    stages: list[ModelStage],
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    display = [
        stage
        for stage in stages
        if stage.key in {"equilibrium_raw", "equilibrium_affine"}
    ]
    paths = {
        "settled_overlay": figure_dir / "settled_sample_overlay.png",
        "settled_selection": figure_dir / "settled_selection_diagnostics.png",
        "prediction_time": figure_dir / "settled_measured_vs_prediction_time.png",
        "train_test_rmse": figure_dir / "settled_train_test_rmse.png",
    }
    plot_settled_overlay(df, paths["settled_overlay"], stamp_text)
    plot_settled_selection(df, paths["settled_selection"], stamp_text)
    plot_prediction_time(
        df,
        display,
        paths["prediction_time"],
        stamp_text,
        mask_col="is_settled_primary",
    )
    plot_train_test_rmse(metrics, paths["train_test_rmse"], stamp_text)
    return paths


def create_residual_diagnostic_figures(
    df: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
    residual_col: str = "residual_equilibrium_raw",
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "residual_time": figure_dir / "equilibrium_residual_time.png",
        "residual_histogram": figure_dir / "equilibrium_residual_histogram.png",
        "residual_feature_maps": figure_dir / "equilibrium_residual_feature_maps.png",
        "session_summary": figure_dir / "equilibrium_residual_by_session.png",
    }
    plot_residual_time(df, residual_col, paths["residual_time"], stamp_text)
    plot_single_residual_histogram(df, residual_col, paths["residual_histogram"], stamp_text)
    plot_residual_feature_maps(df, residual_col, paths["residual_feature_maps"], stamp_text)
    plot_group_residual_bar(df, "session_id", residual_col, paths["session_summary"], stamp_text)
    return paths


def create_activity_dilution_figures(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    parameters: pd.DataFrame,
    stages: list[ModelStage],
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    best_stage = best_stage_from_metrics(metrics, stages)
    paths = {
        "prediction_time": figure_dir / "activity_dilution_prediction_time.png",
        "prediction_scatter": figure_dir / "activity_dilution_best_scatter.png",
        "train_test_rmse": figure_dir / "activity_dilution_train_test_rmse.png",
        "coefficient_summary": figure_dir / "activity_dilution_coefficients.png",
        "residual_feature_maps": figure_dir / "activity_dilution_residual_feature_maps.png",
    }
    plot_prediction_time(df, [best_stage], paths["prediction_time"], stamp_text)
    plot_prediction_scatter(df, best_stage, paths["prediction_scatter"], stamp_text)
    plot_train_test_rmse(metrics, paths["train_test_rmse"], stamp_text)
    plot_coefficients(parameters, paths["coefficient_summary"], stamp_text)
    plot_residual_feature_maps(
        df,
        f"residual_{best_stage.key}",
        paths["residual_feature_maps"],
        stamp_text,
    )
    return paths


def plot_prediction_time(
    df: pd.DataFrame,
    stages: list[ModelStage],
    path: Path,
    stamp_text: str,
    mask_col: str | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["ph_measured"],
        color=COLORS["ph_measured"],
        linewidth=1.15,
        label="measured PH_2",
    )
    base_mask = df["valid_for_model"]
    if mask_col is not None:
        base_mask = base_mask & df[mask_col]
    for stage in stages:
        mask = base_mask & df[stage.prediction_col].notna()
        ax.plot(
            df.loc[mask, "sample_index"],
            df.loc[mask, stage.prediction_col],
            color=COLORS.get(stage.key, "#333333"),
            linewidth=1.1,
            label=stage.label,
        )
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("Measured PH_2 versus model predictions")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_prediction_scatter(
    df: pd.DataFrame,
    stage: ModelStage,
    path: Path,
    stamp_text: str,
) -> None:
    mask = df["valid_for_model"] & df[stage.prediction_col].notna()
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    colors = df.loc[mask, "split"].map({"train": "#0a9396", "test": "#ae2012"})
    ax.scatter(
        df.loc[mask, stage.prediction_col],
        df.loc[mask, "ph_measured"],
        c=colors,
        alpha=0.65,
        s=26,
    )
    lo = min(df.loc[mask, stage.prediction_col].min(), df.loc[mask, "ph_measured"].min()) - 0.1
    hi = max(df.loc[mask, stage.prediction_col].max(), df.loc[mask, "ph_measured"].max()) + 0.1
    grid = np.linspace(lo, hi, 100)
    ax.plot(grid, grid, "--", color="0.35", linewidth=1.1)
    ax.scatter([], [], color="#0a9396", label="train")
    ax.scatter([], [], color="#ae2012", label="test")
    ax.set_xlabel(stage.label)
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Measured versus predicted pH")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_residual_histograms(
    df: pd.DataFrame,
    stages: list[ModelStage],
    path: Path,
    stamp_text: str,
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    bins = np.linspace(-1.2, 1.2, 45)
    for stage in stages:
        residual = df.loc[
            df["valid_for_model"],
            "ph_measured",
        ] - df.loc[df["valid_for_model"], stage.prediction_col]
        ax.hist(
            residual.dropna(),
            bins=bins,
            histtype="step",
            linewidth=1.7,
            color=COLORS.get(stage.key, "#333333"),
            label=stage.label,
        )
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("PH_2 - prediction")
    ax.set_ylabel("Sample count")
    ax.set_title("Residual distributions")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_train_test_rmse(metrics: pd.DataFrame, path: Path, stamp_text: str) -> None:
    subset = metrics.loc[metrics["split"].isin(["train", "test"])]
    pivot = subset.pivot(index="model_label", columns="split", values="rmse")
    fig, ax = plt.subplots(figsize=(11, 5.8))
    x = np.arange(len(pivot.index))
    width = 0.36
    ax.bar(x - width / 2, pivot.get("train"), width, color="#0a9396", label="train")
    ax.bar(x + width / 2, pivot.get("test"), width, color="#ae2012", label="test")
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=25, ha="right")
    ax.set_ylabel("RMSE (pH)")
    ax.set_title("Train/test RMSE comparison")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_settled_overlay(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["ph_measured"],
        color="#8d99ae",
        linewidth=1.0,
        label="all PH_2",
    )
    mask = df["is_settled_primary"]
    ax.scatter(
        df.loc[mask, "sample_index"],
        df.loc[mask, "ph_measured"],
        color="#ae2012",
        s=28,
        label="primary settled proxy",
    )
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("PH_2")
    ax.set_title("Selected settled-proxy samples")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_settled_selection(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 6.2))
    ax.scatter(
        df["delta_log10_ratio"],
        df["delta_total_flow"],
        c=df["is_settled_primary"].map({True: "#ae2012", False: "#8d99ae"}),
        alpha=0.65,
        s=25,
    )
    ax.axvline(0.25, color="#ae2012", linestyle="--", linewidth=1.0)
    ax.axhline(2.0, color="#ae2012", linestyle="--", linewidth=1.0)
    ax.set_xlabel("abs(delta log10 acetate/acid)")
    ax.set_ylabel("abs(delta total flow) (mL/min)")
    ax.set_title("Settled-proxy flow-stability rule")
    ax.grid(True, alpha=0.3)
    finalize(fig, path, stamp_text)


def plot_residual_time(
    df: pd.DataFrame,
    residual_col: str,
    path: Path,
    stamp_text: str,
) -> None:
    mask = df["valid_for_model"] & df[residual_col].notna()
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df.loc[mask, "sample_index"],
        df.loc[mask, residual_col],
        color="#9b2226",
        linewidth=1.1,
    )
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("Residual")
    ax.set_title(f"{residual_col} over time")
    ax.grid(True, alpha=0.3)
    finalize(fig, path, stamp_text)


def plot_single_residual_histogram(
    df: pd.DataFrame,
    residual_col: str,
    path: Path,
    stamp_text: str,
) -> None:
    residual = df.loc[df["valid_for_model"], residual_col].dropna()
    fig, ax = plt.subplots(figsize=(8, 5.8))
    ax.hist(residual, bins=35, color="#005f73", alpha=0.84)
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.1)
    ax.axvline(residual.mean(), color="#ee9b00", linewidth=1.4, label=f"mean={residual.mean():.3f}")
    ax.set_xlabel("Residual")
    ax.set_ylabel("Sample count")
    ax.set_title(f"{residual_col} distribution")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_residual_feature_maps(
    df: pd.DataFrame,
    residual_col: str,
    path: Path,
    stamp_text: str,
) -> None:
    features = [
        "total_flow",
        "water_fraction",
        "total_buffer_mol_l",
        "log10_molar_base_acid_ratio",
        "elapsed_h",
        "acid_flow",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2))
    mask = df["valid_for_model"] & df[residual_col].notna()
    for ax, feature in zip(axes.ravel(), features):
        ax.scatter(
            df.loc[mask, feature],
            df.loc[mask, residual_col],
            c=df.loc[mask, "elapsed_h"],
            cmap="viridis",
            alpha=0.62,
            s=22,
        )
        ax.axhline(0.0, color="0.25", linestyle="--", linewidth=0.9)
        ax.set_xlabel(feature)
        ax.set_ylabel("residual")
        ax.grid(True, alpha=0.25)
    fig.suptitle("Residual maps against candidate missing-physics features")
    finalize(fig, path, stamp_text)


def plot_group_residual_bar(
    df: pd.DataFrame,
    group_col: str,
    residual_col: str,
    path: Path,
    stamp_text: str,
) -> None:
    summary = (
        df.loc[df["valid_for_model"] & df[residual_col].notna()]
        .groupby(group_col)[residual_col]
        .mean()
    )
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.bar(summary.index.astype(str), summary.values, color="#005f73")
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel(group_col)
    ax.set_ylabel("Mean residual")
    ax.set_title(f"Mean residual by {group_col}")
    ax.grid(True, axis="y", alpha=0.3)
    finalize(fig, path, stamp_text)


def plot_coefficients(parameters: pd.DataFrame, path: Path, stamp_text: str) -> None:
    subset = parameters.loc[
        parameters["model_stage"].ne("reference")
        & parameters["parameter"].ne("intercept")
    ].copy()
    if subset.empty:
        subset = parameters.loc[parameters["model_stage"].ne("reference")].copy()
    subset["label"] = subset["model_stage"] + ":" + subset["feature"].astype(str)
    fig, ax = plt.subplots(figsize=(11, max(5.8, 0.35 * len(subset))))
    ax.barh(subset["label"], subset["value"], color="#0a9396")
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Coefficient value")
    ax.set_title("Empirical correction coefficients")
    ax.grid(True, axis="x", alpha=0.3)
    finalize(fig, path, stamp_text)


def best_stage_from_metrics(metrics: pd.DataFrame, stages: list[ModelStage]) -> ModelStage:
    test = metrics.loc[metrics["split"].eq("test")].sort_values("rmse")
    if test.empty:
        return stages[0]
    key = test.iloc[0]["model_stage"]
    for stage in stages:
        if stage.key == key:
            return stage
    return stages[0]


def finalize(fig, path: Path, stamp_text: str) -> None:
    fig.text(
        0.99,
        0.01,
        stamp_text,
        ha="right",
        va="bottom",
        fontsize=8,
        color="0.35",
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 0.98))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)
