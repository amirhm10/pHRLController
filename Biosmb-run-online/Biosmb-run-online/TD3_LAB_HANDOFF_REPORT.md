# BioSMB custom TD3 online controller: lab handoff report

**Report date:** July 13, 2026  
**Software status:** custom TD3 integration completed and locally tested  
**Model status:** the bundled 500000-step checkpoint is the selected shipment default<br>
**Lab status:** live BioSMB control and online learning have not yet been validated

## 1. Purpose

This report explains how the original BioSMB online-control program was adapted
to use our custom Twin Delayed Deep Deterministic Policy Gradient (TD3) agent.
It focuses on [main.py](main.py): what was preserved, what was changed, why each
change was needed, and what the lab team should verify before active operation.

The integration is intended to preserve the BioSMB communication code already
used in the lab. The custom code supplies the state, TD3 action, reward, replay
buffer, gradient updates, and checkpoints around that existing communication
path.

## 2. Summary of the implementation

The former Stable-Baselines3 SAC model was replaced by our custom TD3 package.
The controller now:

1. reads `PH_2`, pump flows, and feed masses through the existing BioSMB and
   MFCS interfaces;
2. reads the desired pH from Redis, with `4.7` as the fallback;
3. builds the same five-value state used during offline TD3 training;
4. asks the custom actor for a two-value normalized action;
5. maps that action to acid, sodium acetate, and water flow commands;
6. validates the command before using the existing
   `BioSMBManager.set_flow(...)` calls;
7. waits for the 60-second control interval and reads the new process state;
8. calculates the aligned tracking, movement, and flow-economy reward;
9. stores the transition in a 10,000-transition replay buffer;
10. performs online TD3 updates after at least 64 transitions are available;
11. logs the process, reward, exploration, and training values to MongoDB; and
12. saves complete online-training checkpoints periodically and at shutdown.

The resulting control path is:

```text
BioSMB + MFCS measurements
          |
          v
observation and mass checks
          |
          v
five-value TD3 state --> custom TD3 actor + exploration
          |                         |
          |                         v
          |                normalized two-value action
          |                         |
          |                         v
          |                flow mapping and validation
          |                         |
          |                         v
          |             existing BioSMBManager.set_flow()
          |                         |
          v                         v
next state <-- 60-second wait and new measurements
          |
          v
reward --> replay buffer --> online TD3 update --> checkpoint
          |
          v
      MongoDB log
```

## 3. What was intentionally preserved

The integration does not replace the BioSMB control library. The following
parts retain the original lab-facing approach:

- `Redis` is used to read the experiment target.
- `MongoClient` is used for raw-observation and controller-step logging.
- `asyncua` is used to read the MFCS mass values and connect to the BioSMB OPC
  UA server.
- `BioSMBManager` is constructed from the existing
  [biosmb_interface](biosmb_interface) package and [settings.json](settings.json).
- Pump commands still pass through `BioSMBManager.set_flow(pump_number,
  flow_rate)`.
- `get_mfcs_data`, `get_biosmb_data`, `get_observation`, `apply_action`, and
  `stop_biosmb_safely` retain the reference program's BioSMB interaction
  pattern.
- The existing mass threshold remains `1200 g` for each monitored feed.
- A hard stop still tries to set all flows to zero and disable all pumps.

The reference `biosmb_interface` package and settings were compared with the
previous lab version. No intentional change was made to the library's OPC node
mapping or low-level pump behavior. TD3 changes the requested flow values, not
the mechanism used to send them.

## 4. What changed in `main.py` and why

Every intentionally edited area in [main.py](main.py) is marked with an
`# I changed this line:` comment.

| Area | Change | Reason |
|---|---|---|
| RL import | Replaced `stable_baselines3.SAC` with `BioSMBTD3Policy` and `BioSMBOnlineTD3Trainer` | Use our own TD3 inference and learning implementation without Stable-Baselines3 |
| Operating mode | Set `control_mode = "active_control"` | Allow validated controller outputs to be sent to the pumps |
| Online learning | Set `online_training_enabled = True` | Enable exploration, replay storage, critic updates, and delayed actor updates |
| Model loading | Load the actor description, weights, training checkpoint, and online settings from `models/` | Reconstruct the exact offline actor and continue training from its critics |
| Actor verification | Compare the trainable checkpoint actor with the deployment actor on saved test inputs | Prevent online learning from starting with mismatched model files |
| State construction | Build the exact five-value state used offline | Keep online inputs consistent with offline training |
| Action construction | Convert two TD3 outputs to the existing seven-pump action dictionary | Connect the custom action meaning to the reference BioSMB command format |
| Flow bounds | Use acid and acetate bounds of `1-10 mL/min`, buffer sum `2-20 mL/min`, water `5 mL/min`, and total flow at most `25 mL/min` | Match the offline TD3 environment and physical command checks |
| Exploration | Start online Gaussian action noise at `0.02` and reduce it to `0.01` over 5,000 actions | Continue from the final offline noise level while gradually reducing random variation |
| Reward | Calculate the same `relative_band_offset` shaped reward and optional-flow cost used offline | Train online with the intended tracking, flow-movement, and economic objective |
| Replay and updates | Use capacity `10,000`, batch size `64`, recent window `200`, and one requested update per completed transition | Keep 20% of each batch focused on approximately the latest 3 hours 20 minutes while retaining prioritized and uniform history |
| Water readback | Use a tolerance of `0.1 mL/min`; warn and log if measured water differs from `5 mL/min` | Allow realistic pump readback variation without stopping only because of the water deviation |
| Logging | Add state, next state, reward breakdown, exploration, replay, loss, measured action, and water-warning fields | Make each online transition and update auditable |
| Checkpoints | Save every 10 completed steps and in the final shutdown block | Preserve the learned online state and allow a later run to resume |
| Startup | Load and verify both the deployment actor and online learner before entering the existing OPC/Mongo control context | Fail before issuing commands if model files are missing or inconsistent |

## 5. Mathematical interpretation

### 5.1 TD3 state

At control step `t`, the actor receives

$$
s_t =
\begin{bmatrix}
\mathrm{pH}_t,
\mathrm{pH}^{*}_t,
\mathrm{pH}_t-\mathrm{pH}^{*}_t,
a^{\mathrm{ratio}}_{t-1},
a^{\mathrm{flow}}_{t-1}
\end{bmatrix}.
$$

Here, `PH_2` supplies $\mathrm{pH}_t$, Redis normally supplies the target
$\mathrm{pH}^{*}_t$, and the last two values are reconstructed from measured
pump flows when flow readback is available.

For the actor currently in `models/`, the target must remain in the saved range
$3.76 \leq \mathrm{pH}^{*} \leq 5.70$. The measured pH and complete state must
also remain within the bounds stored in `td3_actor_manifest.json`. The program
rejects an out-of-range state instead of silently clipping it.

### 5.2 TD3 action and physical flows

The actor returns

$$
a_t =
\begin{bmatrix}
a^{\mathrm{ratio}}_t,
a^{\mathrm{flow}}_t
\end{bmatrix},
\qquad a_t \in [-1,1]^2.
$$

The new mapping chooses the chemical ratio first. With
$\rho_t=F_{B,t}/F_{A,t}$, its global bounds are
$\rho_{\min}=F_{B,\min}/F_{A,\max}=0.1$ and
$\rho_{\max}=F_{B,\max}/F_{A,\min}=10$. Therefore,

$$
u_t=\frac{a^{\mathrm{ratio}}_t+1}{2},
\qquad
\rho_t=10^{\log_{10}\rho_{\min}
+u_t(\log_{10}\rho_{\max}-\log_{10}\rho_{\min})}.
$$

For that selected ratio, the feasible acid-plus-acetate total $S_t$ is
recalculated:

$$
S_{\min}(\rho_t)=\max\left(
2,\ F_{A,\min}(1+\rho_t),\
\frac{F_{B,\min}(1+\rho_t)}{\rho_t}
\right),
$$

$$
S_{\max}(\rho_t)=\min\left(
20,\ F_{A,\max}(1+\rho_t),\
\frac{F_{B,\max}(1+\rho_t)}{\rho_t}
\right).
$$

The second actor output selects only a fraction inside this feasible interval:

$$
v_t=\frac{a^{\mathrm{flow}}_t+1}{2},
\qquad
S_t=S_{\min}(\rho_t)+v_t\left(S_{\max}(\rho_t)-S_{\min}(\rho_t)\right),
$$

$$
F_{A,t}=\frac{S_t}{1+\rho_t},
\qquad
F_{B,t}=\rho_t F_{A,t}.
$$

Here, $F_A$ is acetic-acid flow and $F_B$ is sodium-acetate flow, both in
`mL/min`. Choosing the ratio before total flow preserves access to the full
feasible ratio range. The second action can then reduce reagent use without
changing that ratio. Both buffer streams remain between `1` and `10 mL/min`,
their sum remains between `2` and `20 mL/min`, and water is commanded at
$F_W=5\ \mathrm{mL/min}$.

### 5.3 Online transition and TD3 update

After the 60-second decision interval, one transition is stored:

$$
(s_t, a_t, r_t, s_{t+1}, d_t),
$$

with `done = False` during normal continuous operation. The active reward can
be summarized as

$$
r_t = -\left(C_{\mathrm{pH},t}
+ C_{\lvert e\rvert,t}
+ 5\left(\frac{F_{A,t}+F_{B,t}-F_{A,t-1}-F_{B,t-1}}{20-2}\right)^2
+ 0.01v_t^2
- B_t\right),
$$

where $e_t=\mathrm{pH}^{*}_t-\mathrm{pH}_{t+1}$,
$C_{\mathrm{pH},t}$ is the smooth relative-band tracking cost,
$C_{\lvert e\rvert,t}=|e_t|$, $0.01v_t^2$ discourages unnecessarily high
acid-plus-acetate flow within the ratio-specific feasible interval, and $B_t$
is a small near-target bonus. The exact calculation and all logged components are in
[custom_td3/reward.py](custom_td3/reward.py). The same scalar reward is stored
in replay and MongoDB.

TD3 uses two critics and the smaller target value:

$$
y_t = r_t + \gamma(1-d_t)
\min_{i\in\{1,2\}} Q_{i,\mathrm{target}}
\left(s_{t+1},\pi_{\mathrm{target}}(s_{t+1})+\epsilon\right).
$$

Critics are updated from replay batches; the actor is updated at the configured
delayed frequency. With one new transition per 60-second interval and batch
size `64`, the first gradient update occurs only after 64 completed transitions,
approximately 64 minutes after warm-up.

## 6. Step-by-step runtime behavior

### Startup

1. The script creates the Redis client.
2. The deployment actor is loaded from `td3_actor_manifest.json` and the
   weights-only `.pt` file.
3. The weights hash, architecture, state/action contract, and saved test cases
   are checked.
4. The trainable TD3 agent is loaded from the trusted offline `.pkl`
   checkpoint.
5. The trainable actor is required to match the deployment actor.
6. MongoDB and BioSMB OPC connections are opened.
7. `BioSMBManager` is created using the existing `settings.json`.
8. The program performs a 60-second observation and mass-safety warm-up.

No active control step begins if model loading or actor matching fails.

### Each control step

1. Read the target pH from Redis; use `4.7` if Redis does not provide it.
2. Read `PH_2`, all flow readbacks, and all monitored masses.
3. Stop on invalid required measurements or unsafe mass.
4. Build the five-value state.
5. Add the scheduled online exploration noise to the actor action.
6. Convert the normalized action into physical flows.
7. Validate dimensions, finite values, normalized bounds, individual flow
   bounds, buffer-flow sum, water command, and total flow.
8. If the proposed action is invalid, repeat the previous validated command.
9. Send pumps 1, 2, and 3 through the existing `BioSMBManager.set_flow` calls.
10. Observe the system once per second for 60 seconds and repeat the mass and
    observation checks.
11. Reconstruct the normalized action represented by the measured flow
    readback.
12. Warn and log if measured water differs from `5 mL/min` by more than
    `0.1 mL/min`; this water deviation alone does not stop the process.
13. Build the next state and calculate the reward.
14. Store the transition and request one TD3 update.
15. Log the full step to MongoDB.
16. Save a full checkpoint every 10 completed steps.

### Shutdown

On `Ctrl+C`, a safety exception, or an unhandled exception, the active-control
path attempts to zero all flows and disable all pumps. The `finally` block then
attempts to save a final online TD3 checkpoint. Docker is configured to send
`SIGINT` and wait 30 seconds so Python can enter this shutdown path.

## 7. Safety behavior

### Conditions that stop or reject operation

- Missing or non-finite `PH_2` stops the active run through the exception path.
- Missing, non-finite, or below-threshold feed mass triggers a safety shutdown.
- An invalid proposed TD3 command is not sent; the previous validated command
  is repeated.
- Invalid measured flow dimensions, non-finite values, negative values,
  individual controlled flows outside `1-10 mL/min`, buffer sum outside
  `2-20 mL/min`, or total controlled flow above `25 mL/min` triggers shutdown.
- A state outside the actor's saved operating bounds stops inference rather
  than being extrapolated silently.

### Condition changed to warning only

The water command remains fixed at `5 mL/min`. A measured water-flow deviation
greater than `0.1 mL/min` now prints a warning and is written to MongoDB. It
does not, by itself, stop control because pump readback may not exactly equal
the command.

This exception applies only to imperfect measured water readback. Other action,
flow, observation, and mass checks remain active.

## 8. Logging and checkpoint evidence

Raw observations continue to use the MongoDB collection
`biosmb-inline-mixing`. Controller steps use
`biosmb-rl-controller-deployment`.

Each controller-step record now includes:

- target pH and `PH_2` before and after the action;
- proposed, executed, previous, and measured actions;
- current state and next state;
- action validation result and fallback reason;
- water warning status, measured deviation, and tolerance;
- scalar reward and the full reward breakdown;
- exploration standard deviation, magnitude, saturation, and action number;
- replay size, batch size, update count, critic loss, actor-update status, and
  actor loss;
- mass-safety result;
- raw observations before and after the action; and
- controller, model, and checkpoint paths.

The console also prints the current target, pH, executed streams, reward, and
replay size. [dockerfile](dockerfile) enables unbuffered Python output so these
messages appear promptly in Docker logs.

Online checkpoints are written below `models/online_checkpoints/`. New online
checkpoints contain actor and critic networks, target networks, optimizers,
replay contents, counters, and random-number states. Only trusted local `.pkl`
files should ever be loaded because Python pickle is not safe for untrusted
input.

Each 64-transition training batch contains 32 prioritized samples, 12 recent
samples, and 20 uniform samples. The recent pool is limited to the newest 200
transitions after that many observations exist. With one transition per minute,
this corresponds to approximately 3 hours 20 minutes of recent operation.

## 9. Selected shipment model

The four matching files currently in `models/` are the model set selected for
the lab shipment. `main.py` already loads these filenames by default.

| Setting | Selected value |
|---|---:|
| Source run | `offline_ph_td3_training_20260713_204554` |
| Total offline steps | `500000` |
| Action mapping | `ratio_preserving_flow_v1` |
| Actor hidden layers | `[64, 64]` |
| Critic hidden layers | `[64, 64]` |
| Discount factor $\gamma$ | `0.99` |
| Offline batch size | `64` |
| Final offline exploration noise | `0.02` |
| Flow-economy reward weight | `0.01` |
| Policy ID | `custom_td3_687131b557875010` |

The selected matched set is:

```text
td3_actor_manifest.json
td3_actor_weights.pt
td3_training_checkpoint.pkl
td3_training_config.json
```

Their SHA-256 values are recorded in [models/README.md](models/README.md) and
were rechecked during the final handoff audit. Do not replace or mix these files
before shipment. The startup actor-matching check is designed to catch an
inconsistent actor and training checkpoint.

The saved deterministic 25-target simulation grid for this checkpoint has pH
MAE `0.011105`, RMSE `0.013258`, maximum absolute error `0.032116`, and `92%`
of targets within `0.02` pH. Its mean acid-plus-acetate flow is
`10.184659 mL/min`.

This newest checkpoint was selected at the user's direction, but it was not the
best checkpoint in the direct frozen-grid comparison. The preceding
`offline_ph_td3_training_20260713_191125` checkpoint (`[128, 128]`,
$\gamma=0.97$) achieved MAE `0.005471`, maximum absolute error `0.017666`, and
mean acid-plus-acetate flow `5.015525 mL/min` on the same grid. The current
selection must therefore be treated as a requested latest-run selection, not as
evidence of superior performance. Neither checkpoint has live-lab validation.

## 10. Docker and dependency status

The container configuration remains close to the earlier setup:

- `restart: unless-stopped` was intentionally retained;
- the existing `models`, `logs`, and `main.py` volumes were retained;
- [docker-compose.yml](docker-compose.yml) now explicitly selects the lowercase
  `dockerfile`, forwards `SIGINT`, uses Docker's small init process, and allows
  a 30-second shutdown period;
- [dockerfile](dockerfile) now uses unbuffered Python output and runs
  `pip check` during the build; and
- [.dockerignore](.dockerignore) excludes Python caches, logs, and generated
  online checkpoints while retaining the selected offline model files.

[requirements.txt](requirements.txt) now contains only the direct runtime
packages imported by the BioSMB program. Stable-Baselines3 is not installed
because the online controller uses only the custom TD3 package. The Docker build
installs CPU-only PyTorch `2.8.0`, matching the selected checkpoint's PyTorch
release, and NumPy `2.3.1`, matching the saved actor information. Python
`3.11-slim` is retained from the reference container. Actor hashes and saved
inference cases are checked at startup to detect an incompatible runtime.

Because `restart: unless-stopped` is retained, Docker may restart the container
after an internal process exit. The lab team should account for this behavior
during supervised commissioning.

The named `models` volume is populated from the image only when that Docker
volume is first created. On a computer with an existing `models` volume, verify
its four model files and hashes before starting because an older volume can hide
the selected files stored in the image.

## 11. Verification evidence

### Files inspected

- [main.py](main.py)
- [custom_td3](custom_td3) implementation and its
  [README](custom_td3/README.md)
- [models](models) files and [model README](models/README.md)
- [docker-compose.yml](docker-compose.yml)
- [dockerfile](dockerfile)
- [requirements.txt](requirements.txt)
- [settings.json](settings.json)
- the local reference BioSMB program and interface package used for comparison

### Tests completed

The complete local test suite completed with `50 passed`, including offline TD3
behavior, BioSMB TD3 fidelity, model loading, refined state/action conversion,
reward parity, replay updates, checkpointing, and additive integration checks.

A model-only preflight successfully:

- loaded the current actor;
- verified its saved inference cases;
- loaded the online learner;
- verified deployment/training actor equality; and
- confirmed the 500000-step source, `[64, 64]` networks, `gamma = 0.99`, batch
  size `64`, replay capacity `10000`, recent window `200`, and online noise
  `0.02 -> 0.01`.

The current actor identifies itself as
`custom_td3_687131b557875010`.

The final audit also confirmed that the current `biosmb_interface` modules,
`settings.json`, and the five lab-interaction functions in `main.py` are
structurally identical to the Desktop reference. A Linux Python 3.11 dependency
dry-run resolved every runtime package and the official CPU-only PyTorch 2.8.0
wheel without installing them.

### Evidence not yet available

- No live OPC UA, Redis, MongoDB, MFCS, or pump connection was available during
  local testing.
- Docker was not available on the development computer, so the image has not
  been built there.
- No plots or lab performance data are included because this report documents
  software integration, not a completed physical control experiment.

## 12. Main result interpretation

The custom TD3 software path is connected end to end: a BioSMB observation can
be converted to the offline-trained state, the actor action can be converted to
the existing pump-command structure, and a completed control transition can be
rewarded, stored, learned from, logged, and checkpointed.

This is evidence that the software components agree with each other. It is not
evidence that the controller is safe or effective on the physical process. The
starting actor was trained in simulation and the current actor file explicitly
states that it was not lab validated when exported.

## 13. Bugs, inconsistencies, and operational risks

The following items should remain visible during handoff:

1. The selected model was trained in simulation and has not been validated on
   the physical BioSMB process.
2. The simulation used for offline training does not fully represent real
   mixing delay, residence-time behavior, sensor response, pump error, or
   disturbances.
3. Pump indices must be physically confirmed as pump 1 acid, pump 2 sodium
   acetate, and pump 3 Arium water.
4. The team should confirm whether the `FLOW` values returned by the BioSMB
   library represent measured flow, commanded flow, or another internal value.
5. The 60-second decision interval and reward timing have not been validated
   against the real process dynamics.
6. Online exploration from `0.02` to `0.01` is intentionally small but has not
   yet been shown safe on the lab system.
7. The first online gradient update needs 64 completed transitions, so a short
   test will exercise inference and replay storage but not learning.
8. The MongoDB connection string currently contains a plaintext credential in
   `main.py`; it should eventually be supplied through protected deployment
   settings.
9. The inherited exception structure may attempt a second pump stop after the
   OPC context begins closing. The code was kept close to the working reference,
   but shutdown must be tested while connected.
10. `restart: unless-stopped` can restart the process after a safety-related
    exit.
11. Full training checkpoints are pickle files and must be treated as trusted
    internal artifacts only.
12. `suggest_only` must be paired with `online_training_enabled = False`.
    Otherwise, the program would store the suggested action as though it had
    been applied, creating an incorrect online-training transition.
13. An existing Docker `models` volume can hide the selected model files from
    the newly built image. Its contents and hashes must be checked before use.
14. The selected checkpoint was exported with Python `3.13.7`, while the
    reference Docker base remains Python `3.11`. The model loads locally and
    dependency resolution passes, but the final container preflight still must
    be run after Docker is available.

No literature comparison was needed for this software handoff. The controller's
scientific performance should be assessed from supervised lab data rather than
from code inspection alone.

## 14. Recommended next experiment: supervised commissioning

The next experiment should be a staged, supervised lab commissioning run:

1. Keep the selected four model files together and verify their source
   information and hashes.
2. Run the complete local tests using the shipment files.
3. Run `docker compose config`, build the image, and confirm `pip check` passes.
4. Load the actor and online trainer inside the built container and confirm the
   policy ID, `gamma`, network sizes, replay settings, and saved inference cases.
5. Confirm Redis, MongoDB, MFCS, and BioSMB OPC connectivity without sending an
   RL command.
6. Confirm the three physical pump mappings and the meaning of flow readback.
7. Confirm `PH_2`, mass-node values, engineering units, target range, and
   shutdown commands.
8. Begin with `control_mode = "suggest_only"` and
   `online_training_enabled = False` under operator supervision. Compare the
   suggested flows against expected safe values. Disabling learning is
   required because a suggested action is not physically applied and therefore
   must not be stored as the cause of the next measurement.
9. Perform a manual Docker stop test and verify zero flows, disabled pumps, a
    final checkpoint, and clean logs.
10. Enable active control only after the above checks pass. Start with a fixed
    in-range target and closely monitor pH, actions, water warnings, masses, and
    MongoDB records.
11. Use a run shorter than 64 control transitions if the first objective is to
    validate deployment without any gradient update. A later approved run can
    explicitly test online learning.

## 15. Lab sign-off checklist

| Check | Result / initials |
|---|---|
| Selected four-file model set present and hashes verified | |
| Model source and hashes reviewed | |
| Python, NumPy, and Torch versions reconciled | |
| Docker configuration and image build passed | |
| Redis target key confirmed | |
| Target constrained to the model's saved range | |
| MongoDB collections and access confirmed | |
| `PH_2` sensor confirmed | |
| Pump 1 = acetic acid confirmed | |
| Pump 2 = sodium acetate confirmed | |
| Pump 3 = Arium water confirmed | |
| Flow-readback meaning confirmed | |
| MFCS mass nodes and `1200 g` limit confirmed | |
| Zero-flow and pump-disable behavior tested | |
| Docker stop and final checkpoint tested | |
| Suggest-only review passed | |
| Active-control test authorized and supervised | |
| Online-learning test separately authorized | |

## 16. Remaining uncertainty

The main remaining uncertainty is physical rather than structural: whether the
simulation-trained policy, reward timing, state definition, and 60-second action
interval match the real system closely enough for stable control and useful
online adaptation. That question can only be answered through the staged lab
commissioning and logged data review described above.
