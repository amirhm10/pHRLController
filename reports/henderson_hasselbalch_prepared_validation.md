# Henderson-Hasselbalch Prepared-Data Validation

Generated: 2026-06-24 12:53:49

Source data:

```text
Data\dsp_db.biosmb-rl-controller-treated-dataset-weights.csv
```

Generated artifacts:

```text
results\henderson_hasselbalch_prepared_validation_20260624_125349
```

## Objective

Apply the static Henderson-Hasselbalch acetate-buffer model to the newly prepared time-series data. This is a first-principles baseline only. No controller, MPC, RL, dynamic delay, or sensor-response model is added here.

## Model

The model uses the acetic-acid stream as acid and the sodium-acetate stream as conjugate base:

$$
\mathrm{pH}_{HH,k} = pK_a + \log_{10}\left(\frac{C_A F_{A,k}}{C_H F_{H,k}}\right).
$$

For this dataset:

- `F_H` is `acid_flow`, the acetic-acid flow.
- `F_A` is `acetate_flow`, the sodium-acetate flow.
- `C_H = 0.100` mol/L.
- `C_A = 0.100` mol/L.
- `pK_a = 4.760`.

Because the acid and acetate stock concentrations are equal, the ideal static prediction is controlled by the acetate-to-acid flow ratio. Water is retained in the comparison table for later residence-time and dilution diagnostics, but it does not directly change this ideal ratio.

## Metrics

The residual is

$$
e_k = \mathrm{pH}_k - \mathrm{pH}_{HH,k}.
$$

Overall metrics:

| metric_scope | n | mean_error | std_error | mae | rmse | max_abs_error | correlation_measured_predicted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| overall | 962 | -0.286 | 0.129 | 0.287 | 0.314 | 0.568 | 0.913 |
| excluded_rows | 0 | nan | nan | nan | nan | nan | nan |

Metrics by sampling phase:

| sampling_phase_id | sampling_phase | n_total | n_model_valid | start_sample_index | end_sample_index | median_delta_t_min | mean_error | mae | rmse | max_abs_error | correlation_measured_predicted | median_molar_base_acid_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Phase 1: slower sampling | 309 | 309 | 0 | 308 | 2.347 | -0.159 | 0.162 | 0.220 | 0.417 | 0.888 | 0.896 |
| 2 | Phase 2: faster sampling | 653 | 653 | 309 | 961 | 1.152 | -0.347 | 0.347 | 0.350 | 0.568 | 0.990 | 0.939 |

Sampling phase summary:

| sampling_phase_id | sampling_phase | sampling_regime | start_sample_index | end_sample_index | n | median_delta_t_min | min_delta_t_min | max_delta_t_min | long_time_gap_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Phase 1: slower sampling | slow_sampling | 0 | 308 | 309 | 2.347 | 2.304 | 2.909 | 4 |
| 2 | Phase 2: faster sampling | fast_sampling | 309 | 961 | 653 | 1.152 | 1.138 | 1.210 | 2 |

## Generated Tables

- `tables/prepared_time_feature_data.csv`: prepared time-series data used by the model.
- `tables/hh_model_comparison.csv`: measured pH, HH prediction, residual, ratio, and phase labels.
- `tables/overall_metrics.csv`: overall residual metrics.
- `tables/metrics_by_sampling_phase.csv`: residual metrics separated by sampling phase.
- `tables/sampling_phase_summary.csv`: detected sampling phases from `delta_t_min`.
- `tables/model_metadata.csv`: pKa and stock concentration values used for the run.

## Figures

### pH and prediction

![pH and prediction](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_vs_hh_prediction.png)

### pH, prediction, and acid/base flows

![pH and prediction with flows](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_vs_hh_prediction_with_acid_base_flows.png)

### Residual

![Residual](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_minus_hh_prediction.png)

## Initial Interpretation

This static model is expected to capture the ideal direction of pH change with the acetate-to-acid ratio. It is not expected to explain transport delay, mixing residence time, sensor response, calibration bias, or phase-dependent sampling behavior. Therefore, residual structure in these figures should be treated as evidence for the next dynamic-modeling step, not as a reason to add controller logic yet.

## Risks And Notes

- The model assumes ideal acetate-buffer behavior with equal 100 mM acid and acetate stocks.
- The pH sensor value is the prepared `pH-sensor` column from the treated dataset.
- The plot x-axis is sequential sample index. Use `delta_t_min` from the saved comparison table for physical delay calculations.
- The two shaded regions are sampling phases detected from the original timestep spacing.

## Recommended Next Step

Use `tables/hh_model_comparison.csv` to inspect residual structure by sampling phase and by acid/base ratio. The next model step should add calibration and dynamic delay/sensor response before any control design.
