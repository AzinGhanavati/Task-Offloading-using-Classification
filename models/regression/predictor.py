from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ActionOutcomePrediction:
    """Auxiliary information only; it never selects an action.

    ``completion_time_s`` / ``energy_j`` are the physical predictions (seconds /
    joules) used by the adaptive reward to compute predicted slack.  The
    ``*_norm`` fields are the same values min-max scaled into [0, 1]; those are
    what get injected into the DRL state (block 6) so the whole observation
    stays in a consistent 0-1 range.
    """

    completion_time_s: float
    energy_j: float
    deadline_miss_probability: float
    completion_time_norm: float = 0.0
    energy_norm: float = 0.0

    def as_vector(self) -> list[float]:
        # Block 6: normalized 0-1 predictive features.
        return [
            self.completion_time_norm,
            self.energy_norm,
            self.deadline_miss_probability,
        ]


class PredictionProvider(Protocol):
    def predict(
        self, raw_state: Sequence[float], action_mask: Sequence[int]
    ) -> Sequence[ActionOutcomePrediction]:
        """Return one outcome prediction per stable action slot."""

