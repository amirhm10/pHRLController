# BioSMB custom TD3 active-path integration report

**Date:** 2026-07-12

**Status:** software integration completed in `suggest_only`. Online updates and
exploratory hardware actions remain disabled.

## 1. Objective

This step replaces the historical Stable-Baselines3 SAC artifacts with the
latest custom TD3 artifacts, connects the frozen custom actor to the original
BioSMB loop through the minimum policy-specific call sites, and adds only the
TD3 learning code active in the latest offline run.

The Redis, MongoDB, OPC-UA, BioSMB manager, observation acquisition, mass
checks, action checks, pump application, logging, and shutdown structure remain
owned by the supplied BioSMB application.

## 2. Deployment-setting classification

| Setting group | Examples | Meaning | Decision |
|---|---|---|---|
| BioSMB infrastructure | OPC-UA URLs, Redis URL/key, Mongo URL/collections, `settings.json`, MFCS nodes | Laboratory communication and data routing | Kept |
| Physical mapping | controlled pump indices and stream names | Maps logical acid, acetate, and water to pumps | Kept but still requires physical verification |
| Controller timing | warmup, decision interval, fixed or Redis target | Defines the deployment experiment | Kept |
| Generic safety | individual flow limits, total-flow limit, minimum masses | Applies independently of SAC or TD3 | Kept, with total-flow cap tightened to 25 mL/min |
| TD3 contract | `PH_2`, manifest path, normalized ratio/sum state and action mapping | Must match the trained actor | Connected through `BioSMBTD3Policy` |
| Historical SAC | two `sac_*` model paths and `SAC.load()` | Specific to the supplied SB3 example | Removed |

The deployment target of 4.7 pH lies inside the saved manifest target interval
of 3.76 to 5.70. The latest actor remains simulation-only, so the main setting
is `suggest_only`.

Every changed area in `main.py` has a nearby comment beginning with
`# I cnaged this line:` as requested.

## 3. Model artifacts

The historical files were removed from the online `models/` folder:

```text
sac_biosmb_mixing_online_checkpoint.zip
sac_biosmb_mixing_online_checkpoint_replay_buffer.pkl
```

They were replaced with exact copies from:

```text
results/offline_ph_td3_training_20260710_183129/
```

The online model folder now contains:

```text
td3_actor_manifest.json
td3_actor_weights.pt
td3_training_checkpoint.pkl
td3_training_config.json
td3_online_training_config.json
```

The deployment actor SHA-256 is:

```text
0c10ce7b8602bd5c455f74009e233ecc990735a3f73c76b2c99a196d23f91777
```

The `.pt` file and manifest are used for deterministic deployment. The trusted
local `.pkl` contains actor and critic weights for future training work.

## 4. Active TD3 implementation

Only the latest run's active algorithm is retained in `custom_td3`:

- ReLU actor and twin critics with hidden layers `[128, 128]`
- one-step TD3
- Huber twin-critic loss
- minimum twin target
- delayed actor update every two critic updates
- target-policy smoothing with standard deviation 0.2 and clip 0.5
- soft target update with coefficient 0.005
- AdamW actor and critic optimizers
- gradient norm clipping at 10
- mixed prioritized, recent, and uniform replay
- Gaussian action exploration
- the active `relative_band_offset` pH reward

The following inactive paths were intentionally not transferred:

- n-step accumulation
- lambda-return targets
- sequence replay sampling
- parameter noise
- behavioral cloning
- hard target updates
- alternative target-combination modes
- alternative critic losses
- plain uniform replay class
- inactive reward modes
- the simulation Gym environment and Henderson-Hasselbalch transition model

## 5. Mathematical contract

The online state is

$$
s_t =
\begin{bmatrix}
PH_{2,t} & PH_{sp,t} & PH_{2,t}-PH_{sp,t} &
a^{\rho}_{t-1} & a^{S}_{t-1}
\end{bmatrix}^{T}.
$$

The actor produces

$$
a_t = \begin{bmatrix}a^{\rho}_t & a^{S}_t\end{bmatrix}^{T},
\qquad a_t \in [-1,1]^2.
$$

The buffer-flow sum is

$$
S_t = 2 + \frac{a^S_t+1}{2}(20-2).
$$

The ratio coordinate is interpolated in the feasible log acetate-to-acid
ratio interval. The physical flows then satisfy

$$
F_H = \frac{S_t}{1+\rho_t},
\qquad F_A = S_t-F_H,
\qquad F_W = 5\ \mathrm{mL/min}.
$$

The one-step TD3 target retained for future training is

$$
y_t = r_t + \gamma(1-d_t)
\min_{i\in\{1,2\}}Q_{\bar\phi_i}
\left(s_{t+1},\mathrm{clip}(\pi_{\bar\theta}(s_{t+1})+\epsilon)\right),
$$

where $\gamma=0.97$, $\epsilon$ is Gaussian target smoothing noise with
standard deviation 0.2, and the noise is clipped to 0.5.

## 6. Replay and reward

The active replay batch consists of 50 percent prioritized samples, 20 percent
recent samples, and 30 percent uniform samples. The recent window is 1000
transitions. The implementation preserves the original behavior in which
importance weights correct only the prioritized subset.

The active reward is the same `relative_band_offset` reward used by the saved
offline run. Its configured nonzero terms include the pH error cost, normalized
buffer-sum movement penalty with weight 5, and absolute pH error penalty with
weight 1. The near-zero exponential bonus has weight 0.05 and sharpness 6.

For future online transitions, reward must use measured `PH_2` after the hold
interval and the action actually executed by the safety logic. It must not use
a rejected raw actor proposal.

## 7. Online exploration continuation

The offline run used Gaussian exploration that decayed from 0.35 to 0.02. The
separate online configuration therefore starts at 0.02 and decays to 0.01:

$$
\sigma_{online}(k)
= 0.02 + (0.01-0.02)
\min\left(1,\frac{k}{5000}\right).
$$

This preserves continuity at the offline-to-online boundary. It does not by
itself establish that a 0.02 normalized perturbation is safe for the laboratory.
The online config explicitly keeps both online updates and exploratory actions
disabled until those behaviors are reviewed.

## 8. Main-file integration

The original loop now changes only the necessary policy seams:

1. Load `BioSMBTD3Policy` from the local package.
2. Load and verify `models/td3_actor_manifest.json`.
3. Use the TD3 startup action representation.
4. Build the exact trained five-element state.
5. Predict the two normalized TD3 coordinates.
6. Map them to the original BioSMB action dictionary.
7. Log the TD3 manifest path.

The old helper definitions remain in the supplied main file for traceability,
but their SAC-specific call sites are no longer used.

## 9. Verification evidence

Twenty hardware-free tests pass. They verify:

- deployment actor hash and golden vectors
- actor output parity between the `.pkl` checkpoint and `.pt` deployment file
- exact state order and error sign
- action mapping parity against the training environment
- original BioSMB action-dictionary compatibility
- active reward numerical parity against the original reward implementation
- four consecutive active one-step TD3 updates numerically matching the original agent
- online exploration endpoints of 0.02 and 0.01
- exact copies of the latest saved artifacts
- absence of the historical SAC artifacts
- absence of n-step, lambda-return, sequence, and other inactive modules

No OPC-UA, Redis, MongoDB, or pump connection is opened by these tests.

## 10. Limitations and risks

The actor inference path is reproducible. Exact training resume is not. The
existing offline `.pkl` does not restore replay contents, optimizer states,
target-network states through its loader, counters, or random-number states.
Future online learning therefore starts with the pretrained actor and critic
but a new replay history and new optimizers.

Other unresolved risks are:

- the actor was trained on an instantaneous ideal pH simulator
- laboratory delay, mixing, and PH_2 sensor dynamics are not represented
- pump indices still require physical confirmation
- 60-second discount and reward semantics have not been validated
- online terminal behavior for faults and operator stops is not defined
- in `suggest_only`, the original loop still labels the selected proposal as
  `executed_action` even though `apply_action()` performs no pump write
- the current main file contains a plaintext database credential

## 11. Recommended next step

Keep `suggest_only` and review the modified main call sites together. The next
implementation step should be a separate online-transition collector that logs
validated current state, candidate action, executed action, next measured
state, reward components, and terminal reason without calling `train_step()`.

Only after those logged transitions are scientifically reviewed should the
online replay push and TD3 update cadence be enabled.
