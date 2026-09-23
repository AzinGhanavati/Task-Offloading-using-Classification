<<<<<<< HEAD
from .adaptive_reward import AdaptiveRewardConfig, adaptive_reward
from .policy import OffloadingPolicy
from .random_policy import RandomOffloadingPolicy

__all__ = [
    "AdaptiveRewardConfig",
    "OffloadingPolicy",
    "RandomOffloadingPolicy",
    "VFCOffloadingEnv",
    "adaptive_reward",
]


def __getattr__(name):
    # Import the gym-dependent environment lazily so the rest of the package
    # (policies, reward) stays usable without gymnasium installed.
    if name == "VFCOffloadingEnv":
        from .vfc_env import VFCOffloadingEnv

        return VFCOffloadingEnv
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
=======
from .adaptive_reward import AdaptiveRewardConfig, adaptive_reward
from .policy import OffloadingPolicy
from .random_policy import RandomOffloadingPolicy

__all__ = [
    "AdaptiveRewardConfig",
    "OffloadingPolicy",
    "RandomOffloadingPolicy",
    "VFCOffloadingEnv",
    "adaptive_reward",
]


def __getattr__(name):
    # Import the gym-dependent environment lazily so the rest of the package
    # (policies, reward) stays usable without gymnasium installed.
    if name == "VFCOffloadingEnv":
        from .vfc_env import VFCOffloadingEnv

        return VFCOffloadingEnv
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
