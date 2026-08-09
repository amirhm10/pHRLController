---
name: machine-learning-research
description: Analyze, design, and validate machine-learning systems beyond reinforcement learning. Use for PCA, PLS, latent-variable monitoring, regression, classification, tree models, deep neural networks, time series, soft sensors, anomaly detection, fault diagnosis, surrogate models, transfer learning, calibration, uncertainty, distribution shift, and physics-informed or hybrid ML. Audit target definition, data provenance, leakage, split design, baselines, tuning fairness, error structure, and OOD behavior.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Machine Learning Research

## Purpose

Treat ML as an empirical science and an engineering system. Establish whether the prediction task, data, evaluation, and model behavior support the claimed use.

RL-specific sequential decision problems belong in `reinforcement-learning-research`.

## Modes

- data and target audit
- PCA, PLS, and latent-variable analysis
- supervised regression or classification
- deep-learning analysis
- time-series and sequence modeling
- soft sensor or surrogate modeling
- anomaly and fault detection
- calibration and uncertainty
- distribution-shift evaluation
- physics-informed or hybrid ML
- model documentation and deployment-readiness review

## Required workflow

### 1. Define the task

State:

- target or label
- prediction time
- available information at prediction time
- unit of analysis
- decision or scientific use
- error costs
- prediction horizon
- causal, predictive, or descriptive intent
- label quality and measurement delay

A model that uses information unavailable at deployment is invalid even if test accuracy is high.

### 2. Establish data provenance

Identify:

- source systems
- collection periods
- plants, assets, subjects, batches, or runs
- units and sensor mappings
- preprocessing history
- exclusions
- missingness
- label generation
- repeated or correlated observations

### 3. Design splits before preprocessing

Choose a split that matches deployment:

- random only for exchangeable independent samples
- grouped by unit, batch, patient, asset, or plant
- chronological or rolling-origin
- leave-one-regime-out
- leave-one-site-out
- distribution-shifted test set

Fit scaling, imputation, feature selection, PCA, and calibration only on training data. Use pipelines or equivalent safeguards.

### 4. Build a baseline ladder

Compare against:

1. constant, persistence, or naive predictor
2. domain heuristic
3. linear or latent-variable model
4. strong classical ML baseline
5. proposed complex model

Do not skip directly to a deep network.

### 5. Train fairly

Record:

- data split
- preprocessing
- architecture or estimator
- loss
- optimizer
- learning rate
- batch size
- regularization
- early stopping
- search space
- tuning budget
- checkpoint rule
- compute
- seeds

Do not use the final test set for iterative tuning.

### 6. Evaluate appropriately

Regression:

- MAE, RMSE, bias
- residual distribution
- calibration or interval coverage
- regime and horizon breakdown
- physical-bound violations

Classification:

- confusion matrix
- precision, recall, specificity
- ROC or precision-recall behavior
- class imbalance
- calibration
- decision-threshold analysis

Time series:

- rolling or blocked evaluation
- multi-step error by horizon
- persistence baseline
- leakage through windows
- drift

Anomaly or fault detection:

- false-alarm rate
- detection delay
- event-level precision and recall
- operating-mode confounding
- unseen-fault behavior

### 7. Analyze errors

Stratify by:

- operating regime
- batch or grade
- asset or plant
- time
- target range
- sensor condition
- subgroup
- disturbance
- data density
- OOD score

Inspect residual structure and physically impossible predictions.

### 8. Assess uncertainty and shift

Separate:

- aleatoric uncertainty
- epistemic uncertainty
- calibration
- interval coverage
- model disagreement
- in-distribution and out-of-distribution performance
- covariate, label, concept, and operational shift

Read [uncertainty-ood.md](references/uncertainty-ood.md).

### 9. Check scientific and physical consistency

When the application is physical:

- units and bounds
- conservation laws
- monotonic relationships where justified
- invariance
- symmetry
- time causality
- known limiting cases
- extrapolation behavior

Combine with the relevant chemical or engineering specialist.

### 10. Decide

State:

- whether the model beats meaningful baselines
- where it works
- where it fails
- uncertainty
- deployment or scientific-use limits
- next experiment

## Method references

- PCA and PLS: [pca-pls.md](references/pca-pls.md)
- Deep networks: [deep-learning.md](references/deep-learning.md)
- Time series and soft sensors: [time-series-soft-sensors.md](references/time-series-soft-sensors.md)
- Uncertainty and OOD: [uncertainty-ood.md](references/uncertainty-ood.md)

## Gotchas

- Random row splits often leak process trajectories, batches, and time.
- High \(R^2\) can coexist with unacceptable bias in a critical regime.
- PCA components are not automatically physically meaningful.
- A deep model may only be learning grade or operating-mode identity.
- Calibration measured on training data is optimistic.
- A model can be accurate in distribution and unsafe under shift.
- More features can increase leakage and fragility.
