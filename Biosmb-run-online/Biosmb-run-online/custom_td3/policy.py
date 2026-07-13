"""Safe actor-only loader with a Stable-Baselines-style prediction method."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .actor import Actor
from .contracts import (
    ACTION_VARIABLES,
    STATE_VARIABLES,
    FlowMapping,
    RatioSumActionMapper,
    TD3ContractError,
)


class TD3PolicyLoadError(RuntimeError):
    """Raised when actor weights or their manifest cannot be trusted."""


def sha256_file(path: str | Path) -> str:
    """Return the lowercase SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_fields(
    data: Mapping[str, Any],
    names: Sequence[str],
    context: str,
) -> None:
    missing = [name for name in names if name not in data]
    if missing:
        raise TD3PolicyLoadError(f"{context} is missing fields: {missing}.")


class TD3Policy:
    """Frozen custom TD3 actor loaded from an exported deployment bundle.

    ``predict`` intentionally mirrors the return shape of Stable-Baselines3 so
    the original BioSMB loop can later switch models without being rewritten.
    """

    def __init__(
        self,
        actor: Actor,
        manifest: dict[str, Any],
        manifest_path: Path,
    ) -> None:
        self.actor = actor
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.manifest_sha256 = sha256_file(manifest_path)
        self.flow_mapping = FlowMapping.from_manifest(manifest)
        self.mapper = RatioSumActionMapper(self.flow_mapping)

    @classmethod
    def load(
        cls,
        manifest_path: str | Path,
        *,
        device: str | torch.device = "cpu",
    ) -> "TD3Policy":
        """Load and verify one weights-only actor bundle."""

        manifest_file = Path(manifest_path).resolve()
        if not manifest_file.is_file():
            raise TD3PolicyLoadError(f"TD3 manifest not found: {manifest_file}")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TD3PolicyLoadError("TD3 manifest is not valid JSON.") from exc
        if not isinstance(manifest, dict):
            raise TD3PolicyLoadError("TD3 manifest must be a JSON object.")

        _require_fields(
            manifest,
            [
                "schema_version",
                "algorithm",
                "weights_file",
                "weights_sha256",
                "weights_format",
                "state_dim",
                "state_variables",
                "state_bounds",
                "action_dim",
                "action_variables",
                "action_bounds",
                "actor",
                "action_mapping",
                "golden_tolerance",
                "golden_cases",
            ],
            "TD3 manifest",
        )
        if manifest["schema_version"] != 1:
            raise TD3PolicyLoadError("Unsupported TD3 manifest schema.")
        if manifest["algorithm"] != "custom_td3":
            raise TD3PolicyLoadError("Manifest algorithm is not custom_td3.")
        if manifest["weights_format"] != "pytorch_state_dict_weights_only":
            raise TD3PolicyLoadError("TD3 weights format is not approved.")
        if manifest["state_dim"] != 5 or manifest["action_dim"] != 2:
            raise TD3PolicyLoadError("TD3 state/action dimensions are incompatible.")
        if tuple(manifest["state_variables"]) != STATE_VARIABLES:
            raise TD3PolicyLoadError("TD3 state variable order is incompatible.")
        if tuple(manifest["action_variables"]) != ACTION_VARIABLES:
            raise TD3PolicyLoadError("TD3 action variable order is incompatible.")

        try:
            state_bounds = np.asarray(manifest["state_bounds"], dtype=float)
            action_bounds = np.asarray(manifest["action_bounds"], dtype=float)
        except (TypeError, ValueError) as exc:
            raise TD3PolicyLoadError("TD3 bounds must be numeric.") from exc
        if (
            state_bounds.shape != (5, 2)
            or not np.all(np.isfinite(state_bounds))
            or np.any(state_bounds[:, 0] >= state_bounds[:, 1])
        ):
            raise TD3PolicyLoadError("TD3 state bounds are invalid.")
        if not np.array_equal(
            action_bounds,
            np.asarray([[-1.0, 1.0], [-1.0, 1.0]]),
        ):
            raise TD3PolicyLoadError("TD3 action bounds must be [-1,1]^2.")

        try:
            FlowMapping.from_manifest(manifest)
        except TD3ContractError as exc:
            raise TD3PolicyLoadError(str(exc)) from exc

        weights_name = Path(str(manifest["weights_file"]))
        if weights_name.is_absolute() or weights_name.name != str(weights_name):
            raise TD3PolicyLoadError("Actor weights must be beside the manifest.")
        weights_path = (manifest_file.parent / weights_name).resolve()
        if not weights_path.is_file():
            raise TD3PolicyLoadError(f"TD3 actor weights not found: {weights_path}")
        if sha256_file(weights_path) != str(manifest["weights_sha256"]).lower():
            raise TD3PolicyLoadError("TD3 actor weight hash does not match manifest.")

        actor_config = manifest["actor"]
        if not isinstance(actor_config, Mapping):
            raise TD3PolicyLoadError("Manifest actor field must be an object.")
        _require_fields(
            actor_config,
            [
                "state_dim",
                "action_dim",
                "hidden_dims",
                "activation",
                "use_layernorm",
                "dropout",
                "max_action",
                "squash",
            ],
            "TD3 actor configuration",
        )
        if actor_config["state_dim"] != 5 or actor_config["action_dim"] != 2:
            raise TD3PolicyLoadError("Actor dimensions disagree with manifest.")
        if str(actor_config["squash"]).lower() != "tanh":
            raise TD3PolicyLoadError("Deployment actor must use tanh squashing.")
        if not np.isclose(float(actor_config["max_action"]), 1.0):
            raise TD3PolicyLoadError("Deployment actor max_action must equal one.")

        try:
            torch_device = torch.device(device)
            actor = Actor(
                state_dim=5,
                action_dim=2,
                hidden_dims=[int(value) for value in actor_config["hidden_dims"]],
                activation=str(actor_config["activation"]),
                use_layernorm=bool(actor_config["use_layernorm"]),
                dropout=float(actor_config["dropout"]),
                max_action=float(actor_config["max_action"]),
                squash=str(actor_config["squash"]),
            ).to(torch_device)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            raise TD3PolicyLoadError("Could not construct the TD3 actor.") from exc

        try:
            with weights_path.open("rb") as stream:
                state_dict = torch.load(
                    stream,
                    map_location=torch_device,
                    weights_only=True,
                )
        except Exception as exc:
            raise TD3PolicyLoadError("Could not safely load TD3 actor weights.") from exc
        if not isinstance(state_dict, Mapping):
            raise TD3PolicyLoadError("Actor file does not contain a state dictionary.")
        for name, tensor in state_dict.items():
            if not isinstance(name, str) or not isinstance(tensor, torch.Tensor):
                raise TD3PolicyLoadError("Actor state dictionary is malformed.")
            if not torch.isfinite(tensor).all():
                raise TD3PolicyLoadError(f"Actor tensor {name!r} is not finite.")
        try:
            actor.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise TD3PolicyLoadError(
                "Actor weights do not match the declared architecture."
            ) from exc
        actor.eval()
        actor.requires_grad_(False)

        policy = cls(actor, manifest, manifest_file)
        policy._verify_golden_cases()
        return policy

    @property
    def source_metadata(self) -> dict[str, Any]:
        source = self.manifest.get("source", {})
        return dict(source) if isinstance(source, Mapping) else {}

    def validate_state(self, state: Sequence[float]) -> np.ndarray:
        """Return one validated float32 state without running inference."""

        values = np.asarray(state, dtype=np.float32).reshape(-1)
        if values.shape != (5,):
            raise TD3ContractError(
                f"TD3 state must have shape (5,), received {values.shape}."
            )
        if not np.all(np.isfinite(values)):
            raise TD3ContractError("TD3 state contains NaN or infinity.")
        bounds = np.asarray(self.manifest["state_bounds"], dtype=float)
        if np.any(values < bounds[:, 0] - 1.0e-6) or np.any(
            values > bounds[:, 1] + 1.0e-6
        ):
            raise TD3ContractError("TD3 state is outside manifest bounds.")
        return values

    def _predict_array(self, state: Sequence[float]) -> np.ndarray:
        values = self.validate_state(state)

        device = next(self.actor.parameters()).device
        with torch.inference_mode():
            tensor = torch.as_tensor(values, device=device).reshape(1, -1)
            action = self.actor(tensor).cpu().numpy().reshape(-1)
        if action.shape != (2,) or not np.all(np.isfinite(action)):
            raise TD3ContractError("TD3 actor returned an invalid action.")
        if np.any(np.abs(action) > 1.0 + 1.0e-6):
            raise TD3ContractError("TD3 actor action is outside [-1,1].")
        return np.clip(action, -1.0, 1.0).astype(np.float32)

    def predict(
        self,
        observation: Sequence[float],
        state: Any = None,
        episode_start: Any = None,
        *,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, None]:
        """Return `(action, None)` like the existing SAC `predict` call."""

        del state, episode_start
        if deterministic is not True:
            raise TD3ContractError("Deployment TD3 inference must be deterministic.")
        return self._predict_array(observation), None

    def _verify_golden_cases(self) -> None:
        cases = self.manifest["golden_cases"]
        if not isinstance(cases, list) or len(cases) < 3:
            raise TD3PolicyLoadError("TD3 manifest requires three golden cases.")
        tolerance = float(self.manifest["golden_tolerance"])
        if not np.isfinite(tolerance) or tolerance <= 0 or tolerance > 1.0e-5:
            raise TD3PolicyLoadError("TD3 golden tolerance is invalid.")
        for index, case in enumerate(cases):
            if not isinstance(case, Mapping):
                raise TD3PolicyLoadError("TD3 golden case must be an object.")
            expected = np.asarray(case.get("expected_action"), dtype=np.float32)
            actual = self._predict_array(case.get("state"))
            if expected.shape != (2,) or not np.allclose(
                actual,
                expected,
                atol=tolerance,
                rtol=0.0,
            ):
                raise TD3PolicyLoadError(
                    f"TD3 golden inference case {index} did not match."
                )
