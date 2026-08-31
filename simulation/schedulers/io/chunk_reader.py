from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from simulation.entities.task import Task
from simulation.environment import VehicleSnapshot

_CHUNK_NUMBER = re.compile(r"chunk_(\d+)\.xml$")

def numeric_chunk_paths(directory: str | Path) -> list[Path]:
    paths: list[tuple[int, Path]] = []
    for path in Path(directory).glob("chunk_*.xml"):
        match = _CHUNK_NUMBER.search(path.name)
        if match:
            paths.append((int(match.group(1)), path))
    return [path for _, path in sorted(paths)]

def load_vehicle_chunk(path: str | Path) -> dict[float, list[VehicleSnapshot]]:
    root = ET.parse(path).getroot()
    result: dict[float, list[VehicleSnapshot]] = {}
    for timestep in root.findall(".//timestep"):
        now = float(timestep.get("time", "0"))
        snapshots: list[VehicleSnapshot] = []
        for element in timestep.findall("vehicle"):
            snapshots.append(
                VehicleSnapshot(
                    node_id=_required(element, "id"),
                    x=float(_required(element, "x")),
                    y=float(_required(element, "y")),
                    speed_mps=float(element.get("speed", "0")),
                    heading_deg=float(element.get("angle", "0")),
                    lane_id=element.get("lane", ""),
                    vehicle_type=element.get("type", "PKW_special"),
                    generation_rate=float(element.get("base_lambda", "0")),
                    qoe=float(element.get("qoe", "1")),
                )
            )
        result[now] = snapshots
    return result

def load_task_chunk(path: str | Path) -> dict[float, list[Task]]:
    root = ET.parse(path).getroot()
    result: dict[float, list[Task]] = {}
    for timestep in root.findall(".//timestep"):
        now = float(timestep.get("time", "0"))
        tasks: list[Task] = []
        for element in timestep.findall("task"):
            tasks.append(
                Task.from_generator_record(
                    task_id=_required(element, "id"),
                    creator_id=_required(element, "creator"),
                    timestep=now,
                    deadline=float(_required(element, "deadline")),
                    data_size_mbit=float(_required(element, "dataSize")),
                    kilo_cycles_per_bit=float(
                        _required(element, "cycles_per_bit")
                    ),
                    required_compute_units=_optional_float(element, "exec_time"),
                    metadata={
                        "generator_power": _optional_float(element, "power"),
                    },
                )
            )
        result[now] = tasks
    return result

def _required(element: ET.Element, key: str) -> str:
    value = element.get(key)
    if value is None:
        raise ValueError(f"missing XML attribute {key!r} on <{element.tag}>")
    return value

def _optional_float(element: ET.Element, key: str) -> float | None:
    value = element.get(key)
    return None if value is None else float(value)