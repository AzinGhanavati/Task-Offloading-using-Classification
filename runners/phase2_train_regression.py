"""Phase 3 of the project: train the multi-head regression (Digital Twin).

Reads the offline dataset produced by ``phase1`` and trains a shared-trunk
network that predicts (completion time, energy, deadline-miss) for ALL five
stable action slots.  Only the executed action is supervised (masked loss),
since the dataset records the outcome of a single random action per sample.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.hyperparameters import RegressionConfig, default_hyperparameters
from models.regression.masked_loss import masked_action_outcome_loss
from models.regression.multi_head_net import MultiActionOutcomeRegressor


def _load_rows(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number


def run(csv_path: str, checkpoint: str, config: RegressionConfig | None = None) -> str:
    cfg = config or default_hyperparameters().regression
    rows = _load_rows(csv_path)

    states, y_time, y_energy, y_miss, actions = [], [], [], [], []
    for row in rows:
        if row.get("success") != "1":
            continue  # only tasks with a real completion time are usable
        tct = _to_float(row.get("completion_time_s"))
        if tct is None:
            continue
        energy = _to_float(row.get("energy_j"))
        state = row.get("normalized_state")
        action = row.get("selected_action")
        if energy is None or not state or action in (None, ""):
            continue
        states.append(json.loads(state))
        y_time.append(tct)
        y_energy.append(energy)
        y_miss.append(int(row.get("deadline_missed", "0")) == 1)
        actions.append(int(action))

    if not states:
        raise RuntimeError("no usable training rows in dataset")

    X = np.asarray(states, dtype=np.float32)
    time_arr = np.asarray(y_time, dtype=np.float32)
    energy_arr = np.asarray(y_energy, dtype=np.float32)
    miss_arr = np.asarray(y_miss, dtype=np.float32)
    action_arr = np.asarray(actions, dtype=np.int64)

    # Standardize features and the two continuous targets.
    feature_mean = X.mean(axis=0)
    feature_std = X.std(axis=0) + 1.0e-8
    X_norm = (X - feature_mean) / feature_std
    time_mean, time_std = float(time_arr.mean()), float(time_arr.std() + 1.0e-8)
    energy_mean, energy_std = float(energy_arr.mean()), float(energy_arr.std() + 1.0e-8)
    time_norm = (time_arr - time_mean) / time_std
    energy_norm = (energy_arr - energy_mean) / energy_std
    # Dataset min/max of the two continuous targets: used at inference time to
    # min-max scale the predicted latency/energy into [0, 1] for DRL block 6.
    time_min, time_max = float(time_arr.min()), float(time_arr.max())
    energy_min, energy_max = float(energy_arr.min()), float(energy_arr.max())
    targets = np.stack([time_norm, energy_norm, miss_arr], axis=1).astype(np.float32)

    X_t = torch.from_numpy(X_norm)
    act_t = torch.from_numpy(action_arr)
    tgt_t = torch.from_numpy(targets)

    model = MultiActionOutcomeRegressor(
        input_dim=X.shape[1],
        action_count=cfg.action_count,
        outcome_count=cfg.outcome_count,
        hidden_sizes=cfg.hidden_sizes,
        dropout=cfg.dropout,
    ).to(cfg.device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )

    for epoch in range(cfg.epochs):
        model.train()
        perm = torch.randperm(len(X_t))
        epoch_loss = 0.0
        for start in range(0, len(X_t), cfg.batch_size):
            idx = perm[start:start + cfg.batch_size]
            optimizer.zero_grad()
            predictions = model(X_t[idx])
            loss = masked_action_outcome_loss(
                predictions, act_t[idx], tgt_t[idx], miss_loss_weight=cfg.miss_loss_weight
            )
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss)
        if (epoch + 1) % 25 == 0 or epoch == 0:
            print(f"[phase2] epoch {epoch + 1}/{cfg.epochs} loss={epoch_loss:.4f}")

    os.makedirs(os.path.dirname(checkpoint) or ".", exist_ok=True)
    torch.save(
        {
            "feature_mean": feature_mean,
            "feature_std": feature_std,
            "target_mean": np.array([time_mean, energy_mean], dtype=np.float32),
            "target_std": np.array([time_std, energy_std], dtype=np.float32),
            "target_min": np.array([time_min, energy_min], dtype=np.float32),
            "target_max": np.array([time_max, energy_max], dtype=np.float32),
            "model_args": {
                "input_dim": int(X.shape[1]),
                "action_count": cfg.action_count,
                "outcome_count": cfg.outcome_count,
                "hidden_sizes": cfg.hidden_sizes,
                "dropout": cfg.dropout,
            },
            "model_state": model.state_dict(),
        },
        checkpoint,
    )
    print(f"[phase2] trained on {len(states)} samples -> {checkpoint}")
    return checkpoint


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/dataset/dataset.csv")
    parser.add_argument("--checkpoint", default="data/saved_models/regression.pt")
    args = parser.parse_args()
    run(args.dataset, args.checkpoint)
