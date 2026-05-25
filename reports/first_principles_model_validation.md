# First-Principles pH Model Validation And Development Plan

Generated: 2026-05-21 21:48:30

Source data:

```text
Data\dsp_db.biosmb-rl-controller-treated-dataset.csv
```

Generated artifacts:

```text
results\first_principles_model_validation_20260521_214830
```

## Objective

This report is about the plant model, not a controller or RL agent. The modeling objective is to predict the measured outlet pH from the physical inputs: acetic-acid flow, sodium-acetate flow, and water flow.

The current model is a steady-state first-principles buffer model. The next model should keep that chemistry layer, but add the missing process physics needed by the lab setup: explicit time delay, tubing and mixer volume, residence time, mixing location, and pH-sensor response.

## Data Mapping And Quality Checks

The analysis uses the operator-provided lab mapping:

| CSV column | Interpretation | Used for metrics |
|---|---|---|
| `observation.biosmb-sensors.PH_2` | Valid pH sensor | yes |
| `observation.biosmb-sensors.PH_1` | Disconnected pH sensor | no |
| `observation.biosmb-flows[0]` | Acetic acid, 100 mM | yes |
| `observation.biosmb-flows[1]` | Sodium acetate, 100 mM | yes |
| `observation.biosmb-flows[2]` | Arium water | yes |

| Item | Value |
|---|---:|
| Raw rows | 1086 |
| Raw CSV columns | 41 |
| Analysis columns after derived fields | 63 |
| Raw missing values | 0 |
| Time span | 95.29 h |
| Unique targets | 21 |
| Derived chronological sessions | 7 |
| Derived chronological trials | 85 |
| Rows valid for first-principles model | 1085 |
| Rows excluded from model metrics | 1 |
| Rows sharing nonunique `(episode_number, step_number)` pairs | 1029 |
| Rows with any zero flow among streams 0-2 | 1 |

`episode_number` and `step_number` are not globally unique across the combined CSV. A derived `trial_id` is therefore created by chronological ordering, long time gaps, step resets, or episode resets.

## First-Principles Model Formulation

The current first-principles model is the Henderson-Hasselbalch acetate-buffer relation:

$$
\mathrm{pH}_{HH} = pK_a + \log_{10}\left(\frac{F_A}{F_H}\right),
$$

where:

- $F_H$ is acetic-acid flow, from `observation.biosmb-flows[0]`.
- $F_A$ is sodium-acetate flow, from `observation.biosmb-flows[1]`.
- $pK_a = 4.76$ in the current configuration.

The target-implied ideal ratio is:

$$
\left(\frac{F_A}{F_H}\right)_{ideal} = 10^{\mathrm{pH}_{sp} - pK_a}.
$$

The charge-balance equilibrium model is also computed as a secondary reference, but the primary validation target is the Henderson-Hasselbalch model.

## Data-Driven Model Question

For each valid sample, the report tests:

$$
\hat y_k = f_{model}(F_{H,k}, F_{A,k}, F_{W,k})
$$

against the reliable measurement:

$$
y_k = \mathrm{PH2}_k.
$$

The present steady-state model uses only the instantaneous acid/acetate ratio. That is useful as a first diagnostic, but it cannot represent transport delay, finite mixing volume, sensor lag, or action-measurement time misalignment.

## Model-Vs-Data Deviation Results

Overall metrics:

| metric | n | mean | std | mae | rmse | max_abs | correlation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PH_2 minus HH model | 1085 | -0.352 | 0.198 | 0.369 | 0.404 | 1.151 |  |
| PH_2 minus equilibrium model | 1085 | -0.353 | 0.197 | 0.370 | 0.404 | 1.152 |  |
| PH_2 minus target | 1085 | -0.252 | 0.682 | 0.581 | 0.727 | 2.128 |  |
| HH model minus target | 1085 | 0.100 | 0.706 | 0.580 | 0.713 | 2.002 |  |
| log10(actual ratio) minus log10(ideal raw ratio) | 1085 | 0.100 | 0.706 | 0.580 | 0.713 | 2.002 |  |
| PH_2 minus affine HH calibration | 1085 | -0.000 | 0.169 | 0.123 | 0.169 | 0.808 | 0.835 |
| PH_2 versus HH model correlation | 1085 |  |  |  |  |  | 0.835 |
| target versus PH_2 correlation | 1086 |  |  |  |  |  | 0.037 |
| target versus HH model correlation | 1085 |  |  |  |  |  | 0.034 |

Key numbers:

- `PH_2 - HH model` mean deviation: -0.352 pH.
- `PH_2 - HH model` RMSE: 0.404 pH.
- `PH_2 - equilibrium model` RMSE: 0.404 pH.
- `PH_2 - target` RMSE: 0.727 pH.
- Correlation between `PH_2` and HH prediction: 0.835.
- Correlation between target and `PH_2`: 0.037.
- Correlation between target and HH prediction: 0.034.
- Affine calibration from HH prediction reduces RMSE to 0.169 pH.

The HH and equilibrium models are nearly identical for this dataset. The measured pH is strongly related to the flow-ratio model, but it is biased and compressed relative to the raw HH prediction.

Worst targets by HH-model deviation:

| target_ph | n_model_valid | ph_measured_mean | ph_hh_mean | measured_minus_hh_mae | measured_minus_hh_rmse | actual_ratio_median | ideal_ratio_raw |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.000 | 30 | 4.411 | 4.870 | 0.459 | 0.470 | 1.016 | 1.738 |
| 3.900 | 20 | 4.418 | 4.874 | 0.456 | 0.464 | 1.347 | 0.138 |
| 5.300 | 30 | 4.406 | 4.856 | 0.450 | 0.462 | 1.592 | 3.467 |
| 4.000 | 29 | 4.360 | 4.806 | 0.446 | 0.457 | 1.230 | 0.174 |
| 4.900 | 30 | 4.360 | 4.803 | 0.443 | 0.450 | 0.999 | 1.380 |
| 4.100 | 30 | 4.353 | 4.795 | 0.442 | 0.448 | 1.038 | 0.219 |

Worst chronological trials by HH-model deviation:

| trial_id | session_id | episode_number | target_ph | n_model_valid | measured_minus_hh_mae | measured_minus_hh_rmse | final_measured_minus_hh |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 33 | 5 | 1 | 4.700 | 9 | 0.843 | 0.867 | -1.143 |
| 67 | 6 | 9 | 5.000 | 10 | 0.502 | 0.514 | -0.454 |
| 31 | 4 | 15 | 4.100 | 10 | 0.485 | 0.492 | -0.554 |
| 28 | 4 | 12 | 4.200 | 10 | 0.485 | 0.487 | -0.508 |
| 19 | 4 | 3 | 5.700 | 10 | 0.480 | 0.491 | -0.620 |
| 48 | 5 | 14 | 5.300 | 10 | 0.479 | 0.496 | -0.485 |
| 24 | 4 | 8 | 4.400 | 10 | 0.472 | 0.476 | -0.485 |
| 63 | 6 | 5 | 4.600 | 10 | 0.470 | 0.474 | -0.391 |

## Target-Ratio Consistency

The log-ratio deviation is defined as:

$$
\log_{10}\left(\frac{F_A/F_H}{(F_A/F_H)_{ideal}}\right).
$$

For this dataset, its mean absolute value is 0.580. This is large enough to show that many logged flow ratios were not close to the first-principles ratio implied by the target pH.

This distinction matters. The model can explain the measured pH from the actual flow ratio much better than the target explains the measured pH. Therefore, the first-principles model is useful as a diagnostic baseline, but the lab run did not consistently command target-compatible ratios.

## Time Delay, Volume, And Mixing Interpretation

The current CSV is not sufficient to identify a physical delay robustly. A simple discrete lag scan gives the lowest RMSE at lag 0 sample(s), with RMSE 0.404 pH. That does not prove zero delay. It means the logged row alignment already makes the instantaneous HH prediction most correlated with `PH_2`, or that the experiment was not designed to isolate delay.

Lag scan summary:

| lag_samples | n | correlation | rmse | mae | mean_error |
| --- | --- | --- | --- | --- | --- |
| 0 | 1085 | 0.835 | 0.404 | 0.369 | -0.352 |
| 1 | 1000 | -0.008 | 0.585 | 0.472 | -0.346 |
| 2 | 916 | -0.076 | 0.595 | 0.479 | -0.338 |
| 3 | 833 | -0.080 | 0.596 | 0.479 | -0.338 |
| 4 | 750 | -0.043 | 0.582 | 0.467 | -0.325 |
| 5 | 667 | 0.030 | 0.564 | 0.451 | -0.320 |
| 6 | 585 | 0.046 | 0.558 | 0.445 | -0.310 |
| 7 | 504 | -0.017 | 0.560 | 0.450 | -0.296 |
| 8 | 423 | -0.140 | 0.573 | 0.460 | -0.279 |
| 9 | 343 | -0.117 | 0.572 | 0.462 | -0.265 |
| 10 | 266 | -0.111 | 0.544 | 0.427 | -0.232 |

For the next first-principles model, use a layered structure:

1. Flow-to-inlet-composition layer:

$$
C_{HA,in}(t) = C_{HA}^0 \frac{F_H(t)}{F_T(t)},
\quad
C_{A,in}(t) = C_A^0 \frac{F_A(t)}{F_T(t)},
\quad
F_T(t) = F_H(t)+F_A(t)+F_W(t).
$$

2. Mixing-volume layer, if the mixer or post-mixer hold-up is well approximated as a stirred volume:

$$
\tau_{mix}(t) \frac{dC_{HA}}{dt} = C_{HA,in}(t) - C_{HA}(t),
\quad
\tau_{mix}(t) \frac{dC_A}{dt} = C_{A,in}(t) - C_A(t).
$$

The residence time should be computed from total liquid volume and total volumetric flow:

$$
\tau_{mix}(t) = \frac{V_{mix}}{F_T(t)}.
$$

3. Transport-delay layer, if the post-mixing tubing behaves closer to plug flow:

$$
\theta_{tube}(t) = \frac{V_{tube}}{F_T(t)},
\quad
V_{tube} = \frac{\pi D_i^2 L}{4}.
$$

The pH at the sensor is then driven by the mixed chemistry state delayed by `theta_tube`.

4. Chemistry layer:

$$
\mathrm{pH}_{out}(t) = pK_a^{eff} + \log_{10}\left(\frac{C_A(t)}{C_{HA}(t)}\right) + b_{pH},
$$

or use the existing charge-balance model when dilution and water self-ionization are important.

5. Sensor layer:

$$
\tau_{sensor} \frac{dy_{meas}}{dt} =
\mathrm{pH}_{out}(t - \theta_{tube}) - y_{meas}(t).
$$

The unknowns to fit from designed data are:

| Parameter | Meaning | How to identify |
|---|---|---|
| `pKa_eff` | effective acetate-buffer pKa in the lab system | settled target-ratio sweep |
| `b_pH` | sensor or model bias | settled target-ratio sweep |
| `V_mix` | effective mixed volume at tee/static mixer/flow cell | step tests at different total flow |
| `V_tube` | post-mixer transport volume to sensor | physical tubing dimensions or tracer step |
| `tau_sensor` | pH probe/transmitter response time | buffer-to-buffer probe step or process step |

## Where Mixing Likely Happens

The current CSV does not identify the hardware geometry. The next lab note should explicitly document:

- The exact point where acetic acid, sodium acetate, and water first meet.
- Whether that point is a tee, manifold, static mixer, or another geometry.
- The inner diameter and length of tubing from each pump to the mixer.
- The inner diameter and length from mixer outlet to pH sensor 2.
- Any flow cell, dead volume, probe chamber, or collection volume before the pH measurement.
- Whether pH sensor 2 is installed inline, in a flow cell, or downstream in a vessel.

Without this geometry, `time delay` and `total volume` are not identifiable as physical parameters. They can only be fitted as empirical delay and lag terms.

## Figures

### pH sensor check

![pH sensor check](../results/first_principles_model_validation_20260521_214830/figures/sensor_check_ph1_ph2_target.png)

`PH_1` is shown only to document the disconnected sensor behavior. It is not used in metrics.

### Measured pH versus HH model over time

![Measured pH versus HH model](../results/first_principles_model_validation_20260521_214830/figures/measured_vs_hh_model_time.png)

The measured pH follows the HH prediction trend better than it follows the raw target sequence, but with bias and compression.

### Measured pH versus HH model scatter

![Measured pH versus HH model scatter](../results/first_principles_model_validation_20260521_214830/figures/measured_vs_hh_scatter.png)

The scatter plot shows strong correlation and a visible affine calibration relationship.

### Deviation over time

![Deviation over time](../results/first_principles_model_validation_20260521_214830/figures/measured_minus_hh_time.png)

The deviation is not only random noise. It has a persistent negative bias.

### Deviation histogram

![Deviation histogram](../results/first_principles_model_validation_20260521_214830/figures/measured_minus_hh_histogram.png)

The distribution centers below zero, matching the mean `PH_2 - HH` deviation.

### Target summary

![Target summary](../results/first_principles_model_validation_20260521_214830/figures/target_measured_model_summary.png)

The target pH range is broad, but the measured pH range is much more compressed.

### Actual versus ideal flow ratio

![Actual versus ideal flow ratio](../results/first_principles_model_validation_20260521_214830/figures/actual_vs_ideal_ratio_map.png)

The actual flow ratios do not consistently lie on the ideal target-ratio line.

### Flow trajectories

![Flow trajectories](../results/first_principles_model_validation_20260521_214830/figures/flow_trajectories.png)

The nominal flow bounds were respected except for the single zero-flow row already noted.

### Discrete lag scan

![Discrete lag scan](../results/first_principles_model_validation_20260521_214830/figures/delay_lag_scan.png)

The current data do not isolate physical delay. A designed step experiment is needed.

## Interpretation

The first-principles acetate-buffer model is not rejected by this dataset. Instead, the data show that measured `PH_2` is strongly correlated with the pH predicted from the logged acid and acetate flow ratio. The main discrepancy is a bias/compression between ideal HH pH and measured pH, which can plausibly come from pH probe calibration, effective pKa, activity effects, mixing/residence time, or unlogged timing between action and measurement.

The report should not be read as a controller evaluation. The important result for model development is that the instantaneous steady-state model explains a substantial part of measured pH, but the next first-principles model needs dynamic process structure before it can predict measured pH during changing flow conditions.

## Literature-Based Modeling Guidance

- Henderson-Hasselbalch is the correct first buffer baseline for weak-acid/conjugate-base systems, but it is an approximation that uses concentration ratios for buffer calculations. See OpenStax and LibreTexts: [OpenStax buffer chapter](https://openstax.org/books/chemistry/pages/14-6-buffers), [LibreTexts HH approximation](https://chem.libretexts.org/Courses/College_of_the_Canyons/CHEM_202%3A_General_Chemistry_II_OER/06%3A_Acid-Base_Equilibria_in_Mixtures/6.04%3A_Henderson-Hasselbalch_Approximation).
- Dynamic pH modeling literature commonly separates physical mixing/material-balance dynamics from a static pH/equilibrium map for fast acid-base reactions. Gustafsson and Waller describe reaction-invariant pH modeling this way: [Dynamic modeling and reaction invariant control of pH](https://www.sciencedirect.com/science/article/pii/0009250983801572).
- pH control design literature treats delay as a central limitation and separates process, measurement, and valve/instrument delays. Faanes and Skogestad discuss pH-neutralization design with delay and volume explicitly: [pH-neutralization: integrated process and control design](https://www.sciencedirect.com/science/article/pii/S0098135403002928), [author PDF](https://skoge.folk.ntnu.no/publications/2004/faanes_cce_ph/ph.pdf).
- Residence time is fundamentally volume divided by volumetric flow rate, so tubing/mixer volume and total flow determine the first estimate of delay or residence time: [ScienceDirect reactor design overview](https://www.sciencedirect.com/topics/engineering/reactor-design).
- Static mixer behavior depends on flow rate, fluid properties, pipe geometry, and mixer geometry, and residence-time distribution is a useful way to characterize inline mixing: [Static mixers review in Chemical Engineering Research and Design](https://www.sciencedirect.com/science/article/pii/S0263876213002906), [recent static mixer review](https://www.mdpi.com/2305-7084/9/6/128), [University of Michigan mixer overview](https://encyclopedia.che.engin.umich.edu/mixers/).
- pH probes and transmitters add measurement response time. Hamilton notes that pH electrodes do not reach a new buffer value instantaneously and that roughly 30 s can be normal for stable buffer response: [Hamilton pH sensor response time](https://www.hamiltoncompany.com/process-analytics/ph-and-orp-knowledge/ph-calibration/response-time).

## Limits And Risks

- The current fitted report is steady-state plus lag diagnostics. It does not yet estimate physical residence time, probe lag, or mixing delay.
- The CSV does not state whether each flow row is pre-action, post-action, or synchronized exactly with the pH measurement.
- Rows with nonpositive acid, acetate, or water flow are excluded from model metrics.
- The report uses `PH_2` only. `PH_1` is plotted for quality control but excluded from all model-validation metrics.
- The affine calibration result is diagnostic, not a final calibrated process model.
- Physical parameters such as `V_mix`, `V_tube`, and `tau_sensor` cannot be uniquely identified without designed step tests and geometry measurements.

## Recommended Next Step

Run a deterministic open-loop model-identification experiment before another controller test. Use the existing `SimpleBufferModel.flows_from_target()` method to command target-compatible flow ratios over pH 3.8-5.7. Hold each ratio long enough for the outlet pH to settle, log `PH_2`, and save synchronized commanded flows and measured flows.

The experiment should have two parts:

1. Settled calibration sweep:
   - Purpose: fit `pKa_eff` and `b_pH`.
   - Inputs: 8-12 target ratios across the useful acetate buffer range.
   - Output metric: settled `PH_2` versus `pH_HH`.

2. Dynamic step tests:
   - Purpose: identify `theta_tube`, `V_mix`, and `tau_sensor`.
   - Inputs: step the acid/acetate ratio at at least two total flow rates.
   - Required metadata: mixer location, tubing lengths, tubing inner diameters, sensor location, and sampling time.
   - Output metric: measured step response fitted by delay plus first-order or tanks-in-series dynamics.

Success criterion:

- `PH_2` should vary monotonically with `log10(F_A/F_H)`.
- The fitted relation `PH_2 = b_0 + b_1 pH_HH` should be stable across repeated targets.
- The settled-sample RMSE after fitting effective `pKa` and pH bias should be below the raw HH-model RMSE from this dataset.
- The dynamic model should predict the transient `PH_2` response after ratio steps better than the instantaneous steady-state HH model.

After this experiment, the next code step should be a `DynamicBufferModel` that wraps the existing steady-state chemistry with explicit delay and first-order/tanks-in-series mixing. Only after that baseline predicts measured pH should the project add feedback control, MPC, or RL.
