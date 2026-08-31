from __future__ import annotations
import heapq
import itertools
from dataclasses import dataclass, field
from simulation.entities.task import Task

@dataclass(order=True, slots=True)
class QueuedTask:
    absolute_deadline: float
    sequence: int
    task: Task = field(compare=False)
    service_time_s: float = field(compare=False)

class EDFQueue:
    """Non preemptive earliest deadline first queue."""
    def __init__(self, capacity: int | None = None) -> None:
        if capacity is not None and capacity <= 0:
            raise ValueError("capacity must be positive or None")
        self.capacity = capacity
        self._heap: list[QueuedTask] = []
        self._counter = itertools.count()
        self._total_service_time_s = 0.0

    def push(self, task: Task, service_time_s: float) -> None:
        if self.capacity is not None and len(self._heap) >= self.capacity:
            raise OverflowError("EDF queue capacity exceeded")
        if service_time_s < 0:
            raise ValueError("service_time_s cannot be negative")
        item = QueuedTask(
            absolute_deadline=task.absolute_deadline,
            sequence=next(self._counter),
            task=task,
            service_time_s=service_time_s,
        )
        heapq.heappush(self._heap, item)
        self._total_service_time_s += service_time_s

    def pop(self) -> QueuedTask:
        item = heapq.heappop(self._heap)
        self._total_service_time_s -= item.service_time_s
        return item

    def peek(self) -> QueuedTask | None:
        return None if not self._heap else self._heap[0]

    @property
    def total_service_time_s(self) -> float:
        return self._total_service_time_s

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)