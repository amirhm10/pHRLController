"""Export a trained pH TD3 actor as a deployment-only policy bundle.

The training checkpoint contains actor, critic, optimizer, and training state.
The laboratory runtime needs only the frozen actor plus a strict description of
the state and action contracts.  This module writes that smaller bundle.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch


PH_TD3_STATE_VARIABLES = [
    "current_ph",
    "target_ph",
    "current_ph_minus_target_ph",
    "normalized_ratio_action",
    "normalized_buffer_sum_action",
]

PH_TD3_ACTION_VARIABLES = [
    "normalized_acetate_acid_ratio",
    "normalized_acid_acetate_total_flow",
]


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of one file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _golden_states(
    current_ph_min: float,
    current_ph_max: float,
    target_ph_min: float,
    target_ph_max: float,
    nominal_ph: float,
) -> list[np.ndarray]:
    """Create representative states used to verify deployment parity."""

    current_low = float(current_ph_min)
    current_high = float(current_ph_max)
    target_low = float(target_ph_min)
    target_high = float(target_ph_max)
    nominal_low = max(current_low, target_low)
    nominal_high = min(current_high, target_high)
    nominal = float(np.clip(nominal_ph, nominal_low, nominal_high))
    return [
        np.array([nominal, nominal, 0.0, 0.0, 0.0], dtype=np.float32),
        np.array(
            [current_low, target_high, current_low - target_high, -0.5, 0.0],
            dtype=np.float32,
        ),
        np.array(
            [current_high, target_low, current_high - target_low, 0.5, 0.0],
            dtype=np.float32,
        ),
    ]


def export_td3_actor_bundle(
    actor: torch.nn.Module,
    output_dir: str | Path,
    *,
    actor_config: dict[str, Any],
    action_mapping: dict[str, Any],
    current_ph_bounds: tuple[float, float],
    target_ph_bounds: tuple[float, float],
    nominal_ph: float,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Save actor weights, manifest metadata, and golden inference vectors.

    Parameters
    ----------
    actor:
        The trained custom TD3 actor.
    output_dir:
        Destination directory for the deployment bundle.
    actor_config:
        Architecture fields needed to reconstruct the actor exactly.
    action_mapping:
        Physical flow limits and ratio/sum mapping used during training.
    current_ph_bounds:
        Reachable measured-pH interval represented by the training environment.
    target_ph_bounds:
        Approved target interval, which may be narrower than current pH bounds.
    nominal_ph:
        Nominal pH used for the center golden case.
    source_metadata:
        Optional provenance such as training seed and result directory.
    """

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    state_dim = int(actor_config.get("state_dim", -1))
    action_dim = int(actor_config.get("action_dim", -1))
    if state_dim != len(PH_TD3_STATE_VARIABLES):
        raise ValueError("The pH TD3 deployment state dimension must be 5.")
    if action_dim != len(PH_TD3_ACTION_VARIABLES):
        raise ValueError("The pH TD3 deployment action dimension must be 2.")

    current_low, current_high = map(float, current_ph_bounds)
    target_low, target_high = map(float, target_ph_bounds)
    all_bounds = [current_low, current_high, target_low, target_high]
    if not np.isfinite(all_bounds).all():
        raise ValueError("Current-pH and target-pH bounds must all be finite.")
    if current_low >= current_high:
        raise ValueError("current_ph_bounds must contain two increasing values.")
    if target_low >= target_high:
        raise ValueError("target_ph_bounds must contain two increasing values.")
    if max(current_low, target_low) > min(current_high, target_high):
        raise ValueError("Current-pH and target-pH intervals must overlap.")
    if not np.isfinite(float(nominal_ph)):
        raise ValueError("nominal_ph must be finite.")

    weights_path = destination / "td3_actor_weights.pt"
    manifest_path = destination / "td3_actor_manifest.json"

    # Store tensors on CPU so the bundle loads on a CPU-only lab computer.
    state_dict = {
        name: tensor.detach().cpu()
        for name, tensor in actor.state_dict().items()
    }

    # Golden vectors prove that the deployment actor reconstructs the same
    # network and produces the same deterministic actions as training.  Run
    # them before writing files so inference failure cannot leave half a bundle.
    was_training = actor.training
    actor.eval()
    golden_cases = []
    try:
        try:
            actor_device = next(actor.parameters()).device
        except StopIteration as exc:
            raise ValueError("The TD3 actor has no parameters to export.") from exc
        with torch.inference_mode():
            for state in _golden_states(
                current_low,
                current_high,
                target_low,
                target_high,
                nominal_ph,
            ):
                state_tensor = torch.as_tensor(
                    state,
                    device=actor_device,
                ).reshape(1, -1)
                action = actor(state_tensor).cpu().numpy().reshape(-1)
                golden_cases.append(
                    {
                        "state": state.astype(float).tolist(),
                        "expected_action": action.astype(float).tolist(),
                    }
                )
    finally:
        actor.train(was_training)

    # Passing a Python file object avoids a PyTorch/Windows path-handling edge
    # case that can occur in OneDrive-backed workspaces while preserving the
    # same weights-only serialization format.
    with weights_path.open("wb") as stream:
        torch.save(state_dict, stream)

    error_low = current_low - target_high
    error_high = current_high - target_low
    weights_sha256 = sha256_file(weights_path)
    manifest = {
        "schema_version": 1,
        "algorithm": "custom_td3",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "policy_id": f"custom_td3_{weights_sha256[:16]}",
        "weights_file": weights_path.name,
        "weights_format": "pytorch_state_dict_weights_only",
        "weights_sha256": weights_sha256,
        "state_dim": state_dim,
        "state_dtype": "float32",
        "state_scaling": "none",
        "controlled_measurement": "PH_2",
        "error_definition": "current_ph_minus_target_ph",
        "state_variables": PH_TD3_STATE_VARIABLES,
        "state_bounds": [
            [current_low, current_high],
            [target_low, target_high],
            [error_low, error_high],
            [-1.0, 1.0],
            [-1.0, 1.0],
        ],
        "action_dim": action_dim,
        "action_dtype": "float32",
        "action_semantics": "normalized_ratio_and_buffer_flow_sum",
        "action_variables": PH_TD3_ACTION_VARIABLES,
        "action_bounds": [[-1.0, 1.0], [-1.0, 1.0]],
        "actor": actor_config,
        "action_mapping": action_mapping,
        "target_ph_bounds": [target_low, target_high],
        "golden_tolerance": 1.0e-6,
        "golden_cases": golden_cases,
        "source": source_metadata or {},
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "weights_path": weights_path,
        "manifest_path": manifest_path,
    }
