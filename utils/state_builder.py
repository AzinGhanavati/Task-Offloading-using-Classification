from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Mapping, Sequence, TYPE_CHECKING

from simulation.entities.enums import NodeKind, OffloadAction
from simulation.network.energy_model import eptask_compute_energy_j

if TYPE_CHECKING:
    from simulation.entities.compute_node import ComputeNode
    from simulation.entities.sdn_controller import ActionCandidate
    from simulation.entities.task import Task
    from simulation.network.radio_model import RadioModel
    from simulation.network.wired_network import FullMeshWiredNetwork

KIND_CODE = {
    NodeKind.VEHICLE: 0.0,
    NodeKind.MOBILE_FOG: 1.0,
    NodeKind.FIXED_FOG: 2.0,
    NodeKind.EDGE: 3.0,
    NodeKind.CLOUD: 4.0,
}

@dataclass(frozen=True, slots=True)
class ActionFeatures:
    valid: float
    action_slot: float
    node_kind: float
    distance_m: float
    wireless_rate_bps: float
    wireless_snr_db: float
    packet_loss_rate: float
    wired_rate_bps: float
    least_queue_workload_s: float
    queue_depth: float
    core_count: float
    core_frequency_hz: float
    estimated_network_delay_s: float
    estimated_compute_delay_s: float
    estimated_total_delay_s: float
    estimated_compute_energy_j: float
    estimated_source_tx_energy_j: float

    def vector(self) -> list[float]:
        return list(asdict(self).values())

@dataclass(frozen=True, slots=True)
class DecisionState:
    global_features: dict[str, float]
    action_features: tuple[ActionFeatures, ...]

    @property
    def action_mask(self) -> list[int]:
        return [int(item.valid) for item in self.action_features]

    def flat_vector(self) -> list[float]:
        vector = list(self.global_features.values())
        for features in self.action_features:
            vector.extend(features.vector())
        return vector

    @staticmethod
    def feature_names() -> list[str]:
        global_names = [
            "task_size_mbit",
            "required_cycles_giga",
            "cycles_per_bit",
            "remaining_deadline_s",
            "vehicle_speed_mps",
            "generation_rate",
            "qoe",
            "battery_level",
            "local_least_workload_s",
            "local_total_workload_s",
            "local_queue_depth",
            "average_external_load",
        ]
        action_names = [item.name for item in fields(ActionFeatures)]
        return global_names + [
            f"a{action}_{name}"
            for action in range(5)
            for name in action_names
        ]

class StateBuilder:
    """Builds decision-time-only features (no future-information leakage)."""

    def __init__(self, radio: "RadioModel", wired: "FullMeshWiredNetwork") -> None:
        self.radio = radio
        self.wired = wired

    def build(
        self,
        *,
        task: "Task",
        creator: "ComputeNode",
        now: float,
        catalog: Sequence["ActionCandidate"],
        nodes: Mapping[str, "ComputeNode"],
        average_external_load: float,
    ) -> DecisionState:
        global_features = {
            "task_size_mbit": task.data_size_bits / 1.0e6,
            "required_cycles_giga": task.required_cycles / 1.0e9,
            "cycles_per_bit": task.cycles_per_bit,
            "remaining_deadline_s": max(0.0, task.absolute_deadline - now),
            "vehicle_speed_mps": float(getattr(creator, "speed_mps", 0.0)),
            "generation_rate": float(getattr(creator, "generation_rate", 0.0)),
            "qoe": float(getattr(creator, "qoe", 1.0)),
            "battery_level": float(getattr(creator, "battery_level", 1.0)),
            "local_least_workload_s": creator.least_load_seconds(now),
            "local_total_workload_s": creator.total_load_seconds(now),
            "local_queue_depth": float(creator.queue_depth),
            "average_external_load": average_external_load,
        }
        action_features: list[ActionFeatures] = []
        for candidate in catalog:
            if not candidate.valid or candidate.target_node_id is None:
                action_features.append(self._invalid(candidate.action))
                continue
            target = nodes[candidate.target_node_id]
            service_s = task.required_cycles / target.frequency_hz
            compute_delay_s = target.least_load_seconds(now) + service_s
            compute_energy_j = eptask_compute_energy_j(
                task.required_cycles,
                target.frequency_hz,
                target.hardware.energy_coefficient,
                target.hardware.energy_exponent,
            )
            network_delay_s = 0.0
            tx_energy_j = 0.0
            wireless_rate = 0.0
            wireless_snr = 0.0
            plr = 0.0
            wired_rate = 0.0
            if candidate.action is not OffloadAction.LOCAL:
                radius = candidate.coverage_radius_m
                estimate = self.radio.estimate(
                    distance_m=candidate.distance_m,
                    coverage_radius_m=radius,
                )
                wireless_rate = estimate.rate_bps
                wireless_snr = estimate.snr_db
                plr = estimate.packet_loss_rate
                if wireless_rate > 0.0:
                    network_delay_s = task.data_size_bits / wireless_rate
                    tx_energy_j = (
                        estimate.transmit_power_w * network_delay_s
                    )
                if candidate.action is OffloadAction.CLOUD:
                    wired_rate = self.wired.rate_bps
                    network_delay_s += self.wired.estimate_duration_s(
                        task.data_size_bits
                    )
            action_features.append(
                ActionFeatures(
                    valid=1.0,
                    action_slot=float(candidate.action),
                    node_kind=KIND_CODE[target.kind],
                    distance_m=candidate.distance_m,
                    wireless_rate_bps=wireless_rate,
                    wireless_snr_db=wireless_snr,
                    packet_loss_rate=plr,
                    wired_rate_bps=wired_rate,
                    least_queue_workload_s=target.least_load_seconds(now),
                    queue_depth=float(target.queue_depth),
                    core_count=float(target.core_count),
                    core_frequency_hz=target.frequency_hz,
                    estimated_network_delay_s=network_delay_s,
                    estimated_compute_delay_s=compute_delay_s,
                    estimated_total_delay_s=network_delay_s + compute_delay_s,
                    estimated_compute_energy_j=compute_energy_j,
                    estimated_source_tx_energy_j=tx_energy_j,
                )
            )
        return DecisionState(global_features, tuple(action_features))

    @staticmethod
    def _invalid(action: OffloadAction) -> ActionFeatures:
        return ActionFeatures(
            valid=0.0,
            action_slot=float(action),
            node_kind=-1.0,
            distance_m=0.0,
            wireless_rate_bps=0.0,
            wireless_snr_db=0.0,
            packet_loss_rate=1.0,
            wired_rate_bps=0.0,
            least_queue_workload_s=0.0,
            queue_depth=0.0,
            core_count=0.0,
            core_frequency_hz=0.0,
            estimated_network_delay_s=0.0,
            estimated_compute_delay_s=0.0,
            estimated_total_delay_s=0.0,
            estimated_compute_energy_j=0.0,
            estimated_source_tx_energy_j=0.0,
        )