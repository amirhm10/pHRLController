from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulation.equilibrium_buffer_model import EquilibriumBufferModel
from simulation.simple_buffer_model import SimpleBufferModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
REPORT_PATH = Path("reports/lab_rl_controller_data_analysis.md")

PH1_COL = "observation.biosmb-sensors.PH_1"
PH2_COL = "observation.biosmb-sensors.PH_2"
ACID_FLOW_COL = "observation.biosmb-flows[0]"
ACETATE_FLOW_COL = "observation.biosmb-flows[1]"
WATER_FLOW_COL = "observation.biosmb-flows[2]"
FLOW_COLS = [ACID_FLOW_COL, ACETATE_FLOW_COL, WATER_FLOW_COL]
MASS_COLS = [
    "observation.mfcs-mass.acid-mass-grams",
    "observation.mfcs-mass.sodium-mass-grams",
    "observation.mfcs-mass.water-mass-grams",
]

METHOD_NAME = "lab_rl_controller_data_analysis"


def main() -> None:
    run_time = datetime.now()
    run_stamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_time_display = run_time.strftime("%Y-%m-%d %H:%M:%S")
    result_dir = Path("results") / f"{METHOD_NAME}_{run_stamp}"
    figure_dir = result_dir / "figures"
    table_dir = result_dir / "tables"
    figure_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_prepare_data(DATA_PATH)
    add_model_predictions(df)

    overview = make_overview(df)
    tracking_metrics = make_tracking_metrics(df)
    target_metrics = make_target_metrics(df)
    trial_metrics = make_trial_metrics(df)
    flow_metrics = make_flow_metrics(df)
    model_metrics = make_model_metrics(df)

    target_metrics.to_csv(table_dir / "tracking_metrics_by_target.csv", index=False)
    trial_metrics.to_csv(table_dir / "tracking_metrics_by_trial.csv", index=False)
    flow_metrics.to_csv(table_dir / "flow_summary.csv", index=False)
    model_metrics.to_csv(table_dir / "model_comparison_metrics.csv", index=False)

    stamp_text = f"method={METHOD_NAME} | run_time={run_time_display}"
    figure_paths = create_figures(df, figure_dir, stamp_text)
    write_report(
        df=df,
        result_dir=result_dir,
        figure_paths=figure_paths,
        overview=overview,
        tracking_metrics=tracking_metrics,
        target_metrics=target_metrics,
        trial_metrics=trial_metrics,
        flow_metrics=flow_metrics,
        model_metrics=model_metrics,
        run_time_display=run_time_display,
    )

    print("Lab RL controller data analysis completed.")
    print(f"Source data: {DATA_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Results: {result_dir}")
    print(f"Figures: {figure_dir}")
    print(f"Tables: {table_dir}")


def load_and_prepare_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.attrs["source_column_count"] = int(df.shape[1])
    df.attrs["source_missing_values"] = int(df.isna().sum().sum())
    df["utc_datetime"] = pd.to_datetime(df["utc_time"], utc=True)
    df = df.sort_values("utc_datetime").reset_index(drop=True)
    df["elapsed_min"] = (
        df["utc_datetime"] - df["utc_datetime"].iloc[0]
    ).dt.total_seconds() / 60.0
    df["elapsed_h"] = df["elapsed_min"] / 60.0
    df["dt_s"] = df["utc_datetime"].diff().dt.total_seconds()

    new_session = df["dt_s"].gt(900.0).fillna(True)
    df["session_id"] = new_session.cumsum().astype(int)

    previous_step = df["step_number"].shift()
    previous_episode = df["episode_number"].shift()
    new_trial = (
        new_session
        | df["step_number"].lt(previous_step)
        | df["episode_number"].lt(previous_episode)
    ).fillna(True)
    df["trial_id"] = new_trial.cumsum().astype(int)

    df["ph_error"] = df[PH2_COL] - df["target_ph"]
    df["abs_ph_error"] = df["ph_error"].abs()
    df["flow_ratio_acetate_to_acid"] = np.where(
        (df[ACID_FLOW_COL] > 0.0) & (df[ACETATE_FLOW_COL] > 0.0),
        df[ACETATE_FLOW_COL] / df[ACID_FLOW_COL],
        np.nan,
    )
    df["ideal_ratio_from_target"] = 10.0 ** (df["target_ph"] - 4.76)
    df["log10_ratio_error"] = (
        np.log10(df["flow_ratio_acetate_to_acid"])
        - np.log10(df["ideal_ratio_from_target"])
    )
    df["total_flow"] = df[FLOW_COLS].sum(axis=1)
    for col in FLOW_COLS:
        df[f"delta_{col}"] = df.groupby("trial_id")[col].diff()
    df["valid_buffer_flows"] = (df[FLOW_COLS] > 0.0).all(axis=1)
    return df


def add_model_predictions(df: pd.DataFrame) -> None:
    simple_model = SimpleBufferModel()
    equilibrium_model = EquilibriumBufferModel()
    simple_predictions = []
    equilibrium_predictions = []

    for acid_flow, acetate_flow, water_flow in df[FLOW_COLS].itertuples(index=False, name=None):
        if acid_flow <= 0.0 or acetate_flow <= 0.0 or water_flow <= 0.0:
            simple_predictions.append(np.nan)
            equilibrium_predictions.append(np.nan)
            continue
        simple_predictions.append(simple_model.predict_ph(acid_flow, acetate_flow, water_flow))
        equilibrium_predictions.append(
            equilibrium_model.predict_ph(acid_flow, acetate_flow, water_flow)
        )

    df["ph_simple_model"] = simple_predictions
    df["ph_equilibrium_model"] = equilibrium_predictions
    df["simple_model_error"] = df[PH2_COL] - df["ph_simple_model"]
    df["equilibrium_model_error"] = df[PH2_COL] - df["ph_equilibrium_model"]

    valid = df["ph_simple_model"].notna()
    if valid.any():
        x = df.loc[valid, "ph_simple_model"].to_numpy()
        y = df.loc[valid, PH2_COL].to_numpy()
        beta = np.linalg.lstsq(np.column_stack([np.ones_like(x), x]), y, rcond=None)[0]
        df["ph_simple_affine_fit"] = beta[0] + beta[1] * df["ph_simple_model"]
    else:
        df["ph_simple_affine_fit"] = np.nan


def make_overview(df: pd.DataFrame) -> dict:
    time_span_h = (
        df["utc_datetime"].iloc[-1] - df["utc_datetime"].iloc[0]
    ).total_seconds() / 3600.0
    duplicate_episode_steps = int(
        df.duplicated(["episode_number", "step_number"], keep=False).sum()
    )
    zero_flow_rows = int((df[FLOW_COLS] <= 0.0).any(axis=1).sum())
    return {
        "rows": int(len(df)),
        "source_columns": int(df.attrs.get("source_column_count", df.shape[1])),
        "analysis_columns": int(df.shape[1]),
        "start_time": str(df["utc_datetime"].iloc[0]),
        "end_time": str(df["utc_datetime"].iloc[-1]),
        "time_span_h": time_span_h,
        "unique_targets": int(df["target_ph"].nunique()),
        "session_count": int(df["session_id"].nunique()),
        "trial_count": int(df["trial_id"].nunique()),
        "source_missing_values": int(df.attrs.get("source_missing_values", 0)),
        "analysis_missing_values": int(df.isna().sum().sum()),
        "duplicate_episode_steps": duplicate_episode_steps,
        "zero_flow_rows": zero_flow_rows,
    }


def make_tracking_metrics(df: pd.DataFrame) -> dict:
    error = df["ph_error"]
    return {
        "mean_error": float(error.mean()),
        "std_error": float(error.std()),
        "mae": float(error.abs().mean()),
        "rmse": rmse(error),
        "iae": float(error.abs().sum()),
        "ise": float((error**2).sum()),
        "max_abs_error": float(error.abs().max()),
        "within_0p05": float((error.abs() <= 0.05).mean()),
        "within_0p10": float((error.abs() <= 0.10).mean()),
        "within_0p20": float((error.abs() <= 0.20).mean()),
        "within_0p50": float((error.abs() <= 0.50).mean()),
        "target_ph_corr": float(df["target_ph"].corr(df[PH2_COL])),
    }


def make_target_metrics(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("target_ph", sort=True)
    rows = []
    for target, group in grouped:
        error = group["ph_error"]
        rows.append(
            {
                "target_ph": float(target),
                "n": int(len(group)),
                "ph2_mean": float(group[PH2_COL].mean()),
                "ph2_std": float(group[PH2_COL].std()),
                "mean_error": float(error.mean()),
                "mae": float(error.abs().mean()),
                "rmse": rmse(error),
                "max_abs_error": float(error.abs().max()),
                "median_actual_ratio": float(group["flow_ratio_acetate_to_acid"].median()),
                "ideal_ratio": float(group["ideal_ratio_from_target"].iloc[0]),
                "median_log10_ratio_error": float(group["log10_ratio_error"].median()),
                "mean_acid_flow": float(group[ACID_FLOW_COL].mean()),
                "mean_acetate_flow": float(group[ACETATE_FLOW_COL].mean()),
                "mean_water_flow": float(group[WATER_FLOW_COL].mean()),
            }
        )
    return pd.DataFrame(rows)


def make_trial_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for trial_id, group in df.groupby("trial_id", sort=True):
        error = group["ph_error"]
        rows.append(
            {
                "trial_id": int(trial_id),
                "n": int(len(group)),
                "session_id": int(group["session_id"].iloc[0]),
                "episode_number": int(group["episode_number"].iloc[0]),
                "target_ph": float(group["target_ph"].iloc[0]),
                "start_time": str(group["utc_datetime"].iloc[0]),
                "end_time": str(group["utc_datetime"].iloc[-1]),
                "mean_error": float(error.mean()),
                "mae": float(error.abs().mean()),
                "rmse": rmse(error),
                "final_ph2": float(group[PH2_COL].iloc[-1]),
                "final_error": float(error.iloc[-1]),
                "median_actual_ratio": float(group["flow_ratio_acetate_to_acid"].median()),
            }
        )
    return pd.DataFrame(rows)


def make_flow_metrics(df: pd.DataFrame) -> pd.DataFrame:
    labels = {
        ACID_FLOW_COL: "acid_flow_0",
        ACETATE_FLOW_COL: "sodium_acetate_flow_1",
        WATER_FLOW_COL: "water_flow_2",
    }
    rows = []
    for col in FLOW_COLS:
        values = df[col]
        rows.append(
            {
                "stream": labels[col],
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "q25": float(values.quantile(0.25)),
                "median": float(values.median()),
                "q75": float(values.quantile(0.75)),
                "max": float(values.max()),
                "rows_below_1": int((values < 1.0).sum()),
                "rows_above_10": int((values > 10.0).sum()),
                "rows_at_zero": int((values <= 0.0).sum()),
                "total_abs_move": float(df[f"delta_{col}"].abs().sum()),
            }
        )
    return pd.DataFrame(rows)


def make_model_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model_col, error_col, name in [
        ("ph_simple_model", "simple_model_error", "simple_henderson_hasselbalch"),
        ("ph_equilibrium_model", "equilibrium_model_error", "equilibrium_charge_balance"),
        ("ph_simple_affine_fit", None, "affine_fit_from_simple_model"),
    ]:
        valid = df[model_col].notna()
        if not valid.any():
            continue
        error = df.loc[valid, PH2_COL] - df.loc[valid, model_col]
        rows.append(
            {
                "model": name,
                "n": int(valid.sum()),
                "mean_error_measured_minus_predicted": float(error.mean()),
                "mae": float(error.abs().mean()),
                "rmse": rmse(error),
                "correlation_with_ph2": float(df.loc[valid, PH2_COL].corr(df.loc[valid, model_col])),
            }
        )
    return pd.DataFrame(rows)


def create_figures(df: pd.DataFrame, figure_dir: Path, stamp_text: str) -> dict[str, Path]:
    figures = {}
    figures["sensor_check"] = plot_sensor_check(df, figure_dir / "sensor_check_ph1_vs_ph2.png", stamp_text)
    figures["tracking_overview"] = plot_tracking_overview(df, figure_dir / "tracking_overview.png", stamp_text)
    figures["target_summary"] = plot_target_summary(df, figure_dir / "target_vs_measured_summary.png", stamp_text)
    figures["error_by_target"] = plot_error_by_target(df, figure_dir / "tracking_error_by_target.png", stamp_text)
    figures["flows"] = plot_flows_and_ratio(df, figure_dir / "flows_and_ratio.png", stamp_text)
    figures["ratio_target"] = plot_ratio_target_map(df, figure_dir / "target_ratio_map.png", stamp_text)
    figures["model_scatter"] = plot_model_scatter(df, figure_dir / "model_prediction_vs_measured.png", stamp_text)
    figures["masses"] = plot_masses(df, figure_dir / "mass_readings.png", stamp_text)
    return figures


def plot_sensor_check(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.plot(df["elapsed_h"], df[PH1_COL], color="0.55", linewidth=1.4, label="PH_1, disconnected")
    ax.plot(df["elapsed_h"], df[PH2_COL], color="#006d77", linewidth=1.6, label="PH_2, valid")
    ax.plot(df["elapsed_h"], df["target_ph"], color="#f77f00", linewidth=1.2, alpha=0.85, label="target pH")
    ax.set_xlabel("Elapsed time (h)")
    ax.set_ylabel("pH")
    ax.set_title("pH sensor check")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_tracking_overview(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    x = np.arange(len(df))
    ax.plot(x, df["target_ph"], color="#f77f00", linewidth=1.3, label="target pH")
    ax.plot(x, df[PH2_COL], color="#005f73", linewidth=1.2, label="measured pH, PH_2")
    ax.fill_between(
        x,
        df["target_ph"] - 0.2,
        df["target_ph"] + 0.2,
        color="#f77f00",
        alpha=0.12,
        label="+/- 0.2 pH band",
    )
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("RL lab data tracking overview")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_target_summary(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    summary = df.groupby("target_ph", sort=True)[PH2_COL].agg(["mean", "std", "count"]).reset_index()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.errorbar(
        summary["target_ph"],
        summary["mean"],
        yerr=summary["std"],
        fmt="o",
        capsize=3,
        color="#005f73",
        ecolor="#94d2bd",
        label="PH_2 mean +/- std",
    )
    lo = min(df["target_ph"].min(), df[PH2_COL].min()) - 0.1
    hi = max(df["target_ph"].max(), df[PH2_COL].max()) + 0.1
    ax.plot([lo, hi], [lo, hi], "--", color="0.35", label="ideal target tracking")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Target pH")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Measured pH does not scale with target")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_error_by_target(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    targets = sorted(df["target_ph"].unique())
    data = [df.loc[df["target_ph"] == target, "ph_error"].to_numpy() for target in targets]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.boxplot(data, positions=targets, widths=0.055, showfliers=False)
    ax.axhline(0.0, color="0.25", linestyle="--", linewidth=1.2)
    ax.axhspan(-0.2, 0.2, color="#94d2bd", alpha=0.18, label="+/- 0.2 pH")
    ax.set_xlabel("Target pH")
    ax.set_ylabel("PH_2 - target pH")
    ax.set_title("Tracking error by target")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_flows_and_ratio(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    x = np.arange(len(df))
    axes[0].plot(x, df[ACID_FLOW_COL], label="flow 0: acetic acid", color="#ae2012")
    axes[0].plot(x, df[ACETATE_FLOW_COL], label="flow 1: sodium acetate", color="#0a9396")
    axes[0].plot(x, df[WATER_FLOW_COL], label="flow 2: Arium water", color="#005f73")
    axes[0].axhline(1.0, color="0.35", linestyle="--", linewidth=1.0, label="nominal 1-10 mL/min bounds")
    axes[0].axhline(10.0, color="0.35", linestyle="--", linewidth=1.0)
    axes[0].set_ylabel("Flowrate (mL/min)")
    axes[0].set_title("Commanded or observed flowrates")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best", ncols=2)

    axes[1].plot(x, df["flow_ratio_acetate_to_acid"], color="#0a9396", label="actual FA/FH")
    axes[1].plot(x, df["ideal_ratio_from_target"], color="#f77f00", alpha=0.8, label="ideal target ratio")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Chronological sample index")
    axes[1].set_ylabel("FA/FH")
    axes[1].set_title("Actual ratio versus Henderson-Hasselbalch target ratio")
    axes[1].grid(True, alpha=0.3, which="both")
    axes[1].legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_ratio_target_map(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["ideal_ratio_from_target"],
        df["flow_ratio_acetate_to_acid"],
        c=df["target_ph"],
        cmap="viridis",
        alpha=0.55,
        s=24,
    )
    lo = min(df["ideal_ratio_from_target"].min(), df["flow_ratio_acetate_to_acid"].min()) * 0.8
    hi = max(df["ideal_ratio_from_target"].max(), df["flow_ratio_acetate_to_acid"].max()) * 1.2
    ax.plot([lo, hi], [lo, hi], "--", color="0.35", label="actual = ideal")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Ideal FA/FH from target pH")
    ax.set_ylabel("Actual FA/FH from flows")
    ax.set_title("Target ratio was not consistently implemented by the controller")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(loc="best")
    cbar = fig.colorbar(ax.collections[0], ax=ax)
    cbar.set_label("Target pH")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_model_scatter(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    valid = df["ph_simple_model"].notna()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        df.loc[valid, "ph_simple_model"],
        df.loc[valid, PH2_COL],
        c=df.loc[valid, "target_ph"],
        cmap="viridis",
        alpha=0.6,
        s=24,
        label="samples",
    )
    lo = min(df.loc[valid, "ph_simple_model"].min(), df.loc[valid, PH2_COL].min()) - 0.1
    hi = max(df.loc[valid, "ph_simple_model"].max(), df.loc[valid, PH2_COL].max()) + 0.1
    grid = np.linspace(lo, hi, 100)
    ax.plot(grid, grid, "--", color="0.35", label="measured = model")
    ax.plot(
        df.loc[valid, "ph_simple_model"],
        df.loc[valid, "ph_simple_affine_fit"],
        ".",
        color="#ca6702",
        alpha=0.35,
        label="affine fit",
    )
    ax.set_xlabel("Simple-model pH from logged flows")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Measured pH is correlated with flow-ratio model but biased/compressed")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    cbar = fig.colorbar(ax.collections[0], ax=ax)
    cbar.set_label("Target pH")
    finalize_figure(fig, path, stamp_text)
    return path


def plot_masses(df: pd.DataFrame, path: Path, stamp_text: str) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    labels = ["acid mass", "sodium acetate mass", "water mass"]
    colors = ["#ae2012", "#0a9396", "#005f73"]
    for col, label, color in zip(MASS_COLS, labels, colors):
        ax.plot(df["elapsed_h"], df[col], label=label, color=color, linewidth=1.3)
    ax.set_xlabel("Elapsed time (h)")
    ax.set_ylabel("Mass reading (g)")
    ax.set_title("Reservoir mass readings")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize_figure(fig, path, stamp_text)
    return path


def write_report(
    df: pd.DataFrame,
    result_dir: Path,
    figure_paths: dict[str, Path],
    overview: dict,
    tracking_metrics: dict,
    target_metrics: pd.DataFrame,
    trial_metrics: pd.DataFrame,
    flow_metrics: pd.DataFrame,
    model_metrics: pd.DataFrame,
    run_time_display: str,
) -> None:
    best_targets = target_metrics.sort_values("mae").head(5)
    worst_targets = target_metrics.sort_values("mae", ascending=False).head(5)
    worst_trials = trial_metrics.sort_values("mae", ascending=False).head(8)
    model_simple = model_metrics.loc[
        model_metrics["model"] == "simple_henderson_hasselbalch"
    ].iloc[0]
    model_fit = model_metrics.loc[
        model_metrics["model"] == "affine_fit_from_simple_model"
    ].iloc[0]

    report = f"""# Lab RL Controller Data Analysis

Generated: {run_time_display}

Source data:

```text
{DATA_PATH}
```

Generated artifacts:

```text
{result_dir}
```

## Objective

Analyze the treated lab CSV from the RL controller test on the real inline pH setup. The operator note is treated as part of the experimental metadata:

- Only `PH_2` is considered a reliable pH measurement.
- `PH_1` was not connected during operation and is used only as a sensor-quality check.
- `observation.biosmb-flows[0]` is acetic acid, 100 mM.
- `observation.biosmb-flows[1]` is sodium acetate, 100 mM.
- `observation.biosmb-flows[2]` is Arium ultrapure water.
- The nominal flow range is 1-10 mL/min for each controlled stream.
- The immediate control objective is target-pH tracking for buffer preparation.

## Method Reconstruction

The relevant steady-state buffer relation is

$$
\\mathrm{{pH}} \\approx pK_a + \\log_{{10}}\\left(\\frac{{F_A}}{{F_H}}\\right),
$$

where `F_H` is the acetic-acid flow and `F_A` is the sodium-acetate flow. For a target pH,

$$
\\frac{{F_A}}{{F_H}} = 10^{{\\mathrm{{pH}}_{{sp}} - pK_a}}.
$$

The current analysis therefore checks two questions:

1. Did the logged actions choose flow ratios consistent with the target?
2. Did reliable measured pH, `PH_2`, track the target?

The CSV does not contain the RL policy internals, rewards, observations before action, actor output, or training losses. Therefore the controller can be evaluated only from logged target, flow, sensor, and mass trajectories.

## Dataset Summary

| Item | Value |
|---|---:|
| Rows | {overview["rows"]} |
| Raw CSV columns | {overview["source_columns"]} |
| Analysis columns after derived fields | {overview["analysis_columns"]} |
| Time span | {overview["time_span_h"]:.2f} h |
| Start time | {overview["start_time"]} |
| End time | {overview["end_time"]} |
| Unique targets | {overview["unique_targets"]} |
| Chronological sessions | {overview["session_count"]} |
| Chronological trials | {overview["trial_count"]} |
| Missing values in raw CSV | {overview["source_missing_values"]} |
| Missing values after derived columns | {overview["analysis_missing_values"]} |
| Rows sharing nonunique `(episode_number, step_number)` pairs | {overview["duplicate_episode_steps"]} |
| Rows with any zero flow among streams 0-2 | {overview["zero_flow_rows"]} |

`episode_number` and `step_number` are not globally unique in this combined file. The same episode and step numbers appear across separate lab runs. For this report, a derived `trial_id` was created whenever a long time gap or step reset was detected.

## Tracking Performance

Using `PH_2 - target_ph` as the tracking error:

| Metric | Value |
|---|---:|
| Mean error | {tracking_metrics["mean_error"]:.3f} pH |
| Error standard deviation | {tracking_metrics["std_error"]:.3f} pH |
| MAE | {tracking_metrics["mae"]:.3f} pH |
| RMSE | {tracking_metrics["rmse"]:.3f} pH |
| Max absolute error | {tracking_metrics["max_abs_error"]:.3f} pH |
| Fraction within 0.05 pH | {100 * tracking_metrics["within_0p05"]:.1f}% |
| Fraction within 0.10 pH | {100 * tracking_metrics["within_0p10"]:.1f}% |
| Fraction within 0.20 pH | {100 * tracking_metrics["within_0p20"]:.1f}% |
| Fraction within 0.50 pH | {100 * tracking_metrics["within_0p50"]:.1f}% |
| Correlation between target pH and PH_2 | {tracking_metrics["target_ph_corr"]:.3f} |

The strongest result is negative: measured pH did not track user-defined targets reliably. The mean measured pH stayed near the buffer midpoint for many target values. High targets were systematically too low, and low targets were systematically too high.

### Best Targets By MAE

{markdown_table(best_targets[["target_ph", "n", "ph2_mean", "mean_error", "mae", "rmse"]])}

### Worst Targets By MAE

{markdown_table(worst_targets[["target_ph", "n", "ph2_mean", "mean_error", "mae", "rmse"]])}

### Worst Chronological Trials By MAE

{markdown_table(worst_trials[["trial_id", "session_id", "episode_number", "target_ph", "n", "mae", "rmse", "final_error"]])}

## Flow and Ratio Behavior

The operator mapping gives:

| Logged flow | Physical stream |
|---|---|
| `observation.biosmb-flows[0]` | Acetic acid |
| `observation.biosmb-flows[1]` | Sodium acetate |
| `observation.biosmb-flows[2]` | Arium water |

Flow summary:

{markdown_table(flow_metrics)}

The nominal 1-10 mL/min bounds were respected except for one row where all three controlled flows were exactly zero. That row is likely startup, shutdown, communication, or a cleaned-data edge case and should be excluded from model fitting unless confirmed.

The actual acetate-to-acid ratio was not strongly aligned with the ideal ratio required by the target pH. This explains most of the tracking failure. For low-pH targets, the actual ratio was too high. For high-pH targets, the actual ratio was too low.

## Model Consistency

The steady-state model from the logged flows was compared to the valid pH sensor:

{markdown_table(model_metrics)}

The simple Henderson-Hasselbalch model and the charge-balance model are almost identical over these logged flow/concentration conditions. The measured pH was correlated with the model prediction from the current flow ratio, but it was biased and compressed:

- Simple-model correlation with `PH_2`: {model_simple["correlation_with_ph2"]:.3f}
- Simple-model raw RMSE against `PH_2`: {model_simple["rmse"]:.3f} pH
- Affine-corrected simple-model RMSE: {model_fit["rmse"]:.3f} pH

This means the data are chemically meaningful, but the controller actions were not target-consistent. A simple fitted calibration layer can explain much of the pH measurement from the flow ratio, but it does not solve the policy issue.

## Figures

### Sensor reliability

![pH sensor check]({relative_report_path(figure_paths["sensor_check"])})

`PH_1` is inconsistent with `PH_2` and should not be used for control metrics. This supports the operator note that only pH sensor 2 was connected correctly.

### Tracking overview

![Tracking overview]({relative_report_path(figure_paths["tracking_overview"])})

The target is varied across a wide range, but `PH_2` remains much more compressed.

### Target summary

![Target versus measured pH]({relative_report_path(figure_paths["target_summary"])})

The ideal line is not followed. Average measured pH is nearly flat relative to target.

### Error by target

![Tracking error by target]({relative_report_path(figure_paths["error_by_target"])})

Low targets tend to have positive error. High targets tend to have negative error.

### Flows and buffer ratio

![Flows and ratio]({relative_report_path(figure_paths["flows"])})

The actual ratio often differs from the Henderson-Hasselbalch ratio required by the target.

### Target-ratio map

![Target ratio map]({relative_report_path(figure_paths["ratio_target"])})

The controller did not consistently map target pH to the required acetate/acetic-acid ratio.

### Model prediction versus measured pH

![Model prediction versus measured pH]({relative_report_path(figure_paths["model_scatter"])})

The measured pH is strongly related to the current flow-ratio model, but with bias and compression.

### Reservoir masses

![Mass readings]({relative_report_path(figure_paths["masses"])})

Mass readings are useful for checking consumption and long-run continuity, but they were not used as a primary tracking metric here.

## Main Interpretation

This dataset is useful and internally meaningful, but it does not yet show successful target-conditioned pH control. The dominant issue appears to be controller action selection rather than the acetate-buffer chemistry model. The target pH has very weak correlation with the measured `PH_2`, while the flow-ratio model has a strong correlation with `PH_2`.

In practical terms, the controller often stayed near a ratio that produces pH around the buffer midpoint, instead of moving toward the much more acidic or acetate-rich ratios required for the target.

## Literature Connections

No local paper, PDF, or BibTeX reference files were found in this repository during the analysis. The interpretation therefore uses only the repository notes and the standard acetate-buffer relationship already documented in `reports/first_reports/`. If this report is later turned into a paper or slide deck, add verified citations for Henderson-Hasselbalch buffer modeling, pH process control, and target-conditioned RL before making literature claims.

## Bugs, Inconsistencies, Or Risks

- `PH_1` should be excluded from all control and reward calculations because the operator says it was not connected.
- `episode_number` and `step_number` repeat across lab sessions, so they cannot be treated as unique identifiers without adding a session or trial key.
- One row has all controlled flows equal to zero despite the nominal 1-10 mL/min operating range.
- The target pH is almost uncorrelated with the chosen flow ratio. This suggests either the RL policy was not target-conditioned correctly, the target was not included or scaled correctly in the state, the action mapping was wrong, or the logged flows were not the actual post-action commands intended by the policy.
- The current CSV does not include reward, action-before-clipping, action-after-clipping, policy output, or done flags, so root-cause diagnosis of the RL implementation is limited.

## Recommended Next Experiment

1. Run a deterministic open-loop target sweep before another RL test. Use `simulation.simple_buffer_model.SimpleBufferModel.flows_from_target()` to command flows for pH targets 3.8-5.7, hold each condition long enough for the sensor to settle, and log only `PH_2` as pH. This tests the physical mixing model without RL in the loop.
2. In the RL logger, add `target_ph`, normalized target, raw action, clipped action, final commanded flows, observed flows, `PH_2`, reward components, and any termination flags. The key metric is whether `log10(FA/FH)` moves approximately linearly with `target_ph - pKa`.
3. Add a simple safety/interlock rule before closed-loop collection: reject all-zero flows and enforce 1-10 mL/min unless the system is explicitly in startup or shutdown.
4. Fit a small calibration model using the lab data, such as `PH_2 = b_0 + b_1 * pH_model`, but only after separating transient samples from settled samples.
5. For the next RL experiment, compare against a model-based ratio controller. RL should only be considered an improvement if it beats this baseline on RMSE, MAE, final offset, chemical usage, and bound violations.

## Remaining Uncertainty

- The CSV does not state whether each flow row is the command applied before the pH measurement or the action computed after the observation.
- There may be unlogged disturbances, flushing periods, or operator interventions.
- The exact pH probe location and residence time are unknown, so the report does not estimate a physical transport delay.
- The data are labeled as treated, but the treatment rules are not included. Any cleaned-out lab disturbances should be documented next to the CSV.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


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


def rmse(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    return float(np.sqrt(np.nanmean(array**2)))


def relative_report_path(path: Path) -> str:
    return Path("..", path).as_posix()


def markdown_table(df: pd.DataFrame, digits: int = 3) -> str:
    rounded = df.copy()
    for col in rounded.columns:
        if pd.api.types.is_float_dtype(rounded[col]):
            rounded[col] = rounded[col].map(lambda value: f"{value:.{digits}f}")
    headers = [str(col) for col in rounded.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in rounded.iterrows():
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
