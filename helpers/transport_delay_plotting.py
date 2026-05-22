from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_COLORS = {
    "equilibrium_baseline": "#8d99ae",
    "static_calibrated": "#0a9396",
    "transport_delay_calibrated": "#ee9b00",
    "transport_delay_dynamic": "#ae2012",
}

MODEL_LABELS = {
    "equilibrium_baseline": "Equilibrium baseline",
    "static_calibrated": "Static calibrated",
    "transport_delay_calibrated": "Transport-delay calibrated",
    "transport_delay_dynamic": "Transport-delay plus first-order",
}

PREDICTION_COLUMNS = {
    "equilibrium_baseline": "prediction_equilibrium_baseline",
    "static_calibrated": "prediction_static_calibrated",
    "transport_delay_calibrated": "prediction_transport_delay_calibrated",
    "transport_delay_dynamic": "prediction_transport_delay_dynamic",
}

RESIDUAL_COLUMNS = {
    "equilibrium_baseline": "residual_equilibrium_baseline",
    "static_calibrated": "residual_static_calibrated",
    "transport_delay_calibrated": "residual_transport_delay_calibrated",
    "transport_delay_dynamic": "residual_transport_delay_dynamic",
}


def create_transport_delay_figures(
    df: pd.DataFrame,
    metrics: pd.DataFrame,
    search: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "transport_delay_rmse_search": figure_dir / "transport_delay_rmse_search.png",
        "measured_vs_transport_delay_time": (
            figure_dir / "measured_vs_transport_delay_prediction_time.png"
        ),
        "measured_vs_transport_delay_scatter": (
            figure_dir / "measured_vs_transport_delay_prediction_scatter.png"
        ),
        "transport_delay_residual_time": figure_dir / "transport_delay_residual_time.png",
        "transport_delay_residual_histogram": (
            figure_dir / "transport_delay_residual_histogram.png"
        ),
        "theta_transport_time": figure_dir / "theta_transport_time.png",
        "total_flow_cumulative_volume": (
            figure_dir / "total_flow_cumulative_volume.png"
        ),
        "transport_delay_trial_examples": (
            figure_dir / "transport_delay_trial_examples.png"
        ),
        "transport_delay_metric_comparison": (
            figure_dir / "transport_delay_metric_comparison.png"
        ),
    }

    plot_transport_delay_rmse_search(
        search,
        paths["transport_delay_rmse_search"],
        stamp_text,
    )
    plot_measured_vs_transport_delay_time(
        df,
        paths["measured_vs_transport_delay_time"],
        stamp_text,
    )
    plot_measured_vs_transport_delay_scatter(
        df,
        paths["measured_vs_transport_delay_scatter"],
        stamp_text,
    )
    plot_transport_delay_residual_time(
        df,
        paths["transport_delay_residual_time"],
        stamp_text,
    )
    plot_transport_delay_residual_histogram(
        df,
        paths["transport_delay_residual_histogram"],
        stamp_text,
    )
    plot_theta_transport_time(df, paths["theta_transport_time"], stamp_text)
    plot_total_flow_cumulative_volume(
        df,
        paths["total_flow_cumulative_volume"],
        stamp_text,
    )
    plot_transport_delay_trial_examples(
        df,
        paths["transport_delay_trial_examples"],
        stamp_text,
    )
    plot_transport_delay_metric_comparison(
        metrics,
        paths["transport_delay_metric_comparison"],
        stamp_text,
    )
    return paths


def plot_transport_delay_rmse_search(
    search: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))
    grid = search.loc[search["candidate_type"].eq("grid")]
    for split, color in [("train", "#0a9396"), ("test", "#ae2012")]:
        subset = grid.loc[grid["split"].eq(split)].sort_values("v_tube_ml")
        ax.plot(
            subset["v_tube_ml"],
            subset["rmse"],
            color=color,
            linewidth=1.7,
            label=f"{split} grid RMSE",
        )
    refined = search.loc[search["candidate_type"].eq("refined")]
    for split, color in [("train", "#0a9396"), ("test", "#ae2012")]:
        subset = refined.loc[refined["split"].eq(split)]
        ax.scatter(
            subset["v_tube_ml"],
            subset["rmse"],
            color=color,
            marker="*",
            s=170,
            edgecolor="black",
            linewidth=0.6,
            label=f"{split} refined",
        )
    ax.set_xlabel("Effective transport volume, V_tube (mL)")
    ax.set_ylabel("RMSE (pH)")
    ax.set_title("Transport-delay volume search")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_measured_vs_transport_delay_time(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    valid = df["valid_for_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["ph_measured"].where(valid),
        color="#005f73",
        linewidth=1.25,
        label="measured PH_2",
    )
    for key in [
        "equilibrium_baseline",
        "static_calibrated",
        "transport_delay_calibrated",
        "transport_delay_dynamic",
    ]:
        ax.plot(
            df["sample_index"],
            df[PREDICTION_COLUMNS[key]].where(valid),
            color=MODEL_COLORS[key],
            linewidth=1.05,
            alpha=0.86,
            label=MODEL_LABELS[key],
        )
    mark_flat_trial_regions(ax, df)
    mark_test_region(ax, df)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("Measured PH_2 versus transport-delay model predictions")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", ncols=2)
    finalize_figure(fig, path, stamp_text)


def plot_measured_vs_transport_delay_scatter(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    prediction_col = "prediction_transport_delay_calibrated"
    valid = df["valid_for_model"] & df[prediction_col].notna()
    fig, ax = plt.subplots(figsize=(8, 6.2))
    colors = df.loc[valid, "split"].map({"train": "#0a9396", "test": "#ae2012"})
    ax.scatter(
        df.loc[valid, prediction_col],
        df.loc[valid, "ph_measured"],
        c=colors,
        alpha=0.65,
        s=26,
    )
    lo = min(df.loc[valid, prediction_col].min(), df.loc[valid, "ph_measured"].min()) - 0.1
    hi = max(df.loc[valid, prediction_col].max(), df.loc[valid, "ph_measured"].max()) + 0.1
    grid = np.linspace(lo, hi, 100)
    ax.plot(grid, grid, "--", color="0.35", linewidth=1.2)
    ax.scatter([], [], color="#0a9396", label="train")
    ax.scatter([], [], color="#ae2012", label="test")
    ax.set_xlabel("Transport-delay prediction")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Transport-delay prediction versus measured pH")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_transport_delay_residual_time(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    valid = df["valid_for_model"].astype(bool)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    for key in [
        "equilibrium_baseline",
        "static_calibrated",
        "transport_delay_calibrated",
        "transport_delay_dynamic",
    ]:
        ax.plot(
            df["sample_index"],
            df[RESIDUAL_COLUMNS[key]].where(valid),
            color=MODEL_COLORS[key],
            linewidth=1.0,
            alpha=0.86,
            label=MODEL_LABELS[key],
        )
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.0)
    ax.axhspan(-0.2, 0.2, color="#94d2bd", alpha=0.16, label="+/- 0.2 pH")
    mark_test_region(ax, df)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("Residual, PH_2 - prediction")
    ax.set_title("Transport-delay residuals over time")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", ncols=2)
    finalize_figure(fig, path, stamp_text)


def plot_transport_delay_residual_histogram(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.8))
    test = df["valid_for_model"] & df["split"].eq("test")
    bins = np.linspace(-1.2, 1.2, 45)
    for key in [
        "equilibrium_baseline",
        "static_calibrated",
        "transport_delay_calibrated",
        "transport_delay_dynamic",
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
    ax.set_title("Test residual distributions")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_theta_transport_time(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    valid = df["valid_for_model"].astype(bool)
    theta = df["theta_transport_s"].where(valid)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(df["sample_index"], theta, color="#5f0f40", linewidth=1.2)
    if theta.notna().any():
        ax.axhline(
            theta.dropna().median(),
            color="0.25",
            linestyle="--",
            linewidth=1.0,
            label="median theta",
        )
    mark_test_region(ax, df)
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("theta_transport (s)")
    ax.set_title("Time-varying transport delay implied by fitted V_tube")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def plot_total_flow_cumulative_volume(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True)
    axes[0].plot(
        df["sample_index"],
        df["total_flow"],
        color="#005f73",
        linewidth=1.1,
    )
    axes[0].set_ylabel("Total flow (mL/min)")
    axes[0].set_title("Total flow and within-trial cumulative transported volume")
    axes[1].plot(
        df["sample_index"],
        df["cumulative_transport_volume_ml"],
        color="#ee9b00",
        linewidth=1.1,
    )
    axes[1].set_ylabel("Cumulative volume (mL)")
    axes[1].set_xlabel("Chronological sample index")
    for ax in axes:
        mark_test_region(ax, df)
        ax.grid(True, alpha=0.3)
    finalize_figure(fig, path, stamp_text)


def plot_transport_delay_trial_examples(
    df: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    trial_ids = select_trial_examples(df)
    fig, axes = plt.subplots(len(trial_ids), 1, figsize=(12, 3.4 * len(trial_ids)))
    if len(trial_ids) == 1:
        axes = [axes]

    for ax, trial_id in zip(axes, trial_ids):
        group = df.loc[df["trial_id"] == trial_id]
        x = np.arange(len(group))
        valid = group["valid_for_model"].astype(bool)
        ax.plot(x, group["ph_measured"], color="#005f73", marker="o", label="PH_2")
        ax.plot(
            x,
            group["ph_equilibrium_charge_balance"].where(valid),
            color=MODEL_COLORS["equilibrium_baseline"],
            marker="s",
            label="undelayed pH_eq",
        )
        ax.plot(
            x,
            group["ph_equilibrium_transport_delayed"].where(valid),
            color=MODEL_COLORS["transport_delay_calibrated"],
            marker="^",
            label="volume-delayed pH_eq",
        )
        ax.plot(
            x,
            group["prediction_transport_delay_calibrated"].where(valid),
            color=MODEL_COLORS["transport_delay_dynamic"],
            marker="d",
            label="transport prediction",
        )
        ax.set_title(f"Trial {int(trial_id)} delayed chemistry diagnostic")
        ax.set_ylabel("pH")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Sample within trial")
    axes[0].legend(loc="best", ncols=4)
    finalize_figure(fig, path, stamp_text)


def plot_transport_delay_metric_comparison(
    metrics: pd.DataFrame,
    path: Path,
    stamp_text: str,
) -> None:
    rmse = metrics.pivot(index="model_label", columns="split", values="rmse")
    order = [
        "Equilibrium baseline",
        "Static calibrated",
        "Transport-delay calibrated",
        "Transport-delay plus first-order",
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
    ax.set_title("Train/test RMSE by transport-delay model stage")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)


def select_trial_examples(df: pd.DataFrame) -> list[int]:
    test_trials = (
        df.loc[df["split"].eq("test")]
        .groupby("trial_id")
        .size()
        .sort_values(ascending=False)
        .head(3)
        .index.astype(int)
        .tolist()
    )
    train_trials = (
        df.loc[df["split"].eq("train")]
        .groupby("trial_id")
        .size()
        .sort_values(ascending=False)
        .head(1)
        .index.astype(int)
        .tolist()
    )
    trial_ids = train_trials + test_trials
    if trial_ids:
        return trial_ids[:4]
    return df["trial_id"].dropna().astype(int).head(1).tolist()


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
    fig.savefig(path, dpi=220)
    plt.close(fig)
