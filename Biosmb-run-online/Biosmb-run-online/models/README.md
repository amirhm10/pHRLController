# Selected custom TD3 model artifacts

These files replace the historical Stable-Baselines3 SAC artifacts and are the
default model set selected for the lab shipment.

| File | Purpose |
|---|---|
| `td3_actor_manifest.json` | Deployment contract, provenance, hashes, and golden vectors |
| `td3_actor_weights.pt` | CPU-loadable actor state dictionary for deterministic deployment |
| `td3_training_checkpoint.pkl` | Trusted pretrained actor/critic starting point when online training is enabled |
| `td3_training_config.json` | Exact configuration snapshot from the latest offline run |
| `td3_online_training_config.json` | Optional online continuation settings, including batch size `64`, replay capacity `10000`, recent window `200`, and noise `0.02 -> 0.01` |

Source run:

```text
results/offline_ph_td3_training_20260713_204554/
```

Selected model settings:

- `500000` offline rollout steps
- ratio-preserving two-action flow mapping
- actor and critic layers `[64, 64]`
- `gamma = 0.99`
- batch size `64`
- final offline exploration noise `0.02`
- policy ID `custom_td3_687131b557875010`

Verified SHA-256 values:

```text
td3_actor_manifest.json
070179921655aed8939933ceb582432faf734114e7c6752b3e7eaac14e37bb75

td3_actor_weights.pt
687131b5578750103f6dfe93731009c1eb7ab49e792db9f1e0dcd531662c0a88

td3_training_checkpoint.pkl
b2298ab8120ccaa190109d386baa4ed297342d0954aeb2577baca6443bee73ae

td3_training_config.json
c61f15870bc0aad197a8962571b8e4f97a8cd50f3424082f8aba22ec3789e594
```

The saved deterministic 25-target simulation grid produced pH MAE `0.011105`,
RMSE `0.013258`, maximum absolute error `0.032116`, and `92%` of targets within
`0.02` pH. It has not been validated on the live BioSMB process. A preceding
`[128, 128]`, `gamma = 0.97` checkpoint had better fixed-grid tracking and lower
mean buffer use; the current selection follows the explicit decision to ship the
latest run, not a claim that it won the comparison.

The `.pkl` is not a full replay/optimizer/RNG resume checkpoint and must never
be loaded from an untrusted source.

`main.py` always loads the actor description and weights by their fixed names.
It loads the training checkpoint only when `online_training_enabled = True`.
The online loader then verifies that the checkpoint actor matches the deployment
actor before control begins.

If the selected model is deliberately replaced later, copy all four files from
one generated `deployment_bundle` into this folder together. Never mix files
from different offline runs. New-format offline checkpoints include the network
architecture, `gamma`, and optimizer states. The online replay buffer still
starts empty. Keep
`td3_online_training_config.json` for online-only choices such as replay capacity
`10000`, batch size `64`, recent window `200`, update frequency, and exploration
`0.02 -> 0.01`.
