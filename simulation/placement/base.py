from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class PlacementPoint:
    """A single (x, y) location, e.g. a placed edge server."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class EdgePlacementStrategy(Protocol):
    """Interface for swappable edge-server deployment heuristics.

    Implementations take a set of candidate points (typically vehicle / traffic
    positions) and the number of servers to place, and return the chosen
    locations.  Keeping this a Protocol lets a new heuristic be dropped in
    without touching the rest of the system.
    """

    def place(
        self, points: Sequence[tuple[float, float]]
    ) -> list[PlacementPoint]:
        """Return the deployed edge-server locations."""
        ...
