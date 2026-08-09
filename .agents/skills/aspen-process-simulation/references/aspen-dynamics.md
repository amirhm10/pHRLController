# Aspen Plus Dynamics Audit

## Dynamic conversion

- steady-state case valid
- sizing completed where needed
- holdups defined
- pressure-flow network specified
- valves and actuators sized
- controller loops initialized
- dynamic file saved separately

## Hold test

Before disturbances, run a hold test:

- outputs remain near steady values
- inventories do not drift
- controllers remain near initial outputs
- no hidden event fires
- mass and energy balances remain acceptable
- solver step size and warnings are stable

## Disturbance test

Record:

- exact variable and object
- magnitude
- units
- timing
- ramp or step
- duration
- restoration
- expected physical response

## Control audit

- process variable
- setpoint
- controller action
- direct or reverse action
- output limits
- anti-windup
- cascade or ratio structure
- sample or execution rate
