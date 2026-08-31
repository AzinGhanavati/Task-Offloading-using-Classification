from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .enums import OffloadAction, TaskStatus

@dataclass(slots=True)
class Task:
    task_id: str
    creator_id: str
    arrival_time: float
    absolute_deadline: float
    data_size_bits: float
    cycles_per_bit: float
    required_compute_units: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    status: TaskStatus = TaskStatus.CREATED
    chosen_action: OffloadAction | None = None
    target_node_id: str | None = None
    gateway_edge_id: str | None = None
    decision_time: float | None = None
    
    transmission_finished_at: float | None = None
    queue_entered_at: float | None = None
    processing_started_at: float | None = None
    completed_at: float | None = None
    failure_reason: str | None = None
    
    wireless_time_s: float = 0.0
    wired_time_s: float = 0.0
    queue_waiting_time_s: float = 0.0
    processing_time_s: float = 0.0
    
    vehicle_tx_energy_j: float = 0.0
    vehicle_compute_energy_j: float = 0.0
    infrastructure_compute_energy_j: float = 0.0
    wired_energy_j: float = 0.0
    
    transmission_attempts: int = 0
    packet_loss_rate: float = 0.0
    achieved_wireless_rate_bps: float = 0.0
    achieved_wired_rate_bps: float = 0.0

    def __post_init__(self) -> None:
        if self.absolute_deadline < self.arrival_time:
            raise ValueError("absolute_deadline cannot precede arrival_time")
        if self.data_size_bits <= 0 or self.cycles_per_bit <= 0:
            raise ValueError("task data size and cycles_per_bit must be positive")

    @property
    def required_cycles(self) -> float:
        return self.data_size_bits * self.cycles_per_bit

    @property
    def remaining_deadline_at_arrival(self) -> float:
        return self.absolute_deadline - self.arrival_time

    @property
    def completion_time_s(self) -> float | None:
        if self.completed_at is None:
            return None
        return self.completed_at - self.arrival_time

    @property
    def slack_s(self) -> float | None:
        if self.completed_at is None:
            return None
        return self.absolute_deadline - self.completed_at

    @property
    def deadline_missed(self) -> bool | None:
        if self.status is TaskStatus.FAILED:
            return True
        slack = self.slack_s
        return None if slack is None else slack < 0.0

    @property
    def vehicle_energy_j(self) -> float:
        return self.vehicle_tx_energy_j + self.vehicle_compute_energy_j

    @property
    def system_energy_j(self) -> float:
        return (
            self.vehicle_energy_j
            + self.infrastructure_compute_energy_j
            + self.wired_energy_j
        )

    @property
    def succeeded(self) -> bool:
        return self.status is TaskStatus.COMPLETED