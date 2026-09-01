from __future__ import annotations

import random

from simulation.entities.enums import OffloadAction


class RandomOffloadingPolicy:
    """Uniform only over valid slots; intended for offline data collection."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def select_action(self, context) -> OffloadAction:
        valid = [item.action for item in context.catalog if item.valid]
        if not valid:
            raise RuntimeError("no valid action is available")
        return self.rng.choice(valid)

