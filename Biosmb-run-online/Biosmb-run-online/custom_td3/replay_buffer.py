"""Active mixed prioritized/recent/uniform one-step replay buffer."""

from __future__ import annotations

import numpy as np
import torch


class PERRecentReplayBuffer:
    """Replay used by the latest offline TD3 run.

    Sampling is 50 percent prioritized, 20 percent recent, and 30 percent
    uniform by default. Importance weights intentionally apply only to the
    prioritized subset, matching the trained implementation.
    """

    def __init__(
        self,
        capacity: int,
        state_dim: int,
        action_dim: int,
        default_discount: float = 1.0,
        eps: float = 1.0e-6,
        alpha: float = 0.6,
        beta_start: float = 0.4,
        beta_end: float = 1.0,
        beta_steps: int = 50_000,
        frac_per: float = 0.5,
        frac_recent: float = 0.2,
        recent_window: int = 1_000,
    ) -> None:
        self.capacity = int(capacity)
        self.state_dim = int(state_dim)
        self.action_dim = int(action_dim)
        self.default_discount = float(default_discount)
        self.ptr = 0
        self.size = 0
        self.step_counter = 0
        self.current_episode_id = 0

        self.states = np.zeros((self.capacity, self.state_dim), np.float32)
        self.actions = np.zeros((self.capacity, self.action_dim), np.float32)
        self.rewards = np.zeros(self.capacity, np.float32)
        self.next_states = np.zeros((self.capacity, self.state_dim), np.float32)
        self.dones = np.zeros(self.capacity, np.float32)
        self.discounts = np.zeros(self.capacity, np.float32)
        self.birth_step = np.zeros(self.capacity, np.int64)
        self.priorities = np.zeros(self.capacity, np.float32)

        self.eps = float(eps)
        self.alpha = float(alpha)
        self.beta_start = float(beta_start)
        self.beta_end = float(beta_end)
        self.beta_steps = int(beta_steps)
        self.beta_t = 0
        self._max_priority = 1.0
        self.frac_per = float(frac_per)
        self.frac_recent = float(frac_recent)
        self.recent_window = int(recent_window)

    def _beta(self) -> float:
        fraction = min(1.0, self.beta_t / max(1, self.beta_steps))
        return self.beta_start + fraction * (self.beta_end - self.beta_start)

    def push(self, state, action, reward, next_state, done) -> None:
        index = self.ptr
        done = bool(done)
        self.states[index] = state
        self.actions[index] = action
        self.rewards[index] = float(reward)
        self.next_states[index] = next_state
        self.dones[index] = float(done)
        self.discounts[index] = self.default_discount
        self.priorities[index] = self._max_priority
        self.birth_step[index] = self.step_counter
        self.step_counter += 1
        self.ptr = (self.ptr + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
        if done:
            self.current_episode_id += 1

    def sample(self, batch_size: int, device="cpu"):
        if self.size <= 0:
            raise ValueError("Cannot sample from an empty replay buffer.")
        k_per = int(batch_size * self.frac_per)
        k_recent = int(batch_size * self.frac_recent)
        k_uniform = int(batch_size) - k_per - k_recent

        all_indices = np.arange(self.size)
        recent_window = min(self.size, self.recent_window)
        cutoff = np.partition(
            self.birth_step[: self.size],
            -recent_window,
        )[-recent_window]
        recent_pool = all_indices[self.birth_step[: self.size] >= cutoff]

        recent_indices = np.random.choice(
            recent_pool,
            size=k_recent,
            replace=recent_pool.size < k_recent,
        )
        uniform_indices = np.random.choice(self.size, size=k_uniform, replace=True)

        if k_per > 0:
            priorities = np.maximum(self.priorities[: self.size], self.eps)
            probabilities = priorities**self.alpha
            probabilities /= probabilities.sum()
            prioritized_indices = np.random.choice(
                self.size,
                size=k_per,
                replace=True,
                p=probabilities,
            )
            weights = (self.size * probabilities[prioritized_indices]) ** (-self._beta())
            self.beta_t += 1
            weights /= np.maximum(weights.max(), 1.0e-12)
            prioritized_weights = weights.astype(np.float32)
        else:
            prioritized_indices = np.asarray([], dtype=np.int64)
            prioritized_weights = np.asarray([], dtype=np.float32)

        indices = np.concatenate(
            [prioritized_indices, recent_indices, uniform_indices]
        )
        importance_weights = np.concatenate(
            [
                prioritized_weights,
                np.ones(k_recent + k_uniform, dtype=np.float32),
            ]
        )
        return (
            torch.from_numpy(self.states[indices]).to(device),
            torch.from_numpy(self.actions[indices]).to(device),
            torch.from_numpy(self.rewards[indices]).to(device),
            torch.from_numpy(self.next_states[indices]).to(device),
            torch.from_numpy(self.dones[indices]).to(device),
            torch.from_numpy(self.discounts[indices]).to(device),
            indices,
            torch.from_numpy(importance_weights).to(device),
        )

    def update_priorities(self, indices, td_errors) -> None:
        if isinstance(td_errors, torch.Tensor):
            errors = td_errors.detach().abs().view(-1).cpu().numpy()
        else:
            errors = np.abs(td_errors).reshape(-1)
        priorities = np.clip(errors + self.eps, 1.0e-4, 1.0e4)
        self.priorities[indices] = priorities.astype(np.float32)
        self._max_priority = max(self._max_priority, float(priorities.max()))

    def __len__(self) -> int:
        return self.size
