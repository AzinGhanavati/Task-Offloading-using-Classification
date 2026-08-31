from __future__ import annotations
from config.simulation_config import HardwareProfile
from .compute_node import ComputeNode
from .enums import NodeKind

class Vehicle(ComputeNode):
    def __init__(
        self,
        *,
        node_id: str,
        hardware: HardwareProfile,
        x: float,
        y: float,
        speed_mps: float = 0.0,
        heading_deg: float = 0.0,
        lane_id: str = "",
        vehicle_type: str = "PKW_special",
        generation_rate: float = 0.0,
        qoe: float = 1.0,
        battery_level: float = 1.0,
        active: bool = True,
    ) -> None:
        super().__init__(
            node_id=node_id,
            kind=NodeKind.VEHICLE,
            hardware=hardware,
            x=x,
            y=y,
            coverage_radius_m=None,
            active=active,
        )
        self.speed_mps = float(speed_mps)
        self.heading_deg = float(heading_deg)
        self.lane_id = lane_id
        self.vehicle_type = vehicle_type
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
        self.update_position(x, y)
        self.speed_mps = float(speed_mps)
        self.heading_deg = float(heading_deg)
        self.lane_id = lane_id
        if generation_rate is not None:
            self.generation_rate = float(generation_rate)
        if qoe is not None:
            self.qoe = float(qoe)
        self.active = True