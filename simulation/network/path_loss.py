from __future__ import annotations
import math

PATH_LOSS_EXPONENTS: dict[str, tuple[float, float]] = {
    "near_free_space": (2.3, 2.4),
    "good_urban": (2.5, 2.7),
    "medium_urban": (2.7, 3.0),
    "bad_urban": (2.9, 3.3),
}

TRAFFIC_NOISE_DBM: dict[str, tuple[float, float]] = {
    "green": (-110.0, -106.0),
    "orange": (-105.0, -103.0),
    "red": (-100.0, -100.0),
    "black": (-95.0, -97.0),
}

def rato_path_loss_db(
    distance_m: float,
    carrier_frequency_hz: float,
    *,
    environment: str,
    noisy: bool,
    rain_attenuation_db: float = 0.0,
) -> float:
    if carrier_frequency_hz <= 0:
        raise ValueError("carrier_frequency_hz must be positive")
    try:
        stable_n, noisy_n = PATH_LOSS_EXPONENTS[environment]
    except KeyError as exc:
        raise ValueError(f"unknown RATO environment: {environment}") from exc
    
    n = noisy_n if noisy else stable_n
    d = max(1.0, float(distance_m))
    c = 3.0e8
    
    return (
        10.0 * n * math.log10(d)
        + 10.0 * n * math.log10(carrier_frequency_hz)
        + 10.0 * n * math.log10(4.0 * math.pi / c)
        + max(0.0, rain_attenuation_db)
    )

def rato_traffic_noise_dbm(traffic_level: str, profile: int = 1) -> float:
    if profile not in {1, 2}:
        raise ValueError("RATO noise profile must be 1 or 2")
    try:
        values = TRAFFIC_NOISE_DBM[traffic_level]
    except KeyError as exc:
        raise ValueError(f"unknown traffic level: {traffic_level}") from exc
    return values[profile - 1]