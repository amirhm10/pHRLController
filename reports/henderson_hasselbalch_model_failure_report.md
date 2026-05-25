# Steady-State pH Model Failure And Comparison Report

Generated: 2026-05-22

Source data:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset.csv
```

Validation runs:

```text
results/henderson_hasselbalch_lab_validation_20260522_003559
results/equilibrium_charge_balance_lab_validation_20260522_005026
```

## Executive Summary

Two steady-state first-principles models were tested against the lab `PH_2` measurement:

- Ideal Henderson-Hasselbalch model.
- Equilibrium charge-balance model.

Both models fail as simulation models for the current lab process. They are useful chemistry baselines, but neither one can reproduce the measured outlet pH accurately enough to simulate the real setup.

The key result is that the charge-balance model does not materially improve the Henderson-Hasselbalch model. Its RMSE is `0.4042 pH`, compared with `0.4037 pH` for Henderson-Hasselbalch. The two model predictions are almost identical in this operating range, with mean absolute difference only `0.00079 pH` and maximum difference only `0.01198 pH`.

This means the dominant missing behavior is not equilibrium chemistry. The dominant missing behavior is likely effective calibration, pH probe response, mixing volume, tubing delay, residence-time distribution, and synchronization between logged flows and measured pH.

## Objective

The objective is to decide whether a steady-state first-principles pH model can be used as the simulation model for the lab process.

The model input is:

$$
u_k =
\begin{bmatrix}
F_H(k) \\
F_A(k) \\
F_W(k)
\end{bmatrix}
$$

where:

- $F_H$ is acetic-acid flow from `observation.biosmb-flows[0]`.
- $F_A$ is sodium-acetate flow from `observation.biosmb-flows[1]`.
- $F_W$ is Arium-water flow from `observation.biosmb-flows[2]`.

The measured output is:

$$
y_k = \mathrm{PH2}_k
$$

Only `PH_2` is used. `PH_1` is not used because the operator stated that it was disconnected during operation. Target pH is also not used in this report, because the modeling question is only whether inlet flows predict measured pH.

## Data Used

| Item | Value |
|---|---:|
| Total rows | 1086 |
| Valid rows used for metrics | 1085 |
| Rows excluded from metrics | 1 |
| Measured `PH_2` range | 3.572 to 5.219 |
| Total inlet flow range | 3.000 to 28.736 mL/min |
| Acid/acetate stock concentrations | 100 mM each |
| Nominal pKa | 4.76 |
| Reliable pH sensor | `PH_2` only |

The one excluded row has at least one nonpositive inlet flow and is therefore not physically valid for either steady-state model.

## Method 1: Henderson-Hasselbalch Model

The first model is the ideal Henderson-Hasselbalch relation for an acetic acid and sodium acetate buffer:

$$
\mathrm{pH}_{HH}
= pK_a + \log_{10}
\left(
\frac{C_A^0 F_A}{C_H^0 F_H}
\right)
$$

Since the acid and acetate stock concentrations are both `100 mM`, this reduces to:

$$
\mathrm{pH}_{HH}
= pK_a + \log_{10}
\left(
\frac{F_A}{F_H}
\right)
$$

### Step-By-Step Calculation

1. Read acid, acetate, and water flows from the lab CSV.
2. Exclude rows where any inlet flow is nonpositive.
3. Compute the molar acetate-to-acid inlet ratio.
4. Predict pH from the Henderson-Hasselbalch equation.
5. Compare the prediction with measured `PH_2`.
6. Save residuals, overall metrics, trial metrics, lag scan, and figures.

### Henderson-Hasselbalch Results

| Metric | Value |
|---|---:|
| Mean error, `PH_2 - pH_HH` | -0.3519 pH |
| Standard deviation of error | 0.1977 pH |
| Mean absolute error | 0.3690 pH |
| RMSE | 0.4037 pH |
| Maximum absolute error | 1.1514 pH |
| Correlation, `PH_2` vs `pH_HH` | 0.8346 |
| Affine diagnostic RMSE | 0.1692 pH |

The high correlation shows that the acid/base ratio contains real information about pH. The large negative mean error shows that the ideal model is biased high relative to the measured sensor.

### Henderson-Hasselbalch Visual Evidence

![HH measured versus prediction over time](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_vs_hh_prediction_time.png)

The ideal prediction follows some broad movements in `PH_2`, but it is consistently too high.

![HH measured versus predicted scatter](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_vs_hh_prediction_scatter.png)

The samples do not lie on the identity line. The real measured pH is biased and compressed relative to the ideal model.

![HH residual over time](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_minus_hh_time.png)

The residual is mostly negative, so this is not just random noise.

![HH residual histogram](../results/henderson_hasselbalch_lab_validation_20260522_003559/figures/measured_minus_hh_histogram.png)

The residual distribution is shifted below zero.

## Method 2: Equilibrium Charge-Balance Model

The second model solves the acetate equilibrium more explicitly. It includes dilution, weak-acid equilibrium, sodium ion, water self-ionization, and electroneutrality.

### Step 1: Mixed Analytical Concentrations

The total inlet flow is:

$$
F_T = F_H + F_A + F_W
$$

The mixed analytical concentrations are:

$$
C_H = C_H^0 \frac{F_H}{F_T}
$$

$$
C_A = C_A^0 \frac{F_A}{F_T}
$$

The total acetate-family concentration is:

$$
C_T = C_H + C_A
$$

The sodium concentration is:

$$
C_{Na} = C_A
$$

### Step 2: Equilibrium Speciation

For acetic acid:

$$
HA \rightleftharpoons H^+ + A^-
$$

$$
K_a = 10^{-pK_a}
$$

Let:

$$
H = [H^+]
$$

Then:

$$
[A^-](H) = C_T \frac{K_a}{K_a + H}
$$

Water self-ionization gives:

$$
[OH^-](H) = \frac{K_w}{H}
$$

### Step 3: Charge Balance

At equilibrium, positive charge equals negative charge:

$$
H + C_{Na} =
C_T \frac{K_a}{K_a + H}
+ \frac{K_w}{H}
$$

The scalar equation solved numerically is:

$$
f(H)
=
H + C_{Na}
- C_T \frac{K_a}{K_a + H}
- \frac{K_w}{H}
= 0
$$

After solving for $H$:

$$
\mathrm{pH}_{eq} = -\log_{10}(H)
$$

### Step-By-Step Calculation

1. Read acid, acetate, and water flows from the same lab CSV.
2. Exclude rows where any inlet flow is nonpositive.
3. Compute mixed acid, acetate, total buffer, and sodium concentrations.
4. Solve the charge-balance equation for hydrogen concentration.
5. Convert hydrogen concentration to pH.
6. Compare predicted pH with measured `PH_2`.
7. Save residuals, overall metrics, trial metrics, lag scan, and figures.

### Equilibrium Charge-Balance Results

| Metric | Value |
|---|---:|
| Mean error, `PH_2 - pH_eq` | -0.3527 pH |
| Standard deviation of error | 0.1974 pH |
| Mean absolute error | 0.3696 pH |
| RMSE | 0.4042 pH |
| Maximum absolute error | 1.1517 pH |
| Correlation, `PH_2` vs `pH_eq` | 0.8346 |
| Affine diagnostic RMSE | 0.1692 pH |

The charge-balance model still overpredicts the measured pH by about `0.353 pH` on average. It therefore does not fix the main model-data mismatch.

### Equilibrium Visual Evidence

![Equilibrium measured versus prediction over time](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/measured_vs_equilibrium_prediction_time.png)

The equilibrium prediction is still systematically above the measured `PH_2`.

![Equilibrium measured versus predicted scatter](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/measured_vs_equilibrium_prediction_scatter.png)

The scatter remains shifted away from the identity line.

![Equilibrium residual over time](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/measured_minus_equilibrium_time.png)

The residual is again mostly negative, matching the Henderson-Hasselbalch failure pattern.

![Equilibrium residual histogram](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/measured_minus_equilibrium_histogram.png)

The residual histogram is centered below zero.

![Total buffer concentration trajectory](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/total_buffer_concentration_trajectory.png)

The charge-balance model uses dilution and total buffer concentration, but this added information does not remove the main prediction error.

![Residual versus total buffer concentration](../results/equilibrium_charge_balance_lab_validation_20260522_005026/figures/residual_vs_total_buffer.png)

The residual remains biased across the observed buffer-concentration range.

## Direct Model Comparison

| Quantity | Henderson-Hasselbalch | Equilibrium charge balance | Difference, equilibrium minus HH |
|---|---:|---:|---:|
| Mean error | -0.3519 pH | -0.3527 pH | -0.0008 pH |
| Mean absolute error | 0.3690 pH | 0.3696 pH | +0.0006 pH |
| RMSE | 0.4037 pH | 0.4042 pH | +0.0005 pH |
| Maximum absolute error | 1.1514 pH | 1.1517 pH | +0.0003 pH |
| Correlation with `PH_2` | 0.8346 | 0.8346 | -0.0000 |
| Affine diagnostic RMSE | 0.1692 pH | 0.1692 pH | +0.0000 pH |

The two prediction signals are nearly identical:

| Model-to-model comparison | Value |
|---|---:|
| Mean `pH_eq - pH_HH` | 0.00079 pH |
| Mean absolute `pH_eq - pH_HH` | 0.00079 pH |
| RMSE of `pH_eq - pH_HH` | 0.00137 pH |
| Maximum absolute `pH_eq - pH_HH` | 0.01198 pH |
| Correlation between model predictions | 0.999998 |

### Interpretation Of The Comparison

The equilibrium model is chemically more complete, but in this dataset it changes the predicted pH by almost nothing. That is expected because the buffer is not extremely dilute and the acid/base stocks have equal nominal concentration. In this operating range, the Henderson-Hasselbalch approximation and the charge-balance solution collapse to nearly the same prediction.

Therefore, the model failure is not mainly caused by the Henderson-Hasselbalch approximation. Moving from HH to equilibrium chemistry does not solve the lab prediction problem.

## Main Observations

- Both models preserve the same broad acid/base-ratio trend.
- Both models overpredict measured `PH_2` by about `0.35 pH`.
- Both models have RMSE near `0.404 pH`.
- Both models have strong correlation with `PH_2`, around `0.835`, but high correlation is not enough for simulation.
- The affine diagnostic reduces RMSE to about `0.169 pH`, which indicates bias and compression in the measured response.
- Adding dilution, sodium balance, water self-ionization, and electroneutrality does not materially improve prediction.
- The missing behavior is likely outside static equilibrium chemistry.

## Conclusion

Neither steady-state model should be used as the lab simulation model.

Henderson-Hasselbalch is too ideal. Equilibrium charge balance is more chemically detailed, but it gives almost the same answer and almost the same error. The real lab process is not just a static buffer-equilibrium map from inlet flows to pH.

The current evidence says:

$$
\mathrm{static\ chemistry}
\neq
\mathrm{measured\ PH2}
$$

The simulation model needs at least:

$$
\mathrm{flows}
\rightarrow
\mathrm{mixing\ and\ residence\ time}
\rightarrow
\mathrm{static\ chemistry}
\rightarrow
\mathrm{sensor\ dynamics}
\rightarrow
\mathrm{PH2}
$$

## What We Can Do Next

The next safe development step is not control. It is model identification for the physical measurement path.

### 1. Fit Effective Static Chemistry From Settled Samples

Purpose:

- Estimate effective `pKa`.
- Estimate pH bias.
- Check whether the measured pH is linearly compressed relative to equilibrium pH.

Implementation target:

- Add a static calibration workflow that fits:

$$
\mathrm{PH2}
= b_0 + b_1 \mathrm{pH}_{eq}
$$

Decision criterion:

- If settled-sample RMSE becomes much smaller and residuals are centered, static calibration is necessary.
- If residuals remain structured, dynamics dominate.

### 2. Identify Delay And Mixing Volume

Purpose:

- Estimate transport delay from the mixing point to `PH_2`.
- Estimate effective mixed volume or residence-time distribution.

Needed lab metadata:

- Where the three streams first meet.
- Tubing inner diameter and length from mixer to `PH_2`.
- Any static mixer, flow cell, or dead volume.
- pH probe location and response time.
- Whether logged flows are synchronized before or after pH measurement.

Candidate model:

$$
\theta(t) = \frac{V_{tube}}{F_T(t)}
$$

$$
\tau(t) = \frac{V_{mix}}{F_T(t)}
$$

### 3. Add Sensor Dynamics

Purpose:

- Represent the pH probe and transmitter response.

Candidate model:

$$
\tau_s \frac{dy}{dt}
=
\mathrm{pH}_{chem}(t-\theta) - y(t)
$$

where $y(t)$ is the measured `PH_2`.

### 4. Re-Test Against The Same Metrics

The next model should be accepted only if it improves:

- RMSE relative to `0.404 pH`.
- Mean error relative to `-0.352 pH`.
- Residual centering around zero.
- Residual structure over time.
- Prediction during flow-ratio changes.

## Bottom Line

The charge-balance model was the correct next steady-state test, but it did not solve the problem. That is an important result. We can now justify moving beyond static equilibrium chemistry toward a dynamic first-principles model with calibration, delay, mixing volume, and sensor response.
