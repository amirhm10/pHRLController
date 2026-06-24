# HH Residual Shift Diagnostic

Generated: 2026-06-24 13:24:06

Source data:

```text
Data\dsp_db.biosmb-rl-controller-treated-dataset-weights.csv
```

Generated artifacts:

```text
results\hh_residual_shift_diagnostic_20260624_132406
```

## Objective

Check why the Henderson-Hasselbalch residual changes inside the slower-sampling phase before the main sampling-rate transition. The specific question is whether a hidden change in the original dataset, such as flow source, sensor behavior, reservoir state, stock concentration, or effective pKa, explains the shift near sample 200.

## Method

The static model remains

$$
\mathrm{pH}_{HH,k} = pK_a + \log_{10}\left(\frac{C_{acetate} F_{acetate,k}}{C_{acid} F_{acid,k}}\right),
$$

with `pK_a = 4.760`, `C_acid = 0.100` mol/L, and `C_acetate = 0.100` mol/L.

The residual is

$$
e_k = \mathrm{pH}_k - \mathrm{pH}_{HH,k}.
$$

The measured pH used in this residual is the prepared last-column `pH-sensor`, which is numerically the same as `observation.biosmb-sensors.PH_2` in this dataset. `PH_1` is not used as a pH validation channel.

Reliable pH-channel check:

| candidate_sensor | prepared_sensor | n_compared | max_abs_difference | mean_abs_difference | rows_above_1e_6 |
| --- | --- | --- | --- | --- | --- |
| observation.biosmb-sensors.PH_2 | pH-sensor | 962 | 0.000000 | 0.000000 | 0 |

A single mean-residual changepoint scan found the largest persistent shift at sample `183`. The sampling-rate phase change starts later at sample `309`.

## Main Finding

The residual shift starts at sample `183`, not at the sampling-rate change. At the shift sample, `delta_t_min = 1025.4` min because the dataset crosses an overnight lab-session gap. After that boundary, the residual stays near the later biased regime even though the sampling interval remains about 2.33 min until sample `309`.

Changepoint summary:

| changepoint_sample_index | phase2_start_sample_index | changepoint_delta_t_min | changepoint_sampling_phase | mean_residual_before | mean_residual_after | residual_step_change | ph_measured_at_changepoint | ph_predicted_at_changepoint | residual_at_changepoint | molar_base_acid_ratio_at_changepoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 183 | 309 | 1025.352 | Phase 1: slower sampling | -0.037 | -0.345 | -0.308 | 4.508 | 4.800 | -0.292 | 1.097 |

Segment metrics:

| segment | start_sample_index | end_sample_index | n | median_delta_t_min | long_gap_count | mean_residual | median_residual | mae | rmse | max_abs_error | correlation_measured_predicted | mean_effective_pka | median_effective_pka | required_base_acid_stock_factor | median_molar_base_acid_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pre_jump | 0 | 182 | 183 | 2.362 | 2 | -0.037 | -0.035 | 0.042 | 0.050 | 0.156 | 0.994 | 4.723 | 4.725 | 0.919 | 0.833 |
| post_jump_same_sampling | 183 | 308 | 126 | 2.333 | 2 | -0.336 | -0.337 | 0.336 | 0.339 | 0.417 | 0.991 | 4.424 | 4.423 | 0.461 | 0.916 |
| phase2 | 309 | 961 | 653 | 1.152 | 2 | -0.347 | -0.341 | 0.347 | 0.350 | 0.568 | 0.990 | 4.413 | 4.419 | 0.450 | 0.939 |

## Flow Source Check

Using the raw `observation.biosmb-flows[0:2]` columns does not remove the jump. It makes the residual more negative than the treated last-column flows. Therefore the shift is not explained by accidentally using the wrong flow columns.

| flow_source | segment | n | mean_residual | median_residual | mae | rmse | mean_effective_pka | median_effective_pka | required_base_acid_stock_factor | correlation_measured_predicted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| treated_last_columns | pre_jump | 183 | -0.037 | -0.035 | 0.042 | 0.050 | 4.723 | 4.725 | 0.919 | 0.994 |
| treated_last_columns | post_jump_same_sampling | 126 | -0.336 | -0.337 | 0.336 | 0.339 | 4.424 | 4.423 | 0.461 | 0.991 |
| treated_last_columns | phase2 | 653 | -0.347 | -0.341 | 0.347 | 0.350 | 4.413 | 4.419 | 0.450 | 0.990 |
| raw_observation_flows | pre_jump | 183 | -0.121 | -0.101 | 0.123 | 0.145 | 4.639 | 4.659 | 0.758 | 0.987 |
| raw_observation_flows | post_jump_same_sampling | 126 | -0.421 | -0.399 | 0.421 | 0.427 | 4.339 | 4.361 | 0.380 | 0.989 |
| raw_observation_flows | phase2 | 653 | -0.432 | -0.410 | 0.432 | 0.440 | 4.328 | 4.350 | 0.370 | 0.983 |

## Effective pKa Or Concentration Interpretation

For each sample, the effective pKa diagnostic is computed as

$$
pK_{a,k}^{eff} =
\mathrm{pH}_{sensor,k}
- \log_{10}\left(\frac{C_{acetate} F_{acetate,k}}{C_{acid} F_{acid,k}}\right).
$$

Because both stock concentrations are assumed to be 0.100 mol/L, this simplifies to `pH_sensor - log10(flow_sodium / flow_acid)`. The segment mean also equals `pK_a + mean_residual`. This is a lumped intercept diagnostic, not proof that the true thermodynamic acetic-acid pKa changed.

The lumped `pK_a^{eff}` changes from about `4.72` before the jump to about `4.42` after the jump. A real acetic-acid `pK_a` change of about `0.30` pH units is not a normal explanation for the same chemistry. It is better interpreted as either a pH measurement offset, a stock/pump ratio change, or another session-level system change.

If the shift were explained only by effective stock concentration ratio, the post-jump data would imply

$$
\frac{(C_{acetate}/C_{acid})_{actual}}{(C_{acetate}/C_{acid})_{assumed}} \approx 10^{\bar e} \approx 0.46.
$$

That would mean the effective sodium-acetate-to-acetic-acid strength was roughly half of the assumed ratio after the jump. The CSV has no direct stock concentration column, so this cannot be confirmed from the log alone.

## Dilution And Charge-Balance Check

I also checked whether replacing the Henderson-Hasselbalch approximation with a full acetate charge-balance equilibrium model could explain the bias. This model includes dilution by water through the mixed analytical concentrations. It changes the predicted pH by less than `0.01` pH unit in this dataset, so dilution/equilibrium effects are not large enough to explain the persistent `0.3` pH offset.

| segment | n | mean_charge_balance_minus_hh | min_charge_balance_minus_hh | max_charge_balance_minus_hh | mean_ph_minus_charge_balance | rmse_ph_minus_charge_balance |
| --- | --- | --- | --- | --- | --- | --- |
| pre_jump | 183 | 0.001 | 0.000 | 0.009 | -0.038 | 0.051 |
| post_jump_same_sampling | 126 | 0.001 | 0.000 | 0.006 | -0.337 | 0.340 |
| phase2 | 653 | 0.001 | 0.000 | 0.008 | -0.347 | 0.351 |

## Raw Column Evidence

Several raw fields change at the same boundary. `PH_1` also jumps from the low-pH range to about 8, but it is not treated as a reliable pH measurement. It is only a session/instrumentation-state flag here. The stronger evidence is that the reliable `PH_2`/`pH-sensor` channel shifts downward, reservoir mass readings reset upward, and conductivity/UV channels change at the same boundary. This supports a lab-session or hardware/state change rather than a simple sampling-interval effect.

Selected medians by segment:

| segment | column | median | mean | min | max |
| --- | --- | --- | --- | --- | --- |
| pre_jump | observation.biosmb-sensors.PH_1 | 3.877 | 3.751 | 1.857 | 4.612 |
| pre_jump | observation.biosmb-sensors.PH_2 | 4.653 | 4.631 | 3.930 | 5.219 |
| pre_jump | observation.biosmb-sensors.COND_3 | 2.229 | 2.171 | 0.424 | 4.194 |
| pre_jump | observation.biosmb-sensors.COND_4 | 2.716 | 2.621 | 0.588 | 5.122 |
| pre_jump | observation.biosmb-sensors.UV_3B | 0.085 | 0.091 | 0.000 | 0.305 |
| pre_jump | observation.mfcs-mass.acid-mass-grams | 2300.970 | 2212.242 | 1128.400 | 3049.130 |
| pre_jump | observation.mfcs-mass.sodium-mass-grams | 2412.900 | 2358.027 | 1453.690 | 3163.930 |
| pre_jump | observation.mfcs-mass.water-mass-grams | 2268.280 | 2209.832 | 1137.080 | 3068.310 |
| pre_jump | ph_minus_ph_predicted | -0.035 | -0.037 | -0.156 | 0.099 |
| post_jump_same_sampling | observation.biosmb-sensors.PH_1 | 7.990 | 7.992 | 7.296 | 8.684 |
| post_jump_same_sampling | observation.biosmb-sensors.PH_2 | 4.384 | 4.385 | 3.623 | 5.071 |
| post_jump_same_sampling | observation.biosmb-sensors.COND_3 | 2.678 | 2.640 | 0.698 | 4.817 |
| post_jump_same_sampling | observation.biosmb-sensors.COND_4 | 2.954 | 2.932 | 0.787 | 5.322 |
| post_jump_same_sampling | observation.biosmb-sensors.UV_3B | 0.020 | 0.019 | 0.000 | 0.022 |
| post_jump_same_sampling | observation.mfcs-mass.acid-mass-grams | 2119.495 | 2123.147 | 1113.000 | 3131.030 |
| post_jump_same_sampling | observation.mfcs-mass.sodium-mass-grams | 2270.905 | 2256.624 | 1319.570 | 3188.290 |
| post_jump_same_sampling | observation.mfcs-mass.water-mass-grams | 2089.850 | 2127.884 | 1268.400 | 3026.380 |
| post_jump_same_sampling | ph_minus_ph_predicted | -0.337 | -0.336 | -0.417 | -0.016 |
| phase2 | observation.biosmb-sensors.PH_1 | 8.408 | 8.399 | 7.582 | 9.123 |
| phase2 | observation.biosmb-sensors.PH_2 | 4.393 | 4.375 | 3.572 | 5.026 |
| phase2 | observation.biosmb-sensors.COND_3 | 2.733 | 2.656 | 0.001 | 5.125 |
| phase2 | observation.biosmb-sensors.COND_4 | 2.930 | 2.835 | 0.562 | 5.236 |
| phase2 | observation.biosmb-sensors.UV_3B | 0.000 | 0.000 | 0.000 | 0.000 |
| phase2 | observation.mfcs-mass.acid-mass-grams | 2167.830 | 2159.790 | 1201.690 | 3148.810 |
| phase2 | observation.mfcs-mass.sodium-mass-grams | 2359.770 | 2341.063 | 1348.480 | 3221.820 |
| phase2 | observation.mfcs-mass.water-mass-grams | 2275.420 | 2271.686 | 1376.970 | 3222.730 |
| phase2 | ph_minus_ph_predicted | -0.341 | -0.347 | -0.568 | -0.205 |

Top local mean shifts around the residual jump:

| column | left_mean | right_mean | delta_mean | abs_delta_over_global_std |
| --- | --- | --- | --- | --- |
| observation.biosmb-sensors.PH_1 | 4.049 | 8.007 | 3.958 | 2.151 |
| observation.biosmb-sensors.P_5 | 0.001 | 0.006 | 0.004 | 1.778 |
| observation.biosmb-sensors.UV_3B | 0.091 | 0.018 | -0.073 | 1.766 |
| observation.biosmb-sensors.UV_2A | 0.000 | 0.001 | 0.001 | 1.343 |
| observation.biosmb-sensors.UV_3A | 0.013 | 0.026 | 0.013 | 0.885 |
| pH-sensor | 4.632 | 4.362 | -0.270 | 0.851 |
| observation.biosmb-sensors.PH_2 | 4.632 | 4.362 | -0.270 | 0.851 |
| observation.biosmb-sensors.P_7 | 0.079 | 0.083 | 0.004 | 0.811 |
| observation.biosmb-sensors.COND_1 | 0.236 | 0.236 | 0.001 | 0.748 |
| time | 46154.807 | 46155.616 | 0.808 | 0.725 |
| observation.biosmb-sensors.COND_3 | 1.987 | 2.504 | 0.517 | 0.571 |
| observation.biosmb-sensors.UV_3C | 0.035 | 0.026 | -0.009 | 0.471 |

Long-gap events:

| gap_sample_index | utc_time_before | utc_time_after | delta_t_min | episode_before | episode_after | step_before | step_after | ph1_before | ph1_after | ph2_before | ph2_after | residual_before | residual_after | acid_mass_before | acid_mass_after | sodium_mass_before | sodium_mass_after | water_mass_before | water_mass_after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 2026-05-11T20:30:46.486Z | 2026-05-12T13:24:00.581Z | 1013.227 | 1 | 1 | 19 | 1 | 2.010 | 4.112 | 5.088 | 4.887 | -0.036 | 0.050 | 2639.490 | 2592.520 | 2659.930 | 2604.280 | 2627.730 | 2582.370 |
| 113 | 2026-05-12T17:03:56.434Z | 2026-05-12T17:48:48.799Z | 44.870 | 4 | 1 | 4 | 1 | 4.143 | 3.979 | 4.936 | 4.898 | -0.048 | 0.013 | 1128.400 | 3049.130 | 1453.690 | 3163.930 | 1137.080 | 3068.310 |
| 183 | 2026-05-12T20:32:17.416Z | 2026-05-13T13:37:38.080Z | 1025.352 | 3 | 1 | 10 | 2 | 4.010 | 8.010 | 4.556 | 4.508 | -0.034 | -0.292 | 2019.290 | 3131.030 | 2255.120 | 3188.290 | 1991.920 | 3026.380 |
| 307 | 2026-05-13T18:25:13.297Z | 2026-05-14T16:27:14.194Z | 1322.021 | 5 | 1 | 5 | 1 | 8.020 | 8.214 | 4.956 | 4.859 | -0.313 | -0.214 | 1113.000 | 2875.180 | 1319.570 | 2979.970 | 1268.400 | 2872.590 |
| 467 | 2026-05-14T19:34:39.008Z | 2026-05-14T22:23:11.782Z | 168.538 | 16 | 1 | 8 | 1 | 8.357 | 8.296 | 3.886 | 4.662 | -0.508 | -0.289 | 1631.630 | 2948.470 | 1926.400 | 3184.580 | 1683.010 | 3080.420 |
| 704 | 2026-05-15T02:55:21.801Z | 2026-05-15T14:06:10.391Z | 670.824 | 24 | 1 | 7 | 1 | 8.408 | 8.439 | 4.566 | 4.477 | -0.330 | -0.240 | 1201.690 | 3148.810 | 1491.210 | 3221.820 | 1421.700 | 3222.730 |

## Figures

### Residual Overview

![Residual overview](../results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_overview.png)

### Local Context

![Local context](../results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_local_context.png)

## Interpretation

The shift is not caused by the later sampling-rate phase change. The strongest evidence is that the residual changes at sample 183, after an overnight gap and session reset, while the sampling interval remains in the slower regime. The pH-model trend remains highly correlated after the jump, which means the acid/base ratio still explains direction, but the intercept has changed.

The most plausible explanations from the available log are:

1. A pH measurement calibration or probe-state offset changed at the new session.
2. The effective acid/base stock or pump calibration ratio changed after reservoir replacement or setup changes.
3. A physical setup or solution-property change occurred at the same overnight/reservoir-reset boundary.
4. The treated flow columns encode a corrected flow estimate, but the raw observed flow columns do not explain the offset.

## Recommended Next Step

Treat samples before 183 and after 183 as separate calibration regimes. Fit an intercept-only calibration or effective `pK_a` for each regime, then test whether the residual structure remains after this regime correction. If the offset disappears but lag structure remains, move next to delay and sensor-response identification.

## Remaining Uncertainty

The CSV does not contain direct stock concentration, pH probe calibration records, tubing/plumbing changes, or operator notes for the overnight transition. Therefore the diagnostic can identify the timing and likely class of cause, but it cannot prove whether the cause was sensor calibration, concentration, pump calibration, or physical setup.
