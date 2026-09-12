from __future__ import annotations

import numpy as np

from config.hyperparameters import DRLTrainingConfig, default_hyperparameters


def mask_fn(env) -> np.ndarray:
    """Extract the boolean action mask for ``sb3_contrib.ActionMasker``."""
    return env.action_masks()


def train_agent(env, config: DRLTrainingConfig | None = None, total_timesteps: int | None = None):
    """Train a MaskablePPO agent on a pre-built ``VFCOffloadingEnv``.

    ``env`` must already have the trained regression predictor wired in, so the
    observations are the augmented (prediction-aware) states.
    """
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
    from sb3_contrib.common.wrappers import ActionMasker

    cfg = config or default_hyperparameters().drl
    masked_env = ActionMasker(env, mask_fn)

    policy_kwargs = dict(
        net_arch=dict(pi=list(cfg.policy_net), vf=list(cfg.value_net))
    )
    model = MaskablePPO(
        MaskableActorCriticPolicy,
        masked_env,
        learning_rate=cfg.learning_rate,
        n_steps=cfg.n_steps,
        batch_size=cfg.batch_size,
        clip_range=cfg.clip_range,
        ent_coef=cfg.ent_coef,
        vf_coef=cfg.vf_coef,
        gamma=cfg.gamma,
        gae_lambda=cfg.gae_lambda,
        max_grad_norm=cfg.max_grad_norm,
        policy_kwargs=policy_kwargs,
        verbose=1,
        device=cfg.device,
    )

    print("Starting MaskablePPO training...")
    model.learn(total_timesteps=total_timesteps or cfg.total_timesteps)
    return model
