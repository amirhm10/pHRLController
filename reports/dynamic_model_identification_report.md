# Dynamic pH Model Identification Report

Generated from result folder: `results/dynamic_model_identification_20260522_013357`

Data source: `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv`

This report summarizes the staged dynamic-identification workflow for predicting the valid pH measurement, `PH_2`, from the three inlet flowrates. It is not a controller, MPC, RL, reward-design, or target-tracking report. The target pH and `PH_1` are intentionally excluded from the model metrics.

## Executive Summary

The dynamic workflow tested four modeling stages:

| Stage | Question tested | Result |
| --- | --- | --- |
| Equilibrium baseline | Can first-principles charge balance directly predict `PH_2`? | Useful shape, but biased high relative to `PH_2`. |
| Effective static calibration | Is measured pH a shifted or compressed version of equilibrium pH? | Yes. This gives the major improvement. |
| Delay search | Does delayed chemistry explain current `PH_2` better? | No. Best lag is `0` samples. |
| Combined delay plus sensor/mixing dynamics | Does a first-order dynamic wrapper improve held-out prediction? | No additional improvement beyond static calibration. |

The main finding is that the current lab CSV supports an effective static calibration, but it does not identify a reliable transport delay or sensor/mixing dynamic model at the current sampling rate. The equilibrium test RMSE is `0.4412 pH`; after affine calibration it drops to `0.1148 pH`, a `0.3264 pH` reduction, about `74.0%`. Delay and first-order dynamics do not reduce the held-out error further.

## Data Mapping

The modeling input and output are:

| Quantity | CSV column | Use |
| --- | --- | --- |
| Measured pH | `observation.biosmb-sensors.PH_2` | only valid pH output |
| Acetic acid flow | `observation.biosmb-flows[0]` | inlet acid flow |
| Sodium acetate flow | `observation.biosmb-flows[1]` | inlet base/conjugate-base flow |
| Arium water flow | `observation.biosmb-flows[2]` | dilution and total-flow diagnostic |

`PH_1` is not used because it was not connected during operation. `target_ph` is not used because this report is about plant prediction, not controller performance.

The processed data contain `1086` chronological rows and `1085` rows valid for model prediction. Trial segmentation produced `85` trials using long time gaps, step resets, and episode resets. The train/test split keeps trials intact: `59` early trials for training and `26` later trials for testing. The median sampling interval is `69.98 s`, and the median total flow is `16.35 mL/min`.

## Step 1: Equilibrium Chemistry Baseline

The first-principles chemistry stage computes the mixed analytical concentrations from the inlet flows:

$$
F_T = F_H + F_A + F_W
$$

$$
C_H = C_{H,0}\frac{F_H}{F_T}, \qquad
C_A = C_{A,0}\frac{F_A}{F_T}
$$

$$
C_T = C_H + C_A, \qquad C_{Na} = C_A
$$

where `H` denotes acetic acid, `A` denotes sodium acetate, and water only changes the dilution and total flow. The stock concentrations are both `100 mM`.

The charge-balance model solves for hydrogen ion concentration:

$$
f(H^+) =
H^+ + C_{Na}
- \frac{C_T K_a}{K_a + H^+}
- \frac{K_w}{H^+}
= 0
$$

and then computes:

$$
pH_{eq} = -\log_{10}(H^+)
$$

This baseline has no fitted parameters in this workflow. It is the current first-principles steady-state chemistry prediction.

## Step 2: Effective Static Calibration

The next test asks whether the measured pH behaves like a shifted or compressed version of the equilibrium prediction:

$$
\hat y_k = b_0 + b_1 pH_{eq,k}
$$

where:

| Symbol | Meaning |
| --- | --- |
| \(y_k\) | measured `PH_2` at sample \(k\) |
| \(pH_{eq,k}\) | equilibrium charge-balance prediction from the inlet flows |
| \(b_0\) | pH bias or intercept correction |
| \(b_1\) | gain or compression factor |

The parameters were estimated on train trials only using ordinary least squares:

$$
(b_0^\*, b_1^\*) =
\arg\min_{b_0,b_1}
\sum_{k \in \mathcal{D}_{train}}
\left(y_k - b_0 - b_1 pH_{eq,k}\right)^2
$$

Implementation detail: this is a linear least-squares fit using `numpy.linalg.lstsq`.

Estimated parameters:

| Parameter | Value | Interpretation |
| --- | ---: | --- |
| \(b_0\) | `1.140444` | intercept correction |
| \(b_1\) | `0.692802` | measured pH is compressed relative to equilibrium pH |
| train samples | `826` | samples used for the least-squares fit |

The slope is well below `1`, so the measured pH range is compressed relative to the equilibrium prediction. At equal acid/base chemistry near `pKa = 4.76`, the calibrated prediction is:

$$
b_0 + b_1 pK_a = 4.4382
$$

This is about `0.3218 pH` below the nominal pKa. This should not yet be interpreted as the true thermodynamic pKa. It is an effective plant/probe calibration that may include sensor calibration, temperature, activity effects, stock concentration mismatch, CO2/water effects, incomplete mixing, and closed-loop data bias.

## Step 3: Empirical Delay Search

The delay test asks whether past chemistry better explains current `PH_2`:

$$
\hat y_k(d) = b_0(d) + b_1(d)pH_{eq,k-d}
$$

The delay \(d\) is an integer sample lag. Lags were tested from `0` to `10` samples, and lagging was done within each trial only so no future or cross-trial information leaks into the model.

For each candidate lag:

$$
(b_0^\*(d), b_1^\*(d)) =
\arg\min_{b_0,b_1}
\sum_{k \in \mathcal{D}_{train}}
\left(y_k - b_0 - b_1 pH_{eq,k-d}\right)^2
$$

Then the selected lag was:

$$
d^\* = \arg\min_d RMSE_{train}(d)
$$

Estimated delay result:

| Parameter | Value |
| --- | ---: |
| best lag \(d^\*\) | `0` samples |
| approximate delay \(\theta = d^\* \Delta t_{median}\) | `0.0 s` |
| train RMSE at best lag | `0.1848 pH` |
| test RMSE at best lag | `0.1148 pH` |

The best train lag is zero. Longer lags are worse on training data. This does not prove that the real plant has zero physical delay. It means the current one-minute, closed-loop dataset does not identify a delay larger than one sample in this staged model.

## Step 4: Sensor And Mixing Dynamics

The dynamic test wraps the calibrated chemistry signal in a first-order response:

$$
x_k = b_0 + b_1 pH_{eq,k-d^\*}
$$

$$
\hat y_k =
\alpha_k \hat y_{k-1}
+ (1-\alpha_k)x_k
$$

$$
\alpha_k =
\exp\left(-\frac{\Delta t_k}{\tau}\right)
$$

where \(\tau\) is an empirical combined time constant. It can include mixing, tubing residence-time distribution, pH-probe response, transmitter filtering, and synchronization effects. Because the required hardware geometry is not yet available, \(\tau\) is a diagnostic parameter, not a trusted physical volume estimate.

The time constant was estimated by nonlinear scalar optimization on train data:

$$
\tau^\* =
\arg\min_{\tau > 0}
\sqrt{
\frac{1}{N_{train}}
\sum_{k \in \mathcal{D}_{train}}
\left(y_k - \hat y_k(\tau)\right)^2
}
$$

Implementation detail: the optimization is a bounded one-dimensional minimization over \(\log(\tau)\) using `scipy.optimize.minimize_scalar`.

Estimated dynamic parameters:

| Parameter | Value | Comment |
| --- | ---: | --- |
| \(\tau^\*\) | `1.7033 s` | empirical first-order time constant |
| \(\tau^\*\) | `0.0284 min` | same value in minutes |
| median sample time | `69.9825 s` | much larger than fitted \(\tau\) |
| median total flow | `16.3493 mL/min` | used for approximate volume |
| approximate effective volume | `0.4641 mL` | \(\tau F_T / 60\), provisional only |
| optimizer success | `True` | scalar fit converged |

Because \(\tau^\* = 1.70 s\) is far below the median sampling interval of `69.98 s`, the first-order model effectively reaches the calibrated input within one sample. Therefore, the dynamic prediction collapses to the static calibrated prediction at this data resolution.

## Step 5: Combined Model

The combined model is:

$$
x_k =
b_0^\*
+ b_1^\* pH_{eq,k-d^\*}
$$

$$
\hat y_k =
\exp\left(-\frac{\Delta t_k}{\tau^\*}\right)\hat y_{k-1}
+
\left[
1-\exp\left(-\frac{\Delta t_k}{\tau^\*}\right)
\right]x_k
$$

with:

| Parameter | Estimated value |
| --- | ---: |
| \(b_0^\*\) | `1.140444` |
| \(b_1^\*\) | `0.692802` |
| \(d^\*\) | `0` samples |
| \(\tau^\*\) | `1.7033 s` |

This is the most complete model in the current workflow. Numerically, it gives the same train/test metrics as the static calibrated model because the selected delay is zero and the fitted time constant is too fast relative to the sample interval.

## Train And Test Metrics

| Model stage | Split | N | Mean error | MAE | RMSE | Max abs | Corr. |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Equilibrium baseline | train | 826 | -0.3274 | 0.3495 | 0.3918 | 1.1517 | 0.8030 |
| Equilibrium baseline | test | 259 | -0.4337 | 0.4337 | 0.4412 | 0.6749 | 0.9832 |
| Static calibrated | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| Static calibrated | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |
| Lag calibrated | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| Lag calibrated | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |
| First-order dynamic combined | train | 826 | -0.0000 | 0.1443 | 0.1848 | 0.7634 | 0.8030 |
| First-order dynamic combined | test | 259 | -0.0903 | 0.0923 | 0.1148 | 0.2952 | 0.9832 |

The RMSE improvement happens at the static calibration step. Delay and first-order dynamics add no held-out improvement in this dataset.

## Figures

![Measured versus dynamic prediction](../results/dynamic_model_identification_20260522_013357/figures/measured_vs_dynamic_prediction_time.png)

![Dynamic prediction scatter](../results/dynamic_model_identification_20260522_013357/figures/measured_vs_dynamic_prediction_scatter.png)

![Residual time by model](../results/dynamic_model_identification_20260522_013357/figures/residual_time_by_model.png)

![Residual histogram by model](../results/dynamic_model_identification_20260522_013357/figures/residual_histogram_by_model.png)

![Lag search RMSE](../results/dynamic_model_identification_20260522_013357/figures/lag_search_rmse.png)

![Dynamic trial examples](../results/dynamic_model_identification_20260522_013357/figures/dynamic_prediction_by_trial_examples.png)

![Train/test metric comparison](../results/dynamic_model_identification_20260522_013357/figures/train_test_metric_comparison.png)

## Findings

1. The equilibrium charge-balance model is structurally useful but biased. It tracks the monotonic relationship well, especially on test data where correlation is `0.9832`, but it overpredicts measured `PH_2` by about `0.4337 pH` on average in the test split.

2. The effective static calibration is necessary. The fitted slope `0.6928` indicates compression of measured pH relative to equilibrium pH, and the intercept `1.1404` shifts the scale. This reduces held-out RMSE from `0.4412` to `0.1148 pH`.

3. No transport delay is identifiable from this CSV with integer sample lags. The best lag is `0` samples. This does not rule out physical tubing delay, but the dataset and sampling period do not support estimating it reliably.

4. Sensor/mixing dynamics are not identifiable at the current sample resolution. The fitted \(\tau\) is `1.70 s`, far below the median sample interval. At one-minute sampling, that behaves like an instantaneous static mapping.

5. The combined model is not meaningfully more dynamic than the static calibrated model. It has the same train and test RMSE because \(d^\*=0\) and \(\tau^\* \ll \Delta t_{median}\).

6. The held-out mean residual after calibration remains `-0.0903 pH`. This remaining bias suggests that the effective calibration learned from early trials does not perfectly transfer to later trials.

## Interpretation

The current data look dynamic in time, but they are not ideal for dynamic plant identification. They appear to be controller-generated closed-loop data with irregular sampling and trial resets. Because the controller is already choosing flows based on the process state, the inlet signals are not independent excitation signals. This makes it hard to separate chemistry, delay, mixing, and sensor response.

The best conclusion is:

$$
PH_2 \approx 1.1404 + 0.6928\,pH_{eq}
$$

for the current dataset and measurement setup. This should be treated as an empirical effective pH measurement model, not a final physical model. A dynamic simulator should not yet use the fitted delay or time constant as trusted physical parameters.

## What We Need Next

The next safe development step is a designed open-loop identification experiment before building a dynamic simulator. The experiment should include:

- Step changes in acid/acetate ratio at fixed total flow.
- Step changes in total flow at fixed acid/acetate ratio.
- Long enough hold periods for `PH_2` to visibly settle.
- Repeated steps to check reproducibility and hysteresis.
- Hardware metadata: where the streams first meet, tubing inner diameter and length to `PH_2`, static mixer or flow-cell volume, pH probe location, pH probe response time, and logger synchronization.

With that experiment, the next model can separate:

$$
\theta(t) \approx \frac{V_{tube}}{F_T(t)}
$$

from:

$$
\tau(t) \approx \frac{V_{mix}}{F_T(t)}
$$

and from the pH probe response:

$$
\tau_s \frac{dy}{dt} = pH_{chem}(t-\theta) - y(t)
$$

For now, the reliable model result is the calibrated static first-principles mapping. The dynamic parameters should stay diagnostic until the lab experiment provides enough excitation and physical metadata.

## Generated Tables

- `preprocessed_lab_data`: `results/dynamic_model_identification_20260522_013357/tables/preprocessed_lab_data.csv`
- `dynamic_model_comparison`: `results/dynamic_model_identification_20260522_013357/tables/dynamic_model_comparison.csv`
- `model_metrics_train_test`: `results/dynamic_model_identification_20260522_013357/tables/model_metrics_train_test.csv`
- `static_calibration_parameters`: `results/dynamic_model_identification_20260522_013357/tables/static_calibration_parameters.csv`
- `lag_search_metrics`: `results/dynamic_model_identification_20260522_013357/tables/lag_search_metrics.csv`
- `dynamic_parameters`: `results/dynamic_model_identification_20260522_013357/tables/dynamic_parameters.csv`
- `trial_split_summary`: `results/dynamic_model_identification_20260522_013357/tables/trial_split_summary.csv`
