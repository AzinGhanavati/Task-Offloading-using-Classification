<<<<<<< HEAD
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Mapping, Sequence, TYPE_CHECKING

from config.hyperparameters import NormalizationConfig
from simulation.entities.enums import NodeKind, OffloadAction
from simulation.network.energy_model import eptask_compute_energy_j

if TYPE_CHECKING:
    from simulation.entities.compute_node import ComputeNode
    from simulation.entities.sdn_controller import ActionCandidate
    from simulation.entities.task import Task
    from simulation.network.radio_model import RadioModel
    from simulation.network.urban_grid import UrbanGrid
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
    """Raw (un-normalized) per-action features, kept for the offline dataset
    and for the local admission context.  This is NOT the DRL state vector."""

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
    normalized_vector: tuple[float, ...]

    @property
    def action_mask(self) -> list[int]:
        return [int(item.valid) for item in self.action_features]

    def flat_vector(self) -> list[float]:
        """Legacy flat layout (global features + per-action features)."""
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
            f"a{action}_{name}" for action in range(5) for name in action_names
        ]


class StateBuilder:
    """Builds the 6-block normalized decision state (no future-info leakage).

    The normalized vector (blocks 1-5) is the regression-model input and the
    "raw" part of the augmented DRL observation.  Blocks:

        1 (3):  task data-size / workload / deadline ratios
        2 (3):  local best queue time / avg queue time / idle-core ratio
        3 (1):  urban path-loss coefficient of the vehicle's cell
        4 (12): 3 candidate Fog/Edge nodes x (distance, best, avg, idle)
        5 (3):  cloud best / avg queue time / idle-core ratio

    The regression outputs (block 6) are concatenated later by the SDN
    controller to form the full augmented observation.
    """

    def __init__(
        self,
        radio: "RadioModel",
        wired: "FullMeshWiredNetwork",
        normalization: NormalizationConfig | None = None,
        urban_grid: "UrbanGrid | None" = None,
    ) -> None:
        self.radio = radio
        self.wired = wired
        self.normalization = normalization or NormalizationConfig()
        self.urban_grid = urban_grid

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
        # Sample the per-cell path-loss exponent once per decision (the vehicle
        # cell dominates the wireless hop) and reuse it for every link estimate.
        exponent = (
            self.urban_grid.sample_exponent(creator.x, creator.y)
            if self.urban_grid is not None
            else None
        )

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
                estimate = self.radio.estimate(
                    distance_m=candidate.distance_m,
                    coverage_radius_m=candidate.coverage_radius_m,
                    path_loss_exponent=exponent,
                )
                wireless_rate = estimate.rate_bps
                wireless_snr = estimate.snr_db
                plr = estimate.packet_loss_rate
                if wireless_rate > 0.0:
                    network_delay_s = task.data_size_bits / wireless_rate
                    tx_energy_j = estimate.transmit_power_w * network_delay_s
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

        normalized_vector = self._normalized_vector(
            task=task, creator=creator, now=now, catalog=catalog, nodes=nodes
        )
        return DecisionState(global_features, tuple(action_features), tuple(normalized_vector))

    def _normalized_vector(
        self,
        *,
        task: "Task",
        creator: "ComputeNode",
        now: float,
        catalog: Sequence["ActionCandidate"],
        nodes: Mapping[str, "ComputeNode"],
    ) -> list[float]:
        norm = self.normalization

        # Block 1: task features (3)
        remaining_deadline = max(0.0, task.absolute_deadline - now)
        block1 = [
            norm.normalize(task.data_size_bits, norm.max_data_size_bits),
            norm.normalize(task.required_cycles, norm.max_workload_cycles),
            norm.normalize(remaining_deadline, norm.max_deadline_s),
        ]

        # Block 2: local node features (3)
        block2 = [
            norm.normalize(creator.least_load_seconds(now), norm.max_queue_time_s),
            norm.normalize(creator.average_load_seconds(now), norm.max_queue_time_s),
            creator.idle_core_ratio(now),
        ]

        # Block 3: environment / context awareness (1)
        if self.urban_grid is not None:
            coefficient = self.urban_grid.coefficient_at(creator.x, creator.y)
        else:
            coefficient = 0.5 * (norm.path_loss_min + norm.path_loss_max)
        block3 = [norm.normalize_path_loss(coefficient)]

        # Block 4: candidate Fog/Edge nodes (3 nodes x 4 features = 12)
        block4: list[float] = []
        for action in (
            OffloadAction.CANDIDATE_1,
            OffloadAction.CANDIDATE_2,
            OffloadAction.CANDIDATE_3,
        ):
            candidate = catalog[int(action)]
            node = (
                nodes.get(candidate.target_node_id)
                if candidate.valid and candidate.target_node_id
                else None
            )
            if node is None:
                block4.extend([0.0, 0.0, 0.0, 0.0])
            else:
                block4.extend(
                    [
                        norm.normalize(candidate.distance_m, norm.max_distance_m),
                        norm.normalize(
                            node.least_load_seconds(now), norm.max_queue_time_s
                        ),
                        norm.normalize(
                            node.average_load_seconds(now), norm.max_queue_time_s
                        ),
                        node.idle_core_ratio(now),
                    ]
                )

        # Block 5: cloud node features (3)
        cloud_candidate = catalog[int(OffloadAction.CLOUD)]
        cloud_node = (
            nodes.get(cloud_candidate.target_node_id)
            if cloud_candidate.valid and cloud_candidate.target_node_id
            else None
        )
        if cloud_node is None:
            block5 = [0.0, 0.0, 0.0]
        else:
            block5 = [
                norm.normalize(
                    cloud_node.least_load_seconds(now), norm.max_queue_time_s
                ),
                norm.normalize(
                    cloud_node.average_load_seconds(now), norm.max_queue_time_s
                ),
                cloud_node.idle_core_ratio(now),
            ]

        return block1 + block2 + block3 + block4 + block5

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
=======
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Mapping, Sequence, TYPE_CHECKING

from config.hyperparameters import NormalizationConfig
from simulation.entities.enums import NodeKind, OffloadAction
from simulation.network.energy_model import eptask_compute_energy_j

if TYPE_CHECKING:
    from simulation.entities.compute_node import ComputeNode
    from simulation.entities.sdn_controller import ActionCandidate
    from simulation.entities.task import Task
    from simulation.network.radio_model import RadioModel
    from simulation.network.urban_grid import UrbanGrid
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
    """Raw (un-normalized) per-action features, kept for the offline dataset
    and for the local admission context.  This is NOT the DRL state vector."""

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
    normalized_vector: tuple[float, ...]

    @property
    def action_mask(self) -> list[int]:
        return [int(item.valid) for item in self.action_features]

    def flat_vector(self) -> list[float]:
        """Legacy flat layout (global features + per-action features)."""
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
            f"a{action}_{name}" for action in range(5) for name in action_names
        ]


class StateBuilder:
    """Builds the 6-block normalized decision state (no future-info leakage).

    The normalized vector (blocks 1-5) is the regression-model input and the
    "raw" part of the augmented DRL observation.  Blocks:

        1 (3):  task data-size / workload / deadline ratios
        2 (3):  local best queue time / avg queue time / idle-core ratio
        3 (1):  urban path-loss coefficient of the vehicle's cell
        4 (12): 3 candidate Fog/Edge nodes x (distance, best, avg, idle)
        5 (3):  cloud best / avg queue time / idle-core ratio

    The regression outputs (block 6) are concatenated later by the SDN
    controller to form the full augmented observation.
    """

    def __init__(
        self,
        radio: "RadioModel",
        wired: "FullMeshWiredNetwork",
        normalization: NormalizationConfig | None = None,
        urban_grid: "UrbanGrid | None" = None,
    ) -> None:
        self.radio = radio
        self.wired = wired
        self.normalization = normalization or NormalizationConfig()
        self.urban_grid = urban_grid

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
        # Sample the per-cell path-loss exponent once per decision (the vehicle
        # cell dominates the wireless hop) and reuse it for every link estimate.
        exponent = (
            self.urban_grid.sample_exponent(creator.x, creator.y)
            if self.urban_grid is not None
            else None
        )

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
                estimate = self.radio.estimate(
                    distance_m=candidate.distance_m,
                    coverage_radius_m=candidate.coverage_radius_m,
                    path_loss_exponent=exponent,
                )
                wireless_rate = estimate.rate_bps
                wireless_snr = estimate.snr_db
                plr = estimate.packet_loss_rate
                if wireless_rate > 0.0:
                    network_delay_s = task.data_size_bits / wireless_rate
                    tx_energy_j = estimate.transmit_power_w * network_delay_s
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

        normalized_vector = self._normalized_vector(
            task=task, creator=creator, now=now, catalog=catalog, nodes=nodes
        )
        return DecisionState(global_features, tuple(action_features), tuple(normalized_vector))

    def _normalized_vector(
        self,
        *,
        task: "Task",
        creator: "ComputeNode",
        now: float,
        catalog: Sequence["ActionCandidate"],
        nodes: Mapping[str, "ComputeNode"],
    ) -> list[float]:
        norm = self.normalization

        # Block 1: task features (3)
        remaining_deadline = max(0.0, task.absolute_deadline - now)
        block1 = [
            norm.normalize(task.data_size_bits, norm.max_data_size_bits),
            norm.normalize(task.required_cycles, norm.max_workload_cycles),
            norm.normalize(remaining_deadline, norm.max_deadline_s),
        ]

        # Block 2: local node features (3)
        block2 = [
            norm.normalize(creator.least_load_seconds(now), norm.max_queue_time_s),
            norm.normalize(creator.average_load_seconds(now), norm.max_queue_time_s),
            creator.idle_core_ratio(now),
        ]

        # Block 3: environment / context awareness (1)
        if self.urban_grid is not None:
            coefficient = self.urban_grid.coefficient_at(creator.x, creator.y)
        else:
            coefficient = 0.5 * (norm.path_loss_min + norm.path_loss_max)
        block3 = [norm.normalize_path_loss(coefficient)]

        # Block 4: candidate Fog/Edge nodes (3 nodes x 4 features = 12)
        block4: list[float] = []
        for action in (
            OffloadAction.CANDIDATE_1,
            OffloadAction.CANDIDATE_2,
            OffloadAction.CANDIDATE_3,
        ):
            candidate = catalog[int(action)]
            node = (
                nodes.get(candidate.target_node_id)
                if candidate.valid and candidate.target_node_id
                else None
            )
            if node is None:
                block4.extend([0.0, 0.0, 0.0, 0.0])
            else:
                block4.extend(
                    [
                        norm.normalize(candidate.distance_m, norm.max_distance_m),
                        norm.normalize(
                            node.least_load_seconds(now), norm.max_queue_time_s
                        ),
                        norm.normalize(
                            node.average_load_seconds(now), norm.max_queue_time_s
                        ),
                        node.idle_core_ratio(now),
                    ]
                )

        # Block 5: cloud node features (3)
        cloud_candidate = catalog[int(OffloadAction.CLOUD)]
        cloud_node = (
            nodes.get(cloud_candidate.target_node_id)
            if cloud_candidate.valid and cloud_candidate.target_node_id
            else None
        )
        if cloud_node is None:
            block5 = [0.0, 0.0, 0.0]
        else:
            block5 = [
                norm.normalize(
                    cloud_node.least_load_seconds(now), norm.max_queue_time_s
                ),
                norm.normalize(
                    cloud_node.average_load_seconds(now), norm.max_queue_time_s
                ),
                cloud_node.idle_core_ratio(now),
            ]

        return block1 + block2 + block3 + block4 + block5

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
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
