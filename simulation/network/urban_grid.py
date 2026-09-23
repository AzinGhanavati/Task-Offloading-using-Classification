from __future__ import annotations

import math
import random
from dataclasses import dataclass

from config.hyperparameters import UrbanGridConfig


@dataclass(frozen=True, slots=True)
class CellIndex:
    ix: int
    iy: int


class UrbanGrid:
    """Grid of square cells, each with a mean path-loss exponent.

    The urban map is partitioned into ``cell_size_m`` square cells.  Every cell
    is assigned a *mean* path-loss exponent drawn uniformly from
    ``[path_loss_min, path_loss_max]``.  At runtime, ``sample_exponent`` draws a
    lognormal shadowing sample around that cell's mean to obtain the actual
    exponent used for a communication link.
    """

    def __init__(self, config: UrbanGridConfig | None = None) -> None:
        self.config = config or UrbanGridConfig()
        cfg = self.config
        self._cols = max(1, math.ceil(cfg.area_x_max / cfg.cell_size_m))
        self._rows = max(1, math.ceil(cfg.area_y_max / cfg.cell_size_m))
        self._rng = random.Random(cfg.seed)
        # Pre-assign the mean path-loss coefficient for every cell.
        self._coeff: list[list[float]] = [
            [
                self._rng.uniform(cfg.path_loss_min, cfg.path_loss_max)
                for _ in range(self._cols)
            ]
            for _ in range(self._rows)
        ]

    def cell_index(self, x: float, y: float) -> CellIndex:
        """Map a world coordinate to the containing cell (clamped to bounds)."""
        cfg = self.config
        ix = int(x // cfg.cell_size_m)
        iy = int(y // cfg.cell_size_m)
        ix = min(self._cols - 1, max(0, ix))
        iy = min(self._rows - 1, max(0, iy))
        return CellIndex(ix=ix, iy=iy)

    def coefficient_at(self, x: float, y: float) -> float:
        """Mean path-loss coefficient assigned to the cell containing (x, y)."""
        idx = self.cell_index(x, y)
        return self._coeff[idx.iy][idx.ix]

    def sample_exponent(self, x: float, y: float) -> float:
        """Sample the actual path-loss exponent for a link in the cell.

        A lognormal shadowing term is applied around the cell's mean exponent,
        then clamped to a physically sensible range.
        """
        cfg = self.config
        mean = self.coefficient_at(x, y)
        # Lognormal shadowing: exp(N(0, sigma)) ~ 1 on average, so the sample
        # is centered on the cell mean while allowing heavy-tailed variation.
        shadow = math.exp(self._rng.gauss(0.0, cfg.shadowing_sigma))
        exponent = mean * shadow
        return min(cfg.exponent_clamp_max, max(cfg.exponent_clamp_min, exponent))

    def grid_size(self) -> tuple[int, int]:
        """Return (cols, rows) of the urban grid."""
        return self._cols, self._rows
