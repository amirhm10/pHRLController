from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from helpers.dynamic_model_identification import (
    add_baseline_predictions,
    add_dynamic_prediction,
    add_equilibrium_predictions,
    add_lag_calibrated_prediction,
    add_trial_split,
    apply_affine_calibration,
    fit_affine_calibration,
    fit_first_order_tau,
    make_dynamic_parameters_table,
    make_model_metrics_train_test,
    make_static_calibration_table,
    markdown_table,
    search_lag_models,
    select_dynamic_comparison_columns,
)
from helpers.dynamic_model_plotting import create_dynamic_model_figures
from helpers.lab_data import LabPHColumnMap, load_lab_csv, preprocess_lab_data
from helpers.plotting import setup_output_dir
from simulation.config import PHProcessConfig
from simulation.equilibrium_charge_balance_model import EquilibriumChargeBalanceModel


DATA_PATH = Path("Data/dsp_db.biosmb-rl-controller-treated-dataset.csv")
RESULTS_ROOT = Path("results")
REPORT_PATH = Path("reports/dynamic_model_identification_report.md")

METHOD_NAME = "dynamic_model_identification"
TRAIN_FRACTION = 0.70
MAX_LAG_SAMPLES = 10
STEADY_STATE_REFERENCE_RMSE = 0.404


def main() -> None:
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = setup_output_dir(RESULTS_ROOT / f"{METHOD_NAME}_{run_stamp}")
    figure_dir = setup_output_dir(output_dir / "figures")
    table_dir = setup_output_dir(output_dir / "tables")
    stamp_text = f"{METHOD_NAME} | {run_stamp}"

    config = PHProcessConfig()
    column_map = LabPHColumnMap()
    equilibrium_model = EquilibriumChargeBalanceModel.from_config(config)

    raw_data = load_lab_csv(DATA_PATH, column_map)
    preprocessed = preprocess_lab_data(raw_data, column_map, config)
    preprocessed = add_equilibrium_predictions(preprocessed, equilibrium_model)
    identified, trial_split_summary = add_trial_split(
        preprocessed,
        train_fraction=TRAIN_FRACTION,
    )

    identified = add_baseline_predictions(identified)
    static_calibration = fit_affine_calibration(
        identified,
        feature_col="ph_equilibrium_charge_balance",
        split="train",
    )
    identified = apply_affine_calibration(
        identified,
        feature_col="ph_equilibrium_charge_balance",
        calibration=static_calibration,
        prediction_col="prediction_static_calibrated",
        residual_col="residual_static_calibrated",
    )

    lag_search, best_lag_samples, lag_calibration = search_lag_models(
        identified,
        source_col="ph_equilibrium_charge_balance",
        max_lag_samples=MAX_LAG_SAMPLES,
    )
    identified = add_lag_calibrated_prediction(
        identified,
        lag_samples=best_lag_samples,
        calibration=lag_calibration,
    )

    dynamic_fit = fit_first_order_tau(
        identified,
        input_col="prediction_lag_calibrated",
    )
    identified = add_dynamic_prediction(
        identified,
        tau_s=dynamic_fit.tau_s,
        input_col="prediction_lag_calibrated",
    )

    comparison = select_dynamic_comparison_columns(identified)
    metrics = make_model_metrics_train_test(identified)
    static_parameters = make_static_calibration_table(static_calibration)
    dynamic_parameters = make_dynamic_parameters_table(
        dynamic_fit=dynamic_fit,
        best_lag_samples=best_lag_samples,
        lag_calibration=lag_calibration,
        df=identified,
    )

    table_paths = save_tables(
        table_dir=table_dir,
        preprocessed=preprocessed,
        comparison=comparison,
        metrics=metrics,
        static_parameters=static_parameters,
        lag_search=lag_search,
        dynamic_parameters=dynamic_parameters,
        trial_split_summary=trial_split_summary,
    )
    figure_paths = create_dynamic_model_figures(
        df=identified,
        metrics=metrics,
        lag_search=lag_search,
        figure_dir=figure_dir,
        stamp_text=stamp_text,
    )
    write_report(
        report_path=REPORT_PATH,
        run_stamp=run_stamp,
        data_path=DATA_PATH,
        output_dir=output_dir,
        table_paths=table_paths,
        figure_paths=figure_paths,
        preprocessed=preprocessed,
        trial_split_summary=trial_split_summary,
        metrics=metrics,
        static_parameters=static_parameters,
        lag_search=lag_search,
        dynamic_parameters=dynamic_parameters,
    )

    summary = make_console_summary(metrics, dynamic_parameters)
    print(f"Dynamic model identification complete: {output_dir}")
    print(f"Report written: {REPORT_PATH}")
    print(summary)


def save_tables(
    table_dir: Path,
    preprocessed: pd.DataFrame,
    comparison: pd.DataFrame,
    metrics: pd.DataFrame,
    static_parameters: pd.DataFrame,
    lag_search: pd.DataFrame,
    dynamic_parameters: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
) -> dict[str, Path]:
    tables = {
        "preprocessed_lab_data": table_dir / "preprocessed_lab_data.csv",
        "dynamic_model_comparison": table_dir / "dynamic_model_comparison.csv",
        "model_metrics_train_test": table_dir / "model_metrics_train_test.csv",
        "static_calibration_parameters": table_dir / "static_calibration_parameters.csv",
        "lag_search_metrics": table_dir / "lag_search_metrics.csv",
        "dynamic_parameters": table_dir / "dynamic_parameters.csv",
        "trial_split_summary": table_dir / "trial_split_summary.csv",
    }
    preprocessed.to_csv(tables["preprocessed_lab_data"], index=False)
    comparison.to_csv(tables["dynamic_model_comparison"], index=False)
    metrics.to_csv(tables["model_metrics_train_test"], index=False)
    static_parameters.to_csv(tables["static_calibration_parameters"], index=False)
    lag_search.to_csv(tables["lag_search_metrics"], index=False)
    dynamic_parameters.to_csv(tables["dynamic_parameters"], index=False)
    trial_split_summary.to_csv(tables["trial_split_summary"], index=False)
    return tables


def write_report(
    report_path: Path,
    run_stamp: str,
    data_path: Path,
    output_dir: Path,
    table_paths: dict[str, Path],
    figure_paths: dict[str, Path],
    preprocessed: pd.DataFrame,
    trial_split_summary: pd.DataFrame,
    metrics: pd.DataFrame,
    static_parameters: pd.DataFrame,
    lag_search: pd.DataFrame,
    dynamic_parameters: pd.DataFrame,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    valid = preprocessed["valid_for_model"]
    median_dt = preprocessed.loc[valid, "dt_s"].dropna().median()
    median_total_flow = preprocessed.loc[valid, "total_flow"].dropna().median()
    train_trials = int((trial_split_summary["split"] == "train").sum())
    test_trials = int((trial_split_summary["split"] == "test").sum())
    key_metrics = make_report_metric_table(metrics)
    improvement = make_improvement_summary(metrics)
    conclusion = make_conclusion_summary(metrics, dynamic_parameters)
    best_lag = int(dynamic_parameters["best_lag_samples"].iloc[0])
    tau_s = float(dynamic_parameters["tau_s"].iloc[0])
    theta_s = float(dynamic_parameters["theta_approx_s"].iloc[0])
    effective_volume = float(dynamic_parameters["v_effective_approx_ml"].iloc[0])

    best_lag_table = lag_search.loc[
        lag_search["lag_samples"].eq(best_lag),
        ["lag_samples", "split", "n", "mean_error", "mae", "rmse", "max_abs", "correlation"],
    ]
    dynamic_table = dynamic_parameters[[
        "best_lag_samples",
        "theta_approx_s",
        "theta_approx_min",
        "tau_s",
        "tau_min",
        "median_dt_s",
        "median_total_flow_ml_min",
        "v_effective_approx_ml",
        "optimizer_success",
    ]]

    lines = [
        "# Dynamic pH Model Identification Report",
        "",
        f"Generated: `{run_stamp}`",
        "",
        f"Data source: `{data_path.as_posix()}`",
        "",
        f"Result folder: `{output_dir.as_posix()}`",
        "",
        "## Objective",
        "",
        "The goal of this workflow is to test whether the lab CSV can support a dynamic model that predicts the valid inline pH measurement, `PH_2`, from inlet flows. This is not a controller, MPC, RL, reward, or target-tracking workflow. The target signal is intentionally excluded because the modeling question is inlet-to-output prediction.",
        "",
        "The workflow starts with the equilibrium charge-balance pH prediction and then tests three progressively richer hypotheses: a static affine calibration, an empirical sample delay, and a first-order dynamic response. Each stage is fitted only on chronological training trials and evaluated on later test trials.",
        "",
        "## Data And Split",
        "",
        "Only `observation.biosmb-sensors.PH_2` is used as the measured output. `PH_1` is not used because it was not connected during operation. The inlet mapping is acetic acid from `biosmb-flows[0]`, sodium acetate from `biosmb-flows[1]`, and Arium water from `biosmb-flows[2]`.",
        "",
        f"The preprocessed dataset contains `{len(preprocessed)}` chronological rows, `{int(valid.sum())}` valid model rows, and `{trial_split_summary['trial_id'].nunique()}` segmented trials. The chronological split uses `{train_trials}` train trials and `{test_trials}` test trials. The median valid sampling interval is `{median_dt:.2f} s`, and the median total flow is `{median_total_flow:.2f} mL/min`.",
        "",
        "Trial segmentation uses the same safe rule as the earlier validation workflows: a new trial starts after a long time gap, step reset, or episode reset. This matters because lagged features and dynamic states are never allowed to leak across trial boundaries.",
        "",
        "## Model Sequence",
        "",
        "The equilibrium chemistry baseline is the charge-balance model",
        "",
        "$$",
        "f(H) = H + C_{Na} - \\frac{C_T K_a}{K_a + H} - \\frac{K_w}{H} = 0,",
        "$$",
        "",
        "with",
        "",
        "$$",
        "pH_{eq} = -\\log_{10}(H).",
        "$$",
        "",
        "The staged identification sequence is:",
        "",
        "1. Equilibrium baseline:",
        "",
        "$$",
        "\\hat y_k = pH_{eq,k}.",
        "$$",
        "",
        "2. Static calibration:",
        "",
        "$$",
        "\\hat y_k = b_0 + b_1 pH_{eq,k}.",
        "$$",
        "",
        "3. Empirical sample delay:",
        "",
        "$$",
        "\\hat y_k = b_0 + b_1 pH_{eq,k-d}.",
        "$$",
        "",
        "4. First-order dynamic wrapper:",
        "",
        "$$",
        "\\hat y_k = \\alpha_k \\hat y_{k-1} + (1 - \\alpha_k)\\left(b_0 + b_1 pH_{eq,k-d}\\right),",
        "$$",
        "",
        "$$",
        "\\alpha_k = \\exp\\left(-\\frac{\\Delta t_k}{\\tau}\\right).",
        "$$",
        "",
        "`d` is an integer lag in samples. `tau` is treated as an empirical combined mixing and pH-probe time constant for this CSV, not a trusted hardware parameter.",
        "",
        "## Fitted Parameters",
        "",
        "Static affine calibration fitted on train trials:",
        "",
        markdown_table(static_parameters, digits=6),
        "",
        "Best lag diagnostics for the selected lag:",
        "",
        markdown_table(best_lag_table, digits=4),
        "",
        "Dynamic parameter diagnostics:",
        "",
        markdown_table(dynamic_table, digits=4),
        "",
        f"The approximate transport delay is `{theta_s:.1f} s` from `{best_lag}` sample lag(s). The approximate effective volume is `{effective_volume:.1f} mL`, computed from `tau * median_total_flow`. This is only a provisional interpretation because the tubing length, tubing ID, static mixer volume, flow-cell volume, probe response time, and logging synchronization are not yet known.",
        "",
        "## Train And Test Metrics",
        "",
        markdown_table(key_metrics, digits=4),
        "",
        improvement,
        "",
        conclusion,
        "",
        f"The earlier steady-state equilibrium result was approximately `{STEADY_STATE_REFERENCE_RMSE:.3f} pH RMSE`. The table above reports the same kind of residual metric but split by chronological train and test trials, which is a stricter check against overfitting.",
        "",
        "## Figures",
        "",
        f"![Measured versus dynamic prediction]({relative_to_report(figure_paths['measured_vs_dynamic_time'])})",
        "",
        f"![Dynamic prediction scatter]({relative_to_report(figure_paths['measured_vs_dynamic_scatter'])})",
        "",
        f"![Residual time by model]({relative_to_report(figure_paths['residual_time_by_model'])})",
        "",
        f"![Residual histogram by model]({relative_to_report(figure_paths['residual_histogram_by_model'])})",
        "",
        f"![Lag search RMSE]({relative_to_report(figure_paths['lag_search_rmse'])})",
        "",
        f"![Dynamic trial examples]({relative_to_report(figure_paths['dynamic_prediction_by_trial_examples'])})",
        "",
        f"![Train test metric comparison]({relative_to_report(figure_paths['train_test_metric_comparison'])})",
        "",
        "## Observations",
        "",
        "- The static affine calibration tests whether the lab pH probe behaves like a shifted or compressed version of the equilibrium pH prediction. If this stage gives most of the test improvement, the immediate model problem is calibration rather than dynamics.",
        "- The lag search tests whether old chemistry predictions explain current `PH_2` better than same-sample chemistry predictions. Because the sample period is roughly one minute and not perfectly uniform, this is a coarse delay estimate.",
        "- The first-order wrapper tests whether smoothing the delayed chemistry input explains additional `PH_2` behavior. If it mainly improves train RMSE but not test RMSE, the CSV is not strong enough for reliable dynamic identification.",
        "- Structured residuals after all three stages mean the closed-loop lab data are still missing key excitation or physical metadata needed for a predictive plant model.",
        "",
        "## Limits And Risks",
        "",
        "- The dataset appears to be controller-generated closed-loop time-series data, not a designed open-loop identification experiment.",
        "- The sample interval is irregular, and long gaps were split into separate trials. This makes integer sample delay a safe first diagnostic, but not a final transport-delay model.",
        "- The physical delay and effective volume are provisional because the mixing location, tubing geometry, dead volume, pH flow cell volume, probe time constant, and logger synchronization are unknown.",
        "- The model uses `PH_2` only. `PH_1` and target pH are intentionally absent from the metrics.",
        "",
        "## Recommended Next Step",
        "",
        "The next safe modeling step is to treat the affine pH calibration as necessary, then design a small open-loop identification experiment before trusting a dynamic model. The experiment should include flow-ratio steps, total-flow changes, and enough hold time for `PH_2` to settle after each move. The minimum metadata needed are where the streams first meet, tubing inner diameter and length to `PH_2`, any static mixer or flow-cell volume, pH probe response time, and whether logged flows are synchronized before or after the pH measurement.",
        "",
        "## Generated Tables",
        "",
        *[
            f"- `{name}`: `{path.as_posix()}`"
            for name, path in table_paths.items()
        ],
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def make_report_metric_table(metrics: pd.DataFrame) -> pd.DataFrame:
    return metrics[[
        "model_label",
        "split",
        "n",
        "mean_error",
        "mae",
        "rmse",
        "max_abs",
        "correlation",
    ]].copy()


def make_improvement_summary(metrics: pd.DataFrame) -> str:
    pivot = metrics.pivot(index="model_stage", columns="split", values="rmse")
    baseline_test = float(pivot.loc["equilibrium_baseline", "test"])
    static_test = float(pivot.loc["static_calibrated", "test"])
    lag_test = float(pivot.loc["lag_calibrated", "test"])
    dynamic_test = float(pivot.loc["dynamic_first_order", "test"])

    static_gain = baseline_test - static_test
    lag_gain = static_test - lag_test
    dynamic_gain = lag_test - dynamic_test
    best_stage = metrics.loc[
        metrics["split"].eq("test")
    ].sort_values("rmse").iloc[0]["model_label"]

    return (
        "On the held-out test trials, "
        f"the equilibrium baseline RMSE is `{baseline_test:.4f}`, "
        f"the static calibrated RMSE is `{static_test:.4f}`, "
        f"the lag calibrated RMSE is `{lag_test:.4f}`, and "
        f"the first-order dynamic RMSE is `{dynamic_test:.4f}`. "
        f"The largest test-stage reduction should be interpreted by stage: "
        f"static gain `{static_gain:.4f}`, lag gain `{lag_gain:.4f}`, "
        f"and dynamic gain `{dynamic_gain:.4f}`. "
        f"The best held-out stage in this run is `{best_stage}`."
    )


def make_conclusion_summary(
    metrics: pd.DataFrame,
    dynamic_parameters: pd.DataFrame,
) -> str:
    pivot = metrics.pivot(index="model_stage", columns="split", values="rmse")
    residual_pivot = metrics.pivot(index="model_stage", columns="split", values="mean_error")
    static_test = float(pivot.loc["static_calibrated", "test"])
    lag_test = float(pivot.loc["lag_calibrated", "test"])
    dynamic_test = float(pivot.loc["dynamic_first_order", "test"])
    dynamic_mean_error = float(residual_pivot.loc["dynamic_first_order", "test"])
    best_lag = int(dynamic_parameters["best_lag_samples"].iloc[0])
    tau_s = float(dynamic_parameters["tau_s"].iloc[0])
    median_dt_s = float(dynamic_parameters["median_dt_s"].iloc[0])

    if abs(static_test - dynamic_test) < 1e-6 and best_lag == 0:
        return (
            "Conclusion from this run: the improvement is from static affine calibration, "
            "not from an identifiable transport delay or first-order dynamic response. "
            f"The selected lag is `{best_lag}`, and the fitted time constant "
            f"`{tau_s:.2f} s` is far below the median sample interval "
            f"`{median_dt_s:.2f} s`, so the dynamic wrapper collapses to the "
            "static calibrated prediction at the available sampling rate. "
            f"The held-out dynamic residual mean is `{dynamic_mean_error:.4f} pH`, "
            "so residual bias remains and a designed open-loop experiment is still needed."
        )

    if lag_test < static_test and dynamic_test >= lag_test:
        return (
            "Conclusion from this run: the delay stage explains more held-out error than "
            "the first-order dynamic stage. The dynamic time constant should remain a "
            "diagnostic until hardware volume and probe-response metadata are available."
        )

    if dynamic_test < lag_test:
        return (
            "Conclusion from this run: the first-order dynamic wrapper improves the "
            "held-out RMSE beyond static calibration and integer delay. This is promising, "
            "but the parameter remains empirical because the dataset is closed-loop and "
            "hardware geometry is not yet known."
        )

    return (
        "Conclusion from this run: the staged models do not produce a clear held-out "
        "dynamic improvement. Treat the dynamic parameters as diagnostics and collect "
        "designed open-loop data before using them in simulation."
    )


def make_console_summary(metrics: pd.DataFrame, dynamic_parameters: pd.DataFrame) -> str:
    pivot = metrics.pivot(index="model_stage", columns="split", values="rmse")
    best_test = metrics.loc[metrics["split"].eq("test")].sort_values("rmse").iloc[0]
    tau_s = float(dynamic_parameters["tau_s"].iloc[0])
    lag = int(dynamic_parameters["best_lag_samples"].iloc[0])
    return (
        "Test RMSE: "
        f"equilibrium={pivot.loc['equilibrium_baseline', 'test']:.4f}, "
        f"static={pivot.loc['static_calibrated', 'test']:.4f}, "
        f"lag={pivot.loc['lag_calibrated', 'test']:.4f}, "
        f"dynamic={pivot.loc['dynamic_first_order', 'test']:.4f}. "
        f"Best test stage={best_test['model_label']}; lag={lag}; tau={tau_s:.1f} s."
    )


def relative_to_report(path: Path) -> str:
    return Path("..", path).as_posix()


if __name__ == "__main__":
    main()
