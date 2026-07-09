# Offline pH TD3 Method Report

## Objective

This report documents the current offline reinforcement-learning setup for the
pH control simulation. It is a method report, not a claim of laboratory
validation. The current environment is an ideal first-principles
Henderson-Hasselbalch simulator for the acetate buffer system, and the TD3
agent is trained only against this offline simulation.

The report will be expanded step by step. This first version records:

- the first-principles environment model,
- manipulated variables and controlled outputs,
- RL state and action definitions,
- TD3 network architecture and training settings,
- the shaped reward function,
- fixed physical and numerical parameters.

## First-Principles pH Environment

The simulated plant is the inline acetate buffer mixing system with three inlet
streams:

- acetic acid stock solution,
- sodium acetate stock solution,
- Arium water.

The first-principles model currently used in the RL environment is the ideal
Henderson-Hasselbalch relation. Let

- `F_HAc` be the acetic acid flowrate in mL/min,
- `F_Ac` be the sodium acetate flowrate in mL/min,
- `F_W` be the water flowrate in mL/min,
- `C_HAc` be the acetic acid stock concentration,
- `C_Ac` be the sodium acetate stock concentration.

The ideal buffer ratio is

$$
R =
\frac{C_{Ac} F_{Ac}}{C_{HAc} F_{HAc}} .
$$

The simulated pH is

$$
\mathrm{pH}
= pK_a + \log_{10}(R).
$$

Since the current acid and acetate stock concentrations are equal,

$$
C_{HAc} = C_{Ac} = 0.1~\mathrm{mol/L},
$$

the pH prediction reduces to

$$
\mathrm{pH}
= pK_a + \log_{10}\left(\frac{F_{Ac}}{F_{HAc}}\right).
$$

Water is still logged as a physical stream, but in this ideal
Henderson-Hasselbalch environment it does not directly change the acid/acetate
ratio because both stocks have equal concentration. In the real lab system,
water can still affect residence time, delay, mixing, buffer strength, and pH
sensor response. Those dynamic effects are not included in this offline RL
environment.

## Manipulated Inputs And Outputs

The physical pump variables are:

| Variable | Meaning | Current role |
|---|---|---|
| `acid_flow` or `F_HAc` | acetic acid flowrate | changed indirectly by the RL ratio action |
| `acetate_flow` or `F_Ac` | sodium acetate flowrate | changed indirectly by the RL ratio action |
| `water_flow` or `F_W` | Arium water flowrate | fixed at the default value |

The RL action is not a direct three-pump command in the current offline setup.
Instead, the agent outputs one normalized action:

$$
a_t \in [-1, 1].
$$

This action is mapped to a log acid/base ratio. Define

$$
\eta_t = \frac{a_t + 1}{2},
$$

where `eta_t` is a unit-interval interpolation coordinate. The feasible
log-ratio is

$$
\ell_t =
\ell_{\min}
+ \eta_t(\ell_{\max} - \ell_{\min}),
$$

where

$$
\ell_{\min} = \log_{10}(R_{\min}),
\qquad
\ell_{\max} = \log_{10}(R_{\max}).
$$

The commanded acetate-to-acid flow ratio is

$$
R_t = 10^{\ell_t}.
$$

The acid and acetate flows are then computed from the fixed buffer-flow sum

$$
S = F_{HAc} + F_{Ac}.
$$

Specifically,

$$
F_{HAc,t} = \frac{S}{1 + R_t},
\qquad
F_{Ac,t} = S - F_{HAc,t},
\qquad
F_{W,t} = F_W^{\mathrm{fixed}}.
$$

For the current default runner,

$$
S = 15~\mathrm{mL/min},
\qquad
F_W^{\mathrm{fixed}} = 5~\mathrm{mL/min}.
$$

The controlled output in the offline simulation is the simulated outlet pH.
The tracking target is `target_ph`. The logged tracking error is

$$
e^{\mathrm{log}}_t = \mathrm{pH}_t - \mathrm{pH}_{sp,t}.
$$

The reward function uses the opposite sign convention internally:

$$
e_t = \mathrm{pH}_{sp,t} - \mathrm{pH}_t.
$$

Both signs have the same absolute error and squared error. The report uses
`e_t = pH_sp,t - pH_t` in the reward section.

## RL State And Action

The environment observation has dimension 5:

$$
s_t =
\begin{bmatrix}
\mathrm{pH}_t \\
\mathrm{pH}_{sp,t} \\
\mathrm{pH}_t - \mathrm{pH}_{sp,t} \\
a^{\mathrm{ratio}}_t \\
t/T
\end{bmatrix}.
$$

The state components are:

| Index | State component | Meaning |
|---:|---|---|
| 0 | `current_ph` | current simulated pH |
| 1 | `target_ph` | current setpoint |
| 2 | `current_ph - target_ph` | signed pH tracking error |
| 3 | normalized ratio action | current acid/acetate log-ratio coordinate in `[-1, 1]` |
| 4 | step fraction | `step_count / max_episode_steps`, clipped at 1 |

The action has dimension 1:

$$
a_t =
\begin{bmatrix}
a^{\mathrm{ratio}}_t
\end{bmatrix},
\qquad
a^{\mathrm{ratio}}_t \in [-1,1].
$$

The action is clipped to `[-1, 1]` before it is mapped to physical flows.

## TD3 Agent Architecture

The current runner constructs a TD3 agent with:

| Item | Current default |
|---|---:|
| State dimension | 5 |
| Action dimension | 1 |
| Actor hidden layers | `[64, 64]` |
| Critic hidden layers | `[64, 64]` |
| Activation | ReLU |
| Actor output squash | tanh |
| Maximum action magnitude | 1.0 |
| Layer normalization | disabled |
| Dropout | 0.0 |

The actor network is

$$
\pi_\theta:
\mathbb{R}^{5}
\rightarrow
\mathbb{R}^{1}.
$$

With the default hidden layers, the actor structure is:

$$
5 \rightarrow 64 \rightarrow 64 \rightarrow 1,
$$

with ReLU activations on the hidden layers and a final tanh squash so that the
output lies in `[-1, 1]`. The final actor linear layer is initialized uniformly
in `[-1e-3, 1e-3]` for both weights and bias to reduce early saturation.

The critic is a twin-Q critic. Each Q-network takes the concatenated
state-action vector:

$$
\begin{bmatrix}
s_t \\
a_t
\end{bmatrix}
\in \mathbb{R}^{6}.
$$

Each critic branch has structure:

$$
6 \rightarrow 64 \rightarrow 64 \rightarrow 1.
$$

The critic returns two estimates:

$$
Q_{\phi_1}(s_t,a_t),
\qquad
Q_{\phi_2}(s_t,a_t).
$$

The TD3 target uses the minimum of the two target critics by default.

## TD3 Training Settings

The current default runner settings are:

| Parameter | Value |
|---|---:|
| Total rollout steps | 100000 |
| Default setpoint hold length | 200 steps |
| Default number of setpoint cycles | 500 |
| Batch size | 64 |
| Replay buffer capacity | 5000 |
| Discount factor `gamma` | 0.97 |
| Actor learning rate | 1e-4 |
| Critic learning rate | 1e-3 |
| Optimizer | AdamW |
| Critic loss | Huber |
| Gradient clip norm | 10.0 |
| Policy delay | 2 critic updates per actor update |
| Target update type | soft update |
| Soft update coefficient `tau` | 0.005 |
| Target policy smoothing noise std | 0.2 |
| Target policy smoothing noise clip | 0.5 |
| Target critic combine rule | min |
| Warm-start cycles | 0 |
| Evaluation cycle | final setpoint cycle |

The default exploration mode is Gaussian action noise:

| Exploration parameter | Value |
|---|---:|
| Initial standard deviation | 0.35 |
| Final standard deviation | 0.03 |
| Decay mode | linear |
| Decay steps | 5000 |
| Exponential decay rate option | 0.99 |

The replay buffer is a mixed prioritized/recent/uniform buffer:

| Replay parameter | Value |
|---|---:|
| Prioritized replay fraction | 0.5 |
| Recent replay fraction | 0.2 |
| Uniform replay fraction | 0.3 |
| Recent window | 1000 |
| Prioritization exponent `alpha` | 0.6 |
| Importance beta start | 0.4 |
| Importance beta end | 1.0 |
| Importance beta steps | 50000 |

## Reward Function

The current default reward mode in `run_offline_ph_td3_training.py` is
`relative_band_offset`. This reward starts from a relative-band shaped reward
and adds explicit absolute-error and late-hold offset penalties.

Let

$$
e_t = \mathrm{pH}_{sp,t} - \mathrm{pH}_t,
\qquad
|e_t| = \epsilon_t.
$$

The pH band is

$$
b_t =
\max(k_{rel}|\mathrm{pH}_{sp,t}|, b_{\min}, 10^{-12}).
$$

The current defaults use `k_rel = 0`, so

$$
b_t = b_{\min} = 0.02~\mathrm{pH}.
$$

The smooth inside-band weight is

$$
w^{in}_t =
\sigma\left(\frac{b_t - \epsilon_t}{\tau_t}\right),
\qquad
\tau_t = \tau_{frac} b_t,
$$

where `sigma(.)` is the logistic sigmoid. The normalized error is

$$
z_t = \frac{\epsilon_t}{b_t}.
$$

The main quadratic error term is

$$
J_{quad,t} = q_{band} e_t^2.
$$

The effective quadratic term is

$$
J_{eff,t}
=
(1-w^{in}_t)J_{quad,t}
+ w^{in}_t \lambda_{in}J_{quad,t}.
$$

Since the default `lambda_in` is 1, this currently reduces to
`J_eff,t = J_quad,t`, but the explicit form is kept for diagnostic consistency.

The move penalty is

$$
J_{\Delta u,t}
= r_{move}
\frac{1}{n_a}
\sum_{i=1}^{n_a}
(a_{t,i} - a_{t-1,i})^2.
$$

Here `n_a = 1`, because the agent has one action.

The linear outside-band and inside-band terms use the slope at the band edge:

$$
m_t = 2q_{band}b_t.
$$

The outside-band linear term is

$$
J_{lin,out,t}
=
(1-w^{in}_t)\gamma_{out}m_t
\,\max(\epsilon_t-b_t,0).
$$

The inside-band linear term is

$$
J_{lin,in,t}
=
w^{in}_t\gamma_{in}m_t
\,\min(\epsilon_t,b_t).
$$

The bonus term is

$$
J_{bonus,t}
=
w^{in}_t
\,\beta
\,q_{band}
\,b_t^2
f_{bonus}(z_t).
$$

For the default exponential bonus shape,

$$
f_{bonus}(z)
=
\frac{\exp(-k_{bonus}\bar{z})-\exp(-k_{bonus})}
{1-\exp(-k_{bonus})},
\qquad
\bar{z} = \mathrm{clip}(z,0,1).
$$

The late-hold offset activation is computed from the setpoint-hold progress
`p_t`:

$$
h_t =
\mathrm{clip}
\left(
\frac{p_t-p_{start}}{1-p_{start}},
0,
1
\right).
$$

The default reward is

$$
r_t =
-\alpha
\left[
J_{eff,t}
+J_{\Delta u,t}
+J_{lin,out,t}
+J_{lin,in,t}
-J_{bonus,t}
+w_{|e|}\epsilon_t
+w_{tail}h_t\epsilon_t
\right].
$$

The default reward parameters used by the runner are:

| Reward parameter | Value |
|---|---:|
| Reward mode | `relative_band_offset` |
| `q_band` | 1.0 |
| `r_move` | 0.01 |
| `b_min` or `band_floor_ph` | 0.02 |
| `k_rel` | 0.0 |
| `tau_frac` | 0.7 |
| `gamma_out` | 0.5 |
| `gamma_in` | 0.5 |
| `beta` or `reward_bonus_weight` | 25.0 |
| `lambda_in` | 1.0 |
| `bonus_kind` | `exp` |
| `bonus_k` | 12.0 |
| `reward_scale` or `alpha` | 1.0 |
| `w_abs` or `absolute_error_weight` | 1.0 |
| `w_tail` or `tail_offset_weight` | 5.0 |
| `p_start` or `tail_start_fraction` | 0.75 |
| `default_flow_weight` | 0.0 |

The older three-term reward is still available for ablation:

$$
r_t =
-\left(q_2e_t^2 + q_1|e_t|
+ r_{\Delta u}\frac{1}{n_a}\sum_{i=1}^{n_a}
(a_{t,i}-a_{t-1,i})^2
\right).
$$

It can be selected with:

```powershell
--reward-mode three_term
```

## Fixed Physical Parameters

| Parameter | Value | Notes |
|---|---:|---|
| `pKa` | 4.76 | acetic acid buffer pKa used by ideal HH model |
| `Kw` | 1e-14 | configured but not used by the ideal HH environment |
| `acid_stock_mol_l` | 0.1 mol/L | acetic acid stock concentration |
| `acetate_stock_mol_l` | 0.1 mol/L | sodium acetate stock concentration |
| `acid_flow_min` | 1.0 mL/min | pump lower bound |
| `acid_flow_max` | 10.0 mL/min | pump upper bound |
| `acetate_flow_min` | 1.0 mL/min | pump lower bound |
| `acetate_flow_max` | 10.0 mL/min | pump upper bound |
| `water_flow_min` | 1.0 mL/min | pump lower bound |
| `water_flow_max` | 10.0 mL/min | pump upper bound |
| `default_buffer_flow_sum` | 10.0 mL/min | process-config default, not the current TD3 runner fixed sum |
| `fixed_buffer_flow_sum` | 15.0 mL/min | `acid_flow + acetate_flow` |
| `fixed_water_flow` | 5.0 mL/min | current water stream value |
| nominal target range | 3.76 to 5.76 pH | general process target bounds |
| reachable fixed-sum target range | about 4.459 to 5.061 pH | due to fixed 15 mL/min buffer sum and 1-10 mL/min pump bounds |
| target tolerance | 0.02 pH | success flag threshold |

For the current fixed buffer-flow sum, the feasible acid flow range becomes:

$$
F_{HAc} \in [5,10]~\mathrm{mL/min},
$$

and the feasible acetate flow range also becomes:

$$
F_{Ac} \in [5,10]~\mathrm{mL/min}.
$$

Thus

$$
R_{\min} = \frac{5}{10}=0.5,
\qquad
R_{\max} = \frac{10}{5}=2.
$$

With `pKa = 4.76`, this gives

$$
\mathrm{pH}_{\min}
=4.76+\log_{10}(0.5)
\approx 4.459,
$$

and

$$
\mathrm{pH}_{\max}
=4.76+\log_{10}(2)
\approx 5.061.
$$

## Current Environment Variables And Logged Quantities

The environment logs the following quantities in `info` and in the saved
trajectory table:

| Logged variable | Meaning |
|---|---|
| `ph` | simulated current pH |
| `target_ph` | current pH setpoint |
| `ph_error` | `ph - target_ph` |
| `acid_flow` | current acetic acid flow |
| `acetate_flow` | current sodium acetate flow |
| `water_flow` | current water flow |
| `buffer_flow_sum` | `acid_flow + acetate_flow` |
| `flow_ratio_acetate_acid` | `acetate_flow / acid_flow` |
| `log10_flow_ratio_acetate_acid` | log flow ratio |
| `ratio_action` | normalized ratio action |
| `molar_base_acid_ratio` | ideal molar base/acid ratio |
| `success` | true when `abs(ph-target_ph) <= 0.02` |
| `step_count` | step count within environment episode |
| `setpoint_hold_step` | step count within current held setpoint |
| `setpoint_hold_progress` | normalized setpoint-hold progress |
| reward component columns | shaped reward diagnostics |

The runner additionally logs:

| Runner variable | Meaning |
|---|---|
| `cycle` | setpoint-hold segment index |
| `is_warm_start` | whether Henderson-Hasselbalch warm-start action was used |
| `is_test` | whether the step belongs to the final deterministic evaluation cycle |
| `action_source` | `td3_explore`, `td3_eval`, or `warm_start_hh` |
| `action_ratio` | raw TD3 normalized action used for the ratio |
| `exploration_sigma` | current Gaussian noise standard deviation |
| `exploration_magnitude` | mean absolute exploration noise |
| `action_saturation_fraction` | fraction of action dimensions at saturation |
| `critic_loss` | critic loss when a training update occurs |
| `actor_loss` | actor loss when a delayed actor update occurs |

## Scope And Limitations

This setup is useful for testing the offline RL scaffold and reward design
under a clean static chemical map. It is not yet a validated controller for the
lab system.

Important limitations:

- the environment is static and ideal,
- no transport delay is included,
- no mixing or residence-time dynamics are included,
- no pH sensor response model is included,
- no lab-data mismatch or calibration bias is included,
- water does not affect the ideal pH ratio directly in this model,
- final-cycle evaluation is only one held setpoint unless additional evaluation
  sweeps are added.

The next additions to this report should include generated figures from a full
100000-step run, per-setpoint average reward, last-five-setpoint tracking
diagnostics, and a frozen-policy evaluation sweep across the reachable pH
range.
