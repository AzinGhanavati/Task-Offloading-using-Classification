from dataclasses import dataclass

# ==========================================
# 1. HARDWARE PROFILES CONFIGURATION
# ==========================================
@dataclass(frozen=True, slots=True)
class HardwareProfile:
    core_count: int
    core_frequency_hz: float
    energy_coefficient: float
    energy_exponent: float
    queue_capacity: int | None = None

# ==========================================
# 2. WIRELESS NETWORK CONFIGURATION
# ==========================================
@dataclass(frozen=True, slots=True)
class RadioConfig:
    maximum_tx_power_dbm: float
    minimum_tx_power_dbm: float
    carrier_frequency_hz: float
    environment: str
    noisy_environment: bool
    rain_attenuation_db: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    traffic_level: str
    noise_profile: int
    packet_size_bits: int
    bandwidth_hz: float
    bandwidth_share: float
    max_retries: int
    retry_timeout_s: float
    default_coverage_radius_m: float

# ==========================================
# 3. WIRED NETWORK CONFIGURATION
# ==========================================
@dataclass(frozen=True, slots=True)
class WiredConfig:
    average_bandwidth_hz: float
    snr_db: float
    propagation_delay_s: float
    energy_per_bit_j: float

# ==========================================
# 4. MASTER SIMULATION CONFIGURATION
# ==========================================
@dataclass(frozen=True, slots=True)
class SimulationConfig:
    random_seed: int
    vehicle: HardwareProfile
    mobile_fog: HardwareProfile
    fixed_fog: HardwareProfile
    edge: HardwareProfile
    cloud: HardwareProfile
    radio: RadioConfig
    wired: WiredConfig

def default_simulation_config() -> SimulationConfig:
    """
    Returns a complete configuration object populated with 
    default values extracted from the reference papers.
    """
    return SimulationConfig(
        random_seed=42,
        
        # Vehicle: 4 cores, 1.0 GHz
        vehicle=HardwareProfile(
            core_count=4,
            core_frequency_hz=1.0e9,
            energy_coefficient=1.0e-27,
            energy_exponent=2.0,
            queue_capacity=None
        ),
        
        # Mobile Fog: 8 cores, 2.0 GHz
        mobile_fog=HardwareProfile(
            core_count=8,
            core_frequency_hz=2.0e9,
            energy_coefficient=1.0e-27,
            energy_exponent=2.0,
            queue_capacity=None
        ),
        
        # Fixed Fog: 16 cores, 3.0 GHz
        fixed_fog=HardwareProfile(
            core_count=16,
            core_frequency_hz=3.0e9,
            energy_coefficient=1.0e-27,
            energy_exponent=2.0,
            queue_capacity=None
        ),
        
        # Edge Server: 32 cores, 4.5 GHz
        edge=HardwareProfile(
            core_count=32,
            core_frequency_hz=4.5e9,
            energy_coefficient=1.0e-27,
            energy_exponent=2.0,
            queue_capacity=None
        ),
        
        # Cloud Server: 100 cores, 7.5 GHz
        cloud=HardwareProfile(
            core_count=100,
            core_frequency_hz=7.5e9,
            energy_coefficient=1.0e-27,
            energy_exponent=2.0,
            queue_capacity=None
        ),
        
        # Radio settings based on RATO VFC environment
        radio=RadioConfig(
            maximum_tx_power_dbm=30.0,
            minimum_tx_power_dbm=10.0,
            carrier_frequency_hz=5.0e9,
            environment="medium_urban",
            noisy_environment=True,
            rain_attenuation_db=0.0,
            tx_antenna_gain_dbi=27.0,
            rx_antenna_gain_dbi=-5.0,
            traffic_level="orange",
            noise_profile=1,
            packet_size_bits=8192,
            bandwidth_hz=150.0e6,
            bandwidth_share=1.0,
            max_retries=3,
            retry_timeout_s=0.05,
            default_coverage_radius_m=150.0
        ),
        
        # Wired settings for Fog/Edge to Cloud connections
        wired=WiredConfig(
            average_bandwidth_hz=60.0e6,
            snr_db=30.0,
            propagation_delay_s=0.01,
            energy_per_bit_j=1.0e-9
        )
    )