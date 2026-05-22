# Supervisor Summary: pH First-Principles Modeling And Lab Data Diagnostics

## Short Message

We analyzed the lab CSV from the inline acetate-buffer setup to determine whether the measured outlet pH can be predicted from the three inlet flows. The reliable output is `PH_2`; `PH_1` was not used because the operator stated it was not connected. We tested a sequence of increasingly realistic models:

1. ideal Henderson-Hasselbalch chemistry,
2. equilibrium charge-balance chemistry,
3. static calibration of equilibrium pH to measured `PH_2`,
4. integer-lag and first-order dynamic wrappers,
5. physical transport-delay identification using total flow.

The main conclusion is that the current closed-loop CSV is useful for diagnosing model mismatch, but it is not sufficient to identify a physical dynamic model. The best current predictor is an empirical static calibration of equilibrium pH:

$$
PH_2 \approx 0.6567 + 0.7909pH_{eq}
$$

This is a useful empirical mapping for this dataset, but it should not be treated as a validated first-principles simulator.

## Data Used

Source:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset.csv
```

Lab mapping:

| Quantity | CSV column | Use |
| --- | --- | --- |
| measured pH | `observation.biosmb-sensors.PH_2` | only measured output |
| acetic acid flow | `observation.biosmb-flows[0]` | model input |
| sodium acetate flow | `observation.biosmb-flows[1]` | model input |
| water flow | `observation.biosmb-flows[2]` | model input through dilution and total flow |
| `PH_1` | `observation.biosmb-sensors.PH_1` | not used |
| `target_ph` | `target_ph` | not used for plant-model metrics |

The raw CSV has `1086` rows. After filtering invalid or low-information rows, the main steady-state model comparisons used `990` rows.

## Data Diagnostics Before Modeling

Two important issues were found before trusting model results.

First, the sampling time is not consistent across the dataset:

| Region | Samples or sessions | Median sampling time | Interpretation |
| --- | --- | ---: | --- |
| early/two-minute regime | sessions `0-3` | about `140-142 s` | slower logging |
| later/one-minute regime | sessions `4-6` | about `69-70 s` | faster logging |
| full dataset | all sessions | about `70 s`, but mixed | not globally uniform |

Second, there is a suspicious flat or dead regime around sample indices `205-290`. During this interval, `PH_2` stays almost constant while the acid/base ratio changes strongly:

| Region | Rows | `PH_2` behavior | Acid/base-ratio behavior | Decision |
| --- | ---: | --- | --- | --- |
| before index `205` | `205` | active pH changes | active ratio changes | keep |
| indices `205-290` | `86` | nearly flat, about `4.57-4.62` | large ratio sweep | exclude from model metrics |
| after index `291` | `795` | active pH changes again | active ratio changes | keep |

We do not yet know the physical cause of the dead regime. Possible explanations are a routing or mixing abnormality, pH probe or flow-cell not seeing the commanded mixture, logging synchronization issues, a flushing/dead-volume event, or probe conditioning/calibration effects.

## Step 1: Ideal Henderson-Hasselbalch Model

The first model assumed ideal acetate-buffer behavior:

$$
pH_{HH}
=
pK_a
+
\log_{10}\left(\frac{F_A}{F_H}\right)
$$

Because both acid and acetate stocks are `100 mM`, water dilution cancels out of the ideal acid/base ratio. Water can still matter dynamically through residence time, but not in this ideal static pH equation.

Result after filtering:

| Metric | Value |
| --- | ---: |
| rows used | `990` |
| mean error, `PH_2 - pH_HH` | `-0.3660 pH` |
| RMSE | `0.3976 pH` |
| max absolute error | `0.8451 pH` |
| correlation | `0.9012` |

Interpretation: the ideal model captures trend, but it overpredicts pH and is not accurate enough as a plant simulator.

Diagnostic calibration:

$$
PH_2 \approx 0.6308 + 0.7921pH_{HH}
$$

The slope below `1` means the measured pH response is compressed relative to ideal chemistry.

## Step 2: Equilibrium Charge-Balance Model

The next model used analytical concentrations after mixing:

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

Then it solved the charge-balance equation:

$$
H^+ + C_{Na}
-
\frac{C_TK_a}{K_a + H^+}
-
\frac{K_w}{H^+}
=
0
$$

and computed:

$$
pH_{eq} = -\log_{10}(H^+)
$$

Result after filtering:

| Metric | Value |
| --- | ---: |
| rows used | `990` |
| mean error, `PH_2 - pH_eq` | `-0.3668 pH` |
| RMSE | `0.3982 pH` |
| max absolute error | `0.8453 pH` |
| correlation | `0.9011` |

Interpretation: the equilibrium charge-balance model did not improve over Henderson-Hasselbalch. The dominant mismatch is not solved by adding this static equilibrium chemistry.

## Step 3: Static Calibration Of Equilibrium pH

Since the raw equilibrium prediction had a strong systematic bias, we fit a simple affine map on train trials:

$$
PH_2 =
b_0 + b_1pH_{eq} + \epsilon
$$

The fitted result was:

$$
PH_2 \approx 0.6567 + 0.7909pH_{eq}
$$

Train/test results:

| Model | Train RMSE | Test RMSE | Test mean error |
| --- | ---: | ---: | ---: |
| raw equilibrium | `0.3819` | `0.4412` | `-0.4337` |
| static calibrated equilibrium | `0.1500` | `0.0975` | `-0.0805` |

Interpretation: calibration greatly improves prediction. However, this is an empirical correction, not a new first-principles model. The slope `0.7909` again shows compression of measured pH relative to equilibrium chemistry.

## Step 4: Lag And First-Order Dynamics

We tested whether dynamics improve the static calibrated model.

Integer-lag model:

$$
\hat y_k(d) =
b_0(d) + b_1(d)pH_{eq,k-d}
$$

First-order wrapper:

$$
\hat y_k =
\alpha_k\hat y_{k-1}
+
(1-\alpha_k)x_k
$$

$$
\alpha_k =
\exp\left(-\frac{\Delta t_k}{\tau}\right)
$$

Results:

| Model | Best parameter | Test RMSE | Interpretation |
| --- | --- | ---: | --- |
| static calibrated | none | `0.0975` | best simple predictor |
| integer lag | `0` samples | `0.0975` | no lag improvement |
| first-order dynamic | \(\tau = 1.8741 s\) | `0.0975` | time constant far below sampling interval |

Interpretation: the dynamic wrapper collapses to the static calibrated model because the sampling time is about `69-142 s`, much slower than the fitted time constant.

## Step 5: Physical Transport Delay Using Total Flow

We then tested a more physical delay hypothesis:

$$
\theta(t) \approx \frac{V_{tube}}{F_T(t)}
$$

In seconds:

$$
\theta_s(t) =
60\frac{V_{tube}}{F_T(t)}
$$

This is where water flow enters the dynamic model:

$$
F_T = F_H + F_A + F_W
$$

Water may not strongly change ideal pH through the acid/base ratio, but it changes total flow, and therefore residence time and transport delay.

The implemented method used a cumulative transported-volume coordinate:

$$
Q_k =
Q_{k-1}
+
\frac{F_{T,k-1}\Delta t_k}{60}
$$

For each candidate \(V_{tube}\):

$$
Q_{delay,k} = Q_k - V_{tube}
$$

The delayed equilibrium pH was interpolated at \(Q_{delay,k}\), and then an affine calibration was fit on train trials only.

Full-data result:

| Quantity | Value |
| --- | ---: |
| best \(V_{tube}\) | `0.000 mL` |
| median \(\theta_s\) | `0.000 s` |
| static test RMSE | `0.0975` |
| transport-delay test RMSE | `0.0975` |
| identifiability | `weak_non_identifiable_near_zero_volume` |

Interpretation: with the full dataset, a nonzero transport delay is not identifiable.

## Regime-Specific Transport-Delay Tests

Because the dataset has two sampling regimes, we repeated the transport-delay test separately.

| Regime | Sessions | Median sampling | Best \(V_{tube}\) | Median \(\theta_s\) | Static test RMSE | Transport test RMSE | Conclusion |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| two-minute | `0-3` | `141.37 s` | `1.012 mL` | `3.71 s` | `0.2914` | `0.2904` | tiny gain, not reliable |
| one-minute | `4-6` | `69.36 s` | `0.467 mL` | `1.72 s` | `0.0513` | `0.0513` | no held-out improvement |

The apparent delays are much shorter than the logging interval. Therefore they should not be interpreted as tubing geometry. They are best understood as weak empirical artifacts of fitting closed-loop data.

## Key Interpretation For Discussion

The data appear dynamic, but not in a way that lets us identify physical dynamics reliably from this CSV alone. The major findings are:

- The ideal and equilibrium first-principles static models both fail as direct simulators, with RMSE about `0.40 pH`.
- A simple empirical calibration of equilibrium pH reduces held-out RMSE to about `0.10 pH` overall and about `0.05 pH` in the one-minute regime.
- The dead regime around indices `205-290` is not physically informative because `PH_2` is nearly flat while inputs move strongly.
- The one-minute regime is much cleaner than the two-minute regime.
- The two-minute regime is more nonstationary, likely because it crosses the suspicious flat/dead behavior and session changes.
- Physical transport delay was tested using total flow, including water flow, but no trustworthy nonzero \(V_{tube}\) was identified.

## What This Means

The current best model for this dataset is:

$$
PH_2 \approx 0.6567 + 0.7909pH_{eq}
$$

This is useful for describing the current data, but it is not enough for a high-confidence simulator or controller design. It tells us that measured pH is biased and compressed relative to first-principles equilibrium chemistry.

The current data are closed-loop/controller-generated, with changing sample intervals and unknown lab disturbances. This makes it hard to separate chemistry, transport delay, mixing volume, sensor response, and controller feedback.

## Recommended Next Experiment

The next safest step is not RL or MPC yet. We should collect a designed open-loop identification dataset:

1. Use only `PH_2` and confirm sensor calibration before the run.
2. Log faster than the expected delay, ideally every `1-5 s` if possible.
3. Run acid/acetate ratio steps at fixed total flow.
4. Run total-flow steps at fixed acid/acetate ratio.
5. Hold each condition until pH clearly settles.
6. Record where the streams first mix.
7. Record tubing inner diameter and length from mixer to `PH_2`.
8. Record static mixer, flow-cell, and pH-probe dead volumes.
9. Record pH probe/transmitter response time.
10. Confirm whether logged flows are synchronized before or after pH measurement.

With that dataset, we can separately identify:

$$
\theta(t) \approx \frac{V_{tube}}{F_T(t)}
$$

$$
\tau_{mix}(t) \approx \frac{V_{mix}}{F_T(t)}
$$

and:

$$
\tau_s\frac{dy}{dt}
=
pH_{chem}(t-\theta) - y(t)
$$

That would give us a real first-principles-plus-dynamics model rather than only an empirical calibration.

## Key Artifacts

Main detailed report:

```text
reports/dynamic_model_identification_report.md
```

Important result folders:

```text
results/henderson_hasselbalch_lab_validation_20260522_022832/
results/equilibrium_charge_balance_lab_validation_20260522_022832/
results/dynamic_model_identification_20260522_133621/
results/transport_delay_identification_20260522_134840/
results/first_regime_transport_delay_identification_20260522_140759/
results/second_regime_transport_delay_identification_20260522_140308/
```

Useful figures for a meeting:

![Measured pH and inlet behavior](../results/dynamic_model_identification_20260522_133621/figures/measurement_input_output_behavior.png)

![Regime input distributions](../results/dynamic_model_identification_20260522_133621/figures/regime_input_distributions.png)

![Dynamic prediction comparison](../results/dynamic_model_identification_20260522_133621/figures/measured_vs_dynamic_prediction_time.png)

![Transport delay search](../results/transport_delay_identification_20260522_134840/figures/transport_delay_rmse_search.png)

![Two-minute regime delay search](../results/first_regime_transport_delay_identification_20260522_140759/figures/transport_delay_rmse_search.png)

![One-minute regime delay search](../results/second_regime_transport_delay_identification_20260522_140308/figures/transport_delay_rmse_search.png)
