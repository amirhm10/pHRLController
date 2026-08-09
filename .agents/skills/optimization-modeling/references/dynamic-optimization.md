# Dynamic Optimization and Optimal Control

## Generic discrete problem

\[
\begin{aligned}
\min_{\{x_k,u_k\}}\quad&
\Phi(x_N)+\sum_{k=0}^{N-1}\ell(x_k,u_k)\\
\text{subject to}\quad&
x_{k+1}=f(x_k,u_k),\\
&g(x_k,u_k)\le 0,\\
&x_0=x_{\mathrm{init}}.
\end{aligned}
\]

## Formulation choices

- single shooting
- multiple shooting
- direct collocation
- simultaneous DAE transcription
- control blocking
- piecewise constant or higher-order controls
- explicit or implicit integration

## Audit

- Is the continuous model correct?
- Is the time grid adequate for fastest dynamics?
- Are algebraic states initialized consistently?
- Are path constraints enforced between nodes?
- Are controls absolute values or increments?
- Are terminal conditions physically attainable?
- Does the discretized objective approximate the intended integral?
- Are state and control scales suitable?
- Does warm starting preserve variable ordering?
- Is the model local, linearized, or nonlinear?

## MPC-specific distinction

Separate:

- model horizon
- prediction horizon
- control horizon
- decision interval
- plant integration step
- estimator update interval

These time scales are often confused.
