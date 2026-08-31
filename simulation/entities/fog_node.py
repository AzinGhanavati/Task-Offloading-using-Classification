from __future__ import annotations
from config.simulation_config import HardwareProfile
from .compute_node import ComputeNode
from .enums import NodeKind

class FogNode(ComputeNode):
    def __init__(
        self,
        *,
        node_id: str,
        hardware: HardwareProfile,
        x: float,
        y: float,
        mobile: bool,
        coverage_radius_m: float,
        speed_mps: float = 0.0,
        heading_deg: float = 0.0,
        lane_id: str = "",
        generation_rate: float = 0.0,
        qoe: float = 1.0,
        battery_level: float = 1.0,
        active: bool = True,
    ) -> None:
        super().__init__(
            node_id=node_id,
            kind=NodeKind.MOBILE_FOG ,
            hardware=hardware,
            x=x,
            y=y,
            coverage_radius_m=coverage_radius_m,
            active=active,
        )
        self.mobile = mobile
        self.speed_mps = float(speed_mps)
        self.heading_deg = float(heading_deg)
        self.lane_id = lane_id
        self.generation_rate = float(generation_rate)
        self.qoe = float(qoe)
        self.battery_level = float(battery_level)

    def update_mobility(
        self,
        *,
        x: float,
        y: float,
        speed_mps: float,
        heading_deg: float,
        lane_id: str,
        generation_rate: float | None = None,
        qoe: float | None = None,
    ) -> None:
        if not self.mobile:
            raise RuntimeError("mobility can only be updated for a mobile fog node")
        
        self.update_position(x, y)
        self.speed_mps = float(speed_mps)
        self.heading_deg = float(heading_deg)
        self.lane_id = lane_id
        
        if generation_rate is not None:
            self.generation_rate = float(generation_rate)
        if qoe is not None:
            self.qoe = float(qoe)
            
        self.active = True