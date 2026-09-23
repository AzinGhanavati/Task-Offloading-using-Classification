from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence

from config.hyperparameters import Hyperparameters
from config.simulation_config import SimulationConfig, default_simulation_config
from models.local_decision.base import AdmissionContext, LocalAdmissionPolicy
from models.local_decision.threshold_admission import ThresholdAdmissionPolicy
from models.regression.predictor import PredictionProvider
from models.DRL.policy import OffloadingPolicy
from models.DRL.random_policy import RandomOffloadingPolicy
from simulation.entities.cloud_node import CloudNode
from simulation.entities.compute_node import ComputeNode
from simulation.entities.edge_server import EdgeServer
from simulation.entities.enums import AdmissionDecision, NodeKind, OffloadAction, TaskStatus
from simulation.entities.fog_node import FogNode
from simulation.entities.sdn_controller import DecisionContext, SDNController
from simulation.entities.task import Task
from simulation.entities.vehicle import Vehicle
from simulation.network.energy_model import eptask_compute_energy_j
from simulation.network.radio_model import RadioModel
from simulation.network.urban_grid import UrbanGrid
from simulation.network.wired_network import FullMeshWiredNetwork


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    node_id: str
    x: float
    y: float
    speed_mps: float
    heading_deg: float
    lane_id: str
    vehicle_type: str
    generation_rate: float
    qoe: float = 1.0


class SimulationObserver(Protocol):
    def on_decision(
        self,
        task: Task,
        context: DecisionContext,
        action: OffloadAction,
    ) -> None:
        ...

    def on_final(self, task: Task) -> None:
        ...


class _EventType(str, Enum):
    MOBILITY = "mobility"
    CORE_COMPLETE = "core_complete"
    TASK_ARRIVAL = "task_arrival"
    COMPUTE_ARRIVAL = "compute_arrival"
    CLOUD_GATEWAY_ARRIVAL = "cloud_gateway_arrival"
    FAILURE = "failure"


_EVENT_PRIORITY = {
    _EventType.MOBILITY: 0,
    _EventType.CORE_COMPLETE: 1,
    _EventType.TASK_ARRIVAL: 2,
    _EventType.CLOUD_GATEWAY_ARRIVAL: 3,
    _EventType.COMPUTE_ARRIVAL: 4,
    _EventType.FAILURE: 5,
}


@dataclass(order=True, slots=True)
class _Event:
    time: float
    priority: int
    sequence: int
    event_type: _EventType = field(compare=False)
    payload: Any = field(compare=False)


@dataclass(frozen=True, slots=True)
class _TaskArrival:
    task: Task
    bypass_admission: bool
    forced_action: OffloadAction | None


class SimulationEnvironment:
    """Discrete-event vehicular edge computing simulator.

    Two driving modes are supported:

    * **Batch** (offline data collection): schedule everything, then ``run()``
      to completion.  The configured offloading policy makes each decision.
    * **Decision-stepping** (DRL): ``reset_for_episode`` schedules the scenario
      and stops at each offloading decision; ``apply_and_advance`` feeds the
      agent's chosen action and resumes until the next decision.
    """

    def __init__(
        self,
        *,
        edge_servers: Sequence[EdgeServer],
        fog_nodes: Sequence[FogNode],
        cloud: CloudNode,
        config: SimulationConfig | None = None,
        hyperparameters: Hyperparameters | None = None,
        admission_policy: LocalAdmissionPolicy | None = None,
        offloading_policy: OffloadingPolicy | None = None,
        predictor: PredictionProvider | None = None,
        urban_grid: UrbanGrid | None = None,
    ) -> None:
        self.config = config or default_simulation_config()
        self.hyperparameters = hyperparameters or Hyperparameters()
        self.radio = RadioModel(self.config.radio, seed=self.config.random_seed)
        self.wired = FullMeshWiredNetwork(self.config.wired)
        self.urban_grid = urban_grid
        self.sdn = SDNController(
            edge_servers=edge_servers,
            fog_nodes=fog_nodes,
            cloud=cloud,
            radio=self.radio,
            wired=self.wired,
            predictor=predictor,
            urban_grid=urban_grid,
            normalization=self.hyperparameters.normalization,
        )
        self.admission_policy = admission_policy or ThresholdAdmissionPolicy()
        self.offloading_policy = offloading_policy or RandomOffloadingPolicy(
            self.config.random_seed
        )
        self.vehicles: dict[str, ComputeNode] = {}
        self.observers: list[SimulationObserver] = []
        self.now = 0.0
        self.completed_tasks: list[Task] = []
        self.failed_tasks: list[Task] = []
        self._events: list[_Event] = []
        self._sequence = itertools.count()

        # Decision-stepping state (used by the DRL gym wrapper).
        self._pause_at_decision = False
        self._paused = False
        self._current_task: Task | None = None
        self._current_context: DecisionContext | None = None

    @property
    def all_nodes(self) -> dict[str, ComputeNode]:
        return {**self.sdn.infrastructure_nodes, **self.vehicles}

    # ------------------------------------------------------------------
    # Registration / scheduling (batch mode)
    # ------------------------------------------------------------------
    def add_observer(self, observer: SimulationObserver) -> None:
        self.observers.append(observer)

    def register_creator(self, node: ComputeNode) -> None:
        if not isinstance(node, (Vehicle, FogNode)):
            raise TypeError("a task creator must be a Vehicle or mobile FogNode")
        self.vehicles[node.node_id] = node
        if isinstance(node, FogNode):
            if not node.mobile:
                raise ValueError("a fixed fog node is not a vehicle creator")
            self.sdn.fog_nodes[node.node_id] = node

    def schedule_vehicle_snapshot(
        self, time: float, snapshots: Sequence[VehicleSnapshot]
    ) -> None:
        self._schedule(time, _EventType.MOBILITY, tuple(snapshots))

    def schedule_task(
        self,
        task: Task,
        *,
        bypass_admission: bool = False,
        forced_action: OffloadAction | int | None = None,
    ) -> None:
        action = None if forced_action is None else OffloadAction(forced_action)
        self._schedule(
            task.arrival_time,
            _EventType.TASK_ARRIVAL,
            _TaskArrival(task, bypass_admission, action),
        )

    # ------------------------------------------------------------------
    # Event loop
    # ------------------------------------------------------------------
    def run(self, until: float | None = None) -> None:
        while self._events and not self._paused:
            timestamp = self._events[0].time
            if until is not None and timestamp > until:
                break
            self.now = timestamp
            self._process_timestamp(timestamp)
            if self._paused:
                break

    def _process_timestamp(self, timestamp: float) -> None:
        batch: list[_Event] = []
        while self._events and self._same_time(self._events[0].time, timestamp):
            batch.append(heapq.heappop(self._events))
        batch.sort(key=lambda item: (item.priority, item.sequence))
        for index, event in enumerate(batch):
            self._handle(event)
            if self._paused:
                # The pausing event (this one) is consumed: the decision is now
                # pending and will be applied by apply_and_advance.  Requeue only
                # the later events of this timestamp so nothing is lost.
                for remaining in batch[index + 1:]:
                    heapq.heappush(self._events, remaining)
                break
        if not self._paused:
            self._start_all_idle_cores(timestamp)

    def _handle(self, event: _Event) -> None:
        handlers = {
            _EventType.MOBILITY: self._handle_mobility,
            _EventType.TASK_ARRIVAL: self._handle_task_arrival,
            _EventType.COMPUTE_ARRIVAL: self._handle_compute_arrival,
            _EventType.CLOUD_GATEWAY_ARRIVAL: self._handle_cloud_gateway_arrival,
            _EventType.CORE_COMPLETE: self._handle_core_complete,
            _EventType.FAILURE: self._handle_failure,
        }
        handlers[event.event_type](event.payload)

    # ------------------------------------------------------------------
    # Decision-stepping API (DRL)
    # ------------------------------------------------------------------
    @property
    def current_task(self) -> Task | None:
        return self._current_task

    @property
    def current_context(self) -> DecisionContext | None:
        return self._current_context

    def reset_for_episode(self, scenario) -> DecisionContext:
        """Reset nodes and schedule the scenario, then advance to the first
        offloading decision.  Returns the first DecisionContext (or raises if
        the scenario has no decisions)."""
        self._events.clear()
        self._sequence = itertools.count()
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.vehicles.clear()
        self.sdn.fog_nodes.clear()
        self.wired.reset()
        for node in [*self.sdn.edge_servers.values(), self.sdn.cloud]:
            node.reset()

        self._pause_at_decision = True
        self._paused = False
        self._current_task = None
        self._current_context = None
        self.now = 0.0

        for time, snapshots in scenario.vehicle_snapshots():
            self.schedule_vehicle_snapshot(time, snapshots)
        for task in scenario.make_tasks():
            self.schedule_task(task, bypass_admission=True)

        self.run()
        if self._current_context is None:
            raise RuntimeError("scenario produced no offloading decisions")
        return self._current_context

    def apply_and_advance(
        self, action: OffloadAction | int
    ) -> tuple[list[Task], list[Task], DecisionContext | None, bool]:
        """Apply ``action`` to the pending decision, then resume until the next
        decision or the end of the scenario.

        Returns ``(completed, failed, next_context, done)``.
        """
        task = self._current_task
        context = self._current_context
        if task is None or context is None:
            raise RuntimeError("no pending decision to advance")
        self._current_task = None
        self._current_context = None
        self._paused = False

        action = OffloadAction(action)
        self._finish_task_arrival(task, context, action)
        # Locally-executed tasks are enqueued immediately, so start idle cores
        # right away before the event loop resumes.
        self._start_all_idle_cores(self.now)

        completed_before = len(self.completed_tasks)
        failed_before = len(self.failed_tasks)
        self.run()

        completed = self.completed_tasks[completed_before:]
        failed = self.failed_tasks[failed_before:]
        if self._paused:
            return completed, failed, self._current_context, False
        return completed, failed, None, True

    def reset(self) -> None:
        """Clear all state for a fresh batch run (offline data collection)."""
        self._events.clear()
        self._sequence = itertools.count()
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.vehicles.clear()
        self.sdn.fog_nodes.clear()
        self.wired.reset()
        for node in self.all_nodes.values():
            node.reset()
        self._pause_at_decision = False
        self._paused = False
        self._current_task = None
        self._current_context = None
        self.now = 0.0

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_mobility(self, snapshots: Sequence[VehicleSnapshot]) -> None:
        for node in self.vehicles.values():
            node.active = False
        for snapshot in snapshots:
            node = self.vehicles.get(snapshot.node_id)
            is_mobile_fog = snapshot.vehicle_type == "LKW_special"
            if node is None:
                if is_mobile_fog:
                    node = FogNode(
                        node_id=snapshot.node_id,
                        hardware=self.config.mobile_fog,
                        x=snapshot.x,
                        y=snapshot.y,
                        mobile=True,
                        coverage_radius_m=self.config.radio.default_coverage_radius_m,
                        speed_mps=snapshot.speed_mps,
                        heading_deg=snapshot.heading_deg,
                        lane_id=snapshot.lane_id,
                        generation_rate=snapshot.generation_rate,
                        qoe=snapshot.qoe,
                    )
                else:
                    node = Vehicle(
                        node_id=snapshot.node_id,
                        hardware=self.config.vehicle,
                        x=snapshot.x,
                        y=snapshot.y,
                        speed_mps=snapshot.speed_mps,
                        heading_deg=snapshot.heading_deg,
                        lane_id=snapshot.lane_id,
                        vehicle_type=snapshot.vehicle_type,
                        generation_rate=snapshot.generation_rate,
                        qoe=snapshot.qoe,
                    )
                self.register_creator(node)
            elif isinstance(node, FogNode):
                node.update_mobility(
                    x=snapshot.x,
                    y=snapshot.y,
                    speed_mps=snapshot.speed_mps,
                    heading_deg=snapshot.heading_deg,
                    lane_id=snapshot.lane_id,
                    generation_rate=snapshot.generation_rate,
                    qoe=snapshot.qoe,
                )
            elif isinstance(node, Vehicle):
                node.update_mobility(
                    x=snapshot.x,
                    y=snapshot.y,
                    speed_mps=snapshot.speed_mps,
                    heading_deg=snapshot.heading_deg,
                    lane_id=snapshot.lane_id,
                    generation_rate=snapshot.generation_rate,
                    qoe=snapshot.qoe,
                )

    def _handle_task_arrival(self, payload: _TaskArrival) -> None:
        task = payload.task
        creator = self.vehicles.get(task.creator_id)
        if creator is None or not creator.active:
            self._fail(task, "creator_missing_or_inactive")
            return
        task.decision_time = self.now
        task.status = TaskStatus.DECIDED
        context = self.sdn.prepare_decision(task=task, creator=creator, now=self.now)

        if self._pause_at_decision and self._current_task is None:
            self._current_task = task
            self._current_context = context
            self._paused = True
            return

        action = self._resolve_action(payload, context, creator)
        if action is not None:
            self._finish_task_arrival(task, context, action)

    def _resolve_action(
        self,
        payload: _TaskArrival,
        context: DecisionContext,
        creator: ComputeNode,
    ) -> OffloadAction | None:
        task = payload.task
        if payload.forced_action is not None:
            action = payload.forced_action
            if not context.catalog[int(action)].valid:
                self._fail(task, f"forced_action_{int(action)}_invalid")
                return None
            return action
        if payload.bypass_admission:
            return self.sdn.select_action(
                context=context, policy=self.offloading_policy
            )
        admission = self._admission_context(task, creator, context)
        local_decision = self.admission_policy.decide(admission)
        if local_decision is AdmissionDecision.LOCAL:
            return OffloadAction.LOCAL
        return self.sdn.select_action(context=context, policy=self.offloading_policy)

    def _finish_task_arrival(
        self, task: Task, context: DecisionContext, action: OffloadAction
    ) -> None:
        candidate = context.catalog[int(action)]
        task.chosen_action = action
        task.target_node_id = candidate.target_node_id
        task.gateway_edge_id = candidate.gateway_edge_id

        for observer in self.observers:
            observer.on_decision(task, context, action)

        if action is OffloadAction.LOCAL:
            self._handle_compute_arrival(task)
            return

        # Sample the per-cell path-loss exponent for the actual transmission.
        exponent = None
        if self.sdn.urban_grid is not None:
            creator = self.vehicles.get(task.creator_id)
            if creator is not None:
                exponent = self.sdn.urban_grid.sample_exponent(creator.x, creator.y)

        transmission = self.radio.transmit(
            data_size_bits=task.data_size_bits,
            distance_m=candidate.distance_m,
            coverage_radius_m=candidate.coverage_radius_m,
            path_loss_exponent=exponent,
        )
        task.status = TaskStatus.TRANSMITTING
        task.wireless_time_s += transmission.duration_s
        task.vehicle_tx_energy_j += transmission.energy_j
        task.transmission_attempts += transmission.attempts
        task.packet_loss_rate = transmission.estimate.packet_loss_rate
        task.achieved_wireless_rate_bps = transmission.estimate.rate_bps
        arrives_at = self.now + transmission.duration_s

        if not transmission.success:
            self._schedule(
                arrives_at, _EventType.FAILURE, (task, "wireless_transmission_failed")
            )
        elif action is OffloadAction.CLOUD:
            self._schedule(arrives_at, _EventType.CLOUD_GATEWAY_ARRIVAL, task)
        else:
            self._schedule(arrives_at, _EventType.COMPUTE_ARRIVAL, task)

    def _handle_cloud_gateway_arrival(self, task: Task) -> None:
        if task.gateway_edge_id is None:
            self._fail(task, "cloud_gateway_missing")
            return
        transfer = self.wired.reserve(
            source_id=task.gateway_edge_id,
            destination_id=self.sdn.cloud.node_id,
            data_size_bits=task.data_size_bits,
            now=self.now,
        )
        task.wired_time_s += transfer.finishes_at - self.now
        task.wired_energy_j += transfer.energy_j
        task.achieved_wired_rate_bps = transfer.rate_bps
        self._schedule(transfer.finishes_at, _EventType.COMPUTE_ARRIVAL, task)

    def _handle_compute_arrival(self, task: Task) -> None:
        if task.target_node_id is None:
            self._fail(task, "target_missing")
            return
        node = self.all_nodes.get(task.target_node_id)
        if node is None or (not node.active and node.node_id != task.creator_id):
            self._fail(task, "target_missing_or_inactive_at_arrival")
            return
        task.transmission_finished_at = self.now
        try:
            node.enqueue(task, self.now)
        except (OverflowError, RuntimeError) as exc:
            self._fail(task, f"queue_rejected:{exc}")

    def _handle_core_complete(self, payload: tuple[str, str]) -> None:
        node_id, core_id = payload
        node = self.all_nodes[node_id]
        task, compute_energy_j = node.complete(core_id, self.now)
        if node_id == task.creator_id:
            task.vehicle_compute_energy_j += compute_energy_j
        else:
            task.infrastructure_compute_energy_j += compute_energy_j
        task.status = TaskStatus.COMPLETED
        task.completed_at = self.now
        self.completed_tasks.append(task)
        for observer in self.observers:
            observer.on_final(task)

    def _handle_failure(self, payload: tuple[Task, str]) -> None:
        task, reason = payload
        self._fail(task, reason)

    def _start_all_idle_cores(self, now: float) -> None:
        for node in self.all_nodes.values():
            for start in node.start_idle_cores(now):
                self._schedule(
                    start.finishes_at,
                    _EventType.CORE_COMPLETE,
                    (node.node_id, start.core_id),
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _admission_context(
        self,
        task: Task,
        creator: ComputeNode,
        decision: DecisionContext,
    ) -> AdmissionContext:
        local = decision.raw_state.action_features[int(OffloadAction.LOCAL)]
        remotes = [
            features
            for features in decision.raw_state.action_features[1:]
            if features.valid
        ]
        best = min(
            remotes, key=lambda item: item.estimated_total_delay_s, default=local
        )
        local_energy = eptask_compute_energy_j(
            task.required_cycles,
            creator.frequency_hz,
            creator.hardware.energy_coefficient,
            creator.hardware.energy_exponent,
        )
        return AdmissionContext(
            task=task,
            now=self.now,
            remaining_deadline_s=max(0.0, task.absolute_deadline - self.now),
            local_service_s=task.required_cycles / creator.frequency_hz,
            local_workload_s=creator.least_load_seconds(self.now),
            local_load=creator.normalized_load(self.now),
            average_external_load=decision.raw_state.global_features[
                "average_external_load"
            ],
            generation_rate=float(getattr(creator, "generation_rate", 0.0)),
            qoe=float(getattr(creator, "qoe", 1.0)),
            battery_level=float(getattr(creator, "battery_level", 1.0)),
            local_energy_j=local_energy,
            estimated_remote_delay_s=best.estimated_total_delay_s,
            estimated_remote_energy_j=(
                best.estimated_compute_energy_j
                + best.estimated_source_tx_energy_j
            ),
        )

    def _fail(self, task: Task, reason: str) -> None:
        if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
            return
        task.status = TaskStatus.FAILED
        task.failure_reason = reason
        task.completed_at = self.now
        self.failed_tasks.append(task)
        for observer in self.observers:
            observer.on_final(task)

    def _schedule(self, time: float, event_type: _EventType, payload: Any) -> None:
        if time + 1.0e-9 < self.now:
            raise ValueError("cannot schedule an event in the past")
        heapq.heappush(
            self._events,
            _Event(
                float(time),
                _EVENT_PRIORITY[event_type],
                next(self._sequence),
                event_type,
                payload,
            ),
        )

    @staticmethod
    def _same_time(left: float, right: float) -> bool:
        return abs(left - right) <= 1.0e-12
