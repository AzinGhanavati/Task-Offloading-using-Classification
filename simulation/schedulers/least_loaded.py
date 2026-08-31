from __future__ import annotations
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from simulation.entities.compute_node import ProcessingCore
    from simulation.entities.task import Task

class LeastLoadedCoreMapper:
    """Maps a task to the core with the smallest remaining workload."""
    def select_core(
        self,
        cores: Sequence["ProcessingCore"],
        task: "Task",
        now: float,
    ) -> "ProcessingCore":
        del task
        if not cores:
            raise ValueError("at least one core is required")
        return min(
            cores,
            key=lambda core: (core.load_seconds(now), core.queue_depth, core.core_id),
        )