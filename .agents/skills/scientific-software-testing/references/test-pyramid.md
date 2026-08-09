# Scientific Test Pyramid

## Fast on every change

- units and shapes
- pure functions
- scaling
- equations
- invariants
- schema
- configuration
- small derivative checks

## Medium on pull request or selected changes

- controller and estimator integration
- optimizer cases
- notebook smoke
- small simulation
- ML preprocessing and model round trip
- RL environment and replay

## Expensive on schedule or explicit request

- live Aspen
- long nonlinear simulation
- multi-seed training
- full end-to-end reports
- large sensitivity or uncertainty study

## Test metadata

Mark tests by:

- unit
- integration
- simulator
- slow
- stochastic
- requires-license
- GPU
- notebook
- regression

A clear execution policy prevents accidental expensive runs.
