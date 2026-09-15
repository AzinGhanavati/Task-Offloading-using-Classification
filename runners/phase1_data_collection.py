"""Phase 2 of the project: offline data collection with a random policy.

Runs the full discrete-event simulator over the SUMO scenario, letting a
uniform-random offloading policy explore the state space. A dataset recorder
captures decision-time features plus factual labels (TCT, energy, slack) for
every task, which becomes the training set for the regression model.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.hyperparameters import default_hyperparameters
from models.DRL.random_policy import RandomOffloadingPolicy
from runners.common import build_infrastructure, build_scenario, vehicle_points
from simulation.environment import SimulationEnvironment
from simulation.io.dataset_recorder import OfflineDatasetRecorder
from simulation.network.urban_grid import UrbanGrid
from utils.metrics_logger import MetricsLogger, EvaluationMetricsLogger

def run(
    vehicles_dir: str,
    tasks_dir: str,
    out_csv: str,
    seed: int = 42,
    energy_label_scope: str = "vehicle",
) -> str:
    hyper = default_hyperparameters()
    scenario = build_scenario(vehicles_dir, tasks_dir)
    if not scenario.task_templates:
        raise RuntimeError(f"no tasks found under {tasks_dir!r}")

    config, cloud, edge_servers = build_infrastructure(
        hyper, vehicle_points(scenario)
    )
    grid = UrbanGrid(hyper.urban_grid)
    env = SimulationEnvironment(
        edge_servers=edge_servers,
        fog_nodes=[],
        cloud=cloud,
        config=config,
        hyperparameters=hyper,
        urban_grid=grid,
        offloading_policy=RandomOffloadingPolicy(seed),
    )

    # Initialize all observers once
    recorder = OfflineDatasetRecorder(energy_label_scope=energy_label_scope)
    metrics = MetricsLogger()
    eval_metrics = EvaluationMetricsLogger(step_interval_s=5)

    print("[phase1] Loading scenario and scheduling events. Please wait...")
    # Attach all observers to the environment
    env.add_observer(recorder)
    env.add_observer(metrics)
    env.add_observer(eval_metrics)

    # Schedule and run ONLY ONCE
    for time, snapshots in scenario.vehicle_snapshots():
        env.schedule_vehicle_snapshot(time, snapshots)
    for task in scenario.make_tasks():
        env.schedule_task(task, bypass_admission=True)
        
    print(f"[phase1] Total events scheduled: {len(env._events)}")
    print("[phase1] Starting simulation event loop...")
    
    env.run()

    # Save the dataset required for Phase 2
    recorder.write_csv(out_csv)
    
    # Save original summary metrics
    metrics_path = out_csv.rsplit(".", 1)[0] + ".metrics.csv"
    metrics.write_csv(metrics_path)
    
    # Save the new detailed evaluation logs
    base_path = out_csv.rsplit(".", 1)[0]
    task_log_path = f"{base_path}_tasks_log.csv"
    step_log_path = f"{base_path}_timestep_log.csv"
    eval_metrics.write_csvs(task_csv_path=task_log_path, step_csv_path=step_log_path)

    # Print terminal summary
    summary = metrics.summary()
    print(
        "[phase1] tasks=%(total)d completed=%(completed)d "
        "miss_rate=%.3f avg_tct=%.3fs dataset=%s"
        % (
            summary.get("total", 0),
            summary.get("completed", 0),
            summary.get("deadline_miss_rate", 0.0),
            summary.get("avg_completion_time_s", 0.0),
            out_csv,
        )
    )
    print(f"[phase1] Data collection finished.")
    print(f"[phase1] Task Log: {task_log_path}")
    print(f"[phase1] Step Log: {step_log_path}")
    
    return out_csv

if __name__ == "__main__":
    run("data/chunks/vehicles", "data/chunks/tasks", "data/dataset/dataset.csv")