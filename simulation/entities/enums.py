from __future__ import annotations
from enum import Enum, IntEnum

class NodeKind(str, Enum):
    VEHICLE = "vehicle"
    MOBILE_FOG = "mobile_fog"
    EDGE = "edge"
    CLOUD = "cloud"

class TaskStatus(str, Enum):
    CREATED = "created"
    DECIDED = "decided"
    TRANSMITTING = "transmitting"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class OffloadAction(IntEnum):
    LOCAL = 0
    CLOUD = 1
    CANDIDATE_1 = 2
    CANDIDATE_2 = 3
    CANDIDATE_3 = 4

class AdmissionDecision(IntEnum):
    LOCAL = 0
    ESCALATE_TO_SDN = 1