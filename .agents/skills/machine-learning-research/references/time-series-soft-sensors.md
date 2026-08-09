# Time Series, Soft Sensors, and Surrogates

## Time alignment

Identify:

- sensor sample times
- laboratory-assay times
- transport delay
- measurement filtering
- actuator commands
- target availability
- interpolation
- missing intervals

Do not align a laboratory target with future process measurements.

## Split design

Prefer:

- chronological holdout
- rolling-origin evaluation
- blocked cross-validation
- leave-one-run, batch, grade, or operating regime out

## Baselines

- persistence
- seasonal or moving average
- linear dynamic model
- PLS
- autoregression
- domain mechanistic estimate

## Soft-sensor checks

- target measurement uncertainty
- assay delay
- drift
- sensor fouling
- missing inputs
- grade transitions
- extrapolation
- recalibration frequency
- physical bounds
- uncertainty at deployment

## Surrogate checks

- design-of-experiments coverage
- interpolation versus extrapolation
- gradient quality if used in optimization
- constraint and boundary behavior
- uncertainty
- active learning
- validation against the original simulator or experiment
