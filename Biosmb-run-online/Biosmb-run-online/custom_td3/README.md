# Custom TD3 package for BioSMB

This package contains two deliberately separated parts:

1. A verified deterministic deployment facade used by `main.py`.
2. A reduced copy of only the learning path active in the latest offline run,
   prepared for later online-training work.

It does not depend on Stable-Baselines3.

## Deployment API

```python
from custom_td3 import BioSMBTD3Policy

model = BioSMBTD3Policy.load("models/td3_actor_manifest.json")
state = model.build_state(observation, target_ph)
normalized_action, _ = model.predict(state, deterministic=True)
formatted_action = model.format_action(normalized_action)
measured_action = model.action_from_observation(observation_after)
```

The five-element state is:

```text
[PH_2, target pH, PH_2 - target pH,
 previous normalized ratio action,
 previous normalized buffer-sum action]
```

The two actor outputs are:

```text
[normalized log acetate/acid ratio,
 normalized acid+acetate total flow]
```

The mapper enforces acid and acetate bounds of 1-10 mL/min, a buffer-flow sum
of 2-20 mL/min, and fixed Arium water at 5 mL/min.

## Active training modules

Only the components used by the latest run are included:

```text
actor.py
critic.py
agent.py
replay_buffer.py
helpers_net.py
reward.py
```

The active replay path samples one-step transitions directly. The package
excludes n-step returns,
lambda returns, parameter noise, behavioral cloning, hard target updates,
alternative critic losses, plain replay, and inactive reward modes.

The public imports include `TD3Agent`, `GaussianNoiseSchedule`,
`PERRecentReplayBuffer`, `PHRewardConfig`, and `compute_ph_reward`.

The latest offline run used:

- actor and critic layers `[128, 128]`
- gamma `0.97`
- batch size `64`
- replay capacity `60000`
- Gaussian exploration `0.35 -> 0.02`, linearly over 5000 actions
- actor and critic learning rates `1e-4` and `1e-3`
- target smoothing standard deviation `0.2`, clipped at `0.5`
- policy delay `2` and soft target coefficient `0.005`
- mixed replay: 50% prioritized, 20% recent, and 30% uniform

The immutable offline values are stored in `models/td3_training_config.json`.
The proposed online continuation settings are separate in
`models/td3_online_training_config.json`.

Offline exploration ended at standard deviation `0.02`. Online adaptation is
configured to begin at `0.02` and decay to `0.01`, preserving continuity while
reducing random action variation. Exploratory actions and online updates remain
disabled until the laboratory safety protocol is validated.

## Important checkpoint limitation

`models/td3_training_checkpoint.pkl` is the original trusted local checkpoint.
It contains actor and critic weights, target weights, selected hyperparameters,
and no saved replay contents. The original loader restores actor and critic,
hard-synchronizes targets, and creates new optimizers. It does not restore the
replay buffer, optimizer states, counters, or random-number-generator states.

Therefore the actor deployment is numerically reproducible, but later online
training cannot resume bit-for-bit from offline step 500000 with this checkpoint.
That requires a separate complete-resume checkpoint design.

Never load an untrusted `.pkl` file. The deployment path uses the safer
weights-only `.pt` file with a manifest hash and golden-vector checks.

## Current safety status

The latest manifest says the policy is simulation-only and not lab validated.
`main.py` therefore uses `suggest_only`. Do not enable `active_control` until
the pump mapping, PH_2 dynamics, action timing, safety behavior, and frozen
policy performance have been validated in the laboratory.
