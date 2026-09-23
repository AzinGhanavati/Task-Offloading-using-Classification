<<<<<<< HEAD
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import TaskStatus


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
    chosen_action: "Any" = None
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

    @classmethod
    def from_generator_record(
        cls,
        *,
        task_id: str,
        creator_id: str,
        timestep: float,
        deadline: float,
        data_size_mbit: float,
        kilo_cycles_per_bit: float,
        required_compute_units: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Task":
        """Build a Task from a SUMO/chunk generator record.

        The generator stores ``dataSize`` in Mbit and ``cycles_per_bit`` in
        kilo-cycles per bit, so they are expanded to bits and cycles here.
        """
        return cls(
            task_id=task_id,
            creator_id=creator_id,
            arrival_time=float(timestep),
            absolute_deadline=float(deadline),
            data_size_bits=float(data_size_mbit) * 1.0e6,
            cycles_per_bit=float(kilo_cycles_per_bit) * 1.0e3,
            required_compute_units=(
                None
                if required_compute_units is None
                else float(required_compute_units)
            ),
            metadata=dict(metadata or {}),
        )

    def clone_for_reset(self) -> "Task":
        """Return a fresh copy carrying only identity fields (runtime reset)."""
        return Task(
            task_id=self.task_id,
            creator_id=self.creator_id,
            arrival_time=self.arrival_time,
            absolute_deadline=self.absolute_deadline,
            data_size_bits=self.data_size_bits,
            cycles_per_bit=self.cycles_per_bit,
            required_compute_units=self.required_compute_units,
            metadata=dict(self.metadata),
        )

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
=======
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import TaskStatus


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
    chosen_action: "Any" = None
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

    @classmethod
    def from_generator_record(
        cls,
        *,
        task_id: str,
        creator_id: str,
        timestep: float,
        deadline: float,
        data_size_mbit: float,
        kilo_cycles_per_bit: float,
        required_compute_units: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Task":
        """Build a Task from a SUMO/chunk generator record.

        The generator stores ``dataSize`` in Mbit and ``cycles_per_bit`` in
        kilo-cycles per bit, so they are expanded to bits and cycles here.
        """
        return cls(
            task_id=task_id,
            creator_id=creator_id,
            arrival_time=float(timestep),
            absolute_deadline=float(deadline),
            data_size_bits=float(data_size_mbit) * 1.0e6,
            cycles_per_bit=float(kilo_cycles_per_bit) * 1.0e3,
            required_compute_units=(
                None
                if required_compute_units is None
                else float(required_compute_units)
            ),
            metadata=dict(metadata or {}),
        )

    def clone_for_reset(self) -> "Task":
        """Return a fresh copy carrying only identity fields (runtime reset)."""
        return Task(
            task_id=self.task_id,
            creator_id=self.creator_id,
            arrival_time=self.arrival_time,
            absolute_deadline=self.absolute_deadline,
            data_size_bits=self.data_size_bits,
            cycles_per_bit=self.cycles_per_bit,
            required_compute_units=self.required_compute_units,
            metadata=dict(self.metadata),
        )

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
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
