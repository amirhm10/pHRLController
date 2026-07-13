"""Actor used by the active custom TD3 configuration."""

from typing import List

import torch
import torch.nn as nn

from .helpers_net import build_network


class Actor(nn.Module):
    """The trained 5-to-2 ReLU actor with tanh action squashing."""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: List[int],
        activation: str = "relu",
        use_layernorm: bool = False,
        dropout: float = 0.0,
        max_action: float = 1.0,
        squash: str = "tanh",
    ) -> None:
        super().__init__()
        if activation != "relu" or use_layernorm or float(dropout) != 0.0:
            raise ValueError("Only the active ReLU/no-LayerNorm/no-dropout actor is supported.")
        if squash != "tanh":
            raise ValueError("Only the active tanh actor output is supported.")
        self.max_action = float(max_action)
        self.squash = "tanh"
        self.actor = build_network(
            in_dim=state_dim,
            hidden_dims=hidden_dims,
            out_dim=action_dim,
            prefix="pi",
        )

        output = getattr(self.actor, "pi_out")
        nn.init.uniform_(output.weight, -1.0e-3, 1.0e-3)
        nn.init.uniform_(output.bias, -1.0e-3, 1.0e-3)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return torch.tanh(self.actor(state)) * self.max_action
