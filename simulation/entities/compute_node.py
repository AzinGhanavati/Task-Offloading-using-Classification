from __future__ import annotations
from dataclasses import dataclass
from math import hypot
from config.simulation_config import HardwareProfile
from simulation.network.energy_model import eptask_compute_energy_j
from simulation.schedulers.edf import EDFQueue
from simulation.schedulers.least_loaded import LeastLoadedCoreMapper
from .enums import NodeKind
from .processing_core import ProcessingCore
from .task import Task

@dataclass(frozen=True, slots=True)
class CoreStart:
    task: Task
    core_id: str
    finishes_at: float

class ComputeNode:
    def __init__(
        self,
        *,
        node_id: str,
        kind: NodeKind,
        hardware: HardwareProfile,
        x: float = 0.0,
        y: float = 0.0,
        coverage_radius_m: float | None = None,
        active: bool = True,
    ) -> None:
        self.node_id = node_id
        self.kind = kind
        self.hardware = hardware
        self.x = float(x)
        self.y = float(y)
        self.coverage_radius_m = coverage_radius_m
        self.active = active
        
        self.core_mapper = LeastLoadedCoreMapper()
        
        # Cores are defined by hardware profile (e.g., Vehicle=4, Edge=16)
        # Infinite capacity EDF queue is handled by passing None to capacity
        self.cores = [
            ProcessingCore(
                core_id=f"{node_id}:core:{index}",
                frequency_hz=hardware.core_frequency_hz,
                energy_coefficient=hardware.energy_coefficient,
                energy_exponent=hardware.energy_exponent,
                queue=EDFQueue(capacity=None),
            )
            for index in range(hardware.core_count)
        ]

    def distance_to(self, other: "ComputeNode") -> float:
        return hypot(self.x - other.x, self.y - other.y)

    def update_position(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)

    def enqueue(self, task: Task, now: float) -> ProcessingCore:
        if not self.active:
            raise RuntimeError(f"node {self.node_id} is inactive")
        core = self.core_mapper.select_core(self.cores, task, now)
        core.enqueue(task, now)
        return core

    def start_idle_cores(self, now: float) -> list[CoreStart]:
        starts: list[CoreStart] = []
        for core in self.cores:
            result = core.start_next(now)
            if result is not None:
                task, finishes_at = result
                starts.append(CoreStart(task, core.core_id, finishes_at))
        return starts

    def complete(self, core_id: str, now: float) -> tuple[Task, float]:
        core = self.core(core_id)
        task = core.complete(now)
        energy_j = eptask_compute_energy_j(
            required_cycles=task.required_cycles,
            frequency_hz=core.frequency_hz,
            coefficient=core.energy_coefficient,
            exponent=core.energy_exponent,
        )
        return task, energy_j

    def core(self, core_id: str) -> ProcessingCore:
        for core in self.cores:
            if core.core_id == core_id:
                return core
        raise KeyError(f"unknown core {core_id} on node {self.node_id}")

    def least_load_seconds(self, now: float) -> float:
        return min(core.load_seconds(now) for core in self.cores)

    def total_load_seconds(self, now: float) -> float:
        return sum(core.load_seconds(now) for core in self.cores)

    def normalized_load(self, now: float, horizon_s: float = 1.0) -> float:
        capacity = max(1.0e-12, len(self.cores) * horizon_s)
        return min(1.0, self.total_load_seconds(now) / capacity)

    @property
    def queue_depth(self) -> int:
        return sum(core.queue_depth for core in self.cores)

    @property
    def frequency_hz(self) -> float:
        return self.hardware.core_frequency_hz