from __future__ import annotations

from dataclasses import dataclass

from simulation.entities.enums import AdmissionDecision

from .base import AdmissionContext


@dataclass(slots=True)
class ThresholdAdmissionPolicy:
    """Very light baseline suitable for deployment inside a vehicle."""

    maximum_local_load: float = 0.75
    maximum_generation_rate: float = 4.0
    minimum_qoe: float = 0.5
    safety_factor: float = 0.9

    def decide(self, context: AdmissionContext) -> AdmissionDecision:
        local_finish_s = context.local_workload_s + context.local_service_s
        locally_feasible = (
            local_finish_s <= self.safety_factor * context.remaining_deadline_s
        )
        local_is_healthy = (
            context.local_load <= self.maximum_local_load
            and context.generation_rate <= self.maximum_generation_rate
            and context.qoe >= self.minimum_qoe
        )
        external_is_congested = context.average_external_load > context.local_load
        if locally_feasible and (local_is_healthy or external_is_congested):
            return AdmissionDecision.LOCAL
        return AdmissionDecision.ESCALATE_TO_SDN

