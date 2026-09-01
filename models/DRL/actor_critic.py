from __future__ import annotations

import torch
from torch import nn
from torch.distributions import Categorical


class MaskedActorCritic(nn.Module):
    def __init__(
        self,
        *,
        state_dim: int,
        action_count: int = 5,
        hidden_sizes: tuple[int, ...] = (256, 128),
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        previous = state_dim
        for size in hidden_sizes:
            layers.extend([nn.Linear(previous, size), nn.Tanh()])
            previous = size
        self.backbone = nn.Sequential(*layers)
        self.actor = nn.Linear(previous, action_count)
        self.critic = nn.Linear(previous, 1)

    def forward(
        self, states: torch.Tensor, action_masks: torch.Tensor
    ) -> tuple[Categorical, torch.Tensor]:
        latent = self.backbone(states)
        logits = self.actor(latent)
        if action_masks.shape != logits.shape:
            raise ValueError("action mask and actor logits must have equal shape")
        if torch.any(action_masks.sum(dim=-1) <= 0):
            raise ValueError("every state must have at least one valid action")
        masked_logits = logits.masked_fill(~action_masks.bool(), -1.0e9)
        return Categorical(logits=masked_logits), self.critic(latent).squeeze(-1)

