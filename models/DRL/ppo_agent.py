from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch

from config.drl_config import PPOConfig
from simulation.entities.enums import OffloadAction

from .actor_critic import MaskedActorCritic


@dataclass(slots=True)
class RolloutBuffer:
    states: list[np.ndarray] = field(default_factory=list)
    action_masks: list[np.ndarray] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)
    log_probabilities: list[float] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)

    def clear(self) -> None:
        self.states.clear()
        self.action_masks.clear()
        self.actions.clear()
        self.log_probabilities.clear()
        self.values.clear()
        self.rewards.clear()
        self.dones.clear()


class PPOAgent:
    """Masked discrete PPO over the fixed five action slots."""

    def __init__(
        self,
        *,
        state_dim: int,
        config: PPOConfig = PPOConfig(),
        device: str = "cpu",
    ) -> None:
        self.config = config
        self.device = torch.device(device)
        self.network = MaskedActorCritic(
            state_dim=state_dim,
            action_count=config.action_count,
            hidden_sizes=config.hidden_sizes,
        ).to(self.device)
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=config.learning_rate
        )
        self.buffer = RolloutBuffer()

    def select_action(self, context) -> OffloadAction:
        action, _, _ = self.act(context.augmented_state, context.action_mask)
        return OffloadAction(action)

    def act(
        self, state: tuple[float, ...] | list[float], action_mask: list[int]
    ) -> tuple[int, float, float]:
        states = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
        masks = torch.tensor(action_mask, dtype=torch.bool, device=self.device).unsqueeze(0)
        with torch.no_grad():
            distribution, value = self.network(states, masks)
            action = distribution.sample()
            log_probability = distribution.log_prob(action)
        return int(action.item()), float(log_probability.item()), float(value.item())

    def remember(
        self,
        *,
        state: tuple[float, ...] | list[float],
        action_mask: list[int],
        action: int,
        log_probability: float,
        value: float,
        reward: float,
        done: bool,
    ) -> None:
        self.buffer.states.append(np.asarray(state, dtype=np.float32))
        self.buffer.action_masks.append(np.asarray(action_mask, dtype=np.bool_))
        self.buffer.actions.append(int(action))
        self.buffer.log_probabilities.append(float(log_probability))
        self.buffer.values.append(float(value))
        self.buffer.rewards.append(float(reward))
        self.buffer.dones.append(bool(done))

    def update(self, last_value: float = 0.0) -> dict[str, float]:
        if not self.buffer.states:
            raise RuntimeError("rollout buffer is empty")
        advantages, returns = self._gae(last_value)
        states = torch.as_tensor(np.stack(self.buffer.states), device=self.device)
        masks = torch.as_tensor(np.stack(self.buffer.action_masks), device=self.device)
        actions = torch.as_tensor(self.buffer.actions, device=self.device)
        old_log_probs = torch.as_tensor(
            self.buffer.log_probabilities, dtype=torch.float32, device=self.device
        )
        advantages_t = torch.as_tensor(advantages, device=self.device)
        returns_t = torch.as_tensor(returns, device=self.device)
        advantages_t = (advantages_t - advantages_t.mean()) / (
            advantages_t.std(unbiased=False) + 1.0e-8
        )
        size = states.size(0)
        last_metrics: dict[str, float] = {}
        for _ in range(self.config.update_epochs):
            indices = torch.randperm(size, device=self.device)
            for start in range(0, size, self.config.minibatch_size):
                batch = indices[start : start + self.config.minibatch_size]
                distribution, values = self.network(states[batch], masks[batch])
                new_log_probs = distribution.log_prob(actions[batch])
                ratio = torch.exp(new_log_probs - old_log_probs[batch])
                unclipped = ratio * advantages_t[batch]
                clipped = torch.clamp(
                    ratio,
                    1.0 - self.config.clip_ratio,
                    1.0 + self.config.clip_ratio,
                ) * advantages_t[batch]
                policy_loss = -torch.minimum(unclipped, clipped).mean()
                value_loss = torch.nn.functional.mse_loss(values, returns_t[batch])
                entropy = distribution.entropy().mean()
                loss = (
                    policy_loss
                    + self.config.value_coefficient * value_loss
                    - self.config.entropy_coefficient * entropy
                )
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(), self.config.max_gradient_norm
                )
                self.optimizer.step()
                last_metrics = {
                    "loss": float(loss.item()),
                    "policy_loss": float(policy_loss.item()),
                    "value_loss": float(value_loss.item()),
                    "entropy": float(entropy.item()),
                }
        self.buffer.clear()
        return last_metrics

    def _gae(self, last_value: float) -> tuple[np.ndarray, np.ndarray]:
        rewards = self.buffer.rewards
        values = self.buffer.values + [float(last_value)]
        advantages = np.zeros(len(rewards), dtype=np.float32)
        gae = 0.0
        for index in reversed(range(len(rewards))):
            nonterminal = 1.0 - float(self.buffer.dones[index])
            delta = (
                rewards[index]
                + self.config.discount_gamma * values[index + 1] * nonterminal
                - values[index]
            )
            gae = (
                delta
                + self.config.discount_gamma
                * self.config.gae_lambda
                * nonterminal
                * gae
            )
            advantages[index] = gae
        returns = advantages + np.asarray(self.buffer.values, dtype=np.float32)
        return advantages, returns
