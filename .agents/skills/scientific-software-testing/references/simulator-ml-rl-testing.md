# Simulator, ML, and RL Testing

## Simulator contract tests

Offline:

- object paths
- variable names
- units
- expected ranges
- export schema
- snapshot identity

Live, only when authorized:

- open known copy
- read known value
- write bounded test value
- read back
- run small case
- restore
- close owned session

## ML tests

- split before preprocessing
- pipeline serialization
- feature order
- missing input
- target leakage check
- physical bounds
- calibration transform
- OOD flag behavior
- batch and single prediction consistency

## RL tests

- reset contract
- random-action smoke
- termination and truncation
- action scaling
- proposed and executed action logging
- replay tuple
- target update
- checkpoint round trip
- evaluation does not train
- small benchmark aggregate

## Stochastic assertions

Use ranges or aggregate expectations with enough replications. Avoid brittle exact seed-specific scores.
