from __future__ import annotations
from config.simulation_config import HardwareProfile
from .compute_node import ComputeNode
from .enums import NodeKind

class CloudNode(ComputeNode):
    def __init__(
        self,
        *,
        node_id: str,
        hardware: HardwareProfile,
        active: bool = True,
    ) -> None:
        super().__init__(
            node_id=node_id,
            kind=NodeKind.CLOUD,
            hardware=hardware,
            active=active,
        )