# Calibration, Uncertainty, and Distribution Shift

## Classification calibration

Consider:

- reliability diagrams
- negative log likelihood
- Brier score
- expected calibration error
- threshold-specific utility

Fit post-hoc calibration only on data separate from model training.

## Regression uncertainty

Consider:

- predictive intervals
- empirical coverage
- interval width
- residual quantiles
- ensemble disagreement
- Bayesian or approximate uncertainty
- conformal methods when assumptions and exchangeability are appropriate

## Shift types

- covariate shift
- label shift
- concept drift
- temporal drift
- sensor drift
- operating-regime shift
- plant or equipment shift
- intervention-induced shift

## OOD evaluation

Report:

\[
M_{\mathrm{ID}}
\quad \text{and} \quad
M_{\mathrm{OOD}}
\]

separately. Define the shift rather than using "OOD" as a generic label.

## Decision use

Uncertainty should change an action:

- abstain
- request measurement
- switch to mechanistic model
- tighten optimization constraints
- trigger recalibration
- fall back to a safe controller

If uncertainty is computed but never used or validated, its practical value is unclear.
