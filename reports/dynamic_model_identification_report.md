# Full pH Model Development Story

This report tells the full modeling sequence so far for the inline acetate-buffer pH process. The objective is to predict the reliable measured output, `PH_2`, from the three inlet flowrates:

- acetic acid, 100 mM,
- sodium acetate, 100 mM,
- Arium ultrapure water.

This is not a controller, MPC, RL, reward-design, or target-tracking report. The target pH is intentionally excluded from model-validation metrics. `PH_1` is also excluded because it was not connected during operation.

## Executive Conclusion

We tested three model levels:

| Attempt | Model | Main result | Conclusion |
| --- | --- | --- | --- |
| 1 | Ideal Henderson-Hasselbalch | RMSE `0.4037 pH`, mean error `-0.3519 pH` | Failed as a direct plant model. It overpredicts `PH_2` and misses measurement compression. |
| 2 | Equilibrium charge balance | RMSE `0.4042 pH`, mean error `-0.3527 pH` | Also failed as a direct plant model. More chemistry detail did not solve the mismatch. |
| 3 | Dynamic identification from equilibrium pH | calibrated test RMSE `0.1148 pH`, best lag `0`, fitted `tau = 1.7033 s` | Static calibration is useful, but delay and sensor/mixing dynamics are not identifiable from this CSV. |

The main scientific finding is:

$$
PH_2 \approx 1.1404 + 0.6928\,pH_{eq}
$$

for this dataset and measurement setup. This is an empirical effective calibration, not a final physical dynamic model. The current CSV looks dynamic in time, but it is not rich enough to identify transport delay, mixing volume, or pH-probe dynamics reliably.

## Common Data And Validation Setup

The lab CSV used in these workflows is:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset.csv
```

The mapping is fixed:

| Quantity | CSV column | Role |
| --- | --- | --- |
| measured pH | `observation.biosmb-sensors.PH_2` | only reliable output |
| acetic acid flow | `observation.biosmb-flows[0]` | acid inlet |
| sodium acetate flow | `observation.biosmb-flows[1]` | acetate inlet |
| Arium water flow | `observation.biosmb-flows[2]` | water inlet |

Rows were sorted chronologically. Rows with nonpositive acid, acetate, or water flow were excluded from model metrics. The static steady-state workflows used `1085` valid rows and excluded `1` row. The dynamic workflow segmented the data into `85` chronological trials and used a trial-aware split: `59` early trials for fitting and `26` later trials for testing.

The median valid sample interval in the dynamic workflow is `69.98 s`, and the median total flow is `16.35 mL/min`.

## Attempt 1: Ideal Henderson-Hasselbalch Model

### Purpose

The first attempt was the simplest first-principles buffer model. It asks:

Can the acid/acetate inlet ratio directly predict the measured outlet pH?

This is the ideal model we would like to use if mixing is immediate, the probe is accurate, activity effects are negligible, and the outlet is at steady state.

### Mathematics

For an acetate buffer:

$$
pH = pK_a + \log_{10}\left(\frac{[A^-]}{[HA]}\right)
$$

The stock acid and acetate concentrations are both `100 mM`. If the two stock concentrations are equal and the streams are ideally mixed, the concentration ratio equals the flow ratio:

$$
\frac{[A^-]}{[HA]} =
\frac{C_{A,0}F_A/F_T}{C_{H,0}F_H/F_T}
=
\frac{F_A}{F_H}
$$

Therefore the implemented ideal prediction is:

$$
pH_{HH} =
pK_a + \log_{10}\left(\frac{F_A}{F_H}\right)
$$

where:

| Symbol | Meaning |
| --- | --- |
| \(F_H\) | acetic acid flow |
| \(F_A\) | sodium acetate flow |
| \(F_T\) | total flow \(F_H + F_A + F_W\) |
| \(pK_a\) | acetic acid pKa, configured as `4.76` |

Water affects dilution, total flow, residence time, and measurement sensitivity. In the ideal Henderson-Hasselbalch ratio with equal stock concentrations, water does not change the predicted pH.

### Workflow

The runner used the lab CSV, mapped `PH_2` as the measured output, computed `pH_HH`, and evaluated:

$$
e_k = PH_{2,k} - pH_{HH,k}
$$

It also saved figures and diagnostics under:

```text
results/henderson_hasselbalch_lab_validation_20260522_003559/
```

### Results

| Metric | Value |
| --- | ---: |
| valid rows | `1085` |
| mean error, `PH_2 - pH_HH` | `-0.3519 pH` |
| MAE | `0.3690 pH` |
| RMSE | `0.4037 pH` |
| max absolute error | `1.1514 pH` |
| correlation | `0.8346` |

An affine diagnostic was also computed:

$$
PH_2 \approx a + b\,pH_{HH}
$$

with:

| Diagnostic parameter | Value |
| --- | ---: |
| intercept \(a\) | `1.0139` |
| slope \(b\) | `0.7148` |
| affine diagnostic RMSE | `0.1692 pH` |

The slope below `1` is important. It shows that the measured pH is compressed relative to the ideal prediction. The negative mean error means the ideal model usually predicts pH higher than `PH_2`.

### Figures

![Henderson-Hasselbalch time response](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_vs_hh_prediction_time.png)

![Henderson-Hasselbalch scatter](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_vs_hh_prediction_scatter.png)

![Henderson-Hasselbalch residual over time](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_minus_hh_time.png)

![Henderson-Hasselbalch residual histogram](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_minus_hh_histogram.png)

![Henderson-Hasselbalch lag scan](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/lag_scan_diagnostic.png)

### Interpretation

The ideal Henderson-Hasselbalch model did not work as a direct simulation model for this dataset. It captures the general monotonic chemistry trend, but the residuals are too biased and too large. The high correlation is not enough because the model has a systematic scale and offset mismatch.

This failure suggested that either the measurement setup, stock concentrations, activity effects, mixing, closed-loop sampling, or dynamics are not represented by the ideal formula.

## Attempt 2: Equilibrium Charge-Balance Model

### Purpose

The second attempt added a more rigorous steady-state chemistry calculation. The question was:

If Henderson-Hasselbalch is too ideal, does solving the acetate equilibrium charge balance improve the pH prediction?

This model includes dilution and water through the mixed analytical concentrations, and it solves for hydrogen ion concentration directly.

### Mathematics

The inlet flows define the mixed analytical concentrations:

$$
F_T = F_H + F_A + F_W
$$

$$
C_H = C_{H,0}\frac{F_H}{F_T}
$$

$$
C_A = C_{A,0}\frac{F_A}{F_T}
$$

$$
C_T = C_H + C_A
$$

$$
C_{Na} = C_A
$$

For acetic acid equilibrium:

$$
K_a = 10^{-pK_a}
$$

The acetate species concentration implied by equilibrium is:

$$
[A^-] =
\frac{C_T K_a}{K_a + H^+}
$$

The hydroxide concentration is:

$$
[OH^-] = \frac{K_w}{H^+}
$$

The charge balance is:

$$
f(H^+) =
H^+ + C_{Na}
- \frac{C_TK_a}{K_a + H^+}
- \frac{K_w}{H^+}
= 0
$$

After solving for \(H^+\):

$$
pH_{eq} = -\log_{10}(H^+)
$$

### Workflow

The runner computed mixed analytical concentrations from acid, acetate, and water flows, solved the charge-balance root for each valid row, compared the prediction with `PH_2`, and saved artifacts under:

```text
results/equilibrium_charge_balance_lab_validation_20260522_005207/
```

### Results

| Metric | Value |
| --- | ---: |
| valid rows | `1085` |
| mean error, `PH_2 - pH_eq` | `-0.3527 pH` |
| MAE | `0.3696 pH` |
| RMSE | `0.4042 pH` |
| max absolute error | `1.1517 pH` |
| correlation | `0.8346` |

Affine diagnostic:

$$
PH_2 \approx a + b\,pH_{eq}
$$

| Diagnostic parameter | Value |
| --- | ---: |
| intercept \(a\) | `1.0059` |
| slope \(b\) | `0.7164` |
| affine diagnostic RMSE | `0.1692 pH` |

### Figures

![Equilibrium time response](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/measured_vs_equilibrium_prediction_time.png)

![Equilibrium scatter](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/measured_vs_equilibrium_prediction_scatter.png)

![Equilibrium residual over time](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/measured_minus_equilibrium_time.png)

![Equilibrium residual histogram](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/measured_minus_equilibrium_histogram.png)

![Equilibrium total buffer concentration](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/total_buffer_concentration_trajectory.png)

![Equilibrium residual versus total buffer](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/residual_vs_total_buffer.png)

### Interpretation

The equilibrium charge-balance model also failed as a direct plant model. Its RMSE is `0.4042 pH`, almost identical to the ideal Henderson-Hasselbalch RMSE of `0.4037 pH`.

This is an important negative result. It means the failure is probably not caused by Henderson-Hasselbalch algebra alone. Adding ideal equilibrium chemistry and dilution does not resolve the gap between first-principles pH and the lab `PH_2` measurement.

The next hypothesis became:

The chemistry calculation may be structurally useful, but the measured process needs effective calibration and possibly time dynamics.

## Attempt 3: Dynamic Identification And Effective Calibration

### Purpose

The lab data are chronological and appear dynamic. The sampling interval is about one minute, and the data came from controller operation rather than clean steady-state holds. The third attempt therefore asked:

Can we start from equilibrium chemistry and identify the missing static calibration, delay, and first-order sensor or mixing dynamics?

This attempt is still not a controller. It is an input-output model-identification workflow.

### Data Split

The dynamic workflow segmented the data into trials using long time gaps, step resets, and episode resets. It then used chronological trial splitting:

| Split | Trials | Samples used in metrics |
| --- | ---: | ---: |
| train | `59` | `826` |
| test | `26` | `259` |

Keeping whole trials together prevents lagged features and dynamic states from leaking across trial boundaries.

### Stage 3.1: Equilibrium Baseline

The baseline dynamic workflow starts with the same equilibrium prediction:

$$
\hat y_k = pH_{eq,k}
$$

This baseline has no fitted parameters.

### Stage 3.2: Effective Static Calibration

The first fitted model is:

$$
\hat y_k = b_0 + b_1pH_{eq,k}
$$

The parameters were estimated on train trials only with ordinary least squares:

$$
(b_0^{*}, b_1^{*}) =
\underset{b_0,b_1}{\mathrm{arg\,min}}
\sum_{k \in D_{train}}
\left(y_k - b_0 - b_1pH_{eq,k}\right)^2
$$

Implementation: `numpy.linalg.lstsq`.

Estimated parameters:

| Parameter | Value | Meaning |
| --- | ---: | --- |
| \(b_0^{*}\) | `1.140444` | effective pH intercept |
| \(b_1^{*}\) | `0.692802` | effective pH compression |
| train samples | `826` | samples used for fitting |

At equal acid/base chemistry near \(pK_a = 4.76\), this calibrated mapping gives:

$$
b_0^{*} + b_1^{*}pK_a = 4.4382
$$

This value should not be called the true thermodynamic pKa. It is an effective measurement/process calibration.

### Stage 3.3: Integer Delay Search

The delay model is:

$$
\hat y_k(d) =
b_0(d) + b_1(d)pH_{eq,k-d}
$$

For each integer lag from `0` to `10` samples, the affine parameters were refit on train data:

$$
(b_0^{*}(d), b_1^{*}(d)) =
\underset{b_0,b_1}{\mathrm{arg\,min}}
\sum_{k \in D_{train}}
\left(y_k - b_0 - b_1pH_{eq,k-d}\right)^2
$$

The selected lag was:

$$
d^{*} =
\underset{d}{\mathrm{arg\,min}}\ RMSE_{train}(d)
$$

Result:

| Parameter | Value |
| --- | ---: |
| best lag \(d^{*}\) | `0` samples |
| approximate delay \(\theta = d^{*}\Delta t_{median}\) | `0.0 s` |
| train RMSE at best lag | `0.1848 pH` |
| test RMSE at best lag | `0.1148 pH` |

This does not prove the physical delay is zero. It says this closed-loop CSV, sampled roughly once per minute, does not identify a useful integer lag larger than zero.

### Stage 3.4: First-Order Sensor And Mixing Dynamics

The first-order dynamic wrapper uses the calibrated and delayed chemistry signal:

$$
x_k =
b_0^{*} + b_1^{*}pH_{eq,k-d^{*}}
$$

and filters it through:

$$
\hat y_k =
\alpha_k\hat y_{k-1}
+ (1-\alpha_k)x_k
$$

$$
\alpha_k =
\exp\left(-\frac{\Delta t_k}{\tau}\right)
$$

The time constant was fit by one-dimensional nonlinear optimization:

$$
\tau^{*} =
\underset{\tau > 0}{\mathrm{arg\,min}}
\sqrt{
\frac{1}{N_{train}}
\sum_{k \in D_{train}}
\left(y_k - \hat y_k(\tau)\right)^2
}
$$

Implementation: bounded scalar optimization over \(\log(\tau)\) using `scipy.optimize.minimize_scalar`.

Estimated parameters:

| Parameter | Value | Interpretation |
| --- | ---: | --- |
| \(\tau^{*}\) | `1.7033 s` | empirical combined sensor/mixing time constant |
| \(\tau^{*}\) | `0.0284 min` | same value in minutes |
| median sample interval | `69.9825 s` | much slower than fitted \(\tau^{*}\) |
| median total flow | `16.3493 mL/min` | used for provisional volume |
| approximate effective volume | `0.4641 mL` | \(\tau^{*}F_T/60\), diagnostic only |

Because `1.7033 s` is far smaller than the median sample interval, the first-order model effectively settles within one sample. Therefore the dynamic model collapses to the static calibrated model at this data resolution.

### Dynamic Workflow Results

The dynamic workflow result folder is:

```text
results/dynamic_model_identification_20260522_013357/
```

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

### Figures

![Dynamic time response](../results/dynamic_model_identification_20260522_013357/figures/measured_vs_dynamic_prediction_time.png)

![Dynamic scatter](../results/dynamic_model_identification_20260522_013357/figures/measured_vs_dynamic_prediction_scatter.png)

![Dynamic residuals by model](../results/dynamic_model_identification_20260522_013357/figures/residual_time_by_model.png)

![Dynamic residual histograms](../results/dynamic_model_identification_20260522_013357/figures/residual_histogram_by_model.png)

![Dynamic lag search](../results/dynamic_model_identification_20260522_013357/figures/lag_search_rmse.png)

![Dynamic trial examples](../results/dynamic_model_identification_20260522_013357/figures/dynamic_prediction_by_trial_examples.png)

![Dynamic train/test comparison](../results/dynamic_model_identification_20260522_013357/figures/train_test_metric_comparison.png)

### Interpretation

The dynamic workflow did not identify useful dynamic parameters from this CSV. It did identify a strong effective static calibration. The useful model from this workflow is:

$$
PH_2 \approx 1.1404 + 0.6928\,pH_{eq}
$$

The delay estimate is `0` samples, and the fitted first-order time constant is much smaller than the sample interval. That means the available data do not support a trusted delay, tubing-volume, mixing-volume, or probe-time-constant estimate.

## Cross-Model Comparison

| Model | Fitted? | Validation basis | RMSE | Mean error | Main lesson |
| --- | --- | --- | ---: | ---: | --- |
| Ideal Henderson-Hasselbalch | no | all valid rows | `0.4037` | `-0.3519` | Ratio chemistry alone is biased and too wide in pH range. |
| Equilibrium charge balance | no | all valid rows | `0.4042` | `-0.3527` | More equilibrium detail does not fix the lab mismatch. |
| Static calibrated equilibrium | yes | held-out test trials | `0.1148` | `-0.0903` | Effective calibration is necessary and useful. |
| Lag calibrated equilibrium | yes | held-out test trials | `0.1148` | `-0.0903` | No lag improvement is identifiable. |
| First-order dynamic combined | yes | held-out test trials | `0.1148` | `-0.0903` | No additional dynamic improvement is identifiable. |

The two direct first-principles steady-state models fail in essentially the same way. Henderson-Hasselbalch and equilibrium charge balance differ by only `0.0005 pH` RMSE. This tells us the main missing ingredient is not just the equilibrium chemistry equation.

The calibrated model reduces RMSE by about `0.289 pH` relative to the equilibrium steady-state model, a reduction of about `71.6%`. However, the remaining test residual mean is still `-0.0903 pH`, so the calibrated model is not perfect and may not transfer across operating days without recalibration.

## What We Know Now

1. `PH_2` is not directly equal to ideal buffer pH from acid/acetate flow ratio.

2. The equilibrium charge-balance model is scientifically better than Henderson-Hasselbalch, but it does not improve this dataset because the operating range is still dominated by the same acid/acetate ratio and measurement mismatch.

3. The measurement appears compressed relative to ideal pH. The best calibrated slope is about `0.69` to `0.72`, depending on the fitting workflow.

4. The current closed-loop CSV does not identify delay or first-order dynamics. The data may be dynamic, but the sampling interval and input excitation are not enough for reliable dynamic identification.

5. The current best empirical predictor is a calibrated equilibrium pH model, not a physical dynamic simulator.

## What We Should Do Next

The next safe step is a designed open-loop identification experiment. The current data were useful for diagnosing model mismatch, but not sufficient for dynamic physics.

The next experiment should include:

- step changes in acid/acetate ratio at fixed total flow,
- step changes in total flow at fixed acid/acetate ratio,
- long holds after each step until `PH_2` visibly settles,
- repeated steps to check reproducibility,
- known timing between commanded flows and logged pH,
- metadata for where the streams first meet,
- tubing inner diameter and length from mixer to `PH_2`,
- static mixer, flow-cell, or dead-volume estimates,
- pH probe location and response time.

With that information, the next model can separate transport delay:

$$
\theta(t) \approx \frac{V_{tube}}{F_T(t)}
$$

mixing residence time:

$$
\tau_{mix}(t) \approx \frac{V_{mix}}{F_T(t)}
$$

and pH sensor response:

$$
\tau_s\frac{dy}{dt} =
pH_{chem}(t-\theta) - y(t)
$$

Until that experiment is available, the model should be treated as:

$$
PH_2 =
\text{effective calibrated chemistry}
+ \text{unidentified dynamic residual}
$$

not as a validated dynamic simulator.

## Artifact Index

Henderson-Hasselbalch artifacts:

- `results/henderson_hasselbalch_lab_validation_20260522_003559/tables/overall_metrics.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_003559/tables/affine_diagnostic.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_003559/tables/lag_scan.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_003559/figures/`

Equilibrium charge-balance artifacts:

- `results/equilibrium_charge_balance_lab_validation_20260522_005207/tables/overall_metrics.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_005207/tables/affine_diagnostic.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_005207/tables/lag_scan.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/`

Dynamic identification artifacts:

- `results/dynamic_model_identification_20260522_013357/tables/model_metrics_train_test.csv`
- `results/dynamic_model_identification_20260522_013357/tables/static_calibration_parameters.csv`
- `results/dynamic_model_identification_20260522_013357/tables/lag_search_metrics.csv`
- `results/dynamic_model_identification_20260522_013357/tables/dynamic_parameters.csv`
- `results/dynamic_model_identification_20260522_013357/figures/`
