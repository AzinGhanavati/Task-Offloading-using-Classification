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
        model_args = checkpoint["model_args"]
        self.model = MultiActionOutcomeRegressor(**model_args).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()

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
        predictions: list[ActionOutcomePrediction] = []
        for index, valid in enumerate(action_mask):
            if not valid:
                predictions.append(ActionOutcomePrediction(0.0, 0.0, 0.0))
            else:
                predictions.append(
                    ActionOutcomePrediction(
                        completion_time_s=max(0.0, float(continuous[index, 0])),
                        energy_j=max(0.0, float(continuous[index, 1])),
                        deadline_miss_probability=float(miss_probability[index]),
                    )
                )
        return predictions
