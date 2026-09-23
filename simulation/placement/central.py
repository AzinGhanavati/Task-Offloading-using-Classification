from __future__ import annotations

from typing import Sequence

from config.hyperparameters import PlacementConfig

from .base import PlacementPoint


class CentralGridPlacement:
    """Evenly spread edge servers across the map as anchor points.

    A simple, deterministic fallback: divide the map into ``k`` equal columns
    and place a server at the vertical centre of each.  Good as a baseline or
    when traffic data is unavailable (``points`` is ignored).
    """

    def __init__(self, config: PlacementConfig | None = None) -> None:
        self.config = config or PlacementConfig()
        # Map extents reused from the urban grid defaults; overridable below.
        self.area_x_max = 2000.0
        self.area_y_max = 1500.0

    def set_area(self, area_x_max: float, area_y_max: float) -> None:
        self.area_x_max = float(area_x_max)
        self.area_y_max = float(area_y_max)

    def place(self, points: Sequence[tuple[float, float]]) -> list[PlacementPoint]:
        cfg = self.config
        k = max(1, cfg.num_edge_servers)
        result: list[PlacementPoint] = []
        for index in range(k):
            fraction = (index + 0.5) / k
            x = fraction * self.area_x_max
            y = 0.5 * self.area_y_max
            result.append(PlacementPoint(x, y))
        return result
