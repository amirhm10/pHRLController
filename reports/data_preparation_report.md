# Data Preparation Report

Generated: 2026-06-24 12:39:26

Source data:

```text
Data\dsp_db.biosmb-rl-controller-treated-dataset-weights.csv
```

Generated artifacts:

```text
results\data_preparation_20260624_123926
```

## Objective

Start the new data-analysis workflow by preparing only the timestep column and the last four columns from the updated lab CSV. This is intentionally limited to data preparation and visual inspection. No new chemistry model, controller, MPC, or RL logic is added here.

## Method

The raw CSV is loaded without editing the file. The preparation script selects:

- timestep column: `time`
- final feature columns: `flow-acid, flow-sodium, flow-water, pH-sensor`

The selected feature columns are standardized for downstream code:

| source_column | prepared_column |
| --- | --- |
| flow-acid | acid_flow |
| flow-sodium | acetate_flow |
| flow-water | water_flow |
| pH-sensor | ph_measured |

The prepared time-series vector for sample `k` is

$$
z_k = \left[t_k, F_{H,k}, F_{A,k}, F_{W,k}, \mathrm{pH}_k\right],
$$

where `F_H` is acetic acid flow, `F_A` is sodium acetate flow, `F_W` is water flow, and `pH_k` is the measured pH sensor value from the treated dataset.

The figures use chronological sample index on the x-axis:

$$
s_k = k.
$$

This treats the full experiment as one sequential record and removes blank spaces caused by long calendar-time gaps between lab blocks. The original timestamp spacing is still retained as

$$
\Delta t_k = t_k - t_{k-1}.
$$

The two shaded plot regions are sampling phases detected from `delta_t_min`. Phase 1 has the slower sampling interval, and Phase 2 has the faster sampling interval.

## Dataset Summary

| source_path | raw_rows | raw_columns | selected_columns | prepared_columns | source_missing_values | prepared_missing_values | time_column | feature_columns | elapsed_min_start | elapsed_min_end | elapsed_min_span | sampling_phase_count | long_time_gap_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Data\dsp_db.biosmb-rl-controller-treated-dataset-weights.csv | 962 | 47 | 5 | 16 | 0 | 1 | time | flow-acid, flow-sodium, flow-water, pH-sensor | 0.000 | 5714.798 | 5714.798 | 2 | 6 |

## Feature Summary

| column | n | missing | min | mean | std | median | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| acid_flow | 962 | 0 | 2.070 | 6.571 | 2.486 | 6.600 | 11.400 |
| acetate_flow | 962 | 0 | 1.339 | 6.049 | 2.501 | 6.270 | 10.348 |
| water_flow | 962 | 0 | 1.175 | 6.277 | 2.454 | 5.953 | 11.032 |
| ph_measured | 962 | 0 | 3.572 | 4.425 | 0.317 | 4.425 | 5.219 |
| total_flow | 962 | 0 | 4.817 | 18.897 | 4.268 | 18.907 | 31.441 |
| acetate_acid_ratio | 962 | 0 | 0.134 | 1.097 | 0.715 | 0.924 | 3.972 |

## Sampling Phase Summary

| sampling_phase_id | sampling_phase | sampling_regime | start_sample_index | end_sample_index | n | median_delta_t_min | min_delta_t_min | max_delta_t_min | long_time_gap_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Phase 1: slower sampling | slow_sampling | 0 | 308 | 309 | 2.347 | 2.304 | 2.909 | 4 |
| 2 | Phase 2: faster sampling | fast_sampling | 309 | 961 | 653 | 1.152 | 1.138 | 1.210 | 2 |

## Generated Tables

- `tables/selected_time_and_last_four_columns.csv`: exact extraction of timestep plus the last four CSV columns.
- `tables/prepared_time_feature_data.csv`: standardized feature names plus basic derived columns for future analysis.
- `tables/preparation_overview.csv`: source and selected-data metadata.
- `tables/feature_summary.csv`: numeric summary of the prepared features.
- `tables/column_mapping.csv`: source-column to prepared-column mapping.
- `tables/sampling_phase_summary.csv`: detected sampling-phase ranges and median time steps.

## Figures

### Individual feature traces

![Acid flow](../results/data_preparation_20260624_123926/figures/acid_flow_timeseries.png)

![Sodium acetate flow](../results/data_preparation_20260624_123926/figures/acetate_flow_timeseries.png)

![Water flow](../results/data_preparation_20260624_123926/figures/water_flow_timeseries.png)

![Measured pH](../results/data_preparation_20260624_123926/figures/ph_measured_timeseries.png)

### Four-feature overview

![All features](../results/data_preparation_20260624_123926/figures/all_features_four_subplots.png)

### pH with acid/base flows

![pH with acid and base flows](../results/data_preparation_20260624_123926/figures/ph_with_acid_base_flows.png)

## Initial Interpretation

The prepared dataset is a compact sequential time-series view of the experiment: acid flow, sodium acetate flow, water flow, and pH. The original `time` column shows two sampling phases: an earlier slower-sampling phase and a later faster-sampling phase. The first useful checks are visual continuity, flow ranges, abrupt setpoint-like moves, and whether pH responds after flow changes. This report does not yet separate individual trials, estimate delays, or fit any static or dynamic model.

## Risks And Notes

- The selected `time` column appears to be a numeric timestamp in day units in this file, so `delta_t_min` is derived by differencing the time column and multiplying by 1440.
- The single prepared-data missing value is the first `delta_t_min`, which is undefined because there is no previous sample.
- The plots intentionally use sequential sample index rather than elapsed minutes. This removes empty visual gaps, but physical delay estimation should still use `delta_t_min`.
- Existing validation runners still point to the previous treated CSV name. They should be updated only after this new prepared dataset is inspected.
- The current report treats the last four columns as the working features because that is the stated data-preparation rule for this step.

## Recommended Next Step

After visually checking these figures, the next small step is to add trial/session segmentation and simple lag-aware pH response diagnostics using this prepared table. That should happen before any new controller or RL work.
