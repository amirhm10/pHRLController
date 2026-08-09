# pH Control

## Process characteristics

- strongly nonlinear steady-state gain
- steep response near equivalence
- buffering
- mixing and transport delay
- measurement noise and drift
- asymmetric actuator authority
- acid and base constraints

## Controller audit

- manipulated streams
- absolute versus incremental flow
- valve and pump behavior
- actuator deadband
- sample time
- sensor filtering
- anti-windup
- setpoint schedule
- feedforward
- model validity across pH range

## Metrics

- pH error
- hydrogen-ion or alkalinity error when meaningful
- overshoot
- settling
- acid and base use
- simultaneous dosing
- constraint violations
- sensor-noise sensitivity
- performance by buffer and equivalence region

## RL state

Include enough chemistry or history to represent delayed and buffered behavior. A single pH measurement may not be Markov.
