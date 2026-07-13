"""Active one-step TD3 algorithm used for future BioSMB online adaptation."""

from __future__ import annotations

import os
import pickle
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .actor import Actor
from .critic import Critic
from .replay_buffer import PERRecentReplayBuffer


def get_device() -> torch.device:
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def set_global_seeds(seed: int) -> None:
    seed = int(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def hard_update(target: nn.Module, online: nn.Module) -> None:
    target.load_state_dict(online.state_dict())


@torch.no_grad()
def soft_update(target: nn.Module, online: nn.Module, tau: float) -> None:
    for target_parameter, parameter in zip(target.parameters(), online.parameters()):
        target_parameter.data.mul_(1.0 - tau).add_(tau * parameter.data)


@dataclass(frozen=True)
class GaussianNoiseSchedule:
    """Linear online exploration continuing below the offline final noise."""

    std_start: float = 0.02
    std_end: float = 0.01
    decay_steps: int = 5_000

    def value(self, step: int) -> float:
        fraction = min(1.0, int(step) / max(1, int(self.decay_steps)))
        return float(self.std_start + (self.std_end - self.std_start) * fraction)


def _column(tensor: torch.Tensor) -> torch.Tensor:
    return tensor if tensor.ndim == 2 else tensor.view(-1, 1)


class TD3Agent(nn.Module):
    """Reduced TD3 agent containing only the latest run's active code path."""

    def __init__(
        self,
        state_dim: int = 5,
        action_dim: int = 2,
        actor_hidden: List[int] | None = None,
        critic_hidden: List[int] | None = None,
        gamma: float = 0.97,
        actor_lr: float = 1.0e-4,
        critic_lr: float = 1.0e-3,
        batch_size: int = 64,
        grad_clip_norm: float = 10.0,
        policy_delay: int = 2,
        target_policy_smoothing_noise_std: float = 0.2,
        noise_clip: float = 0.5,
        max_action: float = 1.0,
        tau: float = 0.005,
        exploration_schedule: GaussianNoiseSchedule | None = None,
        std_start: float = 0.02,
        std_end: float = 0.01,
        std_decay_steps: int = 5_000,
        buffer_size: int = 60_000,
        replay_frac_per: float = 0.5,
        replay_frac_recent: float = 0.2,
        replay_recent_window: int = 1_000,
        replay_alpha: float = 0.6,
        replay_beta_start: float = 0.4,
        replay_beta_end: float = 1.0,
        replay_beta_steps: int = 50_000,
        device: Optional[torch.device] = None,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.device = device if device is not None else get_device()
        self.seed = None if seed is None else int(seed)
        if self.seed is not None:
            set_global_seeds(self.seed)

        actor_hidden = [128, 128] if actor_hidden is None else actor_hidden
        critic_hidden = [128, 128] if critic_hidden is None else critic_hidden
        self.gamma = float(gamma)
        self.actor_lr = float(actor_lr)
        self.critic_lr = float(critic_lr)
        self.batch_size = int(batch_size)
        self.grad_clip_norm = float(grad_clip_norm)
        self.policy_delay = int(policy_delay)
        self.t_std = float(target_policy_smoothing_noise_std)
        self.noise_clip = float(noise_clip)
        self.max_action = float(max_action)
        self.tau = float(tau)

        self.steps = 0
        self.train_steps = 0
        self.total_it = 0
        self.last_exploration_value = 0.0
        self._expl_sigma = 0.0

        self.actor = Actor(
            state_dim,
            action_dim,
            actor_hidden,
            max_action=max_action,
        ).to(self.device)
        self.actor_target = Actor(
            state_dim,
            action_dim,
            actor_hidden,
            max_action=max_action,
        ).to(self.device)
        self.critic = Critic(state_dim, action_dim, critic_hidden).to(self.device)
        self.critic_target = Critic(state_dim, action_dim, critic_hidden).to(self.device)
        hard_update(self.actor_target, self.actor)
        hard_update(self.critic_target, self.critic)

        self.actor_optimizer = optim.AdamW(
            self.actor.parameters(),
            lr=self.actor_lr,
            weight_decay=0.0,
        )
        self.critic_optimizer = optim.AdamW(
            self.critic.parameters(),
            lr=self.critic_lr,
            weight_decay=0.0,
        )
        self.loss_fn_critic = nn.SmoothL1Loss(reduction="none")
        self.buffer = PERRecentReplayBuffer(
            buffer_size,
            state_dim,
            action_dim,
            default_discount=self.gamma,
            alpha=replay_alpha,
            beta_start=replay_beta_start,
            beta_end=replay_beta_end,
            beta_steps=replay_beta_steps,
            frac_per=replay_frac_per,
            frac_recent=replay_frac_recent,
            recent_window=replay_recent_window,
        )
        self.expl_sched = exploration_schedule or GaussianNoiseSchedule(
            std_start=std_start,
            std_end=std_end,
            decay_steps=std_decay_steps,
        )

        self.actor_losses: list[float] = []
        self.critic_losses: list[float] = []
        self.critic_q1_trace: list[float] = []
        self.critic_q2_trace: list[float] = []
        self.critic_q_gap_trace: list[float] = []
        self.exploration_trace: list[float] = []
        self.exploration_magnitude_trace: list[float] = []
        self.action_saturation_trace: list[float] = []

    @torch.no_grad()
    def act_eval(self, state: np.ndarray, sigma_eval: float = 0.0) -> np.ndarray:
        del sigma_eval
        tensor = torch.as_tensor(state, dtype=torch.float32, device=self.device)
        return self.actor(tensor).clamp(
            -self.max_action,
            self.max_action,
        ).cpu().numpy()

    @torch.no_grad()
    def take_action(self, state: np.ndarray, explore: bool = False) -> np.ndarray:
        self.steps += 1
        tensor = torch.as_tensor(state, dtype=torch.float32, device=self.device)
        clean_action = self.actor(tensor).detach().cpu().numpy()
        action = clean_action.copy()
        self.last_exploration_value = 0.0
        self._expl_sigma = 0.0
        if explore:
            self._expl_sigma = self.expl_sched.value(self.steps)
            noise = np.random.randn(*action.shape) * self._expl_sigma
            action += noise
            self.last_exploration_value = float(np.mean(np.abs(noise)))
        action = np.clip(action, -self.max_action, self.max_action)
        self._record_action_diagnostics(action, clean_action if explore else None)
        return action

    def _record_action_diagnostics(self, action, clean_action=None) -> None:
        values = np.asarray(action, dtype=float)
        if clean_action is not None:
            self.last_exploration_value = float(
                np.mean(np.abs(values - np.asarray(clean_action, dtype=float)))
            )
        saturation = float(
            np.mean(np.abs(values) >= (self.max_action - 1.0e-6))
        )
        self.action_saturation_trace.append(saturation)
        self.exploration_trace.append(self.last_exploration_value)
        self.exploration_magnitude_trace.append(self.last_exploration_value)

    def push(self, state, action, reward, next_state, done) -> None:
        self.buffer.push(state, action, reward, next_state, bool(done))

    def train_step(self) -> dict | None:
        if len(self.buffer) < self.batch_size:
            return None
        train_index_before = self.train_steps
        (
            states,
            actions,
            rewards,
            next_states,
            dones,
            discounts,
            indices,
            importance_weights,
        ) = self.buffer.sample(self.batch_size, device=self.device)

        states = states.float()
        actions = actions.float()
        rewards = _column(rewards.float())
        next_states = next_states.float()
        dones = _column(dones.float())
        discounts = _column(discounts.float())
        importance_weights = _column(importance_weights.float())

        with torch.no_grad():
            base_next_action = self.actor_target(next_states)
            noise = torch.empty_like(base_next_action).normal_(0.0, self.t_std)
            noise.clamp_(-self.noise_clip, self.noise_clip)
            next_action = (base_next_action + noise).clip(
                -self.max_action,
                self.max_action,
            )
            target_q1, target_q2 = self.critic_target(next_states, next_action)
            bootstrap_q = torch.min(target_q1, target_q2) * (1.0 - dones)
            target = rewards + discounts * bootstrap_q

        q1, q2 = self.critic(states, actions)
        q1 = _column(q1)
        q2 = _column(q2)
        td1 = (target - q1).detach().abs().view(-1)
        td2 = (target - q2).detach().abs().view(-1)
        td_error = 0.5 * (td1 + td2)
        q1_loss = self.loss_fn_critic(q1, target)
        q2_loss = self.loss_fn_critic(q2, target)
        critic_loss = (importance_weights * (q1_loss + q2_loss)).mean()

        self.critic_optimizer.zero_grad(set_to_none=True)
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self.critic.parameters(), self.grad_clip_norm)
        self.critic_optimizer.step()

        self.critic_losses.append(float(critic_loss.item()))
        self.critic_q1_trace.append(float(q1.mean().item()))
        self.critic_q2_trace.append(float(q2.mean().item()))
        self.critic_q_gap_trace.append(float((q1 - q2).abs().mean().item()))

        actor_slot = self.total_it % self.policy_delay == 0
        actor_loss_value = None
        if actor_slot:
            current_action = self.actor(states)
            actor_loss = -torch.mean(
                self.critic.q1_forward(states, current_action)
            )
            actor_loss_value = float(actor_loss.item())
            self.actor_optimizer.zero_grad(set_to_none=True)
            actor_loss.backward()
            nn.utils.clip_grad_norm_(self.actor.parameters(), self.grad_clip_norm)
            self.actor_optimizer.step()
            self.actor_losses.append(actor_loss_value)
            soft_update(self.actor_target, self.actor, self.tau)
            soft_update(self.critic_target, self.critic, self.tau)

        self.total_it += 1
        self.train_steps += 1
        self.buffer.update_priorities(indices, td_error)
        return {
            "critic_updated": True,
            "actor_slot": bool(actor_slot),
            "actor_updated": bool(actor_slot),
            "critic_loss": float(critic_loss.item()),
            "actor_loss": actor_loss_value,
            "train_index_before": int(train_index_before),
            "train_index_after": int(self.train_steps),
        }

    def load(self, path: str) -> None:
        """Load the trusted original actor/critic checkpoint."""

        with open(path, "rb") as stream:
            payload = pickle.load(stream)
        self.actor.load_state_dict(payload["actor_state_dict"])
        self.critic.load_state_dict(payload["critic_state_dict"])
        hard_update(self.actor_target, self.actor)
        hard_update(self.critic_target, self.critic)
        self.actor_optimizer = optim.AdamW(
            self.actor.parameters(),
            lr=self.actor_lr,
            weight_decay=0.0,
        )
        self.critic_optimizer = optim.AdamW(
            self.critic.parameters(),
            lr=self.critic_lr,
            weight_decay=0.0,
        )

    def save(self, directory: str, prefix: str = "td3_online") -> str:
        os.makedirs(directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(directory, f"{prefix}_{timestamp}.pkl")
        payload = {
            "actor_state_dict": self.actor.state_dict(),
            "critic_state_dict": self.critic.state_dict(),
            "actor_target_state_dict": self.actor_target.state_dict(),
            "critic_target_state_dict": self.critic_target.state_dict(),
            "hparams": {
                "gamma": self.gamma,
                "actor_lr": self.actor_lr,
                "critic_lr": self.critic_lr,
                "batch_size": self.batch_size,
                "policy_delay": self.policy_delay,
                "tau": self.tau,
                "target_policy_smoothing_noise_std": self.t_std,
                "noise_clip": self.noise_clip,
                "max_action": self.max_action,
                "steps": self.steps,
                "train_steps": self.train_steps,
                "total_it": self.total_it,
            },
        }
        with open(path, "wb") as stream:
            pickle.dump(payload, stream)
        return path
