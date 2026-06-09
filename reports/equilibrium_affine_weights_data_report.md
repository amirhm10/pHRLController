# Weight-Corrected Data And Affine Equilibrium pH Model

![BioSMB pH plumbing map](../results/biosmb_ph_plumbing_map_20260528_021943/figures/biosmb_ph_plumbing_map.png)

## Objective

This report repeats the equilibrium-affine analysis using the new
weight-corrected dataset:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv
```

The dataset was provided after bad measurements were removed and flowrates were
backcalculated from reservoir weights. The sender noted that the last four
columns should now contain the needed information.

Those last four columns are:

| New column | Interpretation used here |
| --- | --- |
| `flow-acid` | weight-backcalculated acetic acid flowrate |
| `flow-sodium` | weight-backcalculated sodium acetate flowrate |
| `flow-water` | weight-backcalculated Arium water flowrate |
| `pH-sensor` | measured pH output, numerically equal to `PH_2` in this file |

The goal is to answer two questions:

1. Does the new dataset make the first-principles equilibrium model behave more
   physically?
2. Does model-validation performance improve relative to the previous
   logged-flow dataset?

This report focuses only on the equilibrium charge-balance model and its
empirical affine correction. It does not add MPC, RL, reward functions,
policies, feedback control, or dynamic model fitting.

## Reproducible Run

The new analysis runner is:

```text
run_equilibrium_weights_data_report.py
```

The generated artifacts are saved in:

```text
results/equilibrium_weights_data_report_20260608_235235/
```

The runner uses the same model code and validation pattern as the previous
equilibrium report, but with a new column map:

| Project variable | New dataset column |
| --- | --- |
| `acid_flow` | `flow-acid` |
| `acetate_flow` | `flow-sodium` |
| `water_flow` | `flow-water` |
| `ph_measured` | `pH-sensor` |

## BioSMB pH Plumbing Reminder

The live BioSMB pH interpretation remains:

| Item | Current interpretation |
| --- | --- |
| Pump 1 | Do not use, reported not working |
| Pump 2 | Acetic acid inlet |
| Pump 3 | Sodium acetate inlet |
| Pump 4 | Arium water inlet |
| `P2` | Valve at column `P`, row 2, aligned with acetic acid row |
| `P3` | Valve at column `P`, row 3, aligned with sodium acetate row |
| `P4` | Valve at column `P`, row 4, aligned with water row |
| `PH_2` | Reliable outlet pH measurement |
| `PH_1` | Diagnostic only, not a validation output |

The historical CSV flow columns and the live pump numbers are different naming
systems. In this report, the main model inputs are the new weight-derived flow
columns, not the old logged pump-flow columns.

## Data Summary

The new CSV has:

| Quantity | Value |
| --- | ---: |
| rows | `962` |
| columns | `47` |
| missing values in last four columns | `0` |
| positive-flow rows | `962` |
| rows flagged by flat-pH trial rule | `0` |
| model-valid rows | `962` |
| train rows | `723` |
| held-out test rows | `239` |

The previous treated dataset had `1086` raw rows and the filtered modeling
workflow used `990` valid rows after removing flat-pH trials. The new file is
therefore smaller and already appears to have removed the obvious bad
measurement region. The flat-pH filter does not remove any additional rows from
the new file.

The new data still contain inferred flows above the nominal `1-10 mL/min` pump
range:

| Check | Rows |
| --- | ---: |
| all three inferred flows inside `1-10 mL/min` | `782` |
| acid above `10 mL/min` | `101` |
| sodium acetate above `10 mL/min` | `15` |
| water above `10 mL/min` | `72` |
| any inferred flow above `10 mL/min` | `180` |

These rows are not removed from the main model fit because the sender specified
the new weight-derived columns as the corrected flowrates. However, the
above-10 mL/min values should be checked with the data provider or pump
calibration notes.

## Corrected Flow Columns Versus Logged Flow Columns

The new backcalculated flow columns are highly correlated with the old logged
flow columns, but they are systematically shifted.

| Quantity | Corrected median | Legacy median | Mean correction | Median correction | Correlation |
| --- | ---: | ---: | ---: | ---: | ---: |
| acid flow | `6.6000` | `5.5044` | `+1.1502` | `+1.1493` | `0.9931` |
| sodium acetate flow | `6.2700` | `6.0076` | `+0.2438` | `+0.2534` | `0.9926` |
| water flow | `5.9526` | `4.8622` | `+1.1113` | `+1.1056` | `0.9936` |
| pH sensor | `4.4252` | `4.4252` | `0.0000` | `0.0000` | `1.0000` |

This means the pH output is unchanged relative to `PH_2`, while the main data
fix is in the three inlet flows.

![Weight-backcalculated flows versus logged flow columns](../results/equilibrium_weights_data_report_20260608_235235/figures/legacy_vs_weight_flows.png)

![Flow correction distributions](../results/equilibrium_weights_data_report_20260608_235235/figures/flow_correction_deltas.png)

## Weight-Corrected Input And Output Behavior

The corrected data retain broad flow excitation and broad pH variation. The old
flat-pH region is no longer flagged by the preprocessing rule.

![Weights-corrected pH and inlet behavior](../results/equilibrium_weights_data_report_20260608_235235/figures/corrected_input_output_behavior.png)

The main corrected-data ranges are:

| Variable | Min | Median | Max |
| --- | ---: | ---: | ---: |
| `acid_flow` | `2.0696` | `6.6000` | `11.4000` |
| `acetate_flow` | `1.3391` | `6.2700` | `10.3478` |
| `water_flow` | `1.1748` | `5.9526` | `11.0324` |
| `total_flow` | `4.8168` | `18.9073` | `31.4408` |
| `flow_ratio_acetate_acid` | `0.1335` | `0.9239` | `3.9722` |
| `pH-sensor` | `3.5717` | `4.4252` | `5.2186` |
| raw equilibrium pH | `3.8945` | `4.7261` | `5.3592` |

The median corrected total flow is `18.9073 mL/min`, which is higher than the
previous logged-flow median of about `16.36 mL/min`.

## Equilibrium Charge-Balance Model

The model is unchanged. Only the input data changed.

Let:

- \(F_H\) be the acetic acid flowrate,
- \(F_A\) be the sodium acetate flowrate,
- \(F_W\) be the Arium water flowrate,
- \(F_T\) be the total flowrate.

Then:

$$
F_T = F_H + F_A + F_W
$$

The stock concentrations are:

$$
C_{H,0} = 0.1\ \mathrm{mol/L}
$$

$$
C_{A,0} = 0.1\ \mathrm{mol/L}
$$

After ideal inline mixing:

$$
C_H = C_{H,0}\frac{F_H}{F_T}
$$

$$
C_A = C_{A,0}\frac{F_A}{F_T}
$$

The total acetate-family concentration and sodium concentration are:

$$
C_T = C_H + C_A
$$

$$
C_{Na} = C_A
$$

For acetic acid:

$$
K_a = 10^{-pK_a}
$$

with:

$$
pK_a = 4.76
$$

Given \(H = [H^+]\), acetate equilibrium and water self-ionization give:

$$
[A^-] = \frac{C_T K_a}{K_a + H}
$$

$$
[OH^-] = \frac{K_w}{H}
$$

with:

$$
K_w = 10^{-14}
$$

The charge-balance residual is:

$$
f(H) =
H + C_{Na}
- \frac{C_TK_a}{K_a + H}
- \frac{K_w}{H}
$$

The model solves:

$$
f(H) = 0
$$

and reports:

$$
pH_{eq} = -\log_{10}(H)
$$

## Affine Calibration

The empirical measurement map is:

$$
\widehat{PH}_{2,k} = b_0 + b_1pH_{eq,k}
$$

For the previous logged-flow dataset, the fitted relation was:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

For the new weight-corrected dataset, the fitted relation is:

$$
pH\text{-sensor} \approx -0.3164 + 1.0106\,pH_{eq}
$$

This is a major physical improvement. The old fit had a slope far below `1`,
which implied that measured pH was compressed relative to equilibrium chemistry.
The new fit has a slope close to `1`, which means the corrected flows make the
first-principles pH coordinate much more consistent with the measured pH scale.

The remaining mismatch is now mostly a downward offset of about `0.27-0.32 pH`,
rather than a strong affine compression.

## Validation Metrics

The new metrics are saved here:

```text
results/equilibrium_weights_data_report_20260608_235235/tables/lab_metrics.csv
```

| Model stage | Split | N | Mean error | MAE | RMSE | Max abs | Correlation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw equilibrium | train | `723` | `-0.2666` | `0.2680` | `0.3014` | `0.5699` | `0.9008` |
| Raw equilibrium | test | `239` | `-0.3491` | `0.3491` | `0.3524` | `0.5219` | `0.9906` |
| Raw equilibrium | all | `962` | `-0.2871` | `0.2882` | `0.3149` | `0.5699` | `0.9135` |
| Equilibrium + bias | train | `723` | `0.0000` | `0.1174` | `0.1406` | `0.3600` | `0.9008` |
| Equilibrium + bias | test | `239` | `-0.0825` | `0.0829` | `0.0954` | `0.2552` | `0.9906` |
| Equilibrium + bias | all | `962` | `-0.0205` | `0.1089` | `0.1308` | `0.3600` | `0.9135` |
| Equilibrium affine | train | `723` | `0.0000` | `0.1176` | `0.1405` | `0.3682` | `0.9008` |
| Equilibrium affine | test | `239` | `-0.0829` | `0.0832` | `0.0951` | `0.2496` | `0.9906` |
| Equilibrium affine | all | `962` | `-0.0206` | `0.1090` | `0.1307` | `0.3682` | `0.9135` |

Because the new affine slope is close to `1`, the bias-only and affine models
are nearly identical. This is another sign that the corrected flow data make
the chemistry model more physically coherent.

## Comparison Against The Previous Dataset

| Quantity | Previous logged-flow dataset | New weight-corrected dataset | Interpretation |
| --- | ---: | ---: | --- |
| valid rows | `990` | `962` | new file is smaller after data cleanup |
| raw equilibrium test RMSE | `0.4412` | `0.3524` | improved by `0.0888 pH` |
| raw equilibrium all-row RMSE | `0.3982` | `0.3149` | improved by `0.0833 pH` |
| affine test RMSE | `0.0975` | `0.0951` | small numerical improvement |
| affine all-row RMSE | `0.1382` | `0.1307` | modest improvement |
| raw test mean error | `-0.4337` | `-0.3491` | raw overprediction is smaller |
| affine slope | `0.7909` | `1.0106` | much more physically sensible |
| affine intercept | `0.6567` | `-0.3164` | model now looks like near-unity slope plus offset |
| affine test max abs error | `0.2470` | `0.2496` | essentially unchanged |

The answer is therefore mixed but encouraging:

- Yes, the first-principles model performs better before calibration.
- Yes, the affine relation makes much better physical sense.
- The final calibrated test RMSE improves only slightly, because affine
  calibration had already removed much of the old logged-flow mismatch.
- The remaining residuals are still large enough that this should not yet be
  treated as a validated dynamic simulator.

## Figures For The New Equilibrium Fit

The time-response plot shows that the raw equilibrium prediction is still above
the measured pH, but the offset is smaller than before.

![Lab pH against equilibrium core predictions](../results/equilibrium_weights_data_report_20260608_235235/figures/lab_equilibrium_validation_time.png)

The scatter plot is the most important qualitative result. Compared with the
previous logged-flow result, the fitted trend has a slope close to the identity
line. The split between early and later behavior is still visible, but the
global compression problem is much weaker.

![Measured pH versus raw equilibrium pH](../results/equilibrium_weights_data_report_20260608_235235/figures/lab_equilibrium_validation_scatter.png)

The residual plots show that affine calibration removes the main offset, but
structured residuals remain with respect to sample index and chemistry
coordinates.

![Equilibrium residuals before and after empirical calibration](../results/equilibrium_weights_data_report_20260608_235235/figures/lab_equilibrium_residuals.png)

The train/test RMSE plot shows the raw-to-calibrated improvement.

![Equilibrium train/test RMSE](../results/equilibrium_weights_data_report_20260608_235235/figures/lab_equilibrium_train_test_rmse.png)

The test residual histogram shows that bias-only and affine calibration are
nearly equivalent for the corrected dataset.

![Weights-corrected test residual distributions](../results/equilibrium_weights_data_report_20260608_235235/figures/weights_residual_histogram.png)

## Generated Pump-Grid Interpretation

The generated pump-grid tables are still useful offline design artifacts. They
are generated from the same pump bounds:

$$
1 \le F_H, F_A, F_W \le 10\ \mathrm{mL/min}
$$

Across the generated grid:

| Quantity | Min | Mean | Max |
| --- | ---: | ---: | ---: |
| raw equilibrium pH | `3.7697` | `4.7612` | `5.7602` |
| affine calibrated pH | `3.4932` | `4.4952` | `5.5047` |
| total buffer concentration, mol/L | `0.0167` | `0.0667` | `0.0952` |
| water fraction | `0.0476` | `0.3333` | `0.8333` |

![Generated pump-grid heatmaps](../results/equilibrium_weights_data_report_20260608_235235/figures/generated_pump_grid_heatmaps.png)

Water still mostly changes dilution, total flow, and future residence-time
coordinates rather than the ideal equal-stock acid/acetate ratio.

![Generated water dilution sensitivity](../results/equilibrium_weights_data_report_20260608_235235/figures/generated_water_dilution_sensitivity.png)

## What Improved

The corrected data improve the first-principles story in three ways.

First, the raw equilibrium error is smaller. Held-out raw test RMSE decreased
from `0.4412 pH` to `0.3524 pH`, and all-row raw RMSE decreased from
`0.3982 pH` to `0.3149 pH`.

Second, the affine slope is now nearly one:

$$
b_1 = 1.0106
$$

This means the corrected flows largely remove the earlier apparent compression
between equilibrium chemistry and measured pH.

Third, the new dataset no longer triggers the flat-pH trial filter. That is
consistent with the sender's note that bad measurements were removed.

## What Still Does Not Fully Work

The raw equilibrium prediction still overpredicts measured pH:

```text
all-row mean error = -0.2871 pH
test mean error = -0.3491 pH
```

The affine model still has held-out test bias:

```text
test mean error = -0.0829 pH
```

The scatter plot also shows two visible bands or regimes. This suggests that
there is still session or routing behavior not explained by a single static
chemistry equation. Possible causes include pH probe calibration offset,
temperature or activity effects, unmodeled mixing or residence time, and
remaining timing differences between flow changes and pH readings.

The 180 rows with at least one inferred flow above `10 mL/min` are also worth
checking. The nominal pump bounds are `1-10 mL/min`, so values above `10` may
reflect backcalculation assumptions, density assumptions, timing windows, or
actual delivered flow differing from the nominal pump command.

## Main Conclusion

The new weight-corrected dataset makes the equilibrium first-principles model
more credible.

The strongest evidence is not only the small affine RMSE improvement. The
strongest evidence is that the fitted calibration changed from:

$$
PH_2 \approx 0.6567 + 0.7909\,pH_{eq}
$$

to:

$$
pH\text{-sensor} \approx -0.3164 + 1.0106\,pH_{eq}
$$

That near-unity slope is much more consistent with a first-principles
equilibrium pH coordinate plus a measurement or process offset.

The model is better, but it is still not ready as a dynamic plant simulator.
The next safe step remains an open-loop dynamic experiment with verified
valve routing, fixed sampling, enough hold time for settling, and logged
commanded and measured flows.
