from __future__ import annotations

from dataclasses import dataclass, field

from simulation.entities.enums import AdmissionDecision

from .base import AdmissionContext, LocalAdmissionPolicy
from .threshold_admission import ThresholdAdmissionPolicy
from .linucb_admission import LinUCBAdmissionPolicy


@dataclass(slots=True)
class VehicleFilter:
    """Deployment-facing facade for interchangeable admission policies."""

    # policy: LocalAdmissionPolicy = field(default_factory=ThresholdAdmissionPolicy)
    policy: LocalAdmissionPolicy = field(default_factory=LinUCBAdmissionPolicy)

    def decide(self, context: AdmissionContext) -> AdmissionDecision:
        return self.policy.decide(context)
