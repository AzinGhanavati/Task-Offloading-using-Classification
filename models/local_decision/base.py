from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from simulation.entities.enums import AdmissionDecision
from simulation.entities.task import Task


@dataclass(frozen=True, slots=True)
class AdmissionContext:
    task: Task
    now: float
    remaining_deadline_s: float
    local_service_s: float
    local_workload_s: float
    local_load: float
    average_external_load: float
    generation_rate: float
    qoe: float
    battery_level: float
    local_energy_j: float
    estimated_remote_delay_s: float
    estimated_remote_energy_j: float

    def feature_vector(self) -> list[float]:
        deadline = max(self.remaining_deadline_s, 1.0e-9)
        return [
            min(10.0, self.local_service_s / deadline),
            min(10.0, self.local_workload_s / deadline),
            self.local_load,
            self.average_external_load,
            min(10.0, self.generation_rate / 5.0),
            self.qoe,
            self.battery_level,
        ]


class LocalAdmissionPolicy(Protocol):
    def decide(self, context: AdmissionContext) -> AdmissionDecision:
        ...

