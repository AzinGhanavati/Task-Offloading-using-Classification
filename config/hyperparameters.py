from __future__ import annotations

from dataclasses import dataclass, field

# ============================================================================
# Action space (stable slot -> integer mapping)
# ----------------------------------------------------------------------------
# The DRL agent always operates over these five fixed slots, regardless of
# which physical node currently occupies a candidate slot:
#
#     0 -> LOCAL         (execute on the vehicle)
#     1 -> CANDIDATE_1   (nearest Fog/Edge node)
#     2 -> CANDIDATE_2   (second nearest Fog/Edge node)
#     3 -> CANDIDATE_3   (third nearest Fog/Edge node)
#     4 -> CLOUD         (execute on the cloud, via the nearest edge gateway)
# ============================================================================
LOCAL_ACTION = 0
CANDIDATE_ACTIONS = (1, 2, 3)
CLOUD_ACTION = 4
NUM_ACTIONS = 5

# ============================================================================
# Normalization constants for the 6-block state vector
# ----------------------------------------------------------------------------
# Every raw feature is divided by one of these scales and clamped to [0, 1].
# They are hyperparameters: tune them to the actual data ranges.
# ============================================================================
@dataclass(frozen=True, slots=True)
class NormalizationConfig:
<<<<<<< HEAD
    max_data_size_bits: float = 2.0e6        # data size ratio denominator
    max_workload_cycles: float = 1.0e9       # workload ratio denominator
    max_deadline_s: float = 30.0             # deadline ratio denominator
    max_queue_time_s: float = 10.0           # queue/workload time denominator
    max_distance_m: float = 1000.0           # distance denominator
=======
    max_data_size_bits: float = 1.7e6    # (1.5e6 + margin)
    max_workload_cycles: float = 3.3e9   # (3.0e9 + margin)
    max_deadline_s: float = 17.6         # (16.0 + margin)
    max_queue_time_s: float = 16.0           # queue/workload time denominator
    max_distance_m: float = 2700.0          # distance denominator d = sqrt(2130^2 + 1590^2)=2658 
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    path_loss_min: float = 3.0               # urban cell coefficient range
    path_loss_max: float = 4.0

    def normalize(self, value: float, scale: float) -> float:
        """Clamp ``value / scale`` into [0, 1]."""
        if scale <= 0:
            return 0.0
        ratio = value / scale
        if ratio < 0.0:
            return 0.0
        if ratio > 1.0:
            return 1.0
        return ratio

    def normalize_path_loss(self, coefficient: float) -> float:
        """Map a path-loss coefficient in [min, max] to [0, 1]."""
        span = self.path_loss_max - self.path_loss_min
        if span <= 0:
            return 0.0
        value = (coefficient - self.path_loss_min) / span
        return min(1.0, max(0.0, value))


# ============================================================================
# Urban grid + path loss model
# ----------------------------------------------------------------------------
# The urban area is split into `cell_size_m` square cells.  Each cell receives
# a mean path-loss exponent drawn uniformly from [path_loss_min, path_loss_max].
# At runtime the *actual* exponent for a link is sampled log-normally around
# that cell's mean (shadowing), which is the RATO-VFC style lognormal shadowing.
# ============================================================================
@dataclass(frozen=True, slots=True)
class UrbanGridConfig:
    cell_size_m: float = 100.0
<<<<<<< HEAD
    area_x_max: float = 2000.0               # metres, x extent of the map
    area_y_max: float = 1500.0               # metres, y extent of the map
=======
    area_x_max: float = 2130.0              # metres, x extent of the map
    area_y_max: float = 1590.0              # metres, y extent of the map
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    path_loss_min: float = 3.0
    path_loss_max: float = 4.0
    shadowing_sigma: float = 0.10            # lognormal spread around cell mean
    exponent_clamp_min: float = 2.0
    exponent_clamp_max: float = 6.0
    seed: int = 42


# ============================================================================
# Edge server placement
# ----------------------------------------------------------------------------
# Modular: swap `strategy` to change the deployment heuristic.  Currently the
# strategies implemented are "kmeans" (traffic/vehicle density clustering) and
# "central" (evenly spread anchor points across the map).
# ============================================================================
@dataclass(frozen=True, slots=True)
class PlacementConfig:
    strategy: str = "kmeans"                 # "kmeans" | "central"
<<<<<<< HEAD
    num_edge_servers: int = 3
    edge_coverage_radius_m: float = 1000.0   # wireless validity radius per edge
=======
    num_edge_servers: int = 10
    edge_coverage_radius_m: float = 300.0   # wireless validity radius per edge
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    random_state: int = 42
    max_iter: int = 100                      # K-Means iteration budget
    tol: float = 1e-4                        # K-Means convergence tolerance


# ============================================================================
# Multi-head regression (Phase 3)
# ----------------------------------------------------------------------------
# The regression input is the raw (blocks 1-5) normalized state.  The model
# outputs 3 outcomes (completion time, energy, deadline-miss logit) per each of
# the 5 stable action slots.  Only the actually-executed action is supervised
# (masked loss).
# ============================================================================
@dataclass(frozen=True, slots=True)
class RegressionConfig:
    hidden_sizes: tuple[int, ...] = (256, 256, 128)
    dropout: float = 0.1
    outcome_count: int = 3                   # (time, energy, miss_logit)
    action_count: int = NUM_ACTIONS
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
<<<<<<< HEAD
    epochs: int = 300
    batch_size: int = 128
    miss_loss_weight: float = 1.0            # weight on the BCE miss head
    device: str = "cpu"
=======
    epochs: int = 50
    batch_size: int = 512
    miss_loss_weight: float = 1.0            # weight on the BCE miss head
    device: str = "gpu" if __import__("torch").cuda.is_available() else "cpu"
>>>>>>> 877352841b18743b81cd2deb8d01201566cbf6bb
    checkpoint_dir: str = "data/saved_models"

    # Number of raw state features fed to the regression trunk (blocks 1-5).
    raw_feature_dim: int = 22


# ============================================================================
# Predictive DRL (Phase 4) -- MaskablePPO hyperparameters
# ============================================================================
@dataclass(frozen=True, slots=True)
class DRLTrainingConfig:
    total_timesteps: int = 200_000
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    gamma: float = 0.99
    gae_lambda: float = 0.95
    max_grad_norm: float = 0.5
    policy_net: tuple[int, ...] = (256, 128)
    value_net: tuple[int, ...] = (256, 128)
    device: str = "auto"
    checkpoint_dir: str = "data/saved_models"


# ============================================================================
# State dimension bookkeeping
# ============================================================================
BLOCK1_TASK = 3          # data size / workload / deadline ratios
BLOCK2_LOCAL = 3         # best queue / avg queue / idle core ratio
BLOCK3_CONTEXT = 1       # urban path-loss coefficient
BLOCK4_CANDIDATES = 12   # 3 nodes x (distance, best, avg, idle ratio)
BLOCK5_CLOUD = 3         # cloud best / avg / idle ratio
RAW_STATE_DIM = (
    BLOCK1_TASK + BLOCK2_LOCAL + BLOCK3_CONTEXT + BLOCK4_CANDIDATES + BLOCK5_CLOUD
)  # 22
PREDICTIONS_PER_ACTION = 3   # completion time, energy, deadline-miss probability
AUGMENTED_STATE_DIM = RAW_STATE_DIM + PREDICTIONS_PER_ACTION * NUM_ACTIONS  # 37


# ============================================================================
# Aggregate hyperparameters bundle
# ============================================================================
@dataclass(frozen=True, slots=True)
class Hyperparameters:
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    urban_grid: UrbanGridConfig = field(default_factory=UrbanGridConfig)
    placement: PlacementConfig = field(default_factory=PlacementConfig)
    regression: RegressionConfig = field(default_factory=RegressionConfig)
    drl: DRLTrainingConfig = field(default_factory=DRLTrainingConfig)


def default_hyperparameters() -> Hyperparameters:
    """Return a fully-populated hyperparameters bundle with sane defaults."""
    return Hyperparameters()
