# Custom TD3 package for BioSMB

This package contains two deliberately separated parts:

1. A verified deployment helper used by `main.py`.
2. A reduced copy of the learning path active in the latest offline run, now
   connected to online BioSMB transitions.

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

The selected shipment checkpoint was trained with:

- total rollout length `500000` steps
- actor and critic layers `[128, 128]`
- gamma `0.97`
- batch size `64`
- replay capacity `60000`
- Gaussian exploration `0.35 -> 0.02`, linearly over 5000 actions
- actor and critic learning rates `1e-4` and `1e-3`
- target smoothing standard deviation `0.2`, clipped at `0.5`
- policy delay `2` and soft target coefficient `0.005`
- mixed replay: 50% prioritized, 20% recent, and 30% uniform

The offline training runner now defaults to a separate controlled experiment:

- total rollout length `500000` steps
- actor and critic layers `[128, 128]`
- gamma `0.99`
- batch size `64`
- Gaussian exploration `0.35 -> 0.04`, linearly over 5000 actions

Running the offline experiment does not automatically change the selected
500000-step shipment checkpoint. `main.py` continues to load the existing
four-file model set from `models/` until a new matched set is deliberately
copied there. The selected shipment checkpoint remains the earlier
`gamma = 0.97`, `0.35 -> 0.02` model until the new experiment is reviewed.

For a future deliberate replacement, the offline runner writes a ready-to-copy
`deployment_bundle` containing
`td3_actor_manifest.json`, `td3_actor_weights.pt`,
`td3_training_checkpoint.pkl`, and `td3_training_config.json`. Copy those four
files together into the BioSMB `models` folder and do not mix files from
different offline runs. The selected 500000-step shipment set should remain in
place for the current handoff.

The immutable offline values are stored in `models/td3_training_config.json`.
The active online continuation settings are separate in
`models/td3_online_training_config.json`.

Offline exploration ended at standard deviation `0.02`. Online adaptation is
configured to begin at `0.02` and decay to `0.01`, preserving continuity while
reducing random action variation. The online run uses batch size `64`, replay
capacity `10000`, a recent-sampling window of `200` transitions, and one
gradient update per completed control transition once the replay buffer contains
64 transitions. At the 60-second control interval, the recent window represents
approximately 3 hours 20 minutes. Before 200 transitions exist, the recent pool
automatically uses every available transition.

The exact active shaped reward is implemented in `reward.py`. `main.py` stores
the same reward value in replay and in the MongoDB deployment record, together
with the full reward breakdown and actor/critic update diagnostics.

## Important checkpoint limitation

The current `models/td3_training_checkpoint.pkl` is the selected trusted local
checkpoint. It contains actor and critic weights, target weights, and selected
hyperparameters, but no replay or optimizer state.

The future offline checkpoint format also records actor/critic architecture and
optimizer states. The online loader reads the architecture and `gamma` from
that checkpoint, so a new `[128, 128]`, `gamma = 0.97` model does not depend on
stale duplicated values in the online JSON. It restores the offline optimizer
state but intentionally starts with an empty online replay buffer.

New `td3_online_*.pkl` checkpoints contain actor, critics, target networks,
optimizers, the 10000-transition replay buffer, update counters, and random
states. These trusted local files can resume an online run completely.

Never load an untrusted `.pkl` file. The deployment path uses the safer
weights-only `.pt` file with a manifest hash and golden-vector checks.

## Current safety status

The latest actor manifest still records that the starting policy was trained in
simulation and was not lab validated at export time. `main.py` is now configured
for active control and active online updates at the user's direction. Laboratory
supervision, verified pump mapping, and reviewed shutdown behavior remain
necessary.
