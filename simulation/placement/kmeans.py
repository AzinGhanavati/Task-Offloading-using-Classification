from __future__ import annotations

from typing import Sequence

import numpy as np

from config.hyperparameters import PlacementConfig

from .base import PlacementPoint


class KMeansEdgePlacement:
    """Deploy edge servers at the centroids of K-Means clusters of traffic.

    The candidate points are the observed vehicle positions.  Clustering them
    with K-Means (K = number of edge servers) and placing a server at each
    centroid puts servers near dense traffic, a common "best practice" heuristic
    for edge placement.  The implementation is a self-contained K-Means with
    k-means++ initialization (no external dependency).
    """

    def __init__(self, config: PlacementConfig | None = None) -> None:
        self.config = config or PlacementConfig()

    def place(self, points: Sequence[tuple[float, float]]) -> list[PlacementPoint]:
        cfg = self.config
        k = max(1, cfg.num_edge_servers)
        data = np.asarray(list(points), dtype=np.float64)

        if data.size == 0 or data.shape[0] == 0:
            return []
        if data.ndim == 1:
            data = data.reshape(-1, 2)

        if data.shape[0] <= k:
            # Not enough distinct points to form k clusters: use them directly.
            unique = self._unique_rows(data)
            return [PlacementPoint(row[0], row[1]) for row in unique[:k]]

        rng = np.random.default_rng(cfg.random_state)
        centroids = self._kmeans_pp_init(data, k, rng)

        for _ in range(cfg.max_iter):
            distances = np.linalg.norm(data[:, None, :] - centroids[None, :, :], axis=2)
            labels = np.argmin(distances, axis=1)
            new_centroids = centroids.copy()
            for cluster in range(k):
                members = data[labels == cluster]
                if members.shape[0] > 0:
                    new_centroids[cluster] = members.mean(axis=0)
            shift = np.linalg.norm(new_centroids - centroids)
            centroids = new_centroids
            if shift < cfg.tol:
                break

        return [
            PlacementPoint(float(c[0]), float(c[1])) for c in centroids
        ]

    @staticmethod
    def _kmeans_pp_init(
        data: np.ndarray, k: int, rng: np.random.Generator
    ) -> np.ndarray:
        n = data.shape[0]
        centroids = np.empty((k, data.shape[1]), dtype=np.float64)
        centroids[0] = data[rng.integers(n)]
        closest_sq = np.min(
            np.sum((data - centroids[0][None, :]) ** 2, axis=1), axis=0
        )
        for c in range(1, k):
            total = closest_sq.sum()
            if total <= 0:
                centroids[c] = data[rng.integers(n)]
                continue
            probs = closest_sq / total
            indices = rng.choice(n, p=probs)
            centroids[c] = data[indices]
            dist_sq = np.sum((data - centroids[c][None, :]) ** 2, axis=1)
            closest_sq = np.minimum(closest_sq, dist_sq)
        return centroids

    @staticmethod
    def _unique_rows(data: np.ndarray) -> np.ndarray:
        # Deduplicate points so we never place two servers at the same spot.
        return np.unique(data, axis=0)
