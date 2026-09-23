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
