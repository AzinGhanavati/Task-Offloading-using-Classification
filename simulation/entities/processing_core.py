from __future__ import annotations
from dataclasses import dataclass
from simulation.schedulers.edf import EDFQueue, QueuedTask
from .enums import TaskStatus
from .task import Task

@dataclass(slots=True)
class ProcessingCore:
    core_id: str
    frequency_hz: float
    energy_coefficient: float
    energy_exponent: float
    queue: EDFQueue
    current: QueuedTask | None = None
    started_at: float | None = None
    finishes_at: float | None = None

    def service_time(self, task: Task) -> float:
        return task.required_cycles / self.frequency_hz

    def enqueue(self, task: Task, now: float) -> None:
        task.status = TaskStatus.QUEUED
        task.queue_entered_at = now
        self.queue.push(task, self.service_time(task))

    def start_next(self, now: float) -> tuple[Task, float] | None:
        if self.current is not None or not self.queue:
            return None
        self.current = self.queue.pop()
        self.started_at = now
        self.finishes_at = now + self.current.service_time_s
        task = self.current.task
        task.status = TaskStatus.RUNNING
        task.processing_started_at = now
        if task.queue_entered_at is not None:
            task.queue_waiting_time_s += now - task.queue_entered_at
        task.processing_time_s += self.current.service_time_s
        return task, self.finishes_at

    def complete(self, now: float, tolerance: float = 1.0e-9) -> Task:
        if self.current is None or self.finishes_at is None:
            raise RuntimeError(f"core {self.core_id} has no running task")
        if now + tolerance < self.finishes_at:
            raise RuntimeError("completion event fired before service finished")
        task = self.current.task
        self.current = None
        self.started_at = None
        self.finishes_at = None
        return task

    def load_seconds(self, now: float) -> float:
        remaining = 0.0
        if self.current is not None and self.finishes_at is not None:
            remaining = max(0.0, self.finishes_at - now)
        return remaining + self.queue.total_service_time_s

    @property
    def queue_depth(self) -> int:
        return len(self.queue) + int(self.current is not None)