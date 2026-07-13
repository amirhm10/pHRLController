# Offline pH TD3 Ratio-Preserving Flow Algorithm

Date: 2026-07-13

## Objective

This report defines the new offline pH TD3 action algorithm. One TD3 actor still
produces two continuous actions, but the action conversion now guarantees that
the optional total-flow decision cannot change or remove the acid/acetate ratio
selected by the first action.

The algorithm has two goals:

1. Track the requested pH by selecting the acetate/acid ratio.
2. Reduce unnecessary acid and acetate use by selecting only the optional flow
   above the minimum needed to realize that ratio.

This implementation is currently an offline simulation method. It has not been
connected to the BioSMB online runner, validated against process dynamics, or
validated in the laboratory.

## Motivation

The previous `ratio_buffer_sum` action mode converted the second actor output to
an acid+acetate total flow first. It then calculated the ratio interval available
at that total flow and interpreted the first actor output inside that interval.

This sum-first order can remove pH control authority. If the actor selects a
total buffer flow close to 20 mL/min, the individual 10 mL/min pump limits force
both acid and acetate flows close to 10 mL/min. Their ratio approaches one and
the ideal pH approaches the pKa of 4.76, regardless of the ratio action.

The saved 500,000-step `gamma = 0.99`, final-noise `0.04` actor demonstrated
this failure. At a target pH of approximately 4.8917, it selected a total buffer
flow of approximately 19.873 mL/min. That flow allowed only approximately
4.7545 to 4.7655 pH under the pump constraints. The resulting deterministic pH
bias was approximately -0.1262.

Fixing the total buffer flow at 15 mL/min avoids that particular collapse, but it
uses more reagent than necessary at many targets and restricts the pH interval
that can be reached with 1 to 10 mL/min individual pump limits.

## One-agent formulation

The controller remains one TD3 actor. Its state is

$$
s_t =
\begin{bmatrix}
\mathrm{pH}_t &
\mathrm{pH}_{sp,t} &
\mathrm{pH}_t-\mathrm{pH}_{sp,t} &
a_{\rho,t-1} &
a_{z,t-1}
\end{bmatrix}^{\mathsf T}.
$$

The actor produces

$$
a_t =
\begin{bmatrix}
a_{\rho,t} & a_{z,t}
\end{bmatrix}^{\mathsf T},
\qquad
a_{\rho,t},a_{z,t}\in[-1,1].
$$

The first output selects the acetate/acid flow ratio. The second output selects
the optional fraction of the ratio-feasible total-flow interval. No second RL
agent or optimization network is used.

## Ratio-first physical action conversion

Let

$$
\rho = \frac{F_A}{F_H},
$$

where $F_H$ is acetic-acid flow and $F_A$ is sodium-acetate flow.

The global physical ratio limits are

$$
\rho_{\min}=\frac{F_{A,\min}}{F_{H,\max}},
\qquad
\rho_{\max}=\frac{F_{A,\max}}{F_{H,\min}}.
$$

The normalized ratio action is converted in logarithmic coordinates:

$$
\ell_t = \log_{10}(\rho_{\min})
+ \frac{a_{\rho,t}+1}{2}
\left[
\log_{10}(\rho_{\max})-\log_{10}(\rho_{\min})
\right],
$$

$$
\rho_t=10^{\ell_t}.
$$

For a selected ratio, total buffer flow is

$$
S_t=F_{H,t}+F_{A,t}.
$$

The ratio-specific feasible interval is calculated before the second action is
used:

$$
S_{\min}(\rho_t)=\max\left(
S_{\mathrm{configured,min}},
F_{H,\min}(1+\rho_t),
\frac{F_{A,\min}(1+\rho_t)}{\rho_t}
\right),
$$

$$
S_{\max}(\rho_t)=\min\left(
S_{\mathrm{configured,max}},
F_{H,\max}(1+\rho_t),
\frac{F_{A,\max}(1+\rho_t)}{\rho_t}
\right).
$$

The second actor output becomes an optional-flow fraction:

$$
z_t=\frac{a_{z,t}+1}{2},
\qquad z_t\in[0,1],
$$

$$
S_t=S_{\min}(\rho_t)
+z_t\left[S_{\max}(\rho_t)-S_{\min}(\rho_t)\right].
$$

The pump commands are then

$$
F_{H,t}=\frac{S_t}{1+\rho_t},
\qquad
F_{A,t}=\frac{\rho_t S_t}{1+\rho_t}.
$$

Changing $z_t$ changes total reagent use but leaves $F_A/F_H=\rho_t$. This is
the key difference from the previous sum-first mapping.

## Examples under the current pump bounds

The current acid and acetate pump bounds are 1 to 10 mL/min.

| Target pH | Required ratio | Minimum feasible buffer flow | Minimum-flow allocation |
|---:|---:|---:|---:|
| 3.76 | 0.100 | 11.000 mL/min | acid 10.000, acetate 1.000 |
| 4.76 | 1.000 | 2.000 mL/min | acid 1.000, acetate 1.000 |
| 5.09 | 2.138 | 3.138 mL/min | acid 1.000, acetate 2.138 |
| 5.70 | 8.710 | 9.710 mL/min | acid 1.000, acetate 8.710 |

These values are mathematical pump-feasibility limits. They are not yet
laboratory-approved operating minima.

## Reward extension

The existing relative-band offset reward and total-flow movement penalty are
retained. The new term penalizes optional flow:

$$
J_{\mathrm{economic},t}=w_{\mathrm{economic}}z_t^2.
$$

The implemented starting weight is

$$
w_{\mathrm{economic}}=0.01.
$$

The new reward can be summarized as

$$
r_t = r_{\mathrm{existing},t}
-w_{\mathrm{economic}}z_t^2.
$$

Penalizing $z_t$ rather than raw total flow avoids penalizing a target merely
because its required ratio has a higher unavoidable minimum flow. The logged
physical flows remain available for direct reagent-consumption calculations.

## Default offline experiment

The offline runner now defaults to:

| Setting | Value |
|---|---:|
| Action mode | `ratio_preserving_flow` |
| Total training steps | 500,000 |
| Actor hidden layers | 128, 128 |
| Critic hidden layers | 128, 128 |
| Batch size | 64 |
| Replay capacity | 60,000 |
| Discount factor | 0.97 |
| Exploration start standard deviation | 0.35 |
| Exploration end standard deviation | 0.02 |
| Exploration decay | 5,000 steps, linear |
| Total-flow movement weight | 5.0 |
| Optional-flow economy weight | 0.01 |

The previous `ratio` and `ratio_buffer_sum` modes remain available for controlled
comparisons.

## Saved data and diagnostics

The trajectory now records:

- `action_ratio`
- `action_optional_flow`
- `economic_flow_fraction`
- `feasible_buffer_flow_sum_min`
- `feasible_buffer_flow_sum_max`
- `reward_economic_flow_cost`
- `reward_economic_flow_penalty_term`
- physical acid, acetate, and water flows
- realized acetate/acid ratio

The action-diagnostic figure labels the second coordinate as the optional-flow
action rather than the old sum action.

## Implementation verification

The repository test suite completed with 50 passing tests. Focused tests verify:

- the realized ratio is unchanged when only the optional-flow action changes
- the total flow increases monotonically with the optional-flow action
- physical acid and acetate bounds remain satisfied
- the ratio-specific feasible interval is correct for a known ratio
- the economic reward prefers the minimum optional flow
- legacy BioSMB reward fields remain numerically unchanged

A disposable 400-step end-to-end run also completed. This run was too short for
performance interpretation. It was used only to test the data path. It produced:

- maximum log-ratio conversion error: approximately $9.32\times10^{-8}$
- maximum optional-flow fraction conversion error: approximately
  $2.52\times10^{-6}$
- ratio-specific infeasible rows: 0
- global pump, sum, and water constraint violations: 0

## Compatibility and deployment status

The new action meaning is not compatible with an old actor checkpoint, even
though both actors have two outputs. Old replay-buffer transitions are also not
compatible with the new meaning of the second action.

The offline runner saves a training checkpoint for the new mode. It does not
export a BioSMB actor bundle for this mode because the current online BioSMB
mapping implements the previous `ratio_buffer_sum_v1` contract. This prevents a
new actor from being accidentally used with the wrong physical action conversion.

The `Biosmb-run-online` folder was intentionally left unchanged.

## Limitations

1. The offline plant remains an instantaneous ideal Henderson-Hasselbalch model.
2. Total flow has no modeled effect on mixing, transport delay, residence time,
   buffer capacity, or pH-sensor response.
3. The configured 2 mL/min total-flow minimum is a mathematical bound, not a
   validated laboratory minimum.
4. The economy weight of 0.01 is a starting value and has not completed a full
   training comparison.
5. A full-range deterministic evaluation is still required after training. A
   single final setpoint is not sufficient evidence.

## Required next experiment

Run the new default 500,000-step experiment and compare it with the reproduced
`gamma = 0.97`, final-noise `0.02`, `ratio_buffer_sum` baseline. Both runs should
use the same seed, target schedule, architecture, and reward settings except for
the action conversion and economy term.

The comparison should report:

- 25-target deterministic MAE and maximum error
- target-wise bias
- ratio command versus realized ratio
- unreachable-target count
- mean and cumulative acid consumption
- mean and cumulative acetate consumption
- mean total buffer flow
- optional-flow fraction
- pump saturation
- total-flow movement

The new method is supported if it preserves or improves full-range pH tracking,
produces zero ratio-induced infeasibility, and reduces reagent use relative to
the fixed or sum-first alternatives.

## Reference

Fujimoto, S., van Hoof, H., and Meger, D. (2018). Addressing Function
Approximation Error in Actor-Critic Methods. Proceedings of Machine Learning
Research, 80, 1587-1596.
https://proceedings.mlr.press/v80/fujimoto18a.html
