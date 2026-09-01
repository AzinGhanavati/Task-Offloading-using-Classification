from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ActionOutcomePrediction:
    """Auxiliary information only; it never selects an action."""

    completion_time_s: float
    energy_j: float
    deadline_miss_probability: float

    def as_vector(self) -> list[float]:
        return [
            self.completion_time_s,
            self.energy_j,
            self.deadline_miss_probability,
        ]


class PredictionProvider(Protocol):
    def predict(
        self, raw_state: Sequence[float], action_mask: Sequence[int]
    ) -> Sequence[ActionOutcomePrediction]:
        """Return one outcome prediction per stable action slot."""

