import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy

from .vfc_env import VFCOffloadingEnv

def mask_fn(env: VFCOffloadingEnv) -> np.ndarray:
    """Helper function to extract action masks for SB3."""
    return env.action_masks()

def train_agent(simulation_env, state_dim: int, total_timesteps: int = 100_000):
    # Initialize the custom Gymnasium environment
    raw_env = VFCOffloadingEnv(
        simulation_env=simulation_env,
        state_dim=state_dim
    )
    
    # Wrap environment to enable action masking capabilities
    env = ActionMasker(raw_env, mask_fn)

    # Define Neural Network architecture (equivalent to 256, 128 hidden layers)
    policy_kwargs = dict(
        net_arch=dict(pi=[256, 128], vf=[256, 128])
    )

    # Initialize Maskable PPO model
    model = MaskablePPO(
        MaskableActorCriticPolicy,
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        policy_kwargs=policy_kwargs,
        verbose=1,
        device="auto"
    )

    print("Starting SB3 Training...")
    model.learn(total_timesteps=total_timesteps)

    # Save the trained model
    model.save("vfc_ppo_model")
    print("Model saved successfully.")
    
    return model