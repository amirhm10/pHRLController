# Full pH Model Development Story After Flat-Trial Filtering

This report summarizes the current first-principles modeling sequence for the inline acetate-buffer pH process. The goal is to predict the reliable measured output, `PH_2`, from the three inlet flowrates:

- acetic acid, 100 mM,
- sodium acetate, 100 mM,
- Arium ultrapure water.

This is not a controller, MPC, RL, reward-design, or target-tracking report. The target pH is intentionally excluded from model-validation metrics. `PH_1` is also excluded because it was not connected during operation.

The latest runs used here are:

| Workflow | Result folder |
| --- | --- |
| Henderson-Hasselbalch validation | `results/henderson_hasselbalch_lab_validation_20260522_021555/` |
| Equilibrium charge-balance validation | `results/equilibrium_charge_balance_lab_validation_20260522_021608/` |
| Dynamic model identification | `results/dynamic_model_identification_20260522_021628/` |

## Executive Conclusion

The three model levels now tell a clearer story after the low-information flat-pH trials were removed from model metrics.

| Attempt | Model | Main result after filtering | Conclusion |
| --- | --- | --- | --- |
| 1 | Ideal Henderson-Hasselbalch | RMSE `0.3976 pH`, mean error `-0.3660 pH` on `990` valid rows | Failed as a direct plant model. It captures trend but overpredicts `PH_2`. |
| 2 | Equilibrium charge balance | RMSE `0.3982 pH`, mean error `-0.3668 pH` on `990` valid rows | Also failed as a direct plant model. More ideal equilibrium chemistry did not fix the measurement/process mismatch. |
| 3 | Dynamic identification from equilibrium pH | test RMSE improved from `0.4412 pH` to `0.0975 pH` after static calibration, best lag `0`, fitted `tau = 1.8741 s` | Static calibration is the useful step. Delay and first-order dynamics are not identifiable from this CSV at the current sampling rate. |

The main empirical relationship found from train trials is:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

This is an effective calibration of the lab measurement and process, not a final physical dynamic model. The data are chronological and dynamic-looking, but the current CSV still does not support a trusted estimate of tubing delay, mixing volume, or pH-probe time constant.

## Common Data And Preprocessing

The lab CSV used in all three workflows is:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset.csv
```

The fixed data mapping is:

| Quantity | CSV column | Role |
| --- | --- | --- |
| measured pH | `observation.biosmb-sensors.PH_2` | only reliable output |
| acetic acid flow | `observation.biosmb-flows[0]` | acid inlet |
| sodium acetate flow | `observation.biosmb-flows[1]` | acetate inlet |
| Arium water flow | `observation.biosmb-flows[2]` | water inlet |

Rows were sorted chronologically. Rows with nonpositive acid, acetate, or water flow are excluded from model metrics.

### Flat-Trial Removal

The updated preprocessing marks low-information flat-pH trials as not valid for model fitting or metrics. These trials are not deleted from exported data. They remain in `preprocessed_lab_data.csv` with audit columns, but `valid_for_model = False`.

The rule is:

$$
\Delta PH_2 \le 0.05
\quad\text{and}\quad
\Delta \log_{10}(F_A/F_H) \ge 0.5
\quad\text{and}\quad
n \ge 5
$$

This catches trials where the flow-ratio input changes strongly, but the measured `PH_2` stays almost flat. Such segments are weak or misleading for calibrating a flow-to-pH model.

The latest preprocessing found:

| Quantity | Value |
| --- | ---: |
| total source rows | `1086` |
| rows valid before flat-trial filtering | `1085` |
| rows valid after all filters | `990` |
| low-information flat-pH rows flagged | `96` |
| otherwise valid rows removed by flat-trial filtering | `95` |
| flat trials flagged | `8`, `9`, `10`, `33` |

The dynamic train/test split still contains the full chronological trial list, but these flagged trials have `n_model_valid = 0`:

| Trial | Split | Rows | Model-valid rows |
| --- | --- | ---: | ---: |
| `8` | train | `30` | `0` |
| `9` | train | `30` | `0` |
| `10` | train | `26` | `0` |
| `33` | train | `10` | `0` |

This matters scientifically. The earlier static calibration was distorted by trials where `PH_2` behaved like a nearly straight line even though the inlet ratio moved. Removing those trials lowered the calibrated held-out test RMSE from about `0.1148 pH` to `0.0975 pH`.

## Attempt 1: Ideal Henderson-Hasselbalch Model

### Purpose

The first model asks whether the acid/acetate inlet ratio directly predicts the outlet `PH_2` under ideal buffer assumptions.

### Mathematics

For an acetate buffer:

$$
pH = pK_a + \log_{10}\left(\frac{[A^-]}{[HA]}\right)
$$

The acid and acetate stock concentrations are both `100 mM`. Under ideal instantaneous mixing:

$$
\frac{[A^-]}{[HA]}
=
\frac{C_{A,0}F_A/F_T}{C_{H,0}F_H/F_T}
=
\frac{F_A}{F_H}
$$

Therefore:

$$
pH_{HH} =
pK_a + \log_{10}\left(\frac{F_A}{F_H}\right)
$$

where \(F_H\) is acetic acid flow, \(F_A\) is sodium acetate flow, \(F_W\) is water flow, and \(F_T = F_H + F_A + F_W\).

Water changes dilution and residence time, but it does not change the ideal Henderson-Hasselbalch pH when the acid and acetate stock concentrations are equal.

### Results

Artifacts:

```text
results/henderson_hasselbalch_lab_validation_20260522_021555/
```

| Metric | Value |
| --- | ---: |
| valid rows | `990` |
| rows excluded from model metrics | `96` |
| mean error, `PH_2 - pH_HH` | `-0.3660 pH` |
| MAE | `0.3689 pH` |
| RMSE | `0.3976 pH` |
| max absolute error | `0.8451 pH` |
| correlation | `0.9012` |

The affine diagnostic was:

$$
PH_2 \approx a + b\,pH_{HH}
$$

| Diagnostic parameter | Value |
| --- | ---: |
| intercept \(a\) | `0.6308` |
| slope \(b\) | `0.7921` |
| affine diagnostic RMSE | `0.1365 pH` |

The slope below `1` means the measured pH range is compressed relative to the ideal prediction. The negative mean error means the ideal model usually predicts pH higher than the measured `PH_2`.

### Figures

![Henderson-Hasselbalch time response](../results/henderson_hasselbalch_lab_validation_20260522_021555/figures/measured_vs_hh_prediction_time.png)

![Henderson-Hasselbalch scatter](../results/henderson_hasselbalch_lab_validation_20260522_021555/figures/measured_vs_hh_prediction_scatter.png)

![Henderson-Hasselbalch residual over time](../results/henderson_hasselbalch_lab_validation_20260522_021555/figures/measured_minus_hh_time.png)

![Henderson-Hasselbalch residual histogram](../results/henderson_hasselbalch_lab_validation_20260522_021555/figures/measured_minus_hh_histogram.png)

### Interpretation

Henderson-Hasselbalch is useful as a chemistry coordinate, but it is not accurate enough to use as a direct simulator of this lab process. The residual has a strong offset and the prediction range is too wide. The improved correlation after flat-trial filtering shows that removing bad trials helped the diagnostic, but the raw model still fails.

## Attempt 2: Equilibrium Charge-Balance Model

### Purpose

The second model tests whether a more rigorous ideal equilibrium calculation improves prediction. It includes dilution through the mixed analytical concentrations and solves for hydrogen ion concentration directly.

### Mathematics

The mixed concentrations are:

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

With \(K_a = 10^{-pK_a}\), the equilibrium acetate concentration is:

$$
[A^-] =
\frac{C_TK_a}{K_a + H^+}
$$

and water contributes:

$$
[OH^-] = \frac{K_w}{H^+}
$$

The charge-balance root is:

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

### Results

Artifacts:

```text
results/equilibrium_charge_balance_lab_validation_20260522_021608/
```

| Metric | Value |
| --- | ---: |
| valid rows | `990` |
| rows excluded from model metrics | `96` |
| mean error, `PH_2 - pH_eq` | `-0.3668 pH` |
| MAE | `0.3697 pH` |
| RMSE | `0.3982 pH` |
| max absolute error | `0.8453 pH` |
| correlation | `0.9011` |

Affine diagnostic:

$$
PH_2 \approx a + b\,pH_{eq}
$$

| Diagnostic parameter | Value |
| --- | ---: |
| intercept \(a\) | `0.6221` |
| slope \(b\) | `0.7937` |
| affine diagnostic RMSE | `0.1366 pH` |

### Figures

![Equilibrium time response](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/measured_vs_equilibrium_prediction_time.png)

![Equilibrium scatter](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/measured_vs_equilibrium_prediction_scatter.png)

![Equilibrium residual over time](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/measured_minus_equilibrium_time.png)

![Equilibrium residual histogram](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/measured_minus_equilibrium_histogram.png)

![Equilibrium total buffer concentration](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/total_buffer_concentration_trajectory.png)

![Equilibrium residual versus total buffer](../results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/residual_vs_total_buffer.png)

### Interpretation

The equilibrium charge-balance model also fails as a direct plant model. Its RMSE is `0.3982 pH`, nearly the same as the Henderson-Hasselbalch RMSE of `0.3976 pH`.

This is the important negative result: the main mismatch is not simply because Henderson-Hasselbalch was too simple. In this operating range, the ideal equilibrium model still produces almost the same biased pH coordinate. The missing pieces are likely measurement calibration, effective chemistry, flow/mixing history, and unresolved experiment timing.

## Attempt 3: Dynamic Identification And Effective Calibration

### Purpose

The lab CSV is chronological and came from a real setup. The sampling interval is roughly one minute, so the data should be treated as time-series data, not independent steady-state samples. The dynamic workflow tests three increasingly complex hypotheses:

1. the equilibrium pH coordinate needs static calibration,
2. the process has an identifiable sample delay,
3. the measurement can be improved with a first-order sensor or mixing wrapper.

This is still model identification, not control.

### Trial-Aware Split

The dynamic workflow segmented the data into chronological trials using time gaps, step resets, and episode resets. It then split whole trials:

| Split | Trials | Model-valid samples |
| --- | ---: | ---: |
| train | `59` | `731` |
| test | `26` | `259` |

The flat-pH trials were all in the train part and now contribute zero model-valid samples. Keeping whole trials together prevents lagged features and dynamic states from leaking across trial boundaries.

### Stage 3.1: Equilibrium Baseline

The baseline model is:

$$
\hat y_k = pH_{eq,k}
$$

There are no fitted parameters. On the held-out test trials, this raw baseline gives:

| Split | Mean error | MAE | RMSE | Max abs | Correlation |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `-0.3430` | `0.3470` | `0.3819` | `0.8453` | `0.8846` |
| test | `-0.4337` | `0.4337` | `0.4412` | `0.6749` | `0.9832` |

The held-out test RMSE is worse than the all-row filtered RMSE because the later test trials sit in a different operating region and have a stronger offset.

### Stage 3.2: Effective Static Calibration

The fitted static model is:

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
| \(b_0^{*}\) | `0.6567` | effective pH intercept |
| \(b_1^{*}\) | `0.7909` | effective pH compression |
| train samples | `731` | samples used for fitting |

At equal acid/base chemistry near \(pK_a = 4.76045\), this calibration predicts:

$$
b_0^{*} + b_1^{*}pK_a = 4.4218
$$

That value should not be interpreted as the true thermodynamic pKa. It is an effective lab measurement and process calibration.

Static calibration results:

| Split | Mean error | MAE | RMSE | Max abs | Correlation |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `0.0000` | `0.1223` | `0.1500` | `0.6949` | `0.8846` |
| test | `-0.0805` | `0.0822` | `0.0975` | `0.2470` | `0.9832` |

The test RMSE improves from `0.4412 pH` to `0.0975 pH`, a reduction of about `77.9%`.

### Stage 3.3: Integer Delay Search

The delayed static model is:

$$
\hat y_k(d) =
b_0(d) + b_1(d)pH_{eq,k-d}
$$

For each integer lag from `0` to `10` samples, the affine parameters were refit on train trials:

$$
(b_0^{*}(d), b_1^{*}(d)) =
\underset{b_0,b_1}{\mathrm{arg\,min}}
\sum_{k \in D_{train}}
\left(y_k - b_0 - b_1pH_{eq,k-d}\right)^2
$$

The selected lag minimizes train RMSE:

$$
d^{*} =
\underset{d}{\mathrm{arg\,min}}\ RMSE_{train}(d)
$$

Result:

| Parameter | Value |
| --- | ---: |
| best lag \(d^{*}\) | `0` samples |
| approximate delay \(\theta = d^{*}\Delta t_{median}\) | `0.0 s` |
| train RMSE at best lag | `0.1500 pH` |
| test RMSE at best lag | `0.0975 pH` |

Lag `0` being best does not mean the real physical delay is zero. It means this closed-loop CSV, with roughly one-minute sampling and irregular excitation, does not identify a useful integer sample delay.

### Stage 3.4: First-Order Sensor Or Mixing Dynamics

The first-order wrapper filters the calibrated and delayed chemistry signal:

$$
x_k =
b_0^{*} + b_1^{*}pH_{eq,k-d^{*}}
$$

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
| \(\tau^{*}\) | `1.8741 s` | empirical combined sensor/mixing time constant |
| \(\tau^{*}\) | `0.0312 min` | same value in minutes |
| median sample interval | `69.7710 s` | much slower than fitted \(\tau^{*}\) |
| median total flow | `16.3606 mL/min` | used for provisional volume |
| approximate effective volume | `0.5110 mL` | \(\tau^{*}F_T/60\), diagnostic only |

Because the fitted time constant is much smaller than the median sample interval, the first-order model effectively settles within one sample. It therefore collapses to the static calibrated model at this data resolution.

Dynamic model results:

| Model stage | Split | N | Mean error | MAE | RMSE | Max abs | Corr. |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Equilibrium baseline | train | `731` | `-0.3430` | `0.3470` | `0.3819` | `0.8453` | `0.8846` |
| Equilibrium baseline | test | `259` | `-0.4337` | `0.4337` | `0.4412` | `0.6749` | `0.9832` |
| Static calibrated | train | `731` | `0.0000` | `0.1223` | `0.1500` | `0.6949` | `0.8846` |
| Static calibrated | test | `259` | `-0.0805` | `0.0822` | `0.0975` | `0.2470` | `0.9832` |
| Lag calibrated | train | `731` | `0.0000` | `0.1223` | `0.1500` | `0.6949` | `0.8846` |
| Lag calibrated | test | `259` | `-0.0805` | `0.0822` | `0.0975` | `0.2470` | `0.9832` |
| First-order dynamic | train | `731` | `0.0000` | `0.1223` | `0.1500` | `0.6949` | `0.8846` |
| First-order dynamic | test | `259` | `-0.0805` | `0.0822` | `0.0975` | `0.2470` | `0.9832` |

### Figures

![Dynamic time response](../results/dynamic_model_identification_20260522_021628/figures/measured_vs_dynamic_prediction_time.png)

![Dynamic scatter](../results/dynamic_model_identification_20260522_021628/figures/measured_vs_dynamic_prediction_scatter.png)

![Dynamic residuals by model](../results/dynamic_model_identification_20260522_021628/figures/residual_time_by_model.png)

![Dynamic residual histograms](../results/dynamic_model_identification_20260522_021628/figures/residual_histogram_by_model.png)

![Dynamic lag search](../results/dynamic_model_identification_20260522_021628/figures/lag_search_rmse.png)

![Dynamic trial examples](../results/dynamic_model_identification_20260522_021628/figures/dynamic_prediction_by_trial_examples.png)

![Dynamic train/test comparison](../results/dynamic_model_identification_20260522_021628/figures/train_test_metric_comparison.png)

### Interpretation

The dynamic workflow found a useful static calibration, but it did not identify useful dynamic parameters. Delay stays at `0` samples, and the fitted first-order time constant is far below the sampling interval.

The corrected conclusion is:

$$
PH_2 =
\text{effective calibrated equilibrium pH}
+ \text{remaining structured residual}
$$

not:

$$
PH_2 =
\text{validated transport-delay plus sensor-dynamic model}
$$

## Cross-Model Comparison

| Model | Fitted? | Validation basis | RMSE | Mean error | Main lesson |
| --- | --- | --- | ---: | ---: | --- |
| Ideal Henderson-Hasselbalch | no | filtered valid rows | `0.3976` | `-0.3660` | Ratio chemistry alone is biased high. |
| Equilibrium charge balance | no | filtered valid rows | `0.3982` | `-0.3668` | Ideal equilibrium detail does not fix the lab mismatch. |
| Static calibrated equilibrium | yes | held-out test trials | `0.0975` | `-0.0805` | Effective calibration is necessary and useful. |
| Lag calibrated equilibrium | yes | held-out test trials | `0.0975` | `-0.0805` | No sample-lag improvement is identifiable. |
| First-order dynamic combined | yes | held-out test trials | `0.0975` | `-0.0805` | First-order dynamics add no measurable improvement at this sampling rate. |

The flat-trial filter changed the interpretation in a good way. It removed misleading segments from fitting, improved the static calibration, and made the comparison more honest. However, it did not rescue the raw first-principles models. Both direct chemistry models still miss `PH_2` by about `0.40 pH` RMSE.

## What We Know Now

1. `PH_2` is not directly equal to ideal buffer pH from acid/acetate flow ratio.

2. The equilibrium charge-balance model is scientifically better than Henderson-Hasselbalch, but for this dataset it produces almost the same pH coordinate and almost the same error.

3. Low-information flat-pH trials existed in the dataset. They are now excluded from model metrics by default, while remaining visible in the exported audit data.

4. The measured pH is compressed relative to ideal chemistry. The latest fitted dynamic-workflow slope is `0.7909`, and the all-row affine diagnostics are about `0.792` to `0.794`.

5. Static calibration is currently the biggest improvement. It reduces held-out test RMSE by about `77.9%` relative to the raw equilibrium test baseline.

6. Delay and first-order sensor or mixing dynamics are not identifiable from this CSV. The data may contain real dynamics, but the sampling interval and excitation are not enough to estimate them reliably.

7. The current best model is an empirical calibrated chemistry predictor. It should be used for analysis, not yet as a trusted dynamic simulator.

## Recommended Next Steps

The next safe modeling work should not jump to control. It should improve the first-principles model and collect data that can separate chemistry, transport, mixing, and measurement effects.

Recommended next actions:

- Run the four improvement workflows already added for effective static chemistry, settled-sample calibration, residual diagnostics, and activity/dilution correction after the same flat-trial preprocessing.

- Compare whether empirical water-fraction, total-flow, or total-buffer concentration terms reduce held-out residuals without overfitting.

- Design an open-loop identification experiment with step changes in acid/acetate ratio at fixed total flow.

- Add separate step changes in total flow at fixed acid/acetate ratio to identify residence-time and dilution effects.

- Hold each step long enough for `PH_2` to visibly settle, then use those settled windows for static chemistry calibration.

- Record hardware metadata: mixing point, tubing inner diameter and length to `PH_2`, static mixer or flow-cell volume, pH probe location, and probe response time.

With hardware metadata, a future model can separately test transport delay:

$$
\theta(t) \approx \frac{V_{tube}}{F_T(t)}
$$

mixing residence time:

$$
\tau_{mix}(t) \approx \frac{V_{mix}}{F_T(t)}
$$

and sensor response:

$$
\tau_s\frac{dy}{dt} =
pH_{chem}(t-\theta) - y(t)
$$

Until that experiment is available, the most defensible model statement is:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

with remaining residuals that still require better experimental excitation and hardware timing information.

## Artifact Index

Henderson-Hasselbalch artifacts:

- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/preprocessed_lab_data.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/overall_metrics.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/affine_diagnostic.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/lag_scan.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_021555/figures/`

Equilibrium charge-balance artifacts:

- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/preprocessed_lab_data.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/overall_metrics.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/affine_diagnostic.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/lag_scan.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/figures/`

Dynamic identification artifacts:

- `results/dynamic_model_identification_20260522_021628/tables/preprocessed_lab_data.csv`
- `results/dynamic_model_identification_20260522_021628/tables/dynamic_model_comparison.csv`
- `results/dynamic_model_identification_20260522_021628/tables/model_metrics_train_test.csv`
- `results/dynamic_model_identification_20260522_021628/tables/static_calibration_parameters.csv`
- `results/dynamic_model_identification_20260522_021628/tables/lag_search_metrics.csv`
- `results/dynamic_model_identification_20260522_021628/tables/dynamic_parameters.csv`
- `results/dynamic_model_identification_20260522_021628/tables/trial_split_summary.csv`
- `results/dynamic_model_identification_20260522_021628/figures/`
