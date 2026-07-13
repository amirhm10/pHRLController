# Custom TD3 integration into the BioSMB online reference

> **Superseded implementation note, 2026-07-12:** The large replacement of the
> original BioSMB `main.py` and container files documented below was reverted.
> The original reference application is restored, and the current TD3 work is
> additive under `Biosmb-run-online/Biosmb-run-online/custom_td3/`. See
> `reports/biosmb_additive_td3_module_report.md` for the current design.

**Date:** 2026-07-10

**Implementation status:** actor-only runtime implemented and verified without hardware

**Default operating mode:** `suggest_only` (zero BioSMB writes)
**Active-control status:** intentionally blocked pending a validated dynamic lab model, an approved actor, and physical commissioning

## 1. Objective

The two imported BioSMB folders are reference examples for connecting research code to the laboratory infrastructure:

- `Biosmb-interact` demonstrates direct interaction with the BioSMB and related services.
- `Biosmb-run-online` demonstrates how an RL policy can receive live observations, produce actions, log an experiment, and communicate with the BioSMB.

The original online example loaded a Stable-Baselines3 SAC model. The implementation in this work replaces that policy path with the repository's custom PyTorch TD3 actor while preserving the useful laboratory interfaces.

This is a deployment implementation, not an authorization to close the loop on the real process. The latest custom TD3 study was trained against an ideal static Henderson-Hasselbalch simulation, and the existing 500,000-step result did not save a checkpoint. A newly trained and scientifically approved actor is therefore still required.

## 2. What changed conceptually

The original example treated the RL policy as a three-flow Stable-Baselines3 SAC policy. The custom TD3 agent has a different contract:

| Contract item | Original online SAC example | Custom pH TD3 implementation |
|---|---|---|
| RL library | Stable-Baselines3 | Repository-owned PyTorch actor |
| State dimension | 5 | 5 |
| State meaning | pH, target, and three previous physical flows | pH, target, error, previous normalized ratio, previous normalized buffer sum |
| Action dimension | 3 | 2 |
| Action meaning | three direct physical flow values | normalized acetate/acid ratio and normalized acid-plus-acetate sum |
| Water action | learned/direct | fixed by the training contract |
| Online training | not required | prohibited in deployment |
| Critic/replay buffer | SAC artifacts present | excluded from runtime |

The equal state dimension is a particularly dangerous detail: a simple model replacement could pass a shape check while giving the TD3 actor the wrong five quantities. The new manifest loader checks the ordered semantic names, not only the dimension.

## 3. Runtime libraries

The custom runtime uses only the libraries needed for deterministic inference and laboratory communication:

| Library | Purpose |
|---|---|
| `torch` | reconstruct and run the frozen custom TD3 actor |
| `numpy` | state, action, flow mapping, and finite-value checks |
| `asyncua` | BioSMB/MFCS OPC-UA communication |
| `redis` | live target-pH input and experiment metadata |
| `pymongo` | raw-observation and deployment audit records |

Stable-Baselines3, Gymnasium, plotting packages, the TD3 critic, replay buffer, optimizer, reward code, and exploration code are absent from the runtime dependency file and Docker image.

## 4. Implemented architecture

```text
new offline TD3 training run
    |
    | --save-checkpoint
    v
actor-only weights + strict JSON manifest + golden inference cases
    |
    v
manifest/hash/architecture/semantic validation before any network connection
    |
    v
PH_2 + target + verified pump readback
    |
    v
exact 5-element TD3 state
    |
    v
frozen deterministic actor (2 normalized actions)
    |
    v
exact ratio/sum mapping to logical acid, acetate, and water flows
    |
    v
flow/slew/mass/commissioning safety checks
    |
    +-------------------- suggest_only: log proposal; no write
    |
    +-------------------- active_control: gated batch write + readback
```

The actor is always evaluated with `eval()` and `torch.inference_mode()`. There is no exploration noise and no call that updates policy parameters.

## 5. Exact TD3 state and action contract

The deployed state is

$$
s_t =
\begin{bmatrix}
pH_{2,t} \\
pH_{sp,t} \\
pH_{2,t} - pH_{sp,t} \\
a^{\rho}_{t-1} \\
a^{S}_{t-1}
\end{bmatrix}.
$$

Important details:

- `PH_2` is the only pH value used by the controller.
- `PH_1` may remain in raw sensor logging, but it never enters the TD3 state.
- The error sign is measured minus target.
- The last two state variables are normalized previous actions reconstructed from the latest seven-pump readback. They are not physical mL/min values.

The actor returns

$$
a_t =
\begin{bmatrix}
a^{\rho}_t \\
a^{S}_t
\end{bmatrix},
\qquad
a^{\rho}_t,a^{S}_t \in [-1,1].
$$

For acid-plus-acetate flow sum $S$,

$$
S = S_{\min}
+ \frac{a^S_t+1}{2}\left(S_{\max}-S_{\min}\right).
$$

At that sum, feasible acid bounds are

$$
F_{H,\min}^{S}
= \max(F_{H,\min}, S-F_{A,\max}),
$$

$$
F_{H,\max}^{S}
= \min(F_{H,\max}, S-F_{A,\min}).
$$

These bounds define the feasible acetate-to-acid ratio interval. The normalized ratio action interpolates in log-ratio space:

$$
\log_{10}(\rho)
= \log_{10}(\rho_{\min})
+ \frac{a^{\rho}_t+1}{2}
\left[
\log_{10}(\rho_{\max})-\log_{10}(\rho_{\min})
\right].
$$

The logical flows are then

$$
F_H = \frac{S}{1+\rho},
\qquad
F_A = S-F_H,
\qquad
F_W = F_{W,\mathrm{fixed}}.
$$

The implemented mapping is tested for parity against `PHEnvironment.action_to_flows()` over a $7\times7$ normalized-action grid.

## 6. Files added or changed

### Training/export bridge

- `helpers/td3_deployment_export.py`
  - exports only CPU actor tensors;
  - separates reachable measured-pH bounds from approved target bounds;
  - records state/action semantics, architecture, physical mapping, provenance, and hashes;
  - creates three golden state-to-action cases using the actor's actual device;
  - restores the actor's original train/eval state after export.

- `run_offline_ph_td3_training.py`
  - retains the complete research checkpoint by default;
  - additionally creates `deployment_bundle/td3_actor_weights.pt` and `deployment_bundle/td3_actor_manifest.json` for `ratio_buffer_sum` mode;
  - marks new exports as simulation-only and not lab validated;
  - records checkpoint/config hashes and Python, PyTorch, and NumPy versions.

### Online deployment

- `Biosmb-run-online/Biosmb-run-online/td3_deployment.py`
  - validates the manifest, file placement, SHA-256, dtypes, bounds, state order, action order, actor topology, and golden cases;
  - loads weights with `weights_only=True`;
  - reconstructs only `TD3Agent.actor.Actor`;
  - implements exact forward and inverse ratio/sum mappings;
  - separates logical streams from physical pump numbers;
  - preserves unrelated pump values in a merged seven-pump command.

- `Biosmb-run-online/Biosmb-run-online/main.py`
  - replaces Stable-Baselines3 inference with frozen custom TD3 inference;
  - uses `PH_2` only;
  - reconciles startup from actual pump readback;
  - implements `suggest_only` and gated `active_control` paths;
  - performs a single full-array write followed by finite seven-value readback validation;
  - handles SIGTERM through the controlled cleanup path;
  - zeros/disables only mapped pumps and records a shutdown-verification receipt;
  - contains numbered and commented sections for joint review.

- `deployment_settings.json`
  - makes pumps 2/3/4 explicit candidates for acid/acetate/water;
  - leaves every physical verification flag false;
  - leaves the independently approved manifest hash empty;
  - defaults to `suggest_only` and a finite ten-step session.

### Packaging and tests

- `requirements-runtime.txt` contains the actor-only runtime libraries.
- `dockerfile` builds from explicit files, runs as a non-root user, and defaults to `suggest_only`.
- `docker-compose.yml` uses separate `shadow` and `active` profiles, read-only model mounts, and no automatic restart.
- the root `.dockerignore` prevents raw data, results, reports, Git metadata, historical SAC artifacts, and live actor bundles from entering the build context.
- `tests/test_biosmb_td3_deployment.py` tests the policy, mapping, online safety helpers, shadow no-write path, and container contract.

## 7. `main.py` walkthrough by numbered section

### Section 1: standard-library imports

Loads argument parsing, timing, signal handling, UUID generation, paths, JSON, and environment-variable support. No connection is opened here.

### Section 2: numerical library

Imports NumPy. The OPC-UA, Redis, and MongoDB packages are deliberately imported later, after policy validation, so policy-only validation cannot accidentally contact the lab.

### Section 3: custom TD3 deployment contract

Makes the root actor package importable when the nested example is run directly from the repository, then imports the frozen-policy and action-mapping utilities.

### Section 4: explicit exceptions

Separates configuration/policy startup errors from process-safety shutdowns. This makes the reason for stopping visible in the session audit record.

### Section 5: configuration and CLI

Loads JSON settings and validates:

- exact control-mode spelling;
- literal JSON booleans rather than truthy strings;
- unique one-indexed pump mappings;
- finite and ordered pH/target limits;
- positive timing and safety settings;
- a finite positive step count in active mode, including after CLI overrides;
- explicit acid, acetate, and water MFCS mass-node names.

`--validate-policy-only` exits before any network library is imported or client is created.

### Section 6: audit-safe conversion and logging

Converts arrays, NumPy scalar values, and timestamps into MongoDB-compatible forms. In active mode, failure to record the command intent prevents the hardware write.

### Section 7: observations

Reads all BioSMB sensors, all seven pump values, and the three configured MFCS masses. All sensors are retained for diagnostics, but only `PH_2` is selected for control.

### Section 8: observation, inventory, and target validation

Requires a finite `PH_2`, exactly seven finite pump values, and the hard pH envelope. The target is accepted only if it lies inside the intersection of the deployment configuration and policy-manifest target ranges. Operator intent is rejected rather than silently clipped.

### Section 9: active preflight

Active control requires all of the following before the OPC connection is created:

1. pump-to-stream mapping verified;
2. MFCS mass mapping verified;
3. outlet path to `PH_2` verified;
4. exclusive pump ownership verified;
5. `FLOW` readback semantics verified;
6. `simulation_only=false`;
7. lab, dynamic-model, and frozen-policy validation flags true;
8. exact match to an independently approved manifest SHA-256;
9. the nonpersistent one-session arming environment value.

The committed settings satisfy none of these active gates.

### Section 10: command and readback

Maps logical acid, acetate, and water values onto configured physical pumps while preserving the other four pumps. It calls `set_all_flows()` once, requires exactly seven finite readback values, and checks controlled and uncontrolled pump entries. Any write/readback uncertainty becomes a failed receipt and safety shutdown.

### Section 11: monitoring

Uses monotonic deadlines and polls observations during the hold between TD3 decisions. Invalid `PH_2`, pump arrays, or verified mass measurements terminate the session.

### Section 12: warm-up and startup reconciliation

Collects consecutive live observations and reconstructs the previous normalized TD3 action from actual pump readback. It does not assume startup flows of `[1,1,1]`. Verified low inventory stops warm-up immediately.

### Section 13: finite deployment loop

For each step, the code:

1. reads and validates the current observation;
2. reads and validates the target;
3. extracts current logical flows using the explicit pump map;
4. reconstructs the exact five-element TD3 state;
5. runs deterministic actor inference;
6. maps the two normalized actions to logical flows;
7. applies flow, total-flow, slew, inventory, and commissioning checks;
8. durably logs the command intent;
9. either logs a zero-write shadow receipt or performs one active batch write;
10. verifies readback and monitors until the next deadline;
11. logs the completed step.

`policy_candidate_valid` and `active_eligible` are logged separately. A numerically reasonable shadow proposal is therefore not presented as hardware-approved.

### Section 14: entrypoint and cleanup

Validates the actor before loading laboratory communication packages. It creates clients, records the session, and keeps cleanup inside the live OPC context. Keyboard interruption, a safety fault, software error, or Docker SIGTERM all reach cleanup. Active cleanup commands zero mapped flows, disables mapped pumps, reads their states back, and adds the result to the shutdown record.

## 8. Policy-bundle lifecycle

### Step 1: produce a new research checkpoint

The existing 500,000-step run cannot be deployed because its configuration recorded `save_checkpoint: false`. New runs now save by default. The explicit `--save-checkpoint` flag remains accepted, while `--no-save-checkpoint` opts out for a disposable run:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  run_offline_ph_td3_training.py `
  --action-mode ratio_buffer_sum `
  --save-checkpoint
```

This creates:

```text
results/offline_ph_td3_training_<timestamp>/
  checkpoints/offline_ph_td3_<timestamp>.pkl
  deployment_bundle/td3_actor_weights.pt
  deployment_bundle/td3_actor_manifest.json
```

The `.pkl` file remains a research checkpoint. It is never loaded by the laboratory runtime. Only the two files under `deployment_bundle` are copied to the online `models/` directory.

### Step 2: validate the bundle without network access

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  Biosmb-run-online/Biosmb-run-online/main.py `
  --config Biosmb-run-online/Biosmb-run-online/deployment_settings.json `
  --manifest results/<run>/deployment_bundle/td3_actor_manifest.json `
  --validate-policy-only
```

This checks hash, schema, architecture, state/action meanings, flow mapping, and golden inference results before returning.

### Step 3: run the container in shadow mode

From `Biosmb-run-online/Biosmb-run-online`, place the reviewed bundle in `models/`, supply `BIOSMB_MONGO_URL` outside source, and use:

```powershell
docker compose --profile shadow up --build biosmb-td3-shadow
```

Shadow mode exercises live acquisition and inference but cannot enter the hardware-write branch.

### Step 4: do not enable active mode yet

The active profile exists so its implementation can be reviewed and fault-tested. It must remain blocked until the scientific and physical gates in Sections 9 and 10 are satisfied.

## 9. Verification performed

The implementation was checked with:

- Python compilation of the exporter, training runner, online policy module, online main, and tests;
- 16 hardware-free unit/contract tests;
- exact online-versus-training action-mapping parity on 49 normalized actions;
- inverse mapping consistency, including degenerate minimum/maximum sum cases;
- actor export/load inference parity;
- hash and state-order rejection tests;
- NaN and short readback rejection;
- one-batch-write behavior;
- one complete mocked `suggest_only` step proving zero hardware writes;
- a four-step training/export smoke run;
- policy-only loading of the smoke-run bundle with no network packages or connections.

The four-step run verifies software wiring only. Its tracking metrics are scientifically meaningless and it is not a controller candidate.

## 10. What is not yet solved

The implementation deliberately does not claim lab readiness. The remaining gaps are:

1. **No deployable trained actor exists yet.** The previous 500,000-step actor was not checkpointed.
2. **The training plant is inadequate for hardware control.** It is an ideal static Henderson-Hasselbalch model, while lab data require delay, mixing/residence dynamics, calibration, and sensor dynamics.
3. **The deployment slew rejection is not part of training.** A policy may repeatedly propose a move larger than `0.5 mL/min` and be stopped after repeated rejection. The exact rate limiter must be included in dynamic training and frozen-policy evaluation before active use.
4. **The 60-second decision interval is provisional.** It must come from identified process and sensor dynamics.
5. **Target freshness and target-step/dwell rules are not yet implemented.** Range validation alone cannot prove a Redis target is current.
6. **OPC `FLOW` may be command echo rather than measured flow.** The active gate remains false until its meaning is verified.
7. **Pumps 2/3/4, MFCS channels, and the outlet path are candidates, not confirmed facts.** All corresponding flags remain false.
8. **Full-array writing requires exclusive ownership.** Another program must not concurrently write any of the seven pumps.
9. **MongoDB is the active audit dependency.** A local write-ahead log should be added before serious active trials.
10. **The Docker image was not built in this workspace.** A container policy-only smoke test remains required on the intended host.

## 11. Recommended joint-edit sequence

The safest next review sequence is:

1. Read `main.py` Sections 5, 9, 10, 13, and 14 together and confirm the desired lab behavior.
2. Physically verify pump, MFCS, valve/outlet, and `FLOW` semantics without enabling RL control.
3. Finish dynamic model identification and make the TD3 training environment use the validated delay/mixing/sensor model.
4. Put the exact deployment slew/rate mechanism into training and frozen evaluation.
5. Train multiple seeds with checkpoint saving and compare TD3 against a simple validated baseline.
6. Export one frozen candidate and run policy-only, unit, container, and software-in-the-loop tests.
7. Run finite live `suggest_only` sessions and inspect every proposed action against operator actions and observed `PH_2` behavior.
8. Only after independent approval, populate the manifest hash and physical verification gates for a supervised one-action experiment.

## 12. Conclusion

The custom TD3 code is now integrated into the BioSMB online reference in the same practical role that Stable-Baselines3 SAC occupied, but with the correct custom state/action semantics and an actor-only PyTorch runtime. The implementation is ready for code review and shadow-mode development. It is intentionally not ready for autonomous active lab control.
