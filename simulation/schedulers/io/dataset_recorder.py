from __future__ import annotations
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from simulation.entities.enums import OffloadAction
from simulation.entities.sdn_controller import DecisionContext
from simulation.entities.task import Task

class OfflineDatasetRecorder:
    """Joins decision time features with post simulation factual labels."""
    def __init__(self, *, energy_label_scope: str = "vehicle") -> None:
        if energy_label_scope not in {"vehicle", "system"}:
            raise ValueError("energy_label_scope must be vehicle or system")
        self.energy_label_scope = energy_label_scope
        self._rows: dict[str, dict[str, Any]] = {}

    def on_decision(
        self,
        task: Task,
        context: DecisionContext,
        action: OffloadAction,
    ) -> None:
        row: dict[str, Any] = {
            "task_id": task.task_id,
            "creator_id": task.creator_id,
            "arrival_time": task.arrival_time,
            "absolute_deadline": task.absolute_deadline,
            **context.raw_state.global_features,
            "selected_action": int(action),
            "selected_target_id": context.catalog[int(action)].target_node_id,
            "gateway_edge_id": context.catalog[int(action)].gateway_edge_id,
            "action_mask": json.dumps(context.action_mask, separators=(",", ":")),
            "behavior_policy": "uniform_random_valid_actions",
            "behavior_probability": 1.0 / max(1, sum(context.action_mask)),
            "energy_label_scope": self.energy_label_scope,
        }
        for action_index, features in enumerate(context.raw_state.action_features):
            for name, value in asdict(features).items():
                row[f"a{action_index}_{name}"] = value
        self._rows[task.task_id] = row

    def on_final(self, task: Task) -> None:
        row = self._rows.get(task.task_id)
        if row is None:
            return
        selected_energy = (
            task.vehicle_energy_j
            if self.energy_label_scope == "vehicle"
            else task.system_energy_j
        )
        row.update(
            {
                "target_node_id": task.target_node_id,
                "completion_time_s": task.completion_time_s,
                "vehicle_energy_j": task.vehicle_energy_j,
                "system_energy_j": task.system_energy_j,
                "energy_j": selected_energy,
                "slack_s": task.slack_s,
                "deadline_missed": int(bool(task.deadline_missed)),
                "success": int(task.succeeded),
                "failure_reason": task.failure_reason or "",
                "wireless_time_s": task.wireless_time_s,
                "wired_time_s": task.wired_time_s,
                "queue_waiting_time_s": task.queue_waiting_time_s,
                "processing_time_s": task.processing_time_s,
                "transmission_attempts": task.transmission_attempts,
                "packet_loss_rate": task.packet_loss_rate,
                "achieved_wireless_rate_bps": task.achieved_wireless_rate_bps,
                "achieved_wired_rate_bps": task.achieved_wired_rate_bps,
            }
        )

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [self._rows[key] for key in sorted(self._rows)]

    def write_csv(self, path: str | Path) -> None:
        rows = self.rows
        if not rows:
            raise RuntimeError("no finalized decision rows to write")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)