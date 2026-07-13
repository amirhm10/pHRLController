"""Network builder for the active ReLU TD3 architecture."""

from typing import List

import torch.nn as nn


def init_layer(layer: nn.Linear, non_linearity: str = "relu") -> None:
    """Use the same initialization as the original active implementation."""

    if non_linearity == "relu":
        nn.init.kaiming_uniform_(layer.weight, nonlinearity="relu")
    else:
        nn.init.xavier_uniform_(layer.weight)
    nn.init.constant_(layer.bias, 0.0)


def build_network(
    in_dim: int,
    hidden_dims: List[int],
    out_dim: int,
    *,
    prefix: str,
) -> nn.Sequential:
    """Build the active Linear-ReLU-Linear-ReLU-Linear network."""

    layers = nn.Sequential()
    previous_dim = int(in_dim)
    for index, hidden_dim in enumerate(hidden_dims):
        linear = nn.Linear(previous_dim, int(hidden_dim))
        init_layer(linear, non_linearity="relu")
        layers.add_module(f"{prefix}_layer{index}", linear)
        layers.add_module(f"{prefix}_activation{index}", nn.ReLU(inplace=True))
        previous_dim = int(hidden_dim)

    output = nn.Linear(previous_dim, int(out_dim))
    init_layer(output, non_linearity="linear")
    layers.add_module(f"{prefix}_out", output)
    return layers
