"""Self-contained actor network used by the saved custom TD3 policy.

The module intentionally contains only inference-time network construction. It
does not import the training agent, critics, replay buffer, or exploration code.
Layer names match the training implementation so its actor state dictionary can
be loaded with ``strict=True``.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
import torch.nn as nn


def _get_activation(name: str) -> nn.Module:
    """Return the activation used by the training network builder."""

    normalized = name.lower()
    if normalized == "relu":
        return nn.ReLU(inplace=True)
    if normalized == "silu":
        return nn.SiLU(inplace=True)
    if normalized == "gelu":
        return nn.GELU()
    if normalized == "elu":
        return nn.ELU(inplace=True)
    if normalized == "tanh":
        return nn.Tanh()
    raise ValueError(f"Unknown activation {name!r}.")


def _initialize_layer(layer: nn.Linear, activation: str) -> None:
    """Mirror the training-time linear-layer initialization."""

    if activation.lower() in {"relu", "silu", "elu", "gelu"}:
        nn.init.kaiming_uniform_(layer.weight, nonlinearity="relu")
    else:
        nn.init.xavier_uniform_(layer.weight)
    nn.init.constant_(layer.bias, 0.0)


def _build_network(
    input_dim: int,
    hidden_dims: Sequence[int],
    output_dim: int,
    *,
    activation: str,
    use_layernorm: bool,
    dropout: float,
) -> nn.Sequential:
    """Build the exact named actor stack expected by saved weights."""

    layers = nn.Sequential()
    previous_dim = int(input_dim)
    for index, hidden_dim in enumerate(hidden_dims):
        hidden_dim = int(hidden_dim)
        linear = nn.Linear(previous_dim, hidden_dim)
        _initialize_layer(linear, activation)
        layers.add_module(f"pi_layer{index}", linear)
        if use_layernorm:
            layers.add_module(f"pi_norm{index}", nn.LayerNorm(hidden_dim))
        layers.add_module(f"pi_activation{index}", _get_activation(activation))
        if dropout > 0.0:
            layers.add_module(f"pi_dropout{index}", nn.Dropout(dropout))
        previous_dim = hidden_dim

    output = nn.Linear(previous_dim, int(output_dim))
    _initialize_layer(output, "linear")
    layers.add_module("pi_out", output)
    return layers


class Actor(nn.Module):
    """Actor-only custom TD3 network for deterministic deployment inference."""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: Sequence[int],
        *,
        activation: str = "relu",
        use_layernorm: bool = False,
        dropout: float = 0.0,
        max_action: float = 1.0,
        squash: str = "tanh",
    ) -> None:
        super().__init__()
        self.max_action = float(max_action)
        self.squash = squash.lower()
        self.actor = _build_network(
            input_dim=state_dim,
            hidden_dims=hidden_dims,
            output_dim=action_dim,
            activation=activation,
            use_layernorm=use_layernorm,
            dropout=float(dropout),
        )

        output = getattr(self.actor, "pi_out")
        nn.init.uniform_(output.weight, -1.0e-3, 1.0e-3)
        nn.init.uniform_(output.bias, -1.0e-3, 1.0e-3)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Return the normalized deterministic action for a state batch."""

        action = self.actor(state)
        if self.squash == "tanh":
            action = torch.tanh(action)
        return action * self.max_action
