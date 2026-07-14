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
 previous normalized optional-flow action]
```

The two actor outputs are:

```text
[normalized log acetate/acid ratio,
 normalized optional total-flow fraction]
```

The first output selects the acetate/acid ratio over the complete feasible ratio
range. For that ratio, the mapper calculates the exact feasible acid-plus-acetate
flow interval. The second output then chooses a fraction inside that interval.
This preserves the ratio authority instead of allowing the total-flow choice to
restrict it. The mapper enforces acid and acetate bounds of 1-10 mL/min, a
buffer-flow sum of 2-20 mL/min, and fixed Arium water at 5 mL/min.

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
- action mapping `ratio_preserving_flow_v1`
- actor and critic layers `[64, 64]`
- gamma `0.99`
- batch size `64`
- replay capacity `60000`
- Gaussian exploration `0.35 -> 0.02`, linearly over 5000 actions
- actor and critic learning rates `1e-4` and `1e-3`
- target smoothing standard deviation `0.2`, clipped at `0.5`
- policy delay `2` and soft target coefficient `0.005`
- mixed replay: 50% prioritized, 20% recent, and 30% uniform
- optional-flow economic penalty weight `0.01`

The selected files came from
`results/offline_ph_td3_training_20260713_204554`. The offline runner writes a
ready-to-copy `deployment_bundle` containing
`td3_actor_manifest.json`, `td3_actor_weights.pt`,
`td3_training_checkpoint.pkl`, and `td3_training_config.json`. Copy those four
files together into the BioSMB `models` folder and do not mix files from
different offline runs.

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

The exact active shaped reward is implemented in `reward.py`. It includes the
same tracking, total-flow movement, near-target bonus, and optional-flow economic
terms used in the selected offline run. `main.py` stores the same reward value in
replay and in the MongoDB deployment record, together with the full reward
breakdown and actor/critic update diagnostics.

## Important checkpoint limitation

The current `models/td3_training_checkpoint.pkl` is the selected trusted local
checkpoint. It contains actor and critic weights, target weights, and selected
hyperparameters, but no replay or optimizer state.

The checkpoint records actor/critic architecture and optimizer states. The
online loader reads the `[64, 64]` architecture and `gamma = 0.99` from that
checkpoint instead of relying on duplicated online JSON values. It restores the
offline optimizer state but intentionally starts with an empty online replay
buffer.

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
