from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import torch

from .multi_head_net import MultiActionOutcomeRegressor
from .predictor import ActionOutcomePrediction


class TorchRegressionPredictor:
    """SDN adapter that converts a trained checkpoint into state predictions."""

    def __init__(self, checkpoint_path: str | Path, device: str = "cpu") -> None:
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        self.device = torch.device(device)
        self.feature_mean = np.asarray(checkpoint["feature_mean"], dtype=np.float32)
        self.feature_std = np.asarray(checkpoint["feature_std"], dtype=np.float32)
        self.target_mean = np.asarray(checkpoint["target_mean"], dtype=np.float32)
        self.target_std = np.asarray(checkpoint["target_std"], dtype=np.float32)
        # Min/max of the two continuous targets (for 0-1 state normalization).
        # Fall back to mean +/- std for older checkpoints that lack them.
        self.target_min = (
            np.asarray(checkpoint["target_min"], dtype=np.float32)
            if "target_min" in checkpoint
            else self.target_mean - self.target_std
        )
        self.target_max = (
            np.asarray(checkpoint["target_max"], dtype=np.float32)
            if "target_max" in checkpoint
            else self.target_mean + self.target_std
        )
        self._target_span = self.target_max - self.target_min
        model_args = checkpoint["model_args"]
        self.model = MultiActionOutcomeRegressor(**model_args).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()

    @property
    def reward_scales(self) -> tuple[float, float]:
        """(T_scale, E_scale): dataset max completion time / energy.

        Used by the adaptive reward so both scaled terms fall in roughly
        [0, 1] instead of relying on hand-picked constants.
        """
        time_scale = float(self.target_max[0])
        energy_scale = float(self.target_max[1])
        return (
            time_scale if time_scale > 1.0e-12 else 1.0,
            energy_scale if energy_scale > 1.0e-12 else 1.0,
        )

    def predict(
        self, raw_state: Sequence[float], action_mask: Sequence[int]
    ) -> Sequence[ActionOutcomePrediction]:
        features = np.asarray(raw_state, dtype=np.float32)
        if features.shape != self.feature_mean.shape:
            raise ValueError(
                f"predictor expected {self.feature_mean.size} features, got "
                f"{features.size}"
            )
        normalized = (features - self.feature_mean) / self.feature_std
        tensor = torch.from_numpy(normalized).unsqueeze(0).to(self.device)
        with torch.no_grad():
            output = self.model(tensor).squeeze(0).cpu().numpy()
        continuous = output[:, :2] * self.target_std + self.target_mean
        miss_logit = np.clip(output[:, 2], -60.0, 60.0)
        miss_probability = 1.0 / (1.0 + np.exp(-miss_logit))

        def unit_scale(value: float, axis: int) -> float:
            span = float(self._target_span[axis])
            if span <= 1.0e-12:
                return 0.0
            return float(np.clip((value - self.target_min[axis]) / span, 0.0, 1.0))

        predictions: list[ActionOutcomePrediction] = []
        for index, valid in enumerate(action_mask):
            if not valid:
                predictions.append(ActionOutcomePrediction(0.0, 0.0, 0.0))
            else:
                time_s = max(0.0, float(continuous[index, 0]))
                energy_j = max(0.0, float(continuous[index, 1]))
                predictions.append(
                    ActionOutcomePrediction(
                        completion_time_s=time_s,
                        energy_j=energy_j,
                        deadline_miss_probability=float(miss_probability[index]),
                        completion_time_norm=unit_scale(time_s, 0),
                        energy_norm=unit_scale(energy_j, 1),
                    )
                )
        return predictions
