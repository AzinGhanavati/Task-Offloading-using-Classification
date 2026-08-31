from __future__ import annotations

def eptask_compute_energy_j(
    required_cycles: float,
    frequency_hz: float,
    coefficient: float,
    exponent: float = 2.0,
) -> float:
    if min(required_cycles, frequency_hz, coefficient) < 0:
        raise ValueError("energy model inputs cannot be negative")
    return coefficient * (frequency_hz**exponent) * required_cycles

def eptask_transmission_energy_j(transmit_power_w: float, duration_s: float) -> float:
    if transmit_power_w < 0 or duration_s < 0:
        raise ValueError("power and duration cannot be negative")
    return transmit_power_w * duration_s

def dbm_to_watt(power_dbm: float) -> float:
    return 10.0 ** ((power_dbm - 30.0) / 10.0)

def watt_to_dbm(power_w: float) -> float:
    if power_w <= 0:
        raise ValueError("power_w must be positive")
    import math
    return 10.0 * math.log10(power_w) + 30.0