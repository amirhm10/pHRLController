# Dynamic pH Model Identification Report

Generated: `20260522_012324`

Data source: `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv`

Result folder: `results/dynamic_model_identification_20260522_012324`

## Objective

The goal of this workflow is to test whether the lab CSV can support a dynamic model that predicts the valid inline pH measurement, `PH_2`, from inlet flows. This is not a controller, MPC, RL, reward, or target-tracking workflow. The target signal is intentionally excluded because the modeling question is inlet-to-output prediction.

The workflow starts with the equilibrium charge-balance pH prediction and then tests three progressively richer hypotheses: a static affine calibration, an empirical sample delay, and a first-order dynamic response. Each stage is fitted only on chronological training trials and evaluated on later test trials.

## Data And Split

Only `observation.biosmb-sensors.PH_2` is used as the measured output. `PH_1` is not used because it was not connected during operation. The inlet mapping is acetic acid from `biosmb-flows[0]`, sodium acetate from `biosmb-flows[1]`, and Arium water from `biosmb-flows[2]`.

The preprocessed dataset contains `1086` chronological rows, `1085` valid model rows, and `85` segmented trials. The chronological split uses `59` train trials and `26` test trials. The median valid sampling interval is `69.98 s`, and the median total flow is `16.35 mL/min`.

Trial segmentation uses the same safe rule as the earlier validation workflows: a new trial starts after a long time gap, step reset, or episode reset. This matters because lagged features and dynamic states are never allowed to leak across trial boundaries.

## Model Sequence

The equilibrium chemistry baseline is the charge-balance model

$$
f(H) = H + C_{Na} - \frac{C_T K_a}{K_a + H} - \frac{K_w}{H} = 0,
$$

with

$$
pH_{eq} = -\log_{10}(H).
$$

The staged identification sequence is:

1. Equilibrium baseline:

$$
\hat y_k = pH_{eq,k}.
$$

2. Static calibration:

$$
\hat y_k = b_0 + b_1 pH_{eq,k}.
$$

3. Empirical sample delay:

$$
\hat y_k = b_0 + b_1 pH_{eq,k-d}.
$$

4. First-order dynamic wrapper:

$$
\hat y_k = \alpha_k \hat y_{k-1} + (1 - \alpha_k)\left(b_0 + b_1 pH_{eq,k-d}\right),
$$

$$
\alpha_k = \exp\left(-\frac{\Delta t_k}{\tau}\right).
$$

`d` is an integer lag in samples. `tau` is treated as an empirical combined mixing and pH-probe time constant for this CSV, not a trusted hardware parameter.

## Fitted Parameters

Static affine calibration fitted on train trials:

| calibration | b0_intercept | b1_slope | n_train |
| --- | --- | --- | --- |
| PH_2 = b0 + b1 * pH_equilibrium | 1.140444 | 0.692802 | 826 |

Best lag diagnostics for the selected lag:

| lag_samples | split | n | mean_error | mae | rmse | max_abs | correlation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| 0 | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |

Dynamic parameter diagnostics:

| best_lag_samples | theta_approx_s | theta_approx_min | tau_s | tau_min | median_dt_s | median_total_flow_ml_min | v_effective_approx_ml | optimizer_success |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.0000 | 0.0000 | 1.7033 | 0.0284 | 69.9825 | 16.3493 | 0.4641 | True |

The approximate transport delay is `0.0 s` from `0` sample lag(s). The approximate effective volume is `0.5 mL`, computed from `tau * median_total_flow`. This is only a provisional interpretation because the tubing length, tubing ID, static mixer volume, flow-cell volume, probe response time, and logging synchronization are not yet known.

## Train And Test Metrics

| model_label | split | n | mean_error | mae | rmse | max_abs | correlation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equilibrium baseline | train | 826 | -0.3274 | 0.3495 | 0.3918 | 1.1517 | 0.8030 |
| Equilibrium baseline | test | 259 | -0.4337 | 0.4337 | 0.4412 | 0.6749 | 0.9832 |
| Static calibrated | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| Static calibrated | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |
| Lag calibrated | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| Lag calibrated | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |
| First-order dynamic | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| First-order dynamic | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |

On the held-out test trials, the equilibrium baseline RMSE is `0.4412`, the static calibrated RMSE is `0.1148`, the lag calibrated RMSE is `0.1148`, and the first-order dynamic RMSE is `0.1148`. The largest test-stage reduction should be interpreted by stage: static gain `0.3264`, lag gain `0.0000`, and dynamic gain `0.0000`. The best held-out stage in this run is `Static calibrated`.

Conclusion from this run: the improvement is from static affine calibration, not from an identifiable transport delay or first-order dynamic response. The selected lag is `0`, and the fitted time constant `1.70 s` is far below the median sample interval `69.98 s`, so the dynamic wrapper collapses to the static calibrated prediction at the available sampling rate. The held-out dynamic residual mean is `-0.0903 pH`, so residual bias remains and a designed open-loop experiment is still needed.

The earlier steady-state equilibrium result was approximately `0.404 pH RMSE`. The table above reports the same kind of residual metric but split by chronological train and test trials, which is a stricter check against overfitting.

## Figures

![Measured versus dynamic prediction](../results/dynamic_model_identification_20260522_012324/figures/measured_vs_dynamic_prediction_time.png)

![Dynamic prediction scatter](../results/dynamic_model_identification_20260522_012324/figures/measured_vs_dynamic_prediction_scatter.png)

![Residual time by model](../results/dynamic_model_identification_20260522_012324/figures/residual_time_by_model.png)

![Residual histogram by model](../results/dynamic_model_identification_20260522_012324/figures/residual_histogram_by_model.png)

![Lag search RMSE](../results/dynamic_model_identification_20260522_012324/figures/lag_search_rmse.png)

![Dynamic trial examples](../results/dynamic_model_identification_20260522_012324/figures/dynamic_prediction_by_trial_examples.png)

![Train test metric comparison](../results/dynamic_model_identification_20260522_012324/figures/train_test_metric_comparison.png)

## Observations

- The static affine calibration tests whether the lab pH probe behaves like a shifted or compressed version of the equilibrium pH prediction. If this stage gives most of the test improvement, the immediate model problem is calibration rather than dynamics.
- The lag search tests whether old chemistry predictions explain current `PH_2` better than same-sample chemistry predictions. Because the sample period is roughly one minute and not perfectly uniform, this is a coarse delay estimate.
- The first-order wrapper tests whether smoothing the delayed chemistry input explains additional `PH_2` behavior. If it mainly improves train RMSE but not test RMSE, the CSV is not strong enough for reliable dynamic identification.
- Structured residuals after all three stages mean the closed-loop lab data are still missing key excitation or physical metadata needed for a predictive plant model.

## Limits And Risks

- The dataset appears to be controller-generated closed-loop time-series data, not a designed open-loop identification experiment.
- The sample interval is irregular, and long gaps were split into separate trials. This makes integer sample delay a safe first diagnostic, but not a final transport-delay model.
- The physical delay and effective volume are provisional because the mixing location, tubing geometry, dead volume, pH flow cell volume, probe time constant, and logger synchronization are unknown.
- The model uses `PH_2` only. `PH_1` and target pH are intentionally absent from the metrics.

## Recommended Next Step

The next safe modeling step is to treat the affine pH calibration as necessary, then design a small open-loop identification experiment before trusting a dynamic model. The experiment should include flow-ratio steps, total-flow changes, and enough hold time for `PH_2` to settle after each move. The minimum metadata needed are where the streams first meet, tubing inner diameter and length to `PH_2`, any static mixer or flow-cell volume, pH probe response time, and whether logged flows are synchronized before or after the pH measurement.

## Generated Tables

- `preprocessed_lab_data`: `results/dynamic_model_identification_20260522_012324/tables/preprocessed_lab_data.csv`
- `dynamic_model_comparison`: `results/dynamic_model_identification_20260522_012324/tables/dynamic_model_comparison.csv`
- `model_metrics_train_test`: `results/dynamic_model_identification_20260522_012324/tables/model_metrics_train_test.csv`
- `static_calibration_parameters`: `results/dynamic_model_identification_20260522_012324/tables/static_calibration_parameters.csv`
- `lag_search_metrics`: `results/dynamic_model_identification_20260522_012324/tables/lag_search_metrics.csv`
- `dynamic_parameters`: `results/dynamic_model_identification_20260522_012324/tables/dynamic_parameters.csv`
- `trial_split_summary`: `results/dynamic_model_identification_20260522_012324/tables/trial_split_summary.csv`
