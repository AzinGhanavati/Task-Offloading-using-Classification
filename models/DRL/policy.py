from __future__ import annotations

from typing import Protocol, Sequence, TYPE_CHECKING

from simulation.entities.enums import OffloadAction

if TYPE_CHECKING:
    from simulation.entities.sdn_controller import DecisionContext


class OffloadingPolicy(Protocol):
    def select_action(self, context: "DecisionContext") -> OffloadAction:
        ...

