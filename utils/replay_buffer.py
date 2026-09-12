from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class Transition:
    """A single experience tuple stored in the replay buffer.

    ``action`` and ``reward`` stay Python-native; the state arrays are kept as
    numpy so batches can be assembled without extra copies.
    """

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    action_mask: np.ndarray | None = None


class ReplayBuffer:
    """FIFO experience replay buffer for offline / offline-pretraining DRL.

    Stores transitions and samples uniform minibatches.  Used to bridge the
    offline data-collection phase (Phase 2) into a DQN-style bootstrap if the
    user prefers a value-based agent, or to warm-start evaluation.
    """

    def __init__(self, capacity: int = 100_000) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._items: list[Transition] = []
        self._write_index = 0
        self._rng = random.Random(0)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def full(self) -> bool:
        return len(self._items) >= self.capacity

    def add(self, transition: Transition) -> None:
        if len(self._items) < self.capacity:
            self._items.append(transition)
        else:
            self._items[self._write_index] = transition
        self._write_index = (self._write_index + 1) % self.capacity

    def extend(self, transitions: Sequence[Transition]) -> None:
        for transition in transitions:
            self.add(transition)

    def sample(self, batch_size: int) -> dict[str, Any]:
        """Sample a uniform minibatch and return stacked numpy arrays."""
        if batch_size > len(self._items):
            raise ValueError(
                f"batch_size {batch_size} exceeds buffer size {len(self._items)}"
            )
        indices = self._rng.sample(range(len(self._items)), batch_size)
        batch = [self._items[i] for i in indices]

        states = np.asarray([t.state for t in batch], dtype=np.float32)
        next_states = np.asarray([t.next_state for t in batch], dtype=np.float32)
        actions = np.asarray([t.action for t in batch], dtype=np.int64)
        rewards = np.asarray([t.reward for t in batch], dtype=np.float32)
        dones = np.asarray([t.done for t in batch], dtype=np.float32)
        masks = (
            np.asarray([t.action_mask for t in batch], dtype=np.int8)
            if all(t.action_mask is not None for t in batch)
            else None
        )
        return {
            "states": states,
            "next_states": next_states,
            "actions": actions,
            "rewards": rewards,
            "dones": dones,
            "action_masks": masks,
        }

    def clear(self) -> None:
        self._items.clear()
        self._write_index = 0
