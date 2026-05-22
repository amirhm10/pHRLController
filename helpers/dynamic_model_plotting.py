from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_COLORS = {
    "equilibrium_baseline": "#8d99ae",
    "static_calibrated": "#0a9396",
    "lag_calibrated": "#ee9b00",
    "dynamic_first_order": "#ae2012",
}

MODEL_LABELS = {
    "equilibrium_baseline": "Equilibrium baseline",
    "static_calibrated": "Static calibrated",
    "lag_calibrated": "Lag calibrated",
    "dynamic_first_order": "First-order dynamic",
}

PREDICTION_COLUMNS = {
    "equilibrium_baseline": "prediction_equilibrium_baseline",
    "static_calibrated": "prediction_static_calibrated",
    "lag_calibrated": "prediction_lag_calibrated",
    "dynamic_first_order": "prediction_dynamic_first_order",
}

RESIDUAL_COLUMNS = {
    "equilibrium_baseline": "residual_equilibrium_baseline",
    "static_calibrated": "residual_static_calibrated",
    "lag_calibrated": "residual_lag_calibrated",
    "dynamic_first_order": "residual_dynamic_first_order",
}


def create_dynamic_model_figures(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    lag_search: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "measured_vs_dynamic_time": figure_dir / "measured_vs_dynamic_prediction_time.png",
        "measured_vs_dynamic_scatter": figure_dir / "measured_vs_dynamic_prediction_scatter.png",
        "residual_time_by_model": figure_dir / "residual_time_by_model.png",
        "residual_histogram_by_model": figure_dir / "residual_histogram_by_model.png",
        "lag_search_rmse": figure_dir / "lag_search_rmse.png",
        "dynamic_prediction_by_trial_examples": figure_dir / "dynamic_prediction_by_trial_examples.png",
        "train_test_metric_comparison": figure_dir / "train_test_metric_comparison.png",
    }

    plot_measured_vs_dynamic_time(df, paths["measured_vs_dynamic_time"], stamp_text)
    plot_measured_vs_dynamic_scatter(df, paths["measured_vs_dynamic_scatter"], stamp_text)
    plot_residual_time_by_model(df, paths["residual_time_by_model"], stamp_text)
    plot_residual_histogram_by_model(df, paths["residual_histogram_by_model"], stamp_text)
    plot_lag_search_rmse(lag_search, paths["lag_search_rmse"], stamp_text)
    plot_dynamic_prediction_by_trial_examples(
        df,
        paths["dynamic_prediction_by_trial_examples"],
        stamp_text,
    )
    plot_train_test_metric_comparison(
        metrics,
        paths["train_test_metric_comparison"],
        stamp_text,
    )
    return paths


def plot_measured_vs_dynamic_time(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["ph_measured"].where(valid),
        color="#005f73",
        linewidth=1.25,
        label="measured PH_2 (model-valid)",
    )
    ax.plot(
        df["sample_index"],
        df["prediction_equilibrium_baseline"].where(valid),
        color=MODEL_COLORS["equilibrium_baseline"],
        linewidth=1.0,
        alpha=0.8,
        label="equilibrium baseline",
    )
    ax.plot(
        df["sample_index"],
        df["prediction_dynamic_first_order"].where(valid),
        color=MODEL_COLORS["dynamic_first_order"],
        linewidth=1.25,
        label="first-order dynamic",
    )
    mark_test_region(ax, df)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("Measured PH_2 versus dynamic model prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_measured_vs_dynamic_scatter(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"] & df["prediction_dynamic_first_order"].notna()
    fig, ax = plt.subplots(figsize=(8, 6.2))
    colors = df.loc[valid, "split"].map({"train": "#0a9396", "test": "#ae2012"})
    ax.scatter(
        df.loc[valid, "prediction_dynamic_first_order"],
        df.loc[valid, "ph_measured"],
        c=colors,
        alpha=0.65,
        s=26,
    )
    lo = min(
        df.loc[valid, "prediction_dynamic_first_order"].min(),
        df.loc[valid, "ph_measured"].min(),
    ) - 0.1
    hi = max(
        df.loc[valid, "prediction_dynamic_first_order"].max(),
        df.loc[valid, "ph_measured"].max(),
    ) + 0.1
    grid = np.linspace(lo, hi, 100)
    ax.plot(grid, grid, "--", color="0.35", linewidth=1.2)
    ax.scatter([], [], color="#0a9396", label="train")
    ax.scatter([], [], color="#ae2012", label="test")
    ax.set_xlabel("First-order dynamic prediction")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Dynamic prediction versus measured pH")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_residual_time_by_model(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    for key in [
        "equilibrium_baseline",
        "static_calibrated",
        "lag_calibrated",
        "dynamic_first_order",
    ]:
        ax.plot(
            df["sample_index"],
            df[RESIDUAL_COLUMNS[key]].where(valid),
            color=MODEL_COLORS[key],
            linewidth=1.0,
            alpha=0.85,
            label=MODEL_LABELS[key],
        )
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.axhspan(-0.2, 0.2, color="#94d2bd", alpha=0.16, label="+/- 0.2 pH")
    mark_test_region(ax, df)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("Residual, PH_2 - prediction")
    ax.set_title("Residuals over time by model stage")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", ncols=2)
    finalize_figure(fig, path, stamp_text)


def plot_residual_histogram_by_model(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))
    test = df["valid_for_model"] & df["split"].eq("test")
    bins = np.linspace(-1.2, 1.2, 45)
    for key in [
        "equilibrium_baseline",
        "static_calibrated",
        "lag_calibrated",
        "dynamic_first_order",
    ]:
        residual = df.loc[test, RESIDUAL_COLUMNS[key]].dropna()
        ax.hist(
            residual,
            bins=bins,
            histtype="step",
            linewidth=1.7,
            color=MODEL_COLORS[key],
            label=MODEL_LABELS[key],
        )
    ax.axvline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Test residual, PH_2 - prediction")
    ax.set_ylabel("Sample count")
    ax.set_title("Test residual distributions by model stage")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_lag_search_rmse(lag_search: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))
    for split, color in [("train", "#0a9396"), ("test", "#ae2012")]:
        subset = lag_search.loc[lag_search["split"] == split]
        ax.plot(
            subset["lag_samples"],
            subset["rmse"],
            marker="o",
            linewidth=1.6,
            color=color,
            label=f"{split} RMSE",
        )
    ax.set_xlabel("Integer lag in samples")
    ax.set_ylabel("RMSE (pH)")
    ax.set_title("Lag search for calibrated equilibrium prediction")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_dynamic_prediction_by_trial_examples(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    test_trials = (
        df.loc[df["split"].eq("test")]
        .groupby("trial_id")
        .size()
        .sort_values(ascending=False)
        .head(4)
        .index
        .tolist()
    )
    if not test_trials:
        test_trials = df.groupby("trial_id").size().sort_values(ascending=False).head(4).index.tolist()

    fig, axes = plt.subplots(len(test_trials), 1, figsize=(11, 3.0 * len(test_trials)), sharex=False)
    if len(test_trials) == 1:
        axes = [axes]

    for ax, trial_id in zip(axes, test_trials):
        group = df.loc[df["trial_id"] == trial_id]
        x = np.arange(len(group))
        ax.plot(x, group["ph_measured"], color="#005f73", marker="o", label="PH_2")
        ax.plot(
            x,
            group["prediction_equilibrium_baseline"],
            color=MODEL_COLORS["equilibrium_baseline"],
            marker="s",
            label="equilibrium",
        )
        ax.plot(
            x,
            group["prediction_dynamic_first_order"],
            color=MODEL_COLORS["dynamic_first_order"],
            marker="^",
            label="dynamic",
        )
        ax.set_title(f"Trial {int(trial_id)} ({group['split'].iloc[0]})")
        ax.set_ylabel("pH")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Sample within trial")
    axes[0].legend(loc="best", ncols=3)
    finalize_figure(fig, path, stamp_text)


def plot_train_test_metric_comparison(
    metrics: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    rmse = metrics.pivot(index="model_label", columns="split", values="rmse")
    order = [
        "Equilibrium baseline",
        "Static calibrated",
        "Lag calibrated",
        "First-order dynamic",
    ]
    rmse = rmse.reindex(order)
    x = np.arange(len(rmse.index))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.bar(x - width / 2, rmse["train"], width, color="#0a9396", label="train")
    ax.bar(x + width / 2, rmse["test"], width, color="#ae2012", label="test")
    ax.set_xticks(x)
    ax.set_xticklabels(rmse.index, rotation=20, ha="right")
    ax.set_ylabel("RMSE (pH)")
    ax.set_title("Train/test RMSE by model stage")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def mark_test_region(ax, df: pd.DataFrame) -> None:
    test = df.loc[df["split"].eq("test")]
    if test.empty:
        return
    x0 = test["sample_index"].min()
    x1 = test["sample_index"].max()
    ax.axvspan(x0, x1, color="#f4a261", alpha=0.08, label="test region")


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
