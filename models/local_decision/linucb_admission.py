from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from simulation.entities.enums import AdmissionDecision

from .base import AdmissionContext


@dataclass(slots=True)
class LinUCBAdmissionPolicy:
    """Two-arm contextual bandit: arm 0=local, arm 1=escalate."""

    feature_count: int = 7
    exploration_alpha: float = 0.5
    _a: list[np.ndarray] = field(init=False, repr=False)
    _b: list[np.ndarray] = field(init=False, repr=False)
    _pending: dict[str, tuple[int, np.ndarray]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._a = [np.eye(self.feature_count) for _ in range(2)]
        self._b = [np.zeros(self.feature_count) for _ in range(2)]

    def decide(self, context: AdmissionContext) -> AdmissionDecision:
        x = np.asarray(context.feature_vector(), dtype=np.float64)
        if x.shape != (self.feature_count,):
            raise ValueError("admission feature dimension changed")
        scores: list[float] = []
        for arm in range(2):
            a_inv = np.linalg.inv(self._a[arm])
            theta = a_inv @ self._b[arm]
            confidence = self.exploration_alpha * np.sqrt(x @ a_inv @ x)
            scores.append(float(theta @ x + confidence))
        arm = int(np.argmax(scores))
        self._pending[context.task.task_id] = (arm, x)
        return AdmissionDecision(arm)

    def update(self, task_id: str, reward: float) -> None:
        """Update after the selected task outcome becomes available."""

        try:
            arm, x = self._pending.pop(task_id)
        except KeyError as exc:
            raise KeyError(f"no pending LinUCB decision for {task_id!r}") from exc
        self._a[arm] += np.outer(x, x)
        self._b[arm] += float(reward) * x
