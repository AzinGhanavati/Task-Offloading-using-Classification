from __future__ import annotations

import torch
from torch import nn


class MultiActionOutcomeRegressor(nn.Module):
    """Shared trunk with one outcome vector for each stable action slot."""

    def __init__(
        self,
        *,
        input_dim: int,
        action_count: int = 5,
        outcome_count: int = 3,
        hidden_sizes: tuple[int, ...] = (256, 256, 128),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        previous = input_dim
        for size in hidden_sizes:
            layers.extend(
                [nn.Linear(previous, size), nn.LayerNorm(size), nn.ReLU()]
            )
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            previous = size
        self.trunk = nn.Sequential(*layers)
        self.head = nn.Linear(previous, action_count * outcome_count)
        self.action_count = action_count
        self.outcome_count = outcome_count

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        output = self.head(self.trunk(features))
        return output.view(-1, self.action_count, self.outcome_count)

