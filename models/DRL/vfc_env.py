<<<<<<< HEAD
from __future__ import annotations

from typing import Any, Dict, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from config.hyperparameters import AUGMENTED_STATE_DIM, NUM_ACTIONS
from models.DRL.adaptive_reward import AdaptiveRewardConfig, adaptive_reward
from simulation.entities.enums import OffloadAction


class VFCOffloadingEnv(gym.Env):
    """Gymnasium wrapper around the discrete-event VFC simulator.

    Each step corresponds to one offloading decision.  The observation is the
    augmented state (normalized blocks 1-5 concatenated with the multi-head
    regression outputs, block 6).  The action is one of the 5 stable slots
    (Local, Candidate_1..3, Cloud); invalid slots are excluded via the
    action mask (compatible with ``sb3_contrib`` MaskablePPO).

    The reward is the slack-adaptive objective:

        S_pred = D_remaining - T_pred
        U      = 1 / (1 + exp(S_pred / tau))
        alpha  = alpha_min + U * (alpha_max - alpha_min)
        beta   = beta_max - U * (beta_max - beta_min)
        R      = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss

    T_scale and E_scale are data-driven (dataset max values from the
    regression checkpoint), so no hand-picked constants appear in the reward.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        simulation_env,
        scenario,
        state_dim: int = AUGMENTED_STATE_DIM,
        energy_scope: str = "vehicle",
        reward_config: AdaptiveRewardConfig | None = None,
        failed_penalty: float = 1.0,
    ) -> None:
        super().__init__()
        if energy_scope not in {"vehicle", "system"}:
            raise ValueError("energy_scope must be 'vehicle' or 'system'")
        self.sim_env = simulation_env
        self.scenario = scenario
        self.energy_scope = energy_scope
        self.reward_config = reward_config or self._default_reward_config()
        self.failed_penalty = float(failed_penalty)

        self.action_space = spaces.Discrete(NUM_ACTIONS)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(state_dim,), dtype=np.float32
        )
        self.current_state = np.zeros(state_dim, dtype=np.float32)
        self.current_mask = np.ones(NUM_ACTIONS, dtype=np.int8)
        # task_id -> (decision-time context, chosen action), for reward credit.
        self._decision_records: dict[str, tuple] = {}

    def _default_reward_config(self) -> AdaptiveRewardConfig:
        """Derive T_scale / E_scale from the regression dataset max values."""
        predictor = getattr(self.sim_env, "predictor", None)
        reward_scales = getattr(predictor, "reward_scales", None)
        if callable(reward_scales):
            time_scale, energy_scale = reward_scales()
        elif reward_scales is not None:
            time_scale, energy_scale = reward_scales
        else:
            return AdaptiveRewardConfig()
        return AdaptiveRewardConfig(
            delay_scale_s=time_scale, energy_scale_j=energy_scale
        )

    def reset(
        self,
        seed: int | None = None,
        options: Dict[str, Any] | None = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self._decision_records.clear()
        context = self.sim_env.reset_for_episode(self.scenario)
        self._update_state(context)
        info = {"action_mask": self.current_mask}
        return self.current_state, info

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        context = self.sim_env.current_context
        current_task = self.sim_env.current_task
        # Register the decision we are about to make so any task that completes
        # this step (including this one, e.g. a fast local execution) can be
        # credited with a reward computed from its decision-time predictions.
        self._decision_records[current_task.task_id] = (context, int(action))

        completed, failed, next_context, done = self.sim_env.apply_and_advance(
            OffloadAction(action)
        )

        reward = 0.0
        for task in completed:
            record = self._decision_records.pop(task.task_id, None)
            if record is None:
                continue
            decision_context, chosen = record
            predicted_time_s = decision_context.predictions[chosen].completion_time_s
            remaining_deadline = max(
                0.0, decision_context.task.absolute_deadline - decision_context.now
            )
            energy = (
                task.vehicle_energy_j
                if self.energy_scope == "vehicle"
                else task.system_energy_j
            )
            step_reward, _, _, _ = adaptive_reward(
                actual_completion_time_s=float(task.completion_time_s),
                actual_energy_j=energy,
                remaining_deadline_at_decision_s=remaining_deadline,
                predicted_completion_time_s=predicted_time_s,
                deadline_missed=bool(task.deadline_missed),
                config=self.reward_config,
            )
            reward += step_reward
        for _task in failed:
            reward -= self.failed_penalty

        if next_context is not None:
            self._update_state(next_context)

        info = {"action_mask": self.current_mask}
        return self.current_state, float(reward), bool(done), False, info

    def action_masks(self) -> np.ndarray:
        """Mask required by ``sb3_contrib.ActionMasker`` (True = allowed)."""
        return self.current_mask.astype(bool)

    def _update_state(self, context) -> None:
        self.current_state = np.asarray(context.augmented_state, dtype=np.float32)
        self.current_mask = np.asarray(context.action_mask, dtype=np.int8)
=======
from __future__ import annotations

from typing import Any, Dict, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from config.hyperparameters import AUGMENTED_STATE_DIM, NUM_ACTIONS
from models.DRL.adaptive_reward import AdaptiveRewardConfig, adaptive_reward
from simulation.entities.enums import OffloadAction


class VFCOffloadingEnv(gym.Env):
    """Gymnasium wrapper around the discrete-event VFC simulator.

    Each step corresponds to one offloading decision.  The observation is the
    augmented state (normalized blocks 1-5 concatenated with the multi-head
    regression outputs, block 6).  The action is one of the 5 stable slots
    (Local, Candidate_1..3, Cloud); invalid slots are excluded via the
    action mask (compatible with ``sb3_contrib`` MaskablePPO).

    The reward is the slack-adaptive objective:

        S_pred = D_remaining - T_pred
        U      = 1 / (1 + exp(S_pred / tau))
        alpha  = alpha_min + U * (alpha_max - alpha_min)
        beta   = beta_max - U * (beta_max - beta_min)
        R      = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss

    T_scale and E_scale are data-driven (dataset max values from the
    regression checkpoint), so no hand-picked constants appear in the reward.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        simulation_env,
        scenario,
        state_dim: int = AUGMENTED_STATE_DIM,
        energy_scope: str = "vehicle",
        reward_config: AdaptiveRewardConfig | None = None,
        failed_penalty: float = 1.0,
    ) -> None:
        super().__init__()
        if energy_scope not in {"vehicle", "system"}:
            raise ValueError("energy_scope must be 'vehicle' or 'system'")
        self.sim_env = simulation_env
        self.scenario = scenario
        self.energy_scope = energy_scope
        self.reward_config = reward_config or self._default_reward_config()
        self.failed_penalty = float(failed_penalty)

        self.action_space = spaces.Discrete(NUM_ACTIONS)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(state_dim,), dtype=np.float32
        )
        self.current_state = np.zeros(state_dim, dtype=np.float32)
        self.current_mask = np.ones(NUM_ACTIONS, dtype=np.int8)
        # task_id -> (decision-time context, chosen action), for reward credit.
        self._decision_records: dict[str, tuple] = {}

    def _default_reward_config(self) -> AdaptiveRewardConfig:
        """Derive T_scale / E_scale from the regression dataset max values."""
        predictor = getattr(self.sim_env, "predictor", None)
        reward_scales = getattr(predictor, "reward_scales", None)
        if callable(reward_scales):
            time_scale, energy_scale = reward_scales()
        elif reward_scales is not None:
            time_scale, energy_scale = reward_scales
        else:
            return AdaptiveRewardConfig()
        return AdaptiveRewardConfig(
            delay_scale_s=time_scale, energy_scale_j=energy_scale
        )

    def reset(
        self,
        seed: int | None = None,
        options: Dict[str, Any] | None = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self._decision_records.clear()
        context = self.sim_env.reset_for_episode(self.scenario)
        self._update_state(context)
        info = {"action_mask": self.current_mask}
        return self.current_state, info

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        context = self.sim_env.current_context
        current_task = self.sim_env.current_task
        # Register the decision we are about to make so any task that completes
        # this step (including this one, e.g. a fast local execution) can be
        # credited with a reward computed from its decision-time predictions.
        self._decision_records[current_task.task_id] = (context, int(action))

        completed, failed, next_context, done = self.sim_env.apply_and_advance(
            OffloadAction(action)
        )

        reward = 0.0
        for task in completed:
            record = self._decision_records.pop(task.task_id, None)
            if record is None:
                continue
            decision_context, chosen = record
            predicted_time_s = decision_context.predictions[chosen].completion_time_s
            remaining_deadline = max(
                0.0, decision_context.task.absolute_deadline - decision_context.now
            )
            energy = (
                task.vehicle_energy_j
                if self.energy_scope == "vehicle"
                else task.system_energy_j
            )
            step_reward, _, _, _ = adaptive_reward(
                actual_completion_time_s=float(task.completion_time_s),
                actual_energy_j=energy,
                remaining_deadline_at_decision_s=remaining_deadline,
                predicted_completion_time_s=predicted_time_s,
                deadline_missed=bool(task.deadline_missed),
                config=self.reward_config,
            )
            reward += step_reward
        for _task in failed:
            reward -= self.failed_penalty

        if next_context is not None:
            self._update_state(next_context)

        info = {"action_mask": self.current_mask}
        return self.current_state, float(reward), bool(done), False, info

    def action_masks(self) -> np.ndarray:
        """Mask required by ``sb3_contrib.ActionMasker`` (True = allowed)."""
        return self.current_mask.astype(bool)

    def _update_state(self, context) -> None:
        self.current_state = np.asarray(context.augmented_state, dtype=np.float32)
        self.current_mask = np.asarray(context.action_mask, dtype=np.int8)
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
