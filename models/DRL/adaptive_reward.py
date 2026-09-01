from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdaptiveRewardConfig:
    alpha_min: float = 0.2
    alpha_max: float = 0.8
    beta_min: float = 0.2
    beta_max: float = 0.8
    slack_temperature_s: float = 2.0
    delay_scale_s: float = 10.0
    energy_scale_j: float = 1.0
    deadline_miss_penalty: float = 1.0


def adaptive_reward(
    *,
    actual_completion_time_s: float,
    actual_energy_j: float,
    remaining_deadline_at_decision_s: float,
    predicted_completion_time_s: float,
    deadline_missed: bool,
    config: AdaptiveRewardConfig = AdaptiveRewardConfig(),
) -> tuple[float, float, float, float]:
    """Return reward, alpha, beta, predicted slack.

    Small/negative predicted slack raises alpha; large slack raises beta.  The
    actual outcome remains the optimized signal, avoiding reward leakage from
    the predictor.
    """

    predicted_slack_s = (
        remaining_deadline_at_decision_s - predicted_completion_time_s
    )
    temperature = max(config.slack_temperature_s, 1.0e-9)
    z = max(-60.0, min(60.0, predicted_slack_s / temperature))
    urgency = 1.0 / (1.0 + math.exp(z))
    alpha = config.alpha_min + urgency * (
        config.alpha_max - config.alpha_min
    )
    beta = config.beta_max - urgency * (config.beta_max - config.beta_min)
    delay_term = actual_completion_time_s / max(config.delay_scale_s, 1.0e-9)
    energy_term = actual_energy_j / max(config.energy_scale_j, 1.0e-9)
    reward = -(alpha * delay_term + beta * energy_term)
    if deadline_missed:
        reward -= config.deadline_miss_penalty
    return reward, alpha, beta, predicted_slack_s

