from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import ScalarFormatter

from helpers.first_principles_improvement import ModelStage
from helpers.first_principles_improvement_plotting import finalize
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel
from simulation.simple_buffer_model import SimpleBufferModel


EQUILIBRIUM_MAIN_STAGES = [
    ModelStage("equilibrium_raw", "Raw equilibrium", "prediction_equilibrium_raw"),
    ModelStage("equilibrium_bias", "Equilibrium + bias", "prediction_equilibrium_bias"),
    ModelStage("equilibrium_affine", "Equilibrium affine", "prediction_equilibrium_affine"),
]


def select_equilibrium_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
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
        "buffer_flow_fraction",
        "valid_for_model",
        "valid_for_model_before_flat_trial_filter",
        "uninformative_flat_ph_trial",
        "flow_ratio_acetate_acid",
        "log10_molar_base_acid_ratio",
        "acid_analytical_mol_l",
        "acetate_analytical_mol_l",
        "total_buffer_mol_l",
        "sodium_mol_l",
        "ph_equilibrium_charge_balance",
    ]
    for stage in EQUILIBRIUM_MAIN_STAGES:
        columns.append(stage.prediction_col)
        columns.append(f"residual_{stage.key}")
    return df[columns].copy()


def extract_equilibrium_calibration(parameters: pd.DataFrame) -> dict[str, float | int]:
    subset = parameters.loc[parameters["model_stage"].eq("equilibrium_affine")]
    intercept = parameter_value(subset, "intercept")
    slope = parameter_value(subset, "coefficient_ph_equilibrium_charge_balance")
    n_fit = int(subset["n_fit"].dropna().iloc[0]) if not subset.empty else 0
    return {
        "intercept": float(intercept),
        "slope": float(slope),
        "n_fit": int(n_fit),
    }


def make_calibration_table(
    parameters: pd.DataFrame,
    calibration: dict[str, float | int],
) -> pd.DataFrame:
    source = parameters.loc[parameters["model_stage"].isin([
        "equilibrium_bias",
        "equilibrium_affine",
    ])].copy()
    summary_rows = [
        {
            "model_stage": "equilibrium_affine_summary",
            "model_label": "Equilibrium affine summary",
            "parameter": "equation",
            "value": np.nan,
            "feature": "PH_2 = b0 + b1 * pH_eq",
            "n_fit": int(calibration["n_fit"]),
            "fit_method": "ordinary_least_squares",
            "condition_number": np.nan,
        },
        {
            "model_stage": "equilibrium_affine_summary",
            "model_label": "Equilibrium affine summary",
            "parameter": "b0_intercept",
            "value": float(calibration["intercept"]),
            "feature": "intercept",
            "n_fit": int(calibration["n_fit"]),
            "fit_method": "ordinary_least_squares",
            "condition_number": np.nan,
        },
        {
            "model_stage": "equilibrium_affine_summary",
            "model_label": "Equilibrium affine summary",
            "parameter": "b1_slope",
            "value": float(calibration["slope"]),
            "feature": "ph_equilibrium_charge_balance",
            "n_fit": int(calibration["n_fit"]),
            "fit_method": "ordinary_least_squares",
            "condition_number": np.nan,
        },
    ]
    return pd.concat([source, pd.DataFrame(summary_rows)], ignore_index=True)


def parameter_value(parameters: pd.DataFrame, name: str) -> float:
    values = parameters.loc[parameters["parameter"].eq(name), "value"]
    if values.empty:
        return np.nan
    return float(values.iloc[0])


def make_generated_pump_grid(
    config: PHProcessConfig,
    model: EquilibriumChargeBalanceModel,
    calibration: dict[str, float | int],
    points_per_axis: int = 10,
) -> pd.DataFrame:
    acid_values = np.linspace(config.acid_flow_min, config.acid_flow_max, points_per_axis)
    acetate_values = np.linspace(
        config.acetate_flow_min,
        config.acetate_flow_max,
        points_per_axis,
    )
    water_values = np.linspace(config.water_flow_min, config.water_flow_max, points_per_axis)

    rows = []
    for acid_flow in acid_values:
        for acetate_flow in acetate_values:
            for water_flow in water_values:
                rows.append(
                    generated_row(
                        model=model,
                        calibration=calibration,
                        acid_flow=acid_flow,
                        acetate_flow=acetate_flow,
                        water_flow=water_flow,
                    )
                )
    return pd.DataFrame(rows)


def make_generated_target_flow_sweep(
    config: PHProcessConfig,
    model: EquilibriumChargeBalanceModel,
    calibration: dict[str, float | int],
    target_points: int = 41,
    water_flows: tuple[float, ...] | None = None,
) -> pd.DataFrame:
    water_flows = water_flows or (
        config.water_flow_min,
        config.default_water_flow,
        config.water_flow_max,
    )
    simple_model = SimpleBufferModel(config)
    target_values = np.linspace(config.target_ph_min, config.target_ph_max, target_points)

    rows = []
    for water_flow in water_flows:
        for target_ph in target_values:
            allocation = simple_model.flows_from_target(
                target_ph,
                water_flow=water_flow,
                buffer_flow_sum=config.default_buffer_flow_sum,
                clip=True,
            )
            row = generated_row(
                model=model,
                calibration=calibration,
                acid_flow=allocation["acid_flow"],
                acetate_flow=allocation["acetate_flow"],
                water_flow=allocation["water_flow"],
            )
            row.update({
                "target_ph_requested": float(allocation["target_ph_requested"]),
                "target_ph_used": float(allocation["target_ph_used"]),
                "hh_ratio": float(allocation["ratio"]),
                "ph_henderson_hasselbalch": float(allocation["predicted_ph"]),
                "ph_eq_minus_target": row["ph_equilibrium_charge_balance"]
                - float(allocation["target_ph_used"]),
                "ph_affine_minus_target": row["ph_equilibrium_affine"]
                - float(allocation["target_ph_used"]),
                "allocation_model": allocation["model"],
            })
            rows.append(row)
    return pd.DataFrame(rows)


def generated_row(
    model: EquilibriumChargeBalanceModel,
    calibration: dict[str, float | int],
    acid_flow: float,
    acetate_flow: float,
    water_flow: float,
) -> dict[str, float]:
    concentrations = model.mixed_concentrations(acid_flow, acetate_flow, water_flow)
    ph_eq = model.predict_ph(acid_flow, acetate_flow, water_flow)
    ph_affine = float(calibration["intercept"] + calibration["slope"] * ph_eq)
    total_flow = concentrations["total_flow"]
    return {
        "acid_flow": float(acid_flow),
        "acetate_flow": float(acetate_flow),
        "water_flow": float(water_flow),
        "total_flow": float(total_flow),
        "flow_ratio_acetate_acid": float(acetate_flow / acid_flow),
        "log10_flow_ratio_acetate_acid": float(np.log10(acetate_flow / acid_flow)),
        "water_fraction": float(water_flow / total_flow),
        "buffer_flow_fraction": float((acid_flow + acetate_flow) / total_flow),
        "acid_analytical_mol_l": concentrations["acid_analytical_mol_l"],
        "acetate_analytical_mol_l": concentrations["acetate_analytical_mol_l"],
        "total_buffer_mol_l": concentrations["total_buffer_mol_l"],
        "sodium_mol_l": concentrations["sodium_mol_l"],
        "ph_equilibrium_charge_balance": float(ph_eq),
        "ph_equilibrium_affine": ph_affine,
    }


def make_generated_grid_summary(
    pump_grid: pd.DataFrame,
    target_sweep: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    rows.append(summarize_generated_frame(pump_grid, "pump_grid", "all"))
    for water_flow, group in pump_grid.groupby("water_flow", sort=True):
        rows.append(
            summarize_generated_frame(
                group,
                "pump_grid",
                f"water_flow={water_flow:.3g}",
            )
        )
    rows.append(summarize_generated_frame(target_sweep, "target_flow_sweep", "all"))
    for water_flow, group in target_sweep.groupby("water_flow", sort=True):
        rows.append(
            summarize_generated_frame(
                group,
                "target_flow_sweep",
                f"water_flow={water_flow:.3g}",
            )
        )
    return pd.DataFrame(rows)


def summarize_generated_frame(
    df: pd.DataFrame,
    source: str,
    group: str,
) -> dict[str, float | str | int]:
    row: dict[str, float | str | int] = {
        "source": source,
        "group": group,
        "n": int(len(df)),
    }
    for column in [
        "acid_flow",
        "acetate_flow",
        "water_flow",
        "total_flow",
        "water_fraction",
        "total_buffer_mol_l",
        "ph_equilibrium_charge_balance",
        "ph_equilibrium_affine",
    ]:
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        row[f"{column}_min"] = float(values.min()) if len(values) else np.nan
        row[f"{column}_mean"] = float(values.mean()) if len(values) else np.nan
        row[f"{column}_max"] = float(values.max()) if len(values) else np.nan
    return row


def create_equilibrium_main_figures(
    lab_df: pd.DataFrame,
    lab_metrics: pd.DataFrame,
    pump_grid: pd.DataFrame,
    target_sweep: pd.DataFrame,
    figure_dir: str | Path,
    stamp_text: str,
) -> dict[str, Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "lab_validation_time": figure_dir / "lab_equilibrium_validation_time.png",
        "lab_validation_scatter": figure_dir / "lab_equilibrium_validation_scatter.png",
        "lab_residuals": figure_dir / "lab_equilibrium_residuals.png",
        "lab_train_test_rmse": figure_dir / "lab_equilibrium_train_test_rmse.png",
        "pump_grid_heatmaps": figure_dir / "generated_pump_grid_heatmaps.png",
        "target_flow_sweep": figure_dir / "generated_target_flow_sweep.png",
        "water_dilution_sensitivity": figure_dir / "generated_water_dilution_sensitivity.png",
    }
    plot_lab_validation_time(lab_df, paths["lab_validation_time"], stamp_text)
    plot_lab_validation_scatter(lab_df, paths["lab_validation_scatter"], stamp_text)
    plot_lab_residuals(lab_df, paths["lab_residuals"], stamp_text)
    plot_lab_train_test_rmse(lab_metrics, paths["lab_train_test_rmse"], stamp_text)
    plot_pump_grid_heatmaps(pump_grid, paths["pump_grid_heatmaps"], stamp_text)
    plot_target_flow_sweep(target_sweep, paths["target_flow_sweep"], stamp_text)
    plot_water_dilution_sensitivity(
        pump_grid,
        paths["water_dilution_sensitivity"],
        stamp_text,
    )
    return paths


def plot_lab_validation_time(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(
        df["sample_index"],
        df["ph_measured"],
        color="#005f73",
        linewidth=1.15,
        label="measured PH_2",
    )
    mask = df["valid_for_model"]
    ax.plot(
        df.loc[mask, "sample_index"],
        df.loc[mask, "prediction_equilibrium_raw"],
        color="#ae2012",
        linewidth=1.1,
        label="raw equilibrium",
    )
    ax.plot(
        df.loc[mask, "sample_index"],
        df.loc[mask, "prediction_equilibrium_affine"],
        color="#0a9396",
        linewidth=1.1,
        label="affine calibrated equilibrium",
    )
    excluded = df["valid_for_model_before_flat_trial_filter"] & ~df["valid_for_model"]
    ax.scatter(
        df.loc[excluded, "sample_index"],
        df.loc[excluded, "ph_measured"],
        color="#8d99ae",
        s=20,
        label="excluded flat-pH rows",
        zorder=3,
    )
    ax.set_xlabel("Chronological sample index")
    ax.set_ylabel("pH")
    ax.set_title("Lab PH_2 against equilibrium core predictions")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_lab_validation_scatter(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    mask = df["valid_for_model"] & df["ph_equilibrium_charge_balance"].notna()
    fig, ax = plt.subplots(figsize=(7.5, 6.3))
    colors = df.loc[mask, "split"].map({"train": "#0a9396", "test": "#ae2012"})
    ax.scatter(
        df.loc[mask, "ph_equilibrium_charge_balance"],
        df.loc[mask, "ph_measured"],
        c=colors,
        alpha=0.68,
        s=26,
    )
    lo = min(
        df.loc[mask, "ph_equilibrium_charge_balance"].min(),
        df.loc[mask, "ph_measured"].min(),
    ) - 0.1
    hi = max(
        df.loc[mask, "ph_equilibrium_charge_balance"].max(),
        df.loc[mask, "ph_measured"].max(),
    ) + 0.1
    grid = np.linspace(lo, hi, 100)
    intercept, slope = fit_display_line(
        df.loc[mask, "ph_equilibrium_charge_balance"],
        df.loc[mask, "ph_measured"],
    )
    ax.plot(grid, grid, "--", color="0.35", linewidth=1.0, label="identity")
    ax.plot(
        grid,
        intercept + slope * grid,
        color="#0a9396",
        linewidth=1.4,
        label="all-row affine trend",
    )
    ax.scatter([], [], color="#0a9396", label="train")
    ax.scatter([], [], color="#ae2012", label="test")
    ax.set_xlabel("Raw equilibrium pH")
    ax.set_ylabel("Measured PH_2")
    ax.set_title("Measured PH_2 versus raw equilibrium pH")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def fit_display_line(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    values = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(values) < 2:
        return np.nan, np.nan
    intercept, slope = np.linalg.lstsq(
        np.column_stack([np.ones(len(values)), values["x"]]),
        values["y"],
        rcond=None,
    )[0]
    return float(intercept), float(slope)


def plot_lab_residuals(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    features = [
        ("sample_index", "sample index"),
        ("log10_molar_base_acid_ratio", "log10 acetate/acid flow ratio"),
        ("water_fraction", "water fraction"),
        ("total_buffer_mol_l", "total buffer concentration (mol/L)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2))
    mask = df["valid_for_model"] & df["residual_equilibrium_affine"].notna()
    for ax, (feature, label) in zip(axes.ravel(), features):
        ax.scatter(
            df.loc[mask, feature],
            df.loc[mask, "residual_equilibrium_raw"],
            color="#ae2012",
            alpha=0.48,
            s=18,
            label="raw",
        )
        ax.scatter(
            df.loc[mask, feature],
            df.loc[mask, "residual_equilibrium_affine"],
            color="#0a9396",
            alpha=0.58,
            s=18,
            label="affine",
        )
        ax.axhline(0.0, color="0.25", linestyle="--", linewidth=0.9)
        ax.set_xlabel(label)
        ax.set_ylabel("PH_2 - prediction")
        ax.grid(True, alpha=0.25)
    axes[0, 0].legend(loc="best")
    fig.suptitle("Equilibrium residuals before and after empirical calibration")
    finalize(fig, path, stamp_text)


def plot_lab_train_test_rmse(metrics: pd.DataFrame, path: Path, stamp_text: str) -> None:
    subset = metrics.loc[metrics["split"].isin(["train", "test"])].copy()
    pivot = subset.pivot(index="model_label", columns="split", values="rmse")
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    x = np.arange(len(pivot.index))
    width = 0.36
    ax.bar(x - width / 2, pivot.get("train"), width, color="#0a9396", label="train")
    ax.bar(x + width / 2, pivot.get("test"), width, color="#ae2012", label="test")
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=20, ha="right")
    ax.set_ylabel("RMSE (pH)")
    ax.set_title("Equilibrium main-model train/test RMSE")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_pump_grid_heatmaps(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    water_slices = nearest_available_values(df["water_flow"], [1.0, 5.0, 10.0])
    fig, axes = plt.subplots(
        1,
        len(water_slices) + 1,
        figsize=(14.4, 4.9),
        sharey=False,
        gridspec_kw={"width_ratios": [1.0] * len(water_slices) + [0.06]},
    )
    map_axes = axes[:-1]
    color_axis = axes[-1]
    vmin = float(df["ph_equilibrium_charge_balance"].min())
    vmax = float(df["ph_equilibrium_charge_balance"].max())
    image = None
    for ax, water_flow in zip(map_axes, water_slices):
        subset = df.loc[np.isclose(df["water_flow"], water_flow)]
        pivot = subset.pivot(
            index="acetate_flow",
            columns="acid_flow",
            values="ph_equilibrium_charge_balance",
        ).sort_index()
        image = ax.imshow(
            pivot.values,
            origin="lower",
            aspect="auto",
            cmap="viridis",
            vmin=vmin,
            vmax=vmax,
            extent=[
                float(pivot.columns.min()),
                float(pivot.columns.max()),
                float(pivot.index.min()),
                float(pivot.index.max()),
            ],
        )
        ax.set_title(f"water={water_flow:.1f} mL/min")
        ax.set_xlabel("acid flow (mL/min)")
        ax.set_ylabel("acetate flow (mL/min)")
    if image is not None:
        fig.colorbar(image, cax=color_axis, label="raw equilibrium pH")
    fig.suptitle("Generated pump-grid equilibrium pH")
    finalize(fig, path, stamp_text)


def nearest_available_values(series: pd.Series, targets: list[float]) -> list[float]:
    values = np.asarray(sorted(pd.unique(series)), dtype=float)
    selected = []
    for target in targets:
        value = float(values[np.argmin(np.abs(values - target))])
        if value not in selected:
            selected.append(value)
    return selected


def plot_target_flow_sweep(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.6))
    default_water = nearest_available_values(df["water_flow"], [5.0])[0]
    flow_slice = df.loc[np.isclose(df["water_flow"], default_water)]
    axes[0].plot(
        flow_slice["target_ph_used"],
        flow_slice["acid_flow"],
        color="#ae2012",
        linewidth=1.9,
        label="acid",
    )
    axes[0].plot(
        flow_slice["target_ph_used"],
        flow_slice["acetate_flow"],
        color="#0a9396",
        linewidth=1.9,
        label="acetate",
    )
    axes[0].plot(
        flow_slice["target_ph_used"],
        flow_slice["water_flow"],
        color="#ee9b00",
        linewidth=1.9,
        label="water",
    )
    axes[0].set_xlabel("target pH used")
    axes[0].set_ylabel("flowrate (mL/min)")
    axes[0].set_title(f"Flow allocation at water={default_water:.1f} mL/min")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    for water_flow, group in df.groupby("water_flow", sort=True):
        axes[1].plot(
            group["target_ph_used"],
            group["ph_equilibrium_charge_balance"],
            linewidth=1.7,
            label=f"raw, water={water_flow:.1f}",
        )
    axes[1].plot(
        df["target_ph_used"].sort_values().unique(),
        df["target_ph_used"].sort_values().unique(),
        "--",
        color="0.35",
        linewidth=1.0,
        label="target",
    )
    axes[1].set_xlabel("target pH used")
    axes[1].set_ylabel("predicted pH")
    axes[1].set_title("Equilibrium prediction from target-flow allocation")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")
    finalize(fig, path, stamp_text)


def plot_water_dilution_sensitivity(df: pd.DataFrame, path: Path, stamp_text: str) -> None:
    candidates = df.loc[
        np.isclose(df["acid_flow"], 5.0) & np.isclose(df["acetate_flow"], 5.0)
    ].sort_values("water_flow")
    if candidates.empty:
        midpoint = df.iloc[
            ((df["acid_flow"] - 5.0).abs() + (df["acetate_flow"] - 5.0).abs())
            .sort_values()
            .index[:1]
        ][["acid_flow", "acetate_flow"]].iloc[0]
        candidates = df.loc[
            np.isclose(df["acid_flow"], midpoint["acid_flow"])
            & np.isclose(df["acetate_flow"], midpoint["acetate_flow"])
        ].sort_values("water_flow")

    fig, ax1 = plt.subplots(figsize=(8.8, 5.8))
    ax2 = ax1.twinx()
    ax1.plot(
        candidates["water_flow"],
        candidates["ph_equilibrium_charge_balance"],
        marker="o",
        color="#005f73",
        linewidth=1.9,
        label="raw equilibrium pH",
    )
    ax2.plot(
        candidates["water_flow"],
        candidates["total_buffer_mol_l"] * 1000.0,
        marker="s",
        color="#ae2012",
        linewidth=1.9,
        label="total buffer",
    )
    ax1.set_xlabel("water flow (mL/min)")
    ax1.set_ylabel("raw equilibrium pH")
    ax2.set_ylabel("total buffer concentration (mM)")
    ax1.set_title("Water sensitivity at acid=acetate=5 mL/min")
    formatter = ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    ax1.yaxis.set_major_formatter(formatter)
    ax1.grid(True, alpha=0.3)
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [line.get_label() for line in lines], loc="best")
    finalize(fig, path, stamp_text)
