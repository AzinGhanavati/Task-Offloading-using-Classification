from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from simulation.entities.task import Task
from simulation.environment import VehicleSnapshot


@dataclass
class Scenario:
    """A re-runnable set of SUMO mobility snapshots and generated tasks.

    Mobility entries are ``(time, [VehicleSnapshot, ...])``.  Task templates
    carry only identity fields; ``make_tasks`` returns fresh copies so the same
    scenario can drive many DRL episodes (or data-collection passes) without
    leaking runtime state between resets.
    """

    mobility: list[tuple[float, list[VehicleSnapshot]]] = field(default_factory=list)
    task_templates: list[Task] = field(default_factory=list)

    def vehicle_snapshots(self) -> list[tuple[float, Sequence[VehicleSnapshot]]]:
        return list(self.mobility)

    def make_tasks(self) -> list[Task]:
        return [template.clone_for_reset() for template in self.task_templates]

    @property
    def time_span(self) -> tuple[float, float]:
        times = [time for time, _ in self.mobility]
        times.extend(task.arrival_time for task in self.task_templates)
        if not times:
            return (0.0, 0.0)
        return (min(times), max(times))

    def __len__(self) -> int:
        return len(self.task_templates)

    @classmethod
    def from_chunk_files(
        cls,
        vehicles_dir: str,
        tasks_dir: str,
    ) -> "Scenario":
        """Load every ``chunk_*.xml`` under the given directories."""
        from simulation.io.chunk_reader import (
            load_task_chunk,
            load_vehicle_chunk,
            numeric_chunk_paths,
        )

        scenario = cls()
        for path in numeric_chunk_paths(vehicles_dir):
            for time, snapshots in sorted(load_vehicle_chunk(path).items()):
                scenario.mobility.append((float(time), list(snapshots)))
        for path in numeric_chunk_paths(tasks_dir):
            for _time, tasks in sorted(load_task_chunk(path).items()):
                scenario.task_templates.extend(tasks)
        return scenario
