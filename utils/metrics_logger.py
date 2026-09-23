from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from simulation.entities.task import Task


class MetricsLogger:
    """Accumulate per-task outcome metrics and produce aggregate summaries.

    A logger instance is attached as a simulation observer (it implements
    ``on_final``) or called directly with completed/failed tasks.  It collects
    the metrics that matter for the offloading objective: completion time,
    slack, energy, deadline-miss, and a per-action breakdown.
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    @property
    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    def record(self, task: Task) -> None:
        self._records.append(
            {
                "task_id": task.task_id,
                "creator_id": task.creator_id,
                "action": int(task.chosen_action) if task.chosen_action is not None else None,
                "target_node_id": task.target_node_id,
                "status": task.status.value,
                "success": int(task.succeeded),
                "deadline_missed": int(bool(task.deadline_missed)),
                "completion_time_s": task.completion_time_s,
                "slack_s": task.slack_s,
                "vehicle_energy_j": task.vehicle_energy_j,
                "system_energy_j": task.system_energy_j,
                "queue_waiting_time_s": task.queue_waiting_time_s,
                "processing_time_s": task.processing_time_s,
                "wireless_time_s": task.wireless_time_s,
                "wired_time_s": task.wired_time_s,
                "failure_reason": task.failure_reason or "",
            }
        )

    def on_decision(self, task: Task, context, action) -> None:
        """Observer hook (no-op); metrics are only meaningful at terminal state."""
        return None

    def on_final(self, task: Task) -> None:
        """Observer hook: record a task once it reaches a terminal state."""
        self.record(task)

    def summary(self) -> dict[str, Any]:
        records = self._records
        total = len(records)
        if total == 0:
            return {"total": 0}

        completed = [r for r in records if r["success"]]
        failed = [r for r in records if not r["success"]]
        missed = [r for r in records if r["deadline_missed"]]

        def _mean(values: list[float]) -> float:
            values = [v for v in values if v is not None]
            return sum(values) / len(values) if values else 0.0

        per_action: dict[int, dict[str, float]] = {}
        for record in records:
            action = record["action"]
            if action is None:
                continue
            bucket = per_action.setdefault(
                action, {"count": 0, "deadline_missed": 0, "completion_time_s": 0.0}
            )
            bucket["count"] += 1
            bucket["deadline_missed"] += record["deadline_missed"]
            if record["completion_time_s"] is not None:
                bucket["completion_time_s"] += record["completion_time_s"]

        for bucket in per_action.values():
            count = bucket["count"]
            bucket["miss_rate"] = bucket["deadline_missed"] / count if count else 0.0
            bucket["avg_completion_time_s"] = (
                bucket["completion_time_s"] / bucket["count"]
                if bucket["completion_time_s"] > 0.0
                else 0.0
            )

        return {
            "total": total,
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / total,
            "deadline_missed": len(missed),
            "deadline_miss_rate": len(missed) / total,
            "avg_completion_time_s": _mean(
                [r["completion_time_s"] for r in completed]
            ),
            "avg_slack_s": _mean([r["slack_s"] for r in records]),
            "avg_vehicle_energy_j": _mean(
                [r["vehicle_energy_j"] for r in records]
            ),
            "avg_system_energy_j": _mean([r["system_energy_j"] for r in records]),
            "avg_queue_waiting_time_s": _mean(
                [r["queue_waiting_time_s"] for r in records]
            ),
            "per_action": per_action,
        }

    def write_csv(self, path: str | Path) -> None:
        records = self._records
        if not records:
            raise RuntimeError("no records to write")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        for record in records:
            for key in record:
                if key not in fieldnames:
                    fieldnames.append(key)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    def clear(self) -> None:
        self._records.clear()
<<<<<<< HEAD
=======


import csv
import math
from simulation.entities.enums import OffloadAction, TaskStatus

class EvaluationMetricsLogger:
    def __init__(self, step_interval_s: int = 1):
        self.step_interval = step_interval_s
        self.task_logs = []
        self.step_logs = []
        
        # Cumulative tracking
        self.current_step = 0
        self.total_tasks = 0
        self.total_deadline_misses = 0
        self.total_no_resource = 0
        
        self.loc_local = 0
        self.loc_fog = 0
        self.loc_cloud = 0
        
        self.sum_delay = 0.0
        self.sum_energy = 0.0

    def on_decision(self, task, context, action) -> None:
        pass  # Data is captured when the task finishes

    def on_final(self, task) -> None:
        task_time = task.completed_at
        step = math.floor(task_time / self.step_interval) * self.step_interval
        
        # Flush step metrics if simulation time crossed a boundary
        while self.current_step < step:
            self._record_step(self.current_step)
            self.current_step += self.step_interval

        # 1. Calculate Task Metrics
        delay = task.completed_at - task.arrival_time
        total_energy = (
            getattr(task, "vehicle_compute_energy_j", 0.0) +
            getattr(task, "infrastructure_compute_energy_j", 0.0) +
            getattr(task, "vehicle_tx_energy_j", 0.0) +
            getattr(task, "wired_energy_j", 0.0)
        )
        slack = task.completed_at - task.absolute_deadline
        
        is_failed = task.status == TaskStatus.FAILED
        missed_deadline = is_failed or (task.completed_at > task.absolute_deadline)
        
        if is_failed and getattr(task, "failure_reason", "") in ["queue_rejected", "target_missing"]:
            self.total_no_resource += 1

        location = "UNKNOWN"
        action = getattr(task, "chosen_action", None)
        if action == OffloadAction.LOCAL:
            location = "LOCAL"
            self.loc_local += 1
        elif action == OffloadAction.CLOUD:
            location = "CLOUD"
            self.loc_cloud += 1
        elif action in (OffloadAction.CANDIDATE_1, OffloadAction.CANDIDATE_2, OffloadAction.CANDIDATE_3):
            location = "FOG/EDGE"
            self.loc_fog += 1

        # 2. Record Task-Level Data
        self.task_logs.append({
            "Task_ID": task.task_id,
            "Arrival_Time": task.arrival_time,
            "Completed_At": task.completed_at,
            "Location": location,
            "Delay_s": delay,
            "Total_Energy_J": total_energy,
            "Deadline_Missed": missed_deadline,
            "Finish_Minus_Deadline": slack,
            "Status": task.status.name
        })

        # 3. Update Cumulative Counters
        self.total_tasks += 1
        if missed_deadline:
            self.total_deadline_misses += 1
        self.sum_delay += delay
        self.sum_energy += total_energy

    def _record_step(self, step_time: int) -> None:
        avg_delay = self.sum_delay / self.total_tasks if self.total_tasks > 0 else 0.0
        avg_energy = self.sum_energy / self.total_tasks if self.total_tasks > 0 else 0.0
        miss_ratio = self.total_deadline_misses / self.total_tasks if self.total_tasks > 0 else 0.0
        no_res_ratio = self.total_no_resource / self.total_tasks if self.total_tasks > 0 else 0.0
        
        # Matches your exact image columns + averages
        self.step_logs.append({
            "timeStep": step_time,
            "Total deadline misses": self.total_deadline_misses,
            "Total cloud tasks": self.loc_cloud,
            "Total local execution tasks": self.loc_local,
            "Total fog execution tasks": self.loc_fog,
            "Total completed tasks": self.total_tasks,
            "Deadline miss ratio": f"{miss_ratio:.3%}",
            "No Resource found by deadline miss ratio": f"{no_res_ratio:.3%}",
            "Average Delay (s)": avg_delay,
            "Average Energy (J)": avg_energy
        })

    def write_csvs(self, task_csv_path: str, step_csv_path: str) -> None:
        self._record_step(self.current_step)  # Flush final step
        if self.task_logs:
            with open(task_csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.task_logs[0].keys())
                writer.writeheader()
                writer.writerows(self.task_logs)
                
        if self.step_logs:
            with open(step_csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.step_logs[0].keys())
                writer.writeheader()
                writer.writerows(self.step_logs)

    
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
