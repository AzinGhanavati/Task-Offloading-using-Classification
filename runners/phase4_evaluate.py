"""Phase 4 of the project: Evaluation (Deployment Inference).

Runs the full discrete-event simulator over an UNSEEN test scenario.
Tasks are first filtered by the local CMAB policy (LinUCB). If escalated,
the trained DRL agent (MaskablePPO) + Regression Twin makes the offloading decision.
"""

from __future__ import annotations

import os
import sys
import numpy as np
from sb3_contrib import MaskablePPO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.hyperparameters import default_hyperparameters
from runners.common import build_infrastructure, build_scenario, vehicle_points
from simulation.environment import SimulationEnvironment
from simulation.network.urban_grid import UrbanGrid
from utils.metrics_logger import MetricsLogger, EvaluationMetricsLogger
from models.regression.torch_predictor import TorchRegressionPredictor
from models.local_decision.linucb_admission import LinUCBAdmissionPolicy
from simulation.entities.enums import OffloadAction


class TrainedDRLPolicy:
    """Wrapper to use the trained PPO model for deterministic inference."""
    def __init__(self, model_path: str):
        self.model = MaskablePPO.load(model_path)

    def select_action(self, context) -> OffloadAction:
        obs = np.asarray(context.augmented_state, dtype=np.float32)
        mask = np.asarray(context.action_mask, dtype=bool)
        # deterministic=True is crucial for evaluation
        action, _ = self.model.predict(obs, action_masks=mask, deterministic=True)
        return OffloadAction(int(action))


def run(
    vehicles_dir: str,
    tasks_dir: str,
    regression_checkpoint: str,
    drl_model_path: str,
    out_prefix: str,
) -> str:
    hyper = default_hyperparameters()
    scenario = build_scenario(vehicles_dir, tasks_dir)
    if not scenario.task_templates:
        raise RuntimeError(f"no TEST tasks found under {tasks_dir!r}")

    config, cloud, edge_servers = build_infrastructure(hyper, vehicle_points(scenario))
    grid = UrbanGrid(hyper.urban_grid)

    predictor = TorchRegressionPredictor(regression_checkpoint)
    drl_policy = TrainedDRLPolicy(drl_model_path)
    cmab_policy = LinUCBAdmissionPolicy()

    env = SimulationEnvironment(
        edge_servers=edge_servers,
        fog_nodes=[],
        cloud=cloud,
        config=config,
        hyperparameters=hyper,
        urban_grid=grid,
        admission_policy=cmab_policy,
        offloading_policy=drl_policy,
        predictor=predictor,
    )

    metrics = MetricsLogger()
    eval_metrics = EvaluationMetricsLogger(step_interval_s=5)
    
    env.add_observer(metrics)
    env.add_observer(eval_metrics)

    for time, snapshots in scenario.vehicle_snapshots():
        env.schedule_vehicle_snapshot(time, snapshots)
        
    # CRITICAL: bypass_admission=False ensures tasks pass through CMAB first
    for task in scenario.make_tasks():
        env.schedule_task(task, bypass_admission=False)

    print(f"[phase4] Starting evaluation on TEST data: {tasks_dir}")
    env.run()

    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)
    metrics_path = f"{out_prefix}.metrics.csv"
    task_log_path = f"{out_prefix}_tasks_log.csv"
    step_log_path = f"{out_prefix}_timestep_log.csv"
    
    metrics.write_csv(metrics_path)
    eval_metrics.write_csvs(task_csv_path=task_log_path, step_csv_path=step_log_path)

    summary = metrics.summary()
    print(
        "[phase4] Evaluation finished: tasks=%(total)d completed=%(completed)d "
        "miss_rate=%.3f avg_tct=%.3fs"
        % (
            summary.get("total", 0),
            summary.get("completed", 0),
            summary.get("deadline_miss_rate", 0.0),
            summary.get("avg_completion_time_s", 0.0),
        )
    )
    print(f"[phase4] Detailed tables saved to: {task_log_path} & {step_log_path}")
    return out_prefix

if __name__ == "__main__":
    run(
        vehicles_dir="data/chunks_test/vehicles",
        tasks_dir="data/chunks_test/tasks",
        regression_checkpoint="data/saved_models/regression.pt",
        drl_model_path="data/saved_models/vfc_ppo_model",
        out_prefix="data/chunks_test/metrics/evaluation"
    )