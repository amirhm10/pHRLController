# Selected custom TD3 model artifacts

These files replace the historical Stable-Baselines3 SAC artifacts and are the
default model set selected for the lab shipment.

| File | Purpose |
|---|---|
| `td3_actor_manifest.json` | Deployment contract, provenance, hashes, and golden vectors |
| `td3_actor_weights.pt` | CPU-loadable actor state dictionary for deterministic deployment |
| `td3_training_checkpoint.pkl` | Trusted pretrained actor/critic starting point for active online training |
| `td3_training_config.json` | Exact configuration snapshot from the latest offline run |
| `td3_online_training_config.json` | Active online continuation settings, including batch size `64`, replay capacity `10000`, recent window `200`, and noise `0.02 -> 0.01` |

Source run:

```text
results/offline_ph_td3_training_20260710_183129/
```

Selected model settings:

- `500000` offline rollout steps
- actor and critic layers `[128, 128]`
- `gamma = 0.97`
- batch size `64`
- final offline exploration noise `0.02`
- policy ID `custom_td3_0c10ce7b8602bd5c`

Verified SHA-256 values:

```text
td3_actor_manifest.json
c243d5d74d1d7ff1377e969a3efe2cffc9656e0c0b73b87dd033b2a9d8dbbec5

td3_actor_weights.pt
0c10ce7b8602bd5c455f74009e233ecc990735a3f73c76b2c99a196d23f91777

td3_training_checkpoint.pkl
3795935a7d84846ecf7341fbe6d5f8bc0afccfe4af2d90d22ad061d2cf97cc4e

td3_training_config.json
4b56db30bd2d7f33630e80a1510e33ae37b3b9d5d079f3d99abfc5dc11800bc0
```

The `.pkl` is not a full replay/optimizer/RNG resume checkpoint and must never
be loaded from an untrusted source.

`main.py` loads this actor description, actor weights, and training checkpoint
by their fixed names. The online loader verifies that the checkpoint actor
matches the deployment actor before control begins.

If the selected model is deliberately replaced later, copy all four files from
one generated `deployment_bundle` into this folder together. Never mix files
from different offline runs. New-format offline checkpoints include the network
architecture, `gamma`, and optimizer states. The online replay buffer still
starts empty. Keep
`td3_online_training_config.json` for online-only choices such as replay capacity
`10000`, batch size `64`, recent window `200`, update frequency, and exploration
`0.02 -> 0.01`.
