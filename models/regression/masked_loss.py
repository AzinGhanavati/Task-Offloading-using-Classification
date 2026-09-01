from __future__ import annotations

import torch
import torch.nn.functional as F


def masked_action_outcome_loss(
    predictions: torch.Tensor,
    selected_actions: torch.Tensor,
    targets: torch.Tensor,
    *,
    miss_loss_weight: float = 1.0,
    sample_weights: torch.Tensor | None = None,
) -> torch.Tensor:
    """Loss only for the action observed in each offline sample.

    The first two targets are standardized completion time and energy (MSE).
    The third target is deadline-miss probability (binary cross entropy).
    """

    if predictions.ndim != 3 or targets.ndim != 2:
        raise ValueError("expected predictions [B,A,3] and targets [B,3]")
    actions = selected_actions.long().view(-1, 1, 1)
    actions = actions.expand(-1, 1, predictions.size(-1))
    selected = predictions.gather(dim=1, index=actions).squeeze(1)
    continuous = F.mse_loss(
        selected[:, :2], targets[:, :2], reduction="none"
    ).mean(dim=1)
    miss = F.binary_cross_entropy_with_logits(
        selected[:, 2], targets[:, 2], reduction="none"
    )
    per_sample = continuous + miss_loss_weight * miss
    if sample_weights is None:
        return per_sample.mean()
    weights = sample_weights.to(per_sample).view(-1)
    weights = weights / weights.mean().clamp_min(1.0e-9)
    return (weights * per_sample).mean()
