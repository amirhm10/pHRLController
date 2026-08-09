# System Identification and Estimation

## Identification audit

- experiment design and excitation
- sample time
- preprocessing
- detrending and scaling
- operating point
- delay
- model structure and order
- training and validation split
- one-step and free-run prediction
- residual autocorrelation
- residual-input correlation
- stability
- uncertainty
- extrapolation region

## State estimation

For an observer or Kalman filter, inspect:

- process and measurement noise assumptions
- gain or covariance
- detectability
- initialization
- innovation sequence
- bias
- sensor mapping
- delayed or asynchronous measurements
- constraints on states

## Online adaptation

State:

- parameterization
- update law
- excitation requirement
- regularization
- forgetting factor
- projection or bounds
- update frequency
- interaction with MPC
- stability assumptions
- rollback behavior

A changing model can make stored RL experience nonstationary.
