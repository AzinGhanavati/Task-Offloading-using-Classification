<<<<<<< HEAD
"""Top-level pipeline CLI for the VEC task-offloading project.

Runs the phases in order (data collection -> regression -> predictive DRL).
Use ``--phase`` to run a single phase, or omit it to run all three.

Examples:
    python main.py                          # run all phases
    python main.py --phase 1                # offline data collection only
    python main.py --phase 3 --timesteps 50000
"""

from __future__ import annotations

=======
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

<<<<<<< HEAD
from runners import phase1_data_collection, phase2_train_regression, phase3_train_drl

=======
from runners import (
    phase1_data_collection,
    phase2_train_regression,
    phase3_train_drl,
    phase4_evaluate
)
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb

def main() -> None:
    parser = argparse.ArgumentParser(description="VEC prediction-aware offloading pipeline")
    parser.add_argument(
<<<<<<< HEAD
        "--phase", type=int, default=None, choices=[1, 2, 3],
        help="run a single phase (1=data collection, 2=regression, 3=DRL). "
        "Omit to run all.",
    )
    parser.add_argument("--vehicles", default="data/chunks/vehicles")
    parser.add_argument("--tasks", default="data/chunks/tasks")
    parser.add_argument("--dataset", default="data/dataset/dataset.csv")
    parser.add_argument("--regression", default="data/saved_models/regression.pt")
    parser.add_argument("--drl-model", default="data/saved_models/vfc_ppo_model")
=======
        "--phase", type=int, default=None, choices=[1, 2, 3, 4],
        help="run a single phase (1=data collection, 2=regression, 3=DRL, 4=evaluation).",
    )
    # Training Data Paths
    parser.add_argument("--vehicles", default="data/chunks/vehicles")
    parser.add_argument("--tasks", default="data/chunks/tasks")
    parser.add_argument("--dataset", default="data/dataset/dataset.csv")
    
    # Testing/Evaluation Data Paths
    parser.add_argument("--test-vehicles", default="data/chunks_test/vehicles")
    parser.add_argument("--test-tasks", default="data/chunks_test/tasks")
    parser.add_argument("--eval-out-prefix", default="data/chunks_test/metrics/eval")
    
    # Model Paths
    parser.add_argument("--regression", default="data/saved_models/regression.pt")
    parser.add_argument("--drl-model", default="data/saved_models/vfc_ppo_model")
    
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.phase in (None, 1):
<<<<<<< HEAD
        phase1_data_collection.run(
            args.vehicles, args.tasks, args.dataset, seed=args.seed
        )
    if args.phase in (None, 2):
        phase2_train_regression.run(args.dataset, args.regression)
    if args.phase in (None, 3):
        phase3_train_drl.run(
            args.vehicles, args.tasks, args.regression, args.drl_model, args.timesteps
        )
    print("pipeline finished")


if __name__ == "__main__":
    main()
=======
        phase1_data_collection.run(args.vehicles, args.tasks, args.dataset, seed=args.seed)
    if args.phase in (None, 2):
        phase2_train_regression.run(args.dataset, args.regression)
    if args.phase in (None, 3):
        phase3_train_drl.run(args.vehicles, args.tasks, args.regression, args.drl_model, args.timesteps)
    if args.phase in (None, 4):
        phase4_evaluate.run(
            vehicles_dir=args.test_vehicles, 
            tasks_dir=args.test_tasks, 
            regression_checkpoint=args.regression, 
            drl_model_path=args.drl_model, 
            out_prefix=args.eval_out_prefix
        )
    print("pipeline finished")

if __name__ == "__main__":
    main()
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
