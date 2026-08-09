# Dynamic Safety Simulation

## Before simulation

- verify steady initial condition
- verify event logic
- verify equipment inventory
- verify actuator and sensor dynamics
- verify trips and interlocks
- preserve original case
- define abort and stop conditions

## During analysis

- track margins, not only violations
- record first alarm and trip time
- record maximum rate of change
- identify dominant time scale
- inspect fallback and saturation
- check whether solver failure occurs before the physical event

## After simulation

- verify balance and model validity
- classify result as model-based evidence
- state omitted phenomena
- compare with independent calculations where possible
