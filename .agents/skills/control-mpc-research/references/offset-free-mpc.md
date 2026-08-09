# Offset-Free MPC and Target Selection

## Augmented model

A common structure is

\[
x_{k+1}=Ax_k+Bu_k+B_d d_k,
\]

\[
d_{k+1}=d_k,
\]

\[
y_k=Cx_k+C_d d_k.
\]

State the actual augmentation used.

## Observer

Verify:

- augmented state ordering
- measurement residual
- gain dimensions
- update timing
- detectability
- disturbance initialization
- scaling

## Steady target

A target selector may solve

\[
x_s = Ax_s + Bu_s + B_d\hat d,
\]

\[
y_s = Cx_s + C_d\hat d,
\]

with input and output constraints and an objective that balances raw-setpoint tracking and regularization.

## Audit distinctions

- raw setpoint \(r\)
- selected target \(y_s\)
- plant output \(y\)
- disturbance estimate \(\hat d\)
- steady input \(u_s\)
- target slack

Report tracking against both raw and selected targets when they differ.
