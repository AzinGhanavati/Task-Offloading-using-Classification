"""Phase 4 of the project: train the predictive DRL agent.

Loads the trained multi-head regression (from ``phase2``) into the SDN, so the
simulator emits augmented, prediction-aware states.  The MaskablePPO agent is
then trained on the ``VFCOffloadingEnv`` gym wrapper using the adaptive reward.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.hyperparameters import default_hyperparameters
from models.DRL.train_sb3 import train_agent
from models.DRL.vfc_env import VFCOffloadingEnv
from models.regression.torch_predictor import TorchRegressionPredictor
from runners.common import build_infrastructure, build_scenario, vehicle_points
from simulation.environment import SimulationEnvironment
from simulation.network.urban_grid import UrbanGrid


def run(
    vehicles_dir: str,
    tasks_dir: str,
    regression_checkpoint: str,
    model_out: str,
    total_timesteps: int | None = None,
) -> str:
    hyper = default_hyperparameters()
    scenario = build_scenario(vehicles_dir, tasks_dir)
    if not scenario.task_templates:
        raise RuntimeError(f"no tasks found under {tasks_dir!r}")

    config, cloud, edge_servers = build_infrastructure(
        hyper, vehicle_points(scenario)
    )
    grid = UrbanGrid(hyper.urban_grid)
    predictor = TorchRegressionPredictor(regression_checkpoint)

    env = SimulationEnvironment(
        edge_servers=edge_servers,
        fog_nodes=[],
        cloud=cloud,
        config=config,
        hyperparameters=hyper,
        urban_grid=grid,
        predictor=predictor,
    )
    gym_env = VFCOffloadingEnv(env, scenario)
    model = train_agent(gym_env, hyper.drl, total_timesteps=total_timesteps)

    out_prefix = os.path.splitext(model_out)[0]
    os.makedirs(os.path.dirname(model_out) or ".", exist_ok=True)
    model.save(out_prefix)
    print(f"[phase3] DRL model saved -> {out_prefix}.zip")
    return out_prefix


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicles", default="data/chunks/vehicles")
    parser.add_argument("--tasks", default="data/chunks/tasks")
    parser.add_argument(
        "--regression", default="data/saved_models/regression.pt"
    )
    parser.add_argument("--out", default="data/saved_models/vfc_ppo_model")
    parser.add_argument("--timesteps", type=int, default=None)
    args = parser.parse_args()
    run(args.vehicles, args.tasks, args.regression, args.out, args.timesteps)
