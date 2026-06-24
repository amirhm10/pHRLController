# Presentation-Ready pH Modeling Report

Generated: 2026-06-24

Source document:

```text
C:\Users\hamed\OneDrive - McMaster University\docukment.docx
```

Repository evidence used:

- `reports/data_preparation_report.md`
- `reports/henderson_hasselbalch_prepared_validation.md`
- `reports/hh_residual_shift_diagnostic.md`

## Objective

This report combines the modeling notes from the Word document with the data-analysis results generated in this repository. The goal is to prepare a clear technical story that can later be converted into presentation slides.

The intended story is:

1. Why Henderson-Hasselbalch is the correct first-principles baseline for this acetate-buffer system.
2. Why water is not expected to strongly change ideal steady-state pH.
3. What the updated lab data show.
4. How the static model predicts the pH trend but reveals a persistent bias.
5. How apparent `pK_a` was calculated and why the post-sample-183 value should not be interpreted as a real temperature-driven pKa change.
6. How this evidence motivates two later controller directions.

## 1. System And Modeling Assumptions

The current inline pH system mixes three inlet streams:

| stream | meaning | nominal stock |
| --- | --- | --- |
| `flow-acid` | acetic acid flowrate | 100 mM |
| `flow-sodium` | sodium acetate flowrate | 100 mM |
| `flow-water` | Arium ultrapure water flowrate | none |

The reliable pH measurement is the last-column `pH-sensor`, which is numerically the same as `observation.biosmb-sensors.PH_2`. The diagnostic comparison found 962 matching rows and a maximum absolute difference of about `5e-10`. `PH_1` is not used for model validation.

The source document makes an important modeling distinction: the acetate/acetic-acid pair is the chemical buffer, while water mostly changes dilution, buffer strength, residence time, and sensor/mixing dynamics. Water should therefore not be treated as a strong independent steady-state pH actuator.

## 2. Why Henderson-Hasselbalch Is The Baseline

The acetic-acid/acetate pair is a weak-acid buffer. For an ideal buffer, the Henderson-Hasselbalch relation is

$$
\mathrm{pH}
= pK_a + \log_{10}\left(
\frac{[\mathrm{acetate}]}{[\mathrm{acetic\ acid}]}
\right).
$$

For this flow system, the mixed analytical concentrations are

$$
C_{acid,k}^{mix}
= \frac{C_{acid}^{stock} F_{acid,k}}{F_{acid,k}+F_{acetate,k}+F_{water,k}},
$$

$$
C_{acetate,k}^{mix}
= \frac{C_{acetate}^{stock} F_{acetate,k}}{F_{acid,k}+F_{acetate,k}+F_{water,k}}.
$$

Substituting into Henderson-Hasselbalch gives

$$
\mathrm{pH}_{HH,k}
= pK_a
+ \log_{10}\left(
\frac{C_{acetate}^{stock}F_{acetate,k}}
{C_{acid}^{stock}F_{acid,k}}
\right).
$$

Because the acid and acetate stocks are both assumed to be 100 mM,

$$
\mathrm{pH}_{HH,k}
= pK_a + \log_{10}\left(
\frac{F_{acetate,k}}{F_{acid,k}}
\right).
$$

This is why Henderson-Hasselbalch is the right first baseline. It is simple, physically interpretable, and directly connects pH to the sodium-acetate/acetic-acid flow ratio. It should not be expected to capture delay, mixing, sensor response, calibration shifts, or nonideal activity effects.

## 3. Why Water Has Weak Direct Steady-State pH Effect

The water flow cancels from the ideal Henderson-Hasselbalch ratio when both stock concentrations are equal. This does not mean water is irrelevant. It means water is weak as a direct steady-state pH actuator.

Water can still matter through:

1. Buffer capacity:

$$
C_{buffer,k}^{mix}
= \frac{C_{acid}^{stock}F_{acid,k}
+ C_{acetate}^{stock}F_{acetate,k}}
{F_{acid,k}+F_{acetate,k}+F_{water,k}}.
$$

A more diluted buffer can have nearly the same pH but lower resistance to disturbances.

2. Residence time and dynamics:

$$
F_{total,k} = F_{acid,k}+F_{acetate,k}+F_{water,k},
$$

$$
\tau_k \approx \frac{V}{F_{total,k}}.
$$

Changing water changes total flowrate, which can change delay, mixing time, and sensor response.

3. Nonideal pH effects:

The source document notes that measured pH depends on hydrogen-ion activity, not only concentration. Dilution and ionic strength can therefore shift the measured pH slightly through activity coefficients and apparent `pK_a`.

The repository diagnostic directly tested whether a more complete acetate charge-balance equilibrium model could explain the observed bias. It could not. The charge-balance prediction differed from Henderson-Hasselbalch by only about `0.001` pH on average and less than `0.009` pH in the checked segments. Therefore the observed `0.3` pH bias is not explained by water dilution or equilibrium chemistry alone.

## 4. Data Preparation Results

The updated dataset was prepared as a sequential time series using only:

$$
z_k =
\left[
t_k,\,
F_{acid,k},\,
F_{acetate,k},\,
F_{water,k},\,
\mathrm{pH}_k
\right].
$$

The dataset contains 962 rows and 47 raw columns. The working features are:

| feature | min | mean | median | max |
| --- | --- | --- | --- | --- |
| acid flow | 2.070 | 6.571 | 6.600 | 11.400 |
| acetate flow | 1.339 | 6.049 | 6.270 | 10.348 |
| water flow | 1.175 | 6.277 | 5.953 | 11.032 |
| measured pH | 3.572 | 4.425 | 4.425 | 5.219 |
| acetate/acid ratio | 0.134 | 1.097 | 0.924 | 3.972 |

Two sampling phases were detected from `delta_t_min`:

| phase | sample range | median `delta_t_min` | interpretation |
| --- | --- | --- | --- |
| Phase 1 | 0-308 | 2.347 min | slower sampling |
| Phase 2 | 309-961 | 1.152 min | faster sampling |

Data-preparation figures:

![All prepared features](../results/data_preparation_20260624_123926/figures/all_features_four_subplots.png)

![pH with acid and acetate flows](../results/data_preparation_20260624_123926/figures/ph_with_acid_base_flows.png)

## 5. Static Model Prediction And Bias

The Henderson-Hasselbalch model was evaluated with

$$
pK_a = 4.760,
\quad
C_{acid}^{stock}=C_{acetate}^{stock}=0.100\ \mathrm{mol/L}.
$$

The residual was defined as

$$
e_k = \mathrm{pH}_{sensor,k} - \mathrm{pH}_{HH,k}.
$$

Overall, the static model captured the direction of pH changes, but not the absolute measured value over the whole dataset.

| scope | n | mean error | MAE | RMSE | max abs error | correlation |
| --- | --- | --- | --- | --- | --- | --- |
| all samples | 962 | -0.286 | 0.287 | 0.314 | 0.568 | 0.913 |
| Phase 1 | 309 | -0.159 | 0.162 | 0.220 | 0.417 | 0.888 |
| Phase 2 | 653 | -0.347 | 0.347 | 0.350 | 0.568 | 0.990 |

The strong correlation, especially after sample 309, shows that the acid/base ratio still explains the direction of pH movement. The problem is a persistent offset.

Static-model figures:

![Measured pH and HH prediction](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_vs_hh_prediction.png)

![Measured pH, HH prediction, and acid/base flows](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_vs_hh_prediction_with_acid_base_flows.png)

![HH residual](../results/henderson_hasselbalch_prepared_validation_20260624_125349/figures/ph_minus_hh_prediction.png)

## 6. Residual Shift Near Sample 183

The residual shift does not start at the sampling-rate phase change. The main changepoint is sample 183, while the sampling-rate phase change starts later at sample 309.

At sample 183:

- The previous timestamp was `2026-05-12T20:32:17.416Z`.
- The next timestamp was `2026-05-13T13:37:38.080Z`.
- The time gap was about `1025.4` min.
- The episode/step counters reset.
- Reservoir mass readings reset upward.
- The reliable `PH_2`/`pH-sensor` measurement shifted downward.

This points to an overnight/session boundary rather than a simple `delta_t` or sampling-rate effect.

| segment | samples | mean residual | RMSE | mean apparent `pK_a` | required acetate/acid stock factor |
| --- | --- | --- | --- | --- | --- |
| before shift | 0-182 | -0.0366 | 0.0503 | 4.723 | 0.919 |
| after shift, same sampling | 183-308 | -0.3364 | 0.3392 | 4.424 | 0.461 |
| after phase change | 309-961 | -0.3466 | 0.3500 | 4.413 | 0.450 |

Residual-shift figures:

![Residual shift overview](../results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_overview.png)

![Residual shift local context](../results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_local_context.png)

## 7. How Apparent pKa Was Calculated

For each sample, the apparent pKa diagnostic is

$$
pK_{a,k}^{eff}
= \mathrm{pH}_{sensor,k}
- \log_{10}\left(
\frac{C_{acetate}^{stock}F_{acetate,k}}
{C_{acid}^{stock}F_{acid,k}}
\right).
$$

With equal 100 mM stocks, this becomes

$$
pK_{a,k}^{eff}
= \mathrm{pH}_{sensor,k}
- \log_{10}\left(
\frac{F_{acetate,k}}{F_{acid,k}}
\right).
$$

This value is not a direct measurement of the true thermodynamic pKa. It is a lumped intercept diagnostic. It can include:

- true acid equilibrium behavior,
- pH probe calibration offset,
- stock concentration mismatch,
- pump calibration mismatch,
- activity and ionic-strength effects,
- session or setup changes,
- unmodeled dynamics when data are not at steady state.

The source document makes the same distinction: literature pKa can be used when no data are available, but real lab data should be used to estimate an apparent pKa or intercept. The document also notes that this apparent pKa should not be estimated from water flow.

Before sample 183, the mean apparent pKa is about `4.723`, close enough to the expected room-temperature acetate-buffer value to be reasonable given sensor, activity, and pump uncertainties. After sample 183, the apparent value drops to about `4.42`, which is too large a change to explain by normal temperature variation.

The source document explicitly addresses this point: normal acetic-acid pKa over ordinary aqueous lab temperatures remains near the mid-4.7 range. Therefore the post-183 value should be interpreted as a regime-dependent intercept shift, not a physical pKa caused by temperature.

Equivalently, the post-shift residual implies

$$
10^{-0.336} \approx 0.46.
$$

That means the post-shift data behave as if the effective acetate-to-acid strength ratio were about half of the assumed ratio, or as if the reliable pH sensor had a roughly `-0.3` pH offset.

## 8. Main Scientific Interpretation

The evidence supports this interpretation:

1. Henderson-Hasselbalch is a correct first-principles baseline for the acetate/acetic-acid ratio.
2. Water should not be forced to explain steady-state pH because it cancels from the ideal ratio when stock concentrations are equal.
3. Water should be kept in the model for buffer capacity, total flow, delay, mixing, and sensor-response dynamics.
4. The static HH model captures the trend but exposes a persistent offset.
5. The offset begins at sample 183, before the sampling-rate phase change at sample 309.
6. The shift is too large to be explained by normal temperature-driven pKa variation or by equilibrium dilution.
7. The most likely missing element is a regime-dependent calibration/intercept shift, caused by pH sensor offset, stock/pump ratio change, reservoir/session change, or a combination of these.

This means the static model is useful, but not sufficient as the final plant model. The next model should combine first-principles chemistry with calibration and dynamics.

## 9. Controller Implications From The Source Document

The source document warns that a controller should not freely control the three raw pump flows as if they were equally meaningful pH actuators. The pH objective alone is non-unique because many acid/acetate flow pairs can have the same ratio and therefore nearly the same pH.

For example, if the stock concentrations are equal, any acid/acetate pair with the same ratio gives the same ideal HH pH. Different total flow levels may consume different amounts of reagent or change dynamics, but they do not create a unique pH target.

The better control coordinates are:

$$
r_k = \frac{F_{acetate,k}}{F_{acid,k}},
$$

$$
F_{buffer,k} = F_{acid,k}+F_{acetate,k},
$$

$$
F_{total,k} = F_{acid,k}+F_{acetate,k}+F_{water,k}.
$$

Here:

- `r_k` controls ideal pH.
- `F_buffer,k` controls buffer strength and chemical usage.
- `F_total,k` controls residence time, delay, and throughput.
- `F_water,k` should be fixed or used for a secondary objective, not treated as a primary pH actuator.

Given a desired ratio `r_k` and total buffer flow `F_buffer,k`, the acid and acetate pump commands can be allocated deterministically:

$$
F_{acid,k} = \frac{F_{buffer,k}}{1+r_k},
$$

$$
F_{acetate,k} = \frac{r_k F_{buffer,k}}{1+r_k}.
$$

This removes the acid/base non-uniqueness from the control problem.

## 10. Two Suggested Next Parts

### Part 1: Calibrated Dynamic First-Principles Model

The immediate next modeling part should not be RL or MPC yet. It should be a calibrated dynamic model built around the HH baseline:

$$
\mathrm{pH}_{static,k}
= pK_{a,regime}^{eff}
+ \log_{10}\left(
\frac{F_{acetate,k}}{F_{acid,k}}
\right),
$$

followed by delay, mixing, and sensor response:

$$
\mathrm{pH}_{mix,k}
= G_{mix}(q^{-1})\,\mathrm{pH}_{static,k-d},
$$

$$
\mathrm{pH}_{sensor,k}
= G_{sensor}(q^{-1})\,\mathrm{pH}_{mix,k}.
$$

The first calibration should separate at least two regimes:

- Regime 1: samples 0-182.
- Regime 2: samples 183 onward.

Confirmation criterion:

If the regime-specific intercept removes the `0.3` pH bias but residual lag remains, then the next missing component is dynamic delay/sensor response.

### Part 2: Ratio-Based Controller Or Residual-RL Controller

After the calibrated dynamic model is validated, controller work can start in a physically constrained action space.

The first controller should control the ratio or pH-equivalent ratio command, not raw acid and acetate flows independently. A possible control input is:

$$
u_k =
\left[
\log_{10}(r_k),\,
F_{buffer,k}
\right],
$$

with water either fixed or assigned to a secondary objective such as maintaining total flow, residence time, or dilution.

A later RL design should use HH as a baseline and learn only a correction:

$$
u_k = u_{HH,k} + \Delta u_{RL,k},
$$

or

$$
\mathrm{pH}_{pred,k}
= \mathrm{pH}_{HH,k}
+ \Delta \mathrm{pH}_{cal/dyn/RL,k}.
$$

The purpose of the learned correction would be sensor bias, regime shift, mixing delay, activity effects, and other model mismatch. The RL agent should not be asked to rediscover the acid/base ratio from raw pump flows.

## 11. Slide-Ready Narrative

The report can become a slide deck with this sequence:

1. Problem setup: inline acetate-buffer pH process.
2. Why HH: pH depends mainly on acetate/acetic-acid ratio.
3. Why water is weak for steady pH: water cancels from the ideal ratio.
4. Data preparation: last four columns and reliable `PH_2`/`pH-sensor`.
5. Prepared data figure: acid, acetate, water, and pH traces.
6. Static HH validation: prediction follows trend but has bias.
7. Residual shift: bias starts at sample 183, not sample 309.
8. Apparent pKa: before sample 183 is reasonable, after sample 183 is not physically a temperature pKa.
9. Interpretation: regime-dependent offset from calibration, stock/pump ratio, or setup/session change.
10. Next model: calibrated HH plus delay, mixing, and sensor response.
11. Controller implication: use ratio-based action coordinates.
12. Final direction: deterministic flow allocator first, residual/RL correction later.

## 12. Limitations

- The Word document contains equation objects that were reconstructed here from surrounding text and from repository model definitions.
- No new external citation was verified in this report. Literature claims from the source document should be checked before a thesis or conference slide deck.
- The CSV does not include temperature, pH calibration records, stock concentration assay records, tubing changes, or operator notes.
- The current evidence identifies the timing and likely class of the residual shift, but not the exact physical cause.

## 13. Immediate Next Work

The next report/code step should fit and validate a regime-specific calibrated HH model:

1. Add a calibration script that estimates an intercept or apparent `pK_a^{eff}` separately before and after sample 183.
2. Save a new comparison table with calibrated predictions and residuals.
3. Generate figures comparing measured pH, raw HH prediction, and calibrated HH prediction.
4. Check whether remaining error is mostly dynamic lag.
5. Only after that, build the dynamic delay/mixing/sensor model that will later support controller design.
