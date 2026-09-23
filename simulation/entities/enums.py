from __future__ import annotations

from enum import Enum, IntEnum


class NodeKind(str, Enum):
    VEHICLE = "vehicle"
    MOBILE_FOG = "mobile_fog"
    FIXED_FOG = "fixed_fog"
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
    """Stable DRL action slots.

    Ordering matters: the integer value of an action is also its index into the
    action catalog and the action mask.  Candidates occupy slots 1-3 (dynamically
    the three nearest reachable Fog/Edge nodes); the cloud is always slot 4.
    """

    LOCAL = 0
    CANDIDATE_1 = 1
    CANDIDATE_2 = 2
    CANDIDATE_3 = 3
    CLOUD = 4


class AdmissionDecision(IntEnum):
    LOCAL = 0
    ESCALATE_TO_SDN = 1
