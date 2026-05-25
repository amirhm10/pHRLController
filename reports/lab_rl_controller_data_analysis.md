# Lab RL Controller Data Analysis

Generated: 2026-05-21 21:20:23

Source data:

```text
Data\dsp_db.biosmb-rl-controller-treated-dataset.csv
```

Generated artifacts:

```text
results\lab_rl_controller_data_analysis_20260521_212023
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
\mathrm{pH} \approx pK_a + \log_{10}\left(\frac{F_A}{F_H}\right),
$$

where `F_H` is the acetic-acid flow and `F_A` is the sodium-acetate flow. For a target pH,

$$
\frac{F_A}{F_H} = 10^{\mathrm{pH}_{sp} - pK_a}.
$$

The current analysis therefore checks two questions:

1. Did the logged actions choose flow ratios consistent with the target?
2. Did reliable measured pH, `PH_2`, track the target?

The CSV does not contain the RL policy internals, rewards, observations before action, actor output, or training losses. Therefore the controller can be evaluated only from logged target, flow, sensor, and mass trajectories.

## Dataset Summary

| Item | Value |
|---|---:|
| Rows | 1086 |
| Raw CSV columns | 41 |
| Analysis columns after derived fields | 62 |
| Time span | 95.29 h |
| Start time | 2026-05-11 19:46:07.807000+00:00 |
| End time | 2026-05-15 19:03:18.401000+00:00 |
| Unique targets | 21 |
| Chronological sessions | 7 |
| Chronological trials | 85 |
| Missing values in raw CSV | 0 |
| Missing values after derived columns | 263 |
| Rows sharing nonunique `(episode_number, step_number)` pairs | 1029 |
| Rows with any zero flow among streams 0-2 | 1 |

`episode_number` and `step_number` are not globally unique in this combined file. The same episode and step numbers appear across separate lab runs. For this report, a derived `trial_id` was created whenever a long time gap or step reset was detected.

## Tracking Performance

Using `PH_2 - target_ph` as the tracking error:

| Metric | Value |
|---|---:|
| Mean error | -0.252 pH |
| Error standard deviation | 0.682 pH |
| MAE | 0.581 pH |
| RMSE | 0.727 pH |
| Max absolute error | 2.128 pH |
| Fraction within 0.05 pH | 7.3% |
| Fraction within 0.10 pH | 11.8% |
| Fraction within 0.20 pH | 23.4% |
| Fraction within 0.50 pH | 50.4% |
| Correlation between target pH and PH_2 | 0.037 |

The strongest result is negative: measured pH did not track user-defined targets reliably. The mean measured pH stayed near the buffer midpoint for many target values. High targets were systematically too low, and low targets were systematically too high.

### Best Targets By MAE

| target_ph | n | ph2_mean | mean_error | mae | rmse |
| --- | --- | --- | --- | --- | --- |
| 4.600 | 75 | 4.501 | -0.099 | 0.172 | 0.274 |
| 4.500 | 56 | 4.454 | -0.046 | 0.212 | 0.285 |
| 4.300 | 30 | 4.223 | -0.077 | 0.217 | 0.272 |
| 4.400 | 30 | 4.358 | -0.042 | 0.221 | 0.273 |
| 4.200 | 30 | 4.347 | 0.147 | 0.260 | 0.296 |

### Worst Targets By MAE

| target_ph | n | ph2_mean | mean_error | mae | rmse |
| --- | --- | --- | --- | --- | --- |
| 5.700 | 138 | 4.462 | -1.238 | 1.238 | 1.274 |
| 5.600 | 20 | 4.416 | -1.184 | 1.184 | 1.207 |
| 5.500 | 20 | 4.465 | -1.035 | 1.035 | 1.058 |
| 5.400 | 20 | 4.463 | -0.937 | 0.937 | 0.982 |
| 5.300 | 30 | 4.406 | -0.894 | 0.894 | 0.959 |

### Worst Chronological Trials By MAE

| trial_id | session_id | episode_number | target_ph | n | mae | rmse | final_error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | 5 | 24 | 5.700 | 8 | 1.410 | 1.445 | -1.134 |
| 37 | 5 | 3 | 5.700 | 10 | 1.393 | 1.423 | -1.306 |
| 82 | 6 | 24 | 5.700 | 10 | 1.357 | 1.366 | -1.430 |
| 61 | 6 | 3 | 5.700 | 10 | 1.321 | 1.353 | -1.667 |
| 13 | 3 | 3 | 5.700 | 30 | 1.295 | 1.324 | -1.361 |
| 78 | 6 | 20 | 5.600 | 10 | 1.265 | 1.285 | -1.218 |
| 19 | 4 | 3 | 5.700 | 10 | 1.171 | 1.209 | -0.819 |
| 3 | 1 | 3 | 5.700 | 30 | 1.157 | 1.209 | -0.943 |

## Flow and Ratio Behavior

The operator mapping gives:

| Logged flow | Physical stream |
|---|---|
| `observation.biosmb-flows[0]` | Acetic acid |
| `observation.biosmb-flows[1]` | Sodium acetate |
| `observation.biosmb-flows[2]` | Arium water |

Flow summary:

| stream | mean | std | min | q25 | median | q75 | max | rows_below_1 | rows_above_10 | rows_at_zero | total_abs_move |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acid_flow_0 | 5.461 | 2.655 | 0.000 | 3.076 | 5.583 | 7.781 | 9.971 | 1 | 0 | 1 | 3077.177 |
| sodium_acetate_flow_1 | 5.770 | 2.630 | 0.000 | 3.523 | 5.959 | 8.077 | 9.994 | 1 | 0 | 1 | 2950.152 |
| water_flow_2 | 5.111 | 2.628 | 0.000 | 2.811 | 4.808 | 7.451 | 9.970 | 1 | 0 | 1 | 3089.193 |

The nominal 1-10 mL/min bounds were respected except for one row where all three controlled flows were exactly zero. That row is likely startup, shutdown, communication, or a cleaned-data edge case and should be excluded from model fitting unless confirmed.

The actual acetate-to-acid ratio was not strongly aligned with the ideal ratio required by the target pH. This explains most of the tracking failure. For low-pH targets, the actual ratio was too high. For high-pH targets, the actual ratio was too low.

## Model Consistency

The steady-state model from the logged flows was compared to the valid pH sensor:

| model | n | mean_error_measured_minus_predicted | mae | rmse | correlation_with_ph2 |
| --- | --- | --- | --- | --- | --- |
| simple_henderson_hasselbalch | 1085 | -0.352 | 0.369 | 0.404 | 0.835 |
| equilibrium_charge_balance | 1085 | -0.353 | 0.370 | 0.404 | 0.835 |
| affine_fit_from_simple_model | 1085 | -0.000 | 0.123 | 0.169 | 0.835 |

The simple Henderson-Hasselbalch model and the charge-balance model are almost identical over these logged flow/concentration conditions. The measured pH was correlated with the model prediction from the current flow ratio, but it was biased and compressed:

- Simple-model correlation with `PH_2`: 0.835
- Simple-model raw RMSE against `PH_2`: 0.404 pH
- Affine-corrected simple-model RMSE: 0.169 pH

This means the data are chemically meaningful, but the controller actions were not target-consistent. A simple fitted calibration layer can explain much of the pH measurement from the flow ratio, but it does not solve the policy issue.

## Figures

### Sensor reliability

![pH sensor check](../results/lab_rl_controller_data_analysis_20260521_212023/figures/sensor_check_ph1_vs_ph2.png)

`PH_1` is inconsistent with `PH_2` and should not be used for control metrics. This supports the operator note that only pH sensor 2 was connected correctly.

### Tracking overview

![Tracking overview](../results/lab_rl_controller_data_analysis_20260521_212023/figures/tracking_overview.png)

The target is varied across a wide range, but `PH_2` remains much more compressed.

### Target summary

![Target versus measured pH](../results/lab_rl_controller_data_analysis_20260521_212023/figures/target_vs_measured_summary.png)

The ideal line is not followed. Average measured pH is nearly flat relative to target.

### Error by target

![Tracking error by target](../results/lab_rl_controller_data_analysis_20260521_212023/figures/tracking_error_by_target.png)

Low targets tend to have positive error. High targets tend to have negative error.

### Flows and buffer ratio

![Flows and ratio](../results/lab_rl_controller_data_analysis_20260521_212023/figures/flows_and_ratio.png)

The actual ratio often differs from the Henderson-Hasselbalch ratio required by the target.

### Target-ratio map

![Target ratio map](../results/lab_rl_controller_data_analysis_20260521_212023/figures/target_ratio_map.png)

The controller did not consistently map target pH to the required acetate/acetic-acid ratio.

### Model prediction versus measured pH

![Model prediction versus measured pH](../results/lab_rl_controller_data_analysis_20260521_212023/figures/model_prediction_vs_measured.png)

The measured pH is strongly related to the current flow-ratio model, but with bias and compression.

### Reservoir masses

![Mass readings](../results/lab_rl_controller_data_analysis_20260521_212023/figures/mass_readings.png)

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
