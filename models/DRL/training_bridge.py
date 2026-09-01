from __future__ import annotations

from dataclasses import dataclass

from simulation.entities.enums import OffloadAction
from simulation.entities.task import Task

from .adaptive_reward import AdaptiveRewardConfig, adaptive_reward
from .ppo_agent import PPOAgent


@dataclass(slots=True)
class _PendingDecision:
    order: int
    state: tuple[float, ...]
    mask: list[int]
    action: int
    log_probability: float
    value: float
    remaining_deadline_s: float
    predicted_completion_time_s: float
    task: Task
    finalized: bool = False


class PPOTrainingBridge:
    """Acts as both the SDN policy and delayed-outcome observer."""

    def __init__(
        self,
        agent: PPOAgent,
        *,
        energy_scope: str = "vehicle",
        reward_config: AdaptiveRewardConfig = AdaptiveRewardConfig(),
    ) -> None:
        if energy_scope not in {"vehicle", "system"}:
            raise ValueError("energy_scope must be vehicle or system")
        self.agent = agent
        self.energy_scope = energy_scope
        self.reward_config = reward_config
        self._pending: dict[str, _PendingDecision] = {}
        self._counter = 0

    def select_action(self, context) -> OffloadAction:
        action, log_probability, value = self.agent.act(
            context.augmented_state, context.action_mask
        )
        prediction = context.predictions[action]
        self._pending[context.task.task_id] = _PendingDecision(
            order=self._counter,
            state=context.augmented_state,
            mask=context.action_mask,
            action=action,
            log_probability=log_probability,
            value=value,
            remaining_deadline_s=context.raw_state.global_features[
                "remaining_deadline_s"
            ],
            predicted_completion_time_s=prediction.completion_time_s,
            task=context.task,
        )
        self._counter += 1
        return OffloadAction(action)

    def on_decision(self, task, context, action) -> None:
        # The policy callback above already captured log-probability and value.
        del task, context, action

    def on_final(self, task: Task) -> None:
        pending = self._pending.get(task.task_id)
        if pending is not None:
            pending.finalized = True

    def finish_episode(self) -> dict[str, float]:
        records = sorted(self._pending.values(), key=lambda item: item.order)
        records = [record for record in records if record.finalized]
        if not records:
            raise RuntimeError("PPO controlled no finalized decisions in this episode")
        rewards: list[float] = []
        for index, record in enumerate(records):
            task = record.task
            energy = (
                task.vehicle_energy_j
                if self.energy_scope == "vehicle"
                else task.system_energy_j
            )
            reward, _, _, _ = adaptive_reward(
                actual_completion_time_s=float(task.completion_time_s),
                actual_energy_j=energy,
                remaining_deadline_at_decision_s=record.remaining_deadline_s,
                predicted_completion_time_s=record.predicted_completion_time_s,
                deadline_missed=bool(task.deadline_missed),
                config=self.reward_config,
            )
            rewards.append(reward)
            self.agent.remember(
                state=record.state,
                action_mask=record.mask,
                action=record.action,
                log_probability=record.log_probability,
                value=record.value,
                reward=reward,
                done=index == len(records) - 1,
            )
        self._pending.clear()
        self._counter = 0
        return {
            "controlled_tasks": float(len(records)),
            "mean_reward": sum(rewards) / len(rewards),
        }

