# BioSMB custom TD3 active-path integration report

**Date:** 2026-07-12

**Status:** `active_control` and `online_training_enabled` are selected. The
online action-noise, shaped-reward, replay, TD3-update, logging, periodic-save,
and final-save paths are now connected to `main.py`.

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

The deployment target of 4.7 pH lies inside the saved model target interval of
3.76 to 5.70. The latest actor remains simulation-only. The user selected
`active_control` for the planned online-training workflow, so this incomplete
intermediate version must not be run on the lab system yet.

Every changed area in `main.py` has a nearby comment beginning with
`# I changed this line:` as requested.

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

For each completed online transition, reward now uses measured `PH_2` after the
hold interval and the action actually executed by the safety logic. A rejected
raw actor proposal is not placed in replay as the executed action.

The online batch size is `64`, replay capacity is `10000`, and one TD3 update is
requested per completed control transition. Learning begins when replay reaches
64 transitions. The exact scalar stored in replay is also logged as `reward` in
MongoDB, with all shaped-reward components under `reward_info`.

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
At the user's direction, online updates and exploratory actions are now active
in the configuration and deployment loop.

## 8. Main-file integration

The original loop now changes the necessary policy and training seams:

1. Load `BioSMBTD3Policy` from the local package.
2. Load and verify `models/td3_actor_manifest.json`.
3. Use the TD3 startup action representation.
4. Build the exact trained five-element state.
5. Load the matching pretrained actor and critic into the active TD3 agent.
6. Predict the two normalized TD3 coordinates with online exploration.
7. Map them to the original BioSMB action dictionary.
8. Compute the exact shaped reward from the completed transition.
9. Store the executed action and reward in the 10000-transition replay buffer.
10. Run one TD3 update after replay contains 64 transitions.
11. Log reward, exploration, replay, and loss diagnostics.
12. Save complete online-resume checkpoints every 10 steps and at exit.

The old helper definitions remain in the supplied main file for traceability,
but their SAC-specific call sites are no longer used.

## 9. Verification evidence

The earlier 22 hardware-free deployment tests verified:

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
- measured-flow round-trip back to the normalized TD3 action
- rejection of wrong water flow and malformed TD3 actions

The active online-path test additionally verifies:

- offline training-checkpoint actor parity with the deployed actor
- batch size `64` and replay capacity `10000`
- exploration inside the configured `0.02` to `0.01` range
- shaped reward calculation and finite replay storage
- the first real critic and actor update at transition 64
- complete checkpoint save and restoration of replay, optimizer, counter, and
  random states
- equality between the logged reward and the reward stored for training

No OPC-UA, Redis, MongoDB, or pump connection is opened by these tests.

## 10. Limitations and risks

The actor inference path is reproducible. The existing offline `.pkl` starts
online learning with the pretrained actor and critic but a new replay history
and new optimizers. New online checkpoints save and restore the actor, critics,
target networks, optimizers, replay contents, counters, and random states.

Other unresolved risks are:

- the actor was trained on an instantaneous ideal pH simulator
- laboratory delay, mixing, and PH_2 sensor dynamics are not represented
- pump indices still require physical confirmation
- 60-second discount and reward semantics have not been validated
- online terminal behavior for faults and operator stops is not defined
- immediate command-versus-flow readback behavior is still not verified
- the current main file contains a plaintext database credential

## 11. Recommended next step

Before an unattended run, execute a supervised short session and review the
logged reward, pH response, exploration magnitude, action saturation, replay
growth, critic loss, and actor updates. Confirm the physical pump mapping and
whether the BioSMB `FLOW` node is actual flow measurement or command readback.

## 12. Data collection and target review

No code was changed in these two sections during the active-mode setting edit.

The Data collection section remains the starting structure because it already
reads BioSMB sensors, seven flow values, three MFCS masses, and logs the raw
observation. During active online development, it should still add:

- timezone-aware measurement times
- command time and before/after measurement times
- flow-array shape and finite-value validation
- confirmation that flow values are measured readback rather than commands
- stale-data, timeout, and OPC quality checks

The Target pH section can also keep its Redis-first and fixed-target fallback
structure. During active online development, it should still add:

- finite numeric validation
- enforcement of the saved model range, currently 3.76 to 5.70 pH
- target freshness and a minimum target hold time
- logging of whether Redis or the fixed fallback supplied the target

An invalid target should be rejected or replaced by the reviewed fallback. It
should not reach the actor and fail indirectly during state validation.

## 13. State and action cleanup

The unused SAC state builder, SAC default action, and three-direct-flow action
converter were removed from `main.py`. State creation and action conversion now
have one TD3 path only.

After every decision interval, the loop now:

1. converts measured acid, acetate, and water flows back to the two normalized
   TD3 action values
2. checks the normalized values, individual flows, buffer-flow sum, fixed water,
   seven-pump mapping, and reported total
3. builds `next_state` from the new PH2 measurement and measured flows
4. logs `state`, `next_state`, the proposed action, the selected command, and
   the measured action
5. keeps the last validated command as the fallback command for the following
   step
6. computes and logs reward and online-training diagnostics

The checked TD3 command rules are acid and acetate from 1 to 10 mL/min, their
sum from 2 to 20 mL/min, water commanded at 5 mL/min within 0.1 mL/min, and
total controlled flow no greater than 25 mL/min. A measured water deviation
outside 0.1 mL/min is logged as a warning rather than used alone to stop the
process.
