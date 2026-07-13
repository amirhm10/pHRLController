# Additive custom TD3 module

This package contains only the custom TD3 pieces that can later be imported by
the original BioSMB `main.py`. The original main file, BioSMB interface,
Dockerfile, Compose file, settings, and Stable-Baselines3 example are unchanged.

## Public API

The intended compatibility facade is:

```python
from custom_td3 import BioSMBTD3Policy
```

It provides:

```python
BioSMBTD3Policy.load(...)
model.build_state(...)
model.predict(...)
model.format_action(...)
model.default_action()
```

The `predict` method returns `(action, None)`, matching the call shape already
used by the Stable-Baselines3 SAC example.

## Latest saved actor

The latest verified deployment bundle is currently:

```text
results/offline_ph_td3_training_20260710_183129/deployment_bundle/
  td3_actor_manifest.json
  td3_actor_weights.pt
```

Use those two files for inference. Do not load or distribute the training
checkpoint `.pkl` in the online runtime.

The saved actor contract is:

```text
state  = [PH_2, target, PH_2-target,
          previous normalized ratio action,
          previous normalized buffer-sum action]

action = [normalized acetate/acid ratio,
          normalized acid+acetate total flow]
```

The action mapper produces physical acid and acetate flows within 1-10 mL/min,
an acid-plus-acetate sum within 2-20 mL/min, and fixed Arium water at 5 mL/min.

The manifest marks this actor as simulation-only and not lab validated. It is
for loader testing and future `suggest_only` evaluation, not active lab control.

## Hardware-free example

Run from `Biosmb-run-online/Biosmb-run-online`:

```python
from custom_td3 import BioSMBTD3Policy

model = BioSMBTD3Policy.load(
    "../../results/offline_ph_td3_training_20260710_183129/"
    "deployment_bundle/td3_actor_manifest.json",
    controlled_flow_indices=[0, 1, 2],
    controlled_stream_names={
        0: "acetic-acid",
        1: "sodium-acetate",
        2: "di-water",
    },
)

observation = {
    "biosmb-sensors": {"PH_2": 4.6},
    "biosmb-flows": [5.0, 5.0, 5.0, 0.0, 0.0, 0.0, 0.0],
}
state = model.build_state(observation, target_ph=4.7)
normalized_action, _ = model.predict(state, deterministic=True)
formatted_action = model.format_action(normalized_action)
```

The pump indices in this example reproduce the original online code. They are
not a statement that the physical lab mapping has been verified.

## Future minimal changes to `main.py`

When the package has been reviewed, only four policy-specific seams need to be
changed in the original main file:

1. Replace the SAC import/load call with `BioSMBTD3Policy.load`.
2. Use `model.default_action()` for the initial action representation.
3. Use `model.build_state(...)` instead of the SAC state builder.
4. Use `model.format_action(raw_action)` instead of the SAC action formatter.

The BioSMB manager, Redis/Mongo clients, logging, safety functions, and loop
structure can remain owned by the original application.

## Containerization later

The original Dockerfile already uses `COPY . .`, so this package will be copied
into the image without modifying the Dockerfile. Its original requirements file
already contains NumPy and PyTorch. In the containerization step, place or mount
the two deployment-bundle files under `models/` and then make the four small
main-file changes listed above.
