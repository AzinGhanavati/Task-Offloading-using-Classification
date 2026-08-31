from __future__ import annotations
from config.simulation_config import HardwareProfile
from .compute_node import ComputeNode
from .enums import NodeKind

class EdgeServer(ComputeNode):
    def __init__(
        self,
        *,
        node_id: str,
        hardware: HardwareProfile,
        x: float,
        y: float,
        coverage_radius_m: float,
        active: bool = True,
    ) -> None:
        super().__init__(
            node_id=node_id,
            kind=NodeKind.EDGE,
            hardware=hardware,
            x=x,
            y=y,
            coverage_radius_m=coverage_radius_m,
            active=active,
        )