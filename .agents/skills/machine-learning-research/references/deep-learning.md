# Deep Neural Network Audit

## Before architecture search

Establish:

- naive baseline
- linear or latent-variable baseline
- strong classical ML baseline
- sample size and effective independent sample size
- target noise
- deployment latency and memory requirements

## Training audit

- architecture and parameter count
- activations
- initialization
- normalization
- loss
- optimizer
- learning-rate schedule
- batch size
- weight decay
- dropout
- augmentation
- early stopping
- checkpoint selection
- seeds
- compute budget

## Diagnostics

- train and validation curves
- gradient norms
- activation saturation
- exploding or vanishing gradients
- overfitting gap
- calibration
- sensitivity to initialization
- feature attribution stability
- physical-bound violations
- OOD behavior
- ablations

## Sequence models

For RNN, GRU, LSTM, temporal convolution, or transformer models, check:

- causal masking
- window definition
- horizon
- overlap leakage
- hidden-state reset
- padding and masks
- exogenous input availability
- long-range versus short-range baseline
- computational cost

## Reporting

A larger architecture is not a contribution by itself. Report what capability it adds and whether the improvement survives fair tuning and independent evaluation.
