"""Online TD3 continuation using completed BioSMB control transitions."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch

from .agent import TD3Agent
from .controller import BioSMBTD3Policy
from .reward import PHRewardConfig, compute_ph_reward


class BioSMBOnlineTD3Trainer:
    """Load offline TD3 weights and perform one online update per transition."""

    def __init__(
        self,
        agent: TD3Agent,
        reward_config: PHRewardConfig,
        config: dict[str, Any],
        source_checkpoint: Path,
        checkpoint_directory: Path,
    ) -> None:
        self.agent = agent
        self.reward_config = reward_config
        self.config = config
        self.source_checkpoint = source_checkpoint
        self.checkpoint_directory = checkpoint_directory
        self.updates_per_step = int(config.get("updates_per_step", 1))
        self.checkpoint_interval_steps = int(
            config.get("checkpoint_interval_steps", 10)
        )
        if self.updates_per_step <= 0:
            raise ValueError("updates_per_step must be positive.")
        if self.checkpoint_interval_steps <= 0:
            raise ValueError("checkpoint_interval_steps must be positive.")
        self.last_checkpoint_path: str | None = None

    @classmethod
    def load(
        cls,
        config_path: str | Path,
        source_checkpoint: str | Path,
        checkpoint_directory: str | Path,
        *,
        device: str | torch.device = "cpu",
    ) -> "BioSMBOnlineTD3Trainer":
        """Create the active agent from JSON settings and trusted weights."""

        config_file = Path(config_path).resolve()
        checkpoint_file = Path(source_checkpoint).resolve()
        if not config_file.is_file():
            raise FileNotFoundError(f"Online TD3 config not found: {config_file}")
        if not checkpoint_file.is_file():
            raise FileNotFoundError(
                f"Online TD3 source checkpoint not found: {checkpoint_file}"
            )
        config = json.loads(config_file.read_text(encoding="utf-8"))
        with checkpoint_file.open("rb") as stream:
            checkpoint_payload = pickle.load(stream)
        checkpoint_architecture = checkpoint_payload.get("architecture", {})
        checkpoint_hparams = checkpoint_payload.get("hparams", {})
        state_dim = int(
            checkpoint_architecture.get("state_dim", config["state_dim"])
        )
        action_dim = int(
            checkpoint_architecture.get("action_dim", config["action_dim"])
        )
        actor_hidden = [
            int(value)
            for value in checkpoint_architecture.get(
                "actor_hidden", config["actor_hidden"]
            )
        ]
        critic_hidden = [
            int(value)
            for value in checkpoint_architecture.get(
                "critic_hidden", config["critic_hidden"]
            )
        ]
        gamma = float(checkpoint_hparams.get("gamma", config["gamma"]))
        config["resolved_source_checkpoint"] = {
            "checkpoint_kind": checkpoint_payload.get(
                "checkpoint_kind", "legacy_offline_checkpoint"
            ),
            "state_dim": state_dim,
            "action_dim": action_dim,
            "actor_hidden": actor_hidden,
            "critic_hidden": critic_hidden,
            "gamma": gamma,
        }
        replay = config["replay"]
        exploration = config["exploration"]
        agent = TD3Agent(
            state_dim=state_dim,
            action_dim=action_dim,
            actor_hidden=actor_hidden,
            critic_hidden=critic_hidden,
            gamma=gamma,
            actor_lr=float(config["actor_lr"]),
            critic_lr=float(config["critic_lr"]),
            batch_size=int(config["batch_size"]),
            policy_delay=int(config["policy_delay"]),
            target_policy_smoothing_noise_std=float(
                config["target_policy_smoothing_noise_std"]
            ),
            noise_clip=float(config["noise_clip"]),
            tau=float(config["tau"]),
            std_start=float(exploration["std_start"]),
            std_end=float(exploration["std_end"]),
            std_decay_steps=int(exploration["decay_steps"]),
            buffer_size=int(config["buffer_size"]),
            replay_frac_per=float(replay["prioritized_fraction"]),
            replay_frac_recent=float(replay["recent_fraction"]),
            replay_recent_window=int(replay["recent_window"]),
            replay_alpha=float(replay["alpha"]),
            replay_beta_start=float(replay["beta_start"]),
            replay_beta_end=float(replay["beta_end"]),
            replay_beta_steps=int(replay["beta_steps"]),
            device=torch.device(device),
            seed=int(config.get("seed", 7)),
        )
        agent.load(str(checkpoint_file))

        reward_values = dict(config["reward"])
        reward_values.pop("mode", None)
        reward_config = PHRewardConfig(**reward_values)
        return cls(
            agent=agent,
            reward_config=reward_config,
            config=config,
            source_checkpoint=checkpoint_file,
            checkpoint_directory=Path(checkpoint_directory).resolve(),
        )

    def verify_initial_actor(self, deployment_model: BioSMBTD3Policy) -> None:
        """Require the offline training actor to match the deployed actor."""

        tolerance = float(deployment_model.manifest["golden_tolerance"])
        for index, case in enumerate(deployment_model.manifest["golden_cases"]):
            state = np.asarray(case["state"], dtype=np.float32)
            deployed_action = deployment_model.predict(state)[0]
            training_action = self.agent.act_eval(state)
            if not np.allclose(
                training_action,
                deployed_action,
                atol=tolerance,
                rtol=0.0,
            ):
                raise ValueError(
                    f"Online TD3 actor differs from deployment actor in case {index}."
                )

    def take_action(
        self,
        state: Sequence[float],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Return one clipped exploratory action and its diagnostics."""

        action = self.agent.take_action(
            np.asarray(state, dtype=np.float32),
            explore=True,
        ).astype(np.float32)
        saturation = (
            float(self.agent.action_saturation_trace[-1])
            if self.agent.action_saturation_trace
            else 0.0
        )
        return action, {
            "action_source": "online_td3_exploration",
            "exploration_sigma": float(self.agent._expl_sigma),
            "exploration_magnitude": float(
                self.agent.last_exploration_value
            ),
            "action_saturation_fraction": saturation,
            "online_action_step": int(self.agent.steps),
        }

    def record_transition(
        self,
        *,
        state: Sequence[float],
        action: Sequence[float],
        reward_target_ph: float,
        measured_ph_after: float,
        previous_action: Sequence[float],
        default_action: Sequence[float],
        next_state: Sequence[float],
        buffer_sum: float,
        previous_buffer_sum: float,
        buffer_sum_min: float,
        buffer_sum_max: float,
        economic_flow_fraction: float,
        done: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compute, store, and learn from one completed BioSMB transition."""

        reward_breakdown = compute_ph_reward(
            target_ph=reward_target_ph,
            ph=measured_ph_after,
            action=action,
            previous_action=previous_action,
            default_action=default_action,
            config=self.reward_config,
            buffer_sum=buffer_sum,
            previous_buffer_sum=previous_buffer_sum,
            buffer_sum_min=buffer_sum_min,
            buffer_sum_max=buffer_sum_max,
            economic_flow_fraction=economic_flow_fraction,
        )
        self.agent.push(
            np.asarray(state, dtype=np.float32),
            np.asarray(action, dtype=np.float32),
            reward_breakdown.reward,
            np.asarray(next_state, dtype=np.float32),
            bool(done),
        )

        update_records = []
        for _ in range(self.updates_per_step):
            update = self.agent.train_step()
            if update is not None:
                update_records.append(update)
        latest_update = update_records[-1] if update_records else None

        reward_info = reward_breakdown.to_info_dict()
        training_info = {
            "enabled": True,
            "transition_stored": True,
            "done": bool(done),
            "buffer_size": int(len(self.agent.buffer)),
            "buffer_capacity": int(self.agent.buffer.capacity),
            "batch_size": int(self.agent.batch_size),
            "updates_requested": self.updates_per_step,
            "updates_completed": len(update_records),
            "train_updated": latest_update is not None,
            "train_steps": int(self.agent.train_steps),
            "critic_loss": (
                None
                if latest_update is None
                else float(latest_update["critic_loss"])
            ),
            "actor_updated": (
                False
                if latest_update is None
                else bool(latest_update["actor_updated"])
            ),
            "actor_loss": (
                None
                if latest_update is None
                or latest_update["actor_loss"] is None
                else float(latest_update["actor_loss"])
            ),
            "source_checkpoint": str(self.source_checkpoint),
            "last_checkpoint_path": self.last_checkpoint_path,
        }
        return reward_info, training_info

    def should_save(self, completed_steps: int) -> bool:
        return int(completed_steps) % self.checkpoint_interval_steps == 0

    def save(self, prefix: str = "td3_online") -> str:
        """Save a complete trusted local online-resume checkpoint."""

        path = self.agent.save(str(self.checkpoint_directory), prefix=prefix)
        self.last_checkpoint_path = path
        return path
