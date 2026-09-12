from .base import EdgePlacementStrategy, PlacementPoint
from .central import CentralGridPlacement
from .kmeans import KMeansEdgePlacement

__all__ = [
    "CentralGridPlacement",
    "EdgePlacementStrategy",
    "KMeansEdgePlacement",
    "PlacementPoint",
    "build_placement_strategy",
]


def build_placement_strategy(
    config,
    *,
    area_x_max: float | None = None,
    area_y_max: float | None = None,
):
    """Factory: return the placement strategy named in ``config.strategy``.

    This is the single place to register a new heuristic.  Add a branch here
    (and an implementing class) to swap the placement algorithm.
    """
    strategy = config.strategy.lower()
    if strategy == "kmeans":
        strategy_obj = KMeansEdgePlacement(config)
    elif strategy == "central":
        strategy_obj = CentralGridPlacement(config)
    else:
        raise ValueError(f"unknown placement strategy: {config.strategy!r}")

    if hasattr(strategy_obj, "set_area") and area_x_max is not None:
        strategy_obj.set_area(area_x_max, area_y_max)
    return strategy_obj
