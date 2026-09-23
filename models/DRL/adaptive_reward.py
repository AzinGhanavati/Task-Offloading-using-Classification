<<<<<<< HEAD
"""Slack-adaptive reward for the predictive DRL phase.

Implements exactly:

    S_pred = D_remaining - T_pred
    U      = 1 / (1 + exp(S_pred / tau))
    alpha  = alpha_min + U * (alpha_max - alpha_min)
    beta   = beta_max - U * (beta_max - beta_min)
    R      = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss

where:
    S_pred   predicted slack: remaining deadline at decision time minus the
             completion time predicted by the regression model (T_pred).
    U        urgency in (0, 1): ~1 when the task is about to miss its
             deadline (low/negative slack), ~0 when slack is plentiful.
    T_scale  data-driven delay scale = dataset max completion time.
    E_scale  data-driven energy scale = dataset max energy.
    P_miss   constant penalty applied only if the task actually misses its
             absolute deadline.

T_scale and E_scale are NEVER hand-picked round numbers: the environment
derives them from the regression checkpoint (dataset max of the two labels),
so both scaled terms naturally fall in roughly [0, 1] and the weights
alpha/beta directly express their relative importance.
"""

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
    # T_scale / E_scale must be data-driven (dataset max completion time /
    # energy). The neutral 1.0 values are only a fallback for cases without a
    # regression checkpoint; VFCOffloadingEnv derives the real scales itself.
    delay_scale_s: float = 1.0
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
    """Return (reward, alpha, beta, predicted_slack)."""

    # S_pred = D_remaining - T_pred
    predicted_slack_s = (
        remaining_deadline_at_decision_s - predicted_completion_time_s
    )
    # U = 1 / (1 + exp(S_pred / tau))
    temperature = max(config.slack_temperature_s, 1.0e-9)
    z = max(-60.0, min(60.0, predicted_slack_s / temperature))
    urgency = 1.0 / (1.0 + math.exp(z))

    # alpha = alpha_min + U * (alpha_max - alpha_min)
    alpha = config.alpha_min + urgency * (config.alpha_max - config.alpha_min)
    # beta = beta_max - U * (beta_max - beta_min)
    beta = config.beta_max - urgency * (config.beta_max - config.beta_min)

    # R = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss
    delay_term = actual_completion_time_s / max(config.delay_scale_s, 1.0e-9)
    energy_term = actual_energy_j / max(config.energy_scale_j, 1.0e-9)
    reward = -(alpha * delay_term + beta * energy_term)

    if deadline_missed:
        reward -= config.deadline_miss_penalty

    return reward, alpha, beta, predicted_slack_s
=======
"""Slack-adaptive reward for the predictive DRL phase.

Implements exactly:

    S_pred = D_remaining - T_pred
    U      = 1 / (1 + exp(S_pred / tau))
    alpha  = alpha_min + U * (alpha_max - alpha_min)
    beta   = beta_max - U * (beta_max - beta_min)
    R      = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss

where:
    S_pred   predicted slack: remaining deadline at decision time minus the
             completion time predicted by the regression model (T_pred).
    U        urgency in (0, 1): ~1 when the task is about to miss its
             deadline (low/negative slack), ~0 when slack is plentiful.
    T_scale  data-driven delay scale = dataset max completion time.
    E_scale  data-driven energy scale = dataset max energy.
    P_miss   constant penalty applied only if the task actually misses its
             absolute deadline.

T_scale and E_scale are NEVER hand-picked round numbers: the environment
derives them from the regression checkpoint (dataset max of the two labels),
so both scaled terms naturally fall in roughly [0, 1] and the weights
alpha/beta directly express their relative importance.
"""

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
    # T_scale / E_scale must be data-driven (dataset max completion time /
    # energy). The neutral 1.0 values are only a fallback for cases without a
    # regression checkpoint; VFCOffloadingEnv derives the real scales itself.
    delay_scale_s: float = 1.0
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
    """Return (reward, alpha, beta, predicted_slack)."""

    # S_pred = D_remaining - T_pred
    predicted_slack_s = (
        remaining_deadline_at_decision_s - predicted_completion_time_s
    )
    # U = 1 / (1 + exp(S_pred / tau))
    temperature = max(config.slack_temperature_s, 1.0e-9)
    z = max(-60.0, min(60.0, predicted_slack_s / temperature))
    urgency = 1.0 / (1.0 + math.exp(z))

    # alpha = alpha_min + U * (alpha_max - alpha_min)
    alpha = config.alpha_min + urgency * (config.alpha_max - config.alpha_min)
    # beta = beta_max - U * (beta_max - beta_min)
    beta = config.beta_max - urgency * (config.beta_max - config.beta_min)

    # R = -(alpha * T_actual / T_scale + beta * E_actual / E_scale) - P_miss
    delay_term = actual_completion_time_s / max(config.delay_scale_s, 1.0e-9)
    energy_term = actual_energy_j / max(config.energy_scale_j, 1.0e-9)
    reward = -(alpha * delay_term + beta * energy_term)

    if deadline_missed:
        reward -= config.deadline_miss_penalty

    return reward, alpha, beta, predicted_slack_s
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
