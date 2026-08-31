from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING
from models.regression.predictor import ActionOutcomePrediction, PredictionProvider
from utils.state_builder import DecisionState, StateBuilder
from .cloud_node import CloudNode
from .compute_node import ComputeNode
from .edge_server import EdgeServer
from .enums import NodeKind, OffloadAction
from .fog_node import FogNode
from .task import Task

if TYPE_CHECKING:
    from models.rl.policy import OffloadingPolicy
    from simulation.network.radio_model import RadioModel
    from simulation.network.wired_network import FullMeshWiredNetwork

@dataclass(frozen=True, slots=True)
class ActionCandidate:
    action: OffloadAction
    valid: bool
    target_node_id: str | None
    target_kind: NodeKind | None
    distance_m: float
    coverage_radius_m: float
    gateway_edge_id: str | None = None

@dataclass(frozen=True, slots=True)
class DecisionContext:
    task: Task
    now: float
    catalog: tuple[ActionCandidate, ...]
    raw_state: DecisionState
    predictions: tuple[ActionOutcomePrediction, ...]
    augmented_state: tuple[float, ...]

    @property
    def action_mask(self) -> list[int]:
        return self.raw_state.action_mask

class SDNController:
    def __init__(
        self,
        *,
        edge_servers: Sequence[EdgeServer],
        fog_nodes: Sequence[FogNode],
        cloud: CloudNode,
        radio: "RadioModel",
        wired: "FullMeshWiredNetwork",
        predictor: PredictionProvider | None = None,
    ) -> None:
        self.edge_servers = {node.node_id: node for node in edge_servers}
        self.fog_nodes = {node.node_id: node for node in fog_nodes}
        self.cloud = cloud
        self.predictor = predictor
        self.state_builder = StateBuilder(radio, wired)

    @property
    def infrastructure_nodes(self) -> dict[str, ComputeNode]:
        return {
            **self.edge_servers,
            **self.fog_nodes,
            self.cloud.node_id: self.cloud,
        }

    def nearest_reachable_edge(self, creator: ComputeNode) -> EdgeServer | None:
        reachable = [
            edge for edge in self.edge_servers.values()
            if edge.active and edge.coverage_radius_m is not None
            and edge.distance_to(creator) <= edge.coverage_radius_m
        ]
        return min(reachable, key=lambda node: node.distance_to(creator), default=None)

    def build_catalog(self, creator: ComputeNode) -> tuple[ActionCandidate, ...]:
        # 1. Local Action
        local = ActionCandidate(
            action=OffloadAction.LOCAL,
            valid=creator.active,
            target_node_id=creator.node_id,
            target_kind=creator.kind,
            distance_m=0.0,
            coverage_radius_m=1.0,
        )
        
        # 2. Cloud Action (Requires Edge Gateway)
        gateway = self.nearest_reachable_edge(creator)
        cloud = ActionCandidate(
            action=OffloadAction.CLOUD,
            valid=gateway is not None and self.cloud.active,
            target_node_id=self.cloud.node_id if gateway is not None else None,
            target_kind=NodeKind.CLOUD if gateway is not None else None,
            distance_m=0.0 if gateway is None else gateway.distance_to(creator),
            coverage_radius_m=1.0 if gateway is None else float(gateway.coverage_radius_m),
            gateway_edge_id=None if gateway is None else gateway.node_id,
        )
        
        # 3. Three nearest Fog/Edge candidates
        reachable: list[ComputeNode] = []
        for node in [*self.edge_servers.values(), *self.fog_nodes.values()]:
            if node.node_id == creator.node_id or not node.active:
                continue
            if node.coverage_radius_m is not None and node.distance_to(creator) <= node.coverage_radius_m:
                reachable.append(node)
                
        reachable.sort(key=lambda node: node.distance_to(creator))
        
        candidate_actions = (OffloadAction.CANDIDATE_1, OffloadAction.CANDIDATE_2, OffloadAction.CANDIDATE_3)
        candidates: list[ActionCandidate] = []
        
        for index, action in enumerate(candidate_actions):
            if index >= len(reachable):
                candidates.append(ActionCandidate(action, False, None, None, 0.0, 1.0))
                continue
            node = reachable[index]
            candidates.append(ActionCandidate(
                action=action,
                valid=True,
                target_node_id=node.node_id,
                target_kind=node.kind,
                distance_m=node.distance_to(creator),
                coverage_radius_m=float(node.coverage_radius_m),
            ))
            
        return (local, cloud, *candidates)

    def prepare_decision(self, *, task: Task, creator: ComputeNode, now: float) -> DecisionContext:
        catalog = self.build_catalog(creator)
        nodes = {creator.node_id: creator, **self.infrastructure_nodes}
        external = [n for n in self.infrastructure_nodes.values() if n.active and n.kind is not NodeKind.CLOUD]
        average_load = sum(n.normalized_load(now) for n in external) / len(external) if external else 0.0
        
        raw_state = self.state_builder.build(
            task=task,
            creator=creator,
            now=now,
            catalog=catalog,
            nodes=nodes,
            average_external_load=average_load,
        )
        
        # Fetching Regression Model Predictions
        if self.predictor is None:
            predictions = tuple(ActionOutcomePrediction(0.0, 0.0, 0.0) for _ in catalog)
        else:
            supplied = tuple(self.predictor.predict(raw_state.flat_vector(), raw_state.action_mask))
            zero = ActionOutcomePrediction(0.0, 0.0, 0.0)
            predictions = tuple(item if candidate.valid else zero for item, candidate in zip(supplied, catalog))
            
        # Concatenate predictions into the augmented DRL state
        augmented = raw_state.flat_vector()
        for prediction in predictions:
            augmented.extend(prediction.as_vector())
            
        return DecisionContext(task, now, catalog, raw_state, predictions, tuple(augmented))

    def select_action(self, *, context: DecisionContext, policy: "OffloadingPolicy") -> OffloadAction:
        action = OffloadAction(policy.select_action(context))
        if not context.catalog[int(action)].valid:
            raise ValueError(f"policy selected invalid action slot {int(action)}")
        return action