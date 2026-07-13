"""Twin critic used by the active custom TD3 configuration."""

from typing import List

import torch
import torch.nn as nn

from .helpers_net import build_network


class Critic(nn.Module):
    """Two independent Q networks over the five-state/two-action input."""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: List[int],
        activation: str = "relu",
        use_layernorm: bool = False,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if activation != "relu" or use_layernorm or float(dropout) != 0.0:
            raise ValueError("Only the active ReLU/no-LayerNorm/no-dropout critic is supported.")
        input_dim = int(state_dim) + int(action_dim)
        self.q1_network = build_network(
            in_dim=input_dim,
            hidden_dims=hidden_dims,
            out_dim=1,
            prefix="q1",
        )
        self.q2_network = build_network(
            in_dim=input_dim,
            hidden_dims=hidden_dims,
            out_dim=1,
            prefix="q2",
        )

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        values = torch.cat([state, action], dim=1)
        return self.q1_network(values), self.q2_network(values)

    def q1_forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        return self.q1_network(torch.cat([state, action], dim=1))
