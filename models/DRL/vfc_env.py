import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Any, Dict, Tuple

from simulation.entities.enums import OffloadAction
from models.rl.adaptive_reward import AdaptiveRewardConfig, adaptive_reward

class VFCOffloadingEnv(gym.Env):
    """
    Standard Gymnasium environment for VFC task offloading.
    """
    def __init__(
        self, 
        simulation_env,
        state_dim: int, 
        energy_scope: str = "vehicle",
        reward_config: AdaptiveRewardConfig = None
    ):
        super().__init__()
        self.sim_env = simulation_env
        self.energy_scope = energy_scope
        self.reward_config = reward_config or AdaptiveRewardConfig()

        # 5 discrete actions: Local, Cloud, Candidate_1, Candidate_2, Candidate_3
        self.action_space = spaces.Discrete(5)
        
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(state_dim,), dtype=np.float32
        )

        self.current_state = np.zeros(state_dim, dtype=np.float32)
        self.current_mask = np.ones(5, dtype=np.int8)
        self.pending_decisions = {}

    def reset(self, seed: int | None = None, options: Dict[str, Any] | None = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self.pending_decisions.clear()
        
        # Reset the core physical simulator
        self.sim_env.reset()
        
        # Advance simulation until the first task requires an offloading decision
        context = self.sim_env.advance_to_next_decision()
        self._update_current_state(context)

        info = {"action_mask": self.current_mask}
        return self.current_state, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        current_task_id = self.sim_env.current_task.task_id
        
        # Store predicted states for delayed adaptive reward calculation
        self.pending_decisions[current_task_id] = {
            "remaining_deadline_s": self.sim_env.current_context.raw_state.global_features["remaining_deadline_s"],
            "predicted_time_s": self.sim_env.current_context.predictions[action].completion_time_s
        }

        # Apply action and resume simulation until the next decision event
        completed_tasks, next_context, is_done = self.sim_env.apply_and_advance(OffloadAction(action))

        # Calculate reward for any tasks that finished during this step
        step_reward = 0.0
        for task in completed_tasks:
            if task.task_id in self.pending_decisions:
                decision_info = self.pending_decisions.pop(task.task_id)
                energy = task.vehicle_energy_j if self.energy_scope == "vehicle" else task.system_energy_j
                
                reward, _, _, _ = adaptive_reward(
                    actual_completion_time_s=float(task.completion_time_s),
                    actual_energy_j=energy,
                    remaining_deadline_at_decision_s=decision_info["remaining_deadline_s"],
                    predicted_completion_time_s=decision_info["predicted_time_s"],
                    deadline_missed=bool(task.deadline_missed),
                    config=self.reward_config,
                )
                step_reward += reward

        if not is_done:
            self._update_current_state(next_context)

        terminated = is_done
        truncated = False
        info = {"action_mask": self.current_mask}

        return self.current_state, step_reward, terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """
        Required by sb3_contrib.MaskablePPO to filter invalid actions.
        """
        return self.current_mask.astype(bool)

    def _update_current_state(self, context) -> None:
        self.current_state = np.asarray(context.augmented_state, dtype=np.float32)
        self.current_mask = np.asarray(context.action_mask, dtype=np.int8)