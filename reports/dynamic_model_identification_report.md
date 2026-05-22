# pH Model Development Story And Flat-Trial Patch

This report documents the first-principles pH modeling sequence for the inline acetate-buffer system. The objective is to predict the reliable measured output, `PH_2`, from the three inlet flowrates:

- acetic acid, 100 mM,
- sodium acetate, 100 mM,
- Arium ultrapure water.

This report only covers three model families:

- ideal Henderson-Hasselbalch,
- equilibrium charge balance,
- dynamic identification built around equilibrium pH.

It does not evaluate controller targets, MPC, RL, rewards, or `PH_1`. The target pH is excluded from all model-validation metrics. `PH_1` is excluded because the operator stated it was not connected during operation.

## Data Mapping

The source file is:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset.csv
```

The fixed mapping is:

| Quantity | CSV column |
| --- | --- |
| measured pH | `observation.biosmb-sensors.PH_2` |
| acetic acid flow | `observation.biosmb-flows[0]` |
| sodium acetate flow | `observation.biosmb-flows[1]` |
| Arium water flow | `observation.biosmb-flows[2]` |

Rows are sorted chronologically. Rows with nonpositive acid, acetate, or water flow are excluded from model metrics.

## Original Modeling Round Before Flat-Trial Filtering

The first full report used these artifacts:

| Workflow | Result folder |
| --- | --- |
| Henderson-Hasselbalch | `results/henderson_hasselbalch_lab_validation_20260522_003559/` |
| Equilibrium charge balance | `results/equilibrium_charge_balance_lab_validation_20260522_005207/` |
| Dynamic identification | `results/dynamic_model_identification_20260522_013357/` |

At this stage, only the one row with invalid flow was excluded. The suspicious flat-pH trials were still included in model fitting and metrics.

## Model 1: Ideal Henderson-Hasselbalch

### Model Equation

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

Water affects dilution and residence time, but it does not change the ideal Henderson-Hasselbalch pH when both stock concentrations are equal.

### Original Result

| Metric | Value |
| --- | ---: |
| valid rows | `1085` |
| mean error, `PH_2 - pH_HH` | `-0.3519 pH` |
| MAE | `0.3690 pH` |
| RMSE | `0.4037 pH` |
| max absolute error | `1.1514 pH` |
| correlation | `0.8346` |

The affine diagnostic was:

$$
PH_2 \approx 1.0139 + 0.7148\,pH_{HH}
$$

The ideal model captured a broad trend but failed as a direct simulator. It overpredicted `PH_2` and the measured pH range was compressed relative to ideal chemistry.

![Original Henderson-Hasselbalch time response](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_vs_hh_prediction_time.png)

## Model 2: Equilibrium Charge Balance

### Model Equation

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

With \(K_a = 10^{-pK_a}\), acetate equilibrium gives:

$$
[A^-] =
\frac{C_TK_a}{K_a + H^+}
$$

and water gives:

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

### Original Result

| Metric | Value |
| --- | ---: |
| valid rows | `1085` |
| mean error, `PH_2 - pH_eq` | `-0.3527 pH` |
| MAE | `0.3696 pH` |
| RMSE | `0.4042 pH` |
| max absolute error | `1.1517 pH` |
| correlation | `0.8346` |

The affine diagnostic was:

$$
PH_2 \approx 1.0059 + 0.7164\,pH_{eq}
$$

This model also failed as a direct simulator. The extra equilibrium detail did not reduce the error relative to Henderson-Hasselbalch.

![Original equilibrium time response](../results/equilibrium_charge_balance_lab_validation_20260522_005207/figures/measured_vs_equilibrium_prediction_time.png)

## Model 3: Dynamic Identification From Equilibrium pH

### Model Sequence

The dynamic workflow tested three stages after the raw equilibrium baseline.

The baseline was:

$$
\hat y_k = pH_{eq,k}
$$

The static calibration was:

$$
\hat y_k = b_0 + b_1pH_{eq,k}
$$

The parameters were estimated on train trials only using ordinary least squares:

$$
(b_0^{*}, b_1^{*}) =
\underset{b_0,b_1}{\mathrm{arg\,min}}
\sum_{k \in D_{train}}
\left(y_k - b_0 - b_1pH_{eq,k}\right)^2
$$

The lag model was:

$$
\hat y_k(d) =
b_0(d) + b_1(d)pH_{eq,k-d}
$$

The first-order wrapper was:

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

The time constant was estimated by scalar nonlinear optimization:

$$
\tau^{*} =
\underset{\tau > 0}{\mathrm{arg\,min}}
\sqrt{
\frac{1}{N_{train}}
\sum_{k \in D_{train}}
\left(y_k - \hat y_k(\tau)\right)^2
}
$$

### Original Result

Original fitted static calibration:

$$
PH_2 \approx 1.1404 + 0.6928\,pH_{eq}
$$

Original dynamic parameters:

| Parameter | Value |
| --- | ---: |
| best lag | `0` samples |
| fitted \(\tau\) | `1.7033 s` |
| median sample interval | `69.9825 s` |
| approximate effective volume | `0.4641 mL` |

Original train/test metrics:

| Model stage | Split | N | Mean error | MAE | RMSE |
| --- | --- | ---: | ---: | ---: | ---: |
| Equilibrium baseline | train | `826` | `-0.3274` | `0.3495` | `0.3918` |
| Equilibrium baseline | test | `259` | `-0.4337` | `0.4337` | `0.4412` |
| Static calibrated | train | `826` | `0.0000` | `0.1443` | `0.1848` |
| Static calibrated | test | `259` | `-0.0903` | `0.0923` | `0.1148` |
| Lag calibrated | test | `259` | `-0.0903` | `0.0923` | `0.1148` |
| First-order dynamic | test | `259` | `-0.0903` | `0.0923` | `0.1148` |

The original conclusion was that static calibration helped, but integer lag and first-order dynamics did not add useful predictive power.

![Original dynamic time response](../results/dynamic_model_identification_20260522_013357/figures/measured_vs_dynamic_prediction_time.png)

## Patch: Flat-Trial Removal And Rerun

After reviewing the time plots, a suspicious region was identified around sample indices `205-290`. These are trials `8`, `9`, and `10`.

The pH behavior in this region is not physically informative for a flow-to-pH model:

| Region | Trials | Rows | Model-valid rows after patch | `PH_2` range | \(\log_{10}(F_A/F_H)\) range |
| --- | --- | ---: | ---: | ---: | ---: |
| before suspicious region | `0-7` | `205` | `205` | `3.9301-5.2186` | `-0.8589` to `0.7757` |
| suspicious flat region | `8-10` | `86` | `0` | `4.5718-4.6248` | `-0.8657` to `0.7988` |
| after suspicious region | `11-84` | `795` | `785` | `3.5717-5.0708` | `-0.9387` to `0.9417` |

The suspicious region has almost constant `PH_2`, only about `0.053 pH` range, while the acid/base ratio sweeps over about `1.66` log units. A normal ideal buffer model would expect a large pH movement from that ratio change. This is why the region was treated as low-information or inconsistent with the logged inlet-flow-to-pH relationship.

The filter rule is:

$$
\Delta PH_2 \le 0.05
\quad\text{and}\quad
\Delta \log_{10}(F_A/F_H) \ge 0.5
\quad\text{and}\quad
n \ge 5
$$

The patch flags these trials and sets `valid_for_model = False`. The raw rows are still kept in `preprocessed_lab_data.csv` for audit. They are not used for fitted parameters, metrics, or cleaned model-validation traces.

The updated rerun artifacts are:

| Workflow | Result folder |
| --- | --- |
| Henderson-Hasselbalch | `results/henderson_hasselbalch_lab_validation_20260522_022832/` |
| Equilibrium charge balance | `results/equilibrium_charge_balance_lab_validation_20260522_022832/` |
| Dynamic identification | `results/dynamic_model_identification_20260522_022832/` |

### Updated Henderson-Hasselbalch Result

| Metric | Value |
| --- | ---: |
| valid rows | `990` |
| excluded rows | `96` |
| mean error, `PH_2 - pH_HH` | `-0.3660 pH` |
| MAE | `0.3689 pH` |
| RMSE | `0.3976 pH` |
| max absolute error | `0.8451 pH` |
| correlation | `0.9012` |

Updated affine diagnostic:

$$
PH_2 \approx 0.6308 + 0.7921\,pH_{HH}
$$

![Filtered Henderson-Hasselbalch time response](../results/henderson_hasselbalch_lab_validation_20260522_022832/figures/measured_vs_hh_prediction_time.png)

### Updated Equilibrium Charge-Balance Result

| Metric | Value |
| --- | ---: |
| valid rows | `990` |
| excluded rows | `96` |
| mean error, `PH_2 - pH_eq` | `-0.3668 pH` |
| MAE | `0.3697 pH` |
| RMSE | `0.3982 pH` |
| max absolute error | `0.8453 pH` |
| correlation | `0.9011` |

Updated affine diagnostic:

$$
PH_2 \approx 0.6221 + 0.7937\,pH_{eq}
$$

![Filtered equilibrium time response](../results/equilibrium_charge_balance_lab_validation_20260522_022832/figures/measured_vs_equilibrium_prediction_time.png)

### Updated Dynamic Identification Result

Updated fitted static calibration:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

Updated dynamic parameters:

| Parameter | Value |
| --- | ---: |
| train samples | `731` |
| test samples | `259` |
| best lag | `0` samples |
| fitted \(\tau\) | `1.8741 s` |
| median sample interval | `69.7710 s` |
| approximate effective volume | `0.5110 mL` |

Updated train/test metrics:

| Model stage | Split | N | Mean error | MAE | RMSE |
| --- | --- | ---: | ---: | ---: | ---: |
| Equilibrium baseline | train | `731` | `-0.3430` | `0.3470` | `0.3819` |
| Equilibrium baseline | test | `259` | `-0.4337` | `0.4337` | `0.4412` |
| Static calibrated | train | `731` | `0.0000` | `0.1223` | `0.1500` |
| Static calibrated | test | `259` | `-0.0805` | `0.0822` | `0.0975` |
| Lag calibrated | test | `259` | `-0.0805` | `0.0822` | `0.0975` |
| First-order dynamic | test | `259` | `-0.0805` | `0.0822` | `0.0975` |

The flat-trial patch improved the calibrated held-out test RMSE from `0.1148 pH` to `0.0975 pH`. The improvement came from cleaner static calibration, not from delay or first-order dynamics.

![Filtered dynamic time response](../results/dynamic_model_identification_20260522_022832/figures/measured_vs_dynamic_prediction_time.png)

![Filtered dynamic train/test comparison](../results/dynamic_model_identification_20260522_022832/figures/train_test_metric_comparison.png)

## Why Performance Changes Before Index 200 And After Index 300

The performance difference is a real diagnostic clue, not only a plotting artifact.

Before index `205`, the raw equilibrium model is much closer to `PH_2`:

| Region | Raw equilibrium RMSE | Dynamic calibrated RMSE |
| --- | ---: | ---: |
| indices `0-204` | `0.1781 pH` | `0.2333 pH` |
| indices `291-end` | `0.4379 pH` | `0.0993 pH` |

This means the early part of the dataset and the later part of the dataset behave like different regimes.

The most likely explanation is nonstationarity in the lab setup. Around indices `205-290`, `PH_2` becomes almost flat even while the commanded acid/base ratio changes strongly. After index `290`, there is a long session break and the measured pH response becomes much more active again, but shifted relative to ideal chemistry. Possible causes include:

- the pH probe or flow cell not seeing the newly commanded mixture during the flat region,
- a logging synchronization problem between flow commands and pH measurement,
- a large unmodeled dead volume or flushing delay during that part of operation,
- a temporary mixing or routing abnormality,
- probe conditioning, calibration drift, or startup effects between sessions.

The raw equilibrium model works better before index `205` because that early segment has a smaller offset from ideal chemistry. The calibrated dynamic model works better after index `291` because the fitted calibration maps the ideal pH coordinate to the lower, compressed pH response that dominates the later data. This is evidence that one global steady-state first-principles model is not enough unless we also model session effects, measurement calibration, and experiment timing.

## Final Comparison After The Patch

| Model | Fitted? | Validation basis | RMSE | Mean error | Conclusion |
| --- | --- | --- | ---: | ---: | --- |
| Ideal Henderson-Hasselbalch | no | filtered valid rows | `0.3976` | `-0.3660` | Still fails as direct plant model. |
| Equilibrium charge balance | no | filtered valid rows | `0.3982` | `-0.3668` | Still fails as direct plant model. |
| Static calibrated equilibrium | yes | held-out test trials | `0.0975` | `-0.0805` | Best current empirical predictor. |
| Lag calibrated equilibrium | yes | held-out test trials | `0.0975` | `-0.0805` | No delay improvement is identifiable. |
| First-order dynamic | yes | held-out test trials | `0.0975` | `-0.0805` | No first-order dynamic improvement is identifiable at this sample rate. |

The safest current statement is:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

with the warning that this is an empirical calibration for this CSV, not a validated dynamic simulator.

## Next Modeling Step

The next step should stay inside first-principles model improvement. The most useful experiment is a designed open-loop dataset with:

- step changes in acid/acetate ratio at fixed total flow,
- step changes in total flow at fixed acid/acetate ratio,
- long holds until `PH_2` visibly settles,
- recorded mixing-point location,
- tubing inner diameter and length to `PH_2`,
- flow-cell, static mixer, and dead-volume estimates,
- probe response-time metadata,
- known synchronization between logged flows and logged pH.

With those data, the next model can test physical transport delay:

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

The current CSV is valuable for diagnosing failure modes, but it is not enough to identify those physical dynamic parameters reliably.
