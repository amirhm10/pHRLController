# Additive custom TD3 modules for the original BioSMB application

**Date:** 2026-07-12

**Current status:** original BioSMB application restored, custom TD3 code added
separately, and `main.py` intentionally not integrated yet.

## 1. Objective

The previous implementation replaced most of the supplied BioSMB online
application. That was not the intended development strategy. The corrected
strategy is:

1. Preserve the supplied BioSMB application as the reference baseline.
2. Keep the BioSMB control-library wrapper, loop, logging, and container files
   owned by the original project.
3. Add our custom TD3 implementation as a separate package.
4. Test the package against the real saved offline actor.
5. Modify only the few SAC-specific seams in `main.py` in a later reviewed task.

## 2. Original files restored

The Desktop copy at
`C:/Users/HAMEDI/Desktop/Biosmb-run-online/Biosmb-run-online` was used as the
source of truth. These workspace files now match its content after normalizing
line endings and final blank lines:

- `main.py`
- `dockerfile`
- `docker-compose.yml`
- `settings.json`
- `biosmb_interface/manager.py`
- `biosmb_interface/utility.py`

The following original files already matched and were left alone:

- `requirements.txt`
- `biosmb_interface/enum.py`
- `biosmb_interface/__init__.py`

Step 1 of the reviewed integration now replaces only the Stable-Baselines3 SAC
import with `from custom_td3 import BioSMBTD3Policy`. No other `main.py` line is
changed in this step. The later `SAC.load(...)` calls are intentionally still
present and will be handled as the next separate edit.

## 3. BioSMB control-library boundary

The supplied application uses `BioSMBManager` from `biosmb_interface`. That
manager remains responsible for OPC-UA operations such as:

- reading all pump flows
- changing pump flow commands
- reading pH and other sensors
- enabling, disabling, or zeroing pumps

The custom TD3 package does not import `BioSMBManager` and cannot perform a
hardware write. It only consumes ordinary dictionaries and returns the same
action-dictionary structure already used by the supplied main file.

This separation is the main architectural correction.

## 4. Additive package layout

```text
Biosmb-run-online/Biosmb-run-online/custom_td3/
  __init__.py
  actor.py
  contracts.py
  policy.py
  controller.py
  README.md
```

### `actor.py`

Contains an inference-only PyTorch actor with the exact layer names used by the
training implementation. It is self-contained so the BioSMB folder can later
be shared or containerized without copying the full training repository.

It contains no critic, target network, optimizer, replay buffer, reward, or
exploration implementation.

### `contracts.py`

Contains:

- the ordered TD3 state and action names
- logical acid, acetate, and Arium-water flows
- the exact normalized ratio/sum action mapping
- the inverse mapping from physical flows to previous normalized actions
- the state builder
- formatting into the original BioSMB action-dictionary schema

### `policy.py`

Loads only the actor weights and verifies:

- manifest schema and algorithm
- state and action dimensions and ordering
- flow-mapping contract
- SHA-256 of the weights file
- strict actor architecture compatibility
- finite tensors
- golden state-to-action cases

It loads with `torch.load(..., weights_only=True)` and returns deterministic
actions only.

### `controller.py`

Defines the public compatibility facade:

```python
from custom_td3 import BioSMBTD3Policy
```

The facade exposes:

```python
BioSMBTD3Policy.load(...)
model.build_state(...)
model.predict(...)
model.format_action(...)
model.default_action()
```

`predict()` returns `(action, None)`, matching the existing SAC prediction call.

## 5. Mathematical contract

The supplied SAC example currently uses a five-element state containing pH,
target, and three physical flow values. The custom TD3 actor also has dimension
five, but the meanings are different:

$$
s_t =
\begin{bmatrix}
PH_{2,t} \\
PH_{sp,t} \\
PH_{2,t}-PH_{sp,t} \\
a^{\rho}_{t-1} \\
a^{S}_{t-1}
\end{bmatrix}.
$$

The last two values are normalized previous actions reconstructed from physical
acid, acetate, and water flows. Raw mL/min values must not be placed directly
in these two state positions.

The actor output is

$$
a_t =
\begin{bmatrix}
a^{\rho}_t \\
a^{S}_t
\end{bmatrix},
\qquad a^{\rho}_t,a^{S}_t \in [-1,1].
$$

The buffer-flow sum is

$$
S_t = S_{\min}
+ \frac{a^S_t+1}{2}(S_{\max}-S_{\min}).
$$

For the saved actor, $S_{\min}=2$ and $S_{\max}=20$ mL/min. The ratio action is
mapped in feasible log acetate-to-acid ratio space. The resulting flows satisfy

$$
F_H = \frac{S_t}{1+\rho_t},
\qquad
F_A = S_t-F_H,
\qquad
F_W = 5\ \mathrm{mL/min}.
$$

Acid and acetate are each restricted to 1-10 mL/min by the mapping.

## 6. Latest saved model inspected

The latest saved run is:

```text
results/offline_ph_td3_training_20260710_183129/
```

The online runtime should use only:

```text
deployment_bundle/td3_actor_manifest.json
deployment_bundle/td3_actor_weights.pt
```

The actor-weight SHA-256 is:

```text
0c10ce7b8602bd5c455f74009e233ecc990735a3f73c76b2c99a196d23f91777
```

The actor architecture is:

```text
5 -> 128 -> 128 -> 2
```

with ReLU hidden activations and tanh output. The legacy training `.pkl` was not
opened and should not be used in the online runtime.

The manifest explicitly records:

```text
simulation_only = true
lab_validated = false
dynamic_model_validated = false
frozen_policy_validated = false
```

Therefore this is a valid saved actor for software testing and future shadow
suggestions, not an active lab controller.

## 7. Result evidence

The saved simulation run reports:

| Scope | Steps | MAE, pH | RMSE, pH | Maximum absolute error, pH |
|---|---:|---:|---:|---:|
| all steps | 500000 | 0.03174 | 0.05302 | 1.34143 |
| final deterministic evaluation | 200 | 0.00621 | 0.00973 | 0.11117 |

The flow-constraint table reports zero acid, acetate, water, buffer-sum, or
nonfinite violations in simulation. These results verify a saved simulation
policy. They do not establish performance under laboratory delay, mixing,
sensor response, or disturbances.

No new performance figure was generated for this refactoring task because the
claim being tested was software compatibility, not improved control quality.

## 8. Compatibility with the original action dictionary

`model.format_action()` returns:

```python
{
    "raw_action": [ratio_action, sum_action],
    "controlled_flow_rates": [acid_flow, acetate_flow, water_flow],
    "flow_rates": [... seven pump values ...],
    "total_controlled_flow_rate": ...,
    "stream_flow_rates": {...},
}
```

This is the same dictionary shape consumed by the existing action validation,
selection, application, and logging functions. Physical pump indices remain a
constructor argument. The default `[0,1,2]` reproduces the original code but is
not treated as verified lab mapping.

## 9. Later minimal `main.py` integration

No main-file integration was performed now. When reviewed, the only intended
policy-specific changes are:

1. Replace the SAC import and model loader with `BioSMBTD3Policy.load()`.
2. Initialize the previous action with `model.default_action()`.
3. Replace the SAC state-builder call with `model.build_state()`.
4. Replace the SAC action formatter with `model.format_action()`.

The existing Redis, MongoDB, MFCS, BioSMB manager, logging, safety, and loop code
can remain in the original file.

## 10. Containerization approach

The original Dockerfile and Compose file are restored unchanged. The Dockerfile
already performs `COPY . .`, so the additive package will enter the container
without a Dockerfile rewrite. The original requirements already include NumPy
and PyTorch.

At the later container step:

1. Copy or mount the two actor deployment files under `models/`.
2. Make the four small reviewed main-file changes.
3. Build the original Compose service.
4. Run actor loading and golden-vector tests in the container before any live
   network connection.

## 11. Verification completed

- Restored file contents match the Desktop originals after line-ending and
  final-blank normalization.
- Python compilation passed for the original main file and all additive TD3
  modules.
- Nine hardware-free additive TD3 tests passed.
- The 49-point action grid matches the training environment.
- Synthetic export/load prediction matches the training actor.
- The real saved 500k actor passes manifest, hash, strict-load, and golden-vector
  checks.
- Tests confirm the main file imports `BioSMBTD3Policy` instead of SAC.

## 12. Remaining uncertainty

- Physical pump-to-stream mapping is not verified.
- The meaning of BioSMB `FLOW` readback remains to be confirmed.
- The latest actor was trained on the static ideal simulation rather than a
  validated dynamic lab model.
- The original main file has known configuration and safety limitations. They
  remain unchanged because preserving the reference was the explicit objective.
- The restored original contains a plaintext laboratory database credential.
  Do not publish or redistribute this folder until the credential is moved to
  an environment variable and the exposed credential is rotated.
- Container build and container-level actor loading remain for the next phase.
