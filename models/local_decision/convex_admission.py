from __future__ import annotations

from dataclasses import dataclass

from simulation.entities.enums import AdmissionDecision

from .base import AdmissionContext


@dataclass(slots=True)
class ConvexAdmissionPolicy:
    """Closed-form convex relaxation of the binary admission problem.

    x=0 means local and x=1 means escalation.  The objective combines the
    two endpoint costs with a quadratic regularizer, then rounds x at 0.5.
    """

    delay_weight: float = 0.7
    energy_weight: float = 0.3
    congestion_weight: float = 0.2
    regularization: float = 1.0

    def decide(self, context: AdmissionContext) -> AdmissionDecision:
        deadline = max(context.remaining_deadline_s, 1.0e-9)
        energy_scale = max(
            context.local_energy_j, context.estimated_remote_energy_j, 1.0e-9
        )
        local_cost = (
            self.delay_weight
            * (context.local_workload_s + context.local_service_s)
            / deadline
            + self.energy_weight * context.local_energy_j / energy_scale
            + self.congestion_weight * context.local_load
        )
        remote_cost = (
            self.delay_weight * context.estimated_remote_delay_s / deadline
            + self.energy_weight * context.estimated_remote_energy_j / energy_scale
            + self.congestion_weight * context.average_external_load
        )
        # min_x (1-x)C_l + xC_r + lambda(x-0.5)^2, 0<=x<=1.
        relaxed_x = 0.5 - (remote_cost - local_cost) / (
            2.0 * max(self.regularization, 1.0e-9)
        )
        relaxed_x = min(1.0, max(0.0, relaxed_x))
        return (
            AdmissionDecision.ESCALATE_TO_SDN
            if relaxed_x >= 0.5
            else AdmissionDecision.LOCAL
        )

